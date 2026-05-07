"""Tests for CapabilityRegistry — merge SkillContract + DemoGuide."""
from unittest.mock import MagicMock

from pawai_brain.capability.demo_guides_loader import DemoGuide
from pawai_brain.capability.effective_status import WorldFlags
from pawai_brain.capability.registry import (
    CapabilityEntry,
    CapabilityRegistry,
    build_capability_entries,
)


class _FakeSkill:
    """Minimal SkillContract stand-in for tests."""
    def __init__(self, name, **kw):
        self.name = name
        self.display_name = kw.get("display_name", name)
        self.demo_status_baseline = kw.get("demo_status_baseline", "available_execute")
        self.demo_value = kw.get("demo_value", "high")
        self.demo_reason = kw.get("demo_reason", "")
        self.static_enabled = kw.get("static_enabled", True)
        self.enabled_when = kw.get("enabled_when", [])
        self.cooldown_s = kw.get("cooldown_s", 0.0)
        self.steps = kw.get("steps", [])
        self.requires_confirmation = kw.get("requires_confirmation", False)


def _say_step():
    s = MagicMock(); s.executor = MagicMock(name="SAY"); return s


def _make_registry(skills, guides):
    return CapabilityRegistry(skills=skills, guides=guides)


def test_assert_disjoint_names():
    skill = _FakeSkill("gesture_demo")  # collides with demo guide name
    guide = DemoGuide(name="gesture_demo", display_name="x",
                      baseline_status="explain_only", demo_value="high", intro="x")
    import pytest
    with pytest.raises(ValueError, match="disjoint"):
        _make_registry({"gesture_demo": skill}, [guide])


def test_build_entries_includes_skill_and_guide():
    skill = _FakeSkill("self_introduce")
    guide = DemoGuide(name="gesture_demo", display_name="手勢",
                      baseline_status="explain_only", demo_value="high", intro="比 OK")
    reg = _make_registry({"self_introduce": skill}, [guide])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    assert {e.name for e in entries} == {"self_introduce", "gesture_demo"}
    by_name = {e.name: e for e in entries}
    assert by_name["self_introduce"].kind == "skill"
    assert by_name["gesture_demo"].kind == "demo_guide"


def test_demo_guide_always_explain_only():
    guide = DemoGuide(name="gesture_demo", display_name="x",
                      baseline_status="explain_only", demo_value="high", intro="x")
    reg = _make_registry({}, [guide])
    entries = reg.build_entries(world=WorldFlags(tts_playing=True), recent_results=[])
    assert entries[0].effective_status == "explain_only"
    assert entries[0].can_execute is False


def test_skill_can_execute_only_when_available():
    skill = _FakeSkill("self_introduce")
    reg = _make_registry({"self_introduce": skill}, [])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    e = entries[0]
    assert e.effective_status == "available"
    assert e.can_execute is True


def test_cooldown_remaining_uses_recent_results():
    skill = _FakeSkill("wave_hello", cooldown_s=10.0)
    reg = _make_registry({"wave_hello": skill}, [])
    import time
    recent = [{"name": "wave_hello", "status": "completed",
               "ts": time.time() - 3.0, "detail": ""}]
    entries = reg.build_entries(world=WorldFlags(), recent_results=recent)
    assert entries[0].effective_status == "cooldown"


def test_lookup_returns_entry_by_name():
    skill = _FakeSkill("self_introduce")
    guide = DemoGuide(name="gesture_demo", display_name="x",
                      baseline_status="explain_only", demo_value="high", intro="x")
    reg = _make_registry({"self_introduce": skill}, [guide])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    by_name = {e.name: e for e in entries}
    assert by_name["self_introduce"].kind == "skill"
    assert by_name["gesture_demo"].kind == "demo_guide"
    assert "missing" not in by_name


def test_serialize_for_llm_minimal_fields():
    skill = _FakeSkill("self_introduce")
    reg = _make_registry({"self_introduce": skill}, [])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    payload = entries[0].to_llm_dict()
    assert payload["name"] == "self_introduce"
    assert payload["kind"] == "skill"
    assert "effective_status" in payload
    assert "can_execute" in payload
