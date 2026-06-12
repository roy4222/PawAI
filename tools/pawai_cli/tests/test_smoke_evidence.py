"""pawai smoke brain / pawai evidence pull (system Phase 2 T2C-1/2/3).

Every shell interaction is mocked (conftest T2C-0 pins PAWAI_REPO_ROOT /
JETSON_HOST; per-test patches cover run_remote / stream_remote / stream) —
no SSH, no rsync, no network, suite stays sub-second. Structured-error paths
(T2C-3) assert the fix-suggestion lines verbatim enough to catch regressions.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from pawai_cli.main import cli
from pawai_cli.shell import Result


def _invoke(args):
    return CliRunner().invoke(cli, args)


# ── pawai smoke brain (T2C-1) ───────────────────────────────────────────────

def test_smoke_brain_runs_remote_script_with_rounds():
    calls: dict = {}

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
    assert "bash scripts/smoke_test_e2e.sh 3" in calls["stream"]


def test_smoke_brain_default_is_5_rounds():
    calls: dict = {}
    with patch("pawai_cli.main.shell.run_remote", return_value=Result(0, "", "")), \
         patch("pawai_cli.main.shell.stream_remote",
               side_effect=lambda cmd: calls.setdefault("stream", cmd) and 0):
        result = _invoke(["smoke", "brain"])
    assert result.exit_code == 0, result.output
    assert "bash scripts/smoke_test_e2e.sh 5" in calls["stream"]


def test_smoke_brain_ssh_unreachable_names_the_fix():
    with patch("pawai_cli.main.shell.run_remote",
               return_value=Result(255, "", "ssh: connect to host ... timed out")):
        result = _invoke(["smoke", "brain"])
    assert result.exit_code != 0
    assert "SSH" in result.output
    assert "pawai doctor" in result.output          # T2C-3 fix hint


def test_smoke_brain_missing_remote_script_fail_closed():
    with patch("pawai_cli.main.shell.run_remote", return_value=Result(1, "", "")):
        result = _invoke(["smoke", "brain"])
    assert result.exit_code != 0
    assert "scripts/smoke_test_e2e.sh" in result.output
    assert "pawai jetson deploy" in result.output   # sync suggestion


def test_smoke_brain_nonzero_rc_propagates_with_hint():
    with patch("pawai_cli.main.shell.run_remote", return_value=Result(0, "", "")), \
         patch("pawai_cli.main.shell.stream_remote", return_value=2):
        result = _invoke(["smoke", "brain"])
    assert result.exit_code == 2
    assert "pawai health brain" in result.output    # next-step hint


# ── pawai evidence pull (T2C-2) ─────────────────────────────────────────────

def _fake_rsync_writing(files: dict[str, str]):
    """Return a shell.stream fake that simulates rsync materializing files."""
    calls: dict = {}

    def fake_stream(argv, cwd=None, env=None):
        calls["argv"] = list(argv)
        dest = Path(list(argv)[-1])
        dest.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (dest / name).write_text(content, encoding="utf-8")
        return 0

    return calls, fake_stream


def test_evidence_pull_rsync_argv_read_only():
    calls, fake = _fake_rsync_writing(
        {"s1.jsonl": '{"ts": 1, "verdict": "suppressed"}\n{"ts": 2, "verdict": "accepted"}\n'}
    )
    with patch("pawai_cli.evidence.shell.stream", side_effect=fake):
        result = _invoke(["evidence", "pull"])
    assert result.exit_code == 0, result.output
    argv = calls["argv"]
    assert argv[0] == "rsync"
    assert "--delete" not in argv                       # pull NEVER deletes
    assert argv[-2] == "jetson-test:/home/jetson/elder_and_dog/runtime/traces/"
    assert argv[-1].endswith("artifacts/evidence/traces/")


def test_evidence_pull_prints_summary():
    calls, fake = _fake_rsync_writing({
        "s1.jsonl": '{"ts": 1, "verdict": "suppressed"}\n{"ts": 2, "verdict": "accepted"}\n',
        "s2.jsonl": '{"ts": 3, "verdict": "suppressed"}\nGARBAGE-LINE\n',
    })
    with patch("pawai_cli.evidence.shell.stream", side_effect=fake):
        result = _invoke(["evidence", "pull"])
    assert result.exit_code == 0, result.output
    assert "2 file(s)" in result.output
    assert "3 event(s)" in result.output                # garbage line skipped
    assert "2 suppressed" in result.output


def test_evidence_pull_custom_dest(tmp_path):
    calls, fake = _fake_rsync_writing({"s1.jsonl": '{"ts": 1}\n'})
    dest = tmp_path / "my-evidence"
    with patch("pawai_cli.evidence.shell.stream", side_effect=fake):
        result = _invoke(["evidence", "pull", "--dest", str(dest)])
    assert result.exit_code == 0, result.output
    assert calls["argv"][-1] == f"{dest}/"


def test_evidence_pull_rsync_missing_names_install_fix():
    with patch("pawai_cli.evidence.shell.stream", return_value=127):
        result = _invoke(["evidence", "pull"])
    assert result.exit_code != 0
    assert "rsync" in result.output
    assert "install" in result.output                   # install hint


def test_evidence_pull_ssh_fail_names_doctor_and_store():
    with patch("pawai_cli.evidence.shell.stream", return_value=255):
        result = _invoke(["evidence", "pull"])
    assert result.exit_code != 0
    assert "pawai doctor" in result.output
    assert "PAWAI_TRACE_STORE_ENABLED" in result.output  # empty-store hint


# ── summarize helper (pure) ─────────────────────────────────────────────────

def test_summarize_jsonl_dir_counts(tmp_path):
    from pawai_cli.evidence import summarize_jsonl_dir
    (tmp_path / "a.jsonl").write_text(
        '{"ts": 1, "verdict": "suppressed"}\n{"ts": 2}\nnot-json\n', encoding="utf-8")
    (tmp_path / "b.jsonl").write_text('{"ts": 3, "verdict": "suppressed"}\n',
                                      encoding="utf-8")
    summary = summarize_jsonl_dir(tmp_path)
    assert summary == {"files": 2, "events": 3, "suppressed": 2}


def test_summarize_jsonl_dir_empty(tmp_path):
    from pawai_cli.evidence import summarize_jsonl_dir
    assert summarize_jsonl_dir(tmp_path) == {"files": 0, "events": 0, "suppressed": 0}
