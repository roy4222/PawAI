"""input_normalizer — strip + reject empty + emit input trace."""
from __future__ import annotations

from ..state import ConversationState


def input_normalizer(state: ConversationState) -> ConversationState:
    user_text = (state.get("user_text") or "").strip()
    state["user_text"] = user_text
    status = "ok" if user_text else "error"
    state.setdefault("trace", []).append(
        {
            "stage": "input",
            "status": status,
            "detail": user_text[:40] if user_text else "empty",
        }
    )
    return state
