---
paths:
  - "speech_processor/**"
  - "docs/pawai-brain/speech/**"
  - "docs/modules/speech/**"
---
# speech_processor 規則
詳見 `docs/pawai-brain/speech/CLAUDE.md`（模組內規則真相來源）
## 快速提醒
- Whisper 在 Jetson 必須 `cuda` + `float16`，CPU int8 不支援會 silent fail
- echo gate：TTS 播放時 ASR 靜音，early return 必須拉回 `tts_playing=False`
- LLM timeout > 2s → fallback：Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain
- MeloTTS 和 ElevenLabs 已棄用（3/26 決議），不要加回來
- 測試：`python3 -m pytest speech_processor/test/ -v`
