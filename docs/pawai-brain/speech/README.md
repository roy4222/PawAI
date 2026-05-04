# 語音互動系統

> Status: current

> 中文語音對話：聽懂 → 理解意圖 → LLM 回應 → 說出來。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Chat 閉環 12 句通過** |
| 版本/決策 | SenseVoice cloud + edge-tts + Cloud Qwen2.5-7B（全雲端主線）；本地 ASR（SenseVoice local / Whisper）作為降級 fallback，本地 LLM（Qwen2.5-1.5B）品質不足僅作形式備援 |
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
llm_bridge_node（OpenRouter Gemini 3 Flash → DeepSeek V4 Flash → Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain 五級 fallback）
    |   output_mode=legacy → 發 /tts + sport /webrtc_req（既有行為）
    |   output_mode=brain  → 只發 /brain/chat_candidate（PawAI Brain MVS 模式）
    |   OpenRouter timeout default 4.0s / overall budget 5.0s（5/4 Jetson smoke 後 bump）
    | /tts（legacy 模式）or /brain/chat_candidate（brain 模式）
tts_node（OpenRouter Gemini 3.1 Flash TTS Despina 主線 → edge-tts → Piper 三級 chain，5/4 落地）
    |   provider=openrouter_gemini → audio tag 原生渲染（[excited]/[laughs]/[curious]）
    |   audio_tag.py + tts_provider.py：provider.supports_audio_tags 守門 strip
    |   Stage 4 chain：main fail → fallback edge_tts (strip tag) → Piper (offline)
    |
USB 喇叭 local playback（Megaphone DataChannel 備用）
    |
echo gate 阻止 ASR 自激（total 1.5s）
```

**Intent fast path**：stop/greet 等高頻 intent 跳過 LLM，直接 RuleBrain（~0ms）。
**LLM timeout** Jetson default 4.0s（5/4 bump from 2.0s — Python urllib3+requests overhead 在 Jetson 把 1.5s curl 推到 2s 邊界，premature fallback）。
**TTS provider chain**（5/4 落地，B1 Plan D）：`openrouter_gemini` (Despina, audio tag native, ~4.6s) → `edge_tts` (strip tag, ~1.5s) → `piper` (offline, last-line)。Detail spec: `docs/pawai-brain/specs/2026-05-05-tts-rewrite-result.md`。

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

## PawAI Brain MVS 整合（2026-04-28 Phase 0+1+2 完成）

### `output_mode` 參數（Phase 0）

`llm_bridge_node` 新增 ROS2 param：

| 模式 | 行為 | 使用時機 |
|------|------|---------|
| `legacy`（預設）| 發 `/tts` + sport `/webrtc_req`（直接控狗，既有行為）| 舊 demo / 不啟動 brain_node 時 |
| `brain` | **只**發 `/brain/chat_candidate`，不發 `/tts`、不發 sport `/webrtc_req` | brain_node 啟動時，由 Executive 唯一控狗 |

`scripts/start_pawai_brain_tmux.sh` 一鍵啟動 brain-mode：
- `llm_bridge_node` 設 `output_mode:=brain`
- `event_action_bridge` 設 `enable_event_action_bridge:=false`
- 不啟動 `vision_perception/interaction_router`

### Source-level guard test

`speech_processor/test/test_tts_audio_api_only.py` — 確保 `tts_node` 只發 audio api_id（4001-4004 Megaphone enter/upload/exit/cleanup），不會誤發 sport 動作 api。

### Brain MVS 後 fallback chain（Phase A）

```
/event/speech_intent_recognized
    ↓
llm_bridge_node（output_mode=brain）
    ↓
   /brain/chat_candidate ──→ brain_node（1500ms 等待）
                                 ├ 命中 → SkillPlan(chat_reply)
                                 └ 逾時 → SkillPlan(say_canned)
                             ↓
                          /brain/proposal
                             ↓
                       interaction_executive_node
                             ↓
                            /tts → tts_node → Megaphone
```

詳細 schema 見 [`docs/contracts/interaction_contract.md`](../contracts/interaction_contract.md) v2.5。

## 下一步

- [ ] **OpenRouter 接入**（4/29 軌道 2）：把 `_call_cloud_llm` 升級成 4 級 fallback — OpenRouter Sonnet 4.6 → 本地 Qwen2.5-7B → Ollama → RuleBrain
- [ ] LLM prompt 智慧化：放寬字數 12→50+、加入 PawAI 個性、自我介紹（陳若恩）
- [ ] Plan B 固定台詞設計：至少 15 組問答（陳若恩）
- [ ] 多輪對話 memory（conversation history）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 語音 pipeline 分析報告 |
| archive/ | Jetson MVP 測試記錄（73K） |
