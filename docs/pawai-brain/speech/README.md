# 語音互動系統

> Status: current

> 中文語音對話：聽懂 → 理解意圖 → LLM 回應 → 說出來。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Chat 閉環 12 句通過** |
| 版本/決策 | **LLM locked**: `google/gemini-3-flash-preview` (OpenRouter) ／ **TTS locked**: `google/gemini-3.1-flash-tts-preview` (OpenRouter, Despina voice)；ASR 用 SenseVoice cloud；fallback chain 完整保留作離線/網路斷線備援 |
| 完成度 | 92% |
| 最後驗證 | 2026-05-04（Jetson smoke + B1 Plan D TTS rewrite，commits `29d46dd` / `54c68d0`） |
| 入口檔案 | `speech_processor/speech_processor/stt_intent_node.py` |
| 測試 | `python3 -m pytest speech_processor/test/ -v` |

## 啟動方式

```bash
# 一鍵啟動（推薦）
bash scripts/start_llm_e2e_tmux.sh

# 全離線模式
TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh
```

### 5/5 補充：tts_node 獨立啟動 + USB 喇叭 fallback

當 Go2 driver 沒在跑（例如本地 perception-only 測試），預設的 Megaphone DataChannel 路徑會 silent fail（沒聲音、沒錯誤）。改走本機 ALSA：

```bash
# Jetson 上獨立啟動 tts_node (跑 demo bridge / smoke test 用)
ros2 run speech_processor tts_node --ros-args \
  -p provider:=edge_tts \
  -p local_playback:=true \
  -p local_output_device:=plughw:0,0
# (plughw:N,0 — N 由 `aplay -l` 找 USB 喇叭 card index，重開機後可能漂移)
```

開啟 `local_playback:=true` 後 startup log 應顯示 `Playback: Local`（而不是 `Robot`），TTS 會送到 USB 喇叭。Megaphone 路徑仍保留作 demo 主線（Go2 driver 跑時自動恢復）。

## 核心流程

