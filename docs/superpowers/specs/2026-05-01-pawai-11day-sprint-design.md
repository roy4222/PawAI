# PawAI 11-Day Sprint Design — 5/12 學校 Demo

> **Status**: current (作戰地圖)
> **Date**: 2026-05-01
> **Scope**: 從 2026-05-02 (D1) 到 2026-05-12 (D11) 的 sprint design,把所有共識凝結成單一作戰地圖。
> **產出來源**: 2026-05-01 brainstorm session(storyboard / skill registry / phase task list / safety gate / LLM 接法 / TTS 換血 / persona / PR port)
> **下一步**: spec approved → invoke writing-plans skill 切 implementation tasks
> **演進關係**: 本 spec 短期作戰版,長期演進依然循 [`2026-04-27-pawai-brain-skill-first-design.md`](2026-04-27-pawai-brain-skill-first-design.md) Phase A + [`2026-04-27-pawclaw-embodied-brain-evolution.md`](2026-04-27-pawclaw-embodied-brain-evolution.md) Phase B

---

## 1. Sprint Goal

> **5/12 晚上學校 Demo:讓觀眾在 4:30 內看到一隻「看懂你 × 理解你 × 會說話 × 能安全地走向你」的具身互動機器狗。**

**核心定位轉變**:
- 從「功能 MOC」(Map of Content,各模組各自能跑)
- 轉為「Demo-directed Architecture」(整個專題是一體,所有功能服務同一條故事線)

**三條衝刺主軸**:
1. **PawAI Brain 變聰明** — LLM/TTS 換血(OpenRouter 主線 + Gemini 3.1 Flash TTS),但保留 fallback;Safety/Executive 仍 deterministic,不讓 LLM 直接控狗
2. **SLAM + Nav2 真的做出效果** — RPLIDAR-A2M12 已採購,5/12 前必須有 `/scan` + 建圖 + AMCL + Nav2 + 短距自主導航
3. **D435 + RPLIDAR 整合** — 分層整合(LiDAR 主導航 / D435 RGB 語意 / D435 Depth 安全 gate)

**一句話**:
> 2D LiDAR navigation + RGB-D semantic interaction + depth safety gate + PawAI Brain skill orchestration

---

## 2. Demo-directed Architecture

```
RPLIDAR-A2M12 ──> /scan ──> SLAM/AMCL/Nav2 ──> 2D 主要導航
                                                    │
D435 RGB ──> face/gesture/pose/object ──> Brain ────┤
                                              │     │
D435 Depth ──> depth_safety ──────────────────┤     │
                                              ▼     ▼
                                      Executive Safety Gate
                                       (Nav Gate + Depth Gate)
                                              │
                                              ▼
                                       Go2 (sport API + Megaphone audio)
```

**分層分工(對應 §5)**:

| Sensor / Module | 負責內容 |
|---|---|
| RPLIDAR-A2M12 | `/scan`、SLAM、AMCL、Nav2、2D costmap、主要導航避障 |
| D435 RGB | 人臉、手勢、姿勢、YOLO 物體辨識 |
| D435 Depth | 前方近距離障礙、人物/物體距離、emergency stop、安全 gate |
| PawAI Brain | 接收事件 → 出 SkillPlan;LLM 動態回覆 + selected_skill 候選 |
| Executive | 安全 gate 仲裁 → 唯一動作出口(say + motion + nav) |

---

## 3. Storyboard v1 [鎖定]

**4:30 8-scene Demo**(順序非硬性可彈性調,但保底 4 場景不能砍):

| # | 時間 | Scene | Plan A | Plan B |
|---|---|---|---|---|
| 1 | 0:00-0:30 | System Ready | Studio 顯示 D435/RPLIDAR/Brain/Nav2 ready | 已錄 map 截圖 |
| 2 | 0:30-1:15 | **Wow A: Nav Backbone** | nav_demo_point Nav2 短距 1-1.5m + Depth Gate 監控 | map + 手動短距 + 口頭說 LiDAR |
| 3 | 1:15-2:00 | **Wow B: Personality** | self_introduce 6 步 + Gemini TTS audio tags | 固定台詞 6 步,動作不變 |
| 4 | 2:00-2:25 | 熟人互動 | greet_known_person LLM 動態 | 寫死「歡迎回來,Roy」 |
| 5 | 2:25-3:00 | 手勢互動 | Wave/Thumb/Palm stop | 縮 Wave + Palm |
| 6 | 3:00-3:25 | 物體語意 | red cup → YOLO + HSV + curious reply | 純 YOLO |
| 7 | 3:25-4:10 | **Wow C: Sensor Fusion** | face+wave → approach_person → safety gate → Nav2 靠近 → hello | 整段砍,口頭/影片補 |
| 8 | 4:10-4:30 | 陌生人 + safety stop | stranger_alert + 喊「停」< 200ms | 只跑 stranger_alert |

