# ElevenLabs Spike-Mini — Voice + Latency Evaluation

> **Run date**: 2026-05-XX (replace XX with actual date)
> **Operator**: Roy
> **Goal**: GO/NO-GO decision for ElevenLabs Flash v2.5 in TTS quality lane

## Setup

- API key: `ELEVENLABS_API_KEY=sk_...` (NOT committed)
- Model: `eleven_flash_v2_5`
- PAYG balance before: $X.XX
- Voices tested (replace placeholders in `tools/tts_spike/elevenlabs_mini.py` first):

| name | voice_id | source/notes |
|---|---|---|
| MandarinChild_F | `<id>` | Childlike Mandarin female |
| MandarinYoung_F | `<id>` | Young Chinese female |
| Bella_or_Hope_multi | `<id>` | Multilingual young female |

## Scores (Roy fills 1-5)

| Voice | Sentence | 雪寶感 | 中文自然度 | 破音/吞字 | 簡體腔 | latency_s |
|---|---|---|---|---|---|---|
| MandarinChild_F | short | | | | | |
| MandarinChild_F | medium | | | | | |
| MandarinChild_F | long | | | | | |
| MandarinChild_F | emotional | | | | | |
| MandarinChild_F | safety | | | | | |
| MandarinYoung_F | short | | | | | |
| MandarinYoung_F | medium | | | | | |
| MandarinYoung_F | long | | | | | |
| MandarinYoung_F | emotional | | | | | |
| MandarinYoung_F | safety | | | | | |
| Bella_or_Hope_multi | short | | | | | |
| Bella_or_Hope_multi | medium | | | | | |
| Bella_or_Hope_multi | long | | | | | |
| Bella_or_Hope_multi | emotional | | | | | |
| Bella_or_Hope_multi | safety | | | | | |

## Latency summary (auto from _results.json)

| voice | short avg | medium avg | long avg |
|---|---|---|---|
| | | | |

## PAYG quota

- chars sent: ___ / approx 50k available
- balance after: $X.XX

## Decision

- [ ] **GO** — winning voice: ___ (voice_id: ___)
   - Reason: 音色 X/5, 中文 X/5, latency ___s short / ___s long, no defects
   - Next: spike-real branch (Megaphone integration)
- [ ] **NO-GO** — failing criterion: ___
   - Next: spike Gemini native SDK (P2-2-fallback)

## Notes
