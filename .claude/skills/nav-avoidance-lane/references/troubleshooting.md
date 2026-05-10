# Troubleshooting — Nav Avoidance Lane

## ⚠️ B5 撞牆事件（5/11）— 已修但要記得

**症狀**：reactive_stop 在跑、LiDAR 沒問題、TF 對的，但 Go2 還是撞到 1.5m 處障礙物。

**雙重根因**：

1. **`twist_mux` 0.5s timeout 沉默降級**
   - 5/11 當時 reactive_stop 走 `mode=progressive`（B5 階段已升級到 4-mode）
   - progressive 在 clear zone **完全不發訊號**（只 danger 才發 0）
   - 0.5s 後 mux 認為 `/cmd_vel_obstacle` channel (priority 200) 過期
   - mux priority 真實值：emergency 255 / **obstacle 200 / teleop 100 / nav 10**
   - obstacle 沉默後 → teleop 100 與 nav 10 競爭 → teleop 永遠贏 → 接管 0.5 m/s 命令
   - mux 假設「沉默 = 不要管」，但 reactive_stop 的「沉默」應被解讀為「保持上一次決定」
   - 安全前提：**capability demo 必須沒有 teleop hot publisher 在跑**，這樣 obstacle 沉默就只剩 nav 10，nav 接管

2. **`danger_distance_m=0.6` 對 Go2 太近**
   - LiDAR 在 base_link 前 17.5cm
   - Go2 機鼻在 base_link 前 50-60cm
   - LiDAR 看到 0.6m → 機鼻只剩 0.2m
   - 加上 0.5 m/s × 0.3s 反應時間 + 機身慣性 → **必撞**

**修法（5/11 後落地）**：
- `danger_distance_m` 0.6 → 1.1m（capability mode 已固定）
- `slow_distance_m` 0.45 → 1.7m
- 移開障礙後不自動 resume（mux 重發機制 待後續）

📍 `docs/pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md §4 B5`

## Go2 sport mode MIN_X = 0.5 m/s

**症狀**：DWB planner 算出 cmd_vel.linear.x = 0.3 m/s，Go2 不抬腳。

**原因**：Go2 sport mode `Move` API (api_id=1008) 對 linear.x 有 0.5 m/s 硬下限。

**修法**：DWB `min_vel_x` ≥ 0.45（已 calibrate 在 nav2_params.yaml）。

## driver 對 cmd_vel zero 沒停（5/11 撞牆事件 ②）

**症狀**：發 `Twist {x:0, y:0, z:0}` 給 `/cmd_vel`，Go2 走過頭 2m 才停。

**原因**：driver `_on_cmd_vel` 對 zero twist 還是走 `Move {x:0}` (api_id=1008)，但 Go2 sport mode 對 `Move` 有 MIN_X=0.5 → silently 忽略 → Go2 繼續執行最後一個有效 Move 直到 sport timeout (~2-3s)。

**修法（5/11 提交）**：
- driver `RobotControlService.handle_cmd_vel` 對 post-deadband zero 改走 `send_stop_move_command()` (api_id=1003 `StopMove`)
- 加 1 Hz dedupe 避免 reactive 10 Hz spam StopMove 撐爆 WebRTC DC buffer

權威 unit test：`go2_robot_sdk/test/test_robot_control_service.py` 11 條全綠。

## slam_toolbox FATAL ERROR

**症狀**：用 slam_toolbox 建圖 → `Mapper FATAL ERROR`。

**原因**：ARM64 + Humble + RPLIDAR 已知不相容 bug。

**修法**：**永久放棄 slam_toolbox**，用 cartographer。

## Cartographer 跟 driver odom 衝突

**症狀**：mapping mode 啟 driver 一起跑 → cartographer pose drift 嚴重。

**原因**：driver 預設發 odom→base_link TF，與 cartographer 內部估計衝突。

**修法**：
- mapping mode：`GO2_PUBLISH_ODOM_TF=0` 給 driver（讓 cartographer own）
- 或更乾淨：mapping mode **完全不啟 driver**（純 LiDAR scan-matching）

## AMCL particles 不收斂

**症狀**：amcl mode 啟動後 `/amcl_pose` covariance 一直很高、`/capability/nav_ready` false。

**檢查項**：
1. `/initialpose` 設了嗎？AMCL 不會自動定位，需手動在 Foxglove/RViz 設一次
2. `/odom` 有 publisher 嗎？AMCL 需要 odom 推 particle prediction
3. LiDAR `/scan_rplidar` Hz 正常嗎？AMCL 需要 sensor update
4. map_server `/map` topic publish 了嗎？