**3-tier Wow Moment**:
- **A. Navigation Backbone**(Scene 2)— 證明 RPLIDAR/Nav2/Depth Gate 真能用
- **B. Embodied Personality**(Scene 3)— Brain MVS 已 merge,風險低
- **C. Sensor Fusion Interaction**(Scene 7)— D435 語意 + RPLIDAR 導航 + Brain orchestrate,賭運氣

**4 個保底場景(Demo 失敗下限)**: System Ready / Nav Demo / Self Introduce / Palm Stop。
**保底導航**: `nav_demo_point` 5/5 PASS,**不是** `approach_person`。
**`approach_person` 是 Wow C 進階整合,不保證當保底**。

---

## 4. Skill Registry v1 [鎖定]

### 4.1 Skill Inventory(唯一真相表)

| Bucket | 數量 | Skill IDs |
|---|---|---|
| **Active**(Demo 啟用,Studio enabled button) | 16 + 1 | stop_move、system_pause、show_status、chat_reply、say_canned、self_introduce、wave_hello、wiggle、stretch、sit_along、careful_remind、greet_known_person、stranger_alert、object_remark、nav_demo_point、approach_person、+ fallen_alert(可控啟用) |
| **Hidden**(registry 內、enabled=false,Studio grayed-out) | 5 | enter_mute_mode、enter_listen_mode、akimbo_react、knee_kneel_react、patrol_route |
| **Disabled / Future**(registry 內、enabled=false,Studio hide 或灰底) | 4 | follow_me、follow_person、dance、go_to_named_place |
| **Retired**(Brain MVS 既有,本 sprint 退場,被 wave_hello/wiggle/stretch 取代) | 1 | acknowledge_gesture |
| **Total** | **26** | |

> Studio Skill Console 顯示:**17 個 enabled button**(16 Active + fallen_alert 可控)+ 5 個 grayed-out(Hidden)+ 4 個 hide-or-灰底(Disabled/Future)。Retired 不顯示。

### 4.2 OK 二次確認 — 分集合落地

> **原則:Safety immediate / low-risk social direct / 高風險 motion+nav+state-change 需要 OK**

#### Active Confirm Set(B3 範圍,4 條)
**wiggle / stretch / approach_person / nav_demo_point(非 Studio button trigger 時)**
→ B3 實作:1 個共用 PendingConfirm state machine,4 條 skill 共用。

#### Hidden Confirm Set(隨 Hidden skill 啟用時生效,2 條)
**enter_mute_mode / patrol_route**
→ 用同一個 state machine,不需重寫。

#### Disabled / Future Confirm Set(本 sprint 不實作,3 條)
**dance / follow_me / follow_person**

#### 不需要 OK
stop_move、system_pause、enter_listen_mode、wave_hello、nav_demo_point(Studio button trigger)、所有 chat、所有 pose-react、所有 face skill、object_remark、show_status

### 4.3 TTS audio tag 預埋

26 條中除 LLM 動態 say 的 5 條(chat_reply、greet_known_person 部分、object_remark 部分、stranger_alert 變數版、fallen_alert 變數版)外,其餘 21 條 say_template 都預埋 audio tag(`[excited]` `[curious]` `[gasps]` `[whispers]` `[laughs]` `[worried]` `[playful]` `[sighs]`)。Plan B 切 edge-tts 時 tag 自動退化成純文字。

---

## 5. D435 + RPLIDAR Integration Strategy [鎖定]

> **不做硬性 3D sensor fusion。採用分層整合。**

