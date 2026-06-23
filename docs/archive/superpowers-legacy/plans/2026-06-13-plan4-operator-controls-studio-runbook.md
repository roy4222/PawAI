# Plan4 — Operator Controls / Studio / Runbook（操作面與操作員手冊）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 角色：Cloud/Fable = planner + reviewer（**不寫 code**）；Codex = builder（依 task packet 實作 + 寫測試 + 跑測試 + 小 commit/PR）
> 計畫群：PawAI Demo Flow Reliability Sprint｜本份 plan_id：**plan4**
> 上游決策鎖定：Q1–Q6（見本份每 Task 引用）；READER DIGEST A/B/C/D 已內化

---

## 角色分工（每份子計畫共同鐵律）

- **Cloud/Fable（本文件作者）**：讀 source、設計、切 task packet、定義 tests/rollback/stop-conditions、review Codex 產出、對抗式驗 overclaim/demo-break/safety、指示修正、整合。**不改任何 runtime code。**
- **Codex（builder）**：依 task packet 實作、寫測試、跑測試、小 commit/PR、回報 diff + test-result + risk。**不擴 scope、不改 runtime-claim、無 Roy 授權 + task 明標前不送 Go2 motion。**

---

## 0. 與其他子計畫的邊界（cross-plan，不重複其 Task）

本 plan **擁有「控制面 + 操作員 runbook」**，不重做別人已有的 Task：

| 依賴對象 | 本 plan 消費什麼 | 不在本 plan 做 |
|---|---|---|
| **plan2 Conductor**（`2026-06-13-demo-phase-conductor-plan.md`）| ① 五幕 phase 詞彙表 `PHASE_ALLOWED_KINDS`（含 `s1_nav/s2_greet/s3_pose_object/s4_gesture/s5_safety` + alias）；② brain 端 `/brain/demo_phase` 控制契約 + `_apply_phase_transition` 清理 helper；③ `_publish_brain_state` 加 `demo_phase` 欄位 | **不**改 `interaction_state.py` 表、**不**寫 brain-side phase 清理邏輯 |
| **plan-fallback**（`2026-06-13-online-offline-fallback-plan.md`）| ① brain `offline_mode` param 語義；② 五幕 canned 表；③ timeout 收緊值 | **不**改 `tts_node.py`/`llm_bridge_node.py`/`brain_node.py` 的 offline 短路邏輯 |
| **plan-s1-nav**（`2026-06-13-s1-low-risk-navigation-plan.md`）+ **nav incident**（`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-motion-incident-root-cause-plan.md`）| ① nav T0/R1/R2/R5 根因與修法歸屬；② initialpose yaw SOP；③ S1 三層 fallback 階梯；④ NOT_DEMO_READY 標籤 | **不**改 nav code、**不**送 goto/cmd_vel |
| **plan-lane3-cli**（`2026-06-13-lane3-cli-v2-completion-plan.md`）| `pawai demo phase` / `pawai demo mode` / `pawai status` brain 區塊 / `pawai face delete` 的 CLI 實作 | **本 plan 的 P4-12 face delete .npz 修法是 runbook+HITL SOP，CLI 落地歸 Lane 3** |
| **nav claim wording**（`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-618-claim-wording.md`）| S1–S8 可講句 / F1–F10 禁講句 | 不新增 claim 詞彙 |

> **本 plan 唯一新寫 runtime code 的範圍**：Studio gateway 的 `/api/demo_phase`（POST/GET）+ `/api/offline_mode`（POST/GET）publisher、對應 frontend HIDDEN 五幕按鈕 + offline toggle + phase chip、以及 runbook markdown 文件。**brain 端 subscriber 由 plan2 提供契約**（本 plan 的 gateway publisher 對該契約發布）。

---

## 1. Goal（目標）

讓**一名操作員**在 6/18 五幕 live demo 全程握有**四階 rollback 階梯的中段兩階**（Q6）：

1. **Studio HIDDEN 五幕按鈕**（write）：在 gateway 新增 `/api/demo_phase`（POST/GET）+ publisher，鏡像現有 `publish_gesture_enabled`（`studio_gateway.py:806`）→ 發布到 brain 端 `/brain/demo_phase`（`std_msgs/String`，subscriber 契約來自 plan2）。每顆按鈕**先發 `/brain/reset_context`（清場）再切 phase**。這是 demo 失速時的**手動 FLOOR fallback**（隱藏、不花俏；自動指揮失效就靠它）。
2. **offline_mode toggle**（write）：同鏡像 pattern，gateway `/api/offline_mode`（POST/GET）→ brain `offline_mode` param（語義歸 plan-fallback）。
3. **ros2 param set backup**（document）：每顆 Studio 按鈕都有等價 `ros2 param set /brain_node demo_phase <phase>` 文件化備援（rollback 階梯第三階）。
4. **`pawai demo phase` CLI**：**post-6/18**（Q3），本 plan 只在 runbook 標 PLANNED + workaround，不實作。
5. **Operator runbook**：五幕 SOP（每幕：trigger / online+offline TTS / verify / trace / rollback）、操作員**角色分工**（誰開 Go2、誰盯 trace+按隱藏鈕、誰用 Studio skill_request 觸發 S5）、平台支援表（Win/WSL/mac/Jetson）、`.env` CRLF 假成功檢查、8GB stack 交接（依 plan1 co-run profiling 結果）、dry-run。

**對外誠實鐵律**（READER A/B/C 三法）：AFK 完成只能說「code merged + 單測綠（needs-HITL）」；只有 Roy 在場真機 HITL 過才算 proven。對外 claim 一律走 nav-618-claim-wording S1–S8/F1–F10。

---

## 2. Current state（code 實證，file:line）

### 2.1 已存在、可直接鏡像的 gateway 機制

- **gesture_enabled publisher 樣板**（要鏡像的對象）：`studio_gateway.py:806` `publish_gesture_enabled(self, enabled)`；publisher 建立於 `:247-248` `self._gesture_enabled_pub = self.create_publisher(Bool, "/brain/gesture_enabled", 10)`；cache `:251` `self._gesture_enabled_last: bool | None = None`；snapshot `:816`。
- **reset_context publisher**（要在每顆 phase 按鈕內呼叫的對象）：`:241-242` `self._reset_pub = self.create_publisher(Empty, "/brain/reset_context", 10)`；method `:801` `publish_reset_context()`。
- **route 樣板**：`:1255` `POST /api/gesture_enabled`（publish + cache + WS 廣播 `brain:gesture_enabled`）；`:1275` `GET /api/gesture_enabled`；`:1246` `POST /api/reset`。
- **pydantic payload 樣板**：`:866` `class GestureEnabledPayload(BaseModel): enabled: bool`。
- **WS 廣播樣板**：`:1265-1271`（`event_type: gesture_enabled`，`data: {enabled}`）。

### 2.2 brain 端控制 topic / param（gateway 發布目標）

