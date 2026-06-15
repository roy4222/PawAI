# S1 Low-Risk Navigation Plan（s1_nav 移動段：低風險主線 + 三層 fallback）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫群：PawAI Demo Flow Reliability Sprint（Cloud A）｜本份：S1 Low-Risk Navigation Plan

---

## 0. 這份在計畫群裡的位置（先讀）

本份是 Cloud A「Demo Flow Reliability Sprint」五份計畫之一，專門承接 demo 五幕的**第一幕 `s1_nav`**——「PawAI 移動到現場」。

- 上層串接：[`2026-06-13-demo-flow-reliability-master-plan.md`](2026-06-13-demo-flow-reliability-master-plan.md)（master，幕順序與整體 rollback）。
- 幕切換機制：[`2026-06-13-demo-phase-conductor-plan.md`](2026-06-13-demo-phase-conductor-plan.md)（Conductor，`demo_phase` 詞彙與清理）。**s1_nav 對映 `quiet`（全 suppress 自發社交）**——但 S1 幾乎一定走獨立 nav stack（與 brain 8GB 互斥），所以本幕的「phase」多半是物理上 brain 根本沒開，Conductor 只負責「nav→s2 過場時 brain 起來後設成 `s2_greet`」。
- 網路降級：[`2026-06-13-online-offline-fallback-plan.md`](2026-06-13-online-offline-fallback-plan.md)（S1 canned phrase「我正在移動到巡檢位置。」屬該份）。
- 操作 SOP：[`2026-06-13-demo-operator-runbook-plan.md`](2026-06-13-demo-operator-runbook-plan.md)（本份產的 nav 安全前置 / e-stop / initialpose SOP 會被 runbook 收編）。

