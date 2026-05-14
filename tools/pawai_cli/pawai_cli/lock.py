from __future__ import annotations

import json
import shlex
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
        """DEPRECATED — use `transition_if_owned`. Writes without owner check;
        kept only to avoid breaking callers that haven't migrated yet."""
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

    def transition_if_owned(self, new_state: str, user: str, host: str) -> bool:
        """Atomically update state only if lock on Jetson still matches user/host.

        Prevents a long-running `start.sh` from silently overwriting a lock
        that was force-taken during that window. Returns False if the lock
        was missing or had a different owner.
        """
        now = datetime.now(timezone.utc).isoformat()
        updated = asdict(self)
        updated["state"] = new_state
        updated["start_time"] = now
        payload = json.dumps(updated)
        lock_path = _remote_lock_path()
        py_script = (
            "import json, os, sys\n"
            "p = os.environ['LOCK_FILE']\n"
            "if not os.path.exists(p):\n"
            "    sys.exit(17)\n"
            "d = json.load(open(p))\n"
            "if d.get('user') != os.environ['EXPECT_USER'] "
            "or d.get('host') != os.environ['EXPECT_HOST']:\n"
            "    sys.exit(17)\n"
            "open(p + '.tmp', 'w').write(os.environ['PAYLOAD'])\n"
            "os.replace(p + '.tmp', p)\n"
            "sys.exit(0)\n"
        )
        cmd = (
            f"EXPECT_USER={shlex.quote(user)} "
            f"EXPECT_HOST={shlex.quote(host)} "
            f"LOCK_FILE={shlex.quote(lock_path)} "
            f"PAYLOAD={shlex.quote(payload)} "
            f"flock -n {shlex.quote(LOCK_FLOCK_PATH)} "
            f"python3 -c {shlex.quote(py_script)}"
        )
        return shell.run_remote(cmd, timeout=10).code == 0

    @classmethod
    def release(cls) -> bool:
        """DEPRECATED — use `release_if_owned`. Bare unlink kept for
        emergency manual cleanup only; production callers must verify owner."""
        result = shell.run_remote(f"rm -f {_remote_lock_path()}", timeout=5)
        return result.ok

    @classmethod
    def release_if_owned(cls, user: str, host: str) -> bool:
        """Atomically remove the remote lock only if user/host still match."""
        lock_path = _remote_lock_path()
        py_script = (
            "import json, os, sys\n"
            "p = os.environ['LOCK_FILE']\n"
            "if not os.path.exists(p):\n"
            "    sys.exit(0)\n"
            "d = json.load(open(p))\n"
            "if d.get('user') == os.environ['EXPECT_USER'] "
            "and d.get('host') == os.environ['EXPECT_HOST']:\n"
            "    os.remove(p)\n"
            "    sys.exit(0)\n"
            "sys.exit(17)\n"
        )
        cmd = (
            f"EXPECT_USER={shlex.quote(user)} "
            f"EXPECT_HOST={shlex.quote(host)} "
            f"LOCK_FILE={shlex.quote(lock_path)} "
            f"flock -n {shlex.quote(LOCK_FLOCK_PATH)} "
            f"python3 -c {shlex.quote(py_script)}"
        )
        return shell.run_remote(cmd, timeout=10).code == 0


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
