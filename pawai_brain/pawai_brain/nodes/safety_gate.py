"""safety_gate — hard-coded keyword short-circuit (mirrors brain_node SafetyLayer).

Hits these tokens → bypass LLM, emit stop_move chat_candidate directly.
Plan §3 row 2.
"""
from __future__ import annotations

from ..state import ConversationState


SAFETY_KEYWORDS = ("停", "stop", "暫停", "煞車", "緊急")


def safety_gate(state: ConversationState) -> ConversationState:
    text = state.get("user_text") or ""
    lower = text.lower()
    hit = any(kw in text or kw in lower for kw in SAFETY_KEYWORDS)
    state["safety_hit"] = hit

    if hit:
        # Pre-fill the output fields so output_builder can ship them as-is.
        state["reply_text"] = "好的，我停下來。"
        state["selected_skill"] = "stop_move"
        state["intent"] = "stop"
        state["reasoning"] = "safety_gate_hit"
        state["confidence"] = 1.0
        state["proposed_skill"] = None
        state["proposed_args"] = {}
        state["proposal_reason"] = ""
        state.setdefault("trace", []).append(
            {"stage": "safety_gate", "status": "hit", "detail": "stop_move"}
        )
    else:
        state.setdefault("trace", []).append(
            {"stage": "safety_gate", "status": "ok", "detail": ""}
        )
    return state
