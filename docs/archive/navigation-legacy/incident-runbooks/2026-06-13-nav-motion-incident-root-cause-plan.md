# Nav Motion Safety Incident — Root-Cause Investigation & Plan（2026-06-13）

> **日期**：2026-06-13　**狀態**：INVESTIGATION + PLAN（純研究產出；**零 motion / goto / cmd_vel 指令發出**）
> **觸發**：HITL #2 Task 3 — `goto_relative 0.3m` 第一發走歪撞牆，Roy e-stop 中止（[post-refactor acceptance §附錄 Task 3](../runbook/2026-06-13-post-refactor-acceptance-report.md)）。
> **方法**：repo-grounded（讀 code，不臆測）+ 18-agent 對抗式驗證 workflow（6 軸調查 × 12 refute/confirm 投票）。
> **這份是什麼**：①事件根因（多因，**非單一 AMCL**）②證明/反證每個因的證據與測試 ③P0-P3 修法 ④S1 demo 改線 ⑤claim 措辭更新 ⑥rollback / stop 條件。
> **這份不是什麼**：① 不是「nav 已修好」的宣告——**nav motion 維持 `NOT_DEMO_READY`** ② 不授權任何 motion——所有 motion 項都標 **needs Roy + e-stop**。
> **權威關係**：升級 nav label 只能透過 [capability ladder](2026-06-13-nav-capability-ladder.md) §8 HITL matrix；本檔的修法落地後回填 ladder + [claim wording](2026-06-13-nav-618-claim-wording.md)。

---

## 0. 硬限制（本調查全程遵守，也是後續執行的紅線）

1. **不發 motion / goto / cmd_vel**——在 root cause 被證明修好 + n 次無撞重驗前。
2. **不把 nav motion 標 ready**——維持 `NOT_DEMO_READY`（[ladder C1/C2](2026-06-13-nav-capability-ladder.md)）。
3. **不 overclaim autonomous navigation**——任何「自主導航/繞障/找人」一律 forbidden（[claim wording §4](2026-06-13-nav-618-claim-wording.md) F1-F10）。
4. **D435 fusion 不寫成已完成**——現況只有 `depth_clear` fail-closed gate（Brain 層），**未進 Nav2 costmap**。
5. 每個 task 標 **pure software / Jetson needed / Go2 motion needed**；每個 task 附 tests / HITL checklist / rollback。

---

## 1. Incident Summary

2026-06-13 晚 HITL #2，nav stack（`start_nav_capability_demo_tmux.sh`，profile=**open_space ±30°**）起來後：

- **靜態閘全綠**：LiDAR `/scan_rplidar` 11.8 Hz、前方 ±15° 約 2.38m 淨空、`reactive_stop` zone=slow 但 `active=false`、`nav_ready=True`（Foxglove `/initialpose` 後）、`pawai smoke nav --static` **8/8 PASS**。
- **第一發 `goto_relative 0.3m`**（Roy 用 `scripts/send_relative_goal.py`，`yaw_offset=0`、direct action、**未經 Brain/IE**）→ Go2 **沒有直直前進，而是歪斜前進並撞到 +25°/1.65m 側邊家具**，Roy e-stop。

**一句話**：靜態安全閘證明「鏈路通 + 定位 position 收斂 + 正前方淨空」，但**沒有一個閘證明「機器人朝向是對的」或「歪斜移動時側向是安全的」**——所以 8/8 PASS ≠ motion safe，第一發 goto 就走歪撞牆。

**結論**：nav 短距 goto 在目前 initialpose 朝向精度 + goto 超衝行為 + reactive_stop 側向幾何下 **NOT_DEMO_READY / NOT safe**。

---

## 2. Confirmed Facts（全部 code/doc 級證據）

### 2.1 「前方」是 AMCL map-frame yaw，不是 robot body frame（B 軸核心）

- `goto_relative` 的 forward 向量由 **AMCL 相信的 map-frame yaw** 算出：
  - `nav_capability/nav_capability/lib/relative_goal_math.py:27-30`：
    `target_heading = current_yaw + yaw_offset` → `goal = (cx + d·cos, cy + d·sin)`。
  - `current_yaw` 唯一來源 = AMCL `/amcl_pose` 四元數：`nav_action_server_node.py:259-266 _current_map_pose → quat_to_yaw`。
  - goal 一律 `frame_id="map"`：`nav_action_server_node.py:462`。
- **沒有 body-frame / 純 odom direct-forward path**。`nav_action_server_node.py:4-5` 明寫「v1: 一律走 map frame（需要 AMCL 在線）；純 odom path 列入 spec T5」。
- ⟹ **AMCL yaw 偏 θ，整條 0.3m 向量就在 map 旋轉 θ → 斜走**。Roy 假設 #3/#4 在 code 層成立。
- 事件當天 client `scripts/send_relative_goal.py` 預設 `--yaw-offset 0.0`（`:149`）→ goal heading = AMCL current_yaw 原值，無額外偏移注入，確認偏移來自 AMCL 本身。

### 2.2 安全閘是 yaw-blind 的（C 軸 / H4，最關鍵的「靜態 pass ≠ safe」證明）