| Layer | Sensor | 角色 |
|---|---|---|
| L1 主導航 | RPLIDAR-A2M12 → `/scan` → SLAM/AMCL/Nav2/costmap | 2D 幾何避障、移動規劃 |
| L2 語意感知 | D435 RGB → face/gesture/pose/object 模組 | 觸發 Brain skill |
| L3 安全 Gate | D435 Depth → 前方 ROI 1m 清空檢查 | Pre-action veto |

**5/12 不做主線**:D435 local costmap、Visual SLAM、Semantic 3D mapping、Tesla-like pure vision、Waymo-like full fusion。

---

## 6. Safety Gate / Capability Predicate [鎖定]

> **Executive 不要變成感測器細節垃圾桶。各 capability 自己提供 boolean,Executive 只看合成結果。**

### 6.1 兩層 Gate(對應 user 5/1 brainstorm 拍板)

```
Nav Gate(由 nav_capability 提供):
  ├─ Nav2 lifecycle = active
  ├─ AMCL covariance < 0.20
  └─ costmap target cell cost < 50
  → publish /capability/nav_ready (Bool)

Depth Gate(由 D435 depth_safety_node 提供):
  └─ D435 depth front ROI 1m 內無 < 0.4m 障礙
  → publish /capability/depth_clear (Bool)

Executive Pre-action Validate(三段判斷):

  if step.kind == NAV:
    require nav_ready AND depth_clear

  elif step.kind == MOTION and skill in {wiggle, stretch, dance,
                                          approach_person, follow_*}:
    # high-risk motion(大動作 + 可能位移)
    require depth_clear AND robot_stable

  elif step.kind == MOTION and skill in {wave_hello, sit_along,
                                          careful_remind, akimbo_react,
                                          knee_kneel_react}:
    # low-risk social motion(原地、小幅度)
    pass  # 不走 gate

  elif step.kind == SAY:
    pass  # SAY 永遠允許

  if not satisfied:
    degrade to SAY with human-readable reason
    publish brain_plan with degradation note
```

> `robot_stable` = IMU 平穩(無摔倒/未在另一動作執行中)。低風險 social motion 不走 gate,確保手勢互動不被 Nav2 掛掉拖累。

### 6.2 答辯亮點

「PawAI 不是硬衝,而是知道自己現在不能安全移動」 — Capability Predicate 讓 skill 灰階 + 人話訊息,對應 PawClaw evolution Phase B `enabled_when` 設計的短期版本。

---

## 7. Phase A: Navigation Attack [鎖定 — 5/2-5/3]

> **2 天攻破最大不確定性。Phase A 失敗會直接降級 storyboard。**

### A1. Bug 修復

- [ ] **BUG #2 修**: `nav_capability/nav_action_server_node.py` goto_relative action 加 `/nav/pause` subscriber + pause/resume 邏輯
- [ ] **BUG #4 修**: K2-lite WP_n=start 短路(BT 內部 goal_pose ≈ current_pose 直接 SUCCEEDED)
- [ ] BUG #1 迴歸測試: K1 baseline 5/5 重跑

### A2. Safety Gate 落地(對應 §6 兩層架構)

- [ ] `nav_capability` 新增 `/capability/nav_ready` publisher(合成 Nav2 active + AMCL cov + costmap cost)
- [ ] D435 新建 `depth_safety_node` 發 `/capability/depth_clear`(ROI 前方 1m / 障礙 < 0.4m 判定)
- [ ] `interaction_executive` Pre-action validate 訂兩個 Bool,任一 false → 降級 NAV/MOTION → SAY
- [ ] Studio Trace Drawer 即時顯示 2 個 Bool 燈

### A3. 兩條主線 Nav skill

- [ ] **`nav_demo_point` skill** 上機 5/5 PASS(保底主線,對應 Scene 2)
  - `nav_capability/goto_relative` 1-1.5m
  - 2-Gate 必過
- [ ] **`approach_person` skill** 上機 1 次 PASS(進階 Wow,對應 Scene 7,**不放保底**)
  - face_state stable_name 非空 + gesture in {Wave, ComeHere}
  - face_centroid → goto_relative 至 1.0m 前

### A4. 供電風險先驗

- [ ] LiDAR + Go2 + Jetson 同跑 30 分鐘無斷電(Phase A 結束前必過)

### A5. 5/3 晚上停損點 [鎖定]

