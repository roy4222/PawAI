# 導航避障（nav_capability + reactive_stop）

## 這個模組是什麼

Layer 3 能力模組，負責 Go2 在室內地圖上的自主導航（Nav2 + AMCL + cartographer）與反應式停障（reactive_stop_node）。
4/26 新增 nav_capability 平台層（named_poses、run_route、GotoRelative action），5/11 B5 burndown 發現並修正 reactive_stop danger threshold 和 cmd_vel=0 無法停車的問題。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/nav/nav-runtime-flow.md` | RPLIDAR → cartographer → Nav2 AMCL → DWB → mux → Go2 driver 完整 flow |
| `docs/pawai-brain/architecture/0511/nav/nav-reactive-stop-and-mux.md` | reactive_stop_node + cmd_vel_mux 架構、safety_only 模式、danger/slow 閾值 |
| `docs/pawai-brain/architecture/0511/nav/nav-capability-brain-integration.md` | nav_capability platform layer + Brain skill_policy_gate 整合 |
| `docs/pawai-brain/architecture/0511/nav/nav-field-runbook.md` | 建圖/定位/demo 現場操作步驟 + 常見故障排查 |
| `docs/pawai-brain/architecture/0511/nav/nav-known-issues-roadmap.md` | 已知問題清單 + 5/11 B5 burndown 修法 |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `go2_robot_sdk/go2_robot_sdk/robot_control_service.py` | cmd_vel 處理（含 StopMove 修正）|
| `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py` | LiDAR 距離 → 發布停障訊號 |
| `nav_capability/nav_capability/named_pose_manager.py` | named_poses CRUD（記憶位置）|
| `nav_capability/nav_capability/route_runner.py` | run_route action server |
| `scripts/start_nav_capability_demo_tmux.sh` | 8-window tmux nav demo 一鍵啟動 |
| `scripts/start_nav2_amcl_demo_tmux.sh` | 5-window Nav2 AMCL demo（無 nav_capability）|
| `scripts/build_map.sh` | cartographer 建圖一鍵啟動 |

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/cmd_vel` | Nav2/mux → go2_driver | 速度指令（mux priority 機制）|
| `/state/reactive_stop/status` | reactive_stop_node → | 停障狀態（CLEAR/DANGER/SLOW）|
| `/state/nav/safety` | nav stack → | 導航安全狀態（nav_safe bool）|
| `/capability/nav_ready` | nav stack → | Nav2 AMCL 就緒狀態（Bool, Studio tri-state）|
| `/capability/depth_clear` | reactive_stop → | D435 depth clear 狀態（Bool）|

## 已知陷阱

- **Go2 sport mode MIN_X = 0.50 m/s**：DWB `min_vel_x` 必須 ≥ 0.45，否則 Go2 拒抬腳（4/25 calibration）
- **cmd_vel=0 不停車**：`Move {x:0,y:0,z:0}` 被 silently 忽略 → driver 改為走 `StopMove (api_id=1003)`（5/11 B4 burndown 修）
- **reactive_stop danger threshold 對 Go2 機身太近**：LiDAR 安在 base_link 前 17.5cm，Go2 機鼻在前 ~50-60cm，danger=0.6m 時機鼻只剩 ~0.2m（5/11 B5 burndown 問題，修法見 `nav-known-issues-roadmap.md`）
- **`safety_only=true` 必須用於 mux 模式**：否則 clear zone 永久 shadow nav 速度指令
- **`slam_toolbox` 在 ARM64+Humble 永久棄用**：Mapper FATAL ERROR known bug，改用 cartographer
- **不要 `ros2 topic pub --once /goal_pose`**：bt_navigator subscriber 是 BEST_EFFORT，改用 `-r 2 --times 5`
- **`GO2_PUBLISH_ODOM_TF=0`** 建圖用（cartographer 負責 odom→base_link TF），預設 1（Nav2 demo 用 AMCL）

## 開發入口

```bash
# 建圖（cartographer + RPLIDAR）
bash scripts/build_map.sh home_living_room

# Nav2 AMCL Demo
bash scripts/start_nav2_amcl_demo_tmux.sh
# 等 ~30s 後設 /initialpose

# Nav Capability Demo（推薦）
bash scripts/start_nav_capability_demo_tmux.sh

# 發 relative goal
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.5}"

# 驗證
ros2 topic echo /state/reactive_stop/status
ros2 topic echo /state/nav/safety
```