- AMCL 閘只看 **position covariance**：`nav_action_server_node.py:252-257 _amcl_covariance_xy` 回傳 `c[0]+c[7]`（σ²x+σ²y），**從不檢查 `c[35]`（σ²yaw）**。閘邏輯 `:417-442`（red>0.5 / yellow 0.3-0.5 限 ≤0.5m / green ≤0.3）全是 position-only。
- `nav_ready` 同樣 yaw-blind：`nav_capability/lib/nav_ready_check.py:30-54` 只用 `covariance_xy`；launch 預設 `covariance_threshold=0.45`（`nav_capability.launch.py:51-53`，position-only）。
- `scripts/smoke_test_nav_static.sh` 8 項全靜態：node 在 / scan hz / `/amcl_pose` 存在 / action server 可見 / reactive status 可見——**沒有一項驗 heading 或 map↔scan 對齊**。
- ⟹ **covariance 綠燈不保證 yaw 對**：covariance 反映粒子離散度，不反映「相對真實朝向的誤差」；剛手設 initialpose、機器人靜止（AMCL `update_min_d/a=0.10`，`nav2_params.yaml:41-42`）時，AMCL **不會自我修正 yaw**，可以「自信地錯」。

### 2.3 goto 會超衝——「0.3m」實際走更遠（B 軸放大器，事件變撞牆的關鍵）

- `nav_action_server` **不 enforce `max_speed`**：`nav_action_server_node.py:406-414` 明寫 v1 忽略 `goal.max_speed`，速度由 `nav2_params.yaml` controller 決定。
- DWB 最低速 **≥0.45 m/s**：`nav2_params.yaml:159,164 min_vel_x=0.45 / min_speed_xy=0.45`（Go2 sport mode MIN_X≈0.50 門檻）。短 goal 也以 ≥0.45 m/s 衝。
- **已實測超衝數據**：[`research/2026-06-13-spec-d435-lidar-fusion.md:10-26` §0](research/2026-06-13-spec-d435-lidar-fusion.md)：**0.5m goal 走到 1.04m（超衝 0.54m）**，根因正是 max_speed 不 enforce + Go2 sport-mode 慣性 + StopMove 延遲（[CLAUDE.md：cmd_vel=0 不停車、sport timeout 2-3s]）。
- ⟹ 一個「0.3m」指令在斜方向上可走到 **~1m**，足以從 0.3m 名義距離抵達 1.0-1.7m 外的家具。**這是「小角度偏差」變「撞牆」的物理橋樑**——不能只講 AMCL。

### 2.4 reactive_stop 救不了側向斜走（D 軸 / H2，mechanism 確認）

- profile=**open_space** 預設：`start_nav_capability_demo_tmux.sh:37-40` → `front_arc_deg=30`（±30° 錐）、`danger=1.1`、`slow=1.7`、`front_offset_rad=π`。
- +25°/1.65m 家具：在 ±30° 錐內，但 `1.1 < 1.65 < 1.7` → `classify_zone="slow"`（`lidar_geometry.py:54-63`）。
- progressive mode 在 slow **沉默**：`lidar_geometry.py:109-112 decide_velocity("slow","progressive")→None`；`reactive_stop_active` 只在 danger/emergency（`reactive_stop_node.py:276`）→ **active=false、不擋**（與現場觀測一致）。
- 安全錐是 **body-forward**（`compute_front_min_distance` 取角度扇形最小距離，`lidar_geometry.py:5-51`），**不對齊斜走路徑、不考慮機身寬度（footprint 0.6×0.3m、機鼻 ~0.4-0.5m）**——off-axis 障礙進 danger 前機身角已可能接觸。
- `front_arc_deg/danger/slow/front_offset_rad` **只在 `__init__` 讀**（`_on_param_change` 只收 `enable_nav_pause/safety_only/mode`，`reactive_stop_node.py:173-197`）→ 改窄場 profile 必 kill 重啟。

### 2.5 TF chain 乾淨、無重複 publisher，LiDAR 外參是「手設 yaw=π」（A 軸）

- 鏈路：`map →(AMCL)→ odom →(driver, GO2_PUBLISH_ODOM_TF=1)→ base_link →(static TF yaw=π)→ laser`。
  - driver 發 odom→base_link：`go2_robot_sdk/.../ros2_publisher.py:29,66-91`，env 預設 `GO2_PUBLISH_ODOM_TF=1`，nav script 未覆寫 → driver own（AMCL 需要）。
  - base_link→laser：`start_nav_capability_demo_tmux.sh:69-72` static_transform_publisher **`x=0.175 y=0 z=0.18 yaw=3.14159`**（手設，**啟動腳本內無物理校正步驟**）。
  - URDF `lidar_joint` 是 CAD 幾何（`go2_on_steroids.urdf:1257-1269`，yaw=0），**被外部 static TF 覆寫**。
- **無重複 TF publisher**（slam:=false，cartographer 不跑；driver vs static 各管不同 edge）。
- `front_offset_rad=π`（reactive_stop）與 base_link→laser TF yaw=π 是**雙重獨立補正、必須一致**（`lidar_geometry.py:20-36`），啟動腳本兩處都填 π，一致。
- ⚠️ **LiDAR 外參是手設、無 per-session 校正**：v8 yaw=π 在 5/1 用「使用者站機鼻」物理錨定驗過一次（covariance σ²x 0.223→0.033，[`research/2026-05-01-amcl-180-degree-diagnosis.md`](research/2026-05-01-amcl-180-degree-diagnosis.md)），但**之後每次 demo 沒有重新確認**。

