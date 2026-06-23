# Demo Phase Conductor Plan — 五幕場景指揮

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫群：PawAI Demo Flow Reliability Sprint（Cloud A）｜本份：Demo Phase Conductor Plan

> **上游**：[master](2026-06-13-demo-flow-reliability-master-plan.md)（本計畫群策略總綱）
> **平行**：[online/offline fallback](2026-06-13-online-offline-fallback-plan.md)（每幕 canned phrase 與 timeout）、[s1 nav](2026-06-13-s1-low-risk-navigation-plan.md)（s1_nav 幕對應的 nav stack）、[operator runbook](2026-06-13-demo-operator-runbook-plan.md)（操作員逐幕指令）
> **協調**：[Lane 1 Brain ISM staged enable](2026-06-13-lane1-brain-ism-staged-enable-plan.md)（**stage 2a = 同一張 phase 表的 ISM policy 接管**，本計畫只做詞彙/清理/控制，2a 做接管）
> **Code 現實基準**：`interaction_executive/interaction_executive/interaction_state.py:33`（`PHASE_ALLOWED_KINDS`）、`:42`（`phase_allows`）；`brain_node.py:496/539`（`demo_phase` param）、`:311-321`（runtime set callback）、`:331-351`（`_DEMO_PHASES` / `_phase_allows`）、`:1348/1747/1945`（gesture/greet/object 早退）、`:2190-2209`（`_on_reset_context`）

---

## 1. Goal

把**已存在但只是「最小外科 phase gate」**的 `demo_phase` 機制（`PHASE_ALLOWED_KINDS`），正式化成 6/18 demo 五幕的**場景指揮（Conductor）**：

1. **詞彙對齊五幕**：把現有 `all / s2_face / s3_object / s4_gesture / quiet` 對映/改名/擴充成 `s1_nav / s2_greet / s3_pose_object / s4_gesture / s5_safety`，並保留舊名為 alias（byte-identical backward-compat）。
2. **切換即清場**：切 phase 時清掉前一幕殘留的 `pending_confirm` / `active_plan` / gesture cooldown（走 `/brain/reset_context` 等價路徑），避免「換 take / 換幕」被上一段狀態污染。
3. **控制面三入口**：runtime `ros2 param set`（已有）+ 新 `pawai demo phase <phase>`（Lane 3 風格 SSH wrapper，規劃）+ Studio 小 indicator 顯示 current phase（不大改 UI）。
4. **與 Lane 1 stage 2a 不打架**：Conductor=詞彙+清理+控制；2a=同表 ISM policy 接管。`ism_enabled` off 且 `demo_phase=all` 時 = 現行為（byte-identical 退路）。

**非目標**：不擴大 phase 去 gate 安全鏈、不接管事件優先序（那是 Lane 1 的 2b-2d）、不重寫 brain 裁決。

---

## 2. Current state（code 實證，2026-06-13）

**phase 機制已存在，不是新建**（brain_node.py 行號已實際查證）：

- `interaction_state.py:33` `PHASE_ALLOWED_KINDS`（5 個 key，純 frozenset 表）。
- `interaction_state.py:42` `phase_allows(demo_phase, kind)`：unknown phase → 視同 `all`（`allowed is None → True`）。
- `brain_node.py:496` `declare_parameter("demo_phase","all")`；`:539` 啟動讀取（lower/strip）；`:311-321` runtime set callback（**unknown phase 拒絕、保留舊值並 log**，`SetParametersResult(successful=True)`）。
- `brain_node.py:331` `_DEMO_PHASES = frozenset(interaction_state.PHASE_ALLOWED_KINDS)`；`:333` `_phase_allows(kind)`。
- 三個自發社交 proposal 早退：`:1348` gesture（前面 `:1342` 還有 `gesture_enabled` 獨立 gate）、`:1747` greet、`:1945` object。
- 設計註解 `:326-330`：**demo_phase 只 gate「自發性社交 proposal」（greet / object_remark / gesture）**。安全鏈（fallen/stop/SafetyLayer）、語音/文字明確指令、Studio `skill_request` 一律不受 phase 影響。priority：**safety > explicit input > phase**。
- 錄影 SOP 已存在（`:330` 註解）：`ros2 param set /brain_node demo_phase s3_object`（換 take 再切）。

