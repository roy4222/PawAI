# PawAI CLI Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land 11 surgical fixes that promote `pawai` CLI from tool collection to Jetson on-site collaboration console, before 2026-05-16 (5/18 demo prep buffer).

**Architecture:** Each task is one Item from the umbrella spec (`docs/superpowers/specs/2026-05-13-pawai-cli-collab-console-design.md`). Items are grouped into 5 batches by file-touch locality to minimize merge conflicts during landing. Each task = 1 commit. Tests run via `python3 -m pytest tools/pawai_cli`. Smoke verification runs against actual Jetson over SSH alias `jetson` (Tailscale 100.83.109.89).

**Tech Stack:** Python 3.10+ click CLI, pytest, bash 4+ scripts, Jetson Orin Nano (Ubuntu 22.04 + ROS2 Humble) over SSH.

**Source-of-truth files:**
- Spec: `docs/superpowers/specs/2026-05-13-pawai-cli-collab-console-design.md` (commit `6388a08`)
- Cross-batch invariants: I1 platform policy, I2 lock schema, I3 output contract, I4 config precedence, I5 redaction
- Existing CLI: `tools/pawai_cli/pawai_cli/` (1586 LOC, 7 modules)
- Existing tests: `tools/pawai_cli/tests/test_{cache,cli,lock,network}.py`

**Important nuance (Roy flagged on review):** I5 redaction whitelist mentions `~/.ssh/*` — that is for *log/debug-bundle redaction*, **NOT** rsync exclude. Item 2's rsync exclude is **repo-relative**: `.env`, `.env.*`, `.env.local`, `.ssh/`. Do not conflate the two.

---

## Pre-flight (do once before starting)

- [ ] **Verify clean working tree + reachable Jetson**

```bash
cd /Users/lubaiyu/elder_and_dog
git status --short          # expect: clean
pawai doctor --cache 0      # expect: 0 blocking · 0 warnings
ssh jetson "hostname"       # expect: orinnano-super
```

If any of the above fail, stop and resolve before proceeding.

- [ ] **Confirm existing test suite is green**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 70 passed
```

If not 70 passed, stop. The baseline must be clean before adding new tests.

---

## Batch 1: Foundation — Platform Gate (Item 0)

### Task 1: Create `platform.py` with detection logic + unit tests

**Files:**
- Create: `tools/pawai_cli/pawai_cli/platform.py`
- Create: `tools/pawai_cli/tests/test_platform.py`

This task lands the I1 invariant. Detection has 5 branches: macOS, Linux native, WSL2, WSL1, Windows native. Plus a `/mnt/c/` repo-path check.

- [ ] **Step 1: Write failing tests**

Create `tools/pawai_cli/tests/test_platform.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pawai_cli import platform as plat


def test_detect_macos():
    with patch("pawai_cli.platform._uname_system", return_value="Darwin"):
        info = plat.detect()
    assert info.kind == "macos"
    assert info.supported is True


def test_detect_linux_native():
    with patch("pawai_cli.platform._uname_system", return_value="Linux"), \
         patch("pawai_cli.platform._read_proc_version", return_value="Linux 6.5.0 generic"), \
         patch("pawai_cli.platform._env_wsl_distro", return_value=""):
        info = plat.detect()
    assert info.kind == "linux"
    assert info.supported is True


def test_detect_wsl2():
    with patch("pawai_cli.platform._uname_system", return_value="Linux"), \
         patch("pawai_cli.platform._read_proc_version",
               return_value="Linux 5.15.146.1-microsoft-standard-WSL2"), \
         patch("pawai_cli.platform._env_wsl_distro", return_value="Ubuntu"):
        info = plat.detect()
    assert info.kind == "wsl2"
    assert info.supported is True


def test_detect_wsl1():
    with patch("pawai_cli.platform._uname_system", return_value="Linux"), \
         patch("pawai_cli.platform._read_proc_version",
               return_value="Linux 4.4.0-19041-Microsoft (Microsoft@Microsoft.com)"), \
         patch("pawai_cli.platform._env_wsl_distro", return_value="Ubuntu"):
        info = plat.detect()
    assert info.kind == "wsl1"
    assert info.supported is False


def test_detect_windows_native():
    with patch("pawai_cli.platform._uname_system", return_value="Windows"):
        info = plat.detect()
    assert info.kind == "windows_native"
    assert info.supported is False


def test_mnt_c_repo_path_rejected():
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    repo = Path("/mnt/c/Users/foo/elder_and_dog")
    err = plat.check_repo_path(info, repo)
    assert err is not None
    assert "/mnt/c" in err


def test_home_repo_path_accepted():
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    repo = Path("/home/user/elder_and_dog")
    assert plat.check_repo_path(info, repo) is None


def test_assert_supported_passes_on_macos():
    with patch("pawai_cli.platform.detect",
               return_value=plat.PlatformInfo(kind="macos", supported=True, reason="")), \
         patch("pawai_cli.platform.check_repo_path", return_value=None):
        plat.assert_supported(Path("/Users/foo/repo"))  # no exception


def test_assert_supported_exits_on_windows_native(capsys):
    info = plat.PlatformInfo(kind="windows_native", supported=False,
                             reason="Windows native unsupported")
    with patch("pawai_cli.platform.detect", return_value=info):
        with pytest.raises(SystemExit) as excinfo:
            plat.assert_supported(Path("C:/Users/foo/repo"))
    assert excinfo.value.code == 10
    captured = capsys.readouterr()
    assert "Windows native unsupported" in captured.out
    assert "wsl --install" in captured.out


def test_assert_supported_exits_on_mnt_c(capsys):
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    with patch("pawai_cli.platform.detect", return_value=info):
        with pytest.raises(SystemExit) as excinfo:
            plat.assert_supported(Path("/mnt/c/Users/foo/repo"))
    assert excinfo.value.code == 10
    captured = capsys.readouterr()
    assert "/mnt/c" in captured.out
```

- [ ] **Step 2: Run tests, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_platform.py -v
# expect: collection error (module pawai_cli.platform does not exist)
```

- [ ] **Step 3: Implement `platform.py`**

Create `tools/pawai_cli/pawai_cli/platform.py`:

```python
"""Platform detection and I1 policy gate.

Supported: macOS, Linux native, WSL2 Ubuntu.
Unsupported: WSL1, Windows native (PowerShell/CMD/Git Bash), repos under /mnt/c.

Called from CLI entry points via assert_supported(). On unsupported platform,
exits with code 10 (per I3) after printing fix instructions.
"""

from __future__ import annotations

import os
import platform as _stdlib_platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# --- low-level signal collectors (mockable in tests) ------------------------

def _uname_system() -> str:
    return _stdlib_platform.system()


def _read_proc_version() -> str:
    try:
        return Path("/proc/version").read_text(errors="replace")
    except (OSError, FileNotFoundError):
        return ""


def _env_wsl_distro() -> str:
    return os.environ.get("WSL_DISTRO_NAME", "")


# --- detection result -------------------------------------------------------

@dataclass(frozen=True)
class PlatformInfo:
    kind: str       # "macos" | "linux" | "wsl2" | "wsl1" | "windows_native" | "unknown"
    supported: bool
    reason: str     # human-readable fix instruction stub; empty if supported


def detect() -> PlatformInfo:
    """Classify the current platform into one of 6 kinds."""
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

        # WSL detection: /proc/version contains "microsoft"
        if "microsoft" in proc or wsl_distro:
            # WSL2 marker: kernel 5.x or higher AND WSL_DISTRO_NAME set
            # WSL1 marker: kernel 4.x typically
            if "wsl2" in proc or (wsl_distro and "wsl2" in proc):
                return PlatformInfo(kind="wsl2", supported=True, reason="")
            # Heuristic: WSL1 has older kernel (4.x); WSL2 is 5.x+
            # If WSL marker is present but no "wsl2" string, look at kernel ver
            import re
            m = re.search(r"linux\s+(\d+)\.", proc)
            major = int(m.group(1)) if m else 0
            if major >= 5:
                return PlatformInfo(kind="wsl2", supported=True, reason="")
            return PlatformInfo(
                kind="wsl1",
                supported=False,
                reason="WSL1 unsupported — upgrade to WSL2.",
            )

        return PlatformInfo(kind="linux", supported=True, reason="")

    return PlatformInfo(
        kind="unknown",
        supported=False,
        reason=f"Unrecognized platform '{system}'.",
    )


# --- repo path policy -------------------------------------------------------

def check_repo_path(info: PlatformInfo, repo: Path) -> Optional[str]:
    """Return error string if repo path is rejected, else None.

    On WSL2, repo under /mnt/c/ is rejected (10x slower I/O, breaks rsync).
    """
    if info.kind == "wsl2":
        try:
            resolved = str(repo.resolve())
        except OSError:
            resolved = str(repo)
        if resolved.startswith("/mnt/c/") or resolved.startswith("/mnt/d/"):
            return (
                "Repo path is under /mnt/c/ (Windows filesystem). "
                "I/O is ~10x slower and rsync semantics break."
            )
    return None


# --- enforcement ------------------------------------------------------------

def _print_unsupported(info: PlatformInfo, repo_err: Optional[str]) -> None:
    """Print the I1-prescribed fix message to stdout."""
    print(f"✗ Platform: {info.reason or info.kind}")
    if repo_err:
        print(f"✗ Repo: {repo_err}")
    print()
    print("PawAI CLI requires macOS, Linux, or WSL2 Ubuntu.")
    if info.kind == "windows_native":
        print("  → Install WSL2:  wsl --install -d Ubuntu")
        print("  → Move repo:    git clone <url> ~/elder_and_dog   (NOT under /mnt/c)")
        print("  → Reopen terminal in: Windows Terminal → Ubuntu")
    elif info.kind == "wsl1":
        print("  → Upgrade to WSL2: wsl --set-version Ubuntu 2")
    elif repo_err:
        print("  → Move repo into Linux home:  cd ~ && git clone <url> elder_and_dog")
    print("  See: docs/pawai_cli/platform-policy.md")


def assert_supported(repo: Path) -> None:
    """Gate: exit(10) if platform or repo path is unsupported.

    Called from every command entry point. Cheap (< 1ms).
    """
    info = detect()
    repo_err = check_repo_path(info, repo)
    if not info.supported or repo_err is not None:
        _print_unsupported(info, repo_err)
        sys.exit(10)
```