- **`/brain/demo_phase` String subscriber**：**目前不存在**（plan2 T-C? 新增的契約）。現況只有 `ros2 param set /brain_node demo_phase <phase>`（runtime callback `brain_node.py:311-321`，unknown phase 拒絕保留舊值）。本 plan 的 gateway publisher 對 plan2 的 String subscriber 發布。
- **`/brain/reset_context`**（`std_msgs/Empty`，`brain_node.py:252`）：清 PendingConfirm（`:2199`）+ object dedup（`:2205`）+ active_plan（`:2207`），**不清** attention。
- **`/brain/gesture_enabled`**（`std_msgs/Bool`，`brain_node.py:258`）。
- **`demo_phase` param**：declare `brain_node.py:496` 預設 `all`；讀 `:539`；runtime callback `:311`；`_DEMO_PHASES` 來自 `interaction_state.PHASE_ALLOWED_KINDS`（`:331`）。
- **`offline_mode` param**：**brain_node 目前無此 param**（plan-fallback T-FB-5 新增）。
- **`_publish_brain_state`**（`brain_node.py:2211`，0.5s timer `:261`）payload **目前不含** `demo_phase` / `offline_mode`（已讀 `:2223-2242` 確認）→ Studio phase chip / offline 指示燈的真相欄位需 plan2 T-C4 / plan-fallback 補上。

### 2.3 frontend 已存在的鏡像樣板

- `pawai-studio/frontend/components/chat/gesture-toggle.tsx`：完整三態（ON/OFF/?）toggle，POST `/api/gesture_enabled` + 掛載讀 GET cache + 樂觀更新；用 `authHeaders()`（`@/lib/gateway-auth`）+ `getGatewayHttpUrl()`。**新五幕按鈕 + offline toggle 照此抄。**
- mount 點：`components/chat/chat-panel.tsx:392/431` 已掛 `<GestureToggle />`。
- state-store：`stores/state-store.ts:91` `gestureToggleEnabled`、`:204` setter（新增 `demoPhase` / `offlineMode` 同 pattern）。

### 2.4 CLI 現況

- `tools/pawai_cli/pawai_cli/main.py` 用 **click**；`demo` 是 click group（`demo start|stop`）。**無 `demo phase` / `demo mode` subcommand**（post-6/18，Q3）。
- **face delete B4 bug（已 code 確認）**：`main.py:2017-2018` `face delete` 與 `:2045` `face rebuild` 只 `rm -f .../model_sface.pkl`，**不刪 `.npz`**。
- **`.npz` 是真實 runtime 格式**（已 code 確認，非臆測）：`face_perception/face_identity_node.py:75/77/82` 用 `.npz`（`model_path.with_suffix(".npz")`）；`face_perception/test/test_model_io.py:58` 測 `model_sface.npz`。**repo 內無 `model_sface.npz` 檔案**（它是 Jetson runtime 訓練產物）→ HITL 必須 `ls /home/jetson/face_db/` 確認真實 embedding-cache 檔名（Gotcha #3），**不可在未上機 ls 前斷言 `.npz` 一定存在/一定是這個名字**。

### 2.5 即時硬體狀態（handoff 2026-06-13 EOD，反映進 runbook §開場）

- Jetson nav stack 還在跑（tmux `nav-cap-demo`，9 windows）；剛發生 **goto_relative 0.3m 走歪撞牆**，Roy e-stop。
- D435 **Right MIPI / Hardware Error**（nav 不需 D435；face/vision/object 受影響）。
- nav stack 與 brain demo stack **8GB 互斥**（不可同跑）。

---

## 3. Scope（範圍）

1. gateway `/api/demo_phase`（POST/GET）+ publisher → `/brain/demo_phase`（String），每次發布**先發 reset_context**。
2. gateway `/api/offline_mode`（POST/GET）+ publisher → brain `offline_mode`（鏡像 pattern）。
3. frontend HIDDEN 五幕按鈕（`s1_nav/s2_greet/s3_pose_object/s4_gesture/s5_safety`）+ offline toggle + phase chip（讀 `/state/brain` 的 `demo_phase`）。
4. operator runbook markdown：開場安全前置、五幕六欄 SOP、角色分工、平台表、`.env` CRLF 檢查、8GB stack 交接、dry-run、ros2 param set backup、`.npz` HITL ls SOP。
5. 四階 rollback 階梯文件化（auto-advance → Studio 隱藏鈕 → ros2 param set → demo_phase=all + 影片）。

---

## 4. Forbidden scope（禁止範圍）

- ❌ 不改 `interaction_state.py` phase 表、不寫 brain-side `_apply_phase_transition`（plan2 擁有）。
- ❌ 不改 `tts_node.py` / `llm_bridge_node.py` / brain offline 短路邏輯（plan-fallback 擁有）。
- ❌ 不改 nav code、不送 goto/cmd_vel、**不讓任何 Task 依賴 goto_relative**（NOT_DEMO_READY）。
- ❌ 不實作 `pawai demo phase` / `pawai demo mode` CLI（post-6/18，Q3）。
- ❌ 不大改 Studio UI（隱藏按鈕 + 唯讀 chip，**不**重排主版面）。
- ❌ 不 flip gateway secure-default（route_id sanitize 歸 Security plan；本 plan 的新 route **沿用** gateway 既有 `auth` 機制，env-gated 預設關 = byte-identical）。
- ❌ 不宣稱：自主導航 / 全自動 live demo / 跌倒偵測 / 2m 物體 / 可靠顏色 / 19 色。
- ❌ 不對移動中 Go2 送 Damp(1001)。
- ❌ 任何 Task 不得無 tests + 無 rollback。

---

## 5. Tasks（總表，逐項 task_type + P + demo_impact + needs_roy + needs_go2_motion + files + tests + rollback）

> task_type：`pure_software`（WSL/開發機，無硬體）｜`jetson`（SSH 上 Jetson，無 Go2 motion）｜`go2_motion`（Go2 會動，e-stop 就位）。
> **P0 = FLOOR（Q6，保證出貨、先做）**；P1 = ENHANCEMENT/加值；P2 = post-6/18。

### P4-1　gateway `/api/demo_phase` publisher + route（FLOOR 隱藏鈕後端）
- **task_type**：pure_software｜**P0**｜**demo_impact**：高（手動 FLOOR fallback 的後端，無此則隱藏鈕不通）｜**needs_roy**：否｜**needs_go2_motion**：否
- **files**：`pawai-studio/gateway/studio_gateway.py`（新增 `_demo_phase_pub` create_publisher、`publish_demo_phase()` method、`demo_phase_snapshot()`、`DemoPhasePayload` pydantic、`POST/GET /api/demo_phase` route、WS 廣播 `brain:demo_phase`）
- **設計**：鏡像 `publish_gesture_enabled`（`:806`）。`publish_demo_phase(phase)`：**先 `self._reset_pub.publish(Empty())`（清場）再** publish `String(data=phase)` 到 `/brain/demo_phase`；cache `self._demo_phase_last`。route 端 **client + server 雙重白名單**：phase ∈ {`s1_nav,s2_greet,s3_pose_object,s4_gesture,s5_safety,all,quiet,s2_face,s3_object`}，否則回 `{"ok": False, "error": "invalid_phase"}` 不發布（解 plan2 G3 打錯字）。
- **tests**：`pawai-studio/gateway/test_gateway.py` 新增 — ① POST 合法 phase → publish_demo_phase 被呼叫且 reset 先於 phase（用 mock publisher 記 call order）；② POST 非法 phase → 不 publish + 回 invalid_phase；③ GET 回 cache（None=未切換）；④ WS 廣播 `brain:demo_phase` envelope 正確。指令：`cd pawai-studio/gateway && python3 -m pytest test_gateway.py -v`
- **rollback**：`git revert <sha>`；route + publisher 為純加法，移除後 gateway byte-identical（其他 route 不受影響）。隱藏鈕落地前操作員退 `ros2 param set /brain_node demo_phase <phase>`（P4-9 文件化）。