**清理路徑已存在**（`brain_node.py:2190-2209` `_on_reset_context`，topic `/brain/reset_context` `std_msgs/Empty`）：
- 清 `PendingConfirm`（`:2197-2199`，僅 `state==PENDING` 時 cancel，reason=`page_reset`）。
- 清 `object_remark` 兩層 dedup（`:2203-2206`：`_object_remark_seen` + `last_alert_ts["object_remark"]`）。
- 清上一段 `active_plan`（`:2207`，`self._state.active_plan = None`）。
- **不清** `self._state.attention`（`:2193` 註解明言保留）。
- ISM shadow：`:2209` 送 `IsmTrigger.OPERATOR {"op":"reset"}`（never-raises）。

**控制 topic 已存在**：`/brain/reset_context`（Empty）、`/brain/gesture_enabled`（`std_msgs/Bool`，`:258`）。

**phase 切換目前「不主動清」pending/active/cooldown**（gap，見 §3）：runtime set callback（`:311-321`）只改 `self.demo_phase` 字串，**不觸發任何 reset**。換幕殘留要靠操作員另外手動發 `/brain/reset_context`。

**能力分級（現況）**：
- phase gate（現有 3 kind 抑制）= **proven**（6/10 demo 已用 `demo_phase s3_object` 等錄影；錄影 SOP 已落 code 註解）。
- 五幕詞彙 / 切換自動清理 / CLI / Studio indicator = **needs-HITL**（本計畫新增 code，待 6/18 前 Roy 在場重驗）。
- ISM policy 接管（stage 2a）= **Lane 1 範疇**，不在本計畫。

---

## 3. Problems / gaps

| # | Gap | 影響 | 來源 |
|---|---|---|---|
| G1 | phase 詞彙與五幕不對齊（`s2_face`≠`s2_greet`、無 `s1_nav`/`s5_safety`） | 操作員與文件講「s5」但 code 沒有，易切錯 | §2 表 |
| G2 | 切 phase 不清 `pending_confirm`/`active_plan`/gesture cooldown | 換幕／換 take 被上一段污染（confirm 黑洞、cup 台詞被吃、wiggle 殘留） | `:311-321` 只改字串 |
| G3 | 切 phase 只能 `ros2 param set`（要 SSH + 記指令） | 現場手忙、易打錯 phase 名 | CLI 無 `demo phase` |
| G4 | Studio 看不到 current phase | 操作員/觀眾不知現在哪一幕、shadow 開沒 | Lane 3 T3-6 status gap |
| G5 | s1_nav 走路時若 brain 在跑，仍可能自發 greet/object/gesture | 走路途中亂搭話、搶資源 | 需 `s1_nav=quiet` 保證 |
| G6 | unknown phase 容錯成 `all`（`phase_allows` `None→True`） | 打錯字 → 靜默變「全開」而非「全靜默」，demo 易翻車 | `interaction_state.py:49` |

---

## 4. Scope

- **詞彙層**：在 `PHASE_ALLOWED_KINDS` 加 5 個 canonical key + alias 解析；`s1_nav`/`s5_safety` 語義 = `quiet`（全 suppress）。
- **清理層**：新 helper `_apply_phase_transition(new_phase)`，切 phase 時走 `_on_reset_context` 等價清理（pending_confirm + active_plan + gesture cooldown 必清；object/greet cooldown 視旗標）。
- **控制層**：`pawai demo phase <phase>`（SSH wrapper，零 runtime 行為以外的副作用——它只發 `ros2 param set`）；Studio 讀 `/state/brain` 既有欄位顯示小 indicator。
- **退路層**：`ism_enabled` off + `demo_phase=all` = byte-identical；alias 解析不改變既有行為。

---

## 5. Forbidden scope

