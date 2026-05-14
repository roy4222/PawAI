# jetson-verify Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a YAML-driven Jetson deployment verification skill with structured JSON output, auto-detecting local vs remote execution.

**Architecture:** Python executor (`verify.py`) reads check definitions from YAML profiles, delegates command execution to a transport abstraction (`transport.py`) that auto-detects Jetson vs WSL, and outputs structured JSON (stdout) + human summary (stderr). Checks follow a 5-status model: PASS/WARN/FAIL/SKIP/ERROR.

**Tech Stack:** Python 3.10+ (stdlib + PyYAML), pytest. PyYAML 在 ROS2 Jetson 環境已有；WSL 上需確認 `python3 -c "import yaml"` 通過，否則 `uv pip install pyyaml`。

**Spec:** `docs/superpowers/specs/2026-03-20-jetson-verify-skill-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `.claude/skills/jetson-verify/scripts/transport.py` | Target execution abstraction (~60 lines) |
| Create | `.claude/skills/jetson-verify/scripts/verify.py` | Main executor: YAML → checks → JSON (~150 lines) |
| Create | `.claude/skills/jetson-verify/profiles/smoke.yaml` | 9 smoke checks (3 system + 2 ROS2 + 4 module) |
| Create | `.claude/skills/jetson-verify/profiles/integration.yaml` | TODO stub |
| Create | `.claude/skills/jetson-verify/profiles/demo.yaml` | TODO stub |
| Create | `.claude/skills/jetson-verify/SKILL.md` | Trigger conditions + usage guide |
| Create | `.claude/skills/jetson-verify/references/gotchas.md` | Known pitfalls |
| Create | `tests/jetson-verify/test_transport.py` | transport.py unit tests |
| Create | `tests/jetson-verify/test_expect_parser.py` | Expect parser unit tests |
| Create | `tests/jetson-verify/test_verify.py` | verify.py integration tests |
| Create | `logs/jetson-verify/.gitkeep` | Output directory |

---

## Task 1: transport.py — Target Execution Abstraction

**Files:**
- Create: `.claude/skills/jetson-verify/scripts/transport.py`
- Create: `tests/jetson-verify/test_transport.py`

- [ ] **Step 1: Write transport.py tests**

```python
# tests/jetson-verify/test_transport.py
"""transport.py unit tests — mock subprocess, no real SSH."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.claude/skills/jetson-verify/scripts"))
from transport import detect_target_env, build_target_command, exec_on_target


class TestDetectTargetEnv:
    @patch("os.path.exists", return_value=True)
    def test_local_jetson_when_tegra_exists(self, mock_exists):
        assert detect_target_env() == "local_jetson"
        mock_exists.assert_called_with("/etc/nv_tegra_release")

    @patch("os.path.exists", return_value=False)
    def test_remote_jetson_when_not_tegra(self, mock_exists):
        assert detect_target_env() == "remote_jetson"


class TestBuildTargetCommand:
    def test_local_returns_bash_lc(self):
        argv = build_target_command("echo hello", "local_jetson")
        assert argv == ["bash", "-lc", "echo hello"]

    def test_remote_returns_ssh_argv(self):
        argv = build_target_command("echo hello", "remote_jetson")
        assert argv[0] == "ssh"
        assert "jetson-nano" in argv
        # Must contain the command quoted for remote shell
        joined = " ".join(argv)
        assert "echo hello" in joined
        assert "bash -lc" in joined

    def test_remote_handles_special_chars(self):
        cmd = "awk '/MemAvailable:/ {print $2}' /proc/meminfo"
        argv = build_target_command(cmd, "remote_jetson")
        # shlex.quote should wrap the entire cmd
        assert argv[0] == "ssh"
        # The command should survive as a single shell argument
        assert len(argv) == 3  # ["ssh", "jetson-nano", "cd ... && bash -lc '...'"]


class TestExecOnTarget:
    @patch("subprocess.run")
    def test_success_returns_stdout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="42\n", stderr="")
        rc, out, err = exec_on_target("echo 42", "local_jetson", timeout_sec=5)
        assert rc == 0
        assert out == "42\n"

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5))
    def test_timeout_returns_minus2(self, mock_run):
        rc, out, err = exec_on_target("sleep 999", "local_jetson", timeout_sec=5)
        assert rc == -2
        assert "timeout" in err.lower()

    @patch("subprocess.run", side_effect=OSError("No such file"))
    def test_transport_failure_returns_minus1(self, mock_run):
        rc, out, err = exec_on_target("echo x", "remote_jetson", timeout_sec=5)
        assert rc == -1
        assert "No such file" in err

    @patch("subprocess.run")
    def test_nonzero_exit_code_passed_through(self, mock_run):
        mock_run.return_value = MagicMock(returncode=127, stdout="", stderr="not found")
        rc, out, err = exec_on_target("badcmd", "local_jetson", timeout_sec=5)
        assert rc == 127
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python3 -m pytest tests/jetson-verify/test_transport.py -v`
Expected: ImportError — `transport` module doesn't exist yet.

- [ ] **Step 3: Implement transport.py**

```python
# .claude/skills/jetson-verify/scripts/transport.py
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
    remote_jetson: ["ssh", "jetson-nano", "cd ... && bash -lc <quoted>"]
    """
    if env == "local_jetson":
        return ["bash", "-lc", cmd]
    # remote — wrap in SSH
    remote_cmd = f"cd /home/jetson/elder_and_dog && bash -lc {shlex.quote(cmd)}"
    return ["ssh", "jetson-nano", remote_cmd]