### P4-2　gateway `/api/offline_mode` publisher + route（FLOOR offline 切換後端）
- **task_type**：pure_software｜**P0**｜**demo_impact**：中（網路降級時的手動切換；env-offline 是 proven 退路）｜**needs_roy**：否｜**needs_go2_motion**：否
- **files**：`pawai-studio/gateway/studio_gateway.py`（新增 `_offline_mode_pub`、`publish_offline_mode(bool)`、`offline_mode_snapshot()`、`OfflineModePayload`、`POST/GET /api/offline_mode`、WS `brain:offline_mode`）
- **設計**：鏡像 gesture toggle。publisher 發布到 brain `offline_mode`（**plan-fallback T-FB-5 定義 brain 端如何消費**——可能是 param 或 `/brain/offline_mode` topic；本 plan 依 plan-fallback 最終契約對齊，**契約未定前 publisher 形態標 TODO-依-plan-fallback**，但 route/cache/WS/test 結構先就緒）。預設 OFF = byte-identical。
- **tests**：`test_gateway.py` — ① POST true → publish_offline_mode(True)；② GET 回 cache；③ WS 廣播。指令同 P4-1。
- **rollback**：`git revert <sha>`；純加法。落地前退啟動前 env override（`LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper ...`，plan-fallback §2.3 proven）。

### P4-3　frontend HIDDEN 五幕按鈕 + offline toggle 元件
- **task_type**：pure_software｜**P0**｜**demo_impact**：高（操作員手動 FLOOR 的前端）｜**needs_roy**：否｜**needs_go2_motion**：否
- **files**：新增 `pawai-studio/frontend/components/operator/demo-phase-buttons.tsx`（五顆按鈕）、`pawai-studio/frontend/components/operator/offline-toggle.tsx`；改 `stores/state-store.ts`（加 `demoPhase` / `offlineMode` + setter，鏡像 `gestureToggleEnabled`）；**mount 點（exact）= `pawai-studio/frontend/components/sheet/dev-panel.tsx`**（`DevPanel()` `:13`，在 `:15` 的 `<div className="flex flex-col">` 內加 `import { DemoPhaseButtons } from "@/components/operator/demo-phase-buttons"` + `import { OfflineToggle } from "@/components/operator/offline-toggle"` 並插入 `<DemoPhaseButtons />` / `<OfflineToggle />`，沿用 `:17` `border-t` section 樣式）。**不**進主 chat-panel（`chat-panel.tsx:392/431` 是 GestureToggle 位置，**不在此加五幕鈕**）→ 符合「hidden, not flashy」Q3
- **設計**：抄 `gesture-toggle.tsx`：`authHeaders()` + `getGatewayHttpUrl()` + POST `/api/demo_phase`（body `{phase}`）/ `/api/offline_mode`（body `{enabled}`）+ 掛載 GET 初始化 + 樂觀更新 + gateway 不在線時靜默不改 state。
- **tests**：`pawai-studio/frontend/components/operator/__tests__/demo-phase-buttons.test.tsx`（vitest，鏡像 `stores/__tests__/reset-conversation.test.ts`）— ① 點 s2_greet → fetch POST `/api/demo_phase` body `{phase:"s2_greet"}`；② gateway 回非 ok → 不改 state；③ offline toggle 翻轉。指令：`cd pawai-studio/frontend && npm test`
- **rollback**：`git revert <sha>`；元件不 mount 進任何 page 即等於不存在；dev-panel feature-flag 隱藏。

### P4-4　Studio current-phase chip + offline 指示燈（唯讀）
- **task_type**：pure_software｜**P1**｜**demo_impact**：中（觀眾/操作員看得到「現在第幾幕」；落地前用 `ros2 param get`）｜**needs_roy**：否｜**needs_go2_motion**：否
- **files**：新增 `pawai-studio/frontend/components/operator/phase-chip.tsx`（讀 `/state/brain` 的 `demo_phase`，唯讀，**無切換按鈕**）；`stores/state-store.ts` 從 `brain:state` WS 事件 set `demoPhase`/`offlineMode`
- **前置依賴**：`/state/brain` payload 須含 `demo_phase`（plan2 T2-x 補 `_publish_brain_state` 欄位）+ `offline_mode`（plan-fallback）。**本 chip 只消費，不負責加欄位。** 欄位未到前 chip 顯示 `?`（鏡像 gesture toggle 的 null 態）。
- **HITL 顯式驗收閘（P4-12 ①）**：彩排/HITL 時，**若 chip 持續顯示 `?`（demo_phase/offline_mode 欄位未由 plan2/plan3 補上）→ 標為 known-limitation、不阻 6/18 交付**（chip 是唯讀 P1 觀眾輔助，非 FLOOR）；操作員改用 `ros2 param get /brain_node demo_phase` 確認當前幕。**P4-12 checklist 須明列「chip 顯示真 phase」為 P1 驗收項、`?` = degraded 但可上**（不把 chip `?` 當 go/no-go blocker）。
- **tests**：`phase-chip.test.tsx` — ① brain:state 帶 `demo_phase=s3_pose_object` → chip 顯示 s3；② 無欄位 → 顯示 `?`。指令同 P4-3。
- **rollback**：`git revert <sha>`；feature-flag 隱藏；落地前 `ros2 param get /brain_node demo_phase`（P4-9 文件化）。

