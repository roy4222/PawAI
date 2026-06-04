import json
from pathlib import Path

from pawai_brain.capability.health_loader import load_capability_health, skill_capability


FIXTURE = Path(__file__).parent / "fixtures" / "baseline_snapshot.example.json"


def test_load_capability_health_from_trusted_snapshot() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    capability_id = "gesture.wave"
    expected = raw["capabilities"][capability_id]

    health = load_capability_health(str(FIXTURE))[capability_id]

    assert health.grade == expected["grade"]
    assert health.claim_level == expected["claim_level"]
    assert health.dependency_role == expected["dependency_role"]
    assert health.risk_role == expected["risk_role"]
    assert health.brain_allowed is expected["brain_allowed"]


def test_load_capability_health_empty_path_fails_closed() -> None:
    health_by_capability = load_capability_health("")

    for capability_id in ("gesture.wave", "nav.short_move", "unknown.capability"):
        assert health_by_capability[capability_id].grade == "insufficient_data"


def test_load_capability_health_missing_path_fails_closed(tmp_path: Path) -> None:
    health_by_capability = load_capability_health(str(tmp_path / "missing.json"))

    for capability_id in ("gesture.wave", "nav.short_move", "unknown.capability"):
        assert health_by_capability[capability_id].grade == "insufficient_data"


def test_load_capability_health_unreadable_path_fails_closed(tmp_path: Path) -> None:
    unreadable = tmp_path / "snapshot-dir"
    unreadable.mkdir()

    health_by_capability = load_capability_health(str(unreadable))

    for capability_id in ("gesture.wave", "nav.short_move", "unknown.capability"):
        assert health_by_capability[capability_id].grade == "insufficient_data"


def test_load_capability_health_invalid_json_fails_closed(tmp_path: Path) -> None:
    invalid = tmp_path / "baseline_snapshot.json"
    invalid.write_text("{not-json", encoding="utf-8")

    health_by_capability = load_capability_health(str(invalid))

    for capability_id in ("gesture.wave", "nav.short_move", "unknown.capability"):
        assert health_by_capability[capability_id].grade == "insufficient_data"


def test_load_capability_health_untrusted_snapshot_fails_closed(tmp_path: Path) -> None:
    untrusted = tmp_path / "baseline_snapshot.json"
    untrusted.write_text(
        json.dumps(
            {
                "run_trusted": False,
                "capabilities": {
                    "gesture.wave": {
                        "capability_id": "gesture.wave",
                        "grade": "pass",
                        "claim_level": "trusted",
                        "risk_role": "allowed",
                        "dependency_role": "available",
                        "brain_allowed": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    health_by_capability = load_capability_health(str(untrusted))

    for capability_id in ("gesture.wave", "nav.short_move", "unknown.capability"):
        assert health_by_capability[capability_id].grade == "insufficient_data"


def test_skill_capability_mapping() -> None:
    assert skill_capability("wave_hello") == "gesture.wave"
    assert skill_capability("sit_along") == "nav.short_move"
    assert skill_capability("show_status") == "content"
    assert skill_capability("unknown_motion") is None
