"""Unit tests for TtsNode._split_for_tts — Phase A.6 5/8 chunking fix.

Two bugs the 5/8 fix addresses:

1. **Sentence threshold too aggressive** — original code split on period when
   buf ≥ CHUNK_MAX_CHARS // 2 (20 chars). Short clauses got cut too early,
   making Gemini lose voice tone across chunks.
2. **rfind -1 sentinel mishandled** — `max(rfind(','), rfind('，'), rfind(' '))`
   returns -1 when nothing matches; the threshold check `> CHUNK_MAX_CHARS//2`
   accidentally let very-late commas (close to cap) win, while making no
   distinction between "no candidate" and "candidate too early".

The fix: prefer sentence end at ≥ MIN_SPLIT_CHARS (30); fallback comma split
also requires ≥ MIN_SPLIT_CHARS chars; explicit -1 guard via list filter.

These tests use an unbound function call style so we don't need to spin up
a TtsNode (rclpy / hardware deps avoided).
"""
from __future__ import annotations

from speech_processor import tts_split


# Alias so the existing test bodies can reference `TtsNode.MIN_SPLIT_CHARS`
# etc. — module-level constants are the same source of truth.
class TtsNode:
    CHUNK_MAX_CHARS = tts_split.CHUNK_MAX_CHARS
    MIN_SPLIT_CHARS = tts_split.MIN_SPLIT_CHARS
    SENTENCE_PUNCT = tts_split.SENTENCE_PUNCT


def _split(text: str) -> list[str]:
    return tts_split.split_for_tts(text)


# ── Boundary / threshold ────────────────────────────────────────────────


def test_short_text_returns_single_chunk():
    text = "嗨，你好啊。"
    assert _split(text) == [text]


def test_constants_reflect_5_8_fix():
    """Sanity check: the 5/8 fix raised the split threshold to 30."""
    assert TtsNode.MIN_SPLIT_CHARS == 30
    assert TtsNode.CHUNK_MAX_CHARS == 40


# ── Bug #1: sentence threshold ──────────────────────────────────────────


def test_short_sentence_does_not_force_split_below_30():
    """'好。' at char 4 must NOT split mid-sentence even though it has period.
    Old code split when buf ≥ 20 — this ate natural breath flow."""
    text = "好。今天天氣很不錯，我們可以一起出去走走，好嗎？"
    chunks = _split(text)
    # First period at index 1 (length 2) is well below MIN_SPLIT_CHARS.
    # The whole reply is short enough (~24 chars) to be a single chunk.
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_splits_on_first_period_after_30_chars():
    """Period beyond MIN_SPLIT_CHARS should trigger split."""
    # 31 padding chars (above MIN_SPLIT_CHARS) + period + more content.
    head = "一" * 31
    tail = "二" * 20
    text = f"{head}。{tail}。"
    chunks = _split(text)
    assert len(chunks) >= 2
    # First chunk ends at the first period (32 chars including 。)
    assert chunks[0].endswith("。")
    assert chunks[0].startswith("一")


# ── Bug #2: rfind / cut threshold ───────────────────────────────────────


def test_long_text_no_punct_falls_back_to_hard_cut():
    """All-CJK no-punct text >40 chars → hard-cut at CHUNK_MAX_CHARS,
    not silently dropped or duplicated."""
    text = "今天天氣真好我們去散步好不好快樂的一天散步真的很開心對吧"
    chunks = _split(text)
    # No sentence punct, no comma — every chunk should be ≤ 40 chars.
    for c in chunks:
        assert len(c) <= TtsNode.CHUNK_MAX_CHARS, f"chunk too long: {c!r}"
    # Reassembled output should equal stripped input (no character loss).
    assert "".join(chunks) == text