### P4-5　operator runbook：開場安全前置（第 0 步）
- **task_type**：pure_software（寫文件）｜**P0**｜**demo_impact**：高（nav stack 沒清/Go2 沒停穩則 brain 段起不來）｜**needs_roy**：否（內容）/ HITL 當天 Roy 照跑｜**needs_go2_motion**：否（撰寫）
- **files**：新增 `docs/runbook/2026-06-18-operator-runbook.md` §0（開場）
- **內容**：依序（任一不過即停）：① 確認 Go2 停穩；仍動 → `python3 scripts/emergency_stop.py engage`（**禁 Damp(1001)**）；② `pawai demo stop`，殘留 → `pawai demo stop --force` + 逐一 `pkill -9 go2_driver; pkill -9 reactive_stop; pkill -9 nav2; pkill -9 robot_state; pkill -9 sllidar`（`killall python3` 只殺 launch parent）；`tmux ls` 確認 `nav-cap-demo` 不在；③ 清 orphaned active goal（重啟 navcap launch）；④ **8GB stack 交接決策**（依 **plan1 co-run profiling 結果**，見 P4-13）；⑤ D435 健康 `ros2 topic hz /camera/.../color/image_raw`，MIPI error → 重插 USB 換 port；⑥ e-stop 就位；⑦ demo mode 決策（offline 用 env override，CLI `pawai demo mode` PLANNED）；⑧ `pawai demo start` 後 **`tmux ls` + `ros2 node list` 數 node**（不信 CLI `✓ Demo running` 假成功）；⑨ `ros2 param set /brain_node stranger_alert_enabled false`（6/9 卡死真兇）+ 確認 `demo_phase=all`。
- **tests**：P4-11 dry-run review（旁人照唸不卡）。
- **rollback**：N/A（文件）；nav 清不掉 → `pawai demo stop --force` + 手動 pkill（已寫進 §0）。

### P4-6　operator runbook：五幕六欄 SOP
- **task_type**：pure_software（寫文件）｜**P0**｜**demo_impact**：高｜**needs_roy**：否（內容）｜**needs_go2_motion**：否（撰寫）
- **files**：`docs/runbook/2026-06-18-operator-runbook.md` §1（五幕表）
- **內容**：每幕一節，六欄：**切 phase（Studio 隱藏鈕 / ros2 param set 備援）/ 預期 TTS(online) / 預期 TTS(offline canned) / 驗證點(topic+trace) / trace reason / rollback**。對映 plan2 §6.2 + plan-fallback §9 五句，**逐字與 `PHASE_ALLOWED_KINDS`（`interaction_state.py:33`）一致**。每幕標能力分級（S1=FAILED 今天撞牆 / S2/S3/S4=needs-HITL / S5=proven 6/10）。Q4 max_wait_s（S1 10–20s / S2 3–5s / S3 5–8s / S4 8–10s / S5 3–5s）+ Q5 三層語音（Layer1 快觸發 / Layer2 LLM ≤1.5–2s / Layer3 canned）寫進每幕「失速處置」欄。**內含 Gotcha：S2 greet 進場觸發**（見 P4-7）。
- **tests**：對照表逐幕 allow/suppress 一致性（P4-11 + 文件 self-check）。
- **rollback**：N/A（文件）。

### P4-7　operator runbook：三洞段（face / confirm / nav）+ Gotcha 反映
- **task_type**：pure_software（寫文件）｜**P0**｜**demo_impact**：高（三洞沒寫清 → 現場 overclaim/翻車）｜**needs_roy**：否（內容）｜**needs_go2_motion**：否（撰寫）
- **files**：`docs/runbook/2026-06-18-operator-runbook.md` §2（三洞）
- **內容**：
  - **§2.1 S2 greet 兩個 Gotcha**（必寫）：① greet **目前只在 unknown→known 轉變觸發、非 steady-state**（`brain_node._on_face`，6/8 commit `f2a0df4`）→ **auto-advance 進 S2 時 Roy 已是 known → greet 不會重觸發**；runbook 標「重現 greet 需遮臉/離框 ~5s 再回來」，並標**這是 plan2/Lane1 需處理的「phase-entry-when-known-face-present 觸發」缺口**（本 plan 只記錄+提供操作 workaround，不改 brain code）。② greet **目前硬依賴 sitting**（commit `f2a0df4`）；Q4 要 sitting 只當 bonus → runbook 標「S2 設 `ros2 param set /brain_node greet_require_sitting false`（face-only 觸發）」，sitting 移到 S3 當 bonus。
  - **§2.2 confirm 路徑差異**：目標 `thumbs_up→OK→wiggle`（未驗）vs HITL#2 驗過 `peace→OK→WeGo`；現場先試目標、失敗立刻退 peace；PendingConfirm 30s 不黑洞（`brain_node.py:186` timeout_s=30）；誤觸 → `gesture_enabled false`（cancel in-flight，`:426/428`）。
  - **§2.3 face_db 衛生 + `.npz` HITL ls SOP**（Gotcha #3）：`pawai face delete`/`rebuild` 只刪 `.pkl`（`main.py:2018/2045`），**`.npz` 是 Jetson runtime 訓練產物**（`face_identity_node.py:75/77` 確認用 `.npz`；repo 無此檔）→ **HITL 第一步必 `ls /home/jetson/face_db/` 確認真實 embedding-cache 檔名後**才定刪除清單；workaround 手動 `rm -f /home/jetson/face_db/model_sface.npz`（若 ls 證實存在）；幽靈目錄 `_backup*`/`old*` 移出 face_db 外；發表日早上重 enroll → rebuild → 重啟 face node → `pawai face test` sim ≥ 0.7。CLI 自動刪 npz 歸 Lane 3。
  - **§2.4 nav motion FAILED**（引 nav incident plan，不重做）：今天 0.3m 撞牆，根因多因（T0 URDF `/tf_static` authority / R1 AMCL yaw / R2 overshoot 0.5→1.04m / R5 yaw-blind gate）；**不靠 goto_relative**；live-motion 選項僅 DriveOnHeading（body-frame）且須 T0 fix + D1–D5 綠 + θ_error<5° + e-stop + n=3；否則 S1 退遙控+Studio 證據 → 影片。
- **tests**：P4-11 dry-run + 與 nav incident plan / nav claim wording 交叉一致性檢查。
- **rollback**：N/A（文件）。

### P4-8　operator runbook：操作員角色分工
- **task_type**：pure_software（寫文件）｜**P0**｜**demo_impact**：高（一人手忙腳亂 = 開天窗）｜**needs_roy**：是（分工人選 Roy 拍）｜**needs_go2_motion**：否（撰寫）
- **files**：`docs/runbook/2026-06-18-operator-runbook.md` §3（角色分工）
- **內容**：定義至少三角色：① **Driver（Roy）**：S1 開 Go2（遙控/initialpose/e-stop）；S4 confirm 觸發手勢；② **Trace Watcher**：盯 Studio Evidence Center + `/state/brain` chip，phase 串台時**按 Studio 隱藏五幕鈕**切回正確幕、必要時按 reset；③ **S5 Trigger**：用 Studio **skill_request 或文字輸入**送「翻跟斗/backflip」觸發 SafetyLayer reject（explicit input，phase-independent，`brain_node.py:326-330`）。每角色列「手上工具 + 觸發時機 + 失速時誰補位」。標 8GB stack 交接時誰口頭過場（§0 ④ + plan1 結果）。
- **tests**：P4-11 dry-run（三人各自能照角色卡做事）。
- **rollback**：N/A（文件）。

