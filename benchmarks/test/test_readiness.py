from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.core.readiness import evaluate_readiness

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "pawai_brain/test/fixtures/baseline_snapshot.example.json"
SCHEMA_PATH = ROOT / ".claude/schemas/baseline_snapshot.schema.json"
NOW_ISO = "2026-06-18T10:00:00+00:00"
DEPLOY_SHA = "abc1234"


def _snapshot() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _mutated(mutator) -> dict:
    snapshot = _snapshot()
    mutator(snapshot)
    return snapshot


def _hard_cases():
    return [
        (
            "snapshot_missing",
            lambda: None,
            DEPLOY_SHA,
            "snapshot_missing",
        ),
        (
            "schema_invalid",
            lambda: _mutated(lambda snapshot: snapshot.__setitem__("schema_version", "wrong")),
            DEPLOY_SHA,
            "schema_invalid",
        ),
        (
            "run_trusted_false",
            lambda: _mutated(lambda snapshot: snapshot.__setitem__("run_trusted", False)),
            DEPLOY_SHA,
            "run_untrusted",
        ),
        (
            "layer0_preflight_fail",
            lambda: _mutated(
                lambda snapshot: snapshot.__setitem__("layer0_preflight_status", "fail")
            ),
            DEPLOY_SHA,
            "layer0_preflight_fail",
        ),
        (
            "sha_mismatch",
            _snapshot,
            "fffffff",
            "sha_mismatch",
        ),
        (
            "capability_list_incomplete",
            lambda: _mutated(lambda snapshot: snapshot["capabilities"].pop("pose.fall")),
            DEPLOY_SHA,
            "capability_list_incomplete",
        ),
        (
            "mainline_grade_missing",
            lambda: _mutated(
                lambda snapshot: snapshot["capabilities"]["gesture.wave"].pop("grade")
            ),
            DEPLOY_SHA,
            "mainline_grade_missing:gesture.wave",
        ),
        (
            "mainline_failure_reason_missing",
            lambda: _mutated(
                lambda snapshot: snapshot["capabilities"]["gesture.wave"].update(
                    {"grade": "fail"}
                )
            ),
            DEPLOY_SHA,
            "mainline_failure_reason_missing:gesture.wave",
        ),
        (
            "mainline_not_pass_with_reason",
            lambda: _mutated(
                lambda snapshot: snapshot["capabilities"]["gesture.wave"].update(
                    {"grade": "fail", "failure_reason": "fail:registered_recall=0.0"}
                )
            ),
            DEPLOY_SHA,
            "mainline_capability_not_pass:gesture.wave",
        ),
    ]


@pytest.mark.parametrize(
    "case_name,snapshot_factory,deploy_sha,expected_reason",
    _hard_cases(),
)
def test_fail_closed_hard_conditions(case_name, snapshot_factory, deploy_sha, expected_reason):
    result = evaluate_readiness(
        snapshot_factory(),
        deploy_sha=deploy_sha,
        now_iso=NOW_ISO,
        schema=_schema(),
    )

    assert result["verdict"] == "not_ready", case_name
    assert any(expected_reason in reason for reason in result["reasons"]), result


def test_fail_closed_truth_table_has_zero_fail_open():
    fail_open_count = 0
    for _, snapshot_factory, deploy_sha, _ in _hard_cases():
        result = evaluate_readiness(
            snapshot_factory(),
            deploy_sha=deploy_sha,
            now_iso=NOW_ISO,
            schema=_schema(),
        )
        if result["verdict"] == "ready":
            fail_open_count += 1

    assert fail_open_count == 0


def test_all_checks_pass_is_ready():
    result = evaluate_readiness(
        _snapshot(),
        deploy_sha=DEPLOY_SHA,
        now_iso=NOW_ISO,
        schema=_schema(),
    )

    assert result == {
        "verdict": "ready",
        "reasons": [],
        "warnings": [],
        "override": None,
    }


def test_short_and_full_sha_prefixes_are_accepted():
    snapshot = _snapshot()
    snapshot["git_commit"] = "abc1234deadbeef"

    result = evaluate_readiness(
        snapshot,
        deploy_sha=DEPLOY_SHA,
        now_iso=NOW_ISO,
        schema=_schema(),
    )

    assert result["verdict"] == "ready"


def test_age_over_three_days_warns_without_blocking():
    snapshot = _snapshot()
    snapshot["timestamp"] = "2026-06-14T09:00:00+00:00"

    result = evaluate_readiness(
        snapshot,
        deploy_sha=DEPLOY_SHA,
        now_iso=NOW_ISO,
        schema=_schema(),
    )

    assert result["verdict"] == "ready"
    assert any("snapshot_age_warning" in warning for warning in result["warnings"])


def test_age_over_seven_days_is_strong_warning_without_blocking():
    snapshot = _snapshot()
    snapshot["timestamp"] = "2026-06-10T09:00:00+00:00"

    result = evaluate_readiness(
        snapshot,
        deploy_sha=DEPLOY_SHA,
        now_iso=NOW_ISO,
        schema=_schema(),
    )

    assert result["verdict"] == "ready"
    assert any("snapshot_age_strong_warning" in warning for warning in result["warnings"])


def test_preflight_pass_with_warnings_is_soft_warning():
    snapshot = _snapshot()
    snapshot["layer0_preflight_status"] = "pass_with_warnings"

    result = evaluate_readiness(
        snapshot,
        deploy_sha=DEPLOY_SHA,
        now_iso=NOW_ISO,
        schema=_schema(),
    )

    assert result["verdict"] == "ready"
    assert "layer0_preflight_pass_with_warnings" in result["warnings"]


def test_accept_warnings_records_override_trace_for_soft_warnings():
    snapshot = _snapshot()
    snapshot["layer0_preflight_status"] = "pass_with_warnings"

    result = evaluate_readiness(
        snapshot,
        deploy_sha=DEPLOY_SHA,
        now_iso=NOW_ISO,
        schema=_schema(),
        overrides={
            "accept_warnings": True,
            "force_ready": False,
            "operator": "roy",
            "reason": "demo-day warning accepted",
            "timestamp": "2026-06-18T10:00:00+00:00",
        },
    )

    assert result["verdict"] == "ready"
    assert result["override"] == {
        "override": True,
        "operator": "roy",
        "reason": "demo-day warning accepted",
        "timestamp": "2026-06-18T10:00:00+00:00",
    }


def test_force_ready_cannot_override_sha_mismatch_but_leaves_trace():
    result = evaluate_readiness(
        _snapshot(),
        deploy_sha="fffffff",
        now_iso=NOW_ISO,
        schema=_schema(),
        overrides={
            "accept_warnings": False,
            "force_ready": True,
            "operator": "roy",
            "reason": "testing hard override",
            "timestamp": "2026-06-18T10:00:00+00:00",
        },
    )

    assert result["verdict"] == "not_ready"
    assert any("sha_mismatch" in reason for reason in result["reasons"])
    assert result["override"]["override"] is True
