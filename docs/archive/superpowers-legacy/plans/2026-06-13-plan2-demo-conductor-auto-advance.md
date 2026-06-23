# Plan2 — Demo Conductor / Auto-Advance / Manual Floor

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫 ID：**plan2**　角色：Cloud/Fable = planner+reviewer；Codex = builder（依本 packet 實作，不擴 scope、不改 runtime-claim、無 Roy 授權＋e-stop 不得發 Go2 motion）
>
> **本份是「可執行版」**，把同群的設計文件 [`2026-06-13-demo-phase-conductor-plan.md`](2026-06-13-demo-phase-conductor-plan.md)（FLOOR 詞彙/清理設計）落成 Codex 可直接做的 task packet，**並新增 ENHANCEMENT（`auto_advance_enabled` per-phase，預設 OFF）的自動推進指揮**。
>
> **上游策略**：[`2026-06-13-demo-flow-reliability-master-plan.md`](2026-06-13-demo-flow-reliability-master-plan.md)（Q1-Q6 鐵律）
> **平行依賴（不重複其 task，僅引用 ID）**：
> - **plan4**（Studio hidden five-phase buttons + phase chip UI + gateway `demo_phase` publisher）— 本計畫只**定義 brain 側 `/brain/demo_phase` String subscriber 契約**，UI/gateway 由 plan4 擁有。
> - **online/offline fallback plan**（每幕 canned phrase 表 + `llm_timeout 15s→6s` + `openrouter_gemini_timeout_s` 一致化 + WAV 預渲染）— 本計畫的 timeout→canned-rescue 觸發點**消費**該份的 canned 表，不自行定義台詞文字。
> - **s1-low-risk-navigation plan**（s1_nav 幕對應 nav stack 三層 fallback、T0 URDF 修復、initialpose SOP、n=3 motion gate）— 本計畫的 `s1_nav` 幕只保證 brain 端 `quiet`，**不替 nav 背書自主移動**。
> - **operator runbook plan**（逐幕六欄操作表、四階回退梯、dry-run）。
> - **Lane 1 Brain ISM staged-enable plan**（stage 2a = 同一張 `PHASE_ALLOWED_KINDS` 的 ISM policy 接管）— 本計畫擁有「詞彙/清理/控制/auto-advance」，2a 擁有「policy 接管」，同表不衝突。
>
> **Code 現實基準（已逐行查證 2026-06-13）**：
> - `interaction_executive/interaction_executive/interaction_state.py:33` `PHASE_ALLOWED_KINDS`（5 key frozenset 表）、`:42` `phase_allows`（unknown→視同 all）。
> - `interaction_executive/interaction_executive/brain_node.py:311-321` runtime set callback（已收 `demo_phase`、unknown 拒絕保留舊值）、`:331` `_DEMO_PHASES`、`:333-351` `_phase_allows`（dual-path：legacy frozenset + ISM 2a 同表）。
> - 三條自發社交早退：`:1342` `gesture_enabled` gate → `:1348` `_phase_allows("gesture")`；`:1747` `_phase_allows("greet")`；`:1945` `_phase_allows("object")`。
> - greet 細節：`:1775-1782` `greet_require_sitting` 硬依賴 sitting window；`:1785-1789` `greet_cooldown_s` per-person cooldown。
> - 清理路徑：`:2190-2209` `_on_reset_context`（清 pending_confirm `:2197-2199`、object dedup `:2203-2206`、active_plan `:2207`；**不清** attention `:2193`；末發 ISM shadow `:2209`）。
> - param declare：`greet_require_sitting=True :490`、`greet_sitting_window_s=3.0 :491`、`greet_cooldown_s=20.0 :492`、`demo_phase="all" :496`、`gesture_enabled=True :465`、`chat_wait_ms=1500 :439`。
> - 既有 subscriber：`/brain/reset_context`（Empty）、`/brain/gesture_enabled`（Bool `:430`）。
> - timeout（online/offline plan 擁有，本計畫只引用）：`llm_bridge_node.py:201 llm_timeout=15.0`、`tts_node.py:153 openrouter_gemini_timeout_s` dataclass=60.0 dead-default、`:989` env declare=6.0 為實際生效值。

---

## 1 Goal

把 `demo_phase` 機制（現為「最小外科 phase gate」，`PHASE_ALLOWED_KINDS`）做成 6/18 五幕 live demo 的**場景指揮（Conductor）**，分兩層交付（Q6 layered）：

**FLOOR（P0，保證出貨、先做）** — 這一層獨立就是一個能跑的 live demo：
1. **五幕詞彙**：`PHASE_ALLOWED_KINDS` 擴成 `s1_nav / s2_greet / s3_pose_object / s4_gesture / s5_safety`，舊名 `s2_face`/`s3_object` 作 alias（byte-identical）。
2. **切換即清場**：phase 真正變更後跑 `_apply_phase_transition`，**必清** `pending_confirm` + `active_plan` + gesture cooldown，並 **trace transition type**；切幕同時清狀態是硬需求。
3. **brain 側 `/brain/demo_phase` String subscriber 契約**（給 plan4 的 hidden 按鈕用）；`ros2 param set /brain_node demo_phase` 仍是 last-resort backup。

**ENHANCEMENT（P1，`auto_advance_enabled` per-phase 旗標，預設 OFF，疊在 FLOOR 上）** — 讓 demo「看起來自動」（Q3 主線）：
4. per-phase guard/trigger（face known 0.5-1s→greet、cup 0.5-1s→remind、gesture 僅 S4、pose=bonus）、per-phase `max_wait_s` 表、timeout→canned-rescue、trace transition types（`real_trigger`/`timeout_canned_rescue`/`operator_skip`/`video_fallback`）。
5. **修 gotcha #1**：greet 目前只在 unknown→known **轉變**觸發；auto-advance 進 s2 時 Roy 已是 known → greet 不會再觸發。s2 必須「**進幕時若 known face 在框**」就觸發（不靠 transition）。
6. **修 gotcha #2**：greet 目前**硬依賴** sitting（commit f2a0df4）；Q4 要 sitting 只當 bonus。`s2_greet` 進幕設 `greet_require_sitting=false`（face-only），sitting 移到 `s3_pose_object` 當 bonus。