- 不擴 phase 去 gate 安全鏈 / explicit input / Studio `skill_request`（永遠 phase-independent，`:326-330` 鐵律）。
- 不接管事件優先序、不動 `_PREEMPTIBLE_BY`、不開 ISM 2b/2c/2d（Lane 1 範疇）。
- 不大改 Studio UI（只加一個唯讀小 indicator）。
- 不重寫 CLI、不換模型、不碰 nav 行為（s1_nav 幕的 nav 細節歸 [s1 nav plan](2026-06-13-s1-low-risk-navigation-plan.md)）。
- 不做 phase 自動排程（不自動「走完 s1 跳 s2」——一律操作員手動切，符合 runbook 保守姿態）。

---

## 6. 五幕 phase 表（Conductor 設計骨幹）

> **抑制範圍只限三種自發社交 kind**：`greet` / `object` / `gesture`。安全鏈、explicit input、Studio skill_request **不在此表內、永遠放行**。

### 6.1 對映 / 改名 / 擴充

| canonical（新）| alias（舊，backward-compat）| allow kinds | 對映現有表 | 語義 |
|---|---|---|---|---|
| `s1_nav` | （新增）| ∅（全 suppress）| `quiet` | 移動到現場，brain 靜默 |
| `s2_greet` | `s2_face` | `{greet}` | `s2_face` | 認 Roy + 問候 |
| `s3_pose_object` | `s3_object` | `{object}` | `s3_object` | 坐姿 + 杯子提醒 |
| `s4_gesture` | （同名）| `{gesture}` | `s4_gesture` | thumbs_up→OK→wiggle |
| `s5_safety` | （新增）| ∅（全 suppress）| `quiet` | 只留 SafetyLayer reject |
| `all` | （保留）| `{greet,object,gesture}` | `all` | 非 demo / 平時 |
| `quiet` | （保留）| ∅ | `quiet` | 全靜默泛用 |

alias 解析：`_canonicalize_phase("s2_face") → "s2_greet"`、`"s3_object" → "s3_pose_object"`；canonical 與 `all`/`quiet` 原樣保留。**alias 與 canonical 行為 byte-identical**（同一 frozenset）。

### 6.2 每幕細表（allow / suppress / TTS / reset+cooldown / trace）

> TTS 來源見 [online/offline plan](2026-06-13-online-offline-fallback-plan.md)；canned phrase 與該份對齊。`/tts` envelope（contract v2.10）帶 `source`：`chat_reply` / `say_canned` / `skill_say`。

**s1_nav**
- allow：∅ ｜ suppress：greet / object / gesture
- expected TTS：online＝（無自發社交，nav stack 自身台詞）｜offline canned＝「我正在移動到巡檢位置。」（say_canned，預先 render WAV cache）
- reset+cooldown：進入時清 pending_confirm + active_plan + gesture cooldown（換幕前清乾淨）
- trace reason：`phase:s1_nav:greet suppressed` / `phase:s1_nav:object suppressed` / `phase:s1_nav:gesture suppressed`
- 備註：S1 走 nav stack，與 brain demo stack **8GB 互斥**（見 master + s1 nav plan）。若現場是「brain 不在、純 nav」則本幕在 brain 端無事；若 brain 在，`s1_nav=quiet` 保證走路不搭話（**解 G5**）。

**s2_greet**（alias `s2_face`）
- allow：greet ｜ suppress：object / gesture
- expected TTS：online＝LLM/persona 問候｜offline canned＝「Roy，歡迎回來，我看到你了。」
- reset+cooldown：進入時清 pending_confirm + active_plan + gesture cooldown；**greet cooldown 視旗標清**（預設「重錄 take 時清」，見 §7 `clear_greet_cooldown`）——因 greet 走 known-face 進場 + `greet_cooldown_s`(20s)/人，重錄要清才會再觸發
- trace reason：`phase:s2_greet:object suppressed` / `phase:s2_greet:gesture suppressed`
- 硬依賴：greet = known face stable + 最近 `greet_sitting_window_s`(3s) 內 pose=sitting + `greet_cooldown_s`(20s)（CLAUDE.md VIS-4）。**pose=sitting 是 greet 硬依賴**；不穩時 runbook 走 `greet_require_sitting false` 退路。

