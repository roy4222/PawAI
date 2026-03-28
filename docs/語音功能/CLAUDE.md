# 語音互動系統 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。`.claude/rules/` 中的對應檔案只是薄橋接。

## 不能做

- 不要改 echo gate 的 timing（tts_playing + cooldown 0.5s + echo_cooldown 1.0s = 1.5s）除非有完整 E2E 測試
- 不要用 MeloTTS 或 ElevenLabs（已棄用 3/26）
- 不要假設 Whisper 可以用 int8（Jetson 不支援，必須 cuda + float16）

## 改之前先看

- `speech_processor/speech_processor/stt_intent_node.py`（1078 行，ASR + VAD + Intent）
- `speech_processor/speech_processor/tts_node.py`（787 行，TTS + 播放）
- `speech_processor/speech_processor/llm_bridge_node.py`（624 行，LLM 三級 fallback）
- `docs/語音功能/README.md`

## 常見陷阱

- USB 麥克風 UACDemoV1.0：device index 會飄（24→0），用 `source scripts/device_detect.sh`
- USB 喇叭 CD002-AUDIO：`plughw:3,0`，card number 重開機可能漂移
- mic_gain 預設 8.0（noisy profile v1），不要改回 4.0 除非安靜環境
- Whisper vad_filter=True + no_speech_threshold=0.6 已啟用，不要關掉
- zsh glob 會炸陣列：用 `'["whisper_local"]'` 加引號
- LD_LIBRARY_PATH 必須含 `/home/jetson/.local/ctranslate2-cuda/lib`
- LLM timeout > 2s → fallback 到 RuleBrain

## 驗證指令

```bash
python3 -m pytest speech_processor/test/ -v
colcon build --packages-select speech_processor
```