> **若 5/3 晚上 Nav2 沒起來 → 立刻降級為 map + Safety Gate + 手動短距展示;Scene 2 改成 map 視覺化 + 口頭說明 LiDAR**

---

## 8. Phase B: Brain × Studio Integration [鎖定 — 5/4-5/8]

> **5 天集中整合,不是各模組各自跑,是「整個專題是一體」。**

### B1. LLM eval + TTS 換血(5/4 當天完成最小版)[鎖定範圍]

> **最小版 = 50 prompt × 3 LLM × 4 軸 → JSON 輸出。不做漂亮 dashboard,Studio Eval Summary 頁 = optional**

- [ ] 50 prompt 中文測試集(對齊 Active Set 16 skill 的 trigger;5 桶:chat 15 / action-in-registry 15 / action-out-of-registry 10 / alert 5 / multi-turn 5)
- [ ] Persona system prompt(對齊 mission/README §2 定位:居家互動 + 守護 + 多模態 + **不列拒絕清單**,用「我學學看!」「我幫你...」這種主動正向語氣)
- [ ] eval script(Python ~150 行,OpenRouter API caller)
- [ ] 跑 3 LLM × 50 prompt:Gemini 3 Flash Preview ($0.50/$3) / DeepSeek V4 Flash ($0.14/$0.28) / Qwen3.6 Plus ($0.325/$1.95)
- [ ] **4 軸評分**:intent accuracy / skill selection accuracy / safety(refuse 是否優雅)/ persona consistency
- [ ] 選定主線 + fallback 模型(eval 數據佐證,可寫進答辯)
- [ ] `llm_bridge_node` provider chain:OpenRouter 主線 → OpenRouter 雲端 fallback → Ollama 1.5B → RuleBrain
- [ ] **`LLMProvider` adapter 化**(借鑑 Hermes-Agent ProviderTransport):`convert_messages` / `convert_tools` / `build_kwargs` / `normalize_response` 4 個介面,不把 OpenRouter / Ollama / RuleBrain 寫死在 Brain
- [ ] **Gemini 3.1 Flash TTS audio contract**:
  - 輸入:text + audio tags
  - 輸出:PCM 24kHz/16-bit/mono(per OpenRouter Gemini 3.1 Flash TTS Preview spec)
  - **TTSProvider 統一輸出 WAV bytes**,下游 player 不關心 provider 差異(adapter 化)
- [ ] 兩條播放路徑:
  - **USB 喇叭(主線)**:24kHz 直接播,品質最佳(對應 mission/README 4/8 共識)
  - **Megaphone(備援)**:必須 resample 到 16kHz/16-bit/mono(Megaphone API 硬體限制)
- [ ] audio tag 渲染驗證(`[excited]` `[laughs]` 是否有差異化合成)
- [ ] TTS provider chain:Gemini 3.1 → edge-tts → Piper(三級 fallback)

### B2. Skill Registry 落地(對齊 §4.1 Inventory)

- [ ] `skill_contract.py` 寫入 26 條 SkillContract dataclass(含 Retired 標記給 acknowledge_gesture)
- [ ] SKILL_REGISTRY dict + Active(17 含 fallen)/Hidden(5)/Disabled(4)/Retired(1) 標記
- [ ] per-skill cooldown / safety_requirements / fallback_skill 設定
- [ ] META_SKILLS["self_introduce"] 6 步序列
- [ ] **TTS audio tag 預埋在 say_template**(對應 §4.3,21 條預埋)

### B3. Brain 規則表 + OK 二次確認狀態機

- [ ] brain_node 規則表擴 ~10 條(對齊 Active 17 條 trigger)
- [ ] **OK 二次確認狀態機 — Active Confirm Set 4 條**(wiggle / stretch / approach_person / nav_demo_point[非 Studio button]):
  - 1 個共用 PendingConfirm state machine
  - 進入 PendingConfirm + 5s timeout
  - timeout / 不同手勢 → 取消(回 Idle)
  - OK 手勢穩定 0.5s → 觸發 skill
  - Hidden / Disabled Confirm skill enabled 時自動套用同 state machine,不需重寫
- [ ] per-skill cooldown table

### B4. 感知模組擴