**s3_pose_object**（alias `s3_object`）
- allow：object ｜ suppress：greet / gesture
- expected TTS：online＝LLM 物體 remark｜offline canned＝「我看到杯子了，記得補充水分。」
- reset+cooldown：進入時清 pending_confirm + active_plan + gesture cooldown；**object cooldown/ dedup 視旗標清**（預設「重錄 take 時清」，等價 `_on_reset_context:2203-2206`）——不清的話第二個 take 的 cup 台詞會被上一個 take 吃掉
- trace reason：`phase:s3_pose_object:greet suppressed` / `phase:s3_pose_object:gesture suppressed`
- 硬依賴：pose=sitting 餵 state → object cup remark。

**s4_gesture**
- allow：gesture ｜ suppress：greet / object
- expected TTS：online＝confirm 詢問（LLM/persona）｜offline canned＝「你要我 WeGo 一下嗎？比 OK 我就開始。」
- reset+cooldown：進入時清 pending_confirm（重置 confirm flow）+ active_plan + gesture cooldown
- trace reason：`phase:s4_gesture:greet suppressed` / `phase:s4_gesture:object suppressed`
- 重要：`gesture_enabled`(`:465` 預設True) 是**獨立於 phase 的第二道 gate**（`:1342` 先查、`:1348` 才查 phase）；s4 要確保 `gesture_enabled=true`。confirm flow 目標路徑 thumbs_up→OK→wiggle，**HITL#2 實際驗的是 peace→OK→WeGo**（`peace_wego_confirm` vs `thumbs_up_demo_ack` param 路徑差異，見 §8 + runbook）。

**s5_safety**
- allow：∅（全 suppress）｜ suppress：greet / object / gesture
- expected TTS：online＝SafetyLayer reject 台詞｜offline canned＝「這個動作不安全，我不能執行。」
- reset+cooldown：進入時清 pending_confirm + active_plan + gesture cooldown
- trace reason：`phase:s5_safety:greet suppressed` / `phase:s5_safety:object suppressed` / `phase:s5_safety:gesture suppressed`
- 重要：backflip 拒絕走 **SafetyLayer reject**，是 **explicit input / safety 鏈**，**phase-independent**——`s5_safety=quiet` 只是把自發社交全關，**不會**因此擋掉 reject。reject 仍正常觸發。

### 6.3 trace 格式（沿用既有，不新增 schema）

每次 phase 抑制走既有漏斗 `_suppressed(gate="demo_phase", reason=f"phase:{phase}:{kind}", throttle_key=f"phase:{kind}")`（`:349`）；trace JSONL 內 `gate=demo_phase` + `reason=phase:<phase>:<kind>` + `demo_phase` 欄位（`:665`）。**本計畫不改 trace schema**，只擴充 phase 字串值域 → `pawai evidence pull` 直接可讀（見 Lane 3）。

---

## 7. 切換清理 helper 設計（純軟體）

新 helper `_apply_phase_transition(new_phase, *, clear_object=None, clear_greet=None)`，在 runtime set callback（`:311-321`）內 phase 真正變更後呼叫：

```
切 phase（_DEMO_PHASES 驗證通過、且 new != old）後：
  with self._lock:
    1. pending_confirm：if state==PENDING → cancel(reason=f"phase_switch:{new_phase}")   # 等價 :2197-2199
    2. active_plan：self._state.active_plan = None                                        # 等價 :2207
    3. gesture cooldown：清 last_alert_ts 內 gesture 相關 key（必清）
    4. clear_object（預設：進 s3 或離開任何幕重錄 take 時 True）→ 清 _object_remark_seen + last_alert_ts["object_remark"]   # 等價 :2203-2206
    5. clear_greet（預設：進 s2 時 True）→ 清 last_alert_ts["greet"] 系（per-person cooldown）
    # 不清 attention（與 _on_reset_context 一致，:2193）
  # 出鎖後送 ISM shadow OPERATOR signal（等價 :2209，never-raises）
  log: f"phase transition {old}->{new}: cleared pending_confirm/active_plan/gesture_cd (object={...},greet={...})"
```

