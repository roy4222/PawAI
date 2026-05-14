"""llm_decision — call OpenRouter via shared client.

The client + system_prompt are injected by the wrapper at startup.
"""
from __future__ import annotations
from typing import Callable

from ..llm_client import OpenRouterClient
from ..state import ConversationState


_client: OpenRouterClient | None = None
_system_prompt: str = ""
_user_message_builder: Callable[[ConversationState], str] | None = None


def configure(
    client: OpenRouterClient,
    system_prompt: str,
    user_message_builder: Callable[[ConversationState], str],
) -> None:
    """Wrapper hook."""
    global _client, _system_prompt, _user_message_builder
    _client = client
    _system_prompt = system_prompt
    _user_message_builder = user_message_builder


def llm_decision(state: ConversationState) -> ConversationState:
    if _client is None or _user_message_builder is None:
        # Configuration not done yet — wrapper failed to wire. Surface as error
        # but don't raise (let the rest of the graph degrade).
        state["llm_raw"] = None
        state.setdefault("trace", []).append(
            {"stage": "llm_decision", "status": "error", "detail": "not_configured"}
        )
        return state

    user_message = _user_message_builder(state)
    history = state.get("history") or []
    result = _client.chat(_system_prompt, history, user_message)

    if result is None:
        state["llm_raw"] = None
        state.setdefault("trace", []).append(
            {
                "stage": "llm_decision",
                "status": "fallback",
                "detail": _client.last_error[:80] if _client.last_error else "chain_exhausted",
            }
        )
    else:
        state["llm_raw"] = result["raw"]
        state.setdefault("trace", []).append(
            {
                "stage": "llm_decision",
                "status": "ok",
                "detail": result["model"],
            }
        )
    return state
