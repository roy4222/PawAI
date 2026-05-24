# Nav KPI Matrix

> **文件類型**：KPI 定義（門檻 + delta + 計算公式 + source topic）
> **日期**：2026-05-24
> **配套**：[`../CAPABILITY-LADDER.md`](../CAPABILITY-LADDER.md)、[`schema.md`](schema.md)、[`baselines/`](baselines/)
> **決策來源**：Q3 三層門檻 + Q7 per-KPI delta + Q8 outcome enum

---

## 0. 通用規則

### 0.1 門檻語意（Q3）

每個核心 KPI 有三層絕對門檻：

```text
PASS    達標
WARN    可用但有風險
FAIL    不可展示
```

外加一個相對門檻：

```text
REGRESSED  相對 accepted.md baseline 退化超過該 KPI 規定 delta
```

**WARN 和 REGRESSED 分開計算**，可以同時。

### 0.2 樣本下限（Q7）

```text
runs < 3   → status = INSUFFICIENT_DATA, regression = UNKNOWN
runs >= 3  → 才開始判 WARN / FAIL / REGRESSED
```

只算 `session_source = manual` 的 run。

### 0.3 Outcome 過濾（Q8）

`SR` 等成功率分母**排除** `outcome IN (UNKNOWN, TIMEOUT_EXTERNAL)`。
這兩種是 recorder / ROS2 daemon 自身問題，不算 navigation 失敗。

如果 `TIMEOUT_EXTERNAL > 0` 或 `UNKNOWN > 0` → 報告 header 標 `metrics_integrity: FAIL`，整份 baseline 視為**作廢**（不允許 promote）。

### 0.4 KPI 引用的 source topic

主要來源：
- `/event/nav/mission` — Q8 定的內部 event（nav_action_server / route_runner 主動發）
- `/state/reactive_stop/status` — JSON @ 10Hz
- `/state/depth_safety/status` — **新增**，D435 證人 JSON（E1 主線 + 不進 costmap）
- `/event/nav/waypoint` — route_runner publish（A 案 canonical；legacy `/event/nav/waypoint_reached` 將 deprecate，見 §2 註）
- `/amcl_pose` + `/odom` — 已 publish
- Action result 是 fallback，不依賴

---

## 1. Phase 6 — Fixed-point navigation

**對應 mission outcome 事件**：`goto_relative` 或 `goto_named` 的 SUCCEEDED / ABORTED_* / CANCELED_*

| KPI | 公式 | PASS | WARN | FAIL | REGRESSED delta | Source |
|---|---|---|---|---|---|---|
| **SR** (success rate) | `COUNT(outcome=SUCCEEDED) / COUNT(outcome NOT IN (UNKNOWN, TIMEOUT_EXTERNAL))` | ≥ 85% | 70-85% | < 70% | ≤ baseline − 5pp | `/event/nav/mission` |
| **final_position_error** | `EUCLID(goal_pose, result_pose)` 的 P50（per scenario）；兩個 pose 都從 `/event/nav/mission` JSON 取，**不要 race `/amcl_pose`** | ≤ 0.20m | 0.20-0.35m | > 0.35m | ≥ baseline + 0.05m | `/event/nav/mission` (accepted event 帶 goal_pose, terminal event 帶 result_pose) |
| **time_to_goal** | `result_ts − accept_ts` 的 P50（per scenario，per 0.5m 標稱距離）| ≤ 20s | 20-35s | > 35s 或 timeout | ≥ baseline × 1.20 | `/event/nav/mission` |
| **no_progress_timeout** | `COUNT(outcome=ABORTED_NO_PROGRESS) per session` | 0 | 1 | ≥ 2 | ≥ baseline + 1 | `/event/nav/mission` |

**註**：
- final_position_error 取 P50 不是平均 — 避免一兩次 AMCL 漂移污染整段
- time_to_goal 必須 **per scenario_tag** 算 — 0.3m goal 跟 0.5m goal 不能混
- no_progress_timeout 對應 F7 blocker — 這條 ≥ 2 直接 FAIL，是診斷訊號

---

## 2. Phase 7 — Multi-point navigation

**對應 mission outcome 事件**：`run_route` 的整條 SUCCEEDED / ABORTED_* / CANCELED_*
**Sub-event**：`/event/nav/waypoint` per waypoint（含 reached/aborted/skipped event_type；legacy `/event/nav/waypoint_reached` 只發成功，是過渡期 fallback）