設計原則：
- **重用 `_on_reset_context` 的清理語義**，不另寫一套（pending_confirm/active_plan/object dedup 行號都對齊 §2）；差別在 phase 切換多清 gesture cooldown + 可選 greet cooldown。
- `clear_object` / `clear_greet` 預設值由「目標幕」決定（進 s2→清 greet cd；進/重錄 s3→清 object dedup），但保留參數讓 runbook/CLI 覆寫。
- **必清**（無條件）：pending_confirm + active_plan + gesture cooldown（master 鎖定）。
- **視情況**：object / greet cooldown（避免誤清掉「刻意保留的進場狀態」）。
- 全程 never-raises（callback 內不可炸）；任何 reset 子步驟用 try/except 包，失敗只 log。
- **byte-identical 退路**：`demo_phase=all` 且不切換時，本 helper 不被呼叫（callback 內 `new != old` 才進）→ 與現行為一致。

**G6 容錯收緊（可選，需 Roy 點頭）**：目前 unknown phase 在 `phase_allows` 容錯成 `all`（全開）。demo 場景更安全的是容錯成 `quiet`（全靜默）。**但這會改變 `interaction_state.phase_allows` 語義（Lane 1 stage 2a 也吃同函式）**→ 列為**需與 Lane 1 協調的決策項**，預設**不動**（保 byte-identical），僅在 runbook 標「打錯 phase 名 → callback `:313` 已拒絕保留舊值，不會變全開」（runtime set 這層其實已防呆，真正風險只在 shadow 路徑）。

---

## 8. 控制面設計

### 8.1 runtime param（已存在，零新增）
`ros2 param set /brain_node demo_phase s3_pose_object`（callback `:311-321` 驗證 + 觸發 §7 helper）。alias 仍可用：`demo_phase s3_object` → canonicalize 成 `s3_pose_object`。

### 8.2 `pawai demo phase <phase>`（新增，Lane 3 風格 SSH wrapper）
- 行為：SSH 上 Jetson 對 demo lock owner 的 `/brain_node` 發 `ros2 param set demo_phase <phase>`。**零 runtime 行為以外副作用**——只是包 `ros2 param set`（符合 CLI 哲學「只包腳本/SSH/rsync」）。
- 入參驗證（client 端）：`<phase>` 必須 ∈ {五幕 canonical + alias + all + quiet}，否則本地報錯不發（**比 ros2 param set 早攔，解 G3 打錯字**）。
- 安全：需 demo lock 存在且 lane=brain；非 brain lane（如 nav）報錯（與 `pawai demo` 路由一致）。
- 歸屬：實作 ticket 落 [Lane 3 CLI plan](2026-06-13-lane3-cli-v2-completion-plan.md)（與 `pawai demo mode online|offline`、`pawai status` brain runtime 區塊同批）；本計畫只定義介面契約。

### 8.3 Studio current-phase indicator（新增，不大改 UI）
- 資料來源：`/state/brain`（`_publish_brain_state` `:2211`）payload 加 `demo_phase` 欄位（若未有），Studio 訂閱顯示。
- UI：右上/狀態列一個唯讀小 chip（`s2_greet` 等），顏色區分 quiet/active；**不加互動、不加切換按鈕**（切換仍走 CLI/param，避免 UI 誤觸）。
- 歸屬：Studio 顯示細節與 Lane 3 `pawai status` brain runtime 區塊（顯示 `ism_shadow_enabled/ism_enabled/ism_stage_2*/demo_phase/gesture_enabled/stranger_alert_enabled`）共用同一份 brain runtime 真相。

---

## 9. 與 Lane 1 stage 2a 協調（不衝突）