### P4-9　operator runbook：CLI/控制清單 + ros2 param set backup + 平台表
- **task_type**：pure_software（寫文件）｜**P0**｜**demo_impact**：中（操作員要知道在哪打什麼、隱藏鈕掛了的備援）｜**needs_roy**：否｜**needs_go2_motion**：否
- **files**：`docs/runbook/2026-06-18-operator-runbook.md` §4（控制清單 + 平台表）
- **內容**：
  - **每顆 Studio 隱藏鈕 ↔ ros2 param set 等價備援**表（rollback 階梯第三階）：切幕 = `ros2 param set /brain_node demo_phase <s1_nav|s2_greet|s3_pose_object|s4_gesture|s5_safety|all|quiet>`；offline = plan-fallback 定義的 param；清場 = `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}`；看 phase = `ros2 param get /brain_node demo_phase`。
  - PLANNED CLI（`pawai demo phase` / `pawai demo mode` / `pawai status` brain 區塊 / `pawai face delete` 修 .npz）一律標 **PLANNED — Lane 3 / post-6/18**，給 workaround 欄，**不讓操作員照不存在的指令打**。**每個 PLANNED CLI 行必附明確 backup 警語**：`pawai demo phase <p>` 未上線 → 用 `ros2 param set /brain_node demo_phase <p>`（SSH 上 Jetson）；`pawai demo mode offline` 未上線 → 用 `ros2 param set /brain_node offline_mode true`（或啟動前 env override `LLM_ENDPOINT=http://127.0.0.1:1/ ...`，proven）；`pawai status` brain 區塊未上線 → 用 `ros2 param get /brain_node demo_phase`。**操作員看到 PLANNED 必直接讀同列 backup 欄，不得卡等 CLI。**
  - **平台支援表**（Win PowerShell / WSL / macOS / Jetson-only）：`pawai`(SSH wrapper) 在 PS 對 zsh/.env/rsync 脆（CRLF、引號）；`ros2 param set/get`/`ros2 action`/`ros2 topic pub` Win/WSL/mac **原生不可**（無 ROS2 runtime，須 SSH 上 Jetson）；Studio UI 任一桌面瀏覽器可；**結論：操作主控台用 WSL 或 macOS**，所有 ROS2 runtime/Go2/感知一律 Jetson。
  - **`.env` CRLF false-positive 檢查**（6/4 教訓）：`.env` 若 CRLF → `source .env` 撞 `$'\r'` + `set -euo pipefail` 靜默 abort，但 CLI 仍報 `✓ Demo running`（假成功）→ 必跑 `ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local"`；起 demo 後 `tmux ls` + 數 node。
- **tests**：每個既有 CLI 在開發機跑 `--help` 確認存在（`pawai demo --help` 等）；指令：`pawai demo --help && pawai face --help && pawai status --help`
- **rollback**：N/A（文件）。

### P4-10　operator runbook：四階 rollback 階梯 + 誠實底線 + 8GB 交接
- **task_type**：pure_software（寫文件）｜**P0**｜**demo_impact**：高（任一環節失速的退路）｜**needs_roy**：否｜**needs_go2_motion**：否
- **files**：`docs/runbook/2026-06-18-operator-runbook.md` §5（rollback + 誠實底線）
- **內容**：
  - **四階 rollback 階梯（Q6）+ 每階明確 timeout + 每階邊界 canned 補位（never dead air）**：
    - **① auto-advance**（plan-conductor enhancement，per-phase flag）。**timeout = 該幕 `max_wait_s`**（S1 10–20s / S2 3–5s / S3 5–8s / S4 8–10s / S5 3–5s）。auto stall 超過 `max_wait_s` → timeout→canned-rescue **先自動播該幕 canned**（rule-based 0s，plan-conductor T2-5）→ 操作員退 ②。
    - **② Studio 隱藏五幕鈕**（本 plan FLOOR）。**timeout = 按鈕後無 200 OK 確認 > 3s**（Studio 不通）→ 退 ③。**⚠ manual-only never-dead-air**：若操作員在該幕 `max_wait_s` 內**未按鈕**，Trace-Watcher / S5-Trigger 須**立即用 Studio `skill_request` 或文字輸入觸發該幕 canned**（或直接退 ③ `ros2 param set`），**不可乾等操作員**——manual floor 不得因「沒人按」開天窗。
    - **③ `ros2 param set /brain_node demo_phase <phase>`**（backup）。**timeout = param set 無 ack > 2s** → 退 ④。
    - **④ `demo_phase=all` + 影片**（最終保底）。
    - **永不押 6/18 在 auto-advance**（Q6）。每階 timeout 數值 = 上方括號值，操作員角色卡（P4-8）標明誰計時、誰觸發 canned、誰按下一階。
  - 全域退保守：`ros2 param set /brain_node demo_phase all` + `ism_enabled false`（byte-identical，plan2 保證）。
  - TTS 退：`TTS_PROVIDER=piper` 重起 / offline mode / canned。手勢退：`gesture_enabled false`。stranger 退：`stranger_alert_enabled false`。換幕殘留退：reset_context。nav 退影片。face 退 generic greet（sim<0.7）。Studio 掛 → `ros2 param get` + `pawai evidence pull` 看 trace。
  - **8GB stack 交接觀眾感知**：S1（nav 段）與 S2–S5（brain 段）有 stack 交接約 1 分鐘空檔 → 操作員口頭過場 + Studio 展示前段 trace 證據填補，不讓觀眾以為當機。**交接決策依 plan1 co-run profiling**（P4-13）。
  - **誠實底線（runbook 開頭）**：AFK 完成只說「merged + 單測綠（needs-HITL）」；proven 須 Roy 在場真機過；對外 claim 全走 nav-618-claim-wording S1–S8/F1–F10，禁 F1–F10 overclaim。
- **tests**：P4-11 dry-run；每個 rollback 動作對映既有已驗指令（不引入新行為）。
- **rollback**：N/A（文件）。

### P4-11　runbook dry-run review
- **task_type**：pure_software｜**P0**｜**demo_impact**：高（照不下去的步驟必須現在抓出來）｜**needs_roy**：否（旁人即可）/ Roy 終驗｜**needs_go2_motion**：否
- **files**：dry-run notes（附在 runbook 末尾 §6 或獨立 review log）
- **內容**：找一位沒參與的人照 runbook §0–§5 唸一遍，標所有「照不下去 / 指令不存在 / 平台跑不了」的步驟，逐條修。發表日前 48h 完成。
- **tests**：dry-run review notes 存在且所有 blocker 已修。
- **rollback**：N/A。

