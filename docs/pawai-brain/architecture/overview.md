# PawAI Brain × PawAI Studio — 整合架構與功能總覽

> **Status**: current
> **Date**: 2026-04-27
> **Scope**: 把 PawAI Brain（決策引擎）與 PawAI Studio（操作與觀測介面）視為一個整體，說明它們的目標、架構、模組職責、資料流、與 Demo 行為
> **演進路線**：Phase A（Brain MVS，5/16 demo）→ Phase B（**PawClaw** Embodied Brain V1，5/16 後）
> **依據文件**：
> - `docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md`（Brain MVS Spec — Phase A）
> - `docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md`（**PawClaw 演進** — Phase B）
> - `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-11-pawai-home-interaction-design.md`（PawAI 系統設計）
> - `docs/pawai-brain/plans/2026-04-27-pawai-brain-skill-first.md`（實作計畫 — Phase A）
>
> **Planned follow-up**（規劃中，尚未存在）：
> - `docs/pawai-brain/specs/2026-05-05-conversation-engine-langgraph-design.md`（Phase A.5 Conversation Engine LangGraph spec — 含 graph node I/O、tools 分層、5-phase 遷移、dependency spike 步驟）

---

## 1. 一句話定位

> **PawAI Brain 是會選技能的決策引擎；PawAI Studio 是讓人跟 Brain 對話、操作 Go2、觀測整個系統的 Conversational Brain Console。**
>
> 兩者合起來像「**一個懂 Go2 也能操作 Go2 的 ChatGPT**」 — 使用者在 Studio 的 Chat 頁打字、按按鈕或說話，背後是 Brain 在分辨聊天 / 動作 / 警示，安全層全程把關，所有決策過程在 Chat 流裡可視化。