def exec_on_target(cmd: str, env: str, timeout_sec: int = 10) -> tuple:
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
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python3 -m pytest tests/jetson-verify/test_transport.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/jetson-verify/scripts/transport.py tests/jetson-verify/test_transport.py
git commit -m "feat(skill): add transport.py — target execution abstraction for jetson-verify"
```

---

## Task 2: verify.py — Expect Parser + Core Engine

**Files:**
- Create: `.claude/skills/jetson-verify/scripts/verify.py`
- Create: `tests/jetson-verify/test_expect_parser.py`
- Create: `tests/jetson-verify/test_verify.py`

### Part A: Expect Parser

- [ ] **Step 1: Write expect parser tests**

```python
# tests/jetson-verify/test_expect_parser.py
"""Expect parser unit tests — all 5 operators + edge cases."""
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.claude/skills/jetson-verify/scripts"))
from verify import evaluate_expect


class TestGreaterEqual:
    def test_pass(self):
        assert evaluate_expect("2400", ">= 800") is True

    def test_fail(self):
        assert evaluate_expect("500", ">= 800") is False

    def test_boundary(self):
        assert evaluate_expect("800", ">= 800") is True

    def test_float(self):
        assert evaluate_expect("800.5", ">= 800") is True

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            evaluate_expect("abc", ">= 800")


class TestLessEqual:
    def test_pass(self):
        assert evaluate_expect("60", "<= 75") is True

    def test_fail(self):
        assert evaluate_expect("80", "<= 75") is False

    def test_boundary(self):
        assert evaluate_expect("75", "<= 75") is True


class TestEqual:
    def test_pass(self):
        assert evaluate_expect("1", "== 1") is True

    def test_fail(self):
        assert evaluate_expect("0", "== 1") is False

    def test_float_equal(self):
        assert evaluate_expect("1.0", "== 1") is True


class TestContains:
    def test_pass(self):
        assert evaluate_expect("daemon is running", "contains running") is True

    def test_fail(self):
        assert evaluate_expect("daemon stopped", "contains running") is False

    def test_multiline(self):
        assert evaluate_expect("line1\nrunning\nline3", "contains running") is True


class TestNonempty:
    def test_pass(self):
        assert evaluate_expect("some output", "nonempty") is True

    def test_fail_empty(self):
        assert evaluate_expect("", "nonempty") is False

    def test_fail_whitespace(self):
        assert evaluate_expect("   \n  ", "nonempty") is False