| KPI | 公式 | PASS | WARN | FAIL | REGRESSED delta | Source |
|---|---|---|---|---|---|---|
| **route_completion** | `COUNT(route outcome=SUCCEEDED) / COUNT(route attempts)` | ≥ 80% | 50-80% | < 50% | ≤ baseline − 5pp | `/event/nav/mission` (action=run_route) |
| **waypoint_completed_ratio** | `SUM(waypoints_completed) / SUM(waypoints_total)` 跨所有 route；`waypoints_completed` 從 mission result payload 拿 | ≥ 90% | 70-90% | < 70% | ≤ baseline − 5pp | `/event/nav/mission` result payload |
| **per_waypoint_abort** | `COUNT(waypoint_events.event_type='aborted') per route average` | 0 | 1 | ≥ 2 | ≥ baseline + 1 | `/event/nav/waypoint`（新；event_type 含 aborted/skipped）|

**註**：
- waypoint_completed_ratio 是 cross-route 加總，不是 per-route 平均 — 短 route 跟長 route 的 waypoint 同權重
- per_waypoint_abort 包含中途 reactive_stop 觸發後 route 整段降級的情況
- **資料源缺口（Finding 3 修正）**：舊版只訂 `/event/nav/waypoint_reached`（只發成功），這條 KPI 無 abort 訊號。Phase 7 開工 prerequisite：
  - **A 案**（推薦）：`route_runner_node` 改名 publish 成 `/event/nav/waypoint`，message JSON 加 `event_type: reached | aborted | skipped` + `waypoint_index` + `reason`。recorder 訂這條寫進 `waypoint_events` table（schema.md §1.3 已對齊 event_type enum）。
  - **B 案**（fallback）：`/event/nav/mission` route 結束的 result payload 必含 `waypoints_completed: int` + `waypoints_total: int` + `failed_waypoint_index: int?` + `abort_reason: str?`。recorder 從 result 反推 abort 數。
  - A 跟 B 至少擇一，不然 per_waypoint_abort 永遠標 INSUFFICIENT_DATA。

---

## 3. Phase 8 — Dynamic obstacle avoidance

**對應 mission outcome 事件**：mission 進行中發生的 reactive_stop pair（`reactive_stop_engaged` → `reactive_stop_disengaged`）
**特殊**：`no_auto_resume` 是**安全紅線**，不允許 WARN 層

| KPI | 公式 | PASS | WARN | FAIL | REGRESSED delta | Source |
|---|---|---|---|---|---|---|
| **time_to_stop (TTS)** | `robot_stopped_ts − danger_entered_ts`（`/odom.linear.x < 0.05` 視為 stopped）的 P50，**僅計入 `pre_danger_speed ≥ 0.10m/s` 的事件**；其他標 `not_applicable` 不進分母 | ≤ 400ms | 400-700ms | > 700ms | ≥ baseline + 100ms | `/state/reactive_stop/status` + `/odom` |
| **stop_margin** | `obstacle_distance_at_stop − go2_nose_offset_m` 的 P50（`go2_nose_offset_m` 由 `session_meta` 帶 metadata 不寫常數）| ≥ 0.25m | 0.10-0.25m | < 0.10m **或碰撞** | ≤ baseline − 0.05m | `/state/reactive_stop/status` + `session_meta.go2_nose_offset_m` |
| **no_auto_resume** | `任一 mission 在 reactive_stop_disengaged 後未經明確 resume / 新 goal 即重新移動 → false` | **true** (100% pass) | — | **任一 false** | 任一 false 直接 REGRESSED | `/state/reactive_stop/status` + `/event/nav/mission` + `/odom` |
| **brake_false_positive_ratio** | `SUM(t where lidar_zone IN ('danger','emergency') AND witness_zone='clear') / SUM(t where lidar_zone IN ('danger','emergency'))`；**witness 必須是獨立感測（D435）或人工 ground truth**，不能用 LiDAR 自己 | ≤ 10% | 10-25% | > 25% | ≥ baseline + 5pp | `sensor_observations` JOIN (lidar source vs witness source) + 時間對齊 |

