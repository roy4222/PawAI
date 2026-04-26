# 導航避障 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。`.claude/rules/` 中的對應檔案只是薄橋接。

## 不能做

- 不要修改 D435 camera launch 參數（那是 face_perception 的領域）
- 不要動 `nav2_params.yaml` 的 footprint（60×30cm 短於 Go2 真實 70×31cm，但 4/26 實機驗證仍 work；正式校正排到 5/13 demo 後）
- 不要在 `start_nav2_amcl_demo_tmux.sh` / `start_reactive_stop_tmux.sh` 同時跑（cmd_vel 衝突）— 互斥使用

## 改之前先看

### Nav2 主線
- `go2_robot_sdk/config/nav2_params.yaml`（AMCL + DWB + costmap，v3.7 已驗證）
- `scripts/start_nav2_amcl_demo_tmux.sh`（5-window 啟動）
- `scripts/send_relative_goal.py`（讀 amcl_pose 算前方相對 goal）

### Reactive fallback
- `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`（≈ 130 行）
- `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py`（純 Python helpers）
- `scripts/start_reactive_stop_tmux.sh`（4-window）

### 舊 D435 / vision_perception 模組
- `vision_perception/vision_perception/obstacle_detector.py`（D435 depth，4/3 停用）
- `vision_perception/vision_perception/lidar_obstacle_detector.py`（LaserScan 純邏輯，可參考）

## 常見陷阱

### Nav2 / AMCL
- **`/goal_pose` QoS 是 BEST_EFFORT**（bt_navigator 訂閱端）— publisher 必須匹配，否則訊息直接丟（4/26 踩過）。`ros2 topic pub --once` 預設 RELIABLE 會 race，要加 `--qos-reliability best_effort`
- **不要連發太密集的 goal**：5 個 goal 1.5s 內連發會讓 controller preempt 太頻繁，`Reached the goal!` 在距離 0.5m 就誤觸發。`send_relative_goal.py` 預設 `--repeat 1` 已修
- **昨天 lethal 是暫態**（4/26 判定）：costmap 髒污 / particle filter 漂移，不是位置固有 / 不是 inflation 過大 / 不是 footprint padding。不要為了「修 lethal」盲改 inflation_radius
- **首次 plan 失敗 → BT 自動 clear costmap → 重 plan 通常成功**：這是 v3.7 的設計行為，但 spin recovery 對 quadruped 無效（Go2 MIN_X=0.50 m/s 下無法原地轉），所以 plan 連續失敗會卡死
- **AMCL covariance 0.22 偏大但仍可規劃**：理想 < 0.05 但需 Go2 移動才會收斂；實機驗證 0.22 仍能成功 plan
- **Foxglove `/initialpose` 設定後**：等 AMCL 發 `map → odom` TF（log 看 `Setting pose: ...`）才能發 goal
- **5 個 nav2 lifecycle 不一定要全 active**：amcl + map_server active 即 Go2 可動；controller_server / planner_server / bt_navigator / behavior_server 第二次 `lifecycle get` 可能 hang（service competing），實際都活著

### Reactive stop
- **/cmd_vel QoS 是 RELIABLE**（go2_driver_node 訂閱端）— reactive_stop_node 已用 RELIABLE
- **/scan_rplidar QoS 是 BEST_EFFORT**（sllidar publisher）— reactive_stop_node 訂閱端用 BEST_EFFORT
- **第一筆 cmd_vel = 0 warmup**：避免與 Go2 driver 已啟動的 stand mode 衝突
- **Hysteresis 3 frame 防抖**：danger → 非 danger 需連 3 frame 確認才解除

### 環境 / 部署
- **Jetson 跳電（XL4015 已知問題）**：4/26 上午跳電過 1 次，重啟後 SSH ~3 分鐘恢復；建圖過程要避免 Go2 同時驅動高功耗（喇叭/相機等），降低跳電風險
- **ros2 daemon 偶爾 sync 慢**：剛啟動的 publisher，topic hz 第一次抓不到很正常，等 5-10s 重試
- **重新建圖前先備份**：`cp /home/jetson/maps/home_living_room.{yaml,pgm,pbstream}{,.bak.$(date +%Y%m%d-%H%M%S)}`

## 驗證指令

### 單元測試
```bash
# reactive_stop_node 純邏輯（17 cases）
cd go2_robot_sdk && python3 -m pytest test/test_reactive_stop_node.py --no-cov

# vision_perception 既有 lidar_obstacle_detector
python3 -m pytest vision_perception/test/test_lidar_obstacle_detector.py -v
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

### Build
```bash
# 改 reactive_stop_node 後
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
ros2 pkg executables go2_robot_sdk | grep reactive_stop_node  # 確認 entry point
```

### 實機 sanity（Nav2 demo 啟動後）
```bash
ros2 lifecycle get /amcl                                # active
ros2 topic hz /scan_rplidar                            # ~10.4 Hz
ros2 topic hz /cmd_vel                                 # ~10 Hz（goal 啟動後）
ros2 topic info /goal_pose -v                          # 確認 BEST_EFFORT 訂閱端
ros2 run tf2_ros tf2_echo map base_link                # AMCL pose 與現場一致
ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap '{}'
```