- [ ] **Step 4: Run tests, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_platform.py -v
# expect: 10 passed
```

- [ ] **Step 5: Wire `assert_supported()` into CLI entry**

Edit `tools/pawai_cli/pawai_cli/main.py` lines 125-129:

Current:
```python
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def cli() -> None:
    """PawAI development and Jetson orchestration CLI."""
    _load_env(shell.repo_root())
```

Change to:
```python
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def cli() -> None:
    """PawAI development and Jetson orchestration CLI."""
    from . import platform as _plat
    root = shell.repo_root()
    _plat.assert_supported(root)
    _load_env(root)
```

- [ ] **Step 6: Add platform line as the first item in doctor output**

Edit `tools/pawai_cli/pawai_cli/main.py` inside `doctor()`, right after `emit("────────────────────────")` (around line 181). Insert:

```python
    # == Platform == (I1)
    from . import platform as _plat
    pinfo = _plat.detect()
    repo_err = _plat.check_repo_path(pinfo, root)
    emit(f"== Platform ==")
    if pinfo.supported and repo_err is None:
        ok(f"Platform: {pinfo.kind}")
    else:
        fail(f"Platform: {pinfo.reason or pinfo.kind}{' + ' + repo_err if repo_err else ''}")
    emit("")
```

(Note: this is non-blocking once `cli()` has already gated. It is a *display* item for `doctor` output completeness.)

- [ ] **Step 7: Smoke test**

```bash
# 1. CLI gate doesn't break on macOS
pawai --help
# expect: normal help output, no platform error

# 2. doctor shows Platform line
pawai doctor --cache 0 | head -5
# expect: first item after divider is `== Platform ==` with `✓ Platform: macos`
```

- [ ] **Step 8: Run full test suite to confirm no regressions**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 80 passed (70 baseline + 10 new platform tests)
```

- [ ] **Step 9: Commit**

```bash
git add tools/pawai_cli/pawai_cli/platform.py \
        tools/pawai_cli/tests/test_platform.py \
        tools/pawai_cli/pawai_cli/main.py
git commit -m "$(cat <<'EOF'
feat(pawai_cli): I1 platform gate — macOS/Linux/WSL2 only (Phase 1 item 0)

New platform.py classifies into 6 kinds (macos/linux/wsl2/wsl1/windows_native/
unknown) and rejects /mnt/c repo paths. cli() entry point calls
assert_supported() which exits 10 with fix instructions for unsupported
platforms. doctor() prints platform line as first diagnostic block.

10 unit tests cover all detection branches + repo path guard.

Spec: docs/superpowers/specs/2026-05-13-pawai-cli-collab-console-design.md §I1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch 2: Detection Truthfulness (Items 7, 1, 5)

These three tasks fix doctor/status from emitting false-positive ✓ signals.

### Task 2: Item 7 — Tailscale `online=false` must FAIL

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (doctor Tailscale section, ~line 187-210)
- Modify: `tools/pawai_cli/tests/test_cli.py` (add doctor offline-peer test)

- [ ] **Step 1: Read existing doctor test to learn patterns**

```bash
grep -n "doctor\|find_jetson_peer" tools/pawai_cli/tests/test_cli.py | head -20
```

If `test_cli.py` does not yet exercise `doctor` with mocked peers, you will add a new test below. If it does, fold the new assertions into the existing test.

- [ ] **Step 2: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
def test_doctor_treats_offline_tailscale_peer_as_fail():
    """When Tailscale peer is matched but online=False, doctor must FAIL."""
    from click.testing import CliRunner
    from pawai_cli import main as cli_main

    offline_peer = {"hostname": "orinnano-super", "ip": "100.83.109.89", "online": False}
    with patch("pawai_cli.network.find_jetson_peer", return_value=offline_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value=None), \
         patch("pawai_cli.network.jetson_go2_link", return_value=None), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=False), \
         patch("pawai_cli.network.gateway_8080_status", return_value="SKIP"), \
         patch("pawai_cli.shell.run") as mock_run:
        # Make all local probes succeed minimally
        from pawai_cli.shell import Result
        mock_run.return_value = Result(code=0, stdout="git version 2.40", stderr="")
        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["doctor", "--cache", "0"])
    # exit 2 = blocking failures present (current convention; Phase 1 keeps this)
    assert result.exit_code != 0
    assert "online=False" in result.output or "offline" in result.output.lower()
    # The fix instruction must be present
    assert "tailscale up" in result.output or "logged out" in result.output.lower()
```

You will need this import at the top of the file if not already present:
```python
from unittest.mock import patch
```

- [ ] **Step 3: Run test, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_doctor_treats_offline_tailscale_peer_as_fail -v
# expect: AssertionError (current code emits ✓ even when peer is offline)
```

- [ ] **Step 4: Implement fix in `doctor()`**

Edit `tools/pawai_cli/pawai_cli/main.py` around lines 194-210. Current code:

```python
    else:
        detected_ip = peer["ip"]
        emit(f"  ✓ Tailscale peer '{peer['hostname']}' online={peer['online']} ip={detected_ip}")
        if env_ip and env_ip != detected_ip:
            ...
```

Change to:

```python
    else:
        detected_ip = peer["ip"]
        if not peer.get("online", False):
            blocking += 1
            emit(f"  ✗ Tailscale peer '{peer['hostname']}' is offline (last seen unknown)")
            emit(f"    → on Jetson:  sudo tailscale up   (peer may be logged out)")
            emit(f"    → or check Jetson Wi-Fi / internet route")
        else:
            emit(f"  ✓ Tailscale peer '{peer['hostname']}' online=True ip={detected_ip}")
        if env_ip and env_ip != detected_ip:
            emit(f"  ⚠ JETSON_TAILSCALE_IP={env_ip} but Tailscale reports {detected_ip} (mismatch)")
            emit(f"    → run `pawai doctor --fix` to update .env.local")
            if fix:
                answer = click.prompt(
                    f"\nUpdate JETSON_TAILSCALE_IP in .env.local from {env_ip} to {detected_ip}?",
                    default="n", show_default=True,
                )
                if answer.lower().startswith("y"):
                    _patch_env_local(Path(shell.repo_root()) / ".env.local",
                                     "JETSON_TAILSCALE_IP", detected_ip)
                    emit(f"  ✓ wrote JETSON_TAILSCALE_IP={detected_ip} to .env.local")
        elif not env_ip:
            emit(f"  ℹ JETSON_TAILSCALE_IP unset — CLI will use detected {detected_ip}")
```

Also update the `Network topology` section a few lines below (around line 215-218):

Current:
```python
    if peer is None:
        emit("  ✗ local → Jetson Tailscale: no peer found (see Tailscale section above)")
    else:
        emit(f"  ✓ local → Jetson Tailscale: OK {peer['ip']}")
```

Change to:
```python
    if peer is None:
        emit("  ✗ local → Jetson Tailscale: no peer found (see Tailscale section above)")
    elif not peer.get("online", False):
        emit(f"  ✗ local → Jetson Tailscale: peer offline (see Tailscale section above)")
    else:
        emit(f"  ✓ local → Jetson Tailscale: OK {peer['ip']}")