### 2.6 D435 在 nav 裡只是 Brain 層 gate，未進 costmap（E 軸，禁 overclaim）

- D435 → `/capability/depth_clear`（Bool, latched, fail-closed）：ROI 中央 50%、<0.4m 像素 ≥5% → false（`go2_robot_sdk/depth_safety_node.py` + `depth_geometry.py:20-90`）。
- 消費者是 **Brain/IE SafetyLayer**（`interaction_executive/safety_layer.py:133-140`，擋 NAV+MOTION skill）。
- **D435 沒進 Nav2 costmap**：`nav2_params.yaml:220-238 obstacle_layer.observation_sources` 只有 `/scan_rplidar`。**無 `/scan_d435`、無 depthimage_to_laserscan / pointcloud_to_laserscan node 被啟動**。
- ⚠️ **事件當天 depth_clear 不在保護路徑上**：Roy 用 `send_relative_goal.py` direct action → **bypass Brain/IE SafetyLayer**；nav_action_server 自己**不檢查 depth_clear**（只查 odom 活性 + AMCL covariance + paused）。直接 action 路徑只剩 yaw-blind AMCL 閘 + reactive_stop 兩道。
- D435 目前有 **Right MIPI / Hardware Error**（handoff）→ 短期不可硬依賴。

### 2.7 場地是小客廳（margin 薄）

- `home_living_room_v8.yaml`：origin `[-2.41,-2.81,0]`、res 0.05、205×98 px = **10.25×4.90m**。家具密、margin 薄——斜走幾十公分就到牆/家具。

### 2.8 Studio initialpose 設定無 sanity check（H1 的操作面入口）

- Studio 兩段點擊設 initialpose：click1=位置、click2/拖曳=yaw（`atan2(-(dy),dx)`，`nav-map-canvas.tsx:239-245`），**無 bounds/合理性檢查**；gateway 直接 `sin(yaw/2)/cos(yaw/2)` 發 `/initialpose`（`studio_gateway.py:487-507`）。
- **錯的 yaw 在畫面上看起來是對的**（綠三角沿 yaw 指向；cartographer/AMCL 對任何 yaw 都建出內部一致的 map）——5/1 v7 即「畫面對、實體錯 180°」。

---

## 3. Likely Root Causes — Ranked（多因，對抗式驗證後）

> 驗證方法：6 假設 × 2 lens（code-mechanism / skeptic）對抗投票。verdict 直接標在每項。

> **🔴 2026-06-13 後續更新（runbook 階段新增）**：發現一個 **code 級新確認、排序應在 R1 之前先排除的共同主因 T0**——單機 nav 載入的 `go2.urdf` 把 `map→odom`（`map_joint`）/`odom→base_link`（`odom_joint`）宣告成 **`type="fixed"` identity**（`go2.urdf:48-58,70-80`），`robot_state_publisher` 會把 fixed joint 發到 `/tf_static`（`robot.launch.py:67,219-237`），與 AMCL 動態 `map→odom`（`nav2_params.yaml:38`）+ driver 動態 `odom→base_link`（`ros2_publisher.py:29`）**雙重 authority 衝突**；依 tf2 規格 static「good across all time、cannot change after first call」可遮蔽動態定位。**T0 與 R1 都表現成「朝向不對→走歪」，必須先用 no-motion 診斷（`ros2 topic echo /tf_static`）排除 T0**。完整 TF authority matrix + 外部 REP-105/tf2 依據 + 修法見 **[`2026-06-13-nav-incident-runbook.md`](2026-06-13-nav-incident-runbook.md) §2/§4**。

| # | 根因 | 角色 | 驗證 verdict | 為何 |
|---|---|---|---|---|
| **R1** | **AMCL initialpose 朝向(yaw)誤差**，經 map-frame goto 注入「前方」 | **PRIMARY** | code STRONGLY_SUPPORTED / skeptic SUPPORTED（H1） | §2.1+§2.2；事件報告直指「朝向不準」；操作面 §2.8 易設錯、§2.5 無 per-session 校正 |
| **R2** | **goto 超衝**：max_speed 不 enforce + Go2 sport 慣性 → 0.5m 走 1.04m | **CRITICAL AMPLIFIER**（小偏差→撞牆的物理橋） | code-doc CONFIRMED（§2.3，spec §0 實測） | 0.3m 名義走 ~1m，才會抵達 1.0-1.7m 外家具；skeptic 對 H2 的質疑（「0.3m 不該到 1.65m」）正由此解答 |
| **R3** | **reactive_stop 側向幾何**：off-axis slow-band silent + body-forward 錐 + 無 footprint/corridor | **CONTRIBUTING（mechanism 確認、量值待數據）** | code STRONGLY_SUPPORTED / skeptic PLAUSIBLE_UNPROVEN（H2） | §2.4；但「撞的是不是那個 +25°/1.65m」需 log 佐證（也可能是 ±30° 錐外更近物或被超衝帶到） |
| **R4** | **無 body-frame direct mode**：每次短移都人質於 AMCL 朝向 | **ARCHITECTURAL ENABLER（修法正方向，但非免費）** | code STRONGLY_SUPPORTED / skeptic SUPPORTED（H3） | §2.1；但 skeptic 提醒：純 odom body-frame 仍有 Go2 步態 yaw drift，須綁 reactive_stop + 限距 |
| **R5** | **靜態閘 yaw-blind**：8/8 / nav_ready 不驗朝向、不驗 scan 對齊 | **ENABLING CONDITION（為何沒被擋下）** | code STRONGLY_SUPPORTED / skeptic STRONGLY_SUPPORTED（H4） | §2.2；這是「static pass ≠ motion safe」的根 |
| R6 | LiDAR mount yaw / 外參物理 miscalibration | **DOWNGRADED（非 primary，待 no-motion 確認）** | skeptic REFUTED-as-primary（H5） | §2.5；trackB §4 已判「不是 TF bug」；v8 yaw=π 驗過。但 per-session 未重驗，列 no-motion 檢查 |
| R7 | DWB 短 goal 行為（rotate-in-place 不可、tolerance 寬）造成斜 | **MINOR（amplifying，非本次主因）** | code WEAK / skeptic REFUTED-as-primary（H6） | trackB §3 micro-skew 排序（gait 60%>DWB 30%>TF 10%）是**成功移動**的微歪，非本次 macro 撞牆 |

