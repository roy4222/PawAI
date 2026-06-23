# Go2 導航避障 Weekly Execution Plan

更新日期：2026-03-02
**版本：** v2.2 (D435 整合版)  
**基於：** `docs/navigation/落地計畫_v2.md`

---

## 執行原則

1. **一次只改一個變數** — A/B 測試的鐵律
2. **Gate 未過不進下一階段** — 安全第一
3. **每日固定流程** — prelaunch → launch → measure → record → shutdown
4. **可重現性優先** — 所有參數變動都要記錄、可回滾

---

## Phase A：安全與穩定止血

---

### Week 1 — 感測密度與近場可見度

**目標：** 解決「看不到/看太晚」問題，先找到 Jetson Orin Nano 上穩定的 `LIDAR_POINT_STRIDE`

**每日任務：**

#### Day 1 — 建立基線 (stride=8)

```bash
# 1. 清場
zsh scripts/go2_ros_preflight.sh prelaunch

# 2. 啟動 Nav2 localization（基線 stride=8）
GO2_LIDAR_DECODER=wasm LIDAR_POINT_STRIDE=8 \
  MAP_YAML=/home/jetson/go2_map.yaml \
  zsh scripts/start_nav2_localization.sh

# 3. 等待 25 秒，給初始座標
sleep 25
zsh scripts/set_initial_pose.sh 0.0 0.0 0.0
sleep 2

# 4. 驗證單一發布者
zsh scripts/go2_ros_preflight.sh postlaunch

# 5. 量測（記錄結果）
zsh scripts/check_gate_c_rates.sh 5 10
zsh scripts/ros2w.sh topic hz /amcl_pose
tegrastats &  # 背景跑 2-3 分鐘
```

**記錄欄位：**
- `/point_cloud2` Hz: ___
- `/scan` Hz: ___
- `/amcl_pose` Hz: ___
- tegrastats CPU 均值: ___
- `/scan` 有效回波比例: ___

---

#### Day 2 — A/B 測試 stride=2

```bash
# 與 Day 1 相同流程，只改 stride
GO2_LIDAR_DECODER=wasm LIDAR_POINT_STRIDE=2 \
  MAP_YAML=/home/jetson/go2_map.yaml \
  zsh scripts/start_nav2_localization.sh

# 驗證 /scan 不是全 inf
zsh scripts/ros2w.sh topic echo /scan --once

# 短距導航測試（無障礙）
for i in {1..10}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.4 --timeout 40 || break
  sleep 1
done
```

---

#### Day 3 — A/B 測試 stride=1

```bash
# 與 Day 2 相同，stride=1
GO2_LIDAR_DECODER=wasm LIDAR_POINT_STRIDE=1 \
  MAP_YAML=/home/jetson/go2_map.yaml \
  zsh scripts/start_nav2_localization.sh

# 同樣的 10 次短距測試
```

**記錄：** stride=1 的 Hz、CPU、成功率

---

#### Day 4 — 決定「生產 stride」

**選擇原則：**
1. 優先 stride=1（幾何最佳）
2. 若 Hz < 5Hz 或 CPU 滿載，退到 stride=2
3. 只有性能崩潰時才用 stride=8

**決策後，更新預設：**

```bash
# 修改 scripts/start_nav2_localization.sh
# 第 15 行改為選定的值
export LIDAR_POINT_STRIDE="${LIDAR_POINT_STRIDE:-<chosen_value>}"

# 同樣修改 scripts/start_slam_mapping.sh
# 同樣修改 start_go2_wired_webrtc.sh
```

---

#### Day 5 — 近場障礙物驗證

```bash
# 放置小障礙物於 0.4-0.8m 處
# 跑 20 次短距目標（障礙物不在路徑上，只驗證感知）
for i in {1..20}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 45 || true
  sleep 1
done
```

**Week 1 驗收標準：**
- [ ] `/scan` 穩定 >= 8 Hz（最低 >= 5 Hz）
- [ ] `/point_cloud2` 穩定 >= 8 Hz
- [ ] 10 次短距導航成功率 >= 90%
- [ ] 已選定生產 stride 並更新所有腳本