| 面向 | 本計畫（Conductor）| Lane 1 stage 2a |
|---|---|---|
| phase 詞彙表 | **擁有**（定義 5 幕 canonical + alias） | 消費（同一張 `PHASE_ALLOWED_KINDS`） |
| 裁決路徑 | legacy `_phase_allows`（`:334-335`，frozenset 查表） | `ism_stage_2a_demo_phase` on 時改走 `interaction_state.phase_allows`（`:337-342`） |
| 切換清理 | **擁有**（§7 helper） | 不動清理 |
| 控制面 | **擁有**（param/CLI/Studio） | 不動控制 |
| byte-identical 退路 | `ism_enabled` off + `demo_phase=all` | 同 |

關鍵：`_phase_allows`（`:333-351`）**已是 dual-path**——legacy frozenset 與 ISM policy 查的是**同一張 `PHASE_ALLOWED_KINDS`**。本計畫擴充這張表（加 5 幕 key + alias）後，**2a on/off 行為仍等價**（同表同語義），不需 Lane 1 改 code。alias 解析放在 `_canonicalize_phase`（詞彙層），對 2a 透明。**前置依賴**：本計畫的 §6.1 表擴充必須先合，Lane 1 2a 才有完整 5 幕可接管。

---

## 10. Tasks

> 每 Task 標記 [pure software] / [Jetson needed] / [Go2 motion needed]；含 tests + HITL checklist + rollback。能力分級見 §2。

### T-C1 `PHASE_ALLOWED_KINDS` 擴充 5 幕 + alias 解析 [pure software]｜needs-HITL
- `interaction_state.py:33` 加 `s1_nav`/`s2_greet`/`s3_pose_object`/`s5_safety` 四個 canonical key（`s4_gesture` 已存在）；保留 `s2_face`/`s3_object`/`all`/`quiet`。
- 新 `canonicalize_phase(phase) -> str`（alias→canonical），`phase_allows` 與 `_phase_allows` 在查表前先 canonicalize。
- `brain_node.py:331` `_DEMO_PHASES` 自動含新 key（frozenset 衍生，無須改）；`:539` 讀取沿用。
- tests：`s2_face` 與 `s2_greet` allow 集合相同；`s3_object`==`s3_pose_object`；`s1_nav`/`s5_safety` allow=∅；unknown→現行為（不回歸）。
- HITL：Jetson `ros2 param set demo_phase s2_face` 與 `s2_greet` 都接受、行為一致（trace 看 suppress 集合）。
- rollback：revert 表擴充；alias 解析是純加法，移除後回 5-key 原表。

### T-C2 切換清理 helper `_apply_phase_transition` [pure software]｜needs-HITL
- `brain_node.py:311-321` callback 內 phase 變更後呼叫 §7 helper。
- 重用 `_on_reset_context`（`:2190-2209`）清理語義 + 加 gesture cooldown 清除 + 可選 object/greet cooldown。
- tests：切 phase 後 `pending_confirm.state != PENDING`、`active_plan is None`、gesture cooldown 清空；`attention` 保留不變；`demo_phase=all`→`all`（同值）不觸發 helper（byte-identical）。
- HITL：s4 confirm 在飛時切到 s5 → pending_confirm 被 cancel（trace `phase_switch:s5_safety`）；s3 重錄 take 切 `s3_object`→`s3_pose_object` → cup 台詞第二 take 仍觸發。
- rollback：callback 不呼叫 helper（回到「只改字串」現行為，等價今天的 G2）。

### T-C3 `pawai demo phase <phase>` CLI（介面契約，實作歸 Lane 3）[pure software]
- 本計畫只定義 §8.2 契約（client 端 phase 白名單 + lock/lane 檢查 + 包 `ros2 param set`）。
- tests（Lane 3 conftest 風格）：未知 phase 本地報錯不發 SSH；非 brain lane 報錯；合法 phase → 組出正確 `ros2 param set` 指令（mock SSH）。
- HITL：見 Lane 3 + runbook。
- rollback：CLI 是純加法 subcommand；移除不影響 `ros2 param set` 直接用法。

### T-C4 `/state/brain` 帶 `demo_phase` + Studio indicator [pure software]｜needs-HITL
- `_publish_brain_state`（`:2211`）payload 確認含 `demo_phase`（若無則加）；Studio 訂閱顯示唯讀 chip（§8.3）。
- tests：brain_state payload 含 `demo_phase` 字串；Studio 元件 render 對應 chip（前端單測）。
- HITL：Jetson 切 phase → Studio chip 即時反映；不提供切換按鈕。
- rollback：payload 欄位是加法（向下相容）；Studio chip 可 feature-flag 隱藏。