**綜述（誠實版，非單一 AMCL）**：
> 操作員手設 initialpose 朝向偏 θ（R1，§2.8 無防呆）→ AMCL position 收斂綠但 yaw 沒被任何閘驗（R5/§2.2）→ goto 把「前方」算在 map 的歪方向（R1/§2.1，因為沒有 body-frame 退路 R4）→ 8/8 靜態全綠放行（R5）→ Go2 以 ≥0.45 m/s 朝歪方向**超衝到 ~1m**（R2，0.5m→1.04m 實測）→ reactive_stop 對這個 off-axis、slow-band、body-forward 錐外/邊緣的家具**沉默或來不及**（R3）→ 撞。
> **R1 是源、R2 是放大器、R3 是最後一道沒守住、R5 是為何全程沒被擋。缺 R2 不足以從 0.3m 撞到 1.65m。**

---

## 4. Evidence Needed to Prove / Disprove Each Cause

> 全部可由**已落地的 instrumentation + no-motion 量測**取得；motion 證據另列 §7（需 Roy + e-stop）。

| 根因 | 證明它 | 反證它 | 資料來源（已存在） |
|---|---|---|---|
| **R1 AMCL yaw** | 靜置量 `θ_error = AMCL_yaw − 真實機身朝向`（用 LiDAR 對牆/門框幾何錨定）。θ_error 顯著（>5-10°）即成立 | θ_error<±5° 且 `c[35]`<0.05 → AMCL 朝向其實準，R1 反證、轉查 R2/R3 | `/amcl_pose`（含完整 6×6 covariance）、`scripts/lidar_front_sector.py`、`scan_health_check.py` |
| **R2 超衝** | 重放當天 `[PR1a]` log：`accept_pose / goal / actual_dist_from_accept / duration`——actual ≫ 0.3m 即超衝 | actual≈0.3m 且方向對 → 無超衝，撞因另尋 | `nav_action_server_node.py:383-516 [PR1a]` log（brain/nav log）；`pawai evidence pull` 拉 trace |
| **R3 reactive_stop** | 重放 `/state/reactive_stop/status` 時間線：撞擊前 zone 是否一直停在 slow / active=false | 撞前曾進 danger 卻沒發 0 → 是別的 bug（mux/teleop），非幾何 | `/state/reactive_stop/status` JSON（已含 zone/obstacle_distance/active/since_last_zone_change） |
| **R4 無 body-frame** | code 既證（§2.1）。對照測：body-frame 模式在 AMCL 故意設歪時仍走直 | —（架構事實，不需反證） | code review |
| **R5 yaw-blind 閘** | code 既證（§2.2）。零距離 goal（distance=0）在 yaw 大錯下仍 PASS = 閘無能力擋 | —（架構事實） | code review + no-motion zero-goal probe |
| **R6 外參** | `tf2_echo base_link laser` 讀 RPY；物理錨定（使用者站機鼻 → scan 應落 ±180°，因 yaw=π） | RPY=[0,0,π] 且物理錨定吻合 → 外參對，R6 反證 | `tf2_echo`、`scan_health_check.py`、`lidar_front_sector.py` |
| **R7 DWB** | 對照：AMCL yaw 確認準後仍走歪 → DWB 嫌疑 | AMCL yaw 準時走直 → DWB 非主因 | 需 R1 先排除（順序依賴） |

**最高價值單一證據** = 當天那發 goto 的 `[PR1a]` log + 同時段 `reactive_stop/status`：一次回答 R1（goal 方向）、R2（actual 位移 vs 0.3m）、R3（zone 時間線）。**收工前優先 `pawai evidence pull` + 抓 nav log**（只讀、無 motion）。

---

## 5. Code Paths to Inspect（file:line，給修法/複查）

**Goal 方向 / body-frame（R1/R4）**
- `nav_capability/nav_capability/lib/relative_goal_math.py:27-31` — forward = AMCL yaw（核心）。
- `nav_capability/nav_capability/nav_action_server_node.py:259-266`（`_current_map_pose`/`quat_to_yaw`）、`:444-470`（建 map goal）、`:4-5`（v1 map-frame only 註解）、`:406-414`（max_speed 不 enforce）。
- `nav_capability/nav_capability/lib/tf_pose_helper.py:12-16`（`quat_to_yaw`）。

