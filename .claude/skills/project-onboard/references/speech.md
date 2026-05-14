# 語音模組（speech_processor）

## 這個模組是什麼

Layer 2 感知 + Layer 3 輸出的雙重橋樑：麥克風收音 → ASR → Intent 分類 → Brain（或 RuleBrain fallback）→ TTS → Go2 Megaphone 播放。
5/12 主線是 SenseVoice Cloud ASR + gpt-5.4-mini Brain + Gemini TTS Despina（> 12 字）/ edge_tts（快速通道）。
Jetson 本地路徑（Whisper local + Piper）作為完全離線 fallback。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/speech/speech.md` | 主總覽 + 三層管線 + 5/11 freeze 快照 |
| `docs/pawai-brain/architecture/0511/speech/speech-runtime-flow.md` | 完整資料流（KWS → ASR → Brain → TTS → Go2）|
| `docs/pawai-brain/architecture/0511/speech/speech-asr-vad.md` | ASR provider 選型 + VAD 策略 + SenseVoice Cloud vs Local |
| `docs/pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md` | TTS 雙通道（quality/fast）+ Go2 Megaphone DataChannel 協定 |
| `docs/pawai-brain/architecture/0511/speech/speech-brain-executive-integration.md` | `/event/speech_intent_recognized` 與 Brain、Executive 的整合 |
| `docs/pawai-brain/architecture/0511/speech/speech-debug-runbook.md` | 現場症狀 → 節點 + 常見故障排查 |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `speech_processor/speech_processor/stt_intent_node.py` | ASR + Intent 整合節點（Whisper/SenseVoice + IntentClassifier）|
| `speech_processor/speech_processor/tts_node.py` | TTS 合成 + Go2 Megaphone DataChannel 播放（4001/4003/4002）|
| `speech_processor/speech_processor/llm_bridge_node.py` | Cloud LLM 橋接，發布 /tts + /webrtc_req |
| `speech_processor/config/speech_processor.yaml` | ASR/TTS provider、設備、閾值設定 |
| `scripts/start_full_demo_tmux.sh` | 13-window 全功能 demo 一鍵啟動 |
| `scripts/start_llm_e2e_tmux.sh` | 純語音 e2e（dev 用，不啟 perception/Go2）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/event/speech_intent_recognized` | stt_intent_node → | 語音意圖 JSON（intent, text, confidence, session_id）|
| `/tts` | → tts_node / Gateway | TTS 輸入（純文字或 JSON envelope {text, input_origin}）|
| `/state/interaction/speech` | stt_intent_node → | 語音管線狀態（phase, last_asr_text, models_loaded）|
| `/asr_result` | stt_intent_node → | ASR 純文字輸出 |
| `/webrtc_req` | tts_node → go2_driver | Go2 WebRTC Megaphone 指令 |

## 已知陷阱

- **Whisper + Jetson CUDA**：必須用 `device: cuda` + `compute_type: float16`（int8 不支援，silent fail）。`speech_processor.yaml` 預設 `cpu + int8`，Demo 啟動腳本覆寫為 `cuda + float16`
- **Megaphone cooldown**：4002 EXIT 後 sleep 0.5s，防止 Go2 狀態機未重置導致 silent fail
- **mid-session tts_node 重啟**：會導致 Megaphone silent fail，必須連 Go2 driver 一起重啟
- **HyperX SoloCast 是 stereo-only**：需 `channels:=2` + 手動 downmix，不能用 `channels:=1`
- **zsh glob 炸陣列參數**：`provider_order` 參數要加引號 `'["whisper_local"]'`
- **機身 USB 麥克風已廢棄**：Go2 風扇噪音導致 ~20% 辨識率，Demo 改用筆電 Studio 收音

## 開發入口

```bash
# 全功能 demo（13-window tmux）
bash scripts/start_full_demo_tmux.sh

# 純語音 e2e（dev 用）
bash scripts/start_llm_e2e_tmux.sh

# 快速驗證 TTS → Go2 播放
ros2 topic pub --once /tts std_msgs/msg/String '{data: "測試播放"}'

# 清理
bash scripts/clean_speech_env.sh
```