class TestInvalidOperator:
    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown expect"):
            evaluate_expect("42", "!= 42")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python3 -m pytest tests/jetson-verify/test_expect_parser.py -v`
Expected: ImportError — `verify` module not found.

- [ ] **Step 3: Implement verify.py with evaluate_expect**

```python
# .claude/skills/jetson-verify/scripts/verify.py
"""jetson-verify main executor.

Reads YAML profile → runs checks via transport → outputs JSON + summary.

Usage:
    python3 verify.py --profile smoke [--output-dir logs/jetson-verify/]

Exit codes: 0 = PASS, 1 = FAIL, 2 = ERROR/config
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from transport import detect_target_env, exec_on_target

# ── Expect parser ──────────────────────────────────────────────

def evaluate_expect(stdout_stripped: str, expect: str) -> bool:
    """Evaluate stdout against an expect expression.

    Supported operators (v0):
      ">= N", "<= N", "== N"  — numeric comparison
      "contains TEXT"          — substring match
      "nonempty"               — non-empty after strip

    Returns True if expectation met, False if not.
    Raises ValueError on parse failure (non-numeric, unknown operator).
    """
    if expect == "nonempty":
        return len(stdout_stripped.strip()) > 0

    if expect.startswith("contains "):
        text = expect[len("contains "):]
        return text in stdout_stripped

    for op in (">=", "<=", "=="):
        if expect.startswith(op):
            threshold = float(expect[len(op):].strip())
            value = float(stdout_stripped.strip())
            if op == ">=":
                return value >= threshold
            elif op == "<=":
                return value <= threshold
            else:  # ==
                return value == threshold

    raise ValueError(f"Unknown expect operator: {expect!r}")


# ── Check runner ───────────────────────────────────────────────

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"
STATUS_ERROR = "ERROR"


def run_single_check(check: dict, env: str) -> dict:
    """Execute one check, return result record."""
    check_id = check["id"]
    blocking = check["blocking"]
    timeout = check.get("timeout_sec", 10)
    template = check.get("message_template", "")

    start = time.monotonic()

    # ── Precondition ──
    if "precondition" in check:
        rc, _, _ = exec_on_target(check["precondition"], env, timeout_sec=timeout)
        if rc == -1 or rc == -2 or rc > 1:
            elapsed = int((time.monotonic() - start) * 1000)
            reason = "transport failure" if rc == -1 else "timeout" if rc == -2 else f"precondition error (rc={rc})"
            return {
                "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
                "value": None, "message": f"precondition error: {reason}",
                "duration_ms": elapsed,
            }
        if rc == 1:
            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "id": check_id, "status": STATUS_SKIP, "blocking": blocking,
                "value": None, "message": f"precondition not met",
                "duration_ms": elapsed,
            }

    # ── Main command ──
    rc, stdout, stderr = exec_on_target(check["command"], env, timeout_sec=timeout)
    elapsed = int((time.monotonic() - start) * 1000)

    if rc == -1:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": "transport failure",
            "duration_ms": elapsed,
        }
    if rc == -2:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": f"timeout after {timeout}s",
            "duration_ms": elapsed,
        }
    if rc > 0:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": f"command failed (rc={rc}): {stderr.strip()[:120]}",
            "duration_ms": elapsed,
        }

    # ── Evaluate expect ──
    value = stdout.strip()
    try:
        passed = evaluate_expect(value, check["expect"])
    except ValueError as e:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": f"expect parse error: {e}",
            "duration_ms": elapsed,
        }

    if passed:
        status = STATUS_PASS
    else:
        status = STATUS_FAIL if blocking else STATUS_WARN

    message = template.replace("{value}", value) if value else template
    return {
        "id": check_id, "status": status, "blocking": blocking,
        "value": value, "message": message,
        "duration_ms": elapsed,
    }


# ── Profile loader ─────────────────────────────────────────────

def load_profile(profile_name: str, skill_dir: Path) -> dict:
    """Load and validate a YAML profile. Raises SystemExit on error."""
    profile_path = skill_dir / "profiles" / f"{profile_name}.yaml"
    if not profile_path.exists():
        print(f"ERROR: profile not found: {profile_path}", file=sys.stderr)
        sys.exit(2)

    try:
        with open(profile_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {e}", file=sys.stderr)
        sys.exit(2)

    if not data or not isinstance(data.get("checks"), list):
        print(f"ERROR: profile '{profile_name}' has no checks (stub profile?)", file=sys.stderr)
        sys.exit(2)

    min_checks = data.get("min_checks", 1)
    if len(data["checks"]) < min_checks:
        print(f"ERROR: profile '{profile_name}' has {len(data['checks'])} checks, min {min_checks}", file=sys.stderr)
        sys.exit(2)

    return data


# ── Output ─────────────────────────────────────────────────────

def print_summary(profile: str, target: str, results: list, overall: str, duration_ms: int):
    """Print human-readable summary to stderr."""
    W = sys.stderr.write
    W(f"jetson-verify | profile={profile} | target={target}\n")
    W("─" * 50 + "\n")
    for r in results:
        tag = f"[{r['status']}]"
        msg = r.get("message", "")
        dur = f"  ({r['duration_ms']}ms)" if r["status"] != STATUS_SKIP else ""
        W(f"{tag} {r['id']} — {msg}{dur}\n")
    W("─" * 50 + "\n")
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    parts = [f"{s}={counts.get(s, 0)}" for s in ["PASS", "WARN", "FAIL", "SKIP", "ERROR"]]
    W("  ".join(parts) + "\n")
    W(f"Overall: {overall} ({duration_ms}ms)\n")


def write_json_output(report: dict, output_dir: Path):
    """Write JSON to file + update latest.json symlink."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = report["timestamp"].replace(":", "").replace("-", "").replace("T", "_").split("+")[0]
    filename = f"verify_{ts}.json"
    filepath = output_dir / filename
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    latest = output_dir / "latest.json"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(filename)


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="jetson-verify: deployment health checks")
    parser.add_argument("--profile", required=True, help="Profile name (e.g., smoke)")
    parser.add_argument("--output-dir", default="logs/jetson-verify",
                        help="Directory for JSON output (default: logs/jetson-verify)")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent.parent
    profile_data = load_profile(args.profile, skill_dir)
    env = detect_target_env()

    # SSH connectivity check for remote
    if env == "remote_jetson":
        rc, _, err = exec_on_target("echo ok", env, timeout_sec=5)
        if rc != 0:
            print(f"ERROR: cannot reach jetson-nano: {err}", file=sys.stderr)
            sys.exit(2)

    # Run checks
    total_start = time.monotonic()
    results = []
    for check in profile_data["checks"]:
        result = run_single_check(check, env)
        results.append(result)
    total_ms = int((time.monotonic() - total_start) * 1000)

    # Compute overall
    has_error = any(r["status"] == STATUS_ERROR for r in results)
    has_blocking_fail = any(r["status"] == STATUS_FAIL and r["blocking"] for r in results)

    if has_error:
        overall = "ERROR"
        exit_code = 2
    elif has_blocking_fail:
        overall = "FAIL"
        exit_code = 1
    else:
        overall = "PASS"
        exit_code = 0

    # Build report
    summary = {}
    for s in ["PASS", "WARN", "FAIL", "SKIP", "ERROR"]:
        summary[s.lower()] = sum(1 for r in results if r["status"] == s)

    tz = timezone(timedelta(hours=8))
    report = {
        "profile": args.profile,
        "target": env,
        "timestamp": datetime.now(tz).isoformat(),
        "overall": overall,
        "exit_code": exit_code,
        "duration_ms": total_ms,
        "summary": summary,
        "checks": results,
    }

    # Output
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    print_summary(args.profile, env, results, overall, total_ms)
    write_json_output(report, Path(args.output_dir))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run expect parser tests — verify they pass**