```

- [ ] **Step 5: Run test, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_doctor_treats_offline_tailscale_peer_as_fail -v
# expect: PASS
```

- [ ] **Step 6: Run full test suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 81 passed (80 + 1 new)
```

- [ ] **Step 7: Smoke test against real Jetson**

```bash
# When Jetson is online and reachable (current state):
pawai doctor --cache 0 | head -10
# expect: ✓ Tailscale peer 'orinnano-super' online=True ip=...
```

- [ ] **Step 8: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "$(cat <<'EOF'
fix(pawai_cli): doctor — Tailscale offline peer is now FAIL not OK (Phase 1 item 7)

Previously doctor emitted ✓ even when `tailscale status --json` showed
online=False (peer logged out or out of contact). Today's morning session
spent ~30 min hunting "why is SSH not working" before noticing the
online=False in the existing OK line.

Now: offline peer → ✗ with `sudo tailscale up` fix instruction. Network
topology line also flips to ✗ when peer is offline.

Spec: §Phase 1 item 7

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Item 1 — Gateway 8080 severity wires `Lock.read().state`

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (doctor Gateway section, line 248-254)
- Modify: `tools/pawai_cli/tests/test_cli.py`

The current code sets `lock_state = None` as a TODO placeholder. We wire it to `Lock.read().state`. If lock is `running`, gateway down → FAIL (not SKIP).

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
def test_doctor_gateway_fails_when_running_lock_and_8080_down():
    """If a running lock exists and Gateway 8080 is down, severity is FAIL."""
    from click.testing import CliRunner
    from pawai_cli import main as cli_main
    from pawai_cli.lock import Lock

    fake_lock = Lock(
        user="alice", host="alice-mac", branch="main", sha="abc1234",
        state="running",
        start_time="2026-05-13T10:00:00+00:00",
        demo_mode="full", tmux_session="demo", lane="brain",
    )
    online_peer = {"hostname": "orinnano-super", "ip": "100.83.109.89", "online": True}

    with patch("pawai_cli.network.find_jetson_peer", return_value=online_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value="wlan0"), \
         patch("pawai_cli.network.jetson_go2_link",
               return_value={"iface": "eth0", "ip": "192.168.123.10/24"}), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=True), \
         patch("pawai_cli.lock.Lock.read", return_value=fake_lock), \
         patch("pawai_cli.network.gateway_8080_status") as mock_gw, \
         patch("pawai_cli.shell.run") as mock_run:
        from pawai_cli.shell import Result
        mock_run.return_value = Result(code=0, stdout="git version 2.40", stderr="")
        mock_gw.return_value = "FAIL"

        runner = CliRunner()
        runner.invoke(cli_main.cli, ["doctor", "--cache", "0"])
        # Assert gateway_8080_status was called with lock_state="running"
        assert mock_gw.call_args.kwargs.get("lock_state") == "running" \
            or (len(mock_gw.call_args.args) > 1 and mock_gw.call_args.args[1] == "running")
```

- [ ] **Step 2: Run test, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_doctor_gateway_fails_when_running_lock_and_8080_down -v
# expect: FAIL (lock_state is hardcoded None in main.py:248)
```

- [ ] **Step 3: Implement fix**

Edit `tools/pawai_cli/pawai_cli/main.py` around line 248. Current:

```python
    lock_state = None  # L2 will populate this from lock module
    gw_status = network.gateway_8080_status(expect_demo=expect_demo, lock_state=lock_state)
```

Change to:

```python
    from .lock import Lock as _Lock
    active_lock = _Lock.read()
    lock_state = active_lock.state if active_lock is not None else None
    gw_status = network.gateway_8080_status(expect_demo=expect_demo, lock_state=lock_state)
```

- [ ] **Step 4: Run test, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_doctor_gateway_fails_when_running_lock_and_8080_down -v
# expect: PASS
```

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 82 passed
```

- [ ] **Step 6: Smoke test**

```bash
# 1. With no demo running, gateway down is SKIP (current behavior)
pawai doctor --cache 0 | grep "Gateway 8080"
# expect: ℹ Gateway 8080: SKIP (no demo running)

# 2. With demo running, gateway should be OK or FAIL (not SKIP)
pawai demo start
sleep 30
pawai doctor --cache 0 | grep "Gateway 8080"
# expect: ✓ Gateway 8080: OK
pawai demo stop
```

- [ ] **Step 7: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "$(cat <<'EOF'
fix(pawai_cli): doctor — Gateway 8080 severity reads Lock.state (Phase 1 item 1)

main.py had `lock_state = None  # L2 will populate this`. Wired now.
When a `running` demo lock exists and gateway 8080 is down, doctor emits
FAIL with proper severity instead of SKIP. Removes the false-green seen
in this morning's session where stop+start race showed SKIP for ~30s
window while the demo was actually still alive.

Spec: §Phase 1 item 1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Item 5 — `pawai status --short` skips ROS node list SSH call

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/status.py` (`collect()` + `print_status()`)
- Modify: `tools/pawai_cli/pawai_cli/main.py` (status command passes short through)
- Modify: `tools/pawai_cli/tests/test_cli.py`

Currently `collect()` always runs `ros2 node list` over SSH (line 59-64), even when caller passes `short=True`. That SSH query hits the ros2 daemon cache → stale "phantom node" output. Fix: pass `short` down to `collect()` and skip the SSH call.

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
def test_status_short_skips_ros_node_list_ssh_call():
    """status --short must not invoke `ros2 node list` over SSH (avoid daemon cache)."""
    from pawai_cli import status as status_mod
    from pawai_cli.shell import Result

    calls = []

    def fake_run_remote(cmd, timeout=None):
        calls.append(cmd)
        return Result(code=0, stdout="", stderr="")

    with patch("pawai_cli.status.shell.run_remote", side_effect=fake_run_remote), \
         patch("pawai_cli.lock.Lock.read", return_value=None):
        status_mod.collect(short=True)

    # No SSH call should mention `ros2 node list`
    ros_calls = [c for c in calls if "ros2 node list" in c]
    assert ros_calls == [], f"unexpected ros2 calls under --short: {ros_calls}"
```

- [ ] **Step 2: Run test, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_status_short_skips_ros_node_list_ssh_call -v
# expect: TypeError (collect() takes no `short` kwarg) OR AssertionError (ros2 call present)
```

- [ ] **Step 3: Implement — modify `collect()` to accept `short`**

Edit `tools/pawai_cli/pawai_cli/status.py`. Replace `collect()` function (line 57-76):

```python
def collect(short: bool = False) -> LiveStatus:
    tmux = shell.run_remote("tmux ls 2>/dev/null || true", timeout=10)
    if short:
        ros = None
    else:
        ros = shell.run_remote(
            "source /opt/ros/humble/setup.zsh 2>/dev/null; "
            f"source {shell.jetson_repo()}/install/setup.zsh 2>/dev/null; "
            "ros2 node list 2>/dev/null || true",
            timeout=12,
        )
    git = shell.run_remote(
        f"cd {shell.jetson_repo()} && "
        "printf 'log=' && git log -1 --format='%h|%ci|%s' 2>/dev/null && "
        "printf 'status=' && git status --short --branch 2>/dev/null",
        timeout=12,
    )
    last = shell.run_remote(
        f"cat {shell.jetson_repo()}/.pawai-last-deploy 2>/dev/null || true",
        timeout=8,
    )
    reachable = tmux.code != 127 and tmux.code != 255
    return LiveStatus(
        tmux=tmux.stdout.strip(),
        ros_nodes="" if ros is None else ros.stdout.strip(),
        git=git.stdout.strip(),
        last_deploy=last.stdout.strip(),
        reachable=reachable,
    )
```

- [ ] **Step 4: Update `print_status()` to pass `short` through**

In the same file, replace line 130 inside `print_status()`:

Current:
```python
def print_status(short: bool = False) -> LiveStatus:
    st = collect()
```

Change to:
```python
def print_status(short: bool = False) -> LiveStatus:
    st = collect(short=short)
```

- [ ] **Step 5: Run test, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_status_short_skips_ros_node_list_ssh_call -v
# expect: PASS
```

- [ ] **Step 6: Run full suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 83 passed
```

- [ ] **Step 7: Smoke test**

```bash
# After demo stop, normal status would show daemon-cached phantom nodes
pawai demo stop  # if a demo was running
time pawai status --short
# expect: no ROS nodes section, response < 4s

time pawai status
# expect: ROS nodes section present, may show stale daemon cache (known limitation; --short is the workaround)
```

- [ ] **Step 8: Commit**

```bash
git add tools/pawai_cli/pawai_cli/status.py tools/pawai_cli/tests/test_cli.py
git commit -m "$(cat <<'EOF'
fix(pawai_cli): status --short skips ros2 node list SSH call (Phase 1 item 5)

