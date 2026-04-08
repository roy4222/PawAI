# 語音互動系統

> Status: current

> 中文語音對話：聽懂 → 理解意圖 → LLM 回應 → 說出來。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Chat 閉環 12 句通過** |
| 版本/決策 | SenseVoice cloud + edge-tts + Cloud Qwen2.5-7B（全雲端主線）；本地 ASR/LLM 不可用 |
| 完成度 | 90% |
| 最後驗證 | 2026-04-08（Studio Chat 閉環 12 句，E2E ~2s） |
| 入口檔案 | `speech_processor/speech_processor/stt_intent_node.py` |
| 測試 | `python3 -m pytest speech_processor/test/ -v` |

## 啟動方式

```bash
# 一鍵啟動（推薦）
bash scripts/start_llm_e2e_tmux.sh

# 全離線模式
TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh
```

## 核心流程

```
筆電麥克風 via PawAI Studio（Demo 主線）
    |  ← USB 麥克風已廢棄（Go2 風扇噪音導致 ~20% 辨識率）
    |  Studio WebSocket → Gateway(Jetson:8080) → ROS2
stt_intent_node（Energy VAD -> ASR 三級 fallback -> Intent 分類）
    |   ASR: SenseVoice cloud -> SenseVoice local (sherpa-onnx int8) -> Whisper small
    | /event/speech_intent_recognized
llm_bridge_node（Cloud Qwen2.5-7B -> Ollama 1.5B -> RuleBrain 三級 fallback）
    | /tts
tts_node（edge-tts 雲端主線 / Piper 本地 fallback）
    |
USB 喇叭 local playback（Megaphone DataChannel 備用）
    |
echo gate 阻止 ASR 自激（total 1.5s）
```

**Intent fast path**：stop/greet 等高頻 intent 跳過 LLM，直接 RuleBrain（~0ms）。
**LLM timeout > 2s** 自動 fallback。

## 輸入/輸出

| Topic | 方向 | 說明 |
|-------|:----:|------|
| `/event/speech_intent_recognized` | 輸出 | Intent 事件 JSON |
| `/state/interaction/speech` | 輸出 | 語音管線狀態 5Hz |
| `/state/tts_playing` | 輸出 | TTS 播放中 flag |
| `/tts` | 輸入 | 要說的文字 |
| `/asr_result` | 輸出 | 原始 ASR 文字 |

## Noisy Profile v1（2026-03-28）

Go2 伺服噪音環境下的 ASR 參數調校結果。

**啟動方式：**
```bash
ENABLE_ACTIONS=false bash scripts/start_full_demo_tmux.sh
```

**參數（寫在 start_full_demo_tmux.sh 的 launch arg）：**
- `mic_gain=8.0`（預設，v1 甜蜜點。gain 10/12 測試過，噪音放大更嚴重）
- `energy_vad.start_threshold=0.02`（原 0.015，避免 Go2 噪音誤觸發）
- `energy_vad.stop_threshold=0.015`
- `energy_vad.silence_duration_ms=1000`
- `energy_vad.min_speech_ms=500`

**Whisper 改善（寫在 stt_intent_node.py）：**
- `vad_filter=True`（啟用 silero VAD，過濾非語音段）
- `no_speech_threshold=0.6`（拒絕低信心結果）
- `log_prob_threshold=-1.0`
- 幻覺黑名單 6→22 pattern + 短文字（< 2 字）過濾

**安全門：** `ENABLE_ACTIONS` 環境變數
- `true`（預設）：llm_bridge 和 event_action_bridge 正常發布 `/webrtc_req`
- `false`：兩條動作路徑都關閉，Go2 不會因垃圾 intent 做危險動作

**A/B 測試結果（固定音檔 controlled test）：**

| 組別 | gain | 正確+部分 | 備註 |
|:----:|:----:|:---------:|------|
| v1 | 8.0 | **64%** | 甜蜜點 |
| v2 | 10.0 | 43% | 觸發暴增但品質下降 |
| v5 | 12.0 | 62% | 無改善，出現幻覺 |

**結論：** Whisper Small 在中文短句+機器噪音場景已到上限（64%），已被 SenseVoice 替換（92%）。

## ASR 三級 Fallback（2026-03-29 驗證通過）

```
sensevoice_cloud (RTX 8000, FunASR) → sensevoice_local (Jetson, sherpa-onnx int8) → whisper_local
```

**Cloud server**：`scripts/sensevoice_server.py`（FastAPI + FunASR SenseVoiceSmall，port 8001，需 SSH tunnel）
**Local model**：`~/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx`（228MB，CPU only，352MB RAM）

**等量三方 A/B 測試（各 25 筆，Go2 噪音環境）：**

| 指標 | SenseVoice Cloud | SenseVoice Local | Whisper Local |
|------|:---:|:---:|:---:|
| 正確+部分 | 92% | 92% | 52% |
| Intent 正確 | 96% | 92% | 56% |
| 幻覺/亂碼 | 0 | 0 | 8% |
| 延遲 | ~600ms | ~400ms | ~3000ms |
| 需要網路 | 是 | 否 | 否 |

**Fallback 行為**：cloud 斷 → `Connection refused` warn → 自動切 sensevoice_local（`degraded=True`）→ 如模型缺失再切 whisper_local。

## 已知問題

- **Go2 機身 USB 麥克風已廢棄**（4/8 決定）：Go2 風扇噪音極大，辨識率 ~20%。Demo 改用筆電麥克風 via Studio
- USB device index 重開機後漂移 → 用 `source scripts/device_detect.sh`
- MeloTTS 和 ElevenLabs 已棄用（3/26 決議）
- SenseVoice 對「現在請停止動作」辨識不穩（stop intent 約 60% 正確）
- **本地 ASR 不可用**：Whisper 上機後噪音干擾嚴重，長句辨識失敗
- **本地 LLM 不可用**：Qwen2.5-0.8B 智商極低，胡言亂語（4/8 會議確認）
- **LLM 回覆品質待改善**：max_tokens=120/25 字限制，回答過短、無個性、無多輪 memory
- **GPU 雲端不穩**：昨天斷線 2 次，Plan B 固定台詞為必備

## Plan B 固定台詞模式（4/8 會議新增）

GPU 斷線時的備案。ASR 判斷意圖後直接匹配固定回答，回應速度 ~0.x 秒。
- 需設計兩版 Demo 對話腳本：Plan A（雲端 AI）+ Plan B（固定台詞）
- Studio 顯示連線狀態燈號，團隊即時判斷是否切換
- 必要時出示錄影作為 AI 對話功能佐證
- **負責人**：陳若恩（見分工文件）

## 下一步

- [ ] LLM prompt 智慧化：放寬字數 12→50+、加入 PawAI 個性、自我介紹（陳若恩）
- [ ] Plan B 固定台詞設計：至少 15 組問答（陳若恩）
- [ ] 多輪對話 memory（conversation history）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 語音 pipeline 分析報告 |
| archive/ | Jetson MVP 測試記錄（73K） |