### P4-12　operator runbook：HITL 五幕全流程 + 控制面真機驗（Roy 在場）
- **task_type**：jetson（S2/S3/S5 無 motion 段）+ go2_motion（S1/S4 段，e-stop 就位）｜**P0**｜**demo_impact**：高（needs-HITL → proven 的唯一閘）｜**needs_roy**：是｜**needs_go2_motion**：是（S1 nav + S4 confirm 段）
- **files**：runbook §7 HITL checklist（不寫 code）
- **內容**：① Studio 隱藏五幕鈕真機切 phase → `/state/brain` chip + trace suppress 集合符合 §6.2；② 每幕只觸發該幕功能、不串台；③ 隱藏鈕「先 reset 再切」真機驗（換幕不污染）；④ offline toggle 真機切（無 silent fail，USB 喇叭非 Megaphone 風險低）；⑤ S2 greet 進場觸發 + greet_require_sitting=false workaround；⑥ S4 confirm 目標 vs peace 路徑（**Go2 會動，e-stop**）；⑦ face re-enroll sim≥0.7（含 `.npz` ls）；⑧ S5 SafetyLayer reject 端到端（proven 復驗）。**先確認 Go2 停穩 + nav/brain 不同跑後才開**（§0）。
- **tests（驗收命令）**：`pawai smoke full`（單測綠 = needs-HITL）；`pawai smoke nav --static`（零 motion wiring）；`pawai face test`（sim≥0.7）；`pawai evidence pull` grep trace reason。
- **rollback**：任一幕失控 → `demo_phase=all` + 影片；Go2 走歪/撞 → e-stop（`emergency_stop.py engage`）+ `pawai demo stop`。

### P4-13　8GB co-run stack 交接決策（消費 plan1 profiling）
- **task_type**：pure_software（寫文件，消費 plan1 結果）｜**P0**｜**demo_impact**：高（S1↔S2 stack 怎麼接決定 S1 形態）｜**needs_roy**：是（決策樹拍板）｜**needs_go2_motion**：否
- **files**：runbook §0 ④ + §5（交接段）
- **內容**：**不自行 profiling**（plan1 擁有 P0 no-motion co-run gate 三 config A/B/C）。本 plan 消費其結論，寫進 runbook 的 stack 交接決策樹（Q2）：C 穩 → S1 免 swap（仍不用 goto_relative，map/LiDAR/pose 當視覺證據）；B 穩 C 不穩 → brain 常駐 + raw LiDAR/Foxglove + 操作員輔助；B 不穩 → S1 純第三人稱 + Studio brain；brain baseline 不穩 → 先修 brain demo、不談 nav。**plan1 結果未出前，runbook 此段標 TODO-依-plan1，預設走「S1 nav 段與 S2–S5 brain 段分段切換」保守路徑。**
- **tests**：與 plan1 profiling 結論交叉一致；P4-11 dry-run。
- **rollback**：N/A（文件）；保守路徑（分段切換）永遠可退。

---

## 6. Pure software tasks（彙整，WSL/開發機可完成 + 單測綠）

P4-1（gateway demo_phase）、P4-2（gateway offline_mode）、P4-3（frontend 五幕鈕+offline toggle）、P4-4（phase chip）、P4-5~P4-10（runbook 文件）、P4-11（dry-run）、P4-13（交接決策文件）。

- gateway 新 route **沿用既有 `auth` 機制**（env-gated 預設關 = byte-identical，`studio_gateway.py:63-66/79`）；不 flip secure-default。
- 新增 core .py 受 blocking flake8（max-line=100）；CI fast gate 跑 speech/vision/gateway 純 Python 測試 + frontend vitest。
- 全部 **byte-identical 退路**：新 route 不被呼叫 + `demo_phase=all` + `offline_mode` off = 現行為。

---

## 7. Jetson tasks（no-motion）

- P4-12 的 S2/S3/S5 段（face / object / SafetyLayer，無 Go2 motion）：SSH 上 Jetson，先確認 nav stack 已停（8GB 互斥）+ D435 健康。
- face_db `.npz` HITL ls（P4-7 §2.3）：`ls /home/jetson/face_db/` 確認真實檔名 → 才定刪除清單。
- offline toggle 真機驗（P4-12 ④）：USB 外接喇叭非 Megaphone，mid-session 切 provider 風險低，仍需驗不卡。
- **禁**：本段不送任何 goto/cmd_vel/motion。

## 8. Go2 HITL tasks（motion, e-stop）

- P4-12 S1 nav 段：**不靠 goto_relative**；live-motion 僅在 nav incident plan 的 T0 fix + D1–D5 綠 + θ_error<5° + e-stop + n=3 全過後才用 DriveOnHeading；否則退遙控+Studio→影片。
- P4-12 S4 confirm 段：Go2 wiggle，**e-stop 就位**；先試 thumbs_up→OK→wiggle，失敗退 peace→OK→WeGo。
- **硬 abort 條件**：非指令方向移動 / 停不下來 / 機鼻 <0.3m 仍動 → 立即 e-stop（`emergency_stop.py engage`，mux pri 255）。**禁 Damp(1001)**。
- **needs_roy = 是、needs_go2_motion = 是**：無 Roy 明確授權 + e-stop 就位前 Codex 不得觸發任何 motion。

---

## 9. Tests（總表）

**pure_software（CI fast gate / 本機）**：
- gateway：`cd pawai-studio/gateway && python3 -m pytest test_gateway.py -v`（P4-1/P4-2 新增 case：reset-before-phase call order、白名單拒非法、cache、WS 廣播）。
- frontend：`cd pawai-studio/frontend && npm test`（P4-3/P4-4 vitest：POST body、gateway 離線靜默、chip 顯示）。
- runbook 一致性：每幕 allow/suppress 逐字對 `interaction_state.py:33`；CLI `--help` 存在性。
- 回歸護欄：新 route 不被呼叫 + `demo_phase=all` + `offline_mode` off → gateway/brain 既有測試全綠（byte-identical）。

**Jetson（no-motion）**：`pawai smoke full` / `pawai smoke nav --static` / `pawai face test`（sim≥0.7）/ `pawai evidence pull` grep trace reason。

**Go2 HITL（motion）**：P4-12 S1/S4 段，Roy 在場 + e-stop。

---

## 10. Rollback（總表）

| 層 | 觸發 | 動作 | 命令 |
|---|---|---|---|
| gateway route | demo_phase/offline route 行為異常 | revert PR | `git revert <sha>` |
| frontend 元件 | 隱藏鈕/chip 異常 | revert / 不 mount / dev-panel flag 隱藏 | `git revert <sha>` |
| 切幕（隱藏鈕掛）| Studio 不通 | 退 ros2 param set | `ros2 param set /brain_node demo_phase <phase>` |
| 換幕殘留 | 上一幕 confirm/plan/dedup 污染 | reset_context | `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}` |
| 全域退保守 | 任一幕失控 | demo_phase=all + ism off | `ros2 param set /brain_node demo_phase all`；`ros2 param set /brain_node ism_enabled false` |
| offline 退 | runtime toggle 失效 | 啟動前 env override（proven） | `LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_full_demo_tmux.sh` |
| nav 退影片 | S1 撞/走歪、n=3 未過 | e-stop → demo stop → 影片 | `python3 scripts/emergency_stop.py engage`；`pawai demo stop` |
| face 退 generic | sim<0.7 | S2 不秀具名 / 還原 backup | `ros2 param set /brain_node greet_require_sitting false` |
| Studio 掛 | UI 不通 | 退 param get + evidence pull | `ros2 param get /brain_node demo_phase`；`pawai evidence pull` |
| 整 stack 退 | Jetson 環境異常 | force stop + 逐一 pkill + clean | `pawai demo stop --force` + `pkill -9 go2_driver; pkill -9 reactive_stop; ...` |