collect() now accepts short=True to skip the `ros2 node list` SSH query.
This both speeds up `pawai status --short` (~2s saved) and prevents the
ros2 daemon cache from lying — today's session saw 20+ phantom nodes
listed after demo stop because daemon discovery had a 30s TTL.

`pawai status` (without --short) still queries nodes for the full view;
use --short when you only need lock/tmux/git/deploy facts.

Spec: §Phase 1 item 5

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch 3: Deploy & Start-script Env Safety (Items 2, 3, 4)

### Task 5: Item 2 — rsync excludes secrets

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (`_do_rsync_and_build` rsync arg list, line 469-487)
- Modify: `tools/pawai_cli/tests/test_cli.py`

I5 redaction whitelist mentions home-dir `~/.ssh/*` separately. Item 2's rsync exclude is **repo-relative**: a teammate may accidentally have a stray `.ssh/` folder under the repo (e.g., a sample SSH config) or `.env.dev`. We exclude the entire family.

**Do NOT** add `~/.ssh/*` as an rsync exclude — that pattern is for redaction context, not rsync. rsync only sees the repo tree; home-dir SSH keys are outside its scope.

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
def test_jetson_deploy_rsync_excludes_env_and_ssh():
    """rsync invocation must include --exclude for secrets families."""
    captured_argv = []

    def fake_stream(argv, cwd=None):
        captured_argv.append(argv)
        return 0

    with patch("pawai_cli.main.shell.stream", side_effect=fake_stream), \
         patch("pawai_cli.main.shell.run_remote") as mock_remote, \
         patch("pawai_cli.main.Lock.read", return_value=None), \
         patch("pawai_cli.main.print_status") as mock_status:
        from pawai_cli.shell import Result
        mock_remote.return_value = Result(code=0, stdout="", stderr="")
        mock_status.return_value.has_demo = False

        from click.testing import CliRunner
        from pawai_cli import main as cli_main
        runner = CliRunner()
        result = runner.invoke(cli_main.cli, [
            "jetson", "deploy", "--module", "brain", "--no-build", "-y"
        ])

    # Find the rsync argv (first one starting with "rsync")
    rsync_argv = next((a for a in captured_argv if a and a[0] == "rsync"), None)
    assert rsync_argv is not None, f"no rsync invocation seen: {captured_argv}"

    excludes = [arg for arg in rsync_argv if arg.startswith("--exclude=")]
    required = {"--exclude=.env", "--exclude=.env.*", "--exclude=.env.local",
                "--exclude=.ssh/"}
    missing = required - set(excludes)
    assert not missing, f"missing rsync excludes: {missing}"
```

- [ ] **Step 2: Run test, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_jetson_deploy_rsync_excludes_env_and_ssh -v
# expect: FAIL (current rsync arg list does not include .env / .ssh excludes)
```

- [ ] **Step 3: Implement — add excludes to rsync argv**

Edit `tools/pawai_cli/pawai_cli/main.py` around line 469. Inside `_do_rsync_and_build`, expand the `argv` list. Current:

```python
            argv = [
                "rsync",
                "-az",
                "--delete",
                "--exclude=.git/",
                "--exclude=build/",
                "--exclude=install/",
                "--exclude=log/",
                "--exclude=__pycache__/",
                "--exclude=.pytest_cache/",
                "--exclude=.venv/",
                "--exclude=node_modules/",
                "--exclude=.next/",
                "--exclude=.ruff_cache/",
                "--exclude=.mypy_cache/",
                "--exclude=.DS_Store",
                f"{root}/",
                dest,
            ]
```

Change to (add 4 new lines for secrets, repo-relative):

```python
            argv = [
                "rsync",
                "-az",
                "--delete",
                "--exclude=.git/",
                "--exclude=build/",
                "--exclude=install/",
                "--exclude=log/",
                "--exclude=__pycache__/",
                "--exclude=.pytest_cache/",
                "--exclude=.venv/",
                "--exclude=node_modules/",
                "--exclude=.next/",
                "--exclude=.ruff_cache/",
                "--exclude=.mypy_cache/",
                "--exclude=.DS_Store",
                # Secrets / local config — must never sync to shared Jetson (I5)
                "--exclude=.env",
                "--exclude=.env.*",
                "--exclude=.env.local",
                "--exclude=.ssh/",
                f"{root}/",
                dest,
            ]
```

Note: `--exclude=.env.*` covers `.env.local`, `.env.dev`, etc. We list `.env.local` explicitly anyway for grep-ability.

- [ ] **Step 4: Run test, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_jetson_deploy_rsync_excludes_env_and_ssh -v
# expect: PASS
```

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 84 passed
```

- [ ] **Step 6: Smoke test — actual deploy with verification**

```bash
# Check that Jetson does NOT have a .env.local after deploy
pawai jetson deploy --module brain --no-build -y 2>&1 | tail -3
ssh jetson "ls -la /home/jetson/elder_and_dog/.env.local 2>&1"
# expect: ls: cannot access ... No such file or directory
# OR: the file is whatever was already there before (rsync did not overwrite)
```

If the file existed previously due to bad past deploys, manually clean:
```bash
ssh jetson "rm -f /home/jetson/elder_and_dog/.env.local"
```

- [ ] **Step 7: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "$(cat <<'EOF'
fix(pawai_cli): rsync excludes .env/.ssh from deploy (Phase 1 item 2)

Adds 4 repo-relative rsync excludes so `.env`, `.env.*`, `.env.local`,
and any stray `.ssh/` folder inside the repo never get pushed to the
shared Jetson. The .env.local file holds OPENROUTER_KEY and other
secrets per developer — should never propagate.

Note: I5 redaction whitelist mentions `~/.ssh/*` separately; that is
for log/debug-bundle redaction. rsync only sees the repo tree, so
home-dir SSH keys are out of scope for this exclude list.

Spec: §I5 + §Phase 1 item 2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Item 3 — `start.sh` reads `JETSON_TAILSCALE_IP` from CLI env, no hardcoded fallback

**Files:**
- Modify: `.claude/skills/brain-studio-lane/scripts/start.sh` (line 47)
- Modify: `tools/pawai_cli/pawai_cli/main.py` (`_invoke_start_sh` passes env explicitly)

The current line 47 reads:
```bash
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"
```

This means: if env is unset, fall back to hardcoded IP. The CLI calls start.sh via `shell.stream(args, cwd=...)` which inherits the CLI process env (`os.environ`). If the CLI properly loads `.env.local` (it does, via `_load_env`), then `JETSON_TAILSCALE_IP` should be in env. The fix is:

1. start.sh fails loudly if `JETSON_TAILSCALE_IP` is unset (not silently fall back to 100.83.109.89)
2. CLI explicitly passes the detected/configured IP via env to start.sh, even if `.env.local` didn't set it

- [ ] **Step 1: Manual reproduction first (no test needed, this is a bash script)**

```bash
# Reproduce current bug:
unset JETSON_TAILSCALE_IP
bash -c 'JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"; echo "$JETSON_TAILSCALE_IP"'
# expect: 100.83.109.89  (the hardcoded fallback — bug)
```

- [ ] **Step 2: Modify `start.sh` to require env**

Edit `.claude/skills/brain-studio-lane/scripts/start.sh`. Around line 47, replace:

```bash
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"
```

with:

```bash
# Phase 1 item 3: no hardcoded IP fallback; CLI must provide JETSON_TAILSCALE_IP
if [ -z "${JETSON_TAILSCALE_IP:-}" ]; then
  echo "✗ JETSON_TAILSCALE_IP is unset" >&2
  echo "  → set in .env.local, or run via: pawai demo start" >&2
  echo "  → CLI auto-detects via Tailscale; bare bash invocation must export it first" >&2
  exit 2
fi
```

- [ ] **Step 3: Modify CLI to inject env explicitly into start.sh subprocess**

Edit `tools/pawai_cli/pawai_cli/main.py` `_invoke_start_sh` function (line 583-592). Current:

```python
def _invoke_start_sh(no_studio: bool, brain_only: bool) -> int:
    """Thin wrapper for tests — calls existing start.sh path."""
    args = ["bash", ".claude/skills/brain-studio-lane/scripts/start.sh"]
    if brain_only:
        args.append("minimal")
    elif no_studio:
        args.append("full")
    else:
        args.append("demo")
    return shell.stream(args, cwd=shell.repo_root())
```

Change to:

