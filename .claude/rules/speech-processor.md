---
paths:
  - "speech_processor/**"
  - "docs/語音功能/**"
  - "docs/modules/speech/**"
---

# speech_processor 模組規則

## 現況
- **狀態**：80% 完成，Demo ready（3/25）
- **主線**：Whisper small（CUDA float16）→ Intent → LLM → edge-tts → USB 喇叭
- **權威文件**：`docs/語音功能/README.md`

## 關鍵檔案
- `speech_processor/speech_processor/stt_intent_node.py`（1078 行，ASR + VAD + Intent）
- `speech_processor/speech_processor/tts_node.py`（787 行，TTS + 播放）
- `speech_processor/speech_processor/llm_bridge_node.py`（624 行，LLM 三級 fallback）
- `speech_processor/speech_processor/intent_classifier.py`（200 行，中文 Intent 分類）

## 開發注意
- **Whisper 在 Jetson 必須 `cuda` + `float16`**，CPU int8 不支援會 silent fail
- **LD_LIBRARY_PATH** 必須含 `/home/jetson/.local/ctranslate2-cuda/lib`
- **echo gate**：TTS 播放時 ASR 靜音，early return 必須拉回 `tts_playing=False`
- **LLM timeout > 2s → fallback**：Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain
- **USB 麥克風**：UACDemoV1.0（device 24，mono，48kHz，mic_gain:=4.0）
- **USB 喇叭**：CD002-AUDIO（`plughw:3,0`），card number 重開機可能漂移
- **MeloTTS 和 ElevenLabs 已棄用**（3/26 決議）
- zsh glob 會炸陣列：用 `'["whisper_local"]'` 加引號

## 測試
```bash
python3 -m pytest speech_processor/test/ -v
colcon build --packages-select speech_processor
```

## ROS2 Topics
- `/event/speech_intent_recognized`（Intent 事件 JSON）
- `/state/interaction/speech`（5Hz 語音管線狀態）
- `/state/tts_playing`（Bool-like，latched）
- `/tts`（String，TTS 輸入）
- `/asr_result`（原始 ASR 文字）