**四階回退梯（Q6）**：auto-advance → Studio hidden buttons（plan4）→ `ros2 param set` → `demo_phase=all` + 影片。

**byte-identical floor 鐵律**：`auto_advance_enabled` 全 OFF + `demo_phase=all` + `ism_enabled` off = 現行為（~955 測試綠）。

**非目標**：不擴 phase 去 gate 安全鏈、不接管事件優先序（Lane 1 的 2b-2d）、不重寫 brain 裁決、不擁有 Studio UI（plan4）、不定 canned 台詞文字（online/offline plan）、不替 nav 背書（s1-nav plan）。

---

## 2 Current state（code 實證，file:line）

| 主題 | 事實 | 來源 |
|---|---|---|
| phase 表 | `PHASE_ALLOWED_KINDS = {all:{greet,object,gesture}, s2_face:{greet}, s3_object:{object}, s4_gesture:{gesture}, quiet:∅}` | `interaction_state.py:33` |
| phase_allows | unknown phase → `allowed is None → True`（容錯成 all） | `interaction_state.py:42-51` |
| runtime callback | `:311-321` 已收 `demo_phase`：`.strip().lower()`，unknown 拒絕保留舊值並 warn，回 `SetParametersResult(successful=True)`；**只改字串、不觸發任何 reset**（G2） | `brain_node.py:311-321` |
| dual-path gate | `_phase_allows`：legacy frozenset 查 `PHASE_ALLOWED_KINDS`；`ism_stage_2a_demo_phase` on 時改走 `interaction_state.phase_allows`（同表）；suppress 走 `_suppressed(gate="demo_phase", reason=f"phase:{phase}:{kind}")` | `brain_node.py:333-351` |
| 三早退 | gesture `:1342`(gesture_enabled)→`:1348`(phase)；greet `:1747`；object `:1945` | `brain_node.py` |
| greet 硬依賴 sitting | `greet_require_sitting`(`:490` 預設 True) → `:1775-1782` 若最近 `greet_sitting_window_s`(3s) 無 sitting 就 suppress | `brain_node.py:1775` |
| greet 只在轉變觸發 | greet 在 `_on_face` 內、`:1745` `unknown_face_first_seen=None` 之後；觸發點是 known-face 進場 + per-person `greet_cooldown_s`(20s) cooldown（`:1786`）→ steady-state 不重發（要遮臉~5s 再回） | `brain_node.py:1745-1789` |
| 清理語義 | `_on_reset_context`：pending_confirm cancel `:2197-2199`、object dedup clear `:2203-2206`、active_plan=None `:2207`；**不清** attention `:2193`；末送 `IsmTrigger.OPERATOR{"op":"reset"}` `:2209` | `brain_node.py:2190-2209` |
| gesture_enabled 關閉清 confirm | `:426-428` 關閉時若 PENDING 一併 cancel | `brain_node.py:426` |
| timeout 現值 | `llm_timeout=15.0`（`llm_bridge_node.py:201`）；`openrouter_gemini_timeout_s` dataclass=60.0 dead-default（`tts_node.py:153`），env declare=6.0 為實際生效（`:989`）；`chat_wait_ms=1500`（`brain_node.py:439`） | 多檔 |

**能力分級（現況）**：
- phase gate（現有 3 kind 抑制）= **proven**（6/10 demo 已用 `demo_phase s3_object` 錄影）。
- 五幕詞彙 / 切換清理 / `/brain/demo_phase` subscriber / auto-advance = **needs-HITL**（本計畫新 code，6/18 前單測綠 + 待 Roy 真機重驗）。

**Gaps**：

| # | Gap | 影響 |
|---|---|---|
| G1 | phase 詞彙與五幕不齊（`s2_face`≠`s2_greet`、無 `s1_nav`/`s5_safety`） | 操作員講 s5 但 code 沒有，易切錯 |
| G2 | 切 phase 不清 pending_confirm/active_plan/gesture cooldown | 換幕/換 take 被上一段污染（confirm 黑洞、cup 台詞被吃、wiggle 殘留） |
| G3（gotcha #1）| greet 只在 unknown→known 轉變觸發 | auto s2 進幕時 Roy 已 known → greet 永不再觸發、s2 自動不開口 |
| G4（gotcha #2）| greet 硬依賴 sitting（f2a0df4） | Q4 要 sitting 當 bonus；sitting 不穩 s2 不開口 |
| G5 | 無 auto-advance；現只能手動切幕 | demo 看起來像手動遙控（Q3 要看起來自動） |
| G6 | 無 brain 側 `/brain/demo_phase` String subscriber | plan4 hidden 按鈕無接點（現只有 param set） |

---

## 3 Scope

- **詞彙層**：`PHASE_ALLOWED_KINDS` 加 4 canonical key（`s1_nav`/`s2_greet`/`s3_pose_object`/`s5_safety`；`s4_gesture` 已存在）+ `canonicalize_phase()` alias 解析（`s2_face→s2_greet`、`s3_object→s3_pose_object`）。
- **清理層**：`_apply_phase_transition(new_phase, old_phase, *, clear_object, clear_greet)` helper，phase 變更後呼叫；**必清** pending_confirm + active_plan + gesture cooldown；trace transition type。
- **控制層（brain 側）**：新 `/brain/demo_phase`（`std_msgs/String`）subscriber，收到合法 phase → 套用（含清理）+ trace；非法 phase 拒絕保留舊值。`ros2 param set` 路徑沿用。
- **ENHANCEMENT 層**：`auto_advance_enabled`（per-phase frozenset 旗標，預設 OFF）、per-phase guard/trigger/`max_wait_s`/timeout→canned-rescue、transition-type trace；gotcha #1（進幕 known-face greet）、gotcha #2（s2 sitting=false / s3 sitting=bonus）。
- **退路層**：所有新行為 default-OFF，`auto_advance_enabled=∅` + `demo_phase=all` + `ism_enabled` off = byte-identical。