```bash
ros2 topic info /amcl_pose
ros2 topic echo /amcl_pose --once  # covariance < 0.45 才算收斂
ros2 topic echo /capability/nav_ready --once  # 應 data: true
```

## /goal_pose 發了 Go2 沒動

**症狀**：發 `/goal_pose` 沒反應。

**檢查順序**：
```bash
# 1. AMCL 收斂了嗎
ros2 topic echo /amcl_pose --once

# 2. /goal_pose 真的有送進去嗎（bt_navigator 是 BEST_EFFORT，會 race）
# 不要用 --once，用 -r 2 --times 5 多次發
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  '{header: {frame_id: map}, pose: {position: {x: 1.0, y: 0, z: 0}, orientation: {w: 1.0}}}' \
  -r 2 --times 5

# 3. cmd_vel 真的有出來嗎
ros2 topic hz /cmd_vel
ros2 topic hz /cmd_vel_nav  # nav2 planner 出口

# 4. mux 把 cmd_vel 路給誰
ros2 topic info /cmd_vel -v  # publisher 是 twist_mux 嗎
```

## 多個 driver instance 殘留

**症狀**：`tmux ls` 看不到 driver session 但 `ros2 node list` 還有 `go2_driver_node`。

**原因**：`pkill python3` 只殺 launch parent，C++ 子 process（pointcloud_to_laserscan、robot_state_publisher、joy 等）殘留 → 下次 launch 雙 publisher。

**修法**：cleanup.sh 已內建 `pkill -9 -f` 逐一清這些 process。手動：
```bash
ssh jetson-nano "pkill -9 -f go2_driver; \
                 pkill -9 -f robot_state; \
                 pkill -9 -f pointcloud; \
                 pkill -9 -f joy_node; \
                 pkill -9 -f teleop; \
                 pkill -9 -f twist_mux"
```

## Go2 OTA 自動更新

**症狀**：Go2 自動連上 Wi-Fi → 韌體被更新 → API 行為改變。

**修法**：用 Ethernet 直連模式（192.168.123.161）開發，避免 Go2 連外網。

## Go2 重開機 WebRTC ICE FROZEN

**症狀**：driver 啟動後 hang 在 ICE handshake 10-15s，第一個 candidate FROZEN→FAILED。

**原因**：第一個 candidate 失敗，第二個會通常成功。

**修法**：耐心等 10-15s，必要時重啟 driver。

## reactive_stop standalone vs mux 模式混用

**症狀**：start fallback 後發 `/cmd_vel_joy` 正常走，但啟 capability mode 後同樣指令無效。

**原因**：
- `fallback` mode：reactive 用 standalone（mode="" + safety_only=false），直發 `/cmd_vel`，3 段速 0/0.45/0.60 m/s
- `capability` mode：reactive 用 `mode=progressive`，發 `/cmd_vel_obstacle` 進 mux（priority 200），danger=0、slow/clear 沉默
- 另有專用腳本 `start_reactive_stop_safety_hold_tmux.sh` 用 `mode=hold_brake`（永遠 publish 0），給 B5 純停車驗證 / demo emergency hold 用，**不是**正常 demo mode

兩個 mode 互斥使用，不能同時啟。preflight 已會擋。

完整 4-mode + standalone 設計：`go2_robot_sdk/go2_robot_sdk/lidar_geometry.py:66 decide_velocity()` docstring。

## clean_all.sh pipefail + grep 空結果中斷

**症狀**：cleanup 腳本跑到 `RESIDUAL=$(ps aux | grep ... | wc -l)` 在無殘留時 grep 回 1，pipefail 傳播，腳本中斷。

**修法**：尾端加 `|| true` 或不用 pipefail。skill 的 cleanup.sh 用 `set -uo pipefail`（不含 -e）。

## nav_capability runtime path 被 colcon 覆蓋

**症狀**：改了 named_poses.json 但下次啟動回到舊內容。

**原因**：早期 nav_capability 預設 `named_poses_file` 指向 `pkg_share`，被 colcon build 覆蓋。

**修法（commit `e2b3932` 已修）**：用 `~/elder_and_dog/runtime/nav_capability/`，env override `NAV_NAMED` / `NAV_ROUTES`。skill start.sh 已自動 export。
