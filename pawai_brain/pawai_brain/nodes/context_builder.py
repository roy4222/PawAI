"""context_builder — Phase 1 stub.

Phase 1 only: source + timestamp. Perception state (face/pose/object) joins
in Phase 2 once it's worth the integration cost.
"""
from __future__ import annotations
import time

from ..state import ConversationState


def context_builder(state: ConversationState) -> ConversationState:
    state["perception_context"] = {
        "source": state.get("source", "speech"),
        "timestamp": time.time(),
    }
    state.setdefault("trace", []).append(
        {"stage": "context", "status": "ok", "detail": "stub"}
    )
    return state
