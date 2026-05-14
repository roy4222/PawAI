"""Validator — JSON parse + emoji strip + audio-tag normalize + truncation guard.

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

# N6 revisited (5/11 night): `[whispers]` is actually GOOD for storytelling
# and bedtime poems — user requested it back. The original N6 concern
# (whisper voice locks entire sentence) is acceptable when the model
# emits it intentionally for narrative content. `[sighs]` stays mapped
# because it tends to inject silence beats that break demo pacing.
_UNSTABLE_TAG_REPLACEMENTS = {
    "[sighs]": "[curious]",
    "[sigh]": "[curious]",
}


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


def normalize_audio_tags(text: str) -> str:
    """Replace TTS-unstable audio tags with stable ones.

    Only `[sighs]` / `[sigh]` are currently normalized → `[curious]` because
    they inject silence beats that break demo pacing. `[whispers]` USED to
    be normalized too (N6, 5/11 morning) but was restored 5/11 night —
    whisper voice is intentionally desirable for storytelling, bedtime
    poems, and similar narrative content, so we let it through.

    Other audio tags (`[excited]`, `[curious]`, `[playful]`, etc.) pass
    through untouched. Match is case-insensitive but only the bracketed
    form (won't touch raw text containing the word).
    """
    if not text:
        return text
    out = text
    for bad, good in _UNSTABLE_TAG_REPLACEMENTS.items():
        # Case-insensitive: [Whispers] / [WHISPERS] etc.
        pattern = re.compile(re.escape(bad), re.IGNORECASE)
        out = pattern.sub(good, out)
    return out


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