**Week 1 交付：**
- `docs/testing/reports/week1_stride_ab.md` — A/B 對照表
- 更新後的啟動腳本（stride 預設值）

---

### Week 2 — 安全包絡 + 恢復策略 + 可觀測性

**目標：** 0 碰撞，降低 ABORT，建立快速診斷流程

**當前基線參數（記錄於 `nav2_params.yaml`）：**
- `footprint_padding: 0.05`
- `inflation_radius: 0.35`
- `cost_scaling_factor: 2.0`
- `movement_time_allowance: 20.0`
- `BaseObstacle.scale: 0.40`

---

#### Day 1 — 建立 Week 2 測試場景

```bash
# 測試場景定義
# - 0.5m 目標（無障礙）
# - 0.8m 目標（無障礙）
# - 0.5m 目標（路徑邊緣放置單一障礙物）

# 先用基線參數跑 10 次記錄問題
for i in {1..10}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 45 || true
  sleep 1
done
```

---

#### Day 2 — 成本圖保守化測試 A

**變更 `go2_robot_sdk/config/nav2_params.yaml`：**

```yaml
# 只改這一項
local_costmap:
  local_costmap:
    ros__parameters:
      footprint_padding: 0.08  # 從 0.05 增加
```

```bash
# 記得 colcon build
colcon build --packages-select go2_robot_sdk

# 測試 20 次
for i in {1..20}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 45 || true
  sleep 1
done
```

**記錄：** 碰撞次數、ABORT 次數、卡住次數

---

#### Day 3 — 成本圖保守化測試 B

**變更（若 Day 2 效果不明顯）：**

```yaml
local_costmap:
  local_costmap:
    ros__parameters:
      inflation_layer:
        inflation_radius: 0.45  # 從 0.35 增加
        cost_scaling_factor: 4.0  # 從 2.0 增加
```

**或測試障礙層縮短視距（減少遠處雜訊）：**

```yaml
obstacle_layer:
  scan:
    obstacle_max_range: 2.5  # 從 3.0 縮短
    raytrace_max_range: 3.0  # 從 3.5 縮短
```

---

#### Day 4 — 卡住與 ABORT 減少

**變更：**

```yaml
controller_server:
  ros__parameters:
    progress_checker:
      movement_time_allowance: 10.0  # 從 20.0 縮短
    
    FollowPath:
      BaseObstacle.scale: 0.80  # 從 0.40 增加（測試）→ 1.20（若仍碰撞）
```

---

#### Day 5 — 建立可觀測性流程

**建立 `scripts/tmux_nav2_debug.sh`：**

```bash
#!/usr/bin/env zsh
# Go2 Nav2 Debug Cockpit
tmux new-session -d -s nav2dbg

# Pane 1: cmd_vel
tmux split-window -v -t nav2dbg
tmux send-keys -t nav2dbg.0 'zsh scripts/ros2w.sh topic echo /cmd_vel' C-m

# Pane 2: action status
tmux split-window -v -t nav2dbg
tmux send-keys -t nav2dbg.1 'zsh scripts/ros2w.sh topic echo /navigate_to_pose/_action/status' C-m

# Pane 3: rates
tmux split-window -h -t nav2dbg
tmux send-keys -t nav2dbg.2 'zsh scripts/check_gate_c_rates.sh 5 10' C-m

# Pane 4: costmap rate
tmux send-keys -t nav2dbg.3 'zsh scripts/ros2w.sh topic hz /local_costmap/costmap_raw' C-m

tmux attach -t nav2dbg
```

**建立失敗分類文件：**
- `docs/testing/reports/week2_failures.md`
- 分類：感測稀疏 / 成本圖 / 控制器 / TF時間

**Week 2 驗收標準：**
- [ ] 連續 50 次 0.5m/0.8m 目標：**0 碰撞**
- [ ] ABORT 率 <= 10%（理想 <= 5%）
- [ ] 每次失敗可在 10 分鐘內分類根因