```python
def _invoke_start_sh(no_studio: bool, brain_only: bool) -> int:
    """Thin wrapper for tests — calls existing start.sh path."""
    args = ["bash", ".claude/skills/brain-studio-lane/scripts/start.sh"]
    if brain_only:
        args.append("minimal")
    elif no_studio:
        args.append("full")
    else:
        args.append("demo")
    env = _build_demo_env()
    return shell.stream(args, cwd=shell.repo_root(), env=env)


def _build_demo_env() -> dict:
    """Compose env for start.sh: inherits os.environ + injects detected Tailscale IP."""
    env = os.environ.copy()
    if not env.get("JETSON_TAILSCALE_IP"):
        # Try detection via network module
        try:
            from . import network
            hint = shell.jetson_hostname_hint()
            peer = network.find_jetson_peer(hint=hint)
            if peer and peer.get("online") and peer.get("ip"):
                env["JETSON_TAILSCALE_IP"] = peer["ip"]
        except Exception:
            pass
    return env
```

- [ ] **Step 4: Update `shell.stream()` signature to accept `env` kwarg**

Check current `tools/pawai_cli/pawai_cli/shell.py` `stream()`:

```python
def stream(argv: Iterable[str], cwd: Path | None = None) -> int:
    try:
        return subprocess.call(list(argv), cwd=str(cwd) if cwd else None)
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 127
```

Change to:

```python
def stream(argv: Iterable[str], cwd: Path | None = None, env: dict | None = None) -> int:
    try:
        return subprocess.call(
            list(argv),
            cwd=str(cwd) if cwd else None,
            env=env,
        )
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 127
```

- [ ] **Step 5: Verify other callers of `shell.stream()` still work**

```bash
grep -n "shell.stream\b" tools/pawai_cli/pawai_cli/*.py
# All call sites without env kwarg will pass None, which subprocess.call interprets as "inherit current env"
# So no other call sites need updating.
```

- [ ] **Step 6: Smoke test**

```bash
# 1. Bare bash invocation without env must fail loudly
unset JETSON_TAILSCALE_IP
cd /Users/lubaiyu/elder_and_dog
bash .claude/skills/brain-studio-lane/scripts/start.sh demo 2>&1 | head -3
# expect: ✗ JETSON_TAILSCALE_IP is unset + fix instructions, exit 2

# 2. CLI works (env injected from .env.local or detection)
pawai demo start
# expect: normal start sequence, gateway alive on the right IP
pawai demo stop
```

- [ ] **Step 7: Run full test suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 84 passed (no new tests added in this task; smoke is manual)
```

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/brain-studio-lane/scripts/start.sh \
        tools/pawai_cli/pawai_cli/main.py \
        tools/pawai_cli/pawai_cli/shell.py
git commit -m "$(cat <<'EOF'
fix(start.sh): require JETSON_TAILSCALE_IP, drop hardcoded fallback (Phase 1 item 3)

start.sh used to silently fall back to 100.83.109.89 when env was unset.
If the Tailscale IP ever rotated (Tailscale generally pins them but does
not contractually guarantee), demos would break silently in confusing
ways. Now:
  - start.sh exits 2 with fix message if env missing
  - CLI _invoke_start_sh() detects + injects env from Tailscale peer info

shell.stream() gains an `env` kwarg (default None = inherit).

Spec: §Phase 1 item 3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Item 4 — `start.sh` forwards `TTS_PROVIDER` / `ASR_PROVIDER_ORDER` to Jetson tmux

**Files:**
- Modify: `.claude/skills/brain-studio-lane/scripts/start.sh` (env propagation block, ~line 100-125)

The bug observed 5/12 night: Mac shell sets `TTS_PROVIDER=edge_tts` and `ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'`, but the demo tmux on Jetson didn't see them. start.sh sends commands to Jetson via SSH but doesn't forward these env vars.

- [ ] **Step 1: Inspect current SSH command that starts demo tmux on Jetson**

```bash
grep -nA 20 "TTS_PROVIDER" .claude/skills/brain-studio-lane/scripts/start.sh | head -40
```

You'll see (around lines 116-125 per earlier grep):
```bash
    # TTS_PROVIDER=openrouter_gemini → quality lane 走 Gemini 3.1 Flash TTS Despina
    ...
      TTS_PROVIDER='${TTS_PROVIDER:-openrouter_gemini}' \
```

The current start.sh has a `${TTS_PROVIDER:-openrouter_gemini}` substitution, but Roy's report says env doesn't propagate. Investigate exactly how the SSH command is built — likely the env var is interpolated *on the Mac side* but Mac shell's env doesn't reach there because of quoting.

- [ ] **Step 2: Reproduce the propagation gap (manual)**

```bash
# In a fresh Mac shell:
export TTS_PROVIDER="edge_tts"
export ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'
# Trigger start.sh path (via CLI):
pawai demo start
# Then inspect what Jetson actually sees:
ssh jetson "tmux capture-pane -t demo:tts -pJ -S -100 | grep -E 'provider|edge_tts|openrouter' | head -10"
# expect (bug): shows openrouter_gemini or default, not edge_tts
pawai demo stop
```

- [ ] **Step 3: Fix start.sh — add ASR_PROVIDER_ORDER to the existing SSH env block**

Edit `.claude/skills/brain-studio-lane/scripts/start.sh` lines 117-122. Current full mode SSH command:

```bash
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t demo 2>/dev/null; \
      WORKSPACE=$JETSON_REPO \
      PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' \
      PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' \
      TTS_PROVIDER='${TTS_PROVIDER:-openrouter_gemini}' \
      bash $JETSON_REPO/scripts/start_full_demo_tmux.sh > /dev/null 2>&1 &"
```

Replace with (uses `printf %q` for shell-safe quoting; adds `ASR_PROVIDER_ORDER`):

```bash
    # Phase 1 item 4: safe-quote env values that may contain single quotes,
    # spaces, or shell metacharacters (e.g., ASR_PROVIDER_ORDER='["x","y"]').
    SAFE_PAWAI_LLM_MODEL=$(printf %q "${PAWAI_LLM_MODEL:-}")
    SAFE_PAWAI_LLM_FALLBACK_MODEL=$(printf %q "${PAWAI_LLM_FALLBACK_MODEL:-}")
    SAFE_TTS_PROVIDER=$(printf %q "${TTS_PROVIDER:-openrouter_gemini}")
    SAFE_ASR_PROVIDER_ORDER=$(printf %q "${ASR_PROVIDER_ORDER:-}")

    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t demo 2>/dev/null; \
      WORKSPACE=$JETSON_REPO \
      PAWAI_LLM_MODEL=$SAFE_PAWAI_LLM_MODEL \
      PAWAI_LLM_FALLBACK_MODEL=$SAFE_PAWAI_LLM_FALLBACK_MODEL \
      TTS_PROVIDER=$SAFE_TTS_PROVIDER \
      ASR_PROVIDER_ORDER=$SAFE_ASR_PROVIDER_ORDER \
      bash $JETSON_REPO/scripts/start_full_demo_tmux.sh > /dev/null 2>&1 &"
```

`printf %q` produces a bash-safe representation that survives one re-evaluation (which SSH does when the remote bash parses the command string). Bare `'${VAR:-}'` is **not** safe for `.env.local`-sourced values that may contain `'` or `$`.

Repeat the same `SAFE_*` extraction + substitution in any other SSH demo-launch block in start.sh (search via grep):

```bash
grep -n "TTS_PROVIDER=" .claude/skills/brain-studio-lane/scripts/start.sh
```

For each occurrence (likely one per mode: full / demo / e2e), add the same `ASR_PROVIDER_ORDER='${ASR_PROVIDER_ORDER:-}' \` line right after `TTS_PROVIDER`.

**Note:** Task 6 already wires `_build_demo_env()` in the CLI to read `os.environ` (which includes `.env.local` parsed values). So setting `ASR_PROVIDER_ORDER` in `.env.local` will reach start.sh, which will pass it to Jetson via this line.

- [ ] **Step 4: Re-test propagation**

```bash
export TTS_PROVIDER="edge_tts"
pawai demo start
sleep 20
ssh jetson "tmux capture-pane -t demo:tts -pJ -S -200 | grep -i 'provider' | head -10"
# expect: shows edge_tts active
pawai demo stop
```

- [ ] **Step 5: Run full test suite (no new tests; bash-only change)**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 84 passed
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/brain-studio-lane/scripts/start.sh
git commit -m "$(cat <<'EOF'
fix(start.sh): forward TTS/ASR/LLM env to Jetson tmux (Phase 1 item 4)

5/12 night offline-fallback verification revealed that Mac-side env
(TTS_PROVIDER=edge_tts, ASR_PROVIDER_ORDER=[...local]) was not reaching
the Jetson tmux. The default openrouter_gemini was used regardless of
local override. Root cause: SSH command inlined `${VAR:-default}` but
the var was not present in start.sh's own shell at that point.

Now start.sh reads three demo-relevant env vars at top, then explicitly
forwards them in the SSH bash -lc invocation that boots the demo tmux.

Spec: §Phase 1 item 4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch 4: Lock + Health + PID Cleanup (Items 6, 8, 10)

### Task 8: Item 6 — `Lock.release()` owner-aware with flock guard

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/lock.py` (release method)
- Modify: `tools/pawai_cli/pawai_cli/main.py` (demo_stop calls release with owner)
- Modify: `tools/pawai_cli/tests/test_lock.py`