Run: `python3 -m pytest tests/jetson-verify/test_expect_parser.py -v`
Expected: All 14 tests PASS.

### Part B: verify.py Integration Tests

- [ ] **Step 5: Write verify.py integration tests**

```python
# tests/jetson-verify/test_verify.py
"""verify.py integration tests — mock transport, test full pipeline."""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.claude/skills/jetson-verify/scripts"))
from verify import run_single_check, STATUS_PASS, STATUS_WARN, STATUS_FAIL, STATUS_SKIP, STATUS_ERROR


def make_check(id="test.check", command="echo 42", expect=">= 1",
               blocking=True, timeout_sec=5, message_template="{value}",
               precondition=None):
    c = {"id": id, "command": command, "expect": expect,
         "blocking": blocking, "timeout_sec": timeout_sec,
         "message_template": message_template}
    if precondition:
        c["precondition"] = precondition
    return c


class TestRunSingleCheck:
    @patch("verify.exec_on_target", return_value=(0, "2400\n", ""))
    def test_pass(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800"), "local_jetson")
        assert result["status"] == STATUS_PASS
        assert result["value"] == "2400"

    @patch("verify.exec_on_target", return_value=(0, "500\n", ""))
    def test_fail_blocking(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800", blocking=True), "local_jetson")
        assert result["status"] == STATUS_FAIL

    @patch("verify.exec_on_target", return_value=(0, "500\n", ""))
    def test_warn_non_blocking(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800", blocking=False), "local_jetson")
        assert result["status"] == STATUS_WARN

    @patch("verify.exec_on_target", return_value=(-2, "", "timeout after 5s"))
    def test_timeout_error(self, mock_exec):
        result = run_single_check(make_check(), "local_jetson")
        assert result["status"] == STATUS_ERROR
        assert result["value"] is None

    @patch("verify.exec_on_target", return_value=(-1, "", "SSH failed"))
    def test_transport_error(self, mock_exec):
        result = run_single_check(make_check(), "local_jetson")
        assert result["status"] == STATUS_ERROR

    @patch("verify.exec_on_target", return_value=(127, "", "not found"))
    def test_nonzero_rc_error(self, mock_exec):
        result = run_single_check(make_check(), "local_jetson")
        assert result["status"] == STATUS_ERROR
        assert "rc=127" in result["message"]

    @patch("verify.exec_on_target", return_value=(0, "abc\n", ""))
    def test_parse_error_is_error(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800"), "local_jetson")
        assert result["status"] == STATUS_ERROR
        assert "parse error" in result["message"]


class TestPrecondition:
    @patch("verify.exec_on_target")
    def test_precondition_pass_runs_check(self, mock_exec):
        mock_exec.side_effect = [(0, "", ""), (0, "42\n", "")]
        result = run_single_check(
            make_check(precondition="grep -q node", expect=">= 1"), "local_jetson"
        )
        assert result["status"] == STATUS_PASS
        assert mock_exec.call_count == 2

    @patch("verify.exec_on_target", return_value=(1, "", ""))
    def test_precondition_rc1_skip(self, mock_exec):
        result = run_single_check(
            make_check(precondition="grep -q missing"), "local_jetson"
        )
        assert result["status"] == STATUS_SKIP
        assert result["value"] is None

    @patch("verify.exec_on_target", return_value=(127, "", "command not found"))
    def test_precondition_rc_gt1_error(self, mock_exec):
        result = run_single_check(
            make_check(precondition="badcmd"), "local_jetson"
        )
        assert result["status"] == STATUS_ERROR
        assert "rc=127" in result["message"]

    @patch("verify.exec_on_target", return_value=(-1, "", "SSH down"))
    def test_precondition_transport_error(self, mock_exec):
        result = run_single_check(
            make_check(precondition="echo test"), "local_jetson"
        )
        assert result["status"] == STATUS_ERROR

    @patch("verify.exec_on_target", return_value=(-2, "", "timeout"))
    def test_precondition_timeout_error(self, mock_exec):
        result = run_single_check(
            make_check(precondition="slow_cmd"), "local_jetson"
        )
        assert result["status"] == STATUS_ERROR
        assert result["value"] is None


class TestOverallComputation:
    """Test overall priority: ERROR > blocking FAIL > PASS."""

    def _compute(self, statuses_and_blocking):
        """Helper: given list of (status, blocking), compute overall."""
        results = [{"status": s, "blocking": b} for s, b in statuses_and_blocking]
        has_error = any(r["status"] == STATUS_ERROR for r in results)
        has_blocking_fail = any(r["status"] == STATUS_FAIL and r["blocking"] for r in results)
        if has_error:
            return "ERROR"
        if has_blocking_fail:
            return "FAIL"
        return "PASS"

    def test_all_pass(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_PASS, False)]) == "PASS"

    def test_warn_still_pass(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_WARN, False)]) == "PASS"

    def test_skip_still_pass(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_SKIP, False)]) == "PASS"

    def test_blocking_fail_is_fail(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_FAIL, True)]) == "FAIL"

    def test_error_beats_fail(self):
        assert self._compute([(STATUS_FAIL, True), (STATUS_ERROR, False)]) == "ERROR"

    def test_error_alone(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_ERROR, True)]) == "ERROR"
```