**Week 2 交付：**
- 安全的 Nav2 參數集（已 colcon build）
- `scripts/tmux_nav2_debug.sh`
- 失敗分類紀錄表

---

### Week 2.5 — D435 近場補強整合（A4）

**前置條件：** Week 1 stride 已確定，`/scan` >= 8Hz 穩定

**目標：** 將 D435 加入 local costmap 作為第二觀測源，補強近場偵測

---

#### Day 1 — D435 驅動安裝與驗證

```bash
# 1. 安裝 realsense2_camera ROS2 套件
sudo apt install ros-humble-realsense2-camera ros-humble-realsense2-description

# 2. 驗證硬體連接
rs-enumerate-devices

# 3. 單獨啟動 D435 節點測試
ros2 launch realsense2_camera rs_launch.py \
  depth_module.depth_profile:=424x240x15 \
  enable_color:=false \
  pointcloud.enable:=true \
  decimation_filter.enable:=true \
  temporal_filter.enable:=true \
  spatial_filter.enable:=true

# 4. 確認 topic 發布
ros2 topic hz /camera/camera/depth/color/points
ros2 topic echo /camera/camera/depth/color/points --once
```

**記錄：**
- D435 PointCloud2 Hz: ___
- tegrastats CPU 增量: ___%
- 是否有 TF 錯誤: ___

---

#### Day 2 — URDF 切換與 TF 驗證

```bash
# 1. 切換 URDF 為 go2_with_realsense.urdf
# 在 robot.launch.py 中修改 urdf 參數指向 go2_with_realsense.urdf

# 2. colcon build
colcon build --packages-select go2_robot_sdk

# 3. 啟動與驗證 TF
# 確認以下 TF 鏈正常：
#   map -> odom -> base_link -> ... -> camera_mount_link -> camera_link
ros2 run tf2_tools view_frames

# 4. 在 RViz 中確認 camera_link 位置與實際相機安裝位置匹配
```

---

#### Day 3 — 將 D435 加入 local costmap

修改 `go2_robot_sdk/config/nav2_params.yaml`：

```yaml
# 只改 local_costmap 區段
local_costmap:
  local_costmap:
    ros__parameters:
      plugins: ["voxel_layer", "inflation_layer"]
      voxel_layer:
        plugin: "nav2_costmap_2d::VoxelLayer"
        observation_sources: scan d435
        scan:
          topic: /scan
          data_type: LaserScan
          marking: true
          clearing: true
          obstacle_max_range: 3.0
          raytrace_max_range: 4.0
        d435:
          topic: /camera/realsense2_camera_node/depth/obstacle_point
          data_type: PointCloud2
          marking: true
          clearing: true
          obstacle_max_range: 2.0
          raytrace_max_range: 2.5
          min_obstacle_height: 0.05
          max_obstacle_height: 1.2
```

```bash
colcon build --packages-select go2_robot_sdk

# 測試 20 次短距導航（含低矮障礙物）
for i in {1..20}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 45 || true
  sleep 1
done
```

**驗證重點：**
- RViz 中 local costmap 是否顯示 D435 偵測的障礙物
- 是否有假障礙（地板、零星雜點）
- 碰撞次數: ___

---

#### Day 4 — collision_monitor 配置

```bash
# 配置 nav2_collision_monitor 以 D435 作為獨立短程急停源
# 範圍：0.2-1.5m 前向區域
# 詳見 nav2 collision_monitor 文件

# 測試 30 次短距導航（含低矮障礙物）
for i in {1..30}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 45 || true
  sleep 1
done
```

---

#### Day 5 — D435 A/B 對照測試

```bash
# LiDAR-only vs LiDAR+D435 對照
# 場景：低矮障礙物（0.15m 高紙箱）放於路徑上

# Test A: LiDAR-only（停用 D435 observation source）
# 跑 20 次，記錄碰撞/ABORT

# Test B: LiDAR+D435
# 跑 20 次，記錄碰撞/ABORT

# 比較兩組差異
```

