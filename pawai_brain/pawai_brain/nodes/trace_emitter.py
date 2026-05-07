"""trace_emitter — terminal marker; actual ROS publish happens in wrapper."""
from __future__ import annotations

from ..state import ConversationState


def trace_emitter(state: ConversationState) -> ConversationState:
    # No-op transformation. Wrapper reads state["trace"] and publishes per-stage.
    return state