- [ ] **Step 6: Run all tests — verify they pass**

Run: `python3 -m pytest tests/jetson-verify/ -v`
Expected: All tests PASS (~27 total: 7 transport + 14 expect + ~12 verify).

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/jetson-verify/scripts/verify.py tests/jetson-verify/
git commit -m "feat(skill): add verify.py — YAML-driven check executor with expect parser"
```

---

## Task 3: YAML Profiles + SKILL.md + Gotchas + Output Dir

**Files:**
- Create: `.claude/skills/jetson-verify/profiles/smoke.yaml`
- Create: `.claude/skills/jetson-verify/profiles/integration.yaml`
- Create: `.claude/skills/jetson-verify/profiles/demo.yaml`
- Create: `.claude/skills/jetson-verify/SKILL.md`
- Create: `.claude/skills/jetson-verify/references/gotchas.md`
- Create: `logs/jetson-verify/.gitkeep`

- [ ] **Step 1: Create smoke.yaml**

Copy the complete 9-check YAML from spec Section 5.5 into `.claude/skills/jetson-verify/profiles/smoke.yaml`. All 9 checks must be present:

1. `system.memory` — awk /proc/meminfo, expect `>= 800`, blocking
2. `system.disk` — df /home, expect `>= 500`, blocking
3. `system.gpu_temp` — thermal_zone1, expect `<= 75`, **non-blocking**
4. `ros2.daemon` — ros2 daemon status | grep -c 'is running' || true, expect `>= 1`, blocking
5. `ros2.topic_count` — ros2 topic list | wc -l, expect `>= 1`, blocking
6. `module.face.state_publishing` — precondition: face_identity_node, echo /state/perception/face, **non-blocking**
7. `module.speech.state_publishing` — precondition: stt_intent_node, echo /state/interaction/speech, **non-blocking**
8. `module.vision.node_alive` — precondition: vision_perception_node, topic hz with `timeout 8`, timeout_sec=12, **non-blocking**
9. `module.go2.webrtc_subscriber` — precondition: go2_driver_node, awk Subscription count, **non-blocking**

The file starts with:

```yaml
profile: smoke
description: "部署後基本健康檢查：system → ROS2 → modules"
min_checks: 1

