"""Tests for demo_guides yaml loader."""
import pytest
from pathlib import Path

from pawai_brain.capability.demo_guides_loader import (
    DemoGuide,
    load_demo_guides,
)


def _config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "demo_guides.yaml"


def test_loads_six_guides():
    guides = load_demo_guides(_config_path())
    assert len(guides) == 6
    names = {g.name for g in guides}
    assert names == {
        "face_recognition_demo", "speech_demo", "gesture_demo",
        "pose_demo", "object_demo", "navigation_demo",
    }


def test_each_guide_has_required_fields():
    guides = load_demo_guides(_config_path())
    for g in guides:
        assert g.display_name
        assert g.baseline_status in ("explain_only", "studio_only", "disabled")
        assert g.demo_value in ("high", "medium", "low")
        assert g.intro


def test_kind_attribute_is_demo_guide():
    guides = load_demo_guides(_config_path())
    assert all(g.kind == "demo_guide" for g in guides)


def test_invalid_baseline_raises():
    invalid = {
        "bad_demo": {
            "display_name": "Bad",
            "baseline_status": "available_execute",  # forbidden for demo_guide
            "demo_value": "low",
            "intro": "x",
        }
    }
    with pytest.raises(ValueError, match="baseline_status"):
        DemoGuide.from_yaml_entry("bad_demo", invalid["bad_demo"])


def test_missing_file_returns_empty_list_with_warn(caplog):
    guides = load_demo_guides(Path("/nonexistent/path.yaml"))
    assert guides == []


def test_related_skills_default_empty():
    guides = load_demo_guides(_config_path())
    by_name = {g.name: g for g in guides}
    # gesture_demo declares related; speech_demo too
    assert "wave_hello" in by_name["gesture_demo"].related_skills
    assert "chat_reply" in by_name["speech_demo"].related_skills