**Week 2.5 驗收標準：**
- [ ] D435 PointCloud2 穩定 >= 10Hz
- [ ] camera_link TF 在 RViz 中位置正確
- [ ] local costmap 可見 D435 偵測障礙
- [ ] CPU 增量 <= 15%
- [ ] D435 離線時導航不中斷（自動回退 LiDAR-only）
- [ ] 連續 30 次短距導航 0 碰撞（含低矮障礙場景）

**Week 2.5 交付：**
- `docs/testing/reports/week2.5_d435_integration.md` — D435 整合報告
- 更新後的 `nav2_params.yaml`（含 D435 observation source）
- 更新後的 launch 檔（含 realsense2_camera 啟動）
- D435 A/B 對照測試結果
- 安全的 Nav2 參數集（已 colcon build）
- `scripts/tmux_nav2_debug.sh`
- 失敗分類紀錄表

---

## Phase B：控制體感優化

---

### Week 3 — DWB Critics 調優（減少抖動/猶豫）

**前置條件：** Week 2 驗收全過

**目標：** 減少「怕怕的狗」體感（stop-go、原地旋轉）

---

#### Day 1 — 建立 Week 3 基線

```bash
# 用 Week 2 的「安全參數」跑 30 次
for i in {1..30}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 50 || true
  sleep 1
done

# 同時觀察 cmd_vel 連續性
zsh scripts/ros2w.sh topic echo /cmd_vel
```

**記錄：** 抖動次數、原地旋轉次數、急停次數

---

#### Day 2 — Critics 調優 A

**變更：**

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      PathAlign.scale: 8.0  # 從 16.0 降低
      GoalAlign.scale: 6.0   # 從 10.0 降低
```

**測試：** 20 次短距，觀察路徑跟隨抖動

---

#### Day 3 — Critics 調優 B

**變更：**

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      RotateToGoal.scale: 0.15      # 從 0.25 降低（減少過度旋轉）
      trans_stopped_velocity: 0.03   # 從 0.05 降低（減少假停判定）
```

**測試：** 20 次，觀察接近目標時的行為

---

#### Day 4 — Velocity 平滑化

**變更：**

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      min_vel_x: 0.02  # 從 0.05 降低（更平滑起步）
```

**測試：** 20 次，觀察起步/停止連續性

---

#### Day 5 — 100 次可靠性測試

```bash
# 用最佳參數跑 100 次
for i in {1..100}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 50 || true
  sleep 1
done
```

**Week 3 驗收標準：**
- [ ] 100 次短距目標：成功率 >= 95%，**0 碰撞**
- [ ] 主觀體感：轉向連續性明顯提升，急停頻率下降

**Week 3 交付：**
- `docs/testing/reports/week3_dwb_ab.md` — 每個參數變動的效果記錄
- DWB 優化參數集

---

### Week 4 — DWB 定版 + MPPI 選擇性評估

**目標：** 鎖定「可交付」的 DWB 配置；若條件允許，評估 MPPI

---

#### Day 1-2 — DWB 定版

**清理 debug 開銷（若需要）：**

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      debug_trajectory_details: False  # 從 True 改為 False
```

**完整回歸測試：**

```bash
# 200 次短距目標（分批跑）
for i in {1..100}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 55 || true
  sleep 1
done

# 換場景：有單一障礙物
for i in {1..50}; do
  python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 55 || true
  sleep 1
done
```

---

#### Day 3 — 驗收 Gate G1/G2/G3/G4

**系統穩定性檢查：**

```bash
zsh scripts/check_gate_c_rates.sh 5 10
python3 scripts/go2_nav_test.py --test topics --wait 10
tegrastats  # 監看 5 分鐘
```

---

#### Day 4-5 — MPPI 選擇性評估（僅若 Day 3 全過）

**安裝/啟用 MPPI：**

```yaml
controller_server:
  ros__parameters:
    controller_plugins: ["FollowPath"]
    FollowPath:
      plugin: "nav2_mppi_controller::MPPIController"
      # Jetson 保守參數
      batch_size: 200
      time_steps: 20
      model_dt: 0.05
      vx_max: 0.22  # 與 DWB 相同，公平比較
      vx_min: 0.02
      max_vel_theta: 0.30
```

