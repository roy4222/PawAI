from pawai_brain.capability.demo_guides_loader import DemoGuide
from pawai_brain.capability.registry import CapabilityRegistry
from pawai_brain.nodes import capability_builder as cb_node


class _FakeSkill:
    def __init__(self, name, baseline="available_execute"):
        self.name = name
        self.display_name = name
        self.demo_status_baseline = baseline
        self.demo_value = "high"
        self.demo_reason = ""
        self.static_enabled = True
        self.enabled_when = []
        self.cooldown_s = 0.0
        self.steps = []
        self.requires_confirmation = False


def _wire(skills_dict, guides, recent_results=None, limits=None):
    reg = CapabilityRegistry(skills=skills_dict, guides=guides)
    cb_node.configure(
        registry=reg,
        skill_result_provider=lambda: list(recent_results or []),
        policy_provider=lambda: {"limits": list(limits or []), "max_motion_per_turn": 1},
    )


def test_writes_capability_context_with_capabilities_list():
    _wire({"self_introduce": _FakeSkill("self_introduce")}, [])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    cc = out["capability_context"]
    assert "capabilities" in cc
    assert any(c["name"] == "self_introduce" for c in cc["capabilities"])


def test_includes_demo_guides():
    guide = DemoGuide(name="gesture_demo", display_name="手勢",
                      baseline_status="explain_only", demo_value="high", intro="比 OK")
    _wire({}, [guide])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    names = {c["name"] for c in out["capability_context"]["capabilities"]}
    assert "gesture_demo" in names


def test_includes_limits_from_policy():
    _wire({}, [], limits=["陌生人警告已關閉"])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    assert "陌生人警告已關閉" in out["capability_context"]["limits"]


def test_includes_recent_skill_results():
    _wire({}, [], recent_results=[{"name": "self_introduce", "status": "completed",
                                    "ts": 1.0, "detail": ""}])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    assert len(out["capability_context"]["recent_skill_results"]) == 1


def test_demo_session_placeholder():
    _wire({}, [])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    sess = out["capability_context"]["demo_session"]
    assert sess["active"] is False
    assert sess["shown_skills"] == []


def test_emits_trace_entry():
    _wire({}, [])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    assert any(t["stage"] == "capability" for t in out["trace"])


# ── N3-B: demo_session_provider override ──────────────────────────────────


def _wire_with_session(session_dict):
    reg = CapabilityRegistry(skills={}, guides=[])
    cb_node.configure(
        registry=reg,
        skill_result_provider=lambda: [],
        policy_provider=lambda: {"limits": [], "max_motion_per_turn": 1},
        demo_session_provider=lambda: session_dict,
    )


def test_demo_session_provider_overrides_placeholder():
    """When provider returns active session, capability_context reflects it."""
    _wire_with_session({
        "active": True,
        "current_segment": "gesture",
        "shown_skills": ["wiggle"],
        "candidate_next": ["stretch"],
    })
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    sess = out["capability_context"]["demo_session"]
    assert sess["active"] is True
    assert sess["current_segment"] == "gesture"
    assert sess["shown_skills"] == ["wiggle"]


def test_demo_session_no_provider_falls_back_to_placeholder():
    """Reconfigure WITHOUT demo_session_provider — must fall back."""
    reg = CapabilityRegistry(skills={}, guides=[])
    cb_node.configure(
        registry=reg,
        skill_result_provider=lambda: [],
        policy_provider=lambda: {"limits": [], "max_motion_per_turn": 1},
        # demo_session_provider intentionally omitted
    )
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    sess = out["capability_context"]["demo_session"]
    assert sess["active"] is False


def test_demo_session_active_extends_trace_detail():
    _wire_with_session({
        "active": True, "current_segment": "object",
        "shown_skills": [], "candidate_next": [],
    })
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    cap_trace = [t for t in out["trace"] if t["stage"] == "capability"][0]
    assert "demo=object" in cap_trace["detail"]


def test_demo_session_inactive_no_demo_in_trace():
    _wire_with_session({"active": False, "shown_skills": [], "candidate_next": []})
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    cap_trace = [t for t in out["trace"] if t["stage"] == "capability"][0]
    assert "demo=" not in cap_trace["detail"]


def test_demo_session_provider_returning_non_dict_falls_back():
    """Defensive: provider returns None / list → fallback placeholder."""
    reg = CapabilityRegistry(skills={}, guides=[])
    cb_node.configure(
        registry=reg,
        skill_result_provider=lambda: [],
        policy_provider=lambda: {"limits": [], "max_motion_per_turn": 1},
        demo_session_provider=lambda: None,
    )
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    sess = out["capability_context"]["demo_session"]
    assert sess["active"] is False
