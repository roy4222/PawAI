# AMIGO ROS2 分析（給 PawAI 借鑑）

- **Source**: https://github.com/eppl-erau-db/amigo_ros2
- **Commit**: `96e830cc6504c9222e84875cef702116dabb5497` (Update README.md)
- **分析日期**: 2026-05-02

## 1. 專案定位

AMIGO = **Autonomous Machine for Inspecting Gas and Operations**，由 Embry-Riddle Aeronautical University 的 EPPL（Engineering Physics Propulsion Lab）開發。**工業巡檢機器狗**，非陪伴/老人場景；目標是在複雜工業環境中自主導航 + 設備巡檢（gas inspection）。**載體：Unitree Go2**（與我們同款）。硬體：Jetson **AGX Orin**（不是 Orin Nano）+ JetPack 6.1 + RealSense D435i/D455 + **RPLIDAR A3** + 未來 ZED X / Unitree LiDAR。

## 2. 整體架構（5 個自製 ROS2 packages）

| Package | 職責 |
|---|---|
| `go2_driver` (C++) | Go2 WebRTC 驅動（與我們的 go2_robot_sdk 同層）|
| `go2_control` (Python) | 13 個 node：odom、TF、lidar、velocity_cmd、initial_pose、`log_pose_action_{server,client}`、`region_map_service/client`、`task_nav_to_pose_test`、`task_nav_path_test`、`vslam_odom`、`occupancy_grid_to_image` |
| `go2_description` | URDF + maps + Nav2/EKF/SLAM yaml + RViz config |
| `go2_bringup` | 兩個 launch：`mapping.launch.py`（建圖）、`go2_deploy.launch.py`（部署巡檢）|
| `go2_interfaces` | `LogPose.action`（記錄當前 pose 到 JSON）、`RegionMap.srv`（取得當前所在區域的 mask map）|

外掛：`isaac_ros_common` + **isaac_ros_nvblox**（NVIDIA 3D voxel mapping）+ `realsense-ros` + `sllidar_ros2` + `unitree_ros2` + `zed-ros2-wrapper`。整個 stack 跑在 **isaac_ros_dev container**。

## 3. SLAM / 導航 stack（與 PawAI 重疊度高）

- **建圖**：`slam_toolbox`（async）+ EKF (`robot_localization`) + RPLIDAR + nvblox（3D voxel）
- **導航**：**Nav2 + MPPI Controller**（不是 DWB）+ EKF odom（**沒用 AMCL**，重定位靠 SLAM toolbox / VSLAM pose）
- **3D 感知**：nvblox `dynamic` mode（dynamic obstacles）整合進 Nav2 costmap
- **VSLAM 備援**：`vslam_odom_node` 訂閱 `/visual_slam/tracking/vo_pose`（Isaac VSLAM）發 odom→base_footprint TF

**vs PawAI**：載體 + RPLIDAR + Nav2 重疊；但他們用 **MPPI + EKF + slam_toolbox + nvblox**，我們用 **DWB + AMCL + cartographer**（slam_toolbox 在我們 ARM64+Humble 已驗證 FATAL ERROR 棄用，他們用 AGX Orin + Isaac container 沒踩到）。

## 4. 獨特 skill / behavior framework

**沒有 BT / state machine / skill DSL**。互動模式是「腳本式」：
- `LogPose action`：手動把 Go2 推到位置 → action client 記錄當前 pose 到 `pose_log.json`，task_type 字串標記
- `task_nav_to_pose_test.py`：讀 JSON → `BasicNavigator.goToPose()` 逐點走 → `perform_task_at_pose()`（目前是 `time.sleep(10)` placeholder）→ 失敗 retry 6 次 → fallback `assistedTeleop`
- `RegionMap service`：把地圖 partition 成 region（cv2 connectedComponents），訂 `/amcl_pose` 查當前 region_id，回傳 masked OccupancyGrid

**精華**：**「teach-and-repeat」pattern** — 人工帶路打點 → 存 JSON → 自動巡檢回放，加 retry / assistedTeleop fallback。

## 5. 與「老人 + 狗」場景相關性

**直接相關度低**。他們是工業巡檢、無人陪伴；沒有 LLM / 語音 / 手勢 / 人臉 / interaction state machine。但**底層導航模式重疊度高**（同 Go2、同 RPLIDAR、同 Nav2、同 EKF），navigation building blocks 可參考。

## 6. 可吸收 vs 不可吸收

**可吸收（高優先）**：
- **`LogPose.action` + `pose_log.json` pattern**：直接套用到 5/12 demo 的 `nav_demo_point` — 我們已有 `LogPose` action（`go2_interfaces`），與其架構一致，可借他們的 task_type 字串標記做多目標管理
- **`task_nav_to_pose_test.py` retry/fallback 邏輯**：6 次 retry → assistedTeleop，可移植到 PawAI Brain Executive 的 Navigate skill 失敗處理
- **`RegionMap.srv` 概念**：把客廳/廚房/玄關 partition，Brain 可用「去廚房」自然語言對應 region_id（取代我們現在的 named_poses 平面結構）
- **nvblox dynamic mode**：未來想做動態障礙避讓（人/狗移動）時，比純 2D costmap 強

**不可吸收**：
- **Isaac ROS container + AGX Orin** 整套：我們是 Orin Nano 8GB，跑不動 nvblox + Isaac VSLAM
- **MPPI controller**：Go2 sport mode `MIN_X = 0.50 m/s` 門檻，MPPI 取樣空間需重調，且我們 DWB 已 calibrated 過
- **slam_toolbox**：ARM64 + Humble + RPLIDAR 已知 FATAL bug（我們已棄用，cartographer 是定案）
- **沒 AMCL**：他們靠 SLAM/VSLAM 持續定位，我們 demo 場景固定地圖 + AMCL 更輕量
- **RPLIDAR A3**：我們是 A2M12（baudrate 不同：256000 vs 115200）

## 7. 5/12 demo 立即行動建議

1. **`approach_person`**：他們沒有，需要我們自製（face/pose detection → goal pose 動態計算）
2. **`nav_demo_point`**：照抄 teach-and-repeat — 用我們現有 `LogPose` action 打 3-5 個點存 JSON，Brain 觸發 `BasicNavigator.goToPose()` 序列回放，加 3 次 retry fallback（不用 assistedTeleop，太危險）