---

## 11. Pure software tasks（彙整）

- T-C1（表擴充 + alias）、T-C2（切換清理 helper）、T-C3（CLI 契約）、T-C4（brain_state 欄位 + Studio chip）全為 [pure software]，**可在 WSL 開發機完成 + 單測綠**，不需 Jetson。
- 全部 byte-identical 退路：`demo_phase=all` + `ism_enabled` off + 不切 phase = 現行為。

---

## 12. Jetson / Go2 HITL tasks

> 全部需 Roy 在場。先決條件（handoff 2026-06-13 EOD）：**先確認 Go2 停穩 + `pawai demo stop` 清場**（剛發生 goto 撞牆 e-stop），nav stack 與 brain demo **8GB 互斥不能同跑**；D435 有 MIPI/Hardware Error → brain demo 前可能要重插 D435 USB。

### H-C1 五幕詞彙逐幕驗證 [Jetson needed]｜needs-HITL
- 逐一 `ros2 param set /brain_node demo_phase <phase>`，看 trace suppress 集合符合 §6.2。
- checklist：s1_nav/s5_safety 三 kind 全 suppress；s2_greet 只 greet 過；s3_pose_object 只 object 過；s4_gesture 只 gesture 過；alias（s2_face/s3_object）行為等價。
- rollback：切回 `demo_phase=all`。

### H-C2 切換清理真機驗 [Jetson needed]｜needs-HITL
- s4 confirm 在飛 → 切 s5 → 確認 pending_confirm 被清、不黑洞；s3 重錄 take → cup 台詞再觸發。
- checklist：trace 看到 `phase_switch:*` cancel；active_plan 清空；attention 不被清（人還在框內不需重進場）。
- rollback：T-C2 disable（回手動 `/brain/reset_context`）。

### H-C3 confirm flow 觸發手勢差異重驗 [Go2 motion needed]｜needs-HITL（高注意）
- **目標路徑 thumbs_up→OK→wiggle，但 HITL#2 實際驗的是 peace→OK→WeGo**（§8 + master）。本幕需在 s4_gesture 下確認到底哪條路徑會動 Go2。
- checklist：runbook 明標「驗過的觸發手勢 vs 目標手勢」；`peace_wego_confirm` / `thumbs_up_demo_ack` param 狀態確認；pending_confirm 30s timeout 不黑洞；**Go2 會動，需備 e-stop**。
- rollback：`gesture_enabled false` 即時關 in-flight confirm（`:426`）。

### H-C4 CLI + Studio indicator 真機 [Jetson needed]｜needs-HITL
- `pawai demo phase s3_pose_object` → Jetson param 改 + Studio chip 反映。
- checklist：lock/lane 路由正確；打錯 phase 本地擋下；chip 即時。
- rollback：改回 `ros2 param set` 直接用。

---

## 13. Tests

- **單測（pure，WSL 可跑）**：`interaction_executive/test/` 加 phase 表/alias/清理 helper 測試（沿用既有 ISM-free 純測風格，`interaction_state.py` 無 rclpy 依賴）；CLI 測試走 Lane 3 conftest（網路封鎖 + mock SSH）。
- **回歸護欄**：`demo_phase=all` + `ism_enabled` off → 既有 brain 測試全綠（byte-identical）；ISM stage 2a on/off 在新表下 parity（與 Lane 1 共驗）。
- **trace 驗證**：`pawai evidence pull` 拉 JSONL，grep `phase:s5_safety:gesture` 等 reason 存在且值域正確。
- **HITL**：H-C1~H-C4（§12），全需 Roy 在場。

---

## 14. Rollback

