"""Validator — JSON parse + emoji strip + truncation guard.

Copied (with light cleanup) from llm_bridge_node._post_process_reply +
llm_contract.strip_markdown_fences. Pure functions — no ROS / IO.
"""
from __future__ import annotations
import json
import re

# Keep regex constants module-scoped (compile once).
_EMOJI_RE = re.compile(r"[\U0001f300-\U0001f9ff]")
_SENTENCE_END = "。！？~~」』）)】."
_MID_CLAUSE = "，、：；,;"


def strip_markdown_fences(raw: str) -> str:
    """Strip ``` fences that LLMs sometimes wrap around JSON."""
    content = raw.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    return content.strip()


def parse_persona_json(raw: str) -> dict | None:
    """Parse a persona LLM response. Returns dict or None on failure.

    Persona schema (tools/llm_eval/persona.txt):
        {"reply": "...", "skill": "...", "args": {...}}
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(strip_markdown_fences(raw))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def strip_emoji(text: str) -> str:
    """Remove decorative emoji glyphs that break TTS.

    Audio-tag tokens like [excited] / [whispers] are kept intact.
    """
    return _EMOJI_RE.sub("", text or "").strip()


def looks_truncated(reply: str) -> str | None:
    """Detect known mid-sentence truncation symptoms.

    Returns a short reason string ('mid-clause' / 'no-terminator') when the
    reply tail looks like the model stopped mid-thought; None when fine.
    """
    if not reply or len(reply) <= 8:
        return None
    tail = reply[-1]
    if tail in _MID_CLAUSE:
        return "mid-clause"
    if tail not in _SENTENCE_END and not tail.isspace():
        return "no-terminator"
    return None


def cap_length(reply: str, max_chars: int) -> str:
    """Apply a hard length cap; max_chars <= 0 means uncapped."""
    if max_chars and max_chars > 0 and len(reply) > max_chars:
        return reply[:max_chars]
    return reply
