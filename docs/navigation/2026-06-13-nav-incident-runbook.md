# Navigation Incident Runbook（可執行版）— 2026-06-13

> **日期**：2026-06-13　**狀態**：RUNBOOK（操作員 + 工程師可照做；**全程零 motion / goto / cmd_vel**）
> **配套**：根因分析在 [`2026-06-13-nav-motion-incident-root-cause-plan.md`](2026-06-13-nav-motion-incident-root-cause-plan.md)；能力階梯 [`2026-06-13-nav-capability-ladder.md`](2026-06-13-nav-capability-ladder.md)；對外措辭 [`2026-06-13-nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md)。
> **這份新增了什麼（相對 root-cause-plan）**：① 一個 **code 級新確認的共同主因**——`go2.urdf` 把 `map→odom`/`odom→base_link` 當 **fixed joint** 發到 `/tf_static`，與 AMCL/driver 的動態 TF **雙重 authority 衝突**（§2/§4，外部 REP-105 + tf2 文件背書）② **TF authority matrix**（§4）③ **LiDAR 前向軸校準 SOP**（§5）④ **AMCL initialpose / scan overlay SOP**（§6）⑤ **short-forward 三方案比較**（§7，含已部署的 Nav2 `DriveOnHeading`）⑥ **可貼上執行的 no-motion 診斷指令集**（§9）⑦ **6/18 S1 main/fallback/forbidden**（§10）。
> **執行紀律**：§9 全部是**唯讀**指令（echo / hz / tf2_echo / view_frames / param get / 既有診斷腳本）。任何會讓 Go2 動的測試一律在 §11 標 **needs Roy + e-stop**，本 runbook **不發、不代跑**。

---

## 1. Executive Summary

2026-06-13 HITL 第一發 `goto_relative 0.3m` 走歪撞牆（profile=open_space ±30°）。根因分析（root-cause-plan）已定為**多因**：R1 AMCL 朝向注入 forward／R2 0.5m→1.04m 超衝／R3 reactive_stop 側向沉默／R5 安全閘 yaw-blind。**本 runbook 追加一個 code 級新確認、且排序在 R1 之前必須先排除的共同主因**：

> **T0（TF authority 衝突）**：單機 nav 啟動載入的 `go2.urdf` 把 `map→odom`（`map_joint`）與 `odom→base_link`（`odom_joint`）宣告成 **`type="fixed"`、identity**，`robot_state_publisher` 會把所有 fixed joint 發到 **`/tf_static`**（[robot_state_publisher README](https://github.com/ros/robot_state_publisher/blob/ros2/README.md)）。這與 AMCL 的動態 `map→odom`（`tf_broadcast:true`）、driver 的動態 `odom→base_link`（`GO2_PUBLISH_ODOM_TF=1`）形成**同一條 edge 兩個 publisher**。依 tf2 規格，static transform *"good across all time, cannot be changed after the first call"*（[tf2 BufferCore](https://docs.ros2.org/foxy/api/tf2/classtf2_1_1BufferCore.html)），靜態 identity 可能**永久遮蔽**動態定位 → 機器人朝向/位置被錯誤鎖定，正是「走歪」的可能上游源。REP-105 明文：*"each frame can only have one parent"*（[REP-105](https://www.ros.org/reps/rep-0105.html)）。

**決策**：nav motion 維持 **`NOT_DEMO_READY`**。修法順序嚴格照研究建議：**先 T0 frame authority → 再 LiDAR 前向軸 → 再 AMCL yaw → 再決定 short-forward 架構 → 最後才談 D435 fusion**。6/18 S1 不押 AMCL goto（§10）。

---

## 2. Root-Cause Hypothesis Table（含外部依據）

| # | 假設 | 角色 | 證據（file:line / 外部 URL） | 狀態 |
|---|---|---|---|---|
| **T0** | `go2.urdf` 的 `map→odom`/`odom→base_link` fixed joint 被 `robot_state_publisher` 發到 `/tf_static`，與 AMCL/driver 動態 TF 衝突 → 靜態 identity 遮蔽動態定位 | **CO-PRIMARY（code 確認；runtime 效果待 §9-D1 echo `/tf_static` 證實）** | `go2.urdf:48-58`(odom_joint fixed) / `:70-80`(map_joint fixed)；`robot.launch.py:67`(single→go2.urdf)、`:219-237`(載入 RSP)；`ros2_publisher.py:29`(driver odom→base_link)；`nav2_params.yaml:38`(amcl tf_broadcast:true)。外部：[REP-105](https://www.ros.org/reps/rep-0105.html)、[tf2 BufferCore static](https://docs.ros2.org/foxy/api/tf2/classtf2_1_1BufferCore.html)、[RSP README](https://github.com/ros/robot_state_publisher/blob/ros2/README.md) | needs HITL（no-motion 即可證） |
| R1 | goto「前方」= AMCL map-frame yaw，無 body-frame 退路；initialpose 朝向偏 θ → 整條向量旋 θ | PRIMARY | `relative_goal_math.py:27-30`、`nav_action_server_node.py:259-266,462` | needs HITL |
| R2 | goto 不 enforce max_speed + Go2 sport 慣性 → **0.5m 實走 1.04m** | CRITICAL 放大器 | `nav_action_server_node.py:406-414`、`nav2_params.yaml:159`、`spec-d435-lidar-fusion.md:14-18` | confirmed(doc) |
| R3 | reactive_stop +25°/1.65m 落 slow band、progressive 沉默、body-forward 錐不對齊斜路、無 footprint/corridor | CONTRIBUTING | `lidar_geometry.py:54-63,109-112`、`reactive_stop_node.py:276`、`start_nav_capability_demo_tmux.sh:37-40` | mechanism 確認/量值待 log |
| R5 | 安全閘 yaw-blind：只查 c[0]+c[7]，從不查 c[35]；8/8 靜態全不驗朝向 | ENABLING | `nav_action_server_node.py:252-257`、`nav_ready_check.py:30-54`、`smoke_test_nav_static.sh:69-121` | confirmed |
| R6 | LiDAR mount yaw / 外參物理偏 | DOWNGRADED（非 primary，§5 SOP 可證） | `start_nav_capability_demo_tmux.sh:69-72`(手設 yaw=π)、`amcl-180-degree-diagnosis.md` | needs HITL |
| R7 | DWB 短 goal 行為（rotate-in-place 不可）造成微歪 | MINOR | `nav2_params.yaml:154-195`、`trackB §3`(micro-skew gait60/DWB30/TF10) | weak |

**T0 與 R1 的關係**：兩者都會表現成「AMCL 朝向不對 → 走歪」。**必須先用 §9-D1 排除 T0**——若 `/tf_static` 真的有 `map→odom`/`odom→base_link`，再準的 initialpose 也救不了（靜態 identity 遮蔽）。

---

## 3. External References（已驗證 URL）

> 全部由 web 驗證 agent 實際 fetch 確認可解析（`ros.org`/`docs.ros.org` 偶有 Anubis bot 牆，已附 GitHub raw 來源備援）。

### TF / 座標系 authority
- **Nav2 Setting Up Transformations** — https://docs.nav2.org/setup_guides/transformation/setup_transforms.html — map→odom(localization) / odom→base_link(odometry) / base_link→sensor(RSP 或 static) 三段需求。
- **REP-105 Coordinate Frames** — https://www.ros.org/reps/rep-0105.html （raw: https://github.com/ros-infrastructure/rep/blob/master/rep-0105.rst）— *"each frame can only have one parent"*；map 是 odom 的 parent、odom 是 base_link 的 parent；map「可離散跳變、不長期漂移」、odom「連續但會漂移」。
- **tf2 BufferCore::setTransform** — https://docs.ros2.org/foxy/api/tf2/classtf2_1_1BufferCore.html — static transform *"good across all time. (This cannot be changed after the first call.)"* → 同 frame 永久 static-or-dynamic，靜態會遮蔽動態。
- **robot_state_publisher（ros2）** — https://github.com/ros/robot_state_publisher/blob/ros2/README.md — *fixed joints → transient_local `/tf_static`（once on startup）*；movable joints → `/tf`。
- **TF_REPEATED_DATA warning** — https://github.com/ros/geometry2/issues/467 — 兩 publisher 同 frame/時戳 → tf2 忽略重複資料並警告。

### Nav2 short-forward / safety primitives
- **DriveOnHeading** — https://docs.nav2.org/configuration/packages/bt-plugins/actions/DriveOnHeading.html — 沿**當前 heading** 位移固定距離；odom/body-relative、**不需 map/AMCL**；ports：`dist_to_travel`(0.15)、`speed`(0.025)、`time_allowance`(10)、`disable_collision_checks`(false)。
- **Behavior Server** — https://docs.nav2.org/configuration/packages/configuring-behavior-server.html — `local_frame=odom`、`simulate_ahead_time=2.0s` 對 **local costmap** 做 collision check（DriveOnHeading/BackUp 內建）。
- **BackUp** — https://docs.nav2.org/configuration/packages/bt-plugins/actions/BackUp.html ｜ **Spin** — https://docs.nav2.org/configuration/packages/bt-plugins/actions/Spin.html
- **Collision Monitor** — https://docs.nav2.org/configuration/packages/configuring-collision-monitor.html ｜ node 細節（Stop/Slowdown/Limit/Approach polygon、VelocityPolygon）— https://docs.nav2.org/configuration/packages/collision_monitor/configuring-collision-monitor-node.html — *"bypassing the costmap and trajectory planners, to monitor for and prevent potential collisions at the emergency-stop level."*
- **Velocity Smoother** — https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html

### Costmap layers / sensor sources
- **Obstacle Layer** — https://docs.nav2.org/configuration/packages/costmap-plugins/obstacle.html — `data_type: LaserScan|PointCloud2`、`observation_sources` 可列多源、`obstacle_max_range`/`raytrace_max_range`。
- **Voxel Layer** — https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html — 3D raycast；`publish_voxel_map` debug 很吃 CPU。
- **Costmap 2D 設定指南** — https://docs.nav2.org/configuration/packages/configuring-costmaps.html — 加第二 source：`observation_sources: scan pointcloud` + 各自 sub-block。
- **STVL（深度相機推薦 3D 層）** — https://docs.nav2.org/tutorials/docs/navigation2_with_stvl.html ｜ repo https://github.com/SteveMacenski/spatio_temporal_voxel_layer/blob/ros2/README.md

### D435 + depth→laserscan
- **RealSense ROS2 wrapper** — https://github.com/IntelRealSense/realsense-ros/blob/ros2-development/README.md — `align_depth.enable`→`/camera/camera/aligned_depth_to_color/image_raw`；`pointcloud.enable`→`/camera/camera/depth/color/points`；`publish_tf`。
- **depthimage_to_laserscan（ros2）** — https://github.com/ros-perception/depthimage_to_laserscan/tree/ros2 — depth image → 單列 LaserScan；`scan_height`、`range_min/max`、`output_frame`。
- **pointcloud_to_laserscan（humble）** — https://github.com/ros-perception/pointcloud_to_laserscan/tree/humble — PointCloud2 → LaserScan；`min_height/max_height`、`angle_min/max`、`target_frame`。

### 視覺化（fixed frame gotcha）
- **Foxglove 3D panel** — https://docs.foxglove.dev/docs/visualization/panels/3d — Display/Fixed frame；*"must exist a transform path from the object's frame to the display frame"*（選錯 frame → 正確的 scan 看起來歪）。
- **Foxglove Bridge** — https://docs.foxglove.dev/docs/visualization/ros-foxglove-bridge ｜ repo（port 8765）https://github.com/foxglove/ros-foxglove-bridge
- **RViz2 User Guide（Humble）** — https://docs.ros.org/en/humble/Tutorials/Intermediate/RViz/RViz-User-Guide/RViz-User-Guide.html （raw: https://github.com/ros2/ros2_documentation/blob/humble/source/Tutorials/Intermediate/RViz/RViz-User-Guide/RViz-User-Guide.rst）— *fixed frame 設錯 → 物件全部出現在機器人前方；改 fixed frame 會清空而非重投影*。

---

## 4. TF Authority Matrix

> 規則來源 REP-105：每個 frame **只能有一個 parent / 一個 authority**。下表「應有 authority」對照「實際 publisher」，標出衝突。

| Edge | 應有 authority（REP-105） | 實際 publisher（PawAI nav 單機） | 衝突？ | file:line | no-motion 診斷 |
|---|---|---|---|---|---|
| `map→odom` | localization（AMCL）動態 | **① AMCL 動態**（`tf_broadcast:true`）**＋② `go2.urdf` map_joint fixed identity → /tf_static** | 🔴 **雙 authority** | amcl: `nav2_params.yaml:38`；urdf: `go2.urdf:70-80`；RSP 載入: `robot.launch.py:67,219-237` | `ros2 topic echo /tf_static`（找 map→odom）、`view_frames` 看 broadcaster |
| `odom→base_link` | odometry（driver）動態 | **① driver 動態**（`GO2_PUBLISH_ODOM_TF=1`）**＋② `go2.urdf` odom_joint fixed identity → /tf_static** | 🔴 **雙 authority** | driver: `ros2_publisher.py:29,66-91`；urdf: `go2.urdf:48-58` | `ros2 topic echo /tf_static`（找 odom→base_link）、grep `TF_REPEATED_DATA` |
| `base_link→laser` | static（mount 外參） | static_transform_publisher（demo 腳本）`x=0.175 z=0.18 yaw=π` | 🟡 單一但**手設未校正** | `start_nav_capability_demo_tmux.sh:69-72` | `tf2_echo base_link laser`、§5 SOP |
| `base_link→base_footprint` | RSP（URDF） | `go2.urdf` base_footprint_joint fixed | 🟢 單一 | `go2.urdf:60-64` | — |
| `base_link→front_camera/D435` | RSP（URDF）或 static | URDF front_camera_joint；detour 另用 hack static `x=0.30 z=0.20 yaw=0` | 🟡 detour hack 未校正 | `go2.urdf:136-141`；`start_nav_capability_demo_tmux_detour.sh:64-67` | `tf2_echo base_link camera_depth_optical_frame` |

**結論**：`map→odom` 與 `odom→base_link` **各有兩個 publisher**（動態 + URDF 靜態 identity）。這是 REP-105/tf2 明文禁止的「一 frame 兩 parent/authority」。**T0 修法（P0）= 從單機載入的 URDF 移除 `map`/`odom` link 與 `map_joint`/`odom_joint`**（保留 `base_footprint_joint`），讓每條 edge 只剩唯一動態 authority；或把單機預設 URDF 換成不含這兩個 joint 的 `go2_on_steroids.urdf`（已確認該檔無 map/odom joint）。修法是單檔編輯、可一鍵 revert。

---

## 5. LiDAR Front-Axis 校準 SOP（no-motion 為主，最後一步需 Roy）

> 目標：讓「實體 Go2 前方」＝「laser frame 經 `front_offset_rad` 校正後的前方」＝「Foxglove/RViz 以 base_link 為準的 scan 朝向」三者一致。現況 `base_link→laser yaw=π` + reactive_stop `front_offset_rad=π` 是手設（`start_nav_capability_demo_tmux.sh:40,69-72`），需升級成可重複 SOP。

**S5-1（no-motion）讀外參**
```bash
ros2 run tf2_ros tf2_echo base_link laser     # 期望 translation≈(0.175,0,0.18)、rotation yaw≈π(±0.01)
ros2 param get /reactive_stop_node front_offset_rad   # 期望 3.14159（與 TF yaw 一致；不一致＝雙重補正只改一邊，必錯）
ros2 param get /reactive_stop_node front_arc_deg      # demo 用哪個 profile（30=open_space / 18=indoor_tight）
```

**S5-2（no-motion）物理錨定（5/1 黃金標準，無誤判）**
- 操作員**站在 Go2 物理機鼻正前方 0.5m**（用人站位法，不用放物體——`amcl-180-degree-diagnosis.md` 教訓：放物體易把鼻尖方向認錯）。
```bash
python3 scripts/lidar_front_sector.py    # 讀 ±15/20/30° 扇區最近障礙的角度(rad)
```
- **判定**：人應落在 **±180°（≈±π）bin**（因 mount yaw=π，laser 0°=Go2 後方）。若落在 0° 或其他角度 → mount 物理偏 / `front_offset_rad` 不對 → **停，先修外參再做任何 motion**。
- 交叉：`scripts/scan_health_check.py` 跑一輪（360° 5°-bin range/jitter，檢測 phantom arc）。

**S5-3（no-motion）Foxglove 一致性**
- Foxglove 3D panel **Display/Fixed frame 設 `base_link`**（[Foxglove 3D panel](https://docs.foxglove.dev/docs/visualization/panels/3d)：frame 選錯會讓正確 scan 看起來歪）。
- 確認正前方淨空在畫面上對齊機鼻方向；牆面 scan 線與實體牆平行。

**S5-4（needs Roy，極小角度，無位移）**——只有 S5-1~S5-3 全過才做
- 原地小角度自轉（≤30°，operator 手動、e-stop 待命），觀察 scan 朝向是否同步、無跳變。**這步屬 motion，不在本 runbook 執行範圍，列入 [root-cause-plan §7](2026-06-13-nav-motion-incident-root-cause-plan.md) M-class 由 Roy 決定。**

**Rollback**：所有 SOP 只讀 + 量測；若要改 `base_link→laser` yaw，先放實驗 launch arg，保留現行 `yaw=π` 一鍵退回。

---

## 6. AMCL Initialpose / Scan-Overlay SOP（no-motion 為主）

> 前置：**先完成 §9-D1 排除 T0**（`/tf_static` 不得有 `map→odom`/`odom→base_link`）。T0 未排除前，本 SOP 的 AMCL 讀數不可信。

**S6-1（no-motion）設 initialpose**
- Studio 兩段點擊（`nav-map-canvas.tsx:239-245`：click1 位置、click2/拖曳定 yaw）或 Foxglove `/initialpose`。⚠️ gateway **無 yaw sanity check**（`studio_gateway.py:487-507`）——拖曳方向要對準**實體機鼻朝向**，不是憑感覺。
- AMCL 參數現況：`set_initial_pose:false`（`nav2_params.yaml:50`，靠手設）、`update_min_d/a=0.10`（`:41-42`，靜止不自我修正 yaw）。

**S6-2（no-motion）讀完整 covariance（含 yaw）**
```bash
ros2 topic echo /amcl_pose --once    # 讀 pose.pose.position + orientation；covariance[0]=σ²x、[7]=σ²y、[35]=σ²yaw
```
- 現有閘只看 `c[0]+c[7]`（`nav_action_server_node.py:252-257`，**從不看 c[35]**）。**SOP 要求人工讀 c[35]**：σ²yaw 偏大即使 position 綠也不准發 goal（這正是 R5/事件的洞）。

**S6-3（no-motion）scan overlay 真對齊（非「看起來差不多」）**
- Foxglove/RViz **Fixed frame 設 `map`**（[RViz guide](https://docs.ros.org/en/humble/Tutorials/Intermediate/RViz/RViz-User-Guide/RViz-User-Guide.html)：fixed frame 設錯會讓 scan 全部跑到機器人前方）。
- 疊 `/scan_rplidar` 到 static map：判定標準是**牆角、家具邊界同時吻合**，不是輪廓大致重合。某一側系統性偏移 = yaw 錯。
```bash
ros2 run tf2_ros tf2_echo map base_link    # AMCL 解算的 map-frame pose；與現場地標比對
```

**S6-4（no-motion）yaw 真值比對**
- 結合 §5 物理錨定：用 `lidar_front_sector.py` 確認的實體朝向 vs `tf2_echo map base_link` 的 yaw → 算 `θ_error`。**`|θ_error|>5-10°` → 重設 initialpose，不准發 goal。**

**S6-5（建議的 nav_ready 三拆）**（軟體 follow-up，root-cause-plan P0-1）：`position_ready`（c[0]+c[7]）/ `yaw_ready`（c[35] + θ_error）/ `scan_overlay_ready`（map/scan residual）。現況只有 position_ready，這是「靜態 pass ≠ motion safe」的根。

**Rollback**：純 SOP / 讀數；不改 AMCL 參數（改門檻是行為變更，需另案 + Roy）。

---

## 7. Short-Forward 三方案比較（0.3–0.5m 室內窄場）

| 維度 | A. `goto_relative`（現行） | B. Nav2 `DriveOnHeading` | C. body-frame `cmd_vel` + safety monitor |
|---|---|---|---|
| 前進方向定義 | **AMCL map-frame yaw**（`relative_goal_math.py:27-30`） | **當前 heading（odom/body）**，不需 AMCL/map（[DriveOnHeading docs](https://docs.nav2.org/configuration/packages/bt-plugins/actions/DriveOnHeading.html)） | **Go2 body forward**（直接 Move 1008，`robot_control_service.py:151`） |
| 依賴 AMCL 朝向？ | **是**（R1 命門） | **否**（用 odom） | **否** |
| 受 T0（URDF TF 衝突）影響？ | 是（map→odom 被遮蔽即錯） | 部分（odom→base_link 仍受 T0 影響，但不靠 map→odom） | 部分（同上，odom→base_link） |
| 障礙檢查 | DWB + local costmap（odom frame，未被 AMCL yaw 污染） | **內建 collision check**（`simulate_ahead_time=2.0s` 對 local costmap，[Behavior Server](https://docs.nav2.org/configuration/packages/configuring-behavior-server.html)） | **無**——必須外掛 reactive_stop / Collision Monitor |
| 速度/超衝 | max_speed 不 enforce → 0.5m 走 1.04m（R2） | `speed` 可設，但 default 0.025 < Go2 MIN_X 0.5 → **必設 ≥0.45**；仍 open-loop on odom，有超衝風險 | 可由 monitor 限速限距 + StopMove，**最可控** |
| 既有部署？ | ✅ `/nav/goto_relative` 在跑 | ✅ **已部署**（`nav2_params.yaml:352-353` behavior_server plugin + BT node `:74`），action `/drive_on_heading` 可直接用 | ❌ 需新寫（root-cause-plan P2-1） |
| Stop/急停 | reactive_stop(mux 200) + emergency_stop(255) | 同左 + 內建 collision abort | 同左；可加 [Collision Monitor](https://docs.nav2.org/configuration/packages/configuring-collision-monitor.html) Approach polygon |
| 適合 6/18？ | ❌ NOT_DEMO_READY | **⚠️ 最有機會的 Nav2-native 選項**（繞過 R1），需設速 ≥0.45 + indoor_tight reactive + HITL n=3 | ⚠️ 治本但要新開發 + HITL，6/18 前能否到位看時間 |

**建議**：短期若要 live 短距，**B（DriveOnHeading）優於 A**——它繞過 R1（不靠 AMCL 朝向）且內建 collision check；但 **B 仍受 T0 影響**（odom→base_link），且 default speed 太低必須調，仍 open-loop 有超衝，**所有前提仍是先排除 T0 + e-stop + indoor_tight + n=3 重驗**。**C（body-frame + Collision Monitor）是治本**（最小控制語意 + 限距 + 獨立 safety），列 P2，post-T0/HITL。**A 不再當主線。**

---

## 8. D435 最小可行融合（現況 + 兩軌；demo 不靠它）

**現況（已確認）**：D435 只做 Brain 層 `depth_clear` fail-closed gate（`safety_layer.py:133-140`、`depth_safety_node.py`），**未進 Nav2 costmap**（`nav2_params.yaml:223` 只有 `/scan_rplidar`）。HITL 用 direct action 還會**繞過** depth_clear gate（`nav_action_server` 不查 depth_clear）。D435 目前有 **Right MIPI / Hardware Error**（handoff）→ 短期不可硬依賴。

**最小可行（已在 disk 的 detour，但有 4 bug、非 demo-ready）**：
- `start_nav_capability_demo_tmux_detour.sh:70-73` 跑 `depthimage_to_laserscan_node` → `/scan_d435`（depth=aligned_depth、`scan_height:=10 range:=0.30-3.0`）；`nav2_params_detour.yaml:220-234` 把 `d435_scan` 加成 local_costmap 第二 `observation_sources`。
- 參考 [depthimage_to_laserscan](https://github.com/ros-perception/depthimage_to_laserscan/tree/ros2) + [Costmap 設定（多 source）](https://docs.nav2.org/configuration/packages/configuring-costmaps.html)。
- ⚠️ **致命前置**：detour 的 `base_link→camera_depth_optical_frame` 是 hardcoded 未校正（`:64-67`），且 CLAUDE.md 列 4 bug（safety_only 舊值、danger 0.40 太低、detour params 未同步、D435 TF 未精校）。**外參未校正前，深度投影到 costmap 會落在錯位置**——與 §5 LiDAR 校準同性質。
- **6/18 前：research only**（先解 root-cause-plan §2.3 的 B1 超衝 + B2 AMCL plateau，再談 fusion）。

**正統長期（post-demo research）**：`PointCloud2` → [Voxel Layer](https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html) 或 [STVL](https://docs.nav2.org/tutorials/docs/navigation2_with_stvl.html)（深度相機推薦）；Orin Nano 8GB CPU/RAM 風險需 bench。spec 在 [`research/2026-06-13-spec-d435-lidar-fusion.md`](research/2026-06-13-spec-d435-lidar-fusion.md)。**禁 claim 已融合。**

---

## 9. No-Motion Diagnostic Commands（可直接貼上執行，全唯讀）

> 全部唯讀。在 Jetson nav stack 已起、Go2 **站立不動**下執行。**先做 D1（T0）**。

### D0 — 證據回收（dev 機，最先）
```bash
pawai evidence pull                                  # 拉 runtime/traces + nav_capability（只讀）
# 在拉回的 trace / nav log 找當天那發：
#   [PR1a] goto_relative ACCEPT/DONE/END → accept_pose / goal / actual_dist_from_accept / duration
#   /state/reactive_stop/status 時間線 → 撞前 zone 是否一直 slow/active=false
```

### D1 — 🔴 T0 TF authority 衝突（最高優先）
```bash
ros2 topic echo /tf_static --once                    # ❗ 若出現 frame_id=map child=odom 或 frame_id=odom child=base_link → T0 成立
ros2 run tf2_tools view_frames                       # 產 frames.pdf：看 map→odom / odom→base_link 的 broadcaster 是否>1
ros2 run tf2_ros tf2_echo map odom                   # 觀察是否在動（AMCL 修正）vs 卡 identity(0,0,0)
ros2 run tf2_ros tf2_echo odom base_link             # 觀察是否隨 Go2 odom 變化 vs 卡 identity
ros2 node info /go2_robot_state_publisher            # 確認 RSP 有 publish /tf_static
# 看 driver/amcl log 是否刷 TF_REPEATED_DATA（兩 publisher 症狀）：
ros2 run tf2_ros tf2_monitor                         # 列每條 edge 的 broadcaster 數量 + 頻率
```
**判讀**：`/tf_static` 含 map→odom 或 odom→base_link、或 `tf2_monitor` 顯示同 edge 多 broadcaster、或 `tf2_echo map odom` 卡 identity 不動 → **T0 確認，先修 §4 P0 再做任何後續**。

### D2 — AMCL yaw / covariance（含 c[35]）
```bash
ros2 topic echo /amcl_pose --once                    # 讀 orientation + covariance[0]/[7]/[35]
ros2 run tf2_ros tf2_echo map base_link              # AMCL 解算朝向 vs 現場真值
ros2 topic echo /capability/nav_ready --once         # 看 yaw 大錯時是否仍 true（證 R5 yaw-blind）
```

### D3 — LiDAR 前向軸（配 §5）
```bash
ros2 run tf2_ros tf2_echo base_link laser
ros2 param get /reactive_stop_node front_offset_rad  # 須 == TF yaw(π)
python3 scripts/lidar_front_sector.py                # 人站機鼻 → 應落 ±180° bin
python3 scripts/scan_health_check.py                 # phantom arc / 360° bin
```

### D4 — reactive_stop 側向幾何（無 Go2 motion，只移障礙物）
```bash
ros2 param get /reactive_stop_node front_arc_deg     # 30=open_space / 18=indoor_tight
ros2 topic echo /state/reactive_stop/status          # 移箱子到 +25°/1.65m → 看 zone（預期 slow、active=false）
ros2 topic hz /scan_rplidar                          # ~10-12 Hz
```

### D5 — 靜態鏈路 / smoke（重申「不等於 motion safe」）
```bash
bash scripts/smoke_test_nav_static.sh                # 8 項全靜態；過了≠朝向對（見 R5）
ros2 action list | grep -E "goto_relative|drive_on_heading"   # 確認 DriveOnHeading 可用
ros2 topic echo /capability/depth_clear --once       # D435 gate（注意 direct action 會 bypass）
```

**全部 D1-D5 完成且 T0 已排除 + θ_error<5-10° 前：不發任何 goto。**

---

## 10. 6/18 S1 Demo 建議

**Main path（預設）**：**② 遙控輔助 + Studio 證據**——遙控/Studio 輔助移動，Studio map + LiDAR 點雲 + reactive_stop 狀態作為「邊緣端即時感知環境」操作證據。可講 [claim wording](2026-06-13-nav-618-claim-wording.md) S2（safe-stop，配標準說法）、S4（窄場安全錐）、S6（拒絕有理由）。

**Fallback（升/降級）**：
- **升級到 ① live 短距**：僅當 **T0 已排除 + §5/§6 SOP 過 + DriveOnHeading(B) 或修好的 goto 在 indoor_tight + e-stop 下 n=3 無撞**（root-cause-plan §7 M1）。短距用 **DriveOnHeading（§7-B）優先**（繞過 AMCL 朝向），speed 設 ≥0.45。
- **保底 ③ 純影片**：S1 已錄（[demo snapshot tag](../mission/2026-06-18-demo-north-star.md)），旁白用保守版。

**Forbidden claims（本事件新增 + 延續 [claim wording §4](2026-06-13-nav-618-claim-wording.md)）**：
- ❌「靜態檢查通過 = 可安全移動」——閘 yaw-blind 且 TF authority 可能衝突（T0/R5）。對外只能說「靜態檢查確認鏈路與**位置**收斂，**不保證朝向**」。
- ❌「goto 0.3m 就走 0.3m」——0.5m 實走 1.04m（R2）。
- ❌ 自主導航 / 動態繞障 / D435 已融合進 costmap / auto-resume / 「聽懂就走到 Roy 身邊」（F1-F10 全延續）。
- ❌「短距自主移動可靠」——T0/R1 未修 + 未 n=3 重驗前一律不講。
- ✅ 誠實亮點：「一次撞牆事件讓我們發現 ① 安全閘只驗位置不驗朝向 ② URDF 把 map/odom 當靜態 TF 與定位打架 ③ 短移會超衝；我們用能力階梯誠實降級、逐項修，不把單次成功講成可靠。」

---

## 11. Safe-Motion Tests（**NOT in this runbook's executable scope** — needs Roy + e-stop）

> 本 runbook 只執行 §9 唯讀診斷。以下 motion 測試**僅供 Roy 在 e-stop 就位下決定**，逐條見 [root-cause-plan §7](2026-06-13-nav-motion-incident-root-cause-plan.md)：M1（initialpose SOP 後 goto/DriveOnHeading 0.3m × n=3）、M2（safe-stop）、M3（body-frame forward 對照）。
>
> **硬前置**：T0 排除（§9-D1）+ §5/§6 SOP 過 + indoor_tight profile + e-stop（`nav_capability/scripts/emergency_stop.py engage`）就位 + 淨空場地。沿用 [Lane 6 §8 abort criteria](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)：非命令方向移動 / 該停沒停 / 機鼻<0.3m 仍動 → 當場 e-stop + FAIL。

---

## 12. Rollback / Stop Conditions

**Stop（立即停）**：① Go2 非命令方向移動/該停沒停/機鼻<0.3m 仍動 → e-stop。② e-stop 未就位 → 不開任何 motion。③ T0 未排除 / θ_error 未知 → 不發 goto。④ open_space(±30°) → 不在窄客廳發短 goto（先切 indoor_tight）。

**Rollback（軟體）**：
- **T0 修法**（移除 URDF map/odom joint 或換 `go2_on_steroids.urdf`）= 單檔編輯，保留原 `go2.urdf` 一鍵退回；修後跑 §9-D1 確認 `/tf_static` 不再有 map→odom/odom→base_link。
- §5/§6 純 SOP/讀數；改外參或 AMCL 參數一律先放實驗 launch arg、保留現值。
- §7-C body-frame、§8 D435 fusion 全 profile/旗標 gated，預設不接 demo。

**收工即時**：確認 Go2 停穩 → `pawai demo stop`（清 nav stack/driver）→ §9-D0 `pawai evidence pull`。

---

## 13. 工程師 Checklist（上機前，全 no-motion）

- [ ] **D0** `pawai evidence pull` 拿到當天 `[PR1a]` + reactive_stop 時間線
- [ ] **D1（最先）** `ros2 topic echo /tf_static` / `view_frames` / `tf2_monitor` → 確認 map→odom、odom→base_link **只有一個 authority**；有衝突先修 §4 P0
- [ ] **D2** `/amcl_pose` 讀 c[35]；`tf2_echo map base_link` vs 現場
- [ ] **D3** `tf2_echo base_link laser` + `lidar_front_sector.py`（人站機鼻 → ±180° bin）+ `front_offset_rad==π`
- [ ] **D4** `/state/reactive_stop/status`（+25°/1.65m → slow/active=false）+ `scan_rplidar` hz
- [ ] **D5** `smoke_test_nav_static.sh`（記得：過了≠朝向對）；`ros2 action list` 確認 DriveOnHeading
- [ ] Foxglove fixed frame：讀 scan 用 `base_link`、讀定位用 `map`（§5-3/§6-3）
- [ ] e-stop 終端就位（任何 motion 前，由 Roy）

## 附錄：能力分級（proven / needs HITL / research only）

| 能力 | 分級 |
|---|---|
| safe-stop 正前停障 | proven (with limit) |
| 靜態鏈路 / 位置收斂 | proven（**僅位置、不含朝向**） |
| TF authority 乾淨（單 authority per edge） | **needs fix（T0）→ no-motion 即可驗** |
| LiDAR 前向軸校準 SOP | needs HITL（S5-4 一步需 Roy） |
| AMCL yaw/scan-overlay SOP + nav_ready 三拆 | needs HITL（軟體可先做） |
| 短距 goto / DriveOnHeading 0.3m | needs HITL（當前 NOT_DEMO_READY；DriveOnHeading 較有機會） |
| body-frame forward + Collision Monitor | needs HITL（軟體可先做） |
| D435 + LiDAR fusion | research only（外參未校 + 4 bug + MIPI 故障） |
| 動態繞障 / 自由巡邏 / approach person | research only / DO_NOT_CLAIM |