Currently `Lock.release()` does a plain `rm -f` — no owner check, no flock. Race condition risk: A reads lock, A starts cleanup, B races in and releases A's lock. Fix: pass user+host to release(); only remove if owner matches; wrap in flock.

Also: `demo_stop` currently treats own stale lock as releasable without `--force` already (logic-wise), but message clarity can be improved.

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_lock.py`:

```python
def test_release_only_removes_if_owner_matches():
    """release_if_owned should not rm the lock when user/host mismatch."""
    from pawai_cli.lock import Lock
    from pawai_cli.shell import Result

    # Build a fake remote that returns exit 17 on mismatch, 0 on match
    captured_cmds = []

    def fake_remote(cmd, timeout=None):
        captured_cmds.append(cmd)
        # Heuristic: if the command embeds expected_user="alice" and lock's user=bob,
        # the shell-side script returns 17.
        if "alice" in cmd:
            return Result(code=0, stdout="", stderr="")
        return Result(code=17, stdout="", stderr="not owner")

    with patch("pawai_cli.lock.shell.run_remote", side_effect=fake_remote):
        ok_alice = Lock.release_if_owned(user="alice", host="alice-mac")
        ok_bob = Lock.release_if_owned(user="bob", host="bob-mac")

    assert ok_alice is True
    assert ok_bob is False
    assert len(captured_cmds) == 2


def test_demo_stop_own_stale_lock_releases_without_force():
    """demo stop on own stale lock must succeed without --force."""
    from click.testing import CliRunner
    from pawai_cli import main as cli_main
    from pawai_cli.lock import Lock

    # Forge a stale-but-own lock
    own_stale = Lock(
        user="lubaiyu", host="Roy422deMacBook-Pro.local",
        branch="main", sha="abc1234",
        state="running",
        # 5 hours ago — past RUNNING_STALE_HOURS (4h)
        start_time="2026-05-13T03:00:00+00:00",
        demo_mode="full", tmux_session="demo", lane="brain",
    )

    with patch("pawai_cli.main.Lock.read", return_value=own_stale), \
         patch("pawai_cli.main.Lock.release_if_owned", return_value=True) as mock_rel, \
         patch("pawai_cli.main._cleanup_for_lock", return_value=0), \
         patch("pawai_cli.main.os.environ", {"USER": "lubaiyu"}), \
         patch("pawai_cli.main.platform.node", return_value="Roy422deMacBook-Pro.local"):
        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["demo", "stop"])  # NO --force

    assert result.exit_code == 0
    mock_rel.assert_called_once()
```

- [ ] **Step 2: Run tests, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_lock.py -v -k "release_only_removes_if_owner_matches or demo_stop_own_stale"
# expect: AttributeError (Lock has no release_if_owned)
```

- [ ] **Step 3: Implement `Lock.release_if_owned()` — injection-safe via env vars**

Edit `tools/pawai_cli/pawai_cli/lock.py`. Add `import shlex` at the top (next to existing imports) if not already present. After the existing `release()` method (line 99-102), add:

```python
    @classmethod
    def release_if_owned(cls, user: str, host: str) -> bool:
        """Atomically remove lock only if user/host matches.

        Returns True if the lock was successfully removed (or was already absent).
        Returns False if a different owner holds the lock.

        Injection-safe: `user`, `host`, and `lock_path` are passed to the remote
        shell as `shlex.quote`-protected env vars; the python3 script reads them
        from os.environ so no value is ever string-interpolated into a shell or
        Python source.
        """
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
        result = shell.run_remote(cmd, timeout=10)
        # code 0 = removed (or was absent); 17 = owner mismatch;
        # other non-zero = flock contention / SSH transient
        return result.code == 0
```

This pattern:
- `shlex.quote(user)` produces safe POSIX shell-quoted string even if `user` contains `'`, `"`, `;`, `$`, `\`, etc.
- `shlex.quote(py_script)` protects the multi-line script body the same way.
- Python script reads from `os.environ` — values never go through string interpolation.
- Even if a malicious teammate later writes a lock file with `"user": "'; rm -rf /; #"`, this code cannot be tricked: the value is compared as a Python string, never executed.

- [ ] **Step 4: Wire `demo_stop` to use `release_if_owned`**

Edit `tools/pawai_cli/pawai_cli/main.py` `demo_stop` (line 734-753). Current:

```python
@demo.command("stop")
@click.option("--force", is_flag=True, help="Stop another user's demo and release their lock.")
def demo_stop(force: bool) -> None:
    """Stop brain-studio-lane."""
    from .lock import Lock, is_own_lock
    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()

    existing = Lock.read()
    if existing is None:
        click.echo("No demo lock present.")
        rc = _invoke_cleanup_sh()
        sys.exit(rc)

    if not is_own_lock(existing, user, host) and not force:
        click.echo(f"Lock is owned by {existing.user}@{existing.host}. "
                   f"Use --force to stop their demo.")
        sys.exit(2)

    rc = _cleanup_for_lock(existing)
    Lock.release()
    sys.exit(rc)
```

Change to:

```python
@demo.command("stop")
@click.option("--force", is_flag=True, help="Stop another user's demo and release their lock.")
def demo_stop(force: bool) -> None:
    """Stop brain-studio-lane."""
    from .lock import Lock, is_own_lock, is_stale
    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()

    existing = Lock.read()
    if existing is None:
        click.echo("No demo lock present.")
        rc = _invoke_cleanup_sh()
        sys.exit(rc)

    own = is_own_lock(existing, user, host)
    if not own and not force:
        click.echo(f"Lock is owned by {existing.user}@{existing.host}. "
                   f"Use --force to stop their demo.")
        sys.exit(2)

    if own and is_stale(existing):
        click.echo(f"Reclaiming your own stale {existing.state} lock (started {existing.start_time}).")

    rc = _cleanup_for_lock(existing)
    if force and not own:
        # Forced takeover of someone else's lock — plain rm (no owner gate)
        Lock.release()
    else:
        ok = Lock.release_if_owned(user=existing.user, host=existing.host)
        if not ok:
            click.echo("⚠ Lock release skipped — another process holds the flock or lock changed.")
    sys.exit(rc)
```

- [ ] **Step 5: Run tests, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_lock.py -v
# expect: all green (incl. 2 new ones)
```

- [ ] **Step 6: Real-Jetson smoke test (precondition + backup/restore)**

```bash
# Precondition: refuse to run if a teammate's lock exists.
EXISTING=$(ssh jetson "cat /home/jetson/elder_and_dog/.pawai-demo-lock 2>/dev/null" || true)
if [ -n "$EXISTING" ]; then
  echo "✗ Lock already present on Jetson. Skipping destructive smoke."
  echo "  Inspect:  pawai status"
  echo "  Owner:    $(echo "$EXISTING" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get(\"user\",\"?\")+\"@\"+d.get(\"host\",\"?\"))' 2>/dev/null || echo unparsable)"
  echo "  Re-run smoke once the lock is released."
  exit 1
fi

# 1. Acquire a lock then verify own-stop works without --force
pawai demo start
sleep 5
pawai demo stop
# expect: clean stop, no --force needed, no "Lock is owned by" message

# 2. Verify the safety: simulate other-user lock manually.
# (Precondition above ensures we won't clobber a real teammate lock.)
ssh jetson 'cat > /home/jetson/elder_and_dog/.pawai-demo-lock <<EOF
{"schema_version":1,"user":"smoke-test-alice","host":"smoke-test-host","branch":"main","sha":"abc","state":"running","start_time":"2026-05-13T10:00:00+00:00","demo_mode":"full","tmux_session":"demo","lane":"brain"}
EOF'
pawai demo stop  # WITHOUT --force
# expect: "Lock is owned by smoke-test-alice@smoke-test-host. Use --force to stop their demo." + exit 2

# Cleanup test fixture — only remove if it still has our smoke marker
ssh jetson '
LOCK=/home/jetson/elder_and_dog/.pawai-demo-lock
if [ -f "$LOCK" ] && grep -q "smoke-test-alice" "$LOCK"; then
  rm "$LOCK"
  echo "✓ smoke fixture removed"
else
  echo "⚠ lock changed during smoke; not removing"
fi
'
```

