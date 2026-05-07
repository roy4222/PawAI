"""skill_policy_gate node — proposal normalisation.

Plan §3 contract:
  chat_reply / say_canned       → proposed_skill = None  (no trace)
  show_status / self_introduce  → proposed_skill = skill, trace status="proposed"
  其他非空 skill (不在 allowlist) → proposed_skill = skill, trace "rejected_not_allowed"
                                  (kept so brain_node rejects + Studio sees it)
  null / 非字串                  → proposed_skill = None
  args 非 dict                  → {}

Allowlist mirrors brain_node.LLM_PROPOSABLE_SKILLS — keep in sync.
"""
from __future__ import annotations

from ..state import ConversationState


# Mirrors interaction_executive.brain_node:386 — keep in sync.
LLM_PROPOSABLE_SKILLS: frozenset[str] = frozenset({"show_status", "self_introduce"})

# Skills that are SAY-only (no side effect) — never count as a proposal.
PASSTHROUGH_SKILLS: frozenset[str] = frozenset({"chat_reply", "say_canned"})


def normalize_proposal(
    raw_skill, raw_args
) -> tuple[str | None, dict, str | None]:
    """Pure normalisation function — no state mutation, fully testable.

    Returns:
        (proposed_skill, proposed_args, trace_status)

        trace_status is None when no skill_gate trace should be emitted
        (passthrough or empty), 'proposed' when in allowlist,
        'rejected_not_allowed' when LLM picked a non-allowlisted skill.
    """
    # args first (independent of skill validity)
    proposed_args: dict = raw_args if isinstance(raw_args, dict) else {}

    # null / non-string skill
    if not isinstance(raw_skill, str):
        return None, proposed_args, None

    skill = raw_skill.strip()
    if not skill:
        return None, proposed_args, None

    # passthrough: chat_reply / say_canned
    if skill in PASSTHROUGH_SKILLS:
        return None, proposed_args, None

    # in allowlist
    if skill in LLM_PROPOSABLE_SKILLS:
        return skill, proposed_args, "proposed"

    # non-empty, not allowlisted — keep, mark rejected_not_allowed,
    # let brain_node enforce.
    return skill, proposed_args, "rejected_not_allowed"


def skill_policy_gate(state: ConversationState) -> ConversationState:
    """LangGraph node: normalise proposal from llm_json into state."""
    llm_json = state.get("llm_json") or {}
    raw_skill = llm_json.get("skill")
    raw_args = llm_json.get("args")

    proposed_skill, proposed_args, trace_status = normalize_proposal(raw_skill, raw_args)
    state["proposed_skill"] = proposed_skill
    state["proposed_args"] = proposed_args
    if not state.get("proposal_reason"):
        state["proposal_reason"] = "openrouter:eval_schema" if llm_json else ""

    if trace_status is not None:
        state.setdefault("trace", []).append(
            {
                "stage": "skill_gate",
                "status": trace_status,
                "detail": str(proposed_skill or ""),
            }
        )
    return state