---

## 4 Forbidden scope

- 不擴 phase 去 gate 安全鏈 / explicit input / Studio `skill_request`（永遠 phase-independent，`:326-330` 鐵律；`s5_safety=quiet` **不**擋 SafetyLayer reject）。
- 不接管事件優先序、不動 `_PREEMPTIBLE_BY`、不開 ISM 2b/2c/2d（Lane 1）。
- **不擁有 Studio UI / gateway publisher**（plan4）；本計畫只定 brain 側 subscriber 契約。
- **不定 canned 台詞文字 / 不改 `llm_timeout` / `openrouter_gemini_timeout_s` 數值**（online/offline plan 擁有）；本計畫只在 timeout→rescue 觸發點**呼叫**該份提供的 canned 路徑。
- 不碰 nav 行為、不替 nav 背書「自主短距移動」（s1-nav plan）。
- 不做 phase 自動排程跨幕（auto-advance 只在**單一幕內**從信號觸發到 canned-rescue；不自動「走完 s1 跳 s2」——跨幕一律操作員手動切，符合 runbook 保守姿態）。
- 不收緊 `phase_allows` unknown→quiet（會改 Lane 1 2a 同函式語義；runtime callback `:313` 已防呆拒絕 unknown，保 byte-identical）。
- **不發任何 Go2 motion / goto / cmd_vel**（H-2C 例外，且需 Roy 授權 + e-stop）。
- 不宣稱自主導航 / 全自動 live demo / fallen 偵測 / 2m 物體 / 可靠色彩 / 19 色。

---

## 5 Tasks

> 每 Task：id｜task_type｜P0/P1/P2｜exact files｜exact tests｜rollback｜demo_impact｜needs_roy｜needs_go2_motion。**無 task 缺 tests 或 rollback。**

### FLOOR（P0）

#### T2-1 `PHASE_ALLOWED_KINDS` 擴五幕 + `canonicalize_phase` alias 解析
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`interaction_executive/interaction_executive/interaction_state.py`
- **內容**：`PHASE_ALLOWED_KINDS` 加 `s1_nav:∅`、`s2_greet:{greet}`、`s3_pose_object:{object}`、`s5_safety:∅`（`s4_gesture` 已有；保留 `s2_face`/`s3_object`/`all`/`quiet`）。新 `canonicalize_phase(phase:str)->str`（`s2_face→s2_greet`、`s3_object→s3_pose_object`，其餘原樣）。`phase_allows` 查表前先 `canonicalize_phase`（語義不變：unknown 仍→all）。
- **exact tests**：`interaction_executive/test/test_phase_conductor.py`
  - `phase_allows("s2_face","greet") == phase_allows("s2_greet","greet") == True`
  - `phase_allows("s3_object","object") == phase_allows("s3_pose_object","object") == True`
  - `phase_allows("s1_nav", k) == False for k in {greet,object,gesture}`；`s5_safety` 同
  - `phase_allows("s4_gesture","gesture")==True`、`phase_allows("s4_gesture","greet")==False`
  - `phase_allows("typo_xyz","greet")==True`（unknown→all 不回歸）
  - `canonicalize_phase("s2_face")=="s2_greet"`、`canonicalize_phase("all")=="all"`
- **rollback**：`git revert <sha>` 回 5-key 原表；alias 純加法移除即回。
- **demo_impact**：FLOOR；操作員/runbook/plan4 用得到 `s5_safety` 等正確詞彙。
- **needs_roy**：否（單測級）；HITL 驗證見 H-1A。
- **needs_go2_motion**：否

#### T2-2 `_apply_phase_transition` 切換清理 helper + trace
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`
- **內容**：新 `_apply_phase_transition(self, new_phase, old_phase, *, clear_object=None, clear_greet=None)`。在 runtime set callback（`:311-321`）內 phase 真正變更（`new != old` 且通過 `_DEMO_PHASES` 驗證）後呼叫。重用 `_on_reset_context` 清理語義：
  - `with self._lock:` ① pending_confirm：`if state==PENDING → cancel(reason=f"phase_switch:{new_phase}")`（等價 `:2197-2199`）② active_plan：`self._state.active_plan = None`（`:2207`）③ gesture cooldown：清 `self._state.last_alert_ts` 內 gesture 相關 key（**必清**）④ `clear_object`（預設由目標幕決定，進/重錄 s3 為 True）→ 清 `_object_remark_seen` + `last_alert_ts.pop("object_remark")`（`:2203-2206`）⑤ `clear_greet`（預設進 s2 為 True）→ 清 `last_alert_ts` 內 `greet_known_person:*` per-person key。**不清** attention（`:2193`）。
  - 出鎖後送 ISM shadow `IsmTrigger.OPERATOR{"op":"reset"}`（等價 `:2209`，never-raises）。
  - 全程 never-raises：每子步驟 try/except，失敗只 log，callback 不可炸。
  - trace：發既有漏斗 trace（如 `_emit_trace` 或 `_suppressed` 同管道）一筆 `transition`，欄位 `from_phase`/`to_phase`/`cleared=[pending_confirm,active_plan,gesture_cd,...]`。**不新增 trace schema**，沿用既有 JSONL（`gate`/`reason`/`demo_phase` 欄位）。
- **exact tests**：`interaction_executive/test/test_phase_conductor.py`（node-level 用既有 ISM-free helper 或 rclpy mock；若需 node 構造走 `test/` 既有 pattern）
  - 切 phase（s4→s5）後 `_pending_confirm.state != PENDING`、`_state.active_plan is None`、gesture cooldown key 清空
  - `attention` 物件未被修改（`:2193` 保留）
  - `demo_phase=all`→`all`（同值）不呼叫 helper（byte-identical：mock helper 斷言未被呼叫）
  - `clear_object=False` 時 `_object_remark_seen` 未清；`=True` 時已清
  - helper 內任一子步驟 raise → callback 仍回 `SetParametersResult(successful=True)`（never-raises）
- **rollback**：callback 不呼叫 helper（回「只改字串」現行為＝今天 G2）；單行 `if new!=old: self._apply_phase_transition(...)` 註解掉即回。
- **demo_impact**：FLOOR；換 take / 換幕不被上一段 confirm/cup/wiggle 污染。
- **needs_roy**：否（單測級）；真機驗證 H-1B。
- **needs_go2_motion**：否

#### T2-3 `/brain/demo_phase` String subscriber（brain 側契約）
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`
- **內容**：新 subscriber `/brain/demo_phase`（`std_msgs/String`，QoS 與 `/brain/reset_context`/`/brain/gesture_enabled` 同 default reliable depth 10）。callback `_on_demo_phase_msg(msg)`：`value = canonicalize_phase(msg.data.strip().lower())`；若 `value in _DEMO_PHASES` → 走與 param-callback 相同的「變更 + `_apply_phase_transition`」路徑（共用一個內部 `_set_demo_phase(value)` helper，避免 param/topic 兩套清理邏輯漂移）；非法 → warn 保留舊值。**契約**（給 plan4）：plan4 gateway 收 Studio hidden 按鈕 → publish `std_msgs/String{data:"s2_greet"}` 到 `/brain/demo_phase`。本計畫不碰 gateway/UI。
- **exact tests**：`interaction_executive/test/test_phase_conductor.py`
  - publish `"s2_face"` → `demo_phase=="s2_greet"`（canonicalize）+ helper 被呼叫
  - publish `"S5_SAFETY "`（大小寫/空白）→ `demo_phase=="s5_safety"`
  - publish `"bogus"` → `demo_phase` 不變 + warn log + helper 未呼叫
  - param-set 與 topic 走同一 `_set_demo_phase`（斷言兩路徑清理一致）
