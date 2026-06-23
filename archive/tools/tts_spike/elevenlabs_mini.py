#!/usr/bin/env python3
"""ElevenLabs Spike-Mini — voice + latency probe.

Usage:
    export ELEVENLABS_API_KEY=sk_...
    python3 tools/tts_spike/elevenlabs_mini.py

Output:
    tools/tts_spike/output/<voice_id>_<idx>.mp3 — 5 sentences × N voices
    tools/tts_spike/output/_results.json        — latency + metadata
    docs/pawai-brain/dev-logs/2026-05-XX-elevenlabs-spike-mini.md  (Roy fills in scores)

GO/NO-GO criteria (Roy listens + scores 1-5):
    1. ≥ 1 voice 音色 ≥ 4/5
    2. 中文自然度 ≥ 4/5
    3. 短句 < 2s AND 長句 < 4s (latency only — no Megaphone integration)
    4. 無破音 / 吞字 / 簡體腔
    5. PAYG quota dashboard 看實際消耗（記下 character usage）

If GO → spike-real (Megaphone integration) on `spike/elevenlabs-tts-real`.
If NO-GO → fall back to Gemini native spike (`spike/gemini-native-tts`).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P2-2a
Plan: docs/pawai-brain/plans/2026-05-11-elevenlabs-spike-and-dual-route.md Phase E-1
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import NamedTuple

try:
    import requests
except ImportError:
    raise SystemExit(
        "requests not installed; run `uv pip install requests` or `pip install requests`"
    )


class Voice(NamedTuple):
    voice_id: str
    name: str
    notes: str  # why we picked this voice


# 3 Mandarin/multilingual female voices to spike-test.
# Voice IDs from ElevenLabs Voice Library — refresh from dashboard if changed.
# https://elevenlabs.io/app/voice-library  (filter language=Chinese / Mandarin)
VOICE_CANDIDATES: list[Voice] = [
    # NOTE: voice IDs below are PLACEHOLDERS — fill in from Voice Library.
    # Search "Mandarin", "Chinese", or multilingual female voices < 30y.
    # Roy: replace these 3 IDs before running.
    Voice(
        voice_id="REPLACE_WITH_VOICE_ID_1",
        name="MandarinChild_F",
        notes="Childlike Mandarin female; closest to '雪寶' tone",
    ),
    Voice(
        voice_id="REPLACE_WITH_VOICE_ID_2",
        name="MandarinYoung_F",
        notes="Young Chinese female; warm/casual",
    ),
    Voice(
        voice_id="REPLACE_WITH_VOICE_ID_3",
        name="Bella_or_Hope_multi",
        notes="Multilingual young female (e.g., Bella/Hope) — tests Chinese coverage",
    ),
]

TEST_SENTENCES: list[tuple[str, str]] = [
    ("short", "嗨！"),
    ("medium", "我看到桌上有杯子，是紅色的，是新買的嗎？"),
    ("long", "我是 PawAI，住在你家的小狗。今天天氣不錯欸，你想出去散步嗎？我會跟著你到處看看。"),
    ("emotional", "[whispers] 我剛剛聽到外面有聲音，有點怕怕的，你陪我一下好嗎？"),
    ("safety", "停下來！前面有東西不要動。"),
]

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
MODEL_ID = "eleven_flash_v2_5"  # low-latency, multilingual


def synthesize(api_key: str, voice_id: str, text: str) -> tuple[bytes | None, float, str | None]:
    """Synthesize via ElevenLabs Flash v2.5; return (audio_mp3, latency_s, error)."""
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
    }
    t0 = time.monotonic()
    try:
        resp = requests.post(
            f"{API_URL}/{voice_id}",
            headers=headers,
            json=payload,
            timeout=30,
        )
        latency = time.monotonic() - t0
        if resp.status_code != 200:
            return None, latency, f"HTTP {resp.status_code}: {resp.text[:200]}"
        return resp.content, latency, None
    except Exception as e:
        return None, time.monotonic() - t0, f"{type(e).__name__}: {e}"


def main() -> int:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not set in env")
        return 1

    placeholder_voices = [v for v in VOICE_CANDIDATES if v.voice_id.startswith("REPLACE")]
    if placeholder_voices:
        print("ERROR: VOICE_CANDIDATES still has placeholder IDs.")
        print("       Pick voices from https://elevenlabs.io/app/voice-library")
        print("       and replace REPLACE_WITH_VOICE_ID_* in this script.")
        return 2

    results: list[dict] = []
    total_chars = 0

    for voice in VOICE_CANDIDATES:
        for sentence_kind, sentence_text in TEST_SENTENCES:
            print(f"[{voice.name}] {sentence_kind}: {sentence_text!r}")
            audio, latency, err = synthesize(api_key, voice.voice_id, sentence_text)
            chars = len(sentence_text)
            total_chars += chars

            entry = {
                "voice_id": voice.voice_id,
                "voice_name": voice.name,
                "voice_notes": voice.notes,
                "sentence_kind": sentence_kind,
                "sentence_text": sentence_text,
                "chars": chars,
                "latency_s": round(latency, 3),
                "ok": audio is not None,
                "error": err,
            }
            if audio is not None:
                out_path = OUTPUT_DIR / f"{voice.name}_{sentence_kind}.mp3"
                out_path.write_bytes(audio)
                entry["output_file"] = str(out_path)
                print(f"  → {out_path} ({len(audio)} bytes, {latency:.2f}s)")
            else:
                print(f"  ✗ FAIL: {err}")

            results.append(entry)

    summary_path = OUTPUT_DIR / "_results.json"
    summary_path.write_text(
        json.dumps(
            {
                "model_id": MODEL_ID,
                "total_chars": total_chars,
                "voices_tested": len(VOICE_CANDIDATES),
                "sentences": [k for k, _ in TEST_SENTENCES],
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n=== Summary ===")
    print(f"Total chars sent: {total_chars}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"Summary JSON: {summary_path}")
    print(f"\nNext steps:")
    print(f"  1. Listen to all .mp3 in {OUTPUT_DIR}")
    print(f"  2. Score each voice (1-5) on: 雪寶感 / 中文自然度")
    print(f"  3. Check ElevenLabs dashboard for actual quota usage")
    print(f"  4. Fill scores in docs/pawai-brain/dev-logs/2026-05-XX-elevenlabs-spike-mini.md")
    print(f"  5. If ≥ 1 voice scored ≥ 4/5 + latency targets met → GO; else NO-GO (try Gemini native)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