| 層 | rollback |
|---|---|
| 表擴充（T-C1）| revert 加的 4 key + alias 解析 → 回 5-key 原表 |
| 清理 helper（T-C2）| callback 不呼叫 helper → 回「只改字串」（手動 `/brain/reset_context`）|
| CLI（T-C3）| 移除 subcommand → `ros2 param set` 直接用 |
| Studio chip（T-C4）| feature-flag 隱藏 / payload 欄位向下相容保留 |
| 全域 | `ism_enabled` off + `demo_phase=all` + 不切 phase = byte-identical 現行為 |

任一 Task 可獨立 revert，互不依賴（T-C1 是 T-C3/T-C4 顯示正確 phase 名的前置，但 revert T-C1 不會讓 T-C2 清理失效）。

---

## 15. Done criteria

- [ ] `PHASE_ALLOWED_KINDS` 含 5 幕 canonical + alias，單測證明 alias↔canonical byte-identical（T-C1）。
- [ ] 切 phase 自動清 pending_confirm + active_plan + gesture cooldown，attention 保留，單測 + H-C2 綠（T-C2）。
- [ ] `pawai demo phase <phase>` 契約定義完成，實作 ticket 落 Lane 3，client 白名單擋打錯字（T-C3）。
- [ ] `/state/brain` 帶 `demo_phase`，Studio 唯讀 chip 反映 current phase（T-C4）。
- [ ] H-C1~H-C4 在 Roy 在場真機驗過（needs-HITL），confirm 觸發手勢差異於 runbook 明標。
- [ ] `ism_enabled` off + `demo_phase=all` 回歸測試證明 byte-identical。
- [ ] 與 Lane 1 2a 確認同表接管 parity（無 code 衝突）。

---

## 16. Execution order

1. **T-C1**（表擴充 + alias）— 前置，Lane 1 2a 與 CLI/Studio 都依賴正確 phase 詞彙。
2. **T-C2**（切換清理 helper）— 解 G2，是 demo 換幕/換 take 不污染的核心。
3. **T-C4**（brain_state `demo_phase` 欄位）— 解鎖 Studio chip + Lane 3 status 區塊。
4. **T-C3**（CLI 契約）— 交棒 Lane 3 實作。
5. **H-C1 → H-C2 → H-C4 → H-C3**（HITL，先低風險詞彙/清理/顯示，**H-C3 Go2 motion 最後且需 e-stop**）。

純軟體（1-4）可在 6/18 前先合 + 單測綠（needs-HITL 標記）；HITL（5）排進 [roy-hitl-queue](../archive/runbook-legacy/2026-06-13-roy-hitl-queue.md)，**且必須在確認 Go2 停穩 + nav/brain stack 不同跑後才開**。

---

## 17. 6/18 presentation impact

- **正面**：五幕詞彙落地後，操作員可一鍵切幕（`pawai demo phase s2_greet`），demo「照順序、不搶話」可操作性大增；換 take 不再被上一段 confirm/cup 污染；Studio chip 讓觀眾/評審看得到「現在第幾幕」。
- **誠實分級**：phase gate 本身 = **proven**（6/10 用過）；五幕詞彙 + 自動清理 + CLI + chip = **needs-HITL**（新 code，6/18 前單測綠 + 待 Roy 真機重驗）；ISM policy 接管 = Lane 1。**未經 H-C1~H-C4 重驗前，對外只講「phase gate 已用於錄影」，不宣稱「五幕指揮全自動」**。
- **保守邊界**：s5_safety 的 backflip 拒絕走 SafetyLayer（phase-independent），**不因 phase 擋掉 reject**——這點要在 demo 講清「安全鏈不受場景開關影響」。
- **nav 連動**：s1_nav 幕對應 nav 移動，**今天剛撞牆（goto 0.3m 走歪）**——s1 幕本身只保證 brain 靜默（`quiet`），nav 是否上場由 [s1 nav plan](2026-06-13-s1-low-risk-navigation-plan.md) 的 fallback 階梯（遙控輔助 → Studio 證據 → 純影片）決定。**Conductor 不替 nav 背書「自主短距移動」**。
- **退路保底**：任何環節失靈，`demo_phase=all` + `ism_enabled` off 回到 6/10 已驗過的現行為，不開天窗。
