"""Unit tests for skill_policy_gate normalisation rules (Plan §3 contract)."""
from pawai_brain.nodes.skill_policy_gate import (
    LLM_PROPOSABLE_SKILLS,
    normalize_proposal,
    skill_policy_gate,
)


# ── normalize_proposal — 5 rules ────────────────────────────────────────

def test_passthrough_chat_reply_yields_no_proposal():
    skill, args, trace = normalize_proposal("chat_reply", {})
    assert skill is None
    assert args == {}
    assert trace is None


def test_passthrough_say_canned_yields_no_proposal():
    skill, _, trace = normalize_proposal("say_canned", None)
    assert skill is None
    assert trace is None


def test_allowlisted_show_status_yields_proposed():
    skill, args, trace = normalize_proposal("show_status", {"foo": 1})
    assert skill == "show_status"
    assert args == {"foo": 1}
    assert trace == "proposed"


def test_allowlisted_self_introduce_yields_proposed():
    skill, _, trace = normalize_proposal("self_introduce", {})
    assert skill == "self_introduce"
    assert trace == "proposed"


def test_non_allowlisted_skill_kept_with_rejected_trace():
    """Critical: keep the skill name so brain_node can really reject."""
    skill, _, trace = normalize_proposal("dance_wildly", {})
    assert skill == "dance_wildly"
    assert trace == "rejected_not_allowed"


def test_null_skill_yields_none():
    skill, _, trace = normalize_proposal(None, {})
    assert skill is None
    assert trace is None


def test_non_string_skill_yields_none():
    skill, _, trace = normalize_proposal(123, {})
    assert skill is None
    assert trace is None


def test_empty_string_skill_yields_none():
    skill, _, trace = normalize_proposal("", {})
    assert skill is None
    assert trace is None


def test_whitespace_only_skill_yields_none():
    skill, _, trace = normalize_proposal("   ", {})
    assert skill is None
    assert trace is None


def test_args_non_dict_normalised_to_empty():
    _, args, _ = normalize_proposal("show_status", "not a dict")
    assert args == {}

    _, args, _ = normalize_proposal("show_status", [1, 2, 3])
    assert args == {}

    _, args, _ = normalize_proposal("show_status", None)
    assert args == {}


def test_skill_with_surrounding_whitespace_stripped():
    skill, _, trace = normalize_proposal("  self_introduce  ", {})
    assert skill == "self_introduce"
    assert trace == "proposed"


# ── allowlist contract ──────────────────────────────────────────────────

def test_allowlist_matches_spec():
    """Sync check: keep allowlist aligned with brain_node.LLM_PROPOSABLE_SKILLS."""
    assert LLM_PROPOSABLE_SKILLS == frozenset({"show_status", "self_introduce"})


# ── skill_policy_gate node integration ──────────────────────────────────

def test_node_writes_state_for_allowlisted():
    state = {"llm_json": {"skill": "show_status", "args": {"k": "v"}}, "trace": []}
    out = skill_policy_gate(state)  # type: ignore[arg-type]
    assert out["proposed_skill"] == "show_status"
    assert out["proposed_args"] == {"k": "v"}
    assert out["trace"][-1]["status"] == "proposed"
    assert out["trace"][-1]["stage"] == "skill_gate"


def test_node_writes_state_for_rejected():
    state = {"llm_json": {"skill": "dance", "args": {}}, "trace": []}
    out = skill_policy_gate(state)  # type: ignore[arg-type]
    assert out["proposed_skill"] == "dance"
    assert out["trace"][-1]["status"] == "rejected_not_allowed"


def test_node_no_trace_for_passthrough():
    state = {"llm_json": {"skill": "chat_reply"}, "trace": []}
    out = skill_policy_gate(state)  # type: ignore[arg-type]
    assert out["proposed_skill"] is None
    assert out["trace"] == []  # passthrough emits no skill_gate trace


def test_node_handles_missing_llm_json():
    state = {"trace": []}
    out = skill_policy_gate(state)  # type: ignore[arg-type]
    assert out["proposed_skill"] is None
    assert out["proposed_args"] == {}
    assert out["trace"] == []


# ── Phase A.6 additions ──
from pawai_brain.nodes.skill_policy_gate import normalize_proposal_v2


def _entry(name, kind, effective="available"):
    return type("E", (), {"name": name, "kind": kind, "effective_status": effective})


def _ctx(*entries):
    return {"capabilities": [{"name": e.name, "kind": e.kind,
                              "effective_status": e.effective_status}
                             for e in entries]}


def test_v2_passthrough_chat_reply_yields_no_proposal_no_trace():
    """HIGH-RISK: chat_reply must not become proposed_skill even though it's in SKILL_REGISTRY."""
    skill, args, guide, status, detail = normalize_proposal_v2("chat_reply", {}, _ctx())
    assert skill is None
    assert guide is None
    assert status is None  # no skill_gate trace at all


def test_v2_passthrough_say_canned_yields_no_proposal_no_trace():
    skill, args, guide, status, _ = normalize_proposal_v2("say_canned", {}, _ctx())
    assert skill is None
    assert guide is None
    assert status is None


def test_v2_demo_guide_routes_to_selected_demo_guide():
    """HIGH-RISK: demo_guide must NOT enter proposed_skill."""
    ctx = _ctx(_entry("gesture_demo", "demo_guide", "explain_only"))
    skill, args, guide, status, _ = normalize_proposal_v2("gesture_demo", {}, ctx)
    assert skill is None
    assert guide == "gesture_demo"
    assert status == "demo_guide"


def test_v2_skill_available_proposed():
    ctx = _ctx(_entry("self_introduce", "skill", "available"))
    skill, _, guide, status, _ = normalize_proposal_v2("self_introduce", {}, ctx)
    assert skill == "self_introduce"
    assert guide is None
    assert status == "proposed"


def test_v2_skill_needs_confirm_preserves_proposed_skill():
    """needs_confirm must keep proposed_skill so brain_node can route to confirm mode.
    Previous behaviour returned None which dropped the handoff entirely."""
    ctx = _ctx(_entry("wiggle", "skill", "needs_confirm"))
    skill, _, guide, status, detail = normalize_proposal_v2("wiggle", {}, ctx)
    assert skill == "wiggle"   # ← was None
    assert guide is None
    assert status == "needs_confirm"
    assert detail == "wiggle"


def test_v2_skill_blocked_states_are_blocked():
    for eff in ("explain_only", "blocked", "cooldown", "defer", "studio_only", "disabled"):
        ctx = _ctx(_entry("foo", "skill", eff))
        skill, _, guide, status, detail = normalize_proposal_v2("foo", {}, ctx)
        assert skill is None
        assert guide is None
        assert status == "blocked"
        assert eff in detail


def test_v2_unknown_skill_kept_with_rejected():
    skill, _, guide, status, _ = normalize_proposal_v2("dance_wildly", {}, _ctx())
    assert skill == "dance_wildly"
    assert guide is None
    assert status == "rejected_not_allowed"


def test_v2_null_or_non_string_skill_yields_none():
    for raw in (None, 123, [], {}):
        skill, _, guide, status, _ = normalize_proposal_v2(raw, {}, _ctx())
        assert skill is None
        assert guide is None
        assert status is None


def test_v2_args_normalised():
    ctx = _ctx(_entry("self_introduce", "skill", "available"))
    _, args, _, _, _ = normalize_proposal_v2("self_introduce", "not a dict", ctx)
    assert args == {}