- **rollback**：移除 subscriber 建立行（`create_subscription(... /brain/demo_phase ...)`）；param set 路徑不受影響。
- **demo_impact**：FLOOR；plan4 hidden 按鈕的接點；四階回退梯第 2 階（Studio buttons）落地依此。
- **needs_roy**：否；真機 H-1C（與 plan4 聯驗）。
- **needs_go2_motion**：否

### ENHANCEMENT（P1，`auto_advance_enabled` 預設 OFF，疊在 FLOOR 上）

#### T2-4 `auto_advance_enabled` per-phase 旗標 + gotcha #1（進幕 known-face greet）
- **task_type**：pure_software
- **優先級**：P1
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`
- **內容**：
  - 新 param `auto_advance_phases`（`std_msgs` 不適用 → 用 `declare_parameter("auto_advance_phases", [])`，STRING_ARRAY；空=全 OFF=byte-identical）。helper `_auto_advance_on(phase)->bool = canonicalize_phase(phase) in set(self.auto_advance_phases)`。
  - **gotcha #1 修法**：在 `_set_demo_phase(value)` 套用後，若 `_auto_advance_on("s2_greet")` 且新 phase 是 `s2_greet`：呼叫新 `_maybe_fire_phase_entry_greet()` —— 讀 world snapshot 最近一個 **stable known face**（不靠 unknown→known transition），若框內有 stable known face 且不在 `greet_cooldown_s` cooldown，**直接走 greet 提案路徑**（與 `:1784` 後段相同 emit，但入口是 phase-entry 而非 face-transition）。auto OFF 時此函式不被呼叫（行為不變）。
  - **「stable known face」數值定義（消歧義，避免 detection churn 漏觸）**：判定 = 來自 `/event/face_identity` 的 **`identity_stable` 事件**（既有事件，6/8 commit `f2a0df4` 的 greet gate 已用此事件），其底層條件 = **同一 known 身份 `sim ≥ 0.7` 連續 ≥3 frame**（與既有 face node `identity_stable` 判定一致；本計畫**不重定義門檻**，只引用該事件最近一筆是否在「框內 + 未過期」）。phase-entry 讀 world snapshot 的「最近一個 `identity_stable` 且 timestamp 在 `greet_sitting_window_s` 等價的新鮮度窗（預設取 face 事件最近 ~3s）內」→ 視為 stable。若 snapshot 內無新鮮 `identity_stable`（detection churn / 剛進框未穩）→ **不觸發 entry-greet**（不誤觸），改由 `max_wait_s` timeout→canned-rescue 補位（T2-5，never dead air）。
  - per-phase guard 表（資料結構，不含 timer）：`_PHASE_GUARD = {"s2_greet":{"trigger":"face_known","min_dwell_s":0.5..1.0}, "s3_pose_object":{"trigger":"object_cup","min_dwell_s":0.5..1.0,"pose_bonus":True}, "s4_gesture":{"trigger":"gesture_highconf","scope":"s4_only"}, "s5_safety":{"trigger":"keyword_safety"}}`。本 task 只落 s2 entry-greet；s3/s4 guard 接點留 T2-5（timer/timeout）。
- **exact tests**：`interaction_executive/test/test_phase_conductor.py`
  - auto OFF（`auto_advance_phases=[]`）：`_set_demo_phase("s2_greet")` 不呼叫 `_maybe_fire_phase_entry_greet`（mock 斷言）→ byte-identical
  - auto ON（`["s2_greet"]`）+ world 有 stable known face（新鮮 `identity_stable` 事件，sim≥0.7×≥3frame）+ 不在 cooldown → entry-greet emit 一次
  - auto ON + known face 在 cooldown → 不重發（`_in_cooldown` 斷言）
  - auto ON + 框內無 known face → 不發（不誤觸）
  - **auto ON + 只有過期/churn 的 face snapshot（無新鮮 `identity_stable`）→ 不發 entry-greet**（驗 stable 數值定義：churn 不誤觸，靠 T2-5 timeout canned 補位）
  - `_auto_advance_on("s2_face")` 與 `("s2_greet")` 等價（canonicalize 後）
- **rollback**：`auto_advance_phases=[]`（預設）即全停 entry-greet；移除 `_maybe_fire_phase_entry_greet` 呼叫行。
- **demo_impact**：ENHANCEMENT；s2 自動開口（看起來自動，Q3）。**6/17 彩排決定是否 enable**。
- **needs_roy**：否（單測）；真機 H-2A（auto s2 entry-greet 觸發）。
- **needs_go2_motion**：否

#### T2-5 gotcha #2（s2 sitting=false / s3 sitting=bonus）+ per-phase `max_wait_s` + timeout→canned-rescue + transition-type trace
- **task_type**：pure_software
- **優先級**：P1
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`
- **內容**：
  - **gotcha #2 修法（精確 save/restore，3 階狀態機）**：在 `_set_demo_phase(value)` 內處理 `greet_require_sitting` 的存還原，**精確變數名 + 順序**：
    - **進 `s2_greet` 前**：`self._greet_sitting_pre_s2 = self.greet_require_sitting`（記住進場前值；初值 = param declare 預設 `True`，`:490`），然後 `self.greet_require_sitting = False`（face-only trigger，與 `:1775` gate 對齊）。
    - **進 `s3_pose_object` 時**：`self.greet_require_sitting = self._greet_sitting_pre_s2`（還原成進場前值），並把 sitting 當 s3 的 **bonus**（不阻擋 object remark；現 object 路徑 `:1945` 本就不硬依賴 sitting，sitting 只豐富台詞 → 確認不引入新硬依賴）。
    - `_greet_sitting_pre_s2` init 值 = `True`（建構時設，與 default 對齊；若從未進 s2 就進 s3，還原為 True = byte-identical）。
  - **此 toggle 對 auto-advance 與 manual floor 兩種進幕路徑都生效**：toggle 寫在 `_set_demo_phase`（param-set / `/brain/demo_phase` topic / auto-advance 共用入口，見 T2-3），**不綁 `auto_advance_enabled`**——只要 phase 進入 `s2_greet`（不論 auto 或 manual Studio 鈕 / `ros2 param set`），`greet_require_sitting` 就設 False；進 `s3_pose_object` 還原。⟹ **manual floor 模式下 s2 也不會因 sitting 缺席 hardlock**（解 review「manual entry 可能 hardlock on sitting」）。**唯一例外（byte-identical 退路）**：`demo_phase` 從未離開 `all`（非 demo 模式、不切五幕）時不動 `greet_require_sitting`（保 default True）。
  - **per-phase `max_wait_s` 表**（Q4）：`_PHASE_MAX_WAIT_S = {"s1_nav":(10,20),"s2_greet":(3,5),"s3_pose_object":(5,8),"s4_gesture":(8,10),"s5_safety":(3,5)}`（區間，runbook 取單值）。新 per-phase one-shot timer（`self.create_timer` + `cancel`，**不跨幕**），auto ON 進幕啟動；若 `max_wait_s` 內無 real trigger（該幕對應信號未到）→ 觸發 **timeout→canned-rescue**：走 online/offline plan 提供的 canned 路徑（`say_canned`/該幕 phrase），**不等 15s LLM**（Q5：rescue 是 rule-based，0s 等待）。
  - **transition-type trace**（Q3/Q4）：每次幕內推進記一筆 trace，type ∈ `{real_trigger, timeout_canned_rescue, operator_skip, video_fallback}`。`operator_skip`/`video_fallback` 由操作員動作（plan4 hidden 按鈕 / 切 `demo_phase`）標記；本 task 落 `real_trigger`/`timeout_canned_rescue` 兩型 + 預留 `operator_skip` 標記入口。
  - **gesture 僅 S4**：auto guard `s4_gesture` 的 gesture trigger 只在 `demo_phase==s4_gesture` 生效（既有 `_phase_allows("gesture")` 已保證 s4 外 suppress；本 task 不放寬）。
  - **safety = keyword/text, no LLM**：`s5_safety` 的 rescue/trigger 走既有 SafetyLayer reject（rule-first），**不經 LLM**（Q5 安全永 rule-first）。