```
筆電麥克風 via PawAI Studio（Demo 主線）
    |  ← USB 麥克風已廢棄（Go2 風扇噪音導致 ~20% 辨識率）
    |  Studio WebSocket → Gateway(Jetson:8080) → ROS2
stt_intent_node（Energy VAD -> ASR 三級 fallback -> Intent 分類）
    |   ASR: SenseVoice cloud -> SenseVoice local (sherpa-onnx int8) -> Whisper small
    | /event/speech_intent_recognized
llm_bridge_node（**locked main**: OpenRouter Gemini 3 Flash Preview → DeepSeek V4 Flash → Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain 五級 fallback）
    |   output_mode=legacy → 發 /tts + sport /webrtc_req（既有行為）
    |   output_mode=brain  → 只發 /brain/chat_candidate（PawAI Brain MVS 模式）
    |   OpenRouter timeout default 4.0s / overall budget 5.0s（5/4 Jetson smoke 後 bump）
    | /tts（legacy 模式）or /brain/chat_candidate（brain 模式）
tts_node（**locked main**: OpenRouter Gemini 3.1 Flash TTS Preview Despina → edge-tts → Piper 三級 chain，5/4 落地）
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

### 為什麼鎖 Gemini 3 Flash + Gemini 3.1 Flash TTS（2026-05-05）

- **Audio tag 原生支援**：Gemini 3.1 Flash TTS 接收 `[excited]` / `[laughs]` / `[curious]` 等情緒標籤直接渲染，不需 strip — 個性表現最強，跟 Brain MVS persona 一致
- **延遲在可接受範圍**：~4.6s P50（Despina voice），對 demo 場景足夠；fallback `edge_tts` 更快（~1.5s）但個性弱
- **單一 provider 維護成本低**：LLM + TTS 都走 OpenRouter，credentials / rate limit / billing 統一管理
- **其他選項不再評估**：Qwen3.6 Plus / DeepSeek V4 / Kimi K2.6 等候選曾出現在 MOC，但 5/12 sprint 已收斂只跑 Gemini 主線；fallback 保留是工程現實，不是 A/B 候選

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
- ~~**LLM 回覆品質待改善**：max_tokens=120/25 字限制，回答過短、無個性、無多輪 memory~~（5/5 evening 處理：persona v3 + max_reply_chars=0 + 5-turn deque）
- **GPU 雲端不穩**：昨天斷線 2 次，Plan B 固定台詞為必備
- **`speech_processor` 用 ament_python，code 改完必須 colcon build**：sync source 不會自動更新 `install/`，stale install 是 5/5 evening 整晚截斷的真兇。改 ROS param 或 persona file 是 runtime 生效，不需 build；改 .py 必須 build。
- **架構碎片化警示（5/5）**：chat + tool calling 路徑跨 `llm_bridge_node` (1100 行) + `brain_node._on_chat_candidate` + ChatPanel + Studio gateway，多源 path 增加 hidden bug 風險（如本次 stale install + 截斷 cap）。已記為 backlog（LangGraph refactor 提案）

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

## 5/5 evening — LLM 個性化 + 對話記憶 + Brain MVS 全鏈接通

當日改動 unstaged，主要把「Voice → Brain → Studio E2E」打通，並把 LLM 的個性、字數、記憶、環境感知一次升級。

### Brain MVS 路徑啟用（先決條件）
- `start_full_demo_tmux.sh` 顯式加 `-p output_mode:=brain` — llm_bridge 改發 `/brain/chat_candidate`，不再直發 `/tts`
- `brain_node._on_speech_intent` 拿掉 self_introduce / show_status keyword bypass：
  - 動作型 self_introduce 6-step 在使用者近距離（D435 ROI）會被 SafetyLayer 擋成 `blocked_by_safety` → 沉默
  - LLM 的 persona 已能自然處理「你是誰 / 現在狀態」相關提問，不需要硬規則
  - MOTION 完整 self_introduce 仍可從 Studio button 觸發（不依賴語音 keyword）
- `interaction_executive/config/executive.yaml` 的 `chat_wait_ms` 1500 → **20000**（雲端 LLM 長回覆有時 ~10s，舊值 buffer 已失效）
- ChatPanel（`pawai-studio/frontend/components/chat/chat-panel.tsx`）加單行 skill trace bar — 顯示最近一筆 `brain:skill_result` 的 `selected_skill / status / detail`，無 drawer 無 timeline

### LLM 字數 + token 完全解除
- `max_reply_chars` 預設 40 → **0（uncapped）**；`_post_process_reply` 改成 `cap<=0` 跳過截斷
- `llm_max_tokens` 預設 80 → **2000**（啟動腳本顯式 4000）
- `llm_timeout` 預設 5 → **20s**
- `openrouter_request_timeout_s` 4 → **30s**、`openrouter_overall_budget_s` 5 → **35s**（短 timeout 是長故事被切的元兇之一）

### 對話記憶（5 turns / 10 messages）
- `llm_bridge_node` 加 `_convo_history: deque(maxlen=10)`，user/assistant pair
- 兩條 LLM 路徑（OpenRouter + vLLM/Ollama）都會把 history 塞進 `messages` array
- 只在「真聊天」（intent ∈ greet/chat/status）才寫入；stop/sit/stand 不污染 context
- 隨手修了一個老 bug：`_call_llm`（vLLM/Ollama）路徑原本還寫死 inline `SYSTEM_PROMPT`（12 字版），現在統一用 `self._system_prompt`（persona file）

### 台北時間 + wttr.in 天氣 context
- `_time_of_day_zh()`：早上 / 中午 / 下午 / 傍晚 / 晚上 / 深夜
- `_get_weather_text()`：打 `https://wttr.in/Taipei?format=%C+%t+濕度%h&lang=zh-tw`，10 分鐘 cache，2s timeout，失敗安靜
- 注入到每次 user_message 結尾：`[環境] 台北 早上 10:23，外面 多雲 22°C 濕度 65%`
- Persona 教 LLM「自然帶入，不要當天氣播報員」

