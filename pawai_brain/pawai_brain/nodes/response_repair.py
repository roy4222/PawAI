"""response_repair — Phase 1 first-pass: pass-through unless validator failed.

Plan §3 row 8: only flip repair_failed=True when downstream needs to fall
back. We DON'T re-call the LLM yet (deferred to Phase 2).
"""
from __future__ import annotations

from ..state import ConversationState


def response_repair(state: ConversationState) -> ConversationState:
    if state.get("validation_error"):
        state["repair_failed"] = True
        state.setdefault("trace", []).append(
            {
                "stage": "repair",
                "status": "fallback",
                "detail": state["validation_error"],
            }
        )
    else:
        state["repair_failed"] = False
        state.setdefault("trace", []).append(
            {"stage": "repair", "status": "ok", "detail": "pass_through"}
        )
    return state