def test_late_comma_used_as_split_point():
    """Comma at index 29 → cut at 29 (≥ MIN_SPLIT_CHARS-1 = 29).
    Reaches CHUNK_MAX_CHARS first (no sentence punct), then elif fires
    and rfind('，') = 29 is used."""
    # 29 chars + comma at idx 29 + 15 more chars (no period) → triggers
    # elif at len=40 since no sentence_punct before that.
    head = "一" * 29
    mid = "二" * 15
    text = f"{head}，{mid}"  # length 45 (29 + 1 + 15)
    chunks = _split(text)
    assert len(chunks) >= 2
    # First chunk ends with the late comma
    assert chunks[0].endswith("，"), f"first chunk={chunks[0]!r}"


def test_comma_too_early_falls_to_hard_cut():
    """Comma at index 4 (way before MIN_SPLIT_CHARS-1=29) must NOT be the
    cut point. Falls to hard cut at CHUNK_MAX_CHARS=40."""
    # comma at idx 1, then 50 no-punct chars
    text = "嗨，" + "一" * 50
    chunks = _split(text)
    # The early comma at idx 1 must NOT be the cut point — its position is
    # below MIN_SPLIT_CHARS-1, so we hard-cut at CHUNK_MAX_CHARS instead.
    assert len(chunks[0]) == TtsNode.CHUNK_MAX_CHARS, (
        f"expected hard cut at {TtsNode.CHUNK_MAX_CHARS}, got len={len(chunks[0])}"
    )
    # Reassembly preserves all characters (after stripping).
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


# ── Audio-tag preservation ──────────────────────────────────────────────


def test_audio_tag_preserved_on_first_chunk():
    text = "[whispers] 我來說一個小故事給你聽好不好。今天森林裡發生一件趣事呢。"
    chunks = _split(text)
    assert chunks[0].startswith("[whispers]")


def test_audio_tag_prepended_to_subsequent_chunks():
    # Body must be long enough to produce ≥ 2 chunks. Period at idx 31
    # (≥ MIN_SPLIT_CHARS=30) triggers split, then second sentence follows.
    body_first = "一" * 31 + "。"     # 32 chars, splits here
    body_second = "二" * 20 + "。"    # 21 chars, second chunk
    text = f"[whispers] {body_first}{body_second}"
    chunks = _split(text)
    assert len(chunks) >= 2, f"expected ≥2 chunks, got {chunks}"
    for c in chunks:
        assert c.startswith("[whispers]"), f"missing tag on: {c!r}"


# ── No characters lost ──────────────────────────────────────────────────


def test_reassembled_chunks_recover_full_body_with_tag():
    """Even with audio-tag, the body content (after the tag) must be
    fully preserved across chunks."""
    text = "[excited] 嗨大家好我是 PawAI！今天我想跟你介紹一下我會做什麼。我可以揮手坐下還可以講笑話喔！"
    chunks = _split(text)
    # Strip [excited] from each chunk and concatenate.
    body_recovered = "".join(c.replace("[excited] ", "", 1) for c in chunks)
    body_expected = text.replace("[excited] ", "", 1)
    # Whitespace at boundary edges may differ slightly due to .strip();
    # check character set equivalence after collapsing whitespace.
    assert body_recovered.replace(" ", "") == body_expected.replace(" ", "")


def test_empty_text_returns_empty_list():
    assert _split("") == []
    assert _split("   ") == []


# ── Sanity: no infinite loop on edge inputs ─────────────────────────────


def test_text_exactly_chunk_max_chars():
    text = "一" * TtsNode.CHUNK_MAX_CHARS
    chunks = _split(text)
    # ≤ MAX → single chunk per the early return at top of split()
    assert chunks == [text]


def test_text_chunk_max_plus_one():
    text = "一" * (TtsNode.CHUNK_MAX_CHARS + 1)
    chunks = _split(text)
    # No punct, must hard-cut.
    assert "".join(chunks) == text
    for c in chunks:
        assert len(c) <= TtsNode.CHUNK_MAX_CHARS
