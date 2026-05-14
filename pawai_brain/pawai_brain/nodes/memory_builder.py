"""memory_builder — pull recent turns out of the (process-local) memory.

The actual ConversationMemory instance is injected by the wrapper through
the graph's `config` mechanism. We use a module-level slot via the wrapper
to keep the node pure-ish.
"""
from __future__ import annotations
from typing import Callable

from ..state import ConversationState


# Wrapper sets this hook to a callable that returns the latest history list.
# Tests can override directly.
_history_provider: Callable[[], list[dict]] = lambda: []


def set_history_provider(provider: Callable[[], list[dict]]) -> None:
    """Wrapper calls this once at startup to bind ConversationMemory.recent."""
    global _history_provider
    _history_provider = provider


def memory_builder(state: ConversationState) -> ConversationState:
    history = _history_provider() or []
    state["history"] = list(history)
    state.setdefault("trace", []).append(
        {
            "stage": "memory",
            "status": "ok",
            "detail": f"{len(history) // 2} turn(s)",
        }
    )
    return state