**AMCL 閘 / nav_ready / 靜態 smoke（R5）**
- `nav_capability/nav_capability/nav_action_server_node.py:252-257`（`_amcl_covariance_xy` = c[0]+c[7]）、`:417-442`（red/yellow/green）。
- `nav_capability/nav_capability/lib/nav_ready_check.py:30-54`（position-only）；`capability_publisher_node.py:72`（threshold param）；`nav_capability/launch/nav_capability.launch.py:51-53`（default 0.45）。
- `scripts/smoke_test_nav_static.sh:69-121`（8 項靜態檢查）。
- AMCL params：`go2_robot_sdk/config/nav2_params.yaml:1-51`（`update_min_d/a=0.10`、`set_initial_pose:false`、alpha 0.4、OmniMotionModel）。

**超衝 / DWB（R2/R7）**
- `go2_robot_sdk/config/nav2_params.yaml:154-195`（DWB：`min_vel_x=0.45`、`max_vel_x=0.70`、`xy_goal_tolerance=0.10`、`yaw_goal_tolerance=0.70`、SmacPlannerHybrid `minimum_turning_radius=0.30` REEDS_SHEPP `:310-324`）。
- `go2_robot_sdk/.../application/services/robot_control_service.py`（StopMove 路由、1 Hz dedupe；MIN_X / cmd_vel=0 不停車）。
- `research/2026-06-13-spec-d435-lidar-fusion.md:10-26`（0.5m→1.04m 實測）。

**reactive_stop 幾何（R3）**
- `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py:74-78`（thresholds/arc）、`:173-197`（param 只收 3 個 runtime）、`:259-276`（publish gate + active 定義）。
- `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py:5-51`（front_min，無 footprint）、`:54-63`（classify）、`:66-118`（decide_velocity）。
- `scripts/start_nav_capability_demo_tmux.sh:37-49`（profile）。

**TF / 外參（R6）**
- `scripts/start_nav_capability_demo_tmux.sh:69-72`（base_link→laser yaw=π）。
- `go2_robot_sdk/go2_robot_sdk/infrastructure/ros2/ros2_publisher.py:27-92`（odom→base_link、GO2_PUBLISH_ODOM_TF）。
- `go2_robot_sdk/launch/robot.launch.py:543-575`（nav2 + AMCL localization 接線、cmd_vel→cmd_vel_nav remap）。

**D435 / costmap（E）**
- `interaction_executive/interaction_executive/safety_layer.py:103-140`（depth_clear/obstacle gate；direct action 不經此）。
- `go2_robot_sdk/go2_robot_sdk/depth_safety_node.py` + `depth_geometry.py:20-90`；`nav2_params.yaml:220-238`（costmap 只吃 /scan_rplidar）。

**Studio initialpose（H1 操作面）**
- `pawai-studio/frontend/components/navigation/nav-map-canvas.tsx:239-245,87-111`；`pawai-studio/gateway/studio_gateway.py:487-507`。

---

## 6. No-Motion Diagnostic Tests（**安全，不動 Go2；可立即做**）

> 全部 `pure software / Jetson needed`（讀 topic / 跑既有診斷腳本），**零 motion**。是 §7 motion 測試的**前置門檻**。

### D0 — 證據回收（最先做，收工前）
- `pawai evidence pull`（拉 `runtime/traces/*.jsonl` + nav_capability 備份，只讀）→ 找當天 `[PR1a]` log 行（`nav_action_server` ACCEPT/DONE/END）+ `/state/reactive_stop/status` 紀錄。
- **產出**：當天 goal 方向、`actual_dist_from_accept`、duration、zone 時間線。一次定 R1/R2/R3。
- Tag：pure software（dev 機跑 CLI）。Rollback：只讀，無。

### D1 — AMCL yaw 真值比對（R1/R6）
- nav stack 起來、設好 initialpose、機器人**不動**。用「**使用者站 Go2 機鼻 0.5m**」物理錨定（5/1 黃金標準、無誤判）：
  - `python3 scripts/lidar_front_sector.py` → 人應落 **±180° bin**（因 yaw=π）；落別處 = 外參或 mount 偏。
  - `ros2 topic echo /amcl_pose --once` → `quat_to_yaw` 算 AMCL yaw；對比牆面/門框幾何真值。
  - 讀完整 covariance：`c[35]`（σ²yaw）。
- **判定**：`|θ_error|>5-10°` → R1 成立；`c[35]` 大但 position 綠 → 證 R5（閘 yaw-blind 放行）。
- Tag：Jetson needed（no motion）。

### D2 — 靜態閘 yaw-blind 實證（R5）
- 故意設一個 yaw 大錯但 position 準的 initialpose（純設 pose，不發 goal）→ 看 `nav_ready`/`smoke nav --static` 是否仍全綠。
- **預期**：全綠（證明閘無法擋朝向錯）。
- Tag：Jetson needed（no motion）。

### D3 — TF / 外參審計（R6）
- `ros2 run tf2_ros tf2_echo base_link laser` → 確認 RPY=[0,0,π] 對上啟動腳本。
- `scan_health_check.py` 跑一輪（phantom arc / 360° bin）。
- Tag：Jetson needed（no motion）。

