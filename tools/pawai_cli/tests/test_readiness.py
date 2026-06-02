from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from pawai_cli.main import cli

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "pawai_brain/test/fixtures/baseline_snapshot.example.json"
NOW_ISO = "2026-06-18T10:00:00+00:00"


def _snapshot_path(tmp_path: Path, mutator=None) -> Path:
    snapshot = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if mutator is not None:
        mutator(snapshot)
    path = tmp_path / "baseline_snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path


def _invoke_readiness(args, *, manifest=None):
    with patch(
        "pawai_cli.readiness._read_last_deploy_remote",
        return_value=manifest or {"git_sha": "abc1234"},
    ), patch("pawai_cli.readiness._now_iso", return_value=NOW_ISO):
        return CliRunner().invoke(cli, ["readiness", *args])


def test_readiness_json_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("PAWAI_SCOREBOARD_PATH", str(_snapshot_path(tmp_path)))

    result = _invoke_readiness(["--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "ready"
    assert payload["reasons"] == []


def test_readiness_accept_warnings_records_override(monkeypatch, tmp_path):
    snapshot_path = _snapshot_path(
        tmp_path,
        lambda snapshot: snapshot.__setitem__(
            "layer0_preflight_status",
            "pass_with_warnings",
        ),
    )
    monkeypatch.setenv("PAWAI_SCOREBOARD_PATH", str(snapshot_path))

    result = _invoke_readiness(
        [
            "--json",
            "--accept-warnings",
            "--operator",
            "roy",
            "--reason",
            "demo warning accepted",
        ]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "ready"
    assert "layer0_preflight_pass_with_warnings" in payload["warnings"]
    assert payload["override"] == {
        "override": True,
        "operator": "roy",
        "reason": "demo warning accepted",
        "timestamp": NOW_ISO,
    }


def test_force_ready_keeps_hard_sha_mismatch_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("PAWAI_SCOREBOARD_PATH", str(_snapshot_path(tmp_path)))

    result = _invoke_readiness(
        [
            "--json",
            "--force-ready",
            "--operator",
            "roy",
            "--reason",
            "try hard override",
        ],
        manifest={"git_sha": "fffffff"},
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["verdict"] == "not_ready"
    assert any("sha_mismatch" in reason for reason in payload["reasons"])
    assert payload["override"]["override"] is True


def test_override_flags_require_operator_and_reason(monkeypatch, tmp_path):
    monkeypatch.setenv("PAWAI_SCOREBOARD_PATH", str(_snapshot_path(tmp_path)))

    result = _invoke_readiness(["--accept-warnings"])

    assert result.exit_code != 0
    assert "--operator and --reason are required" in result.output


def test_readiness_freeze_copies_snapshot_to_dated_folder(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    working = repo / "artifacts/baseline/baseline_snapshot.json"
    working.parent.mkdir(parents=True)
    working.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("PAWAI_REPO_ROOT", str(repo))

    result = CliRunner().invoke(cli, ["readiness", "freeze", "--date", "2026-06-18"])

    assert result.exit_code == 0
    frozen = repo / "artifacts/baseline/frozen/2026-06-18/baseline_snapshot.json"
    assert frozen.read_text(encoding="utf-8") == working.read_text(encoding="utf-8")