**註**：
- **TTS pre_danger_speed gate（Finding 2 修正）**：障礙進 danger 那一瞬 Go2 若本來就站著（reactive_stop hold_brake、或 mission 還沒 started、或剛 succeeded），`/odom.linear.x` 已歸零 → TTS 算出 0ms 是假 PASS。`pre_danger_speed` 從 `danger_entered_ts − 500ms` 取 `/odom.linear.x` 平均，< 0.10m/s 視為「本來就沒動」→ 事件標 `not_applicable`，不進 TTS 分母也不進 stop_margin 分母（stop_margin 該事件仍記 row 但 status 旗標 `not_applicable`）。
- **stop_margin offset 是 metadata（Open Q1 修正）**：寫進 `session_meta.go2_nose_offset_m`（default 0.50m，5/13 後卡尺量完更新）。跨 session 比較時不同 offset 的 stop_margin 不能直接比 — `nav_kpi_report.py` 必須拒絕 promote 如果 baseline 跟 latest 的 offset 不一致。
- stop_margin 設計動機（5/11 撞牆事件）：LiDAR 在 base_link 前 17.5cm，但 Go2 機鼻在 ~50cm，原始 obstacle_distance 不減 offset 會高估 0.3m+。
- **no_auto_resume 是紅線**：任一次 false → 整個 Phase 8 直接 REGRESSED，該 session 不準 promote，該 phase UNLOCKED 立即降為 IN_PROGRESS。
- **brake_false_positive_ratio 重定義（Round 3 Finding 1 修正）**：之前兩版公式都犯一個本質錯誤 — **LiDAR 不能當自己的證人**。要量「LiDAR 誤判 danger」必須拿獨立來源比對：
  - **W1**（推薦）：D435 zone（`/state/depth_safety/status` 出來的證人 JSON），公式 = `lidar=danger AND d435=clear` 的時間佔比
  - **W2**（場測補強）：人工 ground truth 標籤（場測前 scenario_tag 註記「無真實障礙」的 session），公式 = `lidar=danger AND manual_truth=clear`
  - **W3**（回放）：rosbag replay 時人工標記障礙物 ground truth
  
  W1 是第一版實作目標 — 直接用 `sensor_observations` 同 timestamp window join lidar vs d435 source 兩 row。W2 / W3 是 W1 鑑別力不足時的補強。
  
  關鍵：**LiDAR 不能跟自己比**，這是「證人 vs 裁判」原則的具體變現。一個感測器自己判 danger 自己鎖車自己驗證沒誤鎖 — 邏輯上不可能成立。

- **資料前提**：W1 需要 D435 status JSON 持續發佈（Q5 主線 E1 + `/state/depth_safety/status`）+ sensor_observations 有 d435 source row 跟 lidar source row 時序對齊。沒有 D435 證人 = brake_false_positive_ratio 標 `INSUFFICIENT_WITNESS`，不算 KPI。

- **hold_brake 不入此 KPI 分母**：`mode=hold_brake` 是 B5 stop 驗證 / demo emergency hold 的**刻意**永久煞車，分母過濾 `mode='progressive' AND nav_profile='main'` 的時間（用 `sensor_observations.mode` 欄位查 — 見 schema.md §1.4 round 3 新增 columns）。hold_brake session 另成立 **safety-hold smoke** 測項：驗證 `mode=hold_brake` 期間 `/cmd_vel_obstacle` 100% 輸出 0、Go2 velocity 全程 < 0.05m/s。

---

## 4. Phase 12 — Brain / OpenClaw Integration

**狀態**：定義先擺著，等 Executive NAV executor 接通後才有 runtime source 可填。
**對應事件**：Brain skill 觸發 → Executive 呼叫 nav action → result

| KPI | 公式 | PASS | WARN | FAIL | REGRESSED delta | Source |
|---|---|---|---|---|---|---|
| **nav_skill_invoke_success** | `COUNT(Brain nav skill → Executive accepted) / COUNT(Brain nav skill emitted)` | ≥ 95% | 80-95% | < 80% | ≤ baseline − 3pp | `/executive/status` + Brain skill log |
| **executive_block_reason_clarity** | `COUNT(BLOCKED_BY_SAFETY 帶明確 reason) / COUNT(all BLOCKED)` | 100% | 90-100% | < 90% | — | `/executive/status` |

**註**：當前 status = LOCKED_BY_PHASE_6，nav-kpi-matrix 不對它收 baseline，但 schema 留欄位。

