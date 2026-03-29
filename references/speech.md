# 語音模組 Reference

## 定位

ASR（語音轉文字）+ Intent 分類 + LLM 對話 + TTS（文字轉語音）+ Go2 播放。
E2E 流程：使用者說話 → SenseVoice（cloud → local → Whisper fallback） → Intent 分類 → fast path（已知 intent）或 LLM → edge-tts/Piper → USB 喇叭。

## 權威文件

- **語音模組設計**：`docs/語音功能/README.md`
- **LLM 整合規格**：`docs/superpowers/specs/2026-03-16-llm-integration-mini-spec.md`
- **ROS2 介面契約**：`docs/architecture/contracts/interaction_contract.md` (語音相關 topics)

## 核心程式

| 檔案 | 用途 |
|------|------|
| `speech_processor/speech_processor/stt_intent_node.py` | ASR + Energy VAD + Intent 分類 |
| `speech_processor/speech_processor/intent_classifier.py` | Intent 分類器（純 Python，從 stt_intent_node 抽出） |
| `speech_processor/speech_processor/llm_bridge_node.py` | Cloud/Local LLM + fast path + RuleBrain fallback + reply 硬截斷 |
| `speech_processor/speech_processor/llm_contract.py` | LLM JSON 契約（純 Python，從 llm_bridge_node 抽出） |
| `speech_processor/speech_processor/tts_node.py` | TTS 合成 + USB 喇叭 local 播放 / Megaphone DataChannel 播放 |
| `speech_processor/speech_processor/intent_tts_bridge_node.py` | 舊版模板回覆（保留作 fallback） |
| `speech_processor/config/speech_processor.yaml` | 語音模組參數 |

## 關鍵 Topics

- `/event/speech_intent_recognized` — Intent 事件 JSON（觸發式）
- `/state/interaction/speech` — 語音管線狀態（5 Hz）
- `/tts` — TTS 輸入文字（std_msgs/String）
- `/webrtc_req` — Go2 WebRTC 命令

## 啟動方式

```bash
# 一鍵 E2E（推薦，預設 edge-tts + USB 外接設備）
bash scripts/start_llm_e2e_tmux.sh

# 全離線模式（Piper TTS）
TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh

# 切回 HyperX + Megaphone
LOCAL_PLAYBACK=false INPUT_DEVICE=0 CHANNELS=2 CAPTURE_SAMPLE_RATE=44100 \
  TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh

# Smoke test
bash scripts/smoke_test_e2e.sh 5
```

## 外接音訊設備（2026-03-24 驗證通過）

- **麥克風**：UACDemoV1.0（`hw:2,0`，mono，48kHz）— sounddevice index 24
- **喇叭**：CD002-AUDIO（`hw:3,0`，stereo，48kHz）— 音量需 `amixer -c 3 set PCM 147`
- Piper 原生 22050Hz 直出，清晰度相比 Megaphone 16kHz 大幅改善
- `LD_LIBRARY_PATH` 必須含 `/home/jetson/.local/ctranslate2-cuda/lib`（啟動腳本已處理）
- Whisper 必須用 `device=cuda, compute_type=float16`（Jetson CPU 不支援 int8）
- **mic_gain**：USB 麥克風靈敏度低，需 `-p mic_gain:=4.0`。gain 只作用在送 Whisper 的錄音，不影響 VAD 閾值判斷

## 本地 LLM 驗證（2026-03-24）

- **qwen2.5:1.5b**（Ollama）：JSON parse 6/6 = 100%，中文穩定，零 fallback → 建議為本地 fallback 主力
- **qwen2.5:0.5b**：JSON parse 2/8 = 25%，語言漂移嚴重 → 不適合作為 fallback
- intent 映射偏差（come_here/stop/take_photo）→ system prompt 待修
- 用法：`-p llm_endpoint:=http://localhost:11434/v1/chat/completions -p llm_model:=qwen2.5:1.5b`

## TTS 主線：edge-tts + Piper fallback（2026-03-24）

- **主線**：edge-tts（合成 P50 0.72s，A 級音質，需網路）
- **fallback**：Piper（合成 P50 2.0s，離線可用），edge-tts 失敗自動接手
- **TTS_PROVIDER** env var 控制：`edge_tts`（預設）或 `piper`
- reply_text 硬截斷 12 字（`_post_process_reply()`），小模型不遵守 prompt 限制

## Intent fast path（2026-03-24）

- `greet/stop/sit/stand` + confidence >= 0.8 → 跳過 LLM，直接 RuleBrain 模板
- 省掉 LLM 2.3s，TTS cache hit 後 E2E ~2.6s
- `status/chat/unknown` + 人臉事件仍走 LLM

## 延遲基線（2026-03-24 最終）

| 路徑 | E2E P50 | 說明 |
|------|:------:|------|
| stop/sit/stand（fast path, 不播 TTS） | **0.002s** | 只發動作，瞬間完成 |
| greet（fast path + cache） | **2.34s** | 模板回覆 + cache hit |
| Cloud LLM + cache hit | **3.97s** | 重複句第二次起 |
| Cloud LLM + edge-tts | **4.48s** | chat/status/come_here |
| Local LLM + edge-tts | **~6.0s** | Ollama 1.5B fallback |
| 全本地 Piper（保底） | **8.1s** | 所有都走 LLM + Piper |

### 動作 intent 不播 TTS
stop/sit/stand 只發動作指令，跳過 TTS。由 `_dispatch()` 和 `_rule_fallback()` 的 `ACTION_ONLY_SKILLS`/`ACTION_ONLY_INTENTS` 控制。

## 已知陷阱

- **stop/sit/stand 不播 TTS**：只發動作，這是設計決策不是 bug
- **VAD 斷句 2-10s** 是最大延遲瓶頸，不是 LLM
- **Whisper int8 on Jetson CPU 不可用**：必須用 `cuda` + `float16`，否則 silent fail
- **USB 喇叭 card number 可能漂移**：拔插後 `aplay -l` 確認
- **Megaphone cooldown**：4002 EXIT 後 sleep 0.5s（Megaphone 模式）
- **ASR warmup**：daemon thread 預熱 Whisper CUDA ~12s
- **Whisper 幻覺**：靜音/噪音段可能被誤解為假文字（mic_gain 過高會加劇）
- **USB 麥克風靈敏度低**：必須用 `mic_gain:=4.0`，gain 太高（>8）會使噪音放大到影響 ASR

## 測試

- `speech_processor/test/test_intent_classifier.py` — Intent 分類器單元測試
- `speech_processor/test/test_llm_contract.py` — LLM 契約單元測試
- `speech_processor/test/test_speech_test_observer.py` — Observer 單元測試
- `scripts/run_speech_test.sh` — 30 輪驗收測試
- `test_scripts/speech_30round.yaml` — 30 輪測試定義