**演進視角（PawClaw）**：本架構長期目標是「PawAI = PawClaw」 — 借鑑 [OpenClaw](https://github.com/openclaw/openclaw) 的 harness engineering pattern，讓 Brain 不只能演 demo 場景，還能「**懂自己身體**」：知道現在能不能走、地圖載入沒、AMCL 收斂沒、為什麼某個指令做不到。Phase A（MVS，5/16 demo 上場）先完成互動 Brain；Phase B（PawClaw V1）加上 **Capability Registry** + **BodyState** + **Nav Skill Pack** + **Workspace files**，演進為「embodied agent」。

---

## 2. 為什麼要分成 Brain + Studio？

| 模組 | 做什麼 | 不做什麼 |
|---|---|---|
| **PawAI Brain** | 接收多模態感知事件 → 選擇最合適的技能（Skill）→ 產出 SkillPlan 給 Executive 執行 | 不直接控制 Go2、不直接合成 TTS、不擁有 LLM 決策權 |
| **Interaction Executive** | 安全驗證 + 唯一動作出口 + 技能步驟分派（say/motion/nav） | 不做意圖判斷、不做技能編排 |
| **Safety Layer** | 關鍵字硬擋（停 / 緊急）+ 動作前置條件驗證 + 序列中可中斷 | 不依賴 LLM、不依賴 Studio 連線 |
| **PawAI Studio** | 跟 Brain 對話的主介面 + Skill Buttons 操作 + 即時觀測 Brain 決策過程 | 不擁有業務邏輯、不繞過 Brain 直接控狗 |

**設計原則**：
1. **Brain 提建議，Executive 才執行** — 確保系統永遠不會變成「LLM 控狗」
2. **單一動作出口** — sport `/webrtc_req` 只能由 Executive publish；不允許多源競爭
3. **Skill-first** — 所有能力（聊天 / 動作 / 導航 / 警示）都用統一的 SkillContract 表達
4. **Studio 不是另一條捷徑** — Studio Skill Buttons 仍走 Brain rule + Safety，與語音輸入路徑同等
5. **Chat 即觀測** — Brain 的每個決策都以 bubble 形式出現在 Chat 流，不需要 Foxglove 或 ROS2 終端機

---

## 3. 系統整體架構

```
┌─────────────────────────────────────────────────────────────────┐
│                         PawAI Studio                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Brain Skill Console (chat-panel)                          │ │
│  │  ├ Brain Status Strip   (mode / skill / step / safety)     │ │
│  │  ├ Conversation Stream  (8 種 bubble)                      │ │
│  │  ├ Skill Buttons        (self_introduce / stop / ...)      │ │
│  │  ├ Skill Trace Drawer   (proposals + world_state)          │ │
│  │  └ Text Input           (POST /api/text_input)             │ │
│  └────────────┬───────────────────────────────────────────────┘ │
│  Sidebar: Face / Speech / Gesture / Pose / Object（dev panels）  │
└────────────────┼─────────────────────────────────────────────────┘
                 │ WebSocket /ws/events  +  REST /api/*
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  studio_gateway (FastAPI + ROS2)                 │
│  訂閱 ROS2 → broadcast WebSocket：                                │
│    /state/pawai_brain  /brain/proposal  /brain/skill_result      │
│    /event/* + /tts                                               │
│  REST → 發 ROS2 topic：                                          │
│    POST /api/skill_request → /brain/skill_request                │
│    POST /api/text_input    → /brain/text_input                   │
└────────────────┼─────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   感知模組（Jetson 邊緣端）                       │
│  人臉 (YuNet+SFace)  語音 (SenseVoice/Whisper)                   │
│  手勢 (MediaPipe)     姿勢 (MediaPipe)    物體 (YOLO26n+TRT)      │
│  各自發布 /event/* 與 /state/perception/*                         │
└────────────────┼─────────────────────────────────────────────────┘
                 │ 多模態事件
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                          PawAI Brain                             │
│  brain_node（純規則 router，無 LLM 直連）                         │
│   1. world_state.update(event)                                   │
│   2. SafetyLayer.hard_rule → SkillPlan(stop_move) (immediate)    │
│   3. critical_alert_rule → SkillPlan(alert)                      │
│   4. active_sequence guard（只 SAFETY/ALERT 可中斷）              │
│   5. 1 秒 dedup                                                  │
│   6. rule table → SkillPlan                                      │
│   7. speech 未命中 → 等 chat_wait_ms /brain/chat_candidate         │
│      命中 → chat_reply / 逾時 → say_canned                       │
└────────────────┼─────────────────────────────────────────────────┘
                 │ /brain/proposal (SkillPlan)
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Interaction Executive                           │
│  1. SafetyLayer.validate(plan, world_snapshot)                   │
│  2. SAFETY/ALERT 進來 → 清 queue、push_front                      │
│  3. SEQUENCE → enqueue 多步                                      │
│  4. queue worker 逐步 dispatch:                                  │
│       SAY    → /tts                                              │
│       MOTION → /webrtc_req (sport, 含 banned_api 守衛)           │
│       NAV    → nav_capability action client                      │
│  5. 每 plan/step 發 /brain/skill_result                          │
│  6. 發 /state/pawai_brain (TRANSIENT_LOCAL, 2 Hz)                │
└────────────────┼─────────────────────────────────────────────────┘
                 │
                 ▼
              Go2 Pro (sport API + Megaphone audio) + nav stack
```

**並行存在但不參與 Brain 路徑**：
- `tts_node` — 仍是 Megaphone audio `/webrtc_req`（api_id 4001/4002/4003/4004）唯一發送者
- `llm_bridge` — 在 brain mode 下只發 `/brain/chat_candidate`，不再直接控狗

---

## 3.5 Conversation Engine Layer（5/5 night decision）

### 動機

`llm_bridge_node.py` 已長到 1100 行，責任失控（ROS adapter + persona load + OpenRouter chain + history + weather context + JSON parse + emoji strip + truncation guard + RuleBrain fallback + legacy /tts publish）。5/5 night 反覆出現 reply 被截斷在中文逗號處，最後追到根因是 stale `install/` 含舊 `cap=40` 截斷邏輯（colcon build 沒同步）。**Hidden bug 之所以能藏這麼久，是因為 chat 路徑跨太多檔案 + 跨太多責任。**

決議：把 chat orchestration 抽到獨立 layer。新增 `pawai_brain` ROS2 package，內部用 LangGraph 做 stateful conversation graph。`llm_bridge_node` 退回 legacy engine 角色，feature flag 切換新舊。

### 層級插入示意

```
感知模組 → /event/speech_intent_recognized
                         ↓
             Conversation Engine Router
             ┌──────────────────────────────────────┐
             │ ROS param:                           │
             │   conversation_engine                │
             │     legacy   = llm_bridge_node       │
             │     langgraph = pawai_brain/         │
             │                  conversation_graph_ │
             │                  node                │
             │   conversation_shadow_engine         │
             │     none | legacy | langgraph        │
             │     （非 primary，不發 chat_candidate）│
             └──────────────────────────────────────┘
                         ↓ /brain/chat_candidate
             PawAI Brain（engine-agnostic）
                         ↓ /brain/proposal
             Interaction Executive
                         ↓
                    Go2 + nav stack
```

### 設計原則

- **LangGraph 管「想 / 怎麼說 / 想用哪個 skill」** — persona、短期記憶、環境 context、LLM call、JSON validate、截斷 retry、skill proposal 全部進 graph
- **Brain 管「能不能做」** — safety、cooldown、OK confirm、active skill allowlist、序列仲裁
- **Executive 管「真的怎麼做」** — 單一動作出口不變
- **Studio 不當腦** — 只看、顯示、手動觸發 skill；trace topic 進 dev panel，不污染 ChatPanel 主聊天
- **Brain contract 不變** — `brain_node` 不知道 `chat_candidate` 來自 `legacy` 還是 `langgraph`，這是 feature flag 切換能成立的契約基礎

### Feature Flag 矩陣

兩個獨立 enum 參數：

- `conversation_engine:=legacy|langgraph` — primary engine，**唯一** publish `/brain/chat_candidate`
- `conversation_shadow_engine:=none|legacy|langgraph` — optional shadow engine，跟 primary 對齊輸入但只發 `/brain/conversation_trace_shadow`，**不可** publish `chat_candidate`

合法組合：

| primary | shadow | 用途 |
|---|---|---|
| `legacy` | `none` | demo 安全網（100% 走舊路徑） |
| `langgraph` | `none` | 目標狀態（100% 走新 graph） |
| `langgraph` | `legacy` | 新 graph 主線，legacy 背景做 diff 觀察 |
| `legacy` | `langgraph` | 反向 shadow（langgraph 開發初期穩定性觀察） |

不合法：`primary == shadow`（無意義）、兩條都 publish chat_candidate（Brain 雙重觸發）。

### 新 ROS2 package 預告

```
pawai_brain/
├── pawai_brain/
│   ├── conversation_graph_node.py        # ROS2 node wrapper
│   ├── graph.py                          # LangGraph 組裝
│   ├── state.py                          # ConversationState TypedDict
│   ├── nodes/                            # 9-10 個 graph 節點
│   │   ├── safety_gate.py
│   │   ├── context_builder.py
│   │   ├── memory_builder.py
│   │   ├── llm_decision.py
│   │   ├── json_validator.py
│   │   ├── response_repair.py
│   │   ├── skill_policy_gate.py
│   │   ├── output_builder.py
│   │   └── trace_emitter.py
│   ├── prompts/
│   │   └── pawai_persona_v4.txt
│   └── tools/
│       ├── read_status.py / read_perception.py  (read-only)
│       ├── request_skill.py                     (proposal-only)
│       └── say.py
└── launch/pawai_conversation_graph.launch.py
```

完整 spec 明天另寫，本節先建立 contract 與邊界。

### Demo 前落地限制（暫時性策略，不是長期架構不變式）

- **legacy path 不刪**，至少保留到 5/16 demo 後。
- LangGraph dependency 失敗（import 炸 / 模型 timeout 異常）→ 立刻 launch arg 切回 `conversation_engine:=legacy`，不阻塞 demo。
- dependency spike 通過才正式進 Phase 2 實作（不是先寫 code，是先 spike 環境）。
- **Spike 第一波** 只裝 `langgraph + langchain-core`，先包現有 OpenRouter `requests` client。**這是 spike 策略**，不是設計原則 — 後續視情況再評估是否加 LangChain provider adapter。

### 與 Phase B (PawClaw) 的關係

Conversation Engine 是 **Phase A.5 過渡**，不是 Phase B 啟動。Phase B 的 CapabilityRegistry / BodyState / Nav Skill Pack / Workspace files 仍在 5/16 demo 後啟動。Conversation Engine 為 Phase B 的 skill_proposal flow 鋪好 contract：當 Phase B 引入「為什麼某 skill 不能做」的 capability 解釋，graph 的 `skill_policy_gate` 與 `trace_emitter` 已經是天然落地點。

---

## 4. 目標

### 4.1 產品目標（5/16 Demo）

讓 Demo 觀眾在 3 分鐘內看到一隻**會分辨聊天 vs 動作 vs 警示**的居家互動機器狗：

- 「你好」→ 自然回覆（聊天）
- 「介紹你自己」→ 10 步序列（5 段台詞 + 5 個動作交替）
- 「停！」→ 任何進行中的動作立刻中斷（safety）
- 對 PawAI 揮手 → 機器狗回應（手勢觸發技能）
- 熟人入鏡 → 個人化問候（人臉觸發技能）
- 陌生人持續 3 秒 → 警示提醒（守護輔助）
- 偵測到跌倒 → 安全停下並語音提醒

整個過程在 Studio Chat 頁可視化，不需要其他工具就能說明系統如何運作。

### 4.2 工程目標

| 目標 | 衡量方式 |
|---|---|
| 單一動作出口 | grep 確認除 `tts_node`（audio）與 `interaction_executive_node`（sport）外，無其他 `/webrtc_req` publisher |
| 安全事件可硬中斷 | 「停」關鍵字平均響應 < 200ms；序列中按 stop 必中斷 |
| 7 場景通過率 ≥ 90% | Demo dry run 三輪 |
| Studio 全程可觀測 | Brain Status Strip + 8 種 bubble + Trace Drawer |
| 無 LLM 直接控狗風險 | `/brain/chat_candidate.selected_skill` 是 diagnostic-only，Brain MVS 不採用 |
| 降級鏈穩 | LLM 掛 → Brain say_canned 仍能回覆；Brain 掛 → Safety hard rule 仍能停 |

### 4.3 教學 / 答辯目標

- **Embodied interaction system**：感知 / 決策 / 安全 / 執行 / 觀測形成完整迴圈
- **Harness-oriented design**：能力受 SKILL_REGISTRY 約束、Safety 永遠可用、Plan B 備援
- **Privacy-by-design**：感知模組全本地（YuNet / SFace / MediaPipe / YOLO 都跑 Jetson）
- **Skill-first abstraction**：把所有功能統一成 Skill，未來 LLM function calling 直接餵 SKILL_REGISTRY 即可升級

---

## 5. 功能清單

### 5.1 PawAI Brain 功能

| 功能 | 細節 | 對應檔案（MVS） |
|---|---|---|
| **多源事件聚合** | 訂閱 speech / face / gesture / pose / object / chat_candidate / text_input / skill_request | `brain_node.py` |
| **規則 router** | 6 條 rule（safety_keyword / gesture_ack / known_face / unknown_face_3s / pose_fallen_2s / chat_fallback）；`self_introduce_keyword` 已於 5/5 night 移除（含 motion 在使用者近距離會被 SafetyLayer 擋成 sleep；改由 LLM persona 自然處理「你是誰 / 自我介紹」），完整 motion 版 self_introduce 仍可從 Studio button 觸發 | `brain_node.py` |
| **Safety hard rule** | 5 個關鍵字（停 / stop / 煞車 / 暫停 / 緊急）→ 立刻發 stop_move 提案 | `safety_layer.py` |
| **Pre-action validate** | obstacle / emergency / banned_api / unknown_motion 守衛 | `safety_layer.py` |
| **WorldState 聚合** | tts_playing / reactive_stop_obstacle / nav_safe / fallen | `world_state.py` |
| **SkillContract registry** | 27 entries（Active 17 / Hidden 5 / Disabled 4 / Retired 1）+ 4 demo metadata fields per entry (display_name / demo_status_baseline / demo_value / demo_reason) | `interaction_executive/skill_contract.py` |
| **DemoGuide registry**     | 6 entries（face / speech / gesture / pose / object / navigation）— pseudo-skills for self-demonstration | `pawai_brain/config/demo_guides.yaml` |
| **CapabilityContext**      | LLM-facing merged view (27 + 6 = 33 entries) with `effective_status` per turn; flows via `pawai_brain` only — `/brain/chat_candidate` schema unchanged | `pawai_brain/pawai_brain/capability/registry.py` |
| **Skill template 解析** | `text_template`、`name_template` 在 plan 展開時用 args 替換 | `skill_contract.py:build_plan` |
| **Sequence 編排** | self_introduce 10 步交替 say + motion；序列中只 SAFETY/ALERT 可中斷 | `skill_contract.py:META_SKILLS` |
| **Per-skill cooldown** | greet_known_person 每名 20s、stranger_alert 30s、fallen_alert 15s | `brain_node.py:_in_cooldown` |
| **1 秒 dedup** | 同 source + 同 key 的事件 1 秒內忽略 | `brain_node.py:_check_dedup` |
| **Chat candidate 等待** | speech 未命中規則 → buffer + 等 Conversation Engine；`chat_wait_ms` 預設 1500ms；cloud LLM / LangGraph 測試期間可由 launch arg 暫時調高到 8000-20000ms；逾時用 say_canned | `brain_node.py` |
| **State publisher** | `/state/pawai_brain` (TRANSIENT_LOCAL, 2 Hz)，含 mode / active_plan / safety_flags / cooldowns / last_plans ring buffer | `brain_node.py:_publish_brain_state` |

> **engine-agnostic**：`brain_node` 不知道 `/brain/chat_candidate` 來自 legacy `llm_bridge_node` 還是 LangGraph `conversation_graph_node`。Engine identity 不影響 Brain 仲裁邏輯，這是 Conversation Engine feature flag 切換能成立的契約基礎（見 §3.5）。

### 5.2 Interaction Executive 功能

| 功能 | 細節 | 對應檔案 |
|---|---|---|
| **訂 /brain/proposal** | 唯一接受 plan 的 node | `interaction_executive_node.py` |
| **Pre-dispatch validate** | 失敗發 BLOCKED_BY_SAFETY 給 Brain + Studio | 同上 |
| **Skill Queue** | deque + push / push_front / clear 含 ABORTED 通知 | `skill_queue.py` |
| **Step 分派** | SAY → `/tts`；MOTION → `/webrtc_req`（含 banned_api 二次守衛）；NAV → action client | 同上 |
| **TTS-bound 等候** | SAY step 等 `/state/tts_playing` 由 true → false 才下一步 | 同上 |
| **Lifecycle 事件** | 8 種 status：accepted / started / step_started / step_success / step_failed / completed / aborted / blocked_by_safety | `skill_contract.py:SkillResultStatus` |
| **單一 sport 出口** | 所有非 audio 的 `/webrtc_req` 只能由本 node 發 | 設計約束 |

### 5.3 PawAI Studio — Brain Skill Console 功能

| 功能 | 細節 | 對應檔案 |
|---|---|---|
| **Brain Status Strip** | 即時顯示 mode（idle/chat/skill/sequence/alert/safety_stop）+ active skill + step 進度 + 4 個 safety flag | `chat/brain-status-strip.tsx` |
| **8 種 Chat Bubble** | user / voice / say / brain_plan / skill_step / safety / alert / skill_result | `chat/bubble-*.tsx` + `chat-panel.tsx` |
| **Skill Buttons** | stop_move / self_introduce / wave_hello / wiggle / stretch / nav_demo_point / greet_known_person(Studio) / fallen_alert(有人) / approach_person(Studio)；高風險 skill 保留 OK 二次確認流程 | `chat/brain/skill-buttons.tsx` |
| **Skill Trace Drawer** | 可摺疊 drawer，列最近 10 筆 proposal + 當前 world_state flags | `chat/skill-trace-drawer.tsx` |
| **文字輸入** | `POST /api/text_input` → 走 Brain 同 pipeline（含 chat_fallback） | `chat-panel.tsx` |
| **語音輸入** | 沿用既有 ASR（SenseVoice cloud / Whisper local），事件流回 `/event/speech_intent_recognized` | speech_processor 既有 |
| **Sidebar dev panels** | face / speech / gesture / pose / object / live — 工程師除錯用 | 既有 |
| **離線開發** | `mock_server.py` 提供 `/mock/scenario/self_introduce` 等假事件，前端可離線 demo | `backend/mock_server.py` |

### 5.4 Studio Gateway（ROS2 ↔ WebSocket bridge）功能

| 方向 | Topic / Endpoint | 對應 Studio UI |
|---|---|---|
| ROS2 → WS | `/state/pawai_brain` | Brain Status Strip |
| ROS2 → WS | `/brain/proposal` | brain_plan / alert bubble + Trace Drawer |
| ROS2 → WS | `/brain/skill_result` | skill_step / safety / skill_result bubble |
| ROS2 → WS | `/event/*` | dev sidebar panels |
| ROS2 → WS | `/tts` | say bubble（鏡像 PawAI 講出來的話） |
| WS → REST | `POST /api/skill_request` → `/brain/skill_request` | Skill Buttons |
| WS → REST | `POST /api/text_input` → `/brain/text_input` | Chat 文字輸入 |

---

## 6. 互動流程範例

### 範例 A：自我介紹（10 步序列，Studio button 觸發）

> 5/5 night 起，`self_introduce_keyword` 規則已移除。語音「介紹你自己」走 LLM chat path（chat_reply 純 SAY，無 motion，避開 SafetyLayer depth gate）。**完整 10 步 motion 版**僅由 Studio Skill Button 觸發。

```
[studio]          Skill Button: self_introduce  → POST /api/skill_request
                       │
                       ▼ /brain/skill_request
[brain]           SkillContract 查表 → 出 SkillPlan(self_introduce)，source="studio_button"
                       │
                       ▼ /brain/proposal
[executive]       safety validate ✓ → enqueue 10 步 → STARTED
                       │
                       ▼ step 0
[skill_step]      1/10 say "我是 PawAI..."
[say]             我是 PawAI，你的居家互動機器狗  ← /tts → tts_node → Megaphone
                       │ TTS 播完，等 tts_playing flip
                       ▼ step 1
[skill_step]      2/10 motion hello                  ← /webrtc_req(api_id=1016)
                       ...（7 步省略）...
                       ▼ step 9
[skill_step]      10/10 motion balance_stand         ← /webrtc_req(api_id=1002)
[skill_result]    completed · self_introduce
```

整段約 30-40 秒；過程中 Brain Status Strip 會跑 `sequence · self_introduce · 1/10 → 10/10`。

### 範例 B：序列中安全中斷

```
（self_introduce 跑到第 4 步時）
[user]            停！
                       │
                       ▼ /event/speech_intent_recognized
[brain]           SafetyLayer.hard_rule(transcript="停！") 立刻 hit
                  → 出 SkillPlan(stop_move, priority=SAFETY)
                       │
                       ▼ /brain/proposal
[executive]       SAFETY 進來 → clear queue（self_introduce ABORTED）
                  → push_front(stop_move)
[safety]          safety_stop · queue cleared
[skill_step]      1/1 motion stop_move               ← /webrtc_req(api_id=1003)
[skill_result]    completed · stop_move
```

平均響應 < 200ms（Brain hard_rule 不過 LLM）。

### 範例 C：陌生人警示（守護輔助）

```
（鏡頭看到沒註冊的臉）
                       │  /event/face_identity {identity: "unknown"} 持續 3 秒
                       ▼
[brain]           AlertTimerRule 累計 3.0s → 出 SkillPlan(stranger_alert, priority=ALERT)
                       │
                       ▼
[alert]           stranger_alert · rule:unknown_face_3s   ← 紅底 bubble
[skill_step]      1/1 say "偵測到不認識的人，請注意"
[say]             偵測到不認識的人，請注意
[skill_result]    completed · stranger_alert
```

注意：**MVS 階段不做動作**（不揮手、不站立），只用語音警示，把不確定的安全動作風險降到最低；30 秒內同人不重複觸發（cooldown）。

### 範例 D：Studio 文字輸入「今天天氣」（chat fallback）

```
[user]            今天天氣  （Chat 輸入框打字 → /api/text_input）
                       │
                       ▼  /brain/text_input → Brain repackage 為 synthetic speech
[brain]           rule 都不命中 → buffer + 排定 chat_wait_ms 逾時
                  ｜
                  ｜（同時 Conversation Engine 也收到 /event/speech_intent_recognized）
                  ｜
[brain]           chat_wait_ms 內收到 /brain/chat_candidate(reply_text="今天很適合散步")
                  → 出 SkillPlan(chat_reply, text="今天很適合散步")
[brain_plan]      chat_reply · llm_bridge
[skill_step]      1/1 say "今天很適合散步"
[say]             今天很適合散步
[skill_result]    completed
```

LLM 掛掉時：`chat_wait_ms` 逾時 → 出 say_canned("我聽不太懂") → 仍有回應，不卡死。

---

## 7. 與 4/11 spec（PawAI 系統設計）的對應

本架構是 4/11 spec 三層 Brain（Safety / Policy / Expression）的具體實作：

| 4/11 spec 概念 | 本架構落地 |
|---|---|
| Safety Layer（最高優先 deterministic guard） | `safety_layer.py` 的 hard_rule + validate；priority_class=SAFETY |
| Policy Layer（互動上下文 + skill selection） | `brain_node.py` 的 rule table + 仲裁演算法 |
| Expression Layer（reply text + tone + style） | SAY executor + Studio bubble + skill description |
| PawAI Skills | SKILL_REGISTRY 27 entries（Active 17 / Hidden 5 / Disabled 4 / Retired 1），bucket / static_enabled / enabled_when 三層開關 |
| Skill Contract（preconditions / expected_outcome / fallback） | `SkillContract` dataclass + `safety_requirements` + `fallback_skill` |
| Skill Queue + Action Sequencing | `skill_queue.py` + META_SKILLS["self_introduce"] |
| self_introduce meta skill | `META_SKILLS["self_introduce"]`（5 say + 5 motion 交替，10 步） |
| Guardian State Artifact | `/state/pawai_brain` JSON schema |
| Graceful Degradation 四級 | Cloud LLM → Local LLM → say_canned 規則 fallback → Safety-only |
| Brain ≠ Executive | brain_node 與 interaction_executive_node 為**兩個獨立 ROS2 process** |

---

## 8. 不做的事（明確邊界）

| 不做 | 原因 |
|---|---|
| LLM 直接控制 Go2 動作 | 違反 Safety 設計；Conversation Engine 只能透過 `reply_text` + skill proposal 影響 |
| **`brain_node` 直接呼叫 LLM** | `brain_node` 仍是純規則 router；LLM call 集中在 Conversation Engine 層（legacy `llm_bridge_node` 或 langgraph `conversation_graph_node`）。Brain 永遠只消費 `/brain/chat_candidate`，不發 HTTP 出去（見 §3.5） |
| 通用 autonomous agent | Go2 必要性會弱化；Demo 重點是 embodied interaction 不是 LLM 智能 |
| PawAI Memory（跨 session 記憶） | MVS scope 控制；4/13 文件 + 5/16 demo 時程吃緊 |
| nav_capability 完整整合（go_to_named_place） | nav KPI 未通過；registry 預留 enabled=false |
| 抄 4 個 PawAI repo PR（#38/#40/#41/#42） | PR 仍在改進中；Brain MVS 穩定後再抄（Phase 3 hooks） |
| 多源同時 publish /webrtc_req（除 tts_node audio） | 已踩過 nav_capability「多控制源互搶」事故；MVS 強制單一出口 |
| Studio 直接發 /brain/proposal 繞過 Brain | Skill Buttons 仍走 /brain/skill_request → Brain rule + safety；無捷徑 |

---

## 9. Demo 流程（5/16 省夜，3 分鐘）

| 時段 | 內容 | Studio 對應顯示 |
|---|---|---|
| 0:00 - 0:10 | 開場：PawAI 安靜待命 | Brain Status Strip：idle |
| 0:10 - 0:45 | **Wow Moment**：主持人「介紹你自己」→ self_introduce 10 步 | Conversation Stream 流出 brain_plan + 10 個 skill_step + 5 個 say bubble + completed |
| 0:45 - 1:30 | 互動 A：揮手 → wave_hello | brain_plan(rule:gesture_ack) + skill_step + say "嗨！" |
| 1:30 - 2:00 | 互動 B：熟人入鏡 → greet_known_person("alice") | brain_plan(rule:known_face) + say "歡迎回來，alice" + motion hello |
| 2:00 - 2:30 | 互動 C：自由對話 → chat_reply | user → brain_plan(chat_reply, llm_bridge) → say |
| 2:30 - 2:50 | 守護：陌生人持續 3s → stranger_alert | 紅底 alert bubble + say "偵測到不認識的人，請注意" |
| 2:50 - 3:00 | 收尾：說「停」→ safety_stop | safety bubble · queue cleared · stop_move |

整段 **不需要切換工具** — Studio Chat 頁就是 demo 主畫面。

---

## 10. 部署拓樸

```
┌──────────────────────────────┐         ┌─────────────────────────┐
│  Cloud (RTX 8000 ×5, 48GB)   │         │  開發機 (Win/Mac/Linux) │
│                              │         │                         │
│  vLLM Qwen2.5-7B-Instruct    │         │  Browser → Studio /chat │
│  SenseVoice ASR FastAPI      │         │                         │
│  edge-tts proxy              │         │                         │
└──────────────┬───────────────┘         └────────────┬────────────┘
               │ SSH tunnel                            │ HTTP/WS
               ▼                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Jetson Orin Nano 8GB（邊緣 runtime）                 │
│                                                                 │
│  ROS2 Humble nodes:                                             │
│   face_identity_node / vision_perception_node / object_node /   │
│   stt_intent_node / llm_bridge_node (output_mode=brain) /       │
│   tts_node /                                                    │
│   ★ brain_node ★ interaction_executive_node                     │
│                                                                 │
│  pawai-studio gateway (FastAPI + ROS2)                          │
│  pawai-studio frontend (Next.js, optional 走筆電 dev server)    │
└──────────────┬──────────────────────────────────────────────────┘
               │ WebRTC DataChannel
               ▼
        ┌──────────────┐
        │ Unitree Go2  │
        │ - sport API  │
        │ - Megaphone  │
        └──────────────┘
```

- **Cloud / 開發機 / Jetson / Go2** 四端透過明確介面（HTTP / WS / WebRTC DataChannel / ROS2）解耦，任一端故障都有對應 fallback
- Studio 前端可在筆電或 Jetson 任一處跑（透過 `pawai-studio/start.sh`）
- Demo 時建議前端跑筆電（投影 / 大螢幕展示），gateway + ROS2 + Brain 全在 Jetson

---

## 11. 關鍵 Topic 速查

| Topic | Type | 方向 | 用途 |
|---|---|---|---|
| `/event/speech_intent_recognized` | String JSON | stt → brain + llm_bridge | 語音意圖事件 |
| `/event/face_identity` | String JSON | face → brain | 人臉識別事件 |
| `/event/gesture_detected` | String JSON | vision → brain | 手勢事件 |
| `/event/pose_detected` | String JSON | vision → brain | 姿勢事件 |
| `/event/object_detected` | String JSON | object → brain | 物體事件（MVS 不用） |
| `/state/tts_playing` | Bool | tts_node → brain world_state + executive | TTS 播放中 flag |
| `/state/reactive_stop/status` | String JSON | reactive_stop → brain world_state | 障礙 / 緊急 |
| `/state/nav/safety` | String JSON | nav → brain world_state | 導航安全 |
| **`/brain/chat_candidate`** | String JSON | conversation engine → brain | LLM 回覆（primary engine 唯一發送，見 §3.5） |
| **`/brain/conversation_trace`** | String JSON | conversation engine → gateway | LangGraph 各階段 trace（input / safety / context / memory / llm / validate / repair / skill_gate / output）；給 Studio dev trace / Skill Trace Drawer 顯示，**不進 ChatPanel 主聊天** |
| `/brain/conversation_trace_shadow` | String JSON | shadow engine → debug | Shadow engine（非 primary）發；diff 比對用，不進 Brain |
| **`/brain/text_input`** | String JSON | gateway → brain | Studio 文字輸入 |
| **`/brain/skill_request`** | String JSON | gateway → brain | Studio 按鈕請求 |
| **`/brain/proposal`** | String JSON | brain → executive (+gateway) | SkillPlan |
| **`/brain/skill_result`** | String JSON | executive → brain + gateway | 8 種 lifecycle status |
| **`/state/pawai_brain`** | String JSON (TRANSIENT_LOCAL) | brain → gateway | Brain 狀態快照（2 Hz） |
| `/tts` | String | executive → tts_node | SAY step 文字（MVS runtime 唯一發送者：executive） |
| `/webrtc_req` (sport, api_id ≠ 4001-4004) | WebRtcReq | executive → go2 driver | MOTION step（MVS 唯一發送者：executive） |
| `/webrtc_req` (audio, api_id ∈ {4001,4002,4003,4004}) | WebRtcReq | tts_node → go2 driver | Megaphone audio（不變） |

加粗為 Brain MVS 主線新增 topic；`/brain/conversation_trace` 為 Conversation Engine 觀測 topic。`/brain/conversation_trace_shadow` 為 optional debug，不計入主線。

---

## 12. 降級鏈（Resilience）

```
正常：
  Brain rule + LLM candidate → Executive validate → Go2 動作 + TTS
  
LLM 掛（cloud 斷線 / SenseVoice 斷線）：
  Brain rule 仍能跑（safety / sequence / gesture / face / pose 全部不依賴 LLM）
  Speech 未命中規則 → chat_wait_ms 逾時 → say_canned("我聽不太懂")
  
Brain 掛（brain_node crash）：
  Executive 不再收到 proposal → 待機
  Go2 不會亂動（單一出口斷掉就是真的斷掉，不會有殘留命令）
  
Executive 掛（dispatcher crash）：
  Brain 仍會 publish proposal，但無人接
  Studio 看得到 brain_plan bubble 但沒有 skill_step／skill_result follow-up
  視覺上明確顯示問題位置
  
Studio 掛：
  Brain + Executive 完全不受影響；Demo 可改用 ros2 topic pub 手動觸發
  
Jetson 斷電：
  Go2 自己站穩（韌體層）
  
網路斷：
  本地 face / vision / object / 部分語音（whisper_local）仍可跑
  Brain 規則路徑全可用
```

---

## 13. 答辯論述角度

| 面向 | 一句話 |
|---|---|
| 系統架構 | 三層 Brain（Safety / Policy / Expression）+ 單一動作出口 + Skill 統一抽象 |
| Agent 設計 | Harness-oriented：能力被 SKILL_REGISTRY 約束、Safety 永遠可用、無 LLM 直接控狗 |
| HRI | 多模態感知 × Skill 編排 × Studio 可視化 = 端到端可解釋 embodied interaction |
| Edge-Cloud 取捨 | 感知與決策本地（Jetson）、LLM 雲端（RTX 8000），任一端有 fallback |
| Robotics 產品化 | Skill Contract + pre-action validation + lifecycle SkillResult + 觀測 topic |
| Reliability | 4 級降級鏈、output_mode feature flag 漸進切換、source-level test 守護 sport API |
| Privacy-by-design | 人臉 / 手勢 / 姿勢 / 物體全部本地，不離機 |
| Security mindset | Safety hard rule + banned_api gate + LLM selected_skill diagnostic-only |
| Observability | Studio Brain Skill Console 把整個決策過程攤開在 Chat 流，無需 Foxglove |

---

## 14. 文件索引

| 主題 | 文件 |
|---|---|
| **本文件**（系統整合總覽） | `docs/pawai-brain/architecture/overview.md` |
| **Phase A**：Brain MVS 設計 spec | `docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md` |
| **Phase A**：Brain MVS 實作 plan（34 tasks） | `docs/pawai-brain/plans/2026-04-27-pawai-brain-skill-first.md` |
| **Phase A.5**：Conversation Engine LangGraph 演進 spec | `docs/pawai-brain/specs/2026-05-05-conversation-engine-langgraph-design.md`（待寫） |
| **Phase B**：PawClaw Embodied Brain V1 演進 spec | `docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md` |
| PawAI 系統定位（4/11 三層 Brain 概念源） | `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-11-pawai-home-interaction-design.md` |
| 專案方向、Demo、分工 | `docs/mission/README.md` |
| ROS2 介面契約（v2.5 Phase A / v2.6 Phase B 將更新） | `docs/contracts/interaction_contract.md` |
| PawAI Studio 設計 | `docs/pawai-brain/studio/README.md` |
| 各感知模組 | `docs/{語音功能,人臉辨識,手勢辨識,姿勢辨識,辨識物體}/README.md` |

---

## 15. PawClaw 演進預告（Phase B 摘要）

5/16 demo 後啟動，把 Brain 從「demo script player」升級為「embodied agent」。三個核心新增：

| 新增 | 對應 OpenClaw 概念 | PawAI 落地 |
|---|---|---|
| **CapabilityRegistry** — `SkillContract.enabled_when: list[CapabilityPredicate]` | OpenClaw allow/deny + tool registry | 動態 enable/disable per skill；理由人類可讀 |
| **BodyState** — 擴 WorldState 加 localization / map / battery / nav_ready | OpenClaw context engine | Brain 發 plan 前已知道身體可不可行 |
| **Nav Skill Pack** — go_to_named_place / go_to_relative / run_patrol_route / pause / resume / cancel | (PawClaw 獨有) | 對接既有 nav_capability 4 actions + 3 services |
| **Workspace files** — BODY.md / SKILLS.md / SAFETY.md / PLACES.md / DEMO_MODE.md | OpenClaw AGENTS.md / SOUL.md | 系統自描述；Phase C 餵 LLM context |

**Studio 對 PawClaw 的對應升級**：Skill Trace Drawer 加「Capability Status」分頁，列每個 skill 為何可/不可用；Skill Buttons 灰階按鈕 hover 顯示「我為什麼不能做」的人話訊息（不再是「Disabled」單字）。

**Demo 升級對話範例**：

```
[user]   去廚房看一下
[brain]  candidate skill: go_to_named_place(place="廚房")
[capability]  ✗ blocked
              · AMCL 定位未收斂
              · 地圖未載入
[brain]  fallback to chat_reply
[say]    我現在還不能移動 — 定位還沒收斂、地圖也還沒載入。要先建圖嗎？
```

詳細設計請見 `docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md`。
