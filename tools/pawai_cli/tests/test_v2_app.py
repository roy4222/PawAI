"""PawAI CLI v2 (Typer + Rich) parallel skeleton — tests (first batch).

Everything is mocked: conftest T2C-0 pins PAWAI_REPO_ROOT / JETSON_HOST and
refuses un-mocked ssh/rsync, so this suite never touches the network. The key
guarantee these tests enforce is PARITY: v2 commands must delegate to the exact
legacy Click callbacks with the exact kwargs the legacy binary uses — v2 must
NOT reimplement lock / deploy / cleanup / smoke / evidence logic.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("typer")  # v2 deps are an optional [v2] extra; skip when absent (CI base install)

from typer.testing import CliRunner

from pawai_cli import platform as plat
from pawai_cli.shell import Result
from pawai_cli.v2.app import app

runner = CliRunner()


def _invoke(args):
    return runner.invoke(app, args)


# ── help snapshot ────────────────────────────────────────────────────────────

def test_v2_help_lists_first_batch_commands():
    result = _invoke(["--help"])
    assert result.exit_code == 0, result.output
    out = result.output
    # Top-level commands wired in the first batch.
    for cmd in ("doctor", "status", "logs", "smoke", "evidence", "demo"):
        assert cmd in out, f"missing {cmd} in help:\n{out}"


def test_v2_version_flag():
    result = _invoke(["--version"])
    assert result.exit_code == 0, result.output
    assert "pawai2" in result.output


def test_v2_smoke_help_lists_subset():
    result = _invoke(["smoke", "--help"])
    assert result.exit_code == 0, result.output
    for sub in ("brain", "object", "nav-static"):
        assert sub in result.output
    # vision / full are intentionally deferred to a later batch.
    assert "vision" not in result.output
    assert "full" not in result.output


# ── platform gate (Windows native → exit 10, parity with legacy) ─────────────

def test_v2_platform_gate_windows_native_exits_10():
    info = plat.PlatformInfo(kind="windows_native", supported=False,
                             reason="Windows native unsupported")
    with patch("pawai_cli.platform.detect", return_value=info):
        result = _invoke(["doctor"])
    assert result.exit_code == 10
    # Gate's own message steers users to WSL2 — v2 does NOT soft-support PS.
    assert "wsl --install" in result.output


def test_v2_platform_gate_mnt_c_exits_10():
    info = plat.PlatformInfo(kind="wsl2", supported=True, reason="")
    with patch("pawai_cli.platform.detect", return_value=info), \
         patch("pawai_cli.v2.app.shell.repo_root",
               return_value=__import__("pathlib").Path("/mnt/c/Users/foo/repo")):
        result = _invoke(["status"])
    assert result.exit_code == 10
    assert "/mnt/c" in result.output


# ── doctor (mocked) ──────────────────────────────────────────────────────────

def test_v2_doctor_delegates_to_legacy_callback():
    """doctor must call the legacy `doctor` callback with mapped kwargs."""
    captured = {}

    def fake_doctor(**kwargs):
        captured.update(kwargs)
        raise SystemExit(0)

    legacy = SimpleNamespace(callback=fake_doctor)
    legacy_cli = SimpleNamespace(commands={"doctor": legacy})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["doctor", "--deep", "--cache", "7"])
    assert result.exit_code == 0, result.output
    # `--cache N` maps to the legacy `cache_seconds` parameter name.
    assert captured == {"verbose": False, "expect_demo": False, "fix": False,
                        "deep": True, "cache_seconds": 7}


def test_v2_doctor_blocking_exit_code_propagates():
    """Legacy doctor SystemExit(2) (blocking findings) must surface as exit 2."""
    def fake_doctor(**kwargs):
        raise SystemExit(2)

    legacy = SimpleNamespace(callback=fake_doctor)
    legacy_cli = SimpleNamespace(commands={"doctor": legacy})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["doctor"])
    assert result.exit_code == 2


# ── status (mocked) ──────────────────────────────────────────────────────────

def test_v2_status_delegates_and_passes_short():
    captured = {}

    def fake_status(**kwargs):
        captured.update(kwargs)
        # legacy `status` returns normally (no SystemExit) → v2 exits 0

    legacy = SimpleNamespace(callback=fake_status)
    legacy_cli = SimpleNamespace(commands={"status": legacy})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["status", "--short"])
    assert result.exit_code == 0, result.output
    assert captured == {"short": True}


def test_v2_status_real_collect_mocked_unreachable():
    """End-to-end through the real legacy status, with the SSH probe mocked
    unreachable (conftest would otherwise refuse the ssh)."""
    with patch("pawai_cli.status.shell.run_remote",
               return_value=Result(255, "", "ssh failed")):
        result = _invoke(["status", "--short"])
    assert result.exit_code == 0, result.output
    assert "unreachable" in result.output.lower()


# ── logs (mocked) ────────────────────────────────────────────────────────────

def test_v2_logs_delegates_with_module_and_lines():
    captured = {}

    def fake_logs(**kwargs):
        captured.update(kwargs)

    legacy = SimpleNamespace(callback=fake_logs)
    legacy_cli = SimpleNamespace(commands={"logs": legacy})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["logs", "brain", "--lines", "200"])
    assert result.exit_code == 0, result.output
    assert captured == {"module": "brain", "lines": 200}


# ── smoke command-construction (real legacy callbacks, SSH mocked) ───────────

def test_v2_smoke_brain_builds_correct_ssh_command():
    calls = {}

    def fake_run_remote(cmd, timeout=None):
        calls["probe"] = cmd
        return Result(0, "", "")

    def fake_stream_remote(cmd):
        calls["stream"] = cmd
        return 0

    with patch("pawai_cli.main.shell.run_remote", side_effect=fake_run_remote), \
         patch("pawai_cli.main.shell.stream_remote", side_effect=fake_stream_remote):
        result = _invoke(["smoke", "brain", "--rounds", "3"])

    assert result.exit_code == 0, result.output
    assert "scripts/smoke_test_e2e.sh" in calls["probe"]
    assert "cd /home/jetson/elder_and_dog" in calls["stream"]
    assert "source /opt/ros/humble/setup.zsh" in calls["stream"]
    assert "bash scripts/smoke_test_e2e.sh 3" in calls["stream"]


def test_v2_smoke_brain_default_rounds_is_5():
    calls = {}
    with patch("pawai_cli.main.shell.run_remote", return_value=Result(0, "", "")), \
         patch("pawai_cli.main.shell.stream_remote",
               side_effect=lambda cmd: calls.setdefault("stream", cmd) and 0):
        result = _invoke(["smoke", "brain"])
    assert result.exit_code == 0, result.output
    assert "bash scripts/smoke_test_e2e.sh 5" in calls["stream"]


def test_v2_smoke_brain_ssh_unreachable_names_doctor():
    with patch("pawai_cli.main.shell.run_remote",
               return_value=Result(255, "", "ssh: timed out")):
        result = _invoke(["smoke", "brain"])
    assert result.exit_code != 0
    assert "pawai doctor" in result.output


def test_v2_smoke_object_builds_correct_ssh_command():
    calls = {}
    with patch("pawai_cli.main.shell.run_remote", return_value=Result(0, "", "")), \
         patch("pawai_cli.main.shell.stream_remote",
               side_effect=lambda cmd: calls.setdefault("stream", cmd) and 0):
        result = _invoke(["smoke", "object", "--with-cup"])
    assert result.exit_code == 0, result.output
    assert "scripts/smoke_test_object.sh" in calls["stream"]
    assert "--with-cup" in calls["stream"]


def test_v2_smoke_nav_static_hardwires_static_flag():
    """`smoke nav-static` must pass static_only=True to the legacy nav smoke —
    motion regression stays HITL and is never exposed in v2."""
    calls = {}
    with patch("pawai_cli.main.Lock.read", return_value=None), \
         patch("pawai_cli.main.shell.run_remote", return_value=Result(0, "", "")), \
         patch("pawai_cli.main.shell.stream_remote",
               side_effect=lambda cmd: calls.setdefault("stream", cmd) and 0):
        result = _invoke(["smoke", "nav-static"])
    assert result.exit_code == 0, result.output
    assert "scripts/smoke_test_nav_static.sh" in calls["stream"]


def test_v2_smoke_nav_static_blocked_by_brain_lock():
    """Parity with legacy `smoke nav --static`: a brain lock blocks before SSH."""
    run_remote = Mock(return_value=Result(0, "", ""))
    stream_remote = Mock(return_value=0)
    with patch("pawai_cli.main.Lock.read", return_value=SimpleNamespace(lane="brain")), \
         patch("pawai_cli.main.shell.run_remote", run_remote), \
         patch("pawai_cli.main.shell.stream_remote", stream_remote):
        result = _invoke(["smoke", "nav-static"])
    assert result.exit_code != 0
    assert "互斥" in result.output
    run_remote.assert_not_called()
    stream_remote.assert_not_called()


# ── evidence pull command-construction (read-only) ───────────────────────────

def test_v2_evidence_pull_rsync_is_read_only():
    seen = []

    def fake_stream(argv, cwd=None, env=None):
        seen.append(list(argv))
        return 0

    with patch("pawai_cli.evidence.shell.stream", side_effect=fake_stream):
        result = _invoke(["evidence", "pull"])
    assert result.exit_code == 0, result.output
    sources = [argv[-2] for argv in seen]
    assert any(s.endswith("runtime/traces/") for s in sources)
    for argv in seen:
        assert argv[0] == "rsync"
        assert "--delete" not in argv          # pull NEVER deletes


def test_v2_evidence_pull_custom_dest(tmp_path):
    seen = {}

    def fake_stream(argv, cwd=None, env=None):
        seen["argv"] = list(argv)
        return 0

    dest = tmp_path / "my-evidence"
    with patch("pawai_cli.evidence.shell.stream", side_effect=fake_stream):
        result = _invoke(["evidence", "pull", "--dest", str(dest)])
    assert result.exit_code == 0, result.output
    assert seen["argv"][-1] == f"{dest}/"


def test_v2_evidence_pull_rsync_missing_names_install_fix():
    with patch("pawai_cli.evidence.shell.stream", return_value=127):
        result = _invoke(["evidence", "pull"])
    assert result.exit_code != 0
    assert "rsync" in result.output
    assert "install" in result.output


# ── demo start / stop PARITY (the rollback-critical guarantee) ───────────────

def test_v2_demo_start_kwargs_match_legacy_signature():
    """v2 demo start must call the legacy callback with EXACTLY the legacy
    parameter set — no extra, no missing. This is the core parity contract:
    lock/deploy/cleanup core is the legacy callback, v2 only forwards args."""
    from pawai_cli.v2.app import _legacy_demo_start_params

    legacy_params = _legacy_demo_start_params()
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)

    legacy_start = SimpleNamespace(callback=fake_start)
    legacy_demo = SimpleNamespace(commands={"start": legacy_start})
    legacy_cli = SimpleNamespace(commands={"demo": legacy_demo})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["demo", "start", "--brain-only", "-y"])
    assert result.exit_code == 0, result.output
    # Exact 1:1 parameter parity with the legacy demo-start callback.
    assert set(captured) == legacy_params
    # And the forwarded values reflect the CLI flags faithfully.
    assert captured["brain_only"] is True
    assert captured["yes"] is True
    assert captured["force"] is False
    assert captured["nav_mode"] is None


def test_v2_demo_start_nav_capability_forwarded():
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)

    legacy_start = SimpleNamespace(callback=fake_start)
    legacy_demo = SimpleNamespace(commands={"start": legacy_start})
    legacy_cli = SimpleNamespace(commands={"demo": legacy_demo})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["demo", "start", "--nav", "capability", "--force"])
    assert result.exit_code == 0, result.output
    assert captured["nav_mode"] == "capability"
    assert captured["force"] is True


def test_v2_demo_start_lock_collision_exit_code_propagates():
    """When legacy demo start SystemExit(2)s on a `-y` lock collision, v2 must
    surface exit 2 — it does not swallow or remap the lock semantics."""
    def fake_start(**kwargs):
        raise SystemExit(2)

    legacy_start = SimpleNamespace(callback=fake_start)
    legacy_demo = SimpleNamespace(commands={"start": legacy_start})
    legacy_cli = SimpleNamespace(commands={"demo": legacy_demo})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["demo", "start", "-y"])
    assert result.exit_code == 2


def test_v2_demo_stop_delegates_force_flag():
    captured = {}

    def fake_stop(**kwargs):
        captured.update(kwargs)
        raise SystemExit(0)

    legacy_stop = SimpleNamespace(callback=fake_stop)
    legacy_demo = SimpleNamespace(commands={"stop": legacy_stop})
    legacy_cli = SimpleNamespace(commands={"demo": legacy_demo})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["demo", "stop", "--force"])
    assert result.exit_code == 0, result.output
    assert captured == {"force": True}

    # Parity: the legacy stop callback only takes `force`.
    from pawai_cli.main import cli as real_cli
    real_params = set(inspect.signature(
        real_cli.commands["demo"].commands["stop"].callback).parameters)
    assert set(captured) == real_params


# ── ClickException rendering through the delegation boundary ──────────────────

def test_v2_click_exception_renders_and_exits_1():
    import click

    def fake_logs(**kwargs):
        raise click.ClickException("module unknown: bogus")

    legacy = SimpleNamespace(callback=fake_logs)
    legacy_cli = SimpleNamespace(commands={"logs": legacy})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["logs", "bogus"])
    assert result.exit_code == 1
    assert "module unknown: bogus" in result.output


def test_v2_abort_renders_and_exits_1():
    import click

    def fake_stop(**kwargs):
        raise click.exceptions.Abort()

    legacy_stop = SimpleNamespace(callback=fake_stop)
    legacy_demo = SimpleNamespace(commands={"stop": legacy_stop})
    legacy_cli = SimpleNamespace(commands={"demo": legacy_demo})
    with patch("pawai_cli.main.cli", legacy_cli):
        result = _invoke(["demo", "stop"])
    assert result.exit_code == 1
    assert "Aborted" in result.output


# ── legacy `pawai` remains byte-identical (additive guarantee) ───────────────

def test_legacy_pawai_entry_unchanged_and_lacks_v2_commands():
    """The legacy Click `pawai` must NOT have grown a `nav-static` smoke or any
    v2-only surface — v2 is a separate binary, not a mutation of legacy."""
    from pawai_cli.main import cli as legacy_cli

    smoke = legacy_cli.commands["smoke"]
    # Legacy keeps `nav` (with --static), NOT a renamed `nav-static`.
    assert "nav" in smoke.commands
    assert "nav-static" not in smoke.commands
    # Legacy entry callback is still the original group.
    assert legacy_cli.name == "cli" or legacy_cli.name is None