checks:
  - id: system.memory
    command: "awk '/MemAvailable:/ {print int($2/1024)}' /proc/meminfo"
    expect: ">= 800"
    blocking: true
    timeout_sec: 5
    message_template: "{value}MB available (min 800MB)"
# ... remaining 8 checks — copy verbatim from spec Section 5.5
```

- [ ] **Step 2: Create stub profiles**

```yaml
# .claude/skills/jetson-verify/profiles/integration.yaml
# TODO: v1 — multi-module coexistence, resource budgets, prerequisites
# This profile is intentionally empty. verify.py will refuse to run it.
profile: integration
description: "多模組共存前置檢查"
checks: []
```

```yaml
# .claude/skills/jetson-verify/profiles/demo.yaml
# TODO: v2 — demo readiness checklist, go/no-go report
# This profile is intentionally empty. verify.py will refuse to run it.
profile: demo
description: "展示前 readiness check"
checks: []
```

- [ ] **Step 3: Create SKILL.md**

Copy the complete SKILL.md from spec Section 7 into `.claude/skills/jetson-verify/SKILL.md`.

- [ ] **Step 4: Create references/gotchas.md**

```markdown
# jetson-verify Gotchas

Known pitfalls — add new entries as they surface.

1. **check commands 一律用 `setup.bash`，不可用 `setup.zsh`**：transport.py 強制 `bash -lc`，在 bash shell 裡 source zsh script 會出錯。雖然 Jetson 日常用 zsh，但 verify 的 transport 走 bash。

2. **`system.gpu_temp` 的 thermal zone 路徑**：`thermal_zone1` 在 Jetson Orin Nano 上指向 GPU-therm，但不保證跨 Jetson 型號一致。換硬體時需要用 `cat /sys/class/thermal/thermal_zone*/type` 確認。

3. **`ros2 topic hz` 是永不退出的命令**：`module.vision.node_alive` 用 `timeout 8` 包在命令內部，讓它在 8s 後自行終止，避免 transport timeout (-2) 把它升級為 ERROR。`timeout_sec: 12` 比內部 timeout 寬裕，確保 transport 不會先殺掉命令。

4. **`detect_target_env()` 的假設**：非 Jetson 環境一律視為 `remote_jetson`，假設 SSH 到 jetson-nano 可用。這包含 WSL、macOS、CI container 等所有非 Jetson 平台。