- **exact tests**：`interaction_executive/test/test_phase_conductor.py`
  - **3 階狀態機鏈（精確變數）**：初始 `greet_require_sitting==True` → 進 s2 後 `_greet_sitting_pre_s2==True` 且 `greet_require_sitting==False` → 進 s3 後 `greet_require_sitting == _greet_sitting_pre_s2 == True`（斷言還原值等於初值）
  - **manual 路徑也套用（解 hardlock）**：`auto_advance_phases=[]`（auto OFF）下，用 `_set_demo_phase("s2_greet")`（模擬 manual Studio 鈕 / param set）→ `greet_require_sitting==False`（s2 greet 不因 sitting 缺席 hardlock）；再 `_set_demo_phase("s3_pose_object")` → 還原 True。**驗 toggle 不綁 auto_advance_enabled。**
  - `demo_phase` 從未離開 `all`（不切五幕）→ `greet_require_sitting` 維持 default True（byte-identical 退路）
  - timer：注入假時鐘，進 s2 後 `max_wait_s` 內無 trigger → `say_canned`/rescue 路徑被呼叫一次 + trace type=`timeout_canned_rescue`
  - real trigger 先到 → timer cancel，trace type=`real_trigger`，rescue 不被呼叫
  - 切幕時上一幕 timer 被 cancel（不跨幕；切 s2→s3 斷言舊 timer cancel）
  - s5 rescue 不呼叫 LLM bridge（mock 斷言 LLM 未被呼叫）
- **rollback**：`auto_advance_phases=[]` → timer/guard/rescue 全不啟動，`greet_require_sitting` 保 default True；移除 timer 建立行。
- **demo_impact**：ENHANCEMENT；IRON RULE never dead air（timeout 一定有 canned 補位）。
- **needs_roy**：否（單測）；真機 H-2B（max_wait 逾時補 canned）。
- **needs_go2_motion**：否

### HITL（Jetson / Go2，全需 Roy 在場）