> 每個 rollback 都往**現行已驗行為**退，不引入新行為。

---

## 11. Done criteria（完成判準）

- [ ] gateway `/api/demo_phase`（POST/GET）publisher 鏡像 `publish_gesture_enabled`、**先 reset 再切 phase**、白名單擋非法、WS 廣播；單測綠（P4-1）。
- [ ] gateway `/api/offline_mode`（POST/GET）publisher 就緒、預設 OFF byte-identical；單測綠（P4-2）。
- [ ] frontend HIDDEN 五幕按鈕 + offline toggle mount 進 dev/隱藏區塊、抄 gesture-toggle pattern；vitest 綠（P4-3）。
- [ ] phase chip + offline 指示燈唯讀消費 `/state/brain`，欄位未到顯示 `?`；vitest 綠（P4-4）。
- [ ] runbook §0–§5：開場安全前置 / 五幕六欄 / 三洞（含 S2 greet 進場 + sitting bonus + confirm 差異 + `.npz` ls + nav FAILED）/ 角色分工 / CLI+param backup+平台表+`.env` CRLF / 四階 rollback+8GB 交接+誠實底線（P4-5~P4-10）。
- [ ] dry-run review 通過、所有 blocker 已修（P4-11）。
- [ ] HITL 五幕全流程 + 控制面真機驗（Roy 在場、S1/S4 e-stop）（P4-12，needs-HITL）。
- [ ] 8GB stack 交接決策樹消費 plan1 profiling 結論（P4-13）。
- [ ] 每幕能力分級（S1=FAILED/S2-S4=needs-HITL/S5=proven）+ claim 對映 S1–S8/F1–F10；新 CLI 全標 PLANNED + workaround。
- [ ] 與 `PHASE_ALLOWED_KINDS` 逐字一致；新 route 不被呼叫 + demo_phase=all 回歸 byte-identical。

---

## 12. Execution order（執行順序）

1. **P4-1 / P4-2**（gateway 後端 publisher + route）— FLOOR 後端先就緒，依賴 plan2 的 `/brain/demo_phase` String subscriber 契約 + plan-fallback 的 offline 契約（契約未定先標 TODO，結構先寫）。
2. **P4-3**（frontend 五幕鈕 + offline toggle）— 抄 gesture-toggle，接 P4-1/P4-2 route。
3. **P4-5 / P4-9 / P4-10**（開場 + CLI/平台 + rollback 階梯）— 操作員先知道工具與退路。
4. **P4-6 / P4-7 / P4-8**（五幕表 + 三洞 + 角色分工）— 依 plan2 phase 表 + plan-fallback canned 落定。
5. **P4-4**（phase chip）— 依 `/state/brain` 加 `demo_phase` 欄位（plan2 T-C4）後接。
6. **P4-13**（8GB 交接）— 消費 plan1 profiling 結論。
7. **P4-11**（dry-run，發表日前 48h）。
8. **P4-12**（HITL，Roy 在場，S1/S4 e-stop，最後）。

> 純軟體（1–6）可在 6/18 前先合 + 單測綠（needs-HITL 標記），**不阻塞任何 code**，可與 plan2/fallback/Lane3 並行。

---

## 13. Codex Implementation Prompt（給 Codex 的總指令）

你是 builder。依本 plan 的 task packet（§5）實作，**不擴 scope、不改別 plan 擁有的 code、無 Roy 授權 + task 明標前不送 Go2 motion**。從 **P0 純軟體** 開始：P4-1（gateway `/api/demo_phase`）→ P4-2（`/api/offline_mode`）→ P4-3（frontend 隱藏五幕鈕 + offline toggle）。每顆 phase 按鈕的 gateway publisher **必須先發 `/brain/reset_context`（Empty）再發 phase（String）**——這是 demo 換幕不污染的核心。鏡像 `studio_gateway.py:806 publish_gesture_enabled` 與 `frontend/components/chat/gesture-toggle.tsx`。phase 白名單 client+server 雙重驗。**brain 端 `/brain/demo_phase` String subscriber 由 plan2 提供**——你只負責 gateway publisher 對該 topic 發布；若 subscriber 契約未合，先發布到該 topic 名 + 寫 mock-publisher 單測（不依賴 brain 在線）。runbook（P4-5~P4-13）是 markdown 文件，寫進 `docs/runbook/2026-06-18-operator-runbook.md`，每幕逐字對 `interaction_state.py:33` 的 `PHASE_ALLOWED_KINDS`、每步有 trace reason + rollback、新 CLI 全標 PLANNED + workaround。**每個 commit 小、附 diff + test-result + risk；不改 runtime-claim。**

---

# Codex Implementation Packet

## 確切檔案（exact files）

| Task | 檔案 | 動作 |
|---|---|---|
| P4-1 | `pawai-studio/gateway/studio_gateway.py` | 加 `_demo_phase_pub`（create_publisher String `/brain/demo_phase` depth 10）、`publish_demo_phase(phase)`（先 `self._reset_pub.publish(Empty())` 再 publish String + cache `_demo_phase_last`）、`demo_phase_snapshot()`、`class DemoPhasePayload(BaseModel): phase: str`、`POST/GET /api/demo_phase`、WS 廣播 `brain:demo_phase` |
| P4-1 | `pawai-studio/gateway/test_gateway.py` | 4 個新 test case（見下） |
| P4-2 | `pawai-studio/gateway/studio_gateway.py` | 加 `_offline_mode_pub` + `publish_offline_mode(bool)` + `offline_mode_snapshot()` + `OfflineModePayload(enabled: bool)` + `POST/GET /api/offline_mode` + WS `brain:offline_mode`（publisher 形態依 plan-fallback 契約，未定標 TODO） |
| P4-2 | `pawai-studio/gateway/test_gateway.py` | 3 個新 test case |
| P4-3 | `pawai-studio/frontend/components/operator/demo-phase-buttons.tsx`、`offline-toggle.tsx`（新）；`stores/state-store.ts`（加 `demoPhase`/`offlineMode` + setter）；mount 進 `components/sheet/dev-panel.tsx`（`DevPanel()` `:13`，插入 `:15` `<div className="flex flex-col">` 內，沿用 `:17` border-t section） | 抄 `gesture-toggle.tsx` |
| P4-3/P4-4 | `pawai-studio/frontend/components/operator/__tests__/*.test.tsx`（新） | vitest |
| P4-4 | `pawai-studio/frontend/components/operator/phase-chip.tsx`（新）；`stores/state-store.ts`（從 `brain:state` set） | 唯讀 chip |
| P4-5~P4-13 | `docs/runbook/2026-06-18-operator-runbook.md`（新） | markdown |

## 確切測試（exact tests）

