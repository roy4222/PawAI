"""json_validator — parse persona JSON, run emoji strip + truncation guard."""
from __future__ import annotations

from ..state import ConversationState
from ..validator import (
    cap_length,
    looks_truncated,
    parse_persona_json,
    strip_emoji,
)


# Match llm_bridge_node.MAX_REPLY_CHARS default (uncapped today; adjust via
# wrapper if a hard cap is reintroduced).
_DEFAULT_MAX_REPLY_CHARS = 0


def json_validator(state: ConversationState) -> ConversationState:
    raw = state.get("llm_raw")
    if not raw:
        state["llm_json"] = None
        state["validation_error"] = "no_raw"
        state.setdefault("trace", []).append(
            {"stage": "json_validate", "status": "error", "detail": "no_raw"}
        )
        return state

    parsed = parse_persona_json(raw)
    if parsed is None:
        state["llm_json"] = None
        state["validation_error"] = "parse_fail"
        state.setdefault("trace", []).append(
            {"stage": "json_validate", "status": "error", "detail": "parse_fail"}
        )
        return state

    # Persona schema: {"reply": "...", "skill": "...", "args": {...}}.
    # Normalise reply field to .reply (validator handles both).
    reply_raw = (parsed.get("reply") or parsed.get("reply_text") or "").strip()
    reply = strip_emoji(reply_raw)
    reply = cap_length(reply, _DEFAULT_MAX_REPLY_CHARS)
    parsed["reply"] = reply  # canonical key

    truncation = looks_truncated(reply)
    state["llm_json"] = parsed
    if truncation is None:
        state["validation_error"] = ""
        state.setdefault("trace", []).append(
            {"stage": "json_validate", "status": "ok", "detail": "valid"}
        )
    else:
        # Flag for response_repair to fall back. Phase 1 first-pass: no real
        # retry, output_builder routes to RuleBrain say_canned. Phase 2 may
        # add a retry-prompt before falling back.
        state["validation_error"] = f"truncated:{truncation}"
        state.setdefault("trace", []).append(
            {"stage": "json_validate", "status": "retry", "detail": truncation}
        )
    return state