- [ ] **手勢**:Wave 動態軌跡(wrist x 速度方向反轉計數,2s 視窗 ≥ 3 次)
- [ ] **手勢**:Palm Pause / Fist Mute 映射
- [ ] **姿勢**:sitting → sit_along / bending → careful_remind 映射
- [ ] **物體**:HSV 顏色偵測(red/yellow/blue/green 4 色,bbox crop → HSV histogram peak)
- [ ] **人臉**:fallen_alert say_template 加 `{name}` 變數

### B5. Studio Brain trace 全鏈 [優先級高於 B6]

- [ ] **17 個 Active enabled button**(對齊 §4.1)+ 5 grayed-out(Hidden)+ 4 hide-or-灰底(Disabled/Future)
- [ ] **Skill Trace Drawer 即時顯示 Nav Gate + Depth Gate 兩個 Bool 狀態**(§6.1)
- [ ] Plan A↔B 切換按鈕(模擬網路斷)
- [ ] (optional)Studio 顯示 Eval result summary 頁

### B6. 4 個 PawAI PR 程式碼 port [鎖定範圍]

> **必 port = Brain Skill Console 需要的部分;可 port = sidebar panels;不能搶 B5 主畫面 trace 的優先級。**
> **後端全部不直接 merge** — Brain MVS 是 SoT,避免衝突。

- [ ] PR #40 物體:前端 panel(歷史紀錄 / 即時偵測 / 白名單)→ 對應 Scene 6
- [ ] PR #41 姿勢:`pose-panel.tsx` + `use-pose-stream.ts` WebSocket 邏輯 → optional sidebar
- [ ] PR #38 手勢:`gesture-panel.tsx` + 本地相機卡片 → optional sidebar
- [ ] PR #42 語音:`speech-panel.tsx` + `use-audio-recorder.ts` → **注意與 Brain Skill Console 首頁衝突,需釐清前端設計分工**

### B7. E2E Plan A + Plan B + 供電

- [ ] 8 scene Plan A 連跑 1 次完整(整合 milestone)
- [ ] **8 scene Plan B 固定台詞腳本**(網斷時逐字)
- [ ] Studio 連線狀態燈 + 一鍵切 Plan B 機制
- [ ] **供電 60 min 連續測試**(Go2 + Jetson + LiDAR + D435 全開,跑 8 scene 循環)

---

## 9. Phase C: Freeze + Demo [鎖定 — 5/9-5/12]

> **5/9 起 freeze,不再加新功能,只做 dry run / bug 修 / 場地驗證 / Plan B 終版。**

### C1. Dry Run × 3

- [ ] Dry Run #1:Plan A 全 scene 連跑 × 3 + 列 top 5 bugs 修完
- [ ] Dry Run #2:Plan A↔B 切換演練(實際模擬網路斷)
- [ ] Dry Run #3:Demo 4:30 + Q&A 全跑(主持人扮演完整流程)

### C2. 場地與備品

- [ ] 1003 第三廳實地測試 1 次(燈光 / 網路 / 投影 / 主持人走位)
- [ ] Plan B 腳本印實體紙本
- [ ] 備品清點:備電源 / 備網路 hotspot / 備筆電 / 備網線

### C3. Demo Day

- [ ] 上午到場 pre-flight 30 min
- [ ] 中午 dry run 1 次
- [ ] 晚上 Demo + Q&A

---

## 10. PR Port Strategy [鎖定]

| PR | 前端 port | 後端 |
|---|---|---|
| #40 物體 | object panel(歷史/即時/白名單)→ 必 port | **不抄**(elder_and_dog YOLO26n+TRT 已 SoT) |
| #41 姿勢 | pose-panel + WebSocket → optional sidebar | **不抄**(MediaPipe Pose 已 SoT) |
| #38 手勢 | gesture-panel + 相機卡片 → optional sidebar | **不抄**(MediaPipe Gesture 已上機 5/5) |
| #42 語音 | speech-panel + recorder hook → 與 Skill Console 衝突,**需設計決策** | **不抄**(Brain MVS llm_bridge SoT) |

**原則**: 後端不 merge / 前端只 port 對 Studio trace + Demo 有幫助的部分 / 不為了抄 PR 破壞主畫面。

---

## 11. Plan A / Plan B Degradation [鎖定]

每個 scene 雙版本(Plan A 主線 / Plan B 固定台詞 + 動作不變)詳見 §3 表。