#### H-1A 五幕詞彙逐幕驗證
- **task_type**：jetson
- **優先級**：P0
- **exact files**：（驗證，無 code 改）；證據寫 `runbook` evidence 區
- **內容/tests**：逐一 `ros2 param set /brain_node demo_phase <phase>`，`pawai evidence pull` 看 trace suppress 集合符合 §6.2（plan conductor）：s1_nav/s5_safety 三 kind 全 suppress；s2_greet 只 greet；s3_pose_object 只 object；s4_gesture 只 gesture；alias（s2_face/s3_object）等價。
- **legacy-alias 防呆（dry-run + runbook 約定）**：alias `s2_face`/`s3_object` 雖 byte-identical 等價，**live flow / runbook / 操作員 SOP 一律只用 canonical `s2_greet`/`s3_pose_object`**（避免操作員念舊名混淆）。dry-run（plan4 P4-11）須 grep runbook 五幕表確認**無** `s2_face`/`s3_object` 出現在操作步驟欄（只在「alias 等價」說明欄出現）。trace 驗證接受 alias canonicalize 後值。
- **rollback**：切回 `demo_phase=all`。
- **demo_impact**：FLOOR 驗收。**needs_roy**：是。**needs_go2_motion**：否。

#### H-1B 切換清理真機驗
- **task_type**：jetson
- **優先級**：P0
- **內容/tests**：s4 confirm 在飛 → 切 s5 → trace 看 `phase_switch:s5_safety` cancel、`active_plan` 清空、attention 不被清（人在框不需重進場）；s3 重錄 take 切 `s3_object`→`s3_pose_object` → cup 台詞第二 take 仍觸發。
- **rollback**：T2-2 disable（回手動 `/brain/reset_context`）。
- **demo_impact**：FLOOR 驗收。**needs_roy**：是。**needs_go2_motion**：否。

#### H-1C `/brain/demo_phase` subscriber + plan4 聯驗
- **task_type**：jetson
- **優先級**：P0
- **內容/tests**：`ros2 topic pub --once /brain/demo_phase std_msgs/String '{data: s3_pose_object}'` → param 改 + trace；plan4 hidden 按鈕（若已合）→ 同效果；打錯 phase 本地/brain 端擋下保留舊值。
- **rollback**：改回 `ros2 param set` 直接用。
- **demo_impact**：FLOOR；四階回退第 2 階。**needs_roy**：是。**needs_go2_motion**：否。

#### H-2A auto s2 entry-greet 真機驗（gotcha #1/#2）
- **task_type**：jetson
- **優先級**：P1
- **前置**：face re-enroll sim≥0.7（見 master/runbook P0-15）；`auto_advance_phases:=["s2_greet"]`。
- **內容/tests**：Roy 已在框（known）→ `ros2 param set demo_phase s2_greet`（或 topic）→ **不需遮臉重進場**即 greet（驗 gotcha #1）；`greet_require_sitting` 自動 False，不坐也問候（驗 gotcha #2）；20s cooldown 內不重發。
- **rollback**：`auto_advance_phases:=[]`（回手動）；`greet_require_sitting:=true`。
- **demo_impact**：ENHANCEMENT；6/17 彩排決定 s2 是否 enable auto。**needs_roy**：是。**needs_go2_motion**：否。

#### H-2B max_wait 逾時補 canned 真機驗
- **task_type**：jetson
- **優先級**：P1
- **內容/tests**：auto ON 進某幕、刻意不給 real trigger（如 s3 不放杯子）→ `max_wait_s` 到 → canned phrase 補位（never dead air）；trace type=`timeout_canned_rescue`；offline 模式下 canned 0s（WAV cache，online/offline plan）。
- **rollback**：`auto_advance_phases:=[]`（無 timer、無 rescue）。
- **demo_impact**：ENHANCEMENT；IRON RULE never dead air 驗收。**needs_roy**：是。**needs_go2_motion**：否。

#### H-2C s4 confirm 觸發手勢 + Go2 wiggle 真機驗（高注意）
- **task_type**：go2_motion
- **優先級**：P1
- **內容/tests**：s4_gesture（auto ON）下確認哪條 confirm 路徑會動 Go2：**目標 thumbs_up→OK→wiggle**，**HITL#2 實際驗的是 peace→OK→WeGo**（`peace_wego_confirm`/`thumbs_up_demo_ack` param 路徑差異）。現場 30s 試目標路徑，失敗即退 proven peace→OK→WeGo。台詞只講「比 OK 我就執行」，不保證手勢類型。pending_confirm 30s timeout 不黑洞。
- **rollback**：`gesture_enabled false` 即時關 in-flight confirm（`:426`）；`pawai demo stop`。
- **demo_impact**：ENHANCEMENT；S4 confirm beat。**needs_roy**：是（**必須授權 + e-stop 就位**）。**needs_go2_motion**：是。

---

## 6 Pure software tasks

T2-1 / T2-2 / T2-3 / T2-4 / T2-5 全 pure_software，**WSL 開發機可完成 + 單測綠，不需 Jetson**。全 byte-identical 退路：`auto_advance_phases=[]` + `demo_phase=all` + `ism_enabled` off + 不切 phase = 現行為。
- 受 blocking flake8 約束（新增 core .py / 改 brain_node.py，max-line=100）。
- 改完跑 `python3 -m pytest interaction_executive/test/ -v` + `colcon build --packages-select interaction_executive`。

---

## 7 Jetson tasks（no-motion）

H-1A / H-1B / H-1C / H-2A / H-2B 均 Jetson、**無 motion**（純 param/topic 切換 + trace 觀測 + 感知信號）。先決：`pawai demo stop` 清 nav stack（剛 goto 撞牆 e-stop）、brain demo stack 與 nav stack **8GB 互斥不同跑**、D435 MIPI error 可能需重插 USB。

---

## 8 Go2 HITL tasks（motion, e-stop）

僅 H-2C 含 Go2 motion（confirm→wiggle/WeGo）。**鐵律**：需 Roy 明確授權 + e-stop 就位；abort 條件：非指令方向動作 / 停不下來 / 機鼻 <0.3m 仍動 → `emergency_stop.py` engage 或 `StopMove(1003)`（**禁 `Damp(1001)` 對運動中 Go2**）。本計畫**不依賴 goto_relative**（s1-nav plan 範疇）。

