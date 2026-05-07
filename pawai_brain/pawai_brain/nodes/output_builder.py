"""output_builder — build the chat_candidate-equivalent fields on state.

Recognises three paths:
  1. safety_hit  → fields already set by safety_gate; just emit trace
  2. repair_failed / llm missing → RuleBrain fallback
  3. happy path  → pull reply / intent from llm_json
"""
from __future__ import annotations

from ..rule_fallback import fallback_reply
from ..state import ConversationState


def output_builder(state: ConversationState) -> ConversationState:
    if state.get("safety_hit"):
        # safety_gate already populated everything; nothing to do.
        state.setdefault("trace", []).append(
            {"stage": "output", "status": "ok", "detail": "safety_path"}
        )
        return state

    if state.get("repair_failed") or state.get("llm_json") is None:
        # Fall back to RuleBrain canned reply.
        reply, intent, skill = fallback_reply(state.get("user_text", ""))
        state["reply_text"] = reply
        state["intent"] = intent
        state["selected_skill"] = skill
        state["reasoning"] = "rule_fallback"
        state["confidence"] = 0.5
        state.setdefault("proposed_skill", None)
        state.setdefault("proposed_args", {})
        state.setdefault("proposal_reason", "")
        state.setdefault("trace", []).append(
            {"stage": "output", "status": "fallback", "detail": intent}
        )
        return state

    llm_json = state.get("llm_json") or {}
    reply = (llm_json.get("reply") or llm_json.get("reply_text") or "").strip()

    # Intent inference: persona may set explicit intent, else default to chat
    intent = llm_json.get("intent") or "chat"
    if not isinstance(intent, str) or not intent.strip():
        intent = "chat"

    # selected_skill: legacy P0 diagnostic — only the 4 P0 skills make it through.
    raw_skill = llm_json.get("skill")
    legacy_p0 = {"hello", "stop_move", "sit", "stand"}
    selected_skill = raw_skill if (isinstance(raw_skill, str) and raw_skill in legacy_p0) else None

    state["reply_text"] = reply
    state["intent"] = intent
    state["selected_skill"] = selected_skill
    state["reasoning"] = "openrouter:eval_schema"
    confidence_raw = llm_json.get("confidence", 0.8)
    try:
        state["confidence"] = max(0.0, min(1.0, float(confidence_raw)))
    except (TypeError, ValueError):
        state["confidence"] = 0.8
    # proposed_* should already be set by skill_policy_gate; keep defaults if not.
    state.setdefault("proposed_skill", None)
    state.setdefault("proposed_args", {})
    state.setdefault("proposal_reason", "openrouter:eval_schema")

    state.setdefault("trace", []).append(
        {"stage": "output", "status": "ok", "detail": (reply[:40] or "empty")}
    )
    return state