**比較測試：**
- 同一路線各跑 50 次
- 記錄：成功率、抖動、CPU、延遲、完成時間

**Week 4 驗收標準：**
- [ ] DWB：200 次目標，成功率 >= 95%，ABORT <= 5%，**0 碰撞**
- [ ] MPPI（若評估）：必須嚴格優於 DWB 且不造成 CPU 飽和，否則回退 DWB

**Week 4 交付：**
- 「可交付」Nav2 配置（AMCL + 成本圖 + DWB）
- 可選：`docs/testing/reports/week4_mppi_eval.md` — 評估報告與 go/no-go 建議

---

## Phase C：架構升級評估（大綱）

**僅在 Phase A/B 穩定量產後才進入**

---

### Week 5-6 — Cartographer 評估（條件性）

**進入條件：**
1. 已證明主要問題是定位/地圖一致性（非感測稀疏或控制器調參）
2. Jetson 算力與記憶體有明確 headroom

**任務：**
- 安裝 `ros-humble-cartographer`
- 與 AMCL A/B 比較：定位穩定性、地圖一致性、資源消耗
- 決定是否遷移

---

### Week 7+ — D435 進階應用 + AI 模型評估（條件性）

**進入條件：** Phase A/B 穩定量產，D435 基礎整合已穩定

**D435 進階：**
- depth-to-costmap 精細化調整（濾波器參數、視野裁剪）
- D435 輔助的視覺子目標建議（shadow mode）

**AI 模型：**
- NoMaD/ViNT/DRL 僅作研究評估，不直接接管實機主控制
- 必須先通過沙盒測試
- 明確降級策略

> **注意：** Isaac ROS Visual SLAM 對 D435（無 IMU）支援不足，暫不採用。
---

## 附錄：每日執行檢查清單

### 每日啟動前

```bash
# [ ] 清場
zsh scripts/go2_ros_preflight.sh prelaunch

# [ ] 確認 map yaml 存在
ls -la $MAP_YAML

# [ ] 確認上一輪參數已 colcon build
colcon build --packages-select go2_robot_sdk  # 若有改 config
```

### 每日執行中

```bash
# [ ] 啟動
GO2_LIDAR_DECODER=wasm LIDAR_POINT_STRIDE=<chosen> \
  MAP_YAML=/home/jetson/go2_map.yaml \
  zsh scripts/start_nav2_localization.sh

# [ ] 等待 25 秒
sleep 25

# [ ] 給初始座標
zsh scripts/set_initial_pose.sh 0.0 0.0 0.0

# [ ] 驗證發布者
zsh scripts/go2_ros_preflight.sh postlaunch

# [ ] 啟動 debug cockpit（另一 terminal）
zsh scripts/tmux_nav2_debug.sh
```

### 每日執行後

```bash
# [ ] 關閉所有相關进程
zsh scripts/go2_ros_preflight.sh prelaunch  # 會清場

# [ ] 記錄當日結果到 reports/
# [ ] git commit 當日參數變動（含清楚 commit message）
```

---

## 結論

這份周計畫把「深度報告」轉成**每週可執行、可驗收、可回滾**的具體任務：

| 週次 | 主題 | 核心交付 | Gate |
||------|------|----------|------|
| W1 | 感測密度 | 選定 stride、A/B 表 | Hz >= 8, 成功率 >= 90% |
| W2 | 安全包絡 | 安全參數、debug 流程 | 0 碰撞, ABORT <= 10% |
| W2.5 | **D435 整合** | **近場補強、voxel_layer 配置** | **D435 >= 10Hz, 0 碰撞, CPU <= +15%** |
| W3 | DWB 調優 | 優化 critics | 成功率 >= 95%, 0 碰撞 |
| W4 | DWB 定版 | 可交付配置 | 200 次驗證, 可選 MPPI |
| W5+ | 架構升級 | 評估報告 | 條件性進入 |

**關鍵紀律：**
- Gate 未過，不進下一週
- 一次只改一個變數
- 所有變動都要可回滾