---

## 9 Tests

- **單測（pure，WSL）**：新 `interaction_executive/test/test_phase_conductor.py`，涵蓋 T2-1~T2-5 上列每條斷言；沿用既有 ISM-free 純測風格（`interaction_state.py` 無 rclpy；node-level 用既有 test pattern / rclpy mock）。
- **回歸護欄**：`auto_advance_phases=[]` + `demo_phase=all` + `ism_enabled` off → 既有 brain 測試全綠（byte-identical，~955）；ISM stage 2a on/off 在新表下 parity（與 Lane 1 共驗）。
- **trace 驗證**：`pawai evidence pull` 拉 JSONL，grep `phase:s5_safety:gesture`、`timeout_canned_rescue`、`real_trigger` 等存在且值域正確。
- **HITL**：H-1A~H-1C（FLOOR）、H-2A~H-2C（ENHANCEMENT），全需 Roy 在場。

指令：
```bash
python3 -m pytest interaction_executive/test/test_phase_conductor.py -v
python3 -m pytest interaction_executive/test/ -v            # 全套不回歸
colcon build --packages-select interaction_executive
source install/setup.zsh                                    # Jetson 用 .zsh
```

---

## 10 Rollback

| 層 | rollback 指令/動作 |
|---|---|
| 表擴充（T2-1）| `git revert <T2-1 sha>` → 回 5-key 原表；alias 純加法 |
| 清理 helper（T2-2）| callback 內 `if new!=old: self._apply_phase_transition(...)` 行註解 → 回「只改字串」現行為 |
| subscriber（T2-3）| 移除 `create_subscription(String, "/brain/demo_phase", ...)` 行 → param set 不受影響 |
| auto-advance（T2-4/T2-5）| `ros2 param set /brain_node auto_advance_phases "[]"` → 全停 entry-greet/timer/rescue；`greet_require_sitting` 保 default True |
| 四階回退梯（Q6 全域）| ① auto-advance → ② Studio hidden buttons（plan4）→ ③ `ros2 param set /brain_node demo_phase <phase>` → ④ `demo_phase=all` + 影片 |
| 全域 byte-identical | `auto_advance_phases=[]` + `demo_phase=all` + `ism_enabled` off + 不切 phase = 6/10 已驗現行為 |

每 Task 可獨立 revert，互不依賴（T2-1 是 T2-3/T2-4 顯示/解析正確 phase 名的前置；revert T2-1 不會讓 T2-2 清理失效）。

---

## 11 Done criteria

- [ ] `PHASE_ALLOWED_KINDS` 含 5 幕 canonical + alias，單測證 alias↔canonical byte-identical（T2-1）。
- [ ] 切 phase 自動清 pending_confirm + active_plan + gesture cooldown，attention 保留，trace 一筆 transition；單測 + H-1B 綠（T2-2）。
- [ ] `/brain/demo_phase` String subscriber 上線，param/topic 共用 `_set_demo_phase`，非法 phase 拒絕；單測 + H-1C 綠（T2-3）。
- [ ] `auto_advance_phases` 預設 `[]`，auto ON 時 s2 進幕 known-face greet 觸發（gotcha #1）、`greet_require_sitting=False`（gotcha #2）；單測 + H-2A 綠（T2-4）。
- [ ] per-phase `max_wait_s` timeout→canned-rescue（never dead air），transition-type trace（real/timeout/operator/video）；單測 + H-2B 綠（T2-5）。
- [ ] `auto_advance_phases=[]` + `demo_phase=all` + `ism_enabled` off 回歸測試證明 byte-identical（~955 綠）。
- [ ] 與 Lane 1 2a 確認同表接管 parity（無 code 衝突）。
- [ ] 對外措辭：phase gate=proven（6/10 用過）；五幕詞彙/清理/subscriber/auto-advance=needs-HITL，未經 H-* 重驗前**不宣稱「五幕指揮全自動」**。

---

## 12 Execution order

1. **T2-1**（表擴充 + alias）— 前置；plan4/CLI/Lane 1 2a 都依賴正確詞彙。
2. **T2-2**（切換清理 helper + trace）— 解 G2，換幕/換 take 不污染核心。
3. **T2-3**（`/brain/demo_phase` subscriber）— 解 G6；plan4 hidden 按鈕接點；FLOOR 完成（**此處已是可跑 live demo**）。
4. **T2-4**（auto 旗標 + gotcha #1 entry-greet）— ENHANCEMENT 起點。
5. **T2-5**（gotcha #2 + max_wait + rescue + transition-type trace）— ENHANCEMENT 完成。
6. **HITL**：H-1A → H-1B → H-1C（FLOOR）→ H-2A → H-2B（ENHANCEMENT no-motion）→ **H-2C 最後（Go2 motion，需 e-stop）**。

純軟體（1-5）6/18 前先合 + 單測綠（needs-HITL 標記）；HITL（6）排進 roy-hitl-queue，**且必須確認 Go2 停穩 + nav/brain stack 不同跑後才開**。6/17 彩排逐幕決定 auto 是否 enable（never bet 6/18 on auto-advance，Q6）。

---

## 13 Codex Implementation Prompt

> Codex：你是 builder。**只實作下列 task packet，不擴 scope、不改 runtime-claim、無 Roy 授權 + e-stop 不發任何 Go2 motion。** 每個 task 小 commit / 小 PR，回報 diff + 測試結果 + 風險。所有 prose 用繁中，code/param/path identifier 原樣。

依序做 T2-1 → T2-2 → T2-3（FLOOR，先交付，這已是能跑的 live demo）→ T2-4 → T2-5（ENHANCEMENT，default OFF）。每步：
1. 改 `interaction_state.py` / `brain_node.py` 對應段落（行號見 §2/§5）。
2. 在 `interaction_executive/test/test_phase_conductor.py` 寫 §5 列的每條斷言（先寫測試，紅→綠）。
3. `python3 -m pytest interaction_executive/test/ -v` 全綠（**含既有測試不回歸**）+ `colcon build --packages-select interaction_executive`。
4. flake8 新/改 core .py max-line=100 過。
5. 回報：diff 摘要 + 測試輸出 + byte-identical 證明（`auto_advance_phases=[]`+`demo_phase=all` 路徑未動）+ 風險清單。