### Persona v3：寵物優先個性（4777 bytes，from `tools/llm_eval/persona.txt`）
- **70% 小狗 / 20% 童心 / 10% 居家守護者**（Olaf 啟發但非模仿）
- 核心句：「最重要的不是完成任務，而是讓人感覺：家裡有一個小傢伙在」
- 個性原則拆「做這些 / 避免這些」兩欄；明令禁止客服腔、不要拍馬屁、不要每句都拋問題、不要主動列功能
- 守護模式 override：跌倒 / 陌生人 / 危險 → 立刻認真，不撒嬌不脫線
- 回答長度情境決定：閒聊 1-2 句 / 解釋 2-4 句 / 故事 / 安慰 / 共鳴 可長
- 加 「短期對話記憶 vs 長期人臉資料庫」明確區分 — 防止 LLM 用「我看不到你的臉」拒答短期記住的事
- `RuleBrain` `REPLY_TEMPLATES` 同步升人性版（`[excited] 嗨！我在這裡，今天過得怎麼樣？` 等）
- `tools/llm_eval/run_eval.py` alias `gemini` → `google/gemini-2.5-flash`（從 `gemini-3-flash-preview` 切 stable）

### Truncation Bug 真兇 — Stale `install/`
晚間反覆觀察到「reply 在中文逗號或無標點處截斷至 30-40 字」現象，diagnose 路徑：
1. ❌ 一開始懷疑 `gemini-3-flash-preview` preview model bug → 切 `gemini-2.5-flash` → 還截斷
2. ❌ 懷疑 Gemini 系列 structured output 共通問題 → 切 `deepseek/deepseek-v4-flash` → 還截斷
3. ❌ 懷疑 `temperature=0.2` 過低 → 改 0.7 → 還截斷
4. ❌ 懷疑 `openrouter_request_timeout_s=4.0` 短 → 改 30s → 還截斷
5. ❌ 懷疑 conversation history 內含截斷 sample 污染 → 清空 → 還截斷
6. ✅ 用 `curl` 直打 OpenRouter DeepSeek，**回完整 138 token 故事** → 確認 API 層正常
7. ✅ 對比 md5：WSL source 與 Jetson source 一致，但 **Jetson `install/` 目錄是 stale**！
   - Jetson source: `6f8edce4...`
   - Jetson install: `0f8952ca...` ← 含舊 cap=40 截斷邏輯
   - 整晚的 code 改動全部沒生效（只有 ROS param overrides + persona file 因為是 runtime 讀取所以有作用）
8. **Fix**：`colcon build --packages-select speech_processor --symlink-install`，未來改 source 仍需重 build，但 install layout 走 egg-link → build/，drift 會比較顯眼

### 待驗證
- 重 build 後第一次完整 smoke test 還沒跑，確認 reply 不再卡 40 char
- DeepSeek V4 Flash vs Gemini 2.5 Flash 在「真實長回覆」情境下的比較還沒做（之前的 A/B 都被 stale install 干擾，無效）

## 下一步

- [x] **OpenRouter 接入**（5/4 完成，B1 Plan D）：LLM/TTS 均走 OpenRouter，五級 fallback 全鏈通
- [x] **LLM prompt 智慧化**（5/5 evening）：persona v3 寵物個性 / max_reply_chars=0 解鎖 / 對話記憶 / 環境 context
- [ ] **Stale install/ rebuild 後完整 smoke**：3 句固定題目（睡前故事 / 介紹功能 / 累陪聊），確認長 reply 不被砍
- [ ] **長期持續 model A/B**：DeepSeek V4 Flash vs Gemini 2.5 Flash，看 persona 表現 / latency / cost
- [ ] **LangGraph 重構評估（backlog）**：目前 chat + tool calling 邏輯散落 `llm_bridge_node`（1100 行）+ `brain_node`，使用者建議搬到 `pawai-studio/backend/chat_agent/`，5/16 demo 後再做
- [ ] Plan B 固定台詞設計：至少 15 組問答（陳若恩）
- [ ] B1-4 Ollama 1.5B 斷網壓測（驗證 fallback 路徑）
- [ ] B1-5 Megaphone 16kHz 端到端（Despina 降採樣）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 語音 pipeline 分析報告 |
| archive/ | Jetson MVP 測試記錄（73K） |