The `smoke-test-alice` / `smoke-test-host` markers are deliberately unlikely to collide with a real user. Cleanup verifies the marker before deletion — protects against a race where a real lock landed during the test window.

- [ ] **Step 7: Run full test suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 86 passed (84 + 2)
```

- [ ] **Step 8: Commit**

```bash
git add tools/pawai_cli/pawai_cli/lock.py \
        tools/pawai_cli/pawai_cli/main.py \
        tools/pawai_cli/tests/test_lock.py
git commit -m "$(cat <<'EOF'
fix(lock): Lock.release_if_owned + demo stop auto-reclaims own stale (Phase 1 item 6)

Lock.release_if_owned(user, host) does an atomic flock-guarded read +
compare + rm, returning False when the lock owner is someone else.
demo_stop now uses it; own-stale locks release cleanly without --force.
This was today's friction — clearing my own yesterday-night lock prompted
a permission gate around --force when it shouldn't.

Force-takeover path (force=True AND lock not own) still uses plain
release() to bypass the owner gate.

Spec: §Phase 1 item 6

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Item 8 — New `pawai health brain` command + fix `healthcheck.sh` hostname

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (add `health` group + `brain` subcommand)
- Modify: `.claude/skills/brain-studio-lane/scripts/healthcheck.sh` (lines 6 already reads `$JETSON_HOST` but defaults to `jetson-nano`; verify and improve)
- Modify: `tools/pawai_cli/tests/test_cli.py`

**Critical:** When I read `healthcheck.sh` earlier, line 6 already had `JETSON_HOST="${JETSON_HOST:-jetson-nano}"`. So the bug isn't that it's *hardcoded* — it's that the default is `jetson-nano` while my SSH config has `jetson`. Fix: have `pawai health brain` always export `JETSON_HOST=$(pawai's resolved host)` before calling the script.

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
def test_health_brain_passes_jetson_host_env():
    """pawai health brain exports JETSON_HOST before calling healthcheck.sh."""
    captured_env = {}

    def fake_stream(argv, cwd=None, env=None):
        captured_env.update(env or {})
        return 0

    with patch("pawai_cli.main.shell.stream", side_effect=fake_stream), \
         patch("pawai_cli.shell.jetson_host", return_value="jetson"):
        from click.testing import CliRunner
        from pawai_cli import main as cli_main
        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["health", "brain"])
    assert result.exit_code == 0
    assert captured_env.get("JETSON_HOST") == "jetson"
```

- [ ] **Step 2: Run test, expect failure**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_health_brain_passes_jetson_host_env -v
# expect: "No such command 'health'" / exit 2
```

- [ ] **Step 3: Add `health` group + `brain` subcommand to main.py**

Edit `tools/pawai_cli/pawai_cli/main.py`. After the existing `contract` group block (around line 812-839), append:

```python
@cli.group()
def health() -> None:
    """Subsystem health checks (Phase 1 reserves namespace; brain is first occupant)."""


@health.command("brain")
def health_brain() -> None:
    """Run brain-studio-lane healthcheck against Jetson."""
    script = shell.repo_root() / ".claude" / "skills" / "brain-studio-lane" / "scripts" / "healthcheck.sh"
    if not script.exists():
        raise click.ClickException(f"healthcheck script not found: {script}")
    env = os.environ.copy()
    # Override JETSON_HOST so the script's default `jetson-nano` is bypassed
    env["JETSON_HOST"] = shell.jetson_host()
    # Also inject Tailscale IP if known (used by step 7 frontend check)
    if not env.get("JETSON_TAILSCALE_IP"):
        try:
            from . import network
            peer = network.find_jetson_peer(hint=shell.jetson_hostname_hint())
            if peer and peer.get("online"):
                env["JETSON_TAILSCALE_IP"] = peer["ip"]
        except Exception:
            pass
    rc = shell.stream(["bash", str(script)], cwd=shell.repo_root(), env=env)
    sys.exit(rc)
```

- [ ] **Step 4: Run test, expect pass**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_health_brain_passes_jetson_host_env -v
# expect: PASS
```

- [ ] **Step 5: Smoke test against running demo**

```bash
pawai demo start
sleep 30
pawai health brain
# expect: 8 healthcheck steps, no SSH errors about jetson-nano resolution
pawai demo stop
```

- [ ] **Step 6: Run full test suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 87 passed
```

- [ ] **Step 7: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "$(cat <<'EOF'
feat(pawai_cli): new `pawai health brain` wraps lane healthcheck with $JETSON_HOST (Phase 1 item 8)

The brain-studio-lane healthcheck.sh defaulted to `JETSON_HOST=jetson-nano`
when env was unset. Teammates with a different SSH alias (e.g., `jetson`)
saw SSH errors from the script. `pawai health brain` now always exports
JETSON_HOST from the CLI's resolved value before invoking the script,
plus injects JETSON_TAILSCALE_IP for the frontend probe step.

Reserves `pawai health <subsystem>` namespace; brain is first occupant.

Spec: §Phase 1 item 8 + Risk #5

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Item 10 — `start.sh` replaces `pkill -f "next.*dev"` with PID-file kill

**Files:**
- Modify: `.claude/skills/brain-studio-lane/scripts/start.sh` (lines 58 and 174)

Current behavior (`pkill -f "next.*dev"`) kills ANY process matching that pattern in argv — including a teammate's unrelated Next.js project running on their laptop. Fix: write the frontend PID to `/tmp/pawai-frontend.pid` at start; only kill that specific PID on cleanup.

- [ ] **Step 1: Locate both `pkill -f "next.*dev"` occurrences**

```bash
grep -n 'next\.\*dev\|next.\*dev' .claude/skills/brain-studio-lane/scripts/start.sh
# expect:
#  58: LOCAL_OLD=$(pgrep -f "next.*dev" 2>/dev/null | head -1 || true)
# 174: pkill -f "next.*dev" 2>/dev/null || true
```

- [ ] **Step 2: Patch line 58 (cleanup-on-start detection)**

The current line 58 detects orphaned frontend from previous run. Use the PID file as primary source; fall back to pgrep only as a safety net:

```bash
PIDFILE_FRONTEND="/tmp/pawai-frontend.pid"
LOCAL_OLD=""
if [ -f "$PIDFILE_FRONTEND" ]; then
  CANDIDATE=$(cat "$PIDFILE_FRONTEND" 2>/dev/null)
  if [ -n "$CANDIDATE" ] && kill -0 "$CANDIDATE" 2>/dev/null; then
    LOCAL_OLD="$CANDIDATE"
  else
    rm -f "$PIDFILE_FRONTEND"
  fi
