from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from . import shell


def _remote_lock_path() -> str:
    """Resolve full path locally to avoid depending on Jetson-side $JETSON_REPO env."""
    return f"{shell.jetson_repo()}/.pawai-demo-lock"


LOCK_FLOCK_PATH = "/tmp/pawai-demo-lock.flock"

STARTING_STALE_MINUTES = 10
RUNNING_STALE_HOURS = 4


@dataclass
class Lock:
    user: str
    host: str
    branch: str
    sha: str
    state: str  # "starting" | "running"
    start_time: str  # ISO 8601 with tz
    demo_mode: str = "full"
    tmux_session: str = "demo"
    lane: str = "brain"

    @classmethod
    def read(cls) -> Optional["Lock"]:
        """Read lock from Jetson via SSH; return None if absent or malformed."""
        result = shell.run_remote(f"cat {_remote_lock_path()} 2>/dev/null", timeout=5)
        if not result.ok or not result.stdout.strip():
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        try:
            data.setdefault("lane", "brain")
            data.setdefault("tmux_session", "demo")
            return cls(**data)
        except TypeError:
            return None

    @classmethod
    def acquire(cls, user: str, host: str, branch: str, sha: str,
                state: str = "starting", demo_mode: str = "full",
                tmux_session: str = "demo", lane: str = "brain") -> Optional["Lock"]:
        """Atomically write a lock if absent.

        Exit code semantics from the remote `flock` command:
        - 0  → wrote new lock (success)
        - 17 → lock file already exists (someone holds it; do NOT retry)
        - other non-zero → flock contention or transient SSH failure; retry up to 3× with 2s backoff
        """
        now = datetime.now(timezone.utc).isoformat()
        lk = cls(user=user, host=host, branch=branch, sha=sha,
                 state=state, start_time=now, demo_mode=demo_mode,
                 tmux_session=tmux_session, lane=lane)
        payload = json.dumps(asdict(lk)).replace("'", "'\\''")
        cmd = (
            f"flock -n {LOCK_FLOCK_PATH} -c '"
            f"if [ -f {_remote_lock_path()} ]; then exit 17; fi; "
            f"printf %s '\\''{payload}'\\'' > {_remote_lock_path()}.tmp && "
            f"mv {_remote_lock_path()}.tmp {_remote_lock_path()}'"
        )
        for attempt in range(3):
            result = shell.run_remote(cmd, timeout=10)
            if result.code == 0:
                return lk
            if result.code == 17:
                return None  # someone owns the lock — do not retry
            # transient: flock contention or SSH hiccup → backoff and retry
            if attempt < 2:
                time.sleep(2)
        return None  # exhausted retries

    def transition_to(self, new_state: str) -> bool:
        """Update state field on existing lock. Caller must own it."""
        now = datetime.now(timezone.utc).isoformat()
        updated = asdict(self)
        updated["state"] = new_state
        updated["start_time"] = now  # bump for running TTL
        payload = json.dumps(updated).replace("'", "'\\''")
        cmd = (
            f"flock -n {LOCK_FLOCK_PATH} -c '"
            f"printf %s '\\''{payload}'\\'' > {_remote_lock_path()}.tmp && "
            f"mv {_remote_lock_path()}.tmp {_remote_lock_path()}'"
        )
        return shell.run_remote(cmd, timeout=10).ok

    @classmethod
    def release(cls) -> bool:
        result = shell.run_remote(f"rm -f {_remote_lock_path()}", timeout=5)
        return result.ok


def is_stale(lk: Lock) -> Optional[str]:
    """Return 'starting' / 'running' if stale, else None."""
    try:
        start = datetime.fromisoformat(lk.start_time)
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    age = now - start
    if lk.state == "starting" and age.total_seconds() > STARTING_STALE_MINUTES * 60:
        return "starting"
    if lk.state == "running" and age.total_seconds() > RUNNING_STALE_HOURS * 3600:
        return "running"
    return None


def is_own_lock(lk: Lock, user: str, host: str) -> bool:
    return lk.user == user and lk.host == host
