# Speech Runtime Flow

這份文件只看語音端到端 runtime：USB mic 怎麼進 ASR、speech event 怎麼進 Brain/Executive、TTS 怎麼從 Go2 喇叭播出。

## 1. 系統位置

語音主要 package：

```text
speech_processor/
```

主要檔案：

| 角色 | 檔案 |
| --- | --- |
| mic + VAD + ASR + intent | `speech_processor/speech_processor/stt_intent_node.py` |
| pure intent classifier | `speech_processor/speech_processor/intent_classifier.py` |
| TTS node | `speech_processor/speech_processor/tts_node.py` |
| TTS provider protocol | `speech_processor/speech_processor/tts_provider.py` |
| audio tag strip | `speech_processor/speech_processor/audio_tag.py` |
| Gemini TTS chunk split | `speech_processor/speech_processor/tts_split.py` |
| legacy LLM bridge | `speech_processor/speech_processor/llm_bridge_node.py` |
| legacy template bridge | `speech_processor/speech_processor/intent_tts_bridge_node.py` |
| speech launch | `speech_processor/launch/speech_pipeline.launch.py` |
| speech config | `speech_processor/config/speech_processor.yaml` |

## 2. Runtime 架構圖

```text
USB mic / ALSA / sounddevice
        |
        v
stt_intent_node.py
  - echo gate via /state/tts_playing
  - resample/downmix
  - energy VAD
  - ASR provider fallback
  - s2twp normalization
  - intent_classifier.py
        |
        +-----------------------------+
        |                             |
        v                             v
/asr_result                    /event/speech_intent_recognized
                                      |
                                      +-------------------------+
                                      |                         |
                                      v                         v
                                pawai_brain              interaction_executive
                                LangGraph                brain_node buffer
                                      |                         |
                                      v                         v
                              /brain/chat_candidate      SkillPlan / SAY step
                                      |                         |
                                      +-----------+-------------+
                                                  |
                                                  v
                                                /tts
                                                  |
                                                  v
tts_node.py
  - parse plain text or JSON envelope
  - choose fast/quality lane
  - provider fallback
  - cache
  - convert to 16k mono WAV
  - publish /state/tts_playing
  - send /webrtc_req audiohub 4001/4003/4002
                                                  |
                                                  v
                                            Go2 Megaphone
```

## 3. Launch 邊界

`speech_pipeline.launch.py` 目前只啟：

```text
vad_node
stt_intent_node
```

它不直接啟：

```text
tts_node
llm_bridge_node
intent_tts_bridge_node
pawai_brain
interaction_executive
```

所以現場如果「ASR 有字但沒有聲音」，不要只查 speech pipeline，要確認 `tts_node` 和 `interaction_executive_node` 是否也有啟。

## 4. 主要 topic

| Topic | Publisher | Consumer | 用途 |
| --- | --- | --- | --- |
| `/event/speech_intent_recognized` | `stt_intent_node` | Brain / Executive / legacy bridges | 語音事件 |
| `/asr_result` | `stt_intent_node` | debug / observer | ASR 原始結果 |
| `/intent` | `stt_intent_node` | debug | intent label |
| `/state/interaction/speech` | `stt_intent_node` | debug / Studio | speech state |
| `/tts` | Executive / legacy bridge / manual pub | `tts_node` | TTS command |
| `/state/tts_playing` | `tts_node` | STT echo gate / Executive world state | 播放狀態 |
| `/webrtc_req` | `tts_node` | Go2 driver | audiohub Megaphone command |

## 5. 目前最容易混淆的點

語音不是一條單線，而是至少三段：

```text
STT: mic -> /event/speech_intent_recognized
Brain/Executive: speech event -> SkillPlan -> /tts
TTS: /tts -> audio -> Go2
```

所以 debug 時要先定位是哪一段壞：

- 沒有 `/asr_result`：mic / VAD / ASR 壞。
- 有 `/asr_result` 但沒有 `/event/speech_intent_recognized`：intent publish 壞或文字被 hallucination/empty filter 擋。
- 有 speech event 但沒有 `/brain/chat_candidate`：Brain 壞或沒啟。
- 有 chat candidate 但沒有 `/tts`：Executive buffer / timeout / active skill gate 問題。
- 有 `/tts` 但沒聲音：TTS provider / Go2 Megaphone / `/webrtc_req` 問題。

