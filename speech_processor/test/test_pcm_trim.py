"""Tests for speech_processor.pcm_trim — gemini TTS silence trimming.

ROS-free; pytest can run these without sourcing the workspace.
"""
from __future__ import annotations

import numpy as np
import pytest

from speech_processor.pcm_trim import (
    DEFAULT_KEEP_TAIL_SAMPLES,
    DEFAULT_THRESHOLD,
    ChunkTrimError,
    TrimResult,
    trim_and_join_chunks,
    trim_silence_pcm16,
    trim_silence_pcm16_with_stats,
)


def _make_pcm(amplitudes: list[int]) -> bytes:
    return np.array(amplitudes, dtype=np.int16).tobytes()


def _amps(pcm: bytes) -> list[int]:
    return np.frombuffer(pcm, dtype=np.int16).tolist()


def test_trim_removes_leading_and_trailing_silence():
    pcm = _make_pcm([0, 0, 0, 5000, 6000, 5000, 0, 0, 0])
    out = trim_silence_pcm16(pcm, keep_tail_samples=0)
    assert _amps(out) == [5000, 6000, 5000]


def test_trim_keeps_tail_samples():
    pcm = _make_pcm([0, 0, 0, 0, 5000, 6000, 5000, 0, 0, 0, 0])
    out = trim_silence_pcm16(pcm, keep_tail_samples=2)
    # leading: first audio at idx 4; keep_tail=2 → start = idx 2
    # trailing: last audio at idx 6; keep_tail=2 → end = idx 9 (exclusive)
    assert _amps(out) == [0, 0, 5000, 6000, 5000, 0, 0]


def test_trim_empty_input():
    assert trim_silence_pcm16(b"") == b""


def test_trim_fully_silent_returns_empty():
    pcm = _make_pcm([0, 50, -50, 100, 0])  # all below default threshold 200
    assert trim_silence_pcm16(pcm) == b""


def test_trim_does_not_remove_natural_breath():
    """Audio at ~-30 dB (amplitude ~1000) is natural breath; must NOT trim."""
    pcm = _make_pcm([1000, 1500, 8000, 6000, 1500, 1000])
    out = trim_silence_pcm16(pcm, keep_tail_samples=0)
    assert _amps(out) == [1000, 1500, 8000, 6000, 1500, 1000]


def test_trim_threshold_inclusive():
    """Sample exactly at threshold counts as non-silent (>=)."""
    pcm = _make_pcm([0, DEFAULT_THRESHOLD, 0])
    out = trim_silence_pcm16(pcm, keep_tail_samples=0)
    assert _amps(out) == [DEFAULT_THRESHOLD]


def test_trim_and_join_raises_on_silent_chunk():
    """Non-empty input that trims to silence must raise — otherwise the
    corresponding text phrase silently vanishes on join."""
    voice = _make_pcm([0, 0, 5000, 6000, 0, 0])
    silent = _make_pcm([0, 50, -50, 0])
    with pytest.raises(ChunkTrimError):
        trim_and_join_chunks([voice, silent, voice], keep_tail_samples=0)


def test_trim_and_join_skips_empty_input_chunks():
    """Empty input bytes are pre-filtered (caller may have produced them);
    only non-empty-but-silent triggers the error."""
    voice = _make_pcm([0, 0, 5000, 6000, 0, 0])
    out = trim_and_join_chunks([b"", voice, b"", voice], keep_tail_samples=0)
    assert _amps(out) == [5000, 6000, 5000, 6000]


def test_trim_handles_int16_full_scale_negative():
    """np.abs() on int16 overflows for -32768 (stays negative). Without
    int32 cast, full-scale negative samples are mis-classified as silence."""
    # Single full-scale negative sample surrounded by silence.
    pcm = _make_pcm([0, 0, 0, -32768, 0, 0, 0])
    out = trim_silence_pcm16(pcm, keep_tail_samples=0)
    assert _amps(out) == [-32768], "full-scale negative sample dropped"


