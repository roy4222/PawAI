"""Target execution abstraction for jetson-verify.

Detects whether running on Jetson (local) or a remote host (WSL/etc),
and routes commands accordingly. Designed for reuse by other skills
(jetson-deploy, go2-debug).
"""
import os
import shlex
import subprocess


def detect_target_env() -> str:
    """Return 'local_jetson' if on Jetson, else 'remote_jetson'."""
    if os.path.exists("/etc/nv_tegra_release"):
        return "local_jetson"
    return "remote_jetson"


def build_target_command(cmd: str, env: str) -> list[str]:
    """Build argv list for subprocess.run().

    local_jetson:  ["bash", "-lc", cmd]
    remote_jetson: ["ssh", "$JETSON_HOST", "cd $JETSON_REPO && bash -lc <quoted>"]
    """
    if env == "local_jetson":
        return ["bash", "-lc", cmd]
    host = os.getenv("JETSON_HOST", "jetson-nano")
    repo = os.getenv("JETSON_REPO", "/home/jetson/elder_and_dog")
    remote_cmd = f"cd {shlex.quote(repo)} && bash -lc {shlex.quote(cmd)}"
    return ["ssh", host, remote_cmd]


def exec_on_target(cmd: str, env: str, timeout_sec: int = 10) -> tuple[int, str, str]:
    """Execute command on target, return (returncode, stdout, stderr).

    Return codes:
      0+  = command's own exit code
      -1  = transport failure (SSH unreachable, OSError)
      -2  = timeout exceeded
    """
    argv = build_target_command(cmd, env)
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (-2, "", f"timeout after {timeout_sec}s")
    except OSError as e:
        return (-1, "", str(e))
