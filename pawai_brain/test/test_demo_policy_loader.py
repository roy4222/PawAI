from pathlib import Path

from pawai_brain.capability.demo_guides_loader import load_demo_policy


def _path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "demo_policy.yaml"


def test_loads_limits():
    policy = load_demo_policy(_path())
    assert isinstance(policy["limits"], list)
    assert len(policy["limits"]) == 5
    assert "陌生人警告已關閉避免誤觸" in policy["limits"]


def test_max_motion_per_turn():
    policy = load_demo_policy(_path())
    assert policy["max_motion_per_turn"] == 1


def test_missing_file_returns_defaults():
    policy = load_demo_policy(Path("/nonexistent.yaml"))
    assert policy["limits"] == []
    assert policy["max_motion_per_turn"] == 1