fi
```

Replace the existing line 58 (`LOCAL_OLD=$(pgrep -f "next.*dev" ...`) with that block.

- [ ] **Step 3: Patch line 174 (kill-old-frontend before start)**

Current line 174: `pkill -f "next.*dev" 2>/dev/null || true`

Replace with:

```bash
# Phase 1 item 10: only kill our own frontend, not random next dev procs
if [ -f "$PIDFILE_FRONTEND" ]; then
  OLD_PID=$(cat "$PIDFILE_FRONTEND" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
    kill -0 "$OLD_PID" 2>/dev/null && kill -9 "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PIDFILE_FRONTEND"
fi
```

(Note: `PIDFILE_FRONTEND` was defined in Step 2's block; if you placed Step 2 patch later in the script, also define `PIDFILE_FRONTEND="/tmp/pawai-frontend.pid"` near the top.)

- [ ] **Step 4: Write PID after `nohup ... next dev ... &`**

Find line ~182 where the frontend is launched:

```bash
nohup "$FRONTEND_DIR/node_modules/.bin/next" dev > /tmp/studio_frontend.log 2>&1 &
```

Add immediately after:

```bash
echo $! > "$PIDFILE_FRONTEND"
```

- [ ] **Step 5: Update cleanup.sh similarly**

Check `cleanup.sh` for the same anti-pattern:

```bash
grep -n "next.*dev" .claude/skills/brain-studio-lane/scripts/cleanup.sh
```

If `pkill -f "next.*dev"` appears, replace with the PID-file kill block (same as Step 3 above) and ensure `PIDFILE_FRONTEND="/tmp/pawai-frontend.pid"` is defined near top.

- [ ] **Step 6: Smoke test (no-network decoy)**

```bash
# Spawn a decoy whose argv matches "next dev" pattern, no network/install needed.
# `exec -a` sets argv[0]; the process is a plain sleep so it's safe and offline.
bash -c 'exec -a "next dev decoy" sleep 999' &
DECOY_PID=$!
sleep 1

# Verify the decoy is alive and argv matches the dangerous pattern
ps -p $DECOY_PID -o pid,command
pgrep -af "next.*dev" | grep -F "$DECOY_PID" \
  && echo "✓ decoy in place" \
  || { echo "✗ decoy didn't register; aborting smoke"; kill -9 $DECOY_PID 2>/dev/null; exit 1; }

# Start pawai demo (would previously pkill -f "next.*dev" → kills decoy)
pawai demo start
sleep 5

# Verify decoy survived
if kill -0 $DECOY_PID 2>/dev/null; then
  echo "✓ decoy survived (PID-file kill works correctly)"
else
  echo "✗ decoy was killed (regression — Item 10 fix not in effect)"
fi

# Cleanup
pawai demo stop
kill -9 $DECOY_PID 2>/dev/null
```

`exec -a "next dev decoy" sleep 999` runs `sleep` but sets its argv[0] to `next dev decoy`, so `pgrep -f "next.*dev"` matches it without requiring Node or npm. Zero network, zero install, fully deterministic. The PID is captured directly from `$!` (no subshell wrapping) so `$DECOY_PID` is reliable.

- [ ] **Step 7: Run full test suite**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 87 passed (no new tests; bash-only change)
```

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/brain-studio-lane/scripts/start.sh \
        .claude/skills/brain-studio-lane/scripts/cleanup.sh
git commit -m "$(cat <<'EOF'
fix(start.sh): use PID file instead of pkill -f next.*dev (Phase 1 item 10)

`pkill -f "next.*dev"` matched any process whose argv contained
"next dev" — would terminate a teammate's unrelated Next.js project
running on their laptop. Now:
  - frontend pid is written to /tmp/pawai-frontend.pid right after nohup
  - cleanup paths read that pidfile and only kill that one PID
  - pgrep fallback removed

cleanup.sh got the same treatment.

Spec: §Phase 1 item 10

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch 5: Docs Drift (Item 9)

### Task 11: Item 9 — Fix `mac-migration-setup.md` outdated lock claim + add team-onboarding cross-ref

**Files:**
- Modify: `docs/runbook/mac-migration-setup.md` (line 188-189)
- Modify: `docs/pawai_cli/team-onboarding.md` (add cross-ref to new lock behaviour)
- Modify: `docs/pawai_cli/README.md` (mention rsync exclude of secrets if §8 onwards covers deploy)

The outdated line at `mac-migration-setup.md:189`:
> brain/nav lane scripts and does not enforce a hard lock on the shared Go2.

After Phase 1, the CLI **does** enforce a lock (via `.pawai-demo-lock` + lock-aware deploy/start/stop). Update prose.

- [ ] **Step 1: Read context around the outdated line**

```bash
sed -n '175,200p' docs/runbook/mac-migration-setup.md
```

- [ ] **Step 2: Replace the outdated paragraph**

Edit `docs/runbook/mac-migration-setup.md` lines 187-189. Current:

```markdown
The CLI is a thin wrapper around the existing scripts. It does not replace the
brain/nav lane scripts and does not enforce a hard lock on the shared Go2.
```

Replace with:

```markdown
The CLI is a thin wrapper around the lane scripts (brain-studio-lane,
nav-avoidance-lane) but **does enforce a hard demo lock** at
`$JETSON_REPO/.pawai-demo-lock`. Concurrent `pawai demo start` from two
laptops will see the second invocation prompted to `--force` (with a
clear identity message). Stale own-locks auto-reclaim on `demo stop`;
stale running locks of other users only release with `--force --reason`
(Phase 2). See `docs/pawai_cli/team-onboarding.md §5` for the rules.
```

- [ ] **Step 3: Add cross-ref in team-onboarding.md**

Read the existing Step 5 ("規矩") in `docs/pawai_cli/team-onboarding.md`:

```bash
grep -nA 30 "^## 5\|^### 5\|規矩" docs/pawai_cli/team-onboarding.md | head -40
```

Append a bullet to that section (or to the closest list of CLI behaviour rules):

```markdown
- **Lock enforcement** (Phase 1, 2026-05-13+):
  - `pawai demo start` / `demo stop` / `jetson deploy` all read `.pawai-demo-lock` first.
  - Own stale locks (yours, past TTL) release without `--force` — just run `pawai demo stop`.
  - Other-user locks require `--force` (Phase 1) or `--force --reason "..."` (Phase 2).
  - `.env.local` is excluded from rsync to Jetson — no secret leakage.
```

- [ ] **Step 4: Mention rsync exclude in pawai_cli/README.md (optional but helpful)**

Find the deploy section:

```bash
grep -nA 5 "rsync\|deploy.*sync" docs/pawai_cli/README.md | head -20
```

Wherever the deploy mechanism is described, add a single line noting the I5-aligned exclusion:

```markdown
> **Security note:** `pawai jetson deploy` excludes `.env`, `.env.*`, `.env.local`, and any in-repo `.ssh/` directory from rsync. Home-directory SSH keys (`~/.ssh/`) are outside rsync's view by construction.
```

- [ ] **Step 5: Verify no other docs claim "no lock"**

```bash
grep -rn "no.*lock\|does not.*lock\|lacks.*lock\|hard lock" docs/ \
  | grep -v ".pawai-demo-lock" | grep -v archive
```

Fix any other stale claims you find with similar wording.

- [ ] **Step 6: Commit**

```bash
git add docs/runbook/mac-migration-setup.md \
        docs/pawai_cli/team-onboarding.md \
        docs/pawai_cli/README.md
git commit -m "$(cat <<'EOF'
docs(pawai_cli): fix drift — CLI does enforce hard lock (Phase 1 item 9)

mac-migration-setup.md:189 claimed CLI "does not enforce a hard lock";
that's been false since the lock primitives landed (commit afc0b06,
2026-05-12). Phase 1 today adds owner-aware release + own-stale auto-
reclaim, and rsync exclude for .env/.env.* secrets. Prose now matches
the implementation.

team-onboarding.md §5 gets explicit lock rules. README gets a one-line
security note about rsync exclude.

Spec: §Phase 1 item 9

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1 Closing Checklist

After all 11 tasks land:

- [ ] **All tests green**

```bash
python3 -m pytest tools/pawai_cli -q
# expect: 87 passed
```

- [ ] **Smoke through the demo lifecycle**

```bash
pawai doctor --cache 0       # 0 blocking · 0 warnings
pawai status --short          # fast, no phantom nodes
pawai demo start              # acquires lock, gateway alive on detected IP
pawai health brain            # 8/8 green (or close, depending on demo mode)
pawai demo stop               # releases own lock without --force
pawai status --short          # lock: none
```

- [ ] **Verify secrets are not on Jetson**

```bash
ssh jetson "ls -la ~/elder_and_dog/.env.local ~/elder_and_dog/.env 2>&1"
# expect: No such file or directory
```

- [ ] **Verify platform gate works (manual)**

```bash
# On a real WSL1 / Windows native session (if you can get to one), `pawai --help`
# should exit 10 with the I1 fix message. Skip if no test env available.
```

- [ ] **Commit count**

```bash
git log --oneline main..HEAD | wc -l
# expect: ~11 commits (one per item, possibly +1 for pre-flight fix if anything surfaced)
```

- [ ] **Push branch + open PR**

```bash
git push -u origin <branch-name>
# Create PR with body referencing the spec commit 6388a08
```

---

## Out-of-Scope Reminders (Phase 2-4 stuff that may come up during Phase 1)

If during Phase 1 implementation you find yourself wanting to:

- Add `--json` output to anything → **STOP. Phase 4.**
- Write to `.pawai-audit.log` → **STOP. Phase 2.**
- Add `pawai lock {status,reclaim,force --reason}` subcommands → **STOP. Phase 2.**
- Add `pawai setup` wizard or `pawai net` → **STOP. Phase 3.**
- Add `pawai debug bundle` → **STOP. Phase 4.**
- Change exit codes on existing commands (other than the new `10` for platform) → **STOP. Phase 4.**

Leave a TODO comment referencing the spec section and move on. Phase 1 is firefighting only.

---

## Spec Coverage Map

For self-verification: each Phase 1 spec item ↔ task:

| Spec Item | Plan Task | Status |
|-----------|-----------|--------|
| 0 — platform gate | Task 1 | covered |
| 1 — doctor gateway + lock | Task 3 | covered |
| 2 — rsync exclude | Task 5 | covered |
| 3 — start.sh JETSON_TAILSCALE_IP | Task 6 | covered |
| 4 — TTS/ASR env propagation | Task 7 | covered |
| 5 — status --short skip ROS | Task 4 | covered |
| 6 — Lock.release owner-aware | Task 8 | covered |
| 7 — Tailscale online=false fail | Task 2 | covered |
| 8 — pawai health brain | Task 9 | covered |
| 9 — docs drift | Task 11 | covered |
| 10 — start.sh pkill PID-file | Task 10 | covered |

All 11 items covered.