```bash
# gateway（P4-1/P4-2）
cd pawai-studio/gateway && python3 -m pytest test_gateway.py -v
# frontend（P4-3/P4-4）
cd pawai-studio/frontend && npm test
# CLI 存在性（P4-9）
pawai demo --help && pawai face --help && pawai status --help
# 回歸護欄
cd pawai-studio/gateway && python3 -m pytest -v   # 全綠 = byte-identical
```

gateway test case（P4-1）必含：
1. `test_demo_phase_post_resets_before_switch`：POST `/api/demo_phase {phase:"s2_greet"}` → mock publisher 記錄 `reset_context` call **早於** demo_phase String publish。
2. `test_demo_phase_post_rejects_invalid`：POST `{phase:"s9_bogus"}` → 回 `{"ok": False, "error": "invalid_phase"}` 且 demo_phase 未 publish。
3. `test_demo_phase_get_returns_cache`：未切換 GET → `enabled/phase` 為 None；切換後 GET → 該 phase。
4. `test_demo_phase_ws_broadcast`：POST → WS 廣播 envelope `event_type=demo_phase, data.phase`。

## 確切命令（exact commands）

```bash
# 開發機建 frontend / 跑 gateway 測試（無 ROS2 也可——gateway 已 guard import）
cd pawai-studio/gateway && python3 -m pytest test_gateway.py -v
cd pawai-studio/frontend && npm install && npm test
# py_compile 自檢
python3 -m py_compile pawai-studio/gateway/studio_gateway.py
```

## 驗收（acceptance）

- gateway demo_phase route：reset-before-phase call order 單測綠 + 非法 phase 拒發 + cache + WS。
- offline_mode route：POST/GET/WS 結構就緒、預設 OFF byte-identical。
- frontend：五幕鈕 POST 正確 body、gateway 離線靜默不改 state、mount 在隱藏/dev 區塊（非主版面）。
- runbook：五幕逐字對 `PHASE_ALLOWED_KINDS`、三洞段含四 Gotcha、四階 rollback、新 CLI 全 PLANNED。
- 回歸：新 route 不被呼叫 → gateway 既有測試全綠。

---

# Cloud Review Checklist（Cloud/Fable 對 Codex 產出的審查）

1. **reset-before-phase**：`publish_demo_phase` 是否**先** `_reset_pub.publish(Empty())` **再** publish String？（漏了 = 換幕污染，demo-break）
2. **白名單**：client + server 是否雙重驗 phase？非法 phase 是否**不發布**且不靜默變全開？（unknown 容錯成 all 是 plan2 G6 風險）
3. **byte-identical**：新 route 不被呼叫時，gateway 行為是否與現行一致？既有 `test_gateway.py` / `test_auth.py` 是否全綠？
4. **auth 沿用**：新 route 是否沿用既有 `auth` 機制（env-gated 預設關），**沒有**自行 flip secure-default？
5. **frontend 隱藏**：五幕鈕是否在 dev/隱藏區塊（非主 chat-panel 顯眼處）？符合 Q3「hidden, not flashy」？
6. **不越界**：Codex 是否**沒**改 `interaction_state.py` / `tts_node.py` / `llm_bridge_node.py` / nav code / brain phase 清理邏輯（那些歸別 plan）？
7. **runbook 一致性**：五幕 allow/suppress 是否逐字對 `interaction_state.py:33`？三洞段四 Gotcha（S2 greet 進場、sitting bonus、confirm 差異、`.npz` ls）是否齊？
8. **overclaim 掃描**：runbook 是否出現 F1–F10 禁講句（自主導航/全自動/跌倒/2m 物體/可靠顏色/19 色/auto-resume/動態繞障/D435 已融合）？S1 是否標 FAILED/NOT_DEMO_READY？
9. **goto_relative 依賴**：是否有任何 Task 偷渡依賴 goto_relative？（必須無）
10. **tests + rollback**：每個 Task 是否都有 tests **且** rollback？（缺一即退回）
11. **`.npz` 斷言**：runbook 是否要求 HITL 先 `ls /home/jetson/face_db/` 才定刪除清單，**沒有**未上機就斷言 `.npz` 一定存在？
12. **P0 純度**：是否有 P1/P2 偷渡進 P0？（auto-advance / phase chip 必須非 P0-FLOOR）

---

# Stop Conditions（停止條件）

Codex 遇到以下任一**立即停、回報 Cloud，不自行決定**：
1. 需要改 `interaction_state.py` / `tts_node.py` / `llm_bridge_node.py` / nav code / brain phase 清理邏輯（別 plan 擁有）。
2. plan2 的 `/brain/demo_phase` String subscriber 契約 / plan-fallback 的 `offline_mode` 契約**與本 plan 假設衝突**（topic 名、型別、欄位）。
3. 任何 Task 需送 Go2 motion / goto / cmd_vel（無 Roy 授權 + e-stop 明標）。
4. 新 route 導致既有 `test_gateway.py` / `test_auth.py` 失敗（byte-identical 破功）。
5. 需 flip gateway secure-default / 改 auth 機制（route_id sanitize 歸 Security plan，本 plan 只沿用）。
6. runbook 內容與 nav incident plan / nav claim wording 矛盾（claim 衝突）。
7. 任一 Task 無法同時給出 tests + rollback。
8. 需在未上機 ls 前斷言 `.npz` 檔名 / 改 face delete CLI（CLI 歸 Lane 3）。

---

# Required Evidence（必備證據）

每個 Task 完成時 Codex 須附：
1. **diff**（小 commit / PR link）。
2. **test-result**：`pytest test_gateway.py -v` / `npm test` 完整輸出（綠）+ 回歸 `pytest -v`（既有全綠 = byte-identical）。
3. **call-order 證據**（P4-1）：reset-before-phase 單測輸出（mock publisher call 序）。
4. **risk note**：本次改動的 demo-break / overclaim / safety 風險自評（無 = 明確寫「無」）。
5. **runbook 一致性截圖/grep**：`grep -n "PHASE_ALLOWED_KINDS" interaction_state.py` 對照 runbook 五幕表。
6. **HITL（P4-12）**：每幕日期 + 是否串台 + sim 值 + 是否 silent fail + S1/S4 是否有 e-stop 介入；錄影（offline canned 出聲、S5 reject 端到端）= demo snapshot 證據。

---

# Rollback Plan（整份計畫層級）

- **單一最強退路**：所有新 route 不被呼叫 + `demo_phase=all` + `offline_mode` off = gateway/brain byte-identical 現行為。
- **frontend**：元件不 mount / dev-panel feature-flag 隱藏 = 等於不存在。
- **runbook**：純文件，無 runtime 影響；任一段落寫錯 dry-run（P4-11）抓回。
- **HITL 失敗**：S1 退遙控+Studio→影片；S4 退 peace→WeGo；face 退 generic greet；offline 退 env override（proven）。
- **四階 rollback 階梯**（Q6）：auto-advance → Studio 隱藏鈕 → ros2 param set → demo_phase=all + 影片。**永不押 6/18 在 auto-advance。**
