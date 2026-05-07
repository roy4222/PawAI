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
