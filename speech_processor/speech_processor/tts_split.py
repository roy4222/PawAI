"""Pure-Python chunk splitting for OpenRouter Gemini TTS.

Extracted from tts_node so unit tests can import this without sourcing ROS
(tts_node imports std_msgs.msg.Bool, which the pre-commit hook environment
does not have on Python path).

5/8 chunking fixes (see tests/test_tts_split_chunks.py):
  - Sentence threshold: 20 → 30 (avoid early breath cuts)
  - Comma fallback: explicit -1 guard, ≥ MIN_SPLIT_CHARS-1 boundary
"""
from __future__ import annotations
import re


# Gemini Flash TTS Preview drops tail randomly when input ≥ ~80 chars
# (5/6 evening empirical: 95-char chunks lose 25% of audio). Stay well
# under that threshold; rely on parallel synthesis to keep latency flat.
CHUNK_MAX_CHARS: int = 40

# 5/8: prefer sentence-end split once buf hits 30 chars (was //2 = 20).
# Earlier threshold cut at natural pauses too aggressively, which made
# cross-chunk Gemini synthesis lose accumulated voice tone (whisper /
# narrate / story breath all reset on chunk N+1).
MIN_SPLIT_CHARS: int = 30

SENTENCE_PUNCT: str = "。！？!?\n"

_AUDIO_TAG_RE = re.compile(r"^\s*(\[[a-zA-Z][a-zA-Z _-]*\])\s*")


def split_for_tts(text: str) -> list[str]:
    """Split text into chunks ≤ CHUNK_MAX_CHARS at sentence boundaries.

    If text starts with an audio tag like ``[whispers]``, prepend that tag
    to every chunk so Gemini keeps the same voice characteristics across
    the whole reply (otherwise chunks 2+ revert to default voice).

    Behaviour summary:
      - Short replies (≤ CHUNK_MAX_CHARS): single chunk, unchanged.
      - Long replies with periods at idx ≥ MIN_SPLIT_CHARS: split there.
      - Long replies with comma at idx ≥ MIN_SPLIT_CHARS-1: split at comma.
      - Long replies with no usable split point: hard cut at CHUNK_MAX_CHARS.
      - Audio-tag preserved on every chunk for tone consistency.
    """
    text = text.strip()
    if not text:
        return []

    m = _AUDIO_TAG_RE.match(text)
    leading_tag = m.group(1) if m else ""
    body = text[m.end():].strip() if m else text

    if len(text) <= CHUNK_MAX_CHARS:
        return [text]

    raw_chunks: list[str] = []
    buf = ""
    for ch in body:
        buf += ch
        # Prefer sentence-end split once buf is long enough.
        if ch in SENTENCE_PUNCT and len(buf) >= MIN_SPLIT_CHARS:
            raw_chunks.append(buf.strip())
            buf = ""
        elif len(buf) >= CHUNK_MAX_CHARS:
            # Fallback: split at last comma / space. Filter -1 from rfind
            # so we can distinguish "no candidate" from "candidate too early".
            candidates = [
                buf.rfind("，"),
                buf.rfind(","),
                buf.rfind(" "),
            ]
            cut = max([c for c in candidates if c >= 0], default=-1)
            if cut >= MIN_SPLIT_CHARS - 1:
                # cut is index; chunk len = cut+1 (≥ MIN_SPLIT_CHARS chars).
                raw_chunks.append(buf[: cut + 1].strip())
                buf = buf[cut + 1:]
            else:
                # No usable split point at MIN_SPLIT_CHARS or beyond → hard cut.
                raw_chunks.append(buf.strip())
                buf = ""
    if buf.strip():
        raw_chunks.append(buf.strip())

    if not leading_tag:
        return [c for c in raw_chunks if c]

    # Prepend audio tag to every chunk to keep voice consistent across calls.
    return [f"{leading_tag} {chunk}" for chunk in raw_chunks if chunk]