5. **`grep -c` 和其他可能回非零的命令必須尾綴 `|| true`**：因為 `rc > 0` → ERROR，check commands 必須確保正常情境下 rc=0。`grep -c 'pattern' || true` 讓 grep 無匹配時回 rc=0 + stdout="0"，由 expect parser 判斷 PASS/FAIL。

6. **precondition 的 `grep -q` 不需要 `|| true`**：precondition 語意是 rc==0 → run，rc==1 → SKIP。`grep -q` 的 rc=1（無匹配）正好是「條件不成立」= SKIP，不需要強制 rc=0。

7. **v1 考慮加 `--dry-run` 參數**：載入 YAML 並印出 check 列表但不執行，方便開發和測試新 profile。
```

- [ ] **Step 5: Create output directory + gitignore**

```bash
mkdir -p logs/jetson-verify
touch logs/jetson-verify/.gitkeep
echo "logs/jetson-verify/*.json" >> .gitignore
```

- [ ] **Step 6: Verify stub profile rejection**

Run: `python3 .claude/skills/jetson-verify/scripts/verify.py --profile integration 2>&1; echo "exit=$?"`
Expected: stderr shows `ERROR: profile 'integration' has no checks (stub profile?)`, exit=2.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/jetson-verify/profiles/ .claude/skills/jetson-verify/SKILL.md \
        .claude/skills/jetson-verify/references/ logs/jetson-verify/.gitkeep .gitignore
git commit -m "feat(skill): add smoke.yaml, SKILL.md, gotchas, stub profiles, output dir"
```

---

## Task 4: PyYAML Check + Local Dry Run

**Files:**
- None created

- [ ] **Step 1: Verify PyYAML available**

Run: `python3 -c "import yaml; print(yaml.__version__)"`
Expected: Prints version. If ImportError: `uv pip install pyyaml`

- [ ] **Step 2: Local dry run of verify.py (WSL, remote mode)**

This tests the full pipeline on WSL pointing at Jetson via SSH. If Jetson is unreachable, expect exit 2 with SSH error — that's correct behavior confirming the transport path works.

Run:
```bash
cd /home/roy422/newLife/elder_and_dog
python3 .claude/skills/jetson-verify/scripts/verify.py --profile smoke 2>verify_stderr.txt; echo "exit=$?"
cat verify_stderr.txt
```

Expected (if Jetson reachable): JSON on stdout, summary on stderr, `logs/jetson-verify/latest.json` created.
Expected (if Jetson unreachable): exit=2, stderr says "cannot reach jetson-nano".

- [ ] **Step 4: Verify JSON output structure**

```bash
cat logs/jetson-verify/latest.json | python3 -m json.tool > /dev/null && echo "valid JSON"
python3 -c "
import json
with open('logs/jetson-verify/latest.json') as f:
    d = json.load(f)
assert 'profile' in d
assert 'overall' in d
assert 'checks' in d
assert isinstance(d['checks'], list)
print(f'profile={d[\"profile\"]} overall={d[\"overall\"]} checks={len(d[\"checks\"])}')
"
```

- [ ] **Step 5: Run full test suite one final time**

Run: `python3 -m pytest tests/jetson-verify/ -v`
Expected: All tests PASS.

- [ ] **Step 5: Final commit (if any remaining changes)**

```bash
git status
# If any unstaged changes remain, add and commit them
```

---

## Post-Implementation Checklist

After all 4 tasks are done:

- [ ] `python3 -m pytest tests/jetson-verify/ -v` — all green
- [ ] `python3 .claude/skills/jetson-verify/scripts/verify.py --profile smoke` — runs without crash (PASS or ERROR depending on SSH)
- [ ] `python3 .claude/skills/jetson-verify/scripts/verify.py --profile integration` — exits 2 with stub message
- [ ] `logs/jetson-verify/latest.json` exists and is valid JSON
- [ ] All files committed to git

## Manual Follow-up (not part of implementation tasks)

- [ ] Install ralph-loop: `claude plugin install ralph-loop`
- [ ] Verify: `/ralph-loop:help`
- [ ] SSH 到 Jetson 跑一次真實 smoke: `python3 .claude/skills/jetson-verify/scripts/verify.py --profile smoke`
