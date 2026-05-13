"""Platform detection and policy gate for the PawAI CLI."""

from __future__ import annotations

import os
import platform as _stdlib_platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PlatformInfo:
    kind: str
    supported: bool
    reason: str


def _uname_system() -> str:
    return _stdlib_platform.system()


def _read_proc_version() -> str:
    try:
        return Path("/proc/version").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _env_wsl_distro() -> str:
    return os.environ.get("WSL_DISTRO_NAME", "")


def detect() -> PlatformInfo:
    """Classify the current platform for PawAI CLI support."""
    system = _uname_system()
    if system == "Darwin":
        return PlatformInfo(kind="macos", supported=True, reason="")
    if system == "Windows":
        return PlatformInfo(
            kind="windows_native",
            supported=False,
            reason="Windows native unsupported (PowerShell / CMD / Git Bash).",
        )
    if system == "Linux":
        proc = _read_proc_version().lower()
        wsl_distro = _env_wsl_distro()
        if "microsoft" in proc or wsl_distro:
            if "wsl2" in proc:
                return PlatformInfo(kind="wsl2", supported=True, reason="")
            major = _linux_major_version(proc)
            if major >= 5:
                return PlatformInfo(kind="wsl2", supported=True, reason="")
            return PlatformInfo(
                kind="wsl1",
                supported=False,
                reason="WSL1 unsupported - upgrade to WSL2.",
            )
        return PlatformInfo(kind="linux", supported=True, reason="")
    return PlatformInfo(
        kind="unknown",
        supported=False,
        reason=f"Unrecognized platform '{system}'.",
    )


def _linux_major_version(proc_version: str) -> int:
    parts = proc_version.split()
    if len(parts) < 2:
        return 0
    first = parts[1].split(".", maxsplit=1)[0]
    try:
        return int(first)
    except ValueError:
        return 0


def check_repo_path(info: PlatformInfo, repo: Path) -> Optional[str]:
    """Return an error message if the repo path violates platform policy."""
    if info.kind != "wsl2":
        return None
    try:
        resolved = str(repo.resolve())
    except OSError:
        resolved = str(repo)
    if resolved.startswith("/mnt/c/") or resolved.startswith("/mnt/d/"):
        return (
            "Repo path is under /mnt/c/ or /mnt/d/ (Windows filesystem). "
            "I/O is slower and rsync semantics break."
        )
    return None


def assert_supported(repo: Path) -> None:
    """Exit with code 10 when the current platform or repo path is unsupported."""
    info = detect()
    repo_err = check_repo_path(info, repo)
    if info.supported and repo_err is None:
        return
    _print_unsupported(info, repo_err)
    sys.exit(10)


def _print_unsupported(info: PlatformInfo, repo_err: Optional[str]) -> None:
    print(f"✗ Platform: {info.reason or info.kind}")
    if repo_err:
        print(f"✗ Repo: {repo_err}")
    print()
    print("PawAI CLI requires macOS, Linux, or WSL2 Ubuntu.")
    if info.kind == "windows_native":
        print("  -> Install WSL2:  wsl --install -d Ubuntu")
        print("  -> Move repo:    git clone <url> ~/elder_and_dog   (NOT under /mnt/c)")
        print("  -> Reopen terminal in: Windows Terminal -> Ubuntu")
    elif info.kind == "wsl1":
        print("  -> Upgrade to WSL2: wsl --set-version Ubuntu 2")
    elif repo_err:
        print("  -> Move repo into Linux home:  cd ~ && git clone <url> elder_and_dog")
    print("  See: docs/pawai_cli/platform-policy.md")