### D4 — reactive_stop 側向幾何台架驗（R3，無 Go2 motion）
- 機器人**站著不動**，人/箱子放 +25°/1.65m、再移到 +25°/1.0m、+25°/0.8m：echo `/state/reactive_stop/status` 看 zone 何時進 danger。
- 比較 open_space(±30°) vs indoor_tight(±18°)：±18° 下 +25° 是否完全出錐（→ 完全偵測不到的取捨）。
- Tag：Jetson needed（no Go2 motion；只移動障礙物）。

### D5 — covariance 收斂曲線（C 軸 SOP 前置，無 motion）
- 新腳本 `scripts/nav_covariance_probe.py`（Lane 6 T6-5②，**待寫**）：initialpose 後靜置量 `c[0]+c[7]` **與 `c[35]`** 收斂曲線 → 填黃帶決策表（含 yaw 維度）。
- Tag：pure software（腳本）+ Jetson（量測，no motion）。

---

## 7. Safe Motion Tests — **ONLY if Roy approves + e-stop ready**

> **前置硬門檻（全部 PASS 才可開始）**：D1（θ_error<5° 或已用 SOP 校正進準）+ D3（外參對）+ e-stop（`nav_capability/scripts/emergency_stop.py engage` 終端就位、口頭確認）+ 淨空場地 + indoor_tight profile。
> 沿用 [Lane 6 §8 硬性 abort criteria](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)：非命令方向移動 / 該停沒停 / 機鼻<0.3m 仍動 → **當場 e-stop + 該項 FAIL**。

| # | 測試 | 前置 | 中止手段 | 升級對象 |
|---|---|---|---|---|
| M1 | **initialpose yaw 校正 SOP 後**，goto 0.3m × n=3，每發記 `[PR1a]` actual/方向 + covariance(含 c[35]) | D1+D3 PASS、indoor_tight、e-stop | e-stop / `pawai demo stop` | ladder C1 升級候選（N3） |
| M2 | （若 M1 全直）safe-stop：人進正前 0.8-1.0m，看 danger 停 0 撞 | M1 PASS | e-stop | ladder C4（N8） |
| M3 | （若 §8 P2 body-frame 模式做出）body-frame forward 0.3m，故意 AMCL yaw 設歪 ±20°，看是否仍走直（驗 R4 修法） | body-frame 模式 merged + 單測過 | e-stop | 新能力（先 wired_only） |

**不做**：0.5m+ 連續、auto-resume、繞障、open_space 下短 goto（除非淨空大空間）。

---

## 8. Proposed Fixes — P0 / P1 / P2 / P3

> 每項標 **[tag]** + tests + HITL checklist + rollback。pure software 項可 AFK；motion 項需 Roy。

### P0 — Safety Immediate（先擋住「靜態綠就敢發 motion」）

**P0-1　goto 前置「yaw / scan-overlay sanity」+ 結構化拒絕** **[pure software]**
- 在 `nav_action_server` goto 路徑加**朝向 sanity 前置檢查**（不改 covariance 門檻值——Lane 6 §5 禁）：
  - 讀 `c[35]`（σ²yaw）：超閾值 → reject `nav_not_ready:yaw_uncertain=<v>`。
  - （可選）scan-overlay residual：把 `/scan_rplidar` 用 `map→base_link` 投影到 static map，算 match 殘差；超閾值 → reject `scan_overlay_mismatch:<v>`。
- `nav_ready` 拆 **position_ready / yaw_ready / scan_overlay_ready** 三旗（Studio tri-state 沿用 Lane 2 管道）。
- Tests：`nav_capability/test/test_nav_action_server_rejection_reasons.py` 加 yaw_uncertain / scan_overlay_mismatch 路徑（紅綠）；`nav_ready_check` 加 yaw 維度單測。
- HITL：D2（驗 yaw 大錯時新閘會擋）。
- Rollback：純 additive reject（不改既有 accept 邏輯）；新閘預設 enable 但閾值寬到不誤擋，旗標可關回舊行為。

**P0-2　enforce goto 限速 / 限距（治超衝 R2）** **[pure software]**
- goto 前**動態 set DWB `max_vel_x`**（依 `goal.max_speed`，預設 ≤0.25 indoor）+ 短 goal 用 `nav2_params` indoor profile；或在 `_execute_nav_goal_with_pause_aware` 加「actual 位移超 `distance × (1+margin)` 即 cancel」watchdog。
- Tests：單測 watchdog 觸發（mock 位移 > 限）；DWB param set argv 單測。
- HITL：M1 量 actual vs goal（超衝是否收斂）。
- Rollback：watchdog/限速旗標預設可關回現行為；不動 controller 預設值本體。

**P0-3　HITL 路徑強制經 SafetyLayer 或本地 depth/obstacle 前置** **[pure software]**
- 現況 `send_relative_goal.py` direct action **bypass Brain depth_clear/obstacle gate**（§2.6）。在 goto 路徑加「發前確認 `/state/reactive_stop/status` zone≠danger 且 `/capability/depth_clear`（若 D435 在）= true」的本地前置（fail-closed）。
- Tests：單測「zone=danger 時 goto 被 reject」。
- Rollback：旗標預設 on，可關。

