# TTS Spike Tools

Scripts for evaluating new TTS providers before integrating into main chain.

## ElevenLabs Spike-Mini

**Goal**: Decide whether to add ElevenLabs to TTS quality lane (replacing OpenRouter Gemini for emotional/long content).

**Time**: ~30 min setup + 30 min listening + scoring

### Steps

1. **Get API key**: Sign up at https://elevenlabs.io, top up $5 PAYG, copy API key from settings.

   ```bash
   export ELEVENLABS_API_KEY=sk_...
   ```

2. **Pick 3 voice candidates** at https://elevenlabs.io/app/voice-library
   - Filter by language: Chinese / Mandarin (or Multilingual)
   - Look for: female, young, warm/playful tone (closest to '雪寶'-like)
   - Copy each voice's ID (from voice detail page URL or copy button)

3. **Edit `elevenlabs_mini.py`**: replace 3 `REPLACE_WITH_VOICE_ID_*` placeholders with real voice IDs + names.

4. **Run**:

   ```bash
   cd /home/roy422/newLife/elder_and_dog
   python3 tools/tts_spike/elevenlabs_mini.py
   ```

   Output:
   - `tools/tts_spike/output/<voice_name>_<sentence>.mp3` — 5 sentences × 3 voices = 15 mp3
   - `tools/tts_spike/output/_results.json` — latency table

5. **Listen + score** each .mp3 (1-5 scale):
   - 雪寶感 (childlike warmth)
   - 中文自然度 (no robotic / no English-accent / no Mainland accent)
   - 破音/吞字/簡體腔 (any)

6. **Fill in dev-log**: `docs/pawai-brain/dev-logs/2026-05-XX-elevenlabs-spike-mini.md`

7. **Decision**:
   - **GO**: ≥ 1 voice ≥ 4/5 音色 AND ≥ 4/5 中文 AND short < 2s AND long < 4s AND no defects → proceed to Spike-Real
   - **NO-GO**: any criterion fails → fall back to Gemini native SDK spike (`spike/gemini-native-tts`)

### Cost estimate

PAYG $5 ≈ 50k characters Flash v2.5 (rate from https://elevenlabs.io/pricing — verify current).

5 sentences × 3 voices ≈ 200 chars total → < 1% of $5 quota. Plenty of headroom for Spike-Real (Megaphone integration test).

### Out of scope

- Voice cloning (custom voice from sample) — Pro plan only, demo 後再評估
- Streaming endpoint integration — Spike-Real (separate phase)
- Megaphone DataChannel wiring — Spike-Real

## Gemini native SDK fallback

If ElevenLabs Mini NO-GO, the alternative spike script will live at:

```
tools/tts_spike/gemini_native_mini.py
```

(not yet written — only build if ElevenLabs fails)