**切換機制**: Studio 連線狀態燈 + 一鍵切按鈕。**目標切換無感 < 2 秒**。

**為什麼必要**: GPU 雲端曾意外斷線兩次(歷史紀錄),Plan B 是必備保險;Plan B 不是 fallback after fail,是「主動切換」的選項。

---

## 12. Stop-loss Criteria [鎖定]

> **三停損點 + 凍結期一刀切。不憑感覺,機械化執行。**

| 停損點時點 | 觸發條件 | 砍場 / 降級 |
|---|---|---|
| 5/3 晚上 | Nav2 沒起來(K1 5/5 不過 + nav_demo_point 不通) | **Scene 7 整段砍;Scene 2 兩選一**:<br/>**(a) Map only**:RViz/Foxglove 顯示 LiDAR map + `/scan`,不展示移動<br/>**(b) `manual_motion_demo` skill**:Executive 加一條臨時 skill,**只要求 `depth_clear=true`,不要求 `nav_ready`**;走 stand/sit/wiggle 等 stationary motion + 「我的腳還在學走路」台詞;**仍走 Executive 單一出口**,不繞過 Brain |
| 5/6 | approach_person 整合不穩 | Scene 7 砍,Scene 2 保留 |
| 5/7 | LLM eval 結果無一可用 / Brain 整合不穩 | 動作 intent 改走規則,LLM 只跑 chat |
| 5/8 | Gemini TTS 渲染失敗 | 全部 audio tag → edge-tts 純文字 |
| 5/8 | Gesture 不穩 | 手勢只留 Palm + Wave |
| **5/9 起** | **凍結期啟動** | **不加新場景 / 不加新 skill / 不改架構;只 dry run + bug 修 + 場地** |

---

## 13. Architecture References — OpenClaw / Hermes-Agent 借鑑 [鎖定]

> **PawAI Brain 借鑑 OpenClaw 的 Gateway / Skill / lifecycle event 架構,以及 Hermes-Agent 的 provider abstraction / memory / guardrail 設計,但保留 ROS2 + Executive safety-first 的機器人控制邊界;LLM 只負責理解與提案,實體動作永遠由 Executive 驗證後執行。**

### 13.1 OpenClaw 借鑑(控制平面 / Gateway / 可觀測)

| OpenClaw 概念 | PawAI 對應 | 5/12 落地? |
|---|---|---|
| Gateway 為唯一控制平面 | `studio_gateway` 為 Studio ↔ ROS2 唯一 entry | 已存在,B5 補強 |
| Typed WebSocket Event(req/resp/lifecycle) | `/state/pawai_brain` + `/brain/proposal` + `/brain/skill_result` | 已存在,B5 補 trace |
| Skill lifecycle event(8 種狀態) | accepted / started / step_started / step_success / step_failed / completed / aborted / blocked_by_safety | 已存在(Brain MVS) |
| Model failover with allowlist | LLM/TTS provider chain(§8 B1) | B1 落地 |
| Skill eligibility / requires / allowlist | `enabled_when` / `safety_requirements` / `fallback_skill` | B2 落地 |

### 13.2 Hermes-Agent 借鑑(provider / memory / guardrail)

| Hermes-Agent 概念 | PawAI 對應 | 5/12 落地? |
|---|---|---|
| ProviderTransport interface | `LLMProvider` adapter + `TTSProvider` adapter(§8 B1) | B1 強制 adapter 化 |
| Context Engine(session context) | `WorldState` + `BodyState` + `RecentEvents` 餵 LLM(整理過 snapshot,不是 raw events) | 簡版(已在 brain_node) |
| Tool Loop Guardrails | per-skill cooldown(B3)+ approach_person 失敗降級為 SAY | B3 落地 |
| MemoryManager 統一介面 | 不在 5/12 主線(Future Work) | 不做 |
| Curator(自動整理 skill) | 不在 5/12 主線(Demo 後從 dry run log 半人工) | 不做 |

### 13.3 不採納(避免 over-engineering)

- OpenClaw multi-agent / multi-channel 全套 routing
- Hermes 自動 skill creation / curator
- 完整 memory wiki / semantic memory
- Plugin system
- Subagent / delegation runtime

---

## 14. Future Work(5/12 不做,Demo 後)

