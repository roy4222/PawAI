"""skill_policy_gate — proposal normalisation (Phase A.6 v2 with kind branches).

Plan §3 contract (v1, kept for legacy paths without CapabilityContext):
  chat_reply / say_canned       → proposed_skill = None  (no trace)
  show_status / self_introduce  → proposed_skill = skill, trace status="proposed"
  其他非空 skill (不在 allowlist) → proposed_skill = skill, trace "rejected_not_allowed"
  null / 非字串                  → proposed_skill = None
  args 非 dict                  → {}

v2 (Phase A.6) — passthrough first, then capability lookup with kind branch.
"""
from __future__ import annotations

from ..state import ConversationState


# Mirrors brain_node.LLM_PROPOSABLE_SKILLS (kept for v1 compat)
LLM_PROPOSABLE_SKILLS: frozenset[str] = frozenset({"show_status", "self_introduce"})

# v1 passthrough names (unchanged); v2 uses the same set
PASSTHROUGH_SKILLS: frozenset[str] = frozenset({"chat_reply", "say_canned"})


def normalize_proposal(
    raw_skill, raw_args
) -> tuple[str | None, dict, str | None]:
    """v1 (Cut A) — kept for legacy paths that don't have CapabilityContext yet.

    Returns: (proposed_skill, proposed_args, trace_status)
    """
    proposed_args: dict = raw_args if isinstance(raw_args, dict) else {}
    if not isinstance(raw_skill, str):
        return None, proposed_args, None
    skill = raw_skill.strip()
    if not skill or skill in PASSTHROUGH_SKILLS:
        return None, proposed_args, None
    if skill in LLM_PROPOSABLE_SKILLS:
        return skill, proposed_args, "proposed"
    return skill, proposed_args, "rejected_not_allowed"


def normalize_proposal_v2(raw_skill, raw_args, capability_context):
    """v2 (Phase A.6) — passthrough first, then capability lookup with kind branch.

    Returns: (proposed_skill, proposed_args, selected_demo_guide, trace_status, trace_detail)
    """
    args: dict = raw_args if isinstance(raw_args, dict) else {}

    # 1. passthrough / null / 非字串 / 空字串 — must run BEFORE lookup
    if not isinstance(raw_skill, str):
        return None, args, None, None, ""
    skill_str = raw_skill.strip()
    if not skill_str or skill_str in PASSTHROUGH_SKILLS:
        return None, args, None, None, ""

    # 2. lookup in capability_context
    entry = _lookup(skill_str, capability_context)

    # 3. unknown skill — kept so brain_node can reject
    if entry is None:
        return skill_str, args, None, "rejected_not_allowed", skill_str

    # 4. demo_guide branch — never enters proposed_skill
    if entry["kind"] == "demo_guide":
        return None, args, entry["name"], "demo_guide", entry["name"]

    # 5. skill branch — gate by effective_status
    eff = entry["effective_status"]
    if eff == "available":
        return entry["name"], args, None, "proposed", entry["name"]
    if eff == "needs_confirm":
        # Preserve proposed_skill so brain_node can route to confirm mode.
        # (pre-fix: returned None and brain_node never saw the skill.)
        return entry["name"], args, None, "needs_confirm", entry["name"]
    return None, args, None, "blocked", f"{entry['name']}:{eff}"


def _lookup(name: str, capability_context: dict) -> dict | None:
    if not capability_context:
        return None
    for entry in capability_context.get("capabilities", []):
        if entry.get("name") == name:
            return entry
    return None


def skill_policy_gate(state: ConversationState) -> ConversationState:
    """LangGraph node — Phase A.6 uses v2 if capability_context present, else v1."""
    llm_json = state.get("llm_json") or {}
    raw_skill = llm_json.get("skill")
    raw_args = llm_json.get("args")
    cap_ctx = state.get("capability_context")

    if cap_ctx:
        proposed, args, demo_guide, trace_status, trace_detail = \
            normalize_proposal_v2(raw_skill, raw_args, cap_ctx)
        state["proposed_skill"] = proposed
        state["proposed_args"] = args
        state["selected_demo_guide"] = demo_guide
        if not state.get("proposal_reason"):
            state["proposal_reason"] = "openrouter:eval_schema" if llm_json else ""
        if trace_status is not None:
            state.setdefault("trace", []).append(
                {"stage": "skill_gate", "status": trace_status, "detail": trace_detail}
            )
        return state

    # Fallback: legacy v1 path (capability_context not present)
    proposed, args, trace_status = normalize_proposal(raw_skill, raw_args)
    state["proposed_skill"] = proposed
    state["proposed_args"] = args
    state["selected_demo_guide"] = None
    if not state.get("proposal_reason"):
        state["proposal_reason"] = "openrouter:eval_schema" if llm_json else ""
    if trace_status is not None:
        state.setdefault("trace", []).append(
            {"stage": "skill_gate", "status": trace_status,
             "detail": str(state.get("proposed_skill") or "")}
        )
    return state