def test_trim_and_join_preserves_chunk_order():
    a = _make_pcm([0, 1000, 2000, 0])
    b = _make_pcm([0, 3000, 4000, 0])
    c = _make_pcm([0, 5000, 6000, 0])
    out = trim_and_join_chunks([a, b, c], keep_tail_samples=0)
    assert _amps(out) == [1000, 2000, 3000, 4000, 5000, 6000]


def test_trim_reduces_total_size_for_padded_chunks():
    """Realistic test: 200 samples leading + trailing silence (~8ms @ 24kHz)
    around a 100-sample voice region. Trim should reduce significantly."""
    padding = [0] * 200
    voice = [5000] * 100
    pcm = _make_pcm(padding + voice + padding)
    out = trim_silence_pcm16(pcm, keep_tail_samples=DEFAULT_KEEP_TAIL_SAMPLES)
    # default keeps 720 samples each side, but we only have 200 of padding
    # so total = 200 + 100 + 200 = 500, same as input (nothing trimmed).
    # Test instead with a much smaller keep_tail_samples.
    out2 = trim_silence_pcm16(pcm, keep_tail_samples=10)
    assert len(out2) < len(pcm)
    # Expected: 10 + 100 + 10 = 120 samples = 240 bytes
    assert len(out2) == (10 + 100 + 10) * 2


# ── trim_silence_pcm16_with_stats — diagnostic variant ──────────────────────


def test_trim_with_stats_basic_cut_counts():
    """200 leading silence + 100 voice + 150 trailing silence, keep_tail=0
    → cut counts equal full silence runs."""
    pcm = _make_pcm([0] * 200 + [5000] * 100 + [0] * 150)
    res = trim_silence_pcm16_with_stats(pcm, keep_tail_samples=0)
    assert isinstance(res, TrimResult)
    assert res.leading_cut_samples == 200
    assert res.trailing_cut_samples == 150
    # Output should be the 100 voice samples only.
    assert _amps(res.pcm) == [5000] * 100


def test_trim_with_stats_no_silence():
    """All samples above threshold → no cut counted."""
    pcm = _make_pcm([5000] * 50)
    res = trim_silence_pcm16_with_stats(pcm)
    assert res.leading_cut_samples == 0
    assert res.trailing_cut_samples == 0
    assert _amps(res.pcm) == [5000] * 50


def test_trim_with_stats_all_silent():
    """Fully silent input returns TrimResult(b'', 0, 0)."""
    pcm = _make_pcm([0, 50, -50, 100, 0])  # all below default threshold
    res = trim_silence_pcm16_with_stats(pcm)
    assert res.pcm == b""
    assert res.leading_cut_samples == 0
    assert res.trailing_cut_samples == 0


def test_trim_with_stats_respects_keep_tail():
    """With keep_tail_samples=50, only the silence BEYOND 50 samples is
    counted as cut. 200 leading - 50 kept = 150 cut."""
    pcm = _make_pcm([0] * 200 + [5000] * 50 + [0] * 200)
    res = trim_silence_pcm16_with_stats(pcm, keep_tail_samples=50)
    assert res.leading_cut_samples == 150
    assert res.trailing_cut_samples == 150
    # Output: 50 silent + 50 voice + 50 silent = 150 samples
    assert _amps(res.pcm) == [0] * 50 + [5000] * 50 + [0] * 50


def test_trim_with_stats_ms_properties():
    """ms helpers compute against 24kHz sample rate."""
    res = TrimResult(b"", leading_cut_samples=2400, trailing_cut_samples=4800)
    assert res.leading_cut_ms == pytest.approx(100.0)
    assert res.trailing_cut_ms == pytest.approx(200.0)


def test_trim_silence_pcm16_remains_bytes_returning():
    """Public API regression: the bytes-returning wrapper must keep the same
    contract as before this refactor (existing callers depend on it)."""
    pcm = _make_pcm([0, 0, 5000, 6000, 0, 0])
    out = trim_silence_pcm16(pcm, keep_tail_samples=0)
    assert isinstance(out, bytes)
    assert _amps(out) == [5000, 6000]