**權威關係（不可繞過）**：
- nav 能力等級的真相層 = [`docs/navigation/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)（C1-C12，本份**只引用、不自定義** label）。
- nav 對外台詞的真相層 = [`docs/navigation/2026-06-13-nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)（S1-S8 可講句 / F1-F10 禁講 / safe-stop≠繞障標準說法 / 三層 fallback）。
- HITL 場測項 = [`docs/runbook/2026-06-13-roy-hitl-queue.md`](../../runbook/2026-06-13-roy-hitl-queue.md) C 段 N1-N8。
- nav 實作工項歸 [`2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md`](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（T6-*）。**本份不重複 Lane 6 的實作工項**，只做「demo 五幕第一幕的可靠執行 + 場測編排 + 誠實 claim 收斂 + fallback 鎖定」。

> 命名澄清：文件標題的「S1」= **demo 第一幕 s1_nav**（移動段）；claim wording 裡的「S1」= **可講句第 1 句**（「室內已知地圖、操作員下令的短距自主移動 0.3-0.5m」）。兩者剛好同號是巧合，本份內文一律寫「s1_nav 幕」或「可講句 S1」以免混淆。

---

## 1. Goal

讓 demo 第一幕 `s1_nav`（PawAI 移動到現場）**可靠、照順序、可操作、出錯有 trace/rollback**，且**對外宣稱不 overclaim**。具體：

1. 主線是**最低風險的移動形態**：室內已知地圖、操作員下令、短距（goto_relative 0.3-0.5m / short forward）、operator-assisted，遇障**安全停**（不繞行、不 auto-resume）。
2. **誠實反映今天（6/13）剛撞牆的現實**：goto 0.3m 走歪撞牆、Roy e-stop。在 6/18 前未 n=3 無撞重驗成功之前，s1_nav **退影片 fallback、claim 退保守版**，不對外講「自主短距移動」。
3. 提供**三層 fallback**（live 短距 → 遙控輔助 + Studio 證據 → 純影片保底），任一層都能交付 s1_nav 幕，**不開天窗**。
4. 把 nav 安全前置（e-stop 待命、reactive_stop kill 重啟帶 indoor_tight、initialpose 朝向校正 SOP、goto 前朝向 sanity）寫成可被 operator runbook 收編的清單。

**非目標（明確排除）**：不押 live SLAM 主線、不押 autonomous approach Roy 主線、不押 1.0m+ 連續導航、不押動態繞障、不換 nav 模型/stack。

---

## 2. Current state（含今天硬體現實，務必誠實）

### 2.1 即時硬體狀態（handoff 2026-06-13 EOD）—— 開工第一件事

- **Jetson 上 nav stack 還在跑**：tmux session `nav-cap-demo`，9 windows（tf + sllidar + go2_driver + reactive_stop + nav2 + AMCL + navcap + foxglove + monitor）。
- **剛發生 Go2 撞擊**：`goto_relative 0.3m` 第一發走歪撞牆，Roy e-stop。
- **D435 有 Right MIPI error / Hardware Error**：nav 不需 D435（只吃 RPLIDAR 2D scan），但 face/vision 受影響 → **brain demo 前可能要重插 D435 USB**。nav 幕本身不依賴 D435。
- **nav stack 與 brain demo stack 8GB 互斥**（不能同跑）→ s1_nav 是**獨立鏡頭**，不能跟 s2-s5 brain 幕在同一個 process session 連續跑。
- ⚠️ **收工/開工第一件事**：確認 Go2 停穩 + `pawai demo stop` 清場（依 lock lane 路由），不要直接在殘留 active goal / 殘留 driver 上面再發 goto。

### 2.2 能力現況（逐項，引 ladder current label）

> label 直引 [nav-capability-ladder §2 Proven Table](../../navigation/2026-06-13-nav-capability-ladder.md)，本份不改 label。

| ladder | 能力 | current label | s1_nav 角色 | 今日狀態 |
|---|---|---|---|---|
| [C1](../../navigation/2026-06-13-nav-capability-ladder.md) | 0.3m short goto | `HARDWARE_PROVEN_LOW_SAMPLE` | **s1_nav 主線候選** | **今日 0.3m 撞牆** → 在重驗成功前不算可用 |
| [C2](../../navigation/2026-06-13-nav-capability-ladder.md) | 0.5m short goto | `NEEDS_RETEST` | s1_nav 主線候選（與 C1 合併講） | 未獨立重驗 |
| [C3](../../navigation/2026-06-13-nav-capability-ladder.md) | 1.0m goto | `wired_only` / `NOT_DEMO_READY` | **不進 s1_nav 主線** | AMCL 黃帶卡死，從未成功 |
| [C4](../../navigation/2026-06-13-nav-capability-ladder.md) | safe stop（正前停障） | `HARDWARE_PROVEN_WITH_LIMIT` | **s1_nav 安全護欄** | proven 多次（trackB §1 NAV-2 / 6/9 §1.5），stop≠繞障 |
| [C5](../../navigation/2026-06-13-nav-capability-ladder.md) | stop-resume | `wired_only` / `NEEDS_FIX_OR_OPERATOR_CONFIRM` | s1_nav **只用 operator-confirm**，禁 auto-resume | auto-resume 會 lunge 貼牆 0.21m |
| [C6](../../navigation/2026-06-13-nav-capability-ladder.md) | indoor_tight profile（±18°） | `HARDWARE_PROVEN_WITH_LIMIT` | **s1_nav 必用 profile** | proven（trackB §4 / 6/9 §1.3）；窄錐綁低速 ≤0.2 |
| [C7](../../navigation/2026-06-13-nav-capability-ladder.md) | AMCL initialpose 重定位 | `HARDWARE_PROVEN_LOW_SAMPLE` | **s1_nav 前置（朝向校正）** | 跳點可行，covariance 收斂無 SOP |
| [C8](../../navigation/2026-06-13-nav-capability-ladder.md) | orphan goal 自癒 | `HARDWARE_PROVEN_WITH_LIMIT` | s1_nav 韌性護欄 | ~10s 自癒（非即時） |
| [C9](../../navigation/2026-06-13-nav-capability-ladder.md) | patrol（固定 route 單圈） | `research_prototype` / `PROTOTYPE` | **不進 s1_nav 主線**（stretch only） | routes 資料遺失、從未跑過單圈 |
| [C12](../../navigation/2026-06-13-nav-capability-ladder.md) | D435+LiDAR fusion / approach person | `research_prototype` / `DO_NOT_CLAIM`（spec only） | **絕不進 s1_nav** | 只有 spec |

### 2.3 既有 anchor（已存在、可直接用，不需新建）

- **起 nav stack**：`bash scripts/start_nav_capability_demo_tmux.sh`，env `REACTIVE_PROFILE=open_space|indoor_tight`、`ROBOT_IP=192.168.123.161`、`MAP=/home/jetson/maps/home_living_room.yaml`、`NAV_NAMED` / `NAV_ROUTES`。
- **動作**：`ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.3}"`；`/nav/goto_named`；`/nav/run_route`；`/log_pose`。services `/nav/pause` `/nav/resume` `/nav/cancel`。
- **短距工具**：`scripts/send_relative_goal.py`（讀 `/amcl_pose` 算前方相對 goal，QoS BEST_EFFORT 配 bt_navigator）。
- **診斷**：`scripts/lidar_front_sector.py`（±15/20/30° 扇區最近距離 + 角度 debug，現場分辨真障礙 vs 側前家具）。
- **e-stop**：`emergency_stop.py engage`（mux pri 255 + lock）+ `StopMove`（`api_id=1003`，topic 必填 `rt/api/sport/request`）。
- **狀態 topic**：`/capability/nav_ready`、`/state/nav/status`（含 covariance JSON）、`/state/nav/safety`、`/state/nav/paused`（latched）。
- **CLI（純包裝、零 motion）**：`pawai smoke nav --static`（static 鏈路 smoke，零 motion）、`pawai status`、`pawai demo stop`、`pawai evidence pull`。

---

## 3. Problems / gaps

| # | 問題 | 影響 s1_nav | 處置歸屬 |
|---|---|---|---|
| P1 | **今日 0.3m goto 走歪撞牆**（C1 本應 proven，今日 FAILED） | s1_nav 主線當下不可用 | 本份 §8 N3 重驗 + §10 退影片 |
| P2 | **根因研判 = AMCL initialpose 朝向不準** → Go2 以錯誤朝向起步斜走 | 撞 +25°/1.65m 側家具 | 本份 §8 initialpose 朝向校正 SOP（HITL） |
| P3 | **跑成 open_space ±30° 寬錐**（非 indoor_tight ±18°） | 右前角家具誤擋 + 側向覆蓋不足 | 本份 §6 強制 indoor_tight kill 重啟帶參 |
| P4 | `front_arc_deg`/`danger_distance_m`/`front_offset_rad` **只在 `__init__` 讀**，`ros2 param set` 改無效 | 線上改 profile 無效、以為改了其實沒改 | 本份 §6/§8：必 kill 重啟帶參數 |
| P5 | **AMCL covariance 收斂無 SOP**（黃帶 ≤0.5m，>0.5m 被 hardcoded gate 拒；60-90s 偶爾過） | s1_nav 拿不準何時可發 goal | Lane 6 T6-5（N2 covariance SOP）；本份引用、不自做 |
| P6 | **goto 前無朝向 sanity 檢查** | 朝向歪了仍照發 → 斜走撞牆 | 本份 §7 純軟體：朝向 sanity 提示（人讀，不自動下令） |
| P7 | **auto-resume 會 lunge**（MIN_X ~0.5 m/s、貼牆 0.21m） | tight space 危險 | 本份禁用 auto-resume，只 operator-confirm（C5） |
| P8 | **8GB 互斥** + nav 是獨立鏡頭 | s1_nav 與 s2-s5 不能同 session | 本份 §13 + master 幕過場 |
| P9 | nav stack 已在跑、剛撞、可能殘留 active goal | 開工直接發 goto 會被 orphan reject / 撞第二次 | 本份 §8 開工前置：先 stop 清場 |

---

## 4. Scope（本份做什麼）

1. **s1_nav 主線定義**：indoor_tight ±18° + 低速 ≤0.2 m/s + goto_relative 0.3-0.5m / short forward，operator-assisted，safe-stop 護欄。
2. **nav 安全前置清單**（給 operator runbook 收編）：開工先 stop 清場、e-stop 待命、reactive_stop kill 重啟帶 indoor_tight、initialpose 朝向校正 SOP、goto 前朝向 sanity。
3. **HITL 場測編排**：把 [roy-hitl-queue C 段 N1-N8](../../runbook/2026-06-13-roy-hitl-queue.md) 中與 s1_nav 直接相關的項（N8 profile / 朝向校正 / N3 短距 n=3 / N6 operator-confirm / N5 patrol stretch）排成「先安全護欄、再短距重驗、最後 stretch」的順序。
4. **claim 收斂**：把 s1_nav 對外措辭逐句綁 [claim wording S1-S8 / F1-F10](../../navigation/2026-06-13-nav-618-claim-wording.md)，並寫死「6/18 前未重驗成功 → 退保守版 + 影片 fallback」。
5. **純軟體輔助（不當主依賴）**：goto 前朝向 sanity 提示文字、initialpose 朝向校正 SOP 文件、Studio initialpose 證據面板的「證據定位」（明確標記為證據輔助，非主功能）。
6. **三層 fallback 鎖定** + done/rollback。

---

## 5. Forbidden scope（本份不做）

延續計畫群共同 Forbidden（[master §Forbidden](2026-06-13-demo-flow-reliability-master-plan.md)）：

- ❌ 不換 nav 模型 / 不換 nav stack / 不重寫 nav_capability。
- ❌ 不做 live SLAM 主線（建圖只在預備期、不在 demo 主線）。
- ❌ 不做 autonomous approach Roy（C12，research only）。
- ❌ 不做動態繞障 / 自動繞行（reactive_stop 設計上只停不轉）。
- ❌ 不放寬 AMCL covariance 門檻（0.3/0.5 hardcoded，Lane 6 §5 禁止）——靠 N2 SOP + 設準 pose 解。
- ❌ 不把 1.0m+ goto 進 s1_nav 主線。
- ❌ 不把 patrol（C9）/ fusion（C12）當 s1_nav 主功能（patrol 僅 stretch、需 N5 過、操作員監督）。
- ❌ 不在本份做 nav 實作 code（實作歸 Lane 6 T6-*）；本份只寫計畫 + SOP 文件 + 純文字提示規格。
- ❌ **不對移動中 Go2 送 Damp（api_id=1001）**（會摔）；e-stop 走 emergency_stop.py + StopMove(1003)。

---

## 6. Tasks

> 每 Task 標 `[pure software]` / `[Jetson needed]` / `[Go2 motion needed]`，並含 tests / HITL checklist / rollback。能力分級 proven / needs-HITL / research-only 逐項標明。

### T-S1-1：s1_nav 主線參數鎖定（indoor_tight ±18° 低速 0.2）
- 標記：`[Jetson needed]`（profile 套用驗證可在 nav stack 上做，不必動 Go2）。
- 能力分級：**proven（C6 `HARDWARE_PROVEN_WITH_LIMIT`）**。
- 內容：s1_nav 一律用 `REACTIVE_PROFILE=indoor_tight` 起 nav stack；確認 reactive_stop 以 `front_arc_deg≈18` + `danger_distance_m≈1.0` + `slow_speed≈0.2 normal_speed≈0.3` 啟動。**因 P4：這些值只在 `__init__` 讀 → 必 kill 重啟帶參數，`ros2 param set` 改無效。**
- tests：起 stack 後 `ros2 param get /reactive_stop_node front_arc_deg` 應為 18（或 profile 設定值）；`scripts/lidar_front_sector.py` 比對 ±15/20/30° 扇區，確認窄錐生效（右前家具不進前方危險）。
- HITL checklist：☐ `REACTIVE_PROFILE=indoor_tight`；☐ kill 舊 reactive_stop 確認無殘留；☐ front_arc_deg 讀回 = 18；☐ lidar_front_sector 顯示窄錐。
- rollback：profile 異常 → 退 §10 fallback 層②（遙控輔助）；不退回 open_space（open_space 是今日撞牆 profile）。

### T-S1-2：開工/收工 nav 安全前置清單（清場 + e-stop 待命）
- 標記：`[Jetson needed]` + `[Go2 motion needed]`（涉及確認 Go2 停穩）。
- 能力分級：proven（清場/e-stop 是既有操作）。
- 內容：寫死開工前置（交 operator runbook）：① 先 `pawai demo stop`（依 lock lane 清場）/ 確認沒有殘留 driver + 殘留 active goal；② Go2 停穩、e-stop 物理待命；③ `emergency_stop.py engage` 路徑與 StopMove(1003, `rt/api/sport/request`) 預先驗手感；④ **禁對移動中 Go2 送 Damp(1001)**。
- tests：`ros2 action list | grep goto` 無殘留 active goal（或發一筆 dry goto 確認不被 `another goto still active` reject）；`ros2 node list` 無多 driver instance。
- HITL checklist：☐ Go2 停穩；☐ 清場完成；☐ e-stop 手能立刻按到；☐ 確認無殘留 active goal（C8 orphan）。
- rollback：殘留清不掉 → 重啟 nav launch（清 orphan，C8 證據：重啟可清）。

### T-S1-3：AMCL initialpose 朝向校正 SOP（LiDAR 紅點對齊牆）
- 標記：`[Jetson needed]` + `[Go2 motion needed]`（朝向確認需 Go2 在場 + 可能微調朝向）。
- 能力分級：**needs-HITL**（C7 `HARDWARE_PROVEN_LOW_SAMPLE`：跳點可行，但**朝向準度 + covariance 收斂無 SOP**；今日撞牆根因 P2 = 朝向不準）。
- 內容：寫 SOP——在 Foxglove/RViz/Studio 設 `/initialpose`（或 `/api/nav/initialpose`）時，**用 LiDAR scan 紅點對齊已知牆面**校正朝向（不只設位置，朝向要對）；設完讀 `/state/nav/status` covariance；按 N2 黃帶決策表（Lane 6 T6-5，本份引用）決定等 / 推 0.3m warmup / 重設。**covariance ≤0.30 才允許 >0.5m goal（hardcoded YELLOW gate，不放寬）；黃帶只准 ≤0.5m。**
- tests：設 initialpose 後 `/amcl_pose` 跳到設定點（C7 proven）；`scripts/lidar_front_sector.py` 紅點與牆面對齊（朝向 sanity 的人讀依據）。
- HITL checklist：☐ initialpose 位置對；☐ **朝向：LiDAR 紅點貼齊牆面**；☐ 讀 covariance 進黃帶或更好；☐ 朝向偏差 < 目視可接受角度。
- rollback：朝向校不準 / covariance 不收斂 → **不發 goto**，退 §10 fallback 層②/③。

### T-S1-4：goto 前朝向 sanity 提示（人讀，不自動下令）
- 標記：`[pure software]`。
- 能力分級：needs-HITL（提示本身純軟體 proven，但「朝向對不對」的判定要 HITL 目視）。
- 內容：規格化一個**純文字/Studio 顯示的 sanity 提示**：發 goto_relative 前，把當前 `/amcl_pose` 朝向 + LiDAR 正前扇區最近距離（`lidar_front_sector.py` ±15°）並列顯示，提示操作員「正前淨空 ≥ goto 距離 + margin 才發、朝向歪了先回 T-S1-3」。**此提示不自動阻擋、不自動下令**——只輔助人決策（避免把判斷邏輯做進自動鏈，符合 CLI/工具零 runtime 行為哲學）。
- tests：`[pure software]` 單測——給定 amcl yaw + front_sector 距離，提示字串正確組裝；距離 < goto 距離 + margin 時提示「不建議發」。
- HITL checklist：☐ 操作員確認提示距離與目視一致；☐ 朝向歪時提示有跳「先校正」。
- rollback：提示工具不可用 → 操作員手動用 `lidar_front_sector.py` + 目視（提示只是便利層）。

### T-S1-5：s1_nav claim 收斂（逐句綁 wording S1-S8 / F1-F10）
- 標記：`[pure software]`（純文件）。
- 能力分級：N/A（文件治理）。
- 內容：把 s1_nav 對外措辭固定為 [claim wording §2](../../navigation/2026-06-13-nav-618-claim-wording.md) 的 **S1（短距，標單點，N3 過才加「可靠」）→ S2（safe-stop，配 §3 標準說法）→ S3（operator-confirm）→ S4（窄場安全錐）→ S5（orphan ~10s，禁「即時」）**；列 §4 **F1-F10 全部禁講**；safe-stop≠繞障整段照 §3 精神。寫死條件句：**6/18 前未重驗成功（N3 未過）→ S1 去「可靠」、s1_nav 退影片 fallback、不講「自主短距移動」**。
- tests：claim 對照表逐行對 wording 檔，無新增/放水句（人工 review + 引用一致性檢查）。
- HITL checklist：N/A（Roy 過目鎖定，OPEN 書記 A-1 閉合）。
- rollback：N/A。

### T-S1-6：三層 fallback 鎖定（給 B-10 決策依據）
- 標記：`[pure software]`（決策表）+ 依賴 §8 HITL 結果。
- 能力分級：N/A。
- 內容：把 s1_nav 發表日形態鎖成 [claim wording §5 三層](../../navigation/2026-06-13-nav-618-claim-wording.md)：① live 短距（**N3 過才上**）→ ② 遙控輔助 + Studio 證據 → ③ 純影片保底（demo snapshot）。寫死「6/17 回穩日依 N3/N8 結果由 Roy 定 B-10」。
- tests：三層各自的「上場條件 + 可講句」對齊 wording §5。
- HITL checklist：☐ 影片保底已存在（demo snapshot tag）；☐ 遙控輔助路徑可用。
- rollback：本身就是 rollback 機制。

---

## 7. Pure software tasks（彙整）

| Task | 內容 | 為何純軟體 |
|---|---|---|
| T-S1-4 | goto 前朝向 sanity 提示（人讀） | 只組字串、不下令、不阻擋 |
| T-S1-5 | claim 收斂文件 | 文件治理 |
| T-S1-6 | 三層 fallback 決策表 | 文件治理 |
| T-S1-3（SOP 文件部分） | initialpose 朝向校正 SOP 撰寫 | SOP 文字（執行需 HITL，但**寫**是純軟體） |
| Studio initialpose 證據面板（證據定位） | 明確標記為「邊緣端即時感知證據輔助」，**非主功能依賴** | 前端展示，不參與 nav 判定 |

> ⚠️ Studio / Foxglove / pose / LiDAR / depth 在 s1_nav 中**只做「邊緣端即時感知」證據輔助，不當主功能依賴**（claim wording §5 層②）。本份不大改 Studio UI（共同 Forbidden）。

---

## 8. Jetson / Go2 HITL tasks（s1_nav 場測編排，對映 roy-hitl-queue C 段）

> 全部需 Roy 在場 + Go2 + Jetson nav stack。**每項前置 = T-S1-2 安全前置 + e-stop 待命**。執行順序：先安全護欄（N8 + 朝向校正）→ 再短距重驗（N3）→ 最後 stretch（N6 / N5）。

### H1：N8 profile 矩陣重跑（indoor_tight）— **先做，建立安全護欄**
- 對映 [roy-hitl-queue N8](../../runbook/2026-06-13-roy-hitl-queue.md)、ladder [C4/C6](../../navigation/2026-06-13-nav-capability-ladder.md)。
- 標記：`[Jetson needed]` + `[Go2 motion needed]`（safe-stop 場景含 Go2 接近障礙）。
- 能力分級：**proven（重驗護航）**。
- 步驟：indoor_tight 起 stack → danger 停 / clear 放行 / 無誤擋各一輪，`lidar_front_sector.py` 佐證。
- HITL checklist：☐ 正前障礙 → danger 停、0 撞 0 暴衝；☐ clear → 放行；☐ 右前家具 → 不誤擋（zone slow/clear、`nav_paused=false`）。
- rollback：誤擋鎖死 → 收更窄錐或退遙控；safe-stop 失效 → **立即 e-stop**、停 s1_nav live。

### H2：initialpose 朝向校正 + covariance（N2 引用）— **撞牆根因直擊**
- 對映 ladder [C7](../../navigation/2026-06-13-nav-capability-ladder.md)、依賴 [roy-hitl-queue N2 covariance SOP](../../runbook/2026-06-13-roy-hitl-queue.md)（Lane 6 T6-5 軟體，本份引用）。
- 標記：`[Jetson needed]` + `[Go2 motion needed]`。
- 能力分級：**needs-HITL（C7 low-sample；今日撞牆根因）**。
- 步驟：執行 T-S1-3 SOP（LiDAR 紅點對齊牆）→ 讀 covariance → 按黃帶決策表（等 / 0.3m warmup / 重設）→ 進黃帶（≤0.5m 可發）或更好。
- HITL checklist：☐ 朝向紅點貼牆；☐ covariance 進黃帶；☐ T-S1-4 sanity 提示與目視一致。
- rollback：朝向/covariance 不過 → **不進 H3**，s1_nav 退 fallback 層②/③。

### H3：N3 短距可靠性 n=3（**s1_nav 主線升級的唯一閘門**）
- 對映 [roy-hitl-queue N3](../../runbook/2026-06-13-roy-hitl-queue.md)、ladder [C1/C2](../../navigation/2026-06-13-nav-capability-ladder.md)。
- 標記：`[Jetson needed]` + `[Go2 motion needed]`。
- 能力分級：**needs-HITL（今日 FAILED，必須重驗）**。
- 步驟：`scripts/send_relative_goal.py` 0.3m × n=3（每發前過 T-S1-4 sanity + H2 朝向校正）；全 `reached` 且 **0 撞 0 暴衝**再考慮 0.5m × n=3；**1.0m 不做**（C3 不進主線）。每發記 covariance / actual_distance / 結果 → 回填 ladder proven table。
- HITL checklist：☐ 0.3m × 3 全 reached；☐ 每發無偏斜撞牆；☐ e-stop 全程待命；☐ 數據回填 ladder。
- rollback：**任一發撞牆或走歪 → 立即 e-stop、停 H3、s1_nav 退影片 fallback、claim 退保守版（S1 去「可靠」、不講「自主短距移動」）**。

### H4（stretch）：N6 stop-resume operator-confirm
- 對映 [roy-hitl-queue N6](../../runbook/2026-06-13-roy-hitl-queue.md)、ladder [C5](../../navigation/2026-06-13-nav-capability-ladder.md)。
- 標記：`[Jetson needed]` + `[Go2 motion needed]`。能力分級：needs-HITL。
- 步驟：goto/route 中置障 → danger 停 → Studio 按「繼續」→ 續走。**禁 auto-resume**（P7 lunge）。
- rollback：resume lunge → e-stop；只講 operator-confirm（S3）、禁 F4/F5。

### H5（stretch only，非 s1_nav 主線）：N5 patrol 單圈
- 對映 [roy-hitl-queue N5](../../runbook/2026-06-13-roy-hitl-queue.md)、ladder [C9](../../navigation/2026-06-13-nav-capability-ladder.md)、依賴 N1（poses/routes 重錄）。
- 標記：`[Jetson needed]` + `[Go2 motion needed]`。能力分級：**research_prototype**（routes 已遺失、從未跑過單圈）。
- 步驟：N1 重錄 poses/routes → `run_route` 單圈（操作員監督 + e-stop 待命）+ Studio 三層同框錄證據。
- rollback：不過 → **patrol 整段不講**（S7 鎖死、N5 未過不解鎖）；s1_nav 主線不依賴 patrol。

---

## 9. Tests

### 9.1 純軟體（不需 Jetson/Go2）
- T-S1-4 朝向 sanity 提示單測：amcl yaw + front_sector 距離 → 提示字串 / 「不建議發」判定正確。
- T-S1-5 / T-S1-6 claim 與 fallback 文件對齊 wording 檔（引用一致性、無放水句）。
- CLI 靜態：`pawai smoke nav --static`（**零 motion**，只驗鏈路 wired）。

### 9.2 HITL（需 Jetson + Go2，§8）
- H1：safe-stop / clear / 無誤擋各一輪（C4/C6 重驗）。
- H2：朝向校正 + covariance 進黃帶（C7）。
- H3：0.3m × n=3 全 reached、0 撞（C1/C2 升級閘門）。
- H4/H5：stretch，過則解鎖 S3 / S7。

### 9.3 Done gate（s1_nav 能否走 live）
**只有 H1 + H2 + H3 全綠（0.3m n=3 無撞）才允許 s1_nav 走 fallback 層① live；任一不過 → 退層②/③。**

---

## 10. Rollback（三層 fallback，照 claim wording §5）

| 層 | 內容 | 上場條件 | s1_nav 可講句 |
|---|---|---|---|
| **① live 短距** | 現場 live 跑 goto 0.3-0.5m（indoor_tight + 低速 + operator-assisted） | **H3（N3）過、0 撞** | S1（N3 過可加「可靠」）、S2、S3 |
| **② 遙控輔助 + Studio 證據** | 遙控/Studio 輔助定位，Studio map / LiDAR 點雲作「邊緣端即時感知」**證據**（非主功能） | live 不穩 / H3 未過 / 場地不允許 | S2、S4 + 「Studio 顯示即時感知環境（非寫死）」 |
| **③ 純影片保底** | s1_nav 鏡已錄影片（demo snapshot tag） | live + 遙控都不上 | 旁白用 S1-S5 保守版、明標「錄影」 |

**鐵則**：① demo snapshot 影片是發表保底，任何 lane 不得使其失效；② 三層任一都能交付 s1_nav 幕——**不存在 nav 整段開天窗**；③ **6/18 前 H3 未過成功 → s1_nav 退層②/③、claim 退保守版（S1 去「可靠」、不講「自主短距移動」）**。

> 每一 Task 的逐項 rollback 已寫在 §6 / §8 各條。

---

## 11. Done criteria

s1_nav 幕視為「demo-ready（在其誠實級別內）」當且僅當：

1. ☐ T-S1-1 indoor_tight ±18° 低速 0.2 鎖定，kill 重啟帶參數驗過（front_arc_deg 讀回 = 18）。
2. ☐ T-S1-2 開工/收工安全前置清單交 operator runbook、e-stop 手感驗過。
3. ☐ T-S1-3 initialpose 朝向校正 SOP（LiDAR 紅點對齊牆）寫成、H2 驗過。
4. ☐ T-S1-4 朝向 sanity 提示單測綠、操作員確認與目視一致。
5. ☐ T-S1-5 claim 逐句綁 wording S1-S5、F1-F10 禁講鎖定、Roy 過目（OPEN 書記 A-1 閉合）。
6. ☐ T-S1-6 三層 fallback 鎖定、影片保底存在。
7. ☐ **H1 + H2 + H3 全綠（0.3m n=3 無撞）→ s1_nav 可走 live 層①；否則退層②/③且 claim 退保守**。

> 注意：**Done ≠ live 一定上場**。Done 的最低標是「三層任一可交付 + claim 不 overclaim」。live 層① 是 bonus，綁 H3 PASS。

---

## 12. Execution order

1. **開工**：T-S1-2 安全前置（清場 + 確認 Go2 停穩 + e-stop 待命）— **第一件事**。
2. **profile**：T-S1-1 indoor_tight kill 重啟帶參數 → H1（N8 護欄重驗）。
3. **定位**：T-S1-3 SOP + H2（朝向校正 + covariance）。
4. **sanity 工具**：T-S1-4（純軟體，可與 1-3 並行寫）。
5. **主線重驗**：H3（0.3m n=3）— **撞牆根因的最終裁決**。
6. **claim / fallback 收斂**：T-S1-5 + T-S1-6（依 H3 結果定 B-10）。
7. **stretch（時間允許）**：H4（N6 operator-confirm）→ H5（N5 patrol，需 N1 先重錄）。
8. **6/17 回穩日**：Roy 依 H1/H2/H3 結果鎖 B-10 發表日 fallback 層。

> 與 [Lane 1 ISM staged enable](2026-06-13-lane1-brain-ism-staged-enable-plan.md) 無衝突：s1_nav 走獨立 nav stack（brain 多半沒開），Conductor 只在 nav→s2 過場後接手設 `s2_greet`。本份不碰 ISM flag。

---

## 13. 6/18 presentation impact

- **最壞情況也不開天窗**：即使 H3 再次 FAIL，s1_nav 仍有層②（遙控 + Studio 證據）與層③（純影片），claim 退保守版（「室內已知地圖、操作員下令的短距移動——目前以遙控輔助 / 錄影呈現」），不講「自主短距移動」「可靠」。
- **誠實是敘事主軸**：開場用 [claim wording §1 一句話定位](../../navigation/2026-06-13-nav-618-claim-wording.md)（能力階梯 + 誠實）——把「不把單次成功講成可靠、不把停障講成繞障」當賣點，正面回應 6/13 撞牆的真實風險。
- **被追問繞障**：固定用 [claim wording §3 safe-stop≠繞障標準說法](../../navigation/2026-06-13-nav-618-claim-wording.md)：「我們做的是 safe-stop——偵測到正前方障礙會在安全距離停下等待，由操作員確認後再重新下達或遙控輔助；它不會自己轉向繞過障礙，繞障需要轉向控制，而我們的反應式停障在設計上只停不轉（`angular.z=0`），這是刻意的安全選擇（硬轉曾導致四足失衡）。」
- **被追問「會不會自己找人/過來」**：S8 + F6——「研究路線有 spec，目前感知與移動還沒接起來，不在這次展示範圍」。
- **8GB 互斥的舞台安排**：s1_nav 是獨立鏡頭（或影片），與 s2-s5（brain 幕）不同 session；過場時 `pawai demo stop` nav → 起 brain demo → Conductor 設 `s2_greet`。
- **F1-F10 全程封口**：自由巡邏 / 動態繞障 / D435 已融合 / auto-resume / 「停了不會再走」/ 「聽懂走到 Roy 身邊」/ 未 n=3 的「可靠導航」/ 1.0m+ 連續導航 / 三鏡頭參與導航 / 即時恢復——一句都不講。

---

## 附：交叉引用索引

- master：[`2026-06-13-demo-flow-reliability-master-plan.md`](2026-06-13-demo-flow-reliability-master-plan.md)
- conductor：[`2026-06-13-demo-phase-conductor-plan.md`](2026-06-13-demo-phase-conductor-plan.md)
- online/offline：[`2026-06-13-online-offline-fallback-plan.md`](2026-06-13-online-offline-fallback-plan.md)
- operator runbook：[`2026-06-13-demo-operator-runbook-plan.md`](2026-06-13-demo-operator-runbook-plan.md)
- nav 能力階梯：[`docs/navigation/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)
- nav claim wording：[`docs/navigation/2026-06-13-nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)
- Roy HITL queue（C 段 N1-N8）：[`docs/runbook/2026-06-13-roy-hitl-queue.md`](../../runbook/2026-06-13-roy-hitl-queue.md)
- Lane 6 nav 實作工項：[`2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md`](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)
- Lane 1 ISM staged enable：[`2026-06-13-lane1-brain-ism-staged-enable-plan.md`](2026-06-13-lane1-brain-ism-staged-enable-plan.md)
- Lane 3 CLI v2：[`2026-06-13-lane3-cli-v2-completion-plan.md`](2026-06-13-lane3-cli-v2-completion-plan.md)
- post-refactor 驗收：[`docs/runbook/2026-06-13-post-refactor-acceptance-report.md`](../../runbook/2026-06-13-post-refactor-acceptance-report.md)
