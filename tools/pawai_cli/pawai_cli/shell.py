from __future__ import annotations

import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def run(argv: Iterable[str], cwd: Path | None = None, timeout: int | None = None) -> Result:
    try:
        proc = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        return Result(124, exc.stdout or "", exc.stderr or f"timeout after {timeout}s")
    except OSError as exc:
        return Result(127, "", str(exc))


def stream(argv: Iterable[str], cwd: Path | None = None) -> int:
    try:
        return subprocess.call(list(argv), cwd=str(cwd) if cwd else None)
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 127


def repo_root() -> Path:
    override = os.getenv("PAWAI_REPO_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    res = run(["git", "rev-parse", "--show-toplevel"], timeout=5)
    if res.ok and res.stdout.strip():
        return Path(res.stdout.strip()).resolve()
    return Path.cwd().resolve()


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def jetson_host() -> str:
    return env("JETSON_HOST", "jetson-nano")


def jetson_repo() -> str:
    return env("JETSON_REPO", "/home/jetson/elder_and_dog")


def jetson_hostname_hint() -> str:
    return env("JETSON_HOSTNAME_HINT", "jetson")


def ssh_args(command: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        jetson_host(),
        command,
    ]


def run_remote(command: str, timeout: int | None = None) -> Result:
    return run(ssh_args(command), timeout=timeout)


def stream_remote(command: str) -> int:
    return stream(ssh_args(command))


def local_identity() -> str:
    user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    host = socket.gethostname().split(".")[0] or "unknown-host"
    return f"{user}@{host}"