- [ ] follow_me / follow_person / dance
- [ ] patrol_route(若 Phase B 進度允許,可 5/8 前開成 Studio optional 按鈕展示,不進主 storyboard)
- [ ] go_to_named_place 完整 named places UI
- [ ] 註冊新人臉 ROS2 service
- [ ] yolov8n 對比 + 室內資料集
- [ ] 文件網站(由組員處理,Astro + Starlight)
- [ ] Hermes-Agent / OpenClaw 借鑑深度整併(對應 PawClaw evolution Phase B)
- [ ] D435 local costmap / Visual SLAM / Semantic 3D mapping

---

## 附錄 A:鎖定 / 待驗證 / Optional 標記

| 項目 | 狀態 |
|---|---|
| Storyboard v1 8-scene | 鎖定 |
| Skill Inventory(§4.1 唯一表):Active 17 / Hidden 5 / Disabled 4 / Retired 1 = 26 | 鎖定 |
| OK 二次確認:Active Confirm Set 4 / Hidden 2 / Disabled 3 | 鎖定 |
| Safety Gate:Nav Gate + Depth Gate 兩層 + 三段 Pre-action Validate(NAV / high-risk MOTION / low-risk social MOTION) | 鎖定 |
| Gemini TTS audio contract(24kHz PCM,Megaphone 必須 resample 到 16kHz) | 鎖定 |
| 5/3 Plan B:Map only OR `manual_motion_demo` skill(不要求 nav_ready) | 鎖定 |
| OpenClaw / Hermes 借鑑點(§13) | 鎖定 |
| Phase A 任務 | 鎖定 |
| Phase B 任務 | 鎖定 |
| Phase C 任務 | 鎖定 |
| 三停損點 + 凍結期 | 鎖定 |
| LLM 主線 / fallback 選擇 | 待驗證(5/4 eval 數據後拍板) |
| approach_person 上機可行性 | 待驗證(5/3 一次上機 PASS 才能保留 Scene 7) |
| HSV 顏色偵測準確度 | 待驗證(5/4 上機驗) |
| Wave 動態軌跡準確度 | 待驗證(5/4 上機驗) |
| Studio Eval Summary 頁 | optional |
| Hidden / Future skill | optional(進度允許可開) |
| PR #41 / #38 sidebar port | optional |
| PR #42 語音前端 port | 待釐清(與 Brain Skill Console 衝突) |

---

## 附錄 B:依賴與並行化

```
A1 Bug fix ──┐
             ├─> A3 nav_demo_point ──┐
A2 Gate impl ┘                       ├──> A3 approach_person ──┐
                                     ↓                          │
                           (Phase A 5/3 結束)                    │
                                     │                          │
B2 Registry ─┐                       │                          │
B3 規則+OK ──┤                       │                          │
B4 感知擴 ───┼──> B7 E2E Plan A ────┴──> B7 供電 60min ────────┴──> 5/9 凍結
B5 Studio ───┤
B1 LLM eval ─┘
B6 PR port ──> 並行 with B5(優先級 < B5)
```

可叫組員幫忙(per CLAUDE.md §7):
- 50 prompt 寫測試集 → 陳若恩(已負責語音)
- B6 PR review → 黃旭 / 魏宇同
- C2 場地測試 → 全員
- 文件 Ch1-5 補強 → 各自負責章節(平行進行,不影響本 sprint)

---

## 附錄 C:答辯亮點(5 個)

1. **Demo-directed Architecture** — 從功能 MOC 轉一體系統;所有功能服務同一條故事線
2. **Capability Predicate Pattern** — Nav Gate + Depth Gate 兩層 Bool;Executive 不變感測器垃圾桶,降級 NAV → SAY 時給人話訊息
3. **Skill Registry × OK 三層原則** — Safety immediate / low-risk social direct / 高風險需 OK,證明 PawAI 既順暢又安全
4. **D435 + RPLIDAR 分層整合** — 不做硬性 3D fusion,RGB 語意 / Depth 安全 / LiDAR 導航各司其職
5. **4 級降級鏈 + Plan A/B 切換** — Cloud LLM → Local Ollama → RuleBrain → Plan B 固定台詞;主動切換 < 2 秒

---

*Spec written: 2026-05-01*
*來源: brainstorm session 共識(storyboard / skill registry / phase task / safety gate / LLM 接法 / TTS / persona / PR port)*