---

## 5. Phase 9 / 10 / 11 — LOCKED / SPEC_ONLY

對應 ladder 狀態：`LOCKED / SPEC_ONLY`，無 code 也無 runtime source。

**規則**：這節**不定義** KPI，避免為不存在的 capability 蓋假 schema。
等該 phase 進入 IMPLEMENTED_UNMEASURED 時再補。

預留章節：
- Phase 9 person following — 預期 KPI: tracking_continuity / distance_keeping_sigma / target_loss_recovery_time
- Phase 10 free-space — 預期 KPI: floor_mIoU / false_floor_rate / depth_fusion_gain
- Phase 11 sim-to-real — 預期 KPI: sim_real_SR_delta / sensor_noise_KL / replay_determinism

> 上述為「等做的時候會用到」的占位清單，**不是承諾**。

---

## 6. Supplementary KPI（不卡 UNLOCKED）

這些 KPI 不卡 ladder 解鎖，但會出現在每份 baseline markdown 的 supplementary 區，給趨勢分析用。

| KPI | 用途 | 計算 | Source |
|---|---|---|---|
| **SPL** | Success weighted by Path Length，Habitat / BARN 學術標準 | `SR × (straight_line_distance / max(actual_path, straight_line))` | `/event/nav/mission` + `/odom` 累積路徑 |
| **SCT** | Success weighted by Completion Time，BARN dynamics-aware | `SR × clip(optimal_time / actual_time, 0, 1)`，`optimal_time = distance / 0.5m/s` | 同上 |
| **recovery_count** | Nav2 behavior_server 觸發次數 / mission | 訂閱 `/behavior_server/*/_action/status` 或 result message recovery 標誌 | Nav2 BT log |
| **AMCL_cov_improve** | Mission 開始時 vs 結束時 covariance_xy 差值 | session start - session end | `/state/nav/status` |
| **cmd_vel_nav_active_ratio** | mission 期間 `/cmd_vel_nav` 有 publisher 且 Hz ≥ 5 的時間佔比 | sample @ 1Hz during mission | `/cmd_vel_nav` 訂閱端統計 |
| **disagreement_rate** | LiDAR zone vs D435 zone 不一致的時間佔比（fusion 研究核心數字）| `SUM(t where lidar_zone ≠ d435_zone) / session_time` | `/state/reactive_stop/status` + `/state/depth_safety/status` |
| **lidar_only_FP_hold** | LiDAR 說 danger 但 D435 說 clear 的時間（候選 false positive） | `SUM(t where lidar=danger AND d435=clear)` | 同上 |
| **d435_only_FP_hold** | 反向 | `SUM(t where d435=blocked AND lidar=clear)` | 同上 |
| **stop_margin_lidar_only** vs **stop_margin_fused** | 同事件下兩種策略推算的停車 margin（fusion shadow study）| `min(lidar_distance, d435_min_depth) − nose_offset` vs `lidar_distance − nose_offset` | 同上 |

**關鍵**：
`disagreement_rate` + `lidar_only_FP_hold` + `d435_only_FP_hold` 三個是「先做證人」原則的具體變現 — D435 不進 costmap，但這三個數字會直接告訴你：之後要不要進 costmap、進的話 OR / AND / weighted 怎麼選。

---

## 7. KPI ↔ Ladder 對應流程

```text
1. nav_metrics_recorder_node 持續 INSERT rows
2. Session 結束 → nav_kpi_report.py 跑：
   2.1 對每個 phase 算核心 KPI 值
   2.2 對比 §0.2 樣本下限 → 標 INSUFFICIENT_DATA
   2.3 對比 §1-§3 PASS/WARN/FAIL 門檻 → 標當下狀態
   2.4 對比 accepted.md 同 scenario 的 baseline → 算 REGRESSED delta
   2.5 metrics_integrity check (Q8.3) → 標報告 header
3. 輸出 latest.md (覆寫) + 不動 accepted.md
4. 人工 `pawai nav metrics promote` → accepted.md 才更新
```

`pawai nav metrics promote` 預期實作為 `cp latest.md accepted.md` + `git add accepted.md` + 提示 commit message。

---

## 變更紀錄

- 2026-05-24 first draft（Q3 / Q7 / Q8 + supplementary 區包含 fusion-ready KPI）
