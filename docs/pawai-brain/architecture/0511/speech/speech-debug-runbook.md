# Speech Debug Runbook

這份是明天到學校現場排查語音用的順序。先分段定位，不要一開始就改 VAD threshold。

## 1. 看節點

```bash
ros2 node list
```

語音主線至少需要：

```text
/stt_intent_node
/tts_node
/pawai_brain 或 conversation_graph_node 對應 node
/interaction_executive_node
```

檢查 legacy 是否誤開：

```bash
ros2 node list | grep -E "llm_bridge|intent_tts_bridge|event_action_bridge"
```

## 2. Mic / ASR

```bash
ros2 topic echo /state/interaction/speech
ros2 topic echo /asr_result
ros2 topic echo /event/speech_intent_recognized
```

判斷：

| 現象 | 可能原因 |
| --- | --- |
| state 一直 INITIALIZING/ERROR | sounddevice/mic 開不起來 |
| recording=true 但沒有 asr_result | ASR provider 卡住 |
| asr_result provider=whisper_local | cloud/local SenseVoice 失敗或沒啟 |
| degraded=true | fallback 已發生 |
| intent=hallucination | Whisper 黑名單命中 |

## 3. Echo gate

```bash
ros2 topic echo /state/tts_playing
```

如果 `/state/tts_playing` 一直 true：

- TTS node 可能卡住。
- Go2 Megaphone playback 沒完成。
- exception path 沒 publish false。

如果 PawAI 一說話就被 ASR 收進去：

- `/state/tts_playing` QoS/latched 是否正常。
- `stt_intent_node` 是否訂到該 topic。
- 是否有其他喇叭聲源不是由 `tts_node` 控制。

## 4. Brain / Executive

```bash
ros2 topic echo /brain/chat_candidate
ros2 topic echo /brain/conversation_trace
ros2 topic echo /tts
```

判斷：

| 現象 | 可能原因 |
| --- | --- |
| 有 speech event，無 chat_candidate | Brain 沒啟、LLM 掛、session 被過濾 |
| 有 chat_candidate，無 /tts | Executive buffer timeout / session mismatch / active skill |
| /tts 很快出「我聽不太懂」 | chat_wait_ms timeout 比 Brain 慢 |
| /tts 出模板句 | legacy `intent_tts_bridge_node` 可能在跑 |

## 5. TTS / Go2

```bash
ros2 topic echo /tts
ros2 topic echo /webrtc_req
ros2 topic echo /state/tts_playing
```

期望 `/webrtc_req` 看到：

```text
api_id 4001
api_id 4003 ... many chunks
api_id 4002
```

如果有 `/tts` 沒 `/webrtc_req`：

- `tts_node` 沒啟。
- TTS provider 初始化失敗。
- provider chain 全部失敗。

如果有 `/webrtc_req` 沒聲音：

- Go2 driver / DataChannel 問題。
- Megaphone 卡狀態，需要重啟 `tts_node + go2_driver`，嚴重時 Go2 重開。
- 音量太小，確認 +16dB gain path 是否有跑。

## 6. 延遲拆解

現場可以用 topic 時序粗估：

```text
speech start/end log
-> /asr_result latency_ms
-> /brain/conversation_trace llm latency
-> /tts timestamp
-> /state/tts_playing true/false
```

常見瓶頸：

| 段 | 現象 |
| --- | --- |
| VAD | 講完後等 1 秒以上才送 ASR |
| ASR cloud | tunnel/server 慢或 fallback |
| Brain | LLM timeout / repair / fallback |
| TTS quality | Gemini chunk 多、網路慢 |
| Megaphone | 上傳 chunks + playback duration 固定吃時間 |

## 7. 建議調參順序

先不要直接把 VAD threshold 改低。按順序：

1. 確認 echo gate 正常。
2. 確認 ASR provider 是 `qwen_cloud` 或 `sensevoice_local`，不是一直 whisper。
3. 確認 legacy bridge 沒重複發 `/tts`。
4. 再調 VAD stop / silence。

可試：

```bash
ros2 param set /stt_intent_node energy_vad.silence_duration_ms 600
ros2 param set /stt_intent_node speech_end_grace_ms 300
```

如果切太短，句尾會被截掉。

## 8. 可跑測試

```bash
pytest speech_processor/test/test_intent_classifier.py
pytest speech_processor/test/test_text_normalization.py
pytest speech_processor/test/test_audio_tag.py
pytest speech_processor/test/test_tts_split_chunks.py
pytest speech_processor/test/test_tts_dual_route.py
pytest speech_processor/test/test_tts_fallback_chain.py
pytest speech_processor/test/test_pcm_trim.py
pytest interaction_executive/test/test_brain_rules.py
```

這些測試不會測真 mic、真 ASR cloud、真 Go2 Megaphone，只能保護純邏輯。

## 9. 明天 P0

- [ ] 確認 `speech_pipeline.launch.py` 之外，TTS/Brain/Executive 都有啟。
- [ ] 確認 legacy `intent_tts_bridge_node` / `llm_bridge_node legacy` 沒和主線重複。
- [ ] 測 5 句短問答，記錄 provider、ASR latency、TTS lane。
- [ ] 測 PawAI 講完後立刻插話，確認 echo gate 會不會吃掉使用者前幾個字。
- [ ] 測 safety「停」是否走 fast lane 且不被長句 quality lane 卡住。
