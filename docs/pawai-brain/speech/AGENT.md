# 語音互動系統 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界

- **所屬 package**：`speech_processor`
- **上游**：USB 麥克風（硬體）、LLM endpoint（雲端/本地）
- **下游**：interaction_executive_node、tts_node → USB 喇叭

## 輸出 Topic

| Topic | 類型 | 頻率 | Schema |
|-------|------|------|--------|
| `/event/speech_intent_recognized` | String (JSON) | 事件式 | `{"intent": str, "text": str, "confidence": float, "reply_text": str}` |
| `/state/interaction/speech` | String (JSON) | 5 Hz | `{"listening": bool, "processing": bool, "warmup_done": bool}` |
| `/state/tts_playing` | String | 變更式 | `"true"` / `"false"` |
| `/asr_result` | String | 事件式 | 原始 ASR 文字 |

## 輸入 Topic

| Topic | 來源 | 說明 |
|-------|------|------|
| `/tts` | 任何 node | 要說的文字（String） |

## 依賴

- `faster-whisper`（CTranslate2 CUDA）
- `edge-tts`（雲端）或 `piper`（本地）
- USB 麥克風 UACDemoV1.0 + USB 喇叭 CD002-AUDIO
- LLM endpoint（Cloud Qwen2.5-7B 或 Ollama）

## 事件流

```
USB mic → stt_intent_node (VAD→Whisper→Intent)
    → llm_bridge_node (Cloud→Ollama→RuleBrain)
    → tts_node (edge-tts/Piper)
    → USB speaker
    → echo gate (1.5s)
```

## 接手確認清單

- [ ] Whisper warmup 完成？`ros2 topic echo /state/interaction/speech` 看 `warmup_done: true`
- [ ] 說「你好」有回應？
- [ ] echo gate 正常？TTS 播放時 ASR 不會收到自己的聲音
- [ ] LLM endpoint 連得到？`curl http://localhost:8000/v1/models`