**禁止**：不碰 Studio UI/gateway（plan4）、不改 `llm_timeout`/`openrouter_gemini_timeout_s` 數值（online/offline plan）、不定 canned 台詞文字、不碰 nav、不收緊 `phase_allows` unknown→quiet、不擴 phase 去 gate 安全鏈。

---

## Codex Implementation Packet

**exact files**
- `interaction_executive/interaction_executive/interaction_state.py`（T2-1：`PHASE_ALLOWED_KINDS` 表 + `canonicalize_phase`）
- `interaction_executive/interaction_executive/brain_node.py`（T2-2 helper、T2-3 subscriber + `_set_demo_phase`、T2-4 `auto_advance_phases` + `_maybe_fire_phase_entry_greet`、T2-5 `greet_require_sitting` 切換 + `_PHASE_MAX_WAIT_S` timer + rescue + transition-type trace）
- `interaction_executive/test/test_phase_conductor.py`（新檔，所有 §5 斷言）

**exact commands**
```bash
python3 -m pytest interaction_executive/test/test_phase_conductor.py -v
python3 -m pytest interaction_executive/test/ -v
colcon build --packages-select interaction_executive
flake8 interaction_executive/interaction_executive/interaction_state.py interaction_executive/interaction_executive/brain_node.py --max-line-length=100
```

**acceptance**
- 新測試全綠；既有 `interaction_executive/test/` 全綠（不回歸）。
- byte-identical：`auto_advance_phases=[]` + `demo_phase=all` 不呼叫 helper/timer/entry-greet（mock 斷言）。
- canonicalize：`s2_face`/`s3_object` 與 canonical 行為等價（同 frozenset）。
- never-raises：helper/timer/subscriber callback 任一子步驟 raise，外層 callback 仍正常回傳。
- 每 task 一 commit/PR，可獨立 revert（§10）。

## Cloud Review Checklist（Fable 審 Codex 產出）

- [ ] `PHASE_ALLOWED_KINDS` 5 幕 + alias 正確；`s1_nav`/`s5_safety` allow=∅。
- [ ] `phase_allows` unknown→all **未被收緊**（保 byte-identical，未動 Lane 1 2a 語義）。
- [ ] `_apply_phase_transition` **必清** pending_confirm + active_plan + gesture cooldown；**不清** attention（`:2193`）。
- [ ] param set 與 `/brain/demo_phase` topic 共用 `_set_demo_phase`（無兩套清理漂移）。
- [ ] auto OFF（`auto_advance_phases=[]`）時 entry-greet/timer/rescue/`greet_require_sitting` **皆不啟動**（逐條 mock 斷言）。
- [ ] gotcha #1：entry-greet 不靠 unknown→known transition；無 known face 不誤觸。
- [ ] gotcha #2：s2 設 `greet_require_sitting=False`、s3 還原 `_greet_sitting_pre_s2`（進場前值）；**toggle 對 auto + manual 兩路徑都生效**（不綁 `auto_advance_enabled`，manual Studio 鈕進 s2 也不 hardlock on sitting）；`demo_phase` 從未離 `all` 保 default True。
- [ ] timeout→canned-rescue 走 rule-based（**不等 15s LLM**）；s5 rescue 不經 LLM。
- [ ] transition-type trace ∈ `{real_trigger,timeout_canned_rescue,operator_skip,video_fallback}`；**未新增 trace schema**。
- [ ] timer 不跨幕（切幕 cancel 上一幕 timer）。
- [ ] 無 overclaim：PR/commit 描述只講「code merged + unit tests green (needs-HITL)」，不宣稱 proven / 全自動。
- [ ] 未碰 forbidden（plan4 UI、timeout 數值、canned 文字、nav、安全鏈 phase gate）。

## Stop Conditions（Codex 命中即停、回報、等 Fable 指示）

- 需改 `start_full_demo_tmux.sh` / `executive.yaml` / `.claude/skills/` 才能過測（→ 須獨立 PR + demo smoke full green + Roy 核可，不在本 packet）。
- 既有 brain 測試出現非預期紅（byte-identical 被破）。
- 發現需動 `phase_allows` unknown→quiet 才能達標（→ Lane 1 協調，停）。
- 任務暗示要發 Go2 motion / 改 nav / 動 SafetyLayer 才能驗（→ 停，HITL 範疇）。
- canned 台詞文字 / timeout 數值需要本計畫定義（→ online/offline plan 範疇，停）。
- Studio UI / gateway publisher 需本計畫實作（→ plan4 範疇，停）。

## Required Evidence（交付前必附）

- `pytest interaction_executive/test/test_phase_conductor.py -v` 全綠輸出。
- `pytest interaction_executive/test/ -v` 全套不回歸輸出。
- `colcon build --packages-select interaction_executive` 成功輸出。
- byte-identical 證明：`auto_advance_phases=[]`+`demo_phase=all` 下 helper/timer/entry-greet 未被呼叫的 mock 斷言通過。
- diff 摘要（每 task 一 commit/PR）+ 風險清單（含「needs-HITL，未經 H-* 不得宣稱 proven」）。
- HITL 階段（Roy 在場）：`pawai evidence pull` 的 JSONL 證據（H-1A 五幕 suppress 集合、H-1B `phase_switch:*` cancel、H-2B `timeout_canned_rescue` trace）。

## Rollback Plan

見 §10 表。最小回退：`ros2 param set /brain_node auto_advance_phases "[]"`（停 ENHANCEMENT）→ `ros2 param set /brain_node demo_phase all`（停 FLOOR phase gate）→ 四階梯第 4 階 `demo_phase=all` + 影片。每 PR 可 `git revert <sha>` 獨立回退，互不依賴。
