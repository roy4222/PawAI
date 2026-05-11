"""PCM silence trimming for chunked TTS concatenation.

Background (2026-05-11 night):
  Gemini-3.1 Flash TTS Preview returns raw int16 PCM with ~80-200ms of
  near-silence padding at both ends of every generated chunk. When the
  text-side splitter (`tts_split.split_for_tts`) breaks long replies into
  N chunks (CHUNK_MAX_CHARS=40), the parallel synthesis path concatenates
  all chunks with `b"".join(results)`, leaving N*2 silence gaps audible
  as "broken phrasing" / 斷句 during long replies (stories, poems, demos).

  Web research (Google Gemini TTS docs + community findings):
  - Gemini does NOT auto-trim silence; caller responsibility.
  - Re-anchoring voice tag per chunk already done in tts_split; that fixes
    voice consistency but not pacing.
  - Standard fix: amplitude-threshold trim both ends of every chunk
    before concatenation.

Threshold rationale (int16 / 24kHz):
  - max amplitude 32767
  - silence floor around -50 dB = ~103
  - we use 200 (~-44 dB) — conservative; trims only true silence padding,
    not natural breath which usually sits ~-30 dB or louder.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np


# 24kHz mono PCM — matches Gemini TTS output rate. Used for sample → ms math.
_SAMPLE_RATE_HZ: int = 24000

# Diagnostic mode — when env PAWAI_TTS_DIAG=1, trim_and_join_chunks prints
# per-chunk lead/tail cut counts to stderr. Off by default (zero overhead).
_DIAG: bool = os.environ.get("PAWAI_TTS_DIAG", "") == "1"


@dataclass(frozen=True)
class TrimResult:
    """Diagnostic output of trim_silence_pcm16_with_stats — never exposed via
    the existing trim_silence_pcm16() / trim_and_join_chunks() API contract.
    """
    pcm: bytes
    leading_cut_samples: int
    trailing_cut_samples: int

    @property
    def leading_cut_ms(self) -> float:
        return self.leading_cut_samples / _SAMPLE_RATE_HZ * 1000.0

    @property
    def trailing_cut_ms(self) -> float:
        return self.trailing_cut_samples / _SAMPLE_RATE_HZ * 1000.0


# Default silence amplitude threshold for int16 PCM.
# 200 ≈ -44 dB; trims gemini API padding but spares natural breath.
DEFAULT_THRESHOLD: int = 200

# Keep tail of silence on each chunk so consecutive chunks don't collide
# audibly. 80ms @ 24kHz = 1920 samples — natural-sounding pause between
# storytelling sentences without leaving the multi-hundred-ms padding
# gemini ships per chunk. (5/11 night: bumped from 30ms → 80ms after
# user reported "跳句" on long stories — 30ms was a sharp re-onset.)
DEFAULT_KEEP_TAIL_SAMPLES: int = 1920


def trim_silence_pcm16(
    pcm: bytes,
    threshold: int = DEFAULT_THRESHOLD,
    keep_tail_samples: int = DEFAULT_KEEP_TAIL_SAMPLES,
) -> bytes:
    """Trim near-silence from both ends of int16 mono PCM.

    Args:
        pcm: raw little-endian int16 mono PCM bytes.
        threshold: int16 amplitude below which a sample counts as silence.
        keep_tail_samples: leave this many silent samples on each end
            so concatenated chunks don't audibly collide (default ~80ms
            @ 24kHz).

    Returns:
        Trimmed PCM bytes. If the chunk is entirely silent (no sample
        exceeds threshold), returns an empty bytes (caller should skip).
    """
    return trim_silence_pcm16_with_stats(pcm, threshold, keep_tail_samples).pcm


def trim_silence_pcm16_with_stats(
    pcm: bytes,
    threshold: int = DEFAULT_THRESHOLD,
    keep_tail_samples: int = DEFAULT_KEEP_TAIL_SAMPLES,
) -> TrimResult:
    """Same trim semantics as trim_silence_pcm16(), but also returns the
    sample counts trimmed from each end so callers can diagnose padding
    behaviour.

    `leading_cut_samples` / `trailing_cut_samples` count samples ACTUALLY
    removed (after subtracting `keep_tail_samples` headroom). Returns
    `TrimResult(b"", 0, 0)` for empty input or fully-silent input.
    """
    if not pcm:
        return TrimResult(pcm, 0, 0)
    arr = np.frombuffer(pcm, dtype=np.int16)
    if arr.size == 0:
        return TrimResult(pcm, 0, 0)

    # Cast to int32 before abs(): int16 -32768 overflows np.abs() (stays
    # negative as -32768), so a full-scale negative sample would be
    # mis-classified as silence. Rare in practice but a real edge case.
    above = np.abs(arr.astype(np.int32)) >= threshold
    if not above.any():
        # Entire chunk is silence — caller should drop it.
        return TrimResult(b"", 0, 0)

    first = int(np.argmax(above))                       # first non-silent idx
    last = int(arr.size - 1 - np.argmax(above[::-1]))   # last non-silent idx

    start = max(0, first - keep_tail_samples)
    end = min(arr.size, last + 1 + keep_tail_samples)
    leading_cut = start                                 # samples removed from start
    trailing_cut = arr.size - end                       # samples removed from end
    return TrimResult(arr[start:end].tobytes(), leading_cut, trailing_cut)


class ChunkTrimError(RuntimeError):
    """Raised when a non-empty input chunk trims to empty (padding-only).

    Multi-chunk concat is all-or-nothing: if any chunk's audio comes back
    as padding-only, the corresponding text phrase would silently vanish
    on join, leading to confusing demo behaviour ("it just skipped that
    line"). Caller should treat this as synthesis failure and fall back
    to the next TTS provider.
    """


def trim_and_join_chunks(
    chunks: list[bytes],
    threshold: int = DEFAULT_THRESHOLD,
    keep_tail_samples: int = DEFAULT_KEEP_TAIL_SAMPLES,
) -> bytes:
    """Trim silence from each chunk, then concat.

    Empty input chunks are skipped silently (caller may have pre-filtered).
    Non-empty input that trims to empty raises ChunkTrimError so the caller
    can drop to the fallback provider rather than emit a silent phrase or
    an empty WAV.
    """
    trimmed: list[bytes] = []
    for idx, c in enumerate(chunks):
        if not c:
            continue
        res = trim_silence_pcm16_with_stats(c, threshold, keep_tail_samples)
        if _DIAG:
            sys.stderr.write(
                f"pcm_trim DIAG chunk[{idx}] cut_lead={res.leading_cut_ms:.0f}ms "
                f"cut_tail={res.trailing_cut_ms:.0f}ms in_bytes={len(c)} "
                f"out_bytes={len(res.pcm)}\n"
            )
            sys.stderr.flush()
        if not res.pcm:
            raise ChunkTrimError(
                f"chunk {idx} (len={len(c)}) trimmed to empty — "
                "synthesized audio is silence-only"
            )
        trimmed.append(res.pcm)
    return b"".join(trimmed)