### P1 — Demo Fallback（6/18 不靠 AMCL goto）

**P1-1　S1 主線改「遙控輔助 + Studio 證據」或「純影片」** **[pure software / 文件]**
- 詳 §9。把 AMCL/Nav2 `goto_relative` 移出 demo 主線。
- Tests：N/A（文件 + 台詞）。Rollback：影片保底（[demo snapshot tag](../mission/2026-06-18-demo-north-star.md)）。

**P1-2　initialpose yaw 校正 SOP 成文 + 一鍵診斷** **[pure software + Jetson 驗]**
- 寫 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-initialpose-yaw-calibration-sop.md`：①使用者站機鼻 0.5m → `lidar_front_sector.py` 確認 ±180° bin ②`tf2_echo` 確認外參 ③設 initialpose 後等 covariance(含 c[35]) 收斂 ④goto 前 sanity。
- Tests：SOP dry-run（no motion，D1/D3）。Rollback：SOP 是流程，無 code 風險。

### P2 — Nav Architecture（治本 R4，pre-6/18 只到「可審/可單測」，HITL 需 Roy）

**P2-1　body-frame direct-forward 模式（繞過 AMCL/Nav2）** **[pure software → Go2 motion HITL]**
- 新 action `/nav/forward_body`（或 `goto_relative` 加 `frame:=body`）：用 driver `Move`（api_id=1008）發**受限速（≤0.25）、固定短距（≤0.5m）**，**reactive_stop 全程監控 + odom 積分量距 + 超距即 StopMove**。不經 AMCL/planner。
- 解 R1/R4 的源：朝向 = Go2 body forward（步態 yaw drift 仍在，靠限距 + reactive_stop 兜底）。
- Tests：純函式（odom 積分距離、限速 clamp、超距 cancel）單測；mock driver Move/StopMove 路由單測。
- HITL：M3（AMCL 故意設歪仍走直）。
- Rollback：新 action 獨立，不動 goto_relative；預設不接進 demo（wired_only）。

**P2-2　reactive_stop path-corridor / footprint-aware 升級（治 R3）** **[pure software → HITL]**
- `compute_front_min_distance` 之外加「沿速度方向矩形走廊（含機身寬 0.31m + margin）取最小距離」選項；或 danger 判定納入機身投影。
- Tests：`test_reactive_stop_node.py` / `lidar_geometry` 加 corridor 幾何單測（off-axis 障礙進 danger 時機正確）。
- HITL：D4（台架）→ M2（safe-stop）。
- Rollback：corridor 為 opt-in param，預設 = 現行 cone。

**P2-3　covariance 收斂 SOP + 黃帶決策表（含 yaw）** **[pure software + Jetson 量測]**
- `scripts/nav_covariance_probe.py`（D5）→ 黃帶決策表（該等/該推/該重設），**含 yaw 維度**。
- Tests：probe 輸出 CSV 可重算；`bash -n`/flake8。Rollback：純量測工具。

### P3 — Research（post-6/18，只交 spec，不寫 code）

**P3-1　D435 + LiDAR fusion** **[research only]**
- 必先解 §2.3 B1（max_speed enforce = P0-2）+ B2（AMCL plateau = P2-3）兩根因。
- 最小可行：`depthimage_to_laserscan → /scan_d435 →` local_costmap 第二 obstacle source（一個 YAML + 一個 launch node，CPU 安全）。**全部 post-6/18**。
- spec 已在 [`research/2026-06-13-spec-d435-lidar-fusion.md`](research/2026-06-13-spec-d435-lidar-fusion.md)。**禁 claim 已融合**（§0 #4）。

**P3-2　patrol v1 / approach person** **[research only]** — spec 已在 [`research/2026-06-13-spec-patrol-v1.md`](research/2026-06-13-spec-patrol-v1.md)、[`research/2026-06-13-spec-approach-person.md`](research/2026-06-13-spec-approach-person.md)。

---

## 9. Revised S1 Demo Recommendation

**現況判定**：AMCL/Nav2 `goto_relative` 在目前 initialpose 朝向精度 + 超衝 + 側向幾何下 **NOT_DEMO_READY**，**不可當 6/18 nav 主線**（除非 §8 P0-1/P0-2 + initialpose SOP + M1 n=3 無撞全過並回填 ladder）。

**建議 S1 改線（依 [claim wording §5 三層 fallback](2026-06-13-nav-618-claim-wording.md)）**：

1. **預設主線 = ② 遙控輔助 + Studio 證據**：遙控 / Studio 輔助移動，Studio map + LiDAR 點雲 + reactive_stop 狀態作為「邊緣端即時感知環境」證據。可講 S2（safe-stop，配標準說法）、S4（窄場安全錐）、S6（拒絕有理由）。
2. **若 B-9 場測 M1 n=3 全直無撞**（用 indoor_tight + initialpose SOP）→ 才升 ① **live 短距 0.3m**（標單點、n=3 才加「可靠」）。
3. **保底 = ③ 純影片**（S1 已錄影片，[snapshot tag](../mission/2026-06-18-demo-north-star.md)）。
4. **（stretch）body-frame forward（§8 P2-1）** 若做出 + HITL 過，比 AMCL goto **更適合做 live 短距**（不依賴 AMCL 朝向）——但 6/18 前能否到位看時間，預設不承諾。

**不再把 AMCL/Nav2 goto_relative 當 demo 主線，除非 root cause 證明修好。**

---

## 10. Claim Wording Update（回填 [claim wording](2026-06-13-nav-618-claim-wording.md)）

- **S1（短距自主移動）降級**：current label 維持 `NOT_DEMO_READY`（不是 `HARDWARE_PROVEN_LOW_SAMPLE`）——6/13 第一發 goto 撞牆推翻先前單點證據的可展示性。**6/18 不講「短距自主移動」**，除非 M1 n=3 過並回填。
- **新增 forbidden claim**：
  - 「靜態檢查通過代表可以安全移動」——**錯**（§2.2 閘 yaw-blind）。對外只能講「靜態檢查確認鏈路與定位 position，**不保證朝向**」。
  - 「goto 0.3m 就走 0.3m」——**錯**（§2.3 超衝 0.5m→1.04m）。
- **可保留**：S2 safe-stop（正前停障，配 §3 標準說法）、S4 窄場安全錐、S5 orphan 自癒、S6 拒絕有理由（P0-1 後更強：含 yaw_uncertain reason）。
- **新誠實敘事**（可當 nav 段亮點）：「我們用能力階梯誠實管理——一次撞牆事件讓我們發現安全閘只驗位置不驗朝向、且短移會超衝；我們把它降級、補上朝向 sanity 與限速，不把單次成功講成可靠。」（呼應 [master §1 誠實的完成定義](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)）

---

## 11. Rollback / Stop Conditions

**Stop（立即停止、不得繼續）**
1. 任何時刻 Go2 出現非命令方向移動 / 該停沒停 / 機鼻<0.3m 仍動 → **e-stop（`emergency_stop.py engage`）+ 該項 FAIL**（Lane 6 §8）。
2. e-stop 未就位 → **不開始任何 motion 項**。
3. D1（AMCL yaw 真值比對）未做或 θ_error 未知 → **不發任何 goto**。
4. profile=open_space（±30°）→ **不在窄客廳發短 goto**（必先切 indoor_tight）。

**Rollback（軟體）**
- P0-1/P0-2/P0-3 全是 **additive / 旗標預設可關回現行為**；各自獨立 PR revert。covariance 門檻值**零變動**（Lane 6 §5）。
- P2-1 body-frame 為**新獨立 action**，不動 `goto_relative`；預設不接 demo。
- P2-2 corridor 為 **opt-in param**，預設 = 現行 cone。
- HITL 項全部現場可中止（e-stop / `pawai demo stop` 路由 nav lane cleanup）；任一 FAIL 不連坐——ladder 照實標、claim wording 對應降級。

**收工即時動作（撞擊事件後，最先）**
- 確認 Go2 已停穩 → `pawai demo stop`（清 nav stack/driver；handoff §2）。
- `pawai evidence pull` + 抓 nav log（D0，只讀）。

---

## 附錄 A — 能力分級（proven / needs HITL / research only）

| 能力 | 分級 | 依據 |
|---|---|---|
| safe-stop（正前停障） | **proven (with limit)** | trackB §1 / 6/9 §1.5（hardware_proven_with_limit）；本事件不影響此結論（reactive_stop 正前 danger 仍有效） |
| 靜態鏈路 / 定位 position 收斂 | **proven** | 8/8 static PASS；但**僅 position，不含朝向** |
| AMCL initialpose 重定位（跳點） | **proven (low sample)** | ladder C7；收斂 SOP 仍缺 |
| 短距 goto 0.3/0.5m | **needs HITL（且當前 NOT_DEMO_READY）** | 6/13 撞牆；需 P0 修 + initialpose SOP + M1 n=3 |
| yaw / scan-overlay sanity 閘（P0-1） | **needs HITL（軟體可先做）** | 本檔提案，未實作 |
| goto 限速/限距（P0-2，治超衝） | **needs HITL（軟體可先做）** | 本檔提案 |
| body-frame direct forward（P2-1） | **needs HITL（軟體可先做，HITL 後才可展示）** | 本檔提案，未實作 |
| reactive_stop path-corridor（P2-2） | **needs HITL** | 本檔提案 |
| D435 + LiDAR fusion | **research only** | spec 在；2 根因未解；D435 硬體故障中 |
| patrol v1 / approach person / 動態繞障 / 自由巡邏 | **research only / DO_NOT_CLAIM** | ladder C9-C12 |

## 附錄 B — 調查方法與信心

- 6 軸 code 調查 + 12 對抗投票（H1-H6 × code-mechanism/skeptic）。R1/R5 雙 lens STRONGLY_SUPPORTED；R2 doc 實測 CONFIRMED；R3 mechanism 確認、量值 PLAUSIBLE_UNPROVEN（待 D0 log）；R6/R7 skeptic REFUTED-as-primary。
- **最大不確定**：撞的「具體是哪個障礙、超衝多少」需當天 `[PR1a]` log + `reactive_stop/status`（D0）才能定量；在此之前 R3 的「量值」與 R2 的「本次超衝幅度」維持**待證**，不 overclaim。
- 核心 file:line 由 orchestrator 親自讀檔複查（非僅 subagent 自評，遵 handoff §7「subagent 自評不可信」）。
