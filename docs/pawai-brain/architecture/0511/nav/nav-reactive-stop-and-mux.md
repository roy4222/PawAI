# Reactive Stop And Twist Mux

## 5/11 撞牆事件的真正根因

5/11 Go2 在 B5 motion 測試撞到 1.5m 處障礙物。研究文件確認：主因不是 Nav2 看不到 1.5m 障礙物，而是控制權仲裁錯誤。

真實鏈路：

```text
障礙物在 danger zone
  -> reactive_stop 發 /cmd_vel_obstacle = 0
  -> twist_mux obstacle priority 200 勝出
  -> Go2 停住

障礙物移開
  -> 舊 safety_only 在 slow/clear 沉默
  -> 0.5s 後 mux obstacle channel timeout
  -> /cmd_vel_joy 還在 hot publish 0.5m/s
  -> teleop priority 100 勝過 nav priority 10
  -> Go2 衝出去
```

所以真主因是：
- reactive_stop clear/slow 沉默。
- 沒有 release gate，需要重新確認新命令。
- `/cmd_vel_joy` 測試時持續 hot publish。
- danger threshold 舊值 `0.6m` 對 Go2 機鼻太近。

## 4-mode State Machine

權威檔案：

```text
go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py
go2_robot_sdk/go2_robot_sdk/lidar_geometry.py
```

| Mode | 發什麼 | Topic | 用途 | 風險 |
|------|--------|-------|------|------|
| `hold_brake` | 永遠 `0.0` | `/cmd_vel_obstacle` | B5 stop 驗證 / emergency hold | Nav/teleop 都走不了 |
| `progressive` | danger/emergency 發 `0.0`，slow/clear 沉默 | `/cmd_vel_obstacle` | capability 主線，讓 Nav2 接管 | 必須沒有 hot teleop |
| `released` | 不 publish，但 zone 還更新 | none | 操作員釋放給 nav | reactive 不會擋車 |
| `disabled` | 完全 off | none | 關閉 reactive | 無 reactive 防護 |
| `""` | danger `0` / slow `0.45` / clear `0.60` | `/cmd_vel` | standalone fallback | 不可和 Nav2 同跑 |

`safety_only=true` 只作 backwards compatibility，會 promote 成 `hold_brake`。新文件和新腳本應直接用 `mode`。

## 現行安全參數

| 參數 | 值 | 說明 |
|------|----|------|
| `danger_distance_m` | `1.1` | 5/11 後從 0.6 放大 |
| `slow_distance_m` | `1.7` | 5/11 後從 1.0 放大 |
| `front_arc_deg` | `30` | 前方 ±30 度扇形，runtime 不能 param set 改 |
| `front_offset_rad` | `3.14159` | v8 LiDAR mount yaw=pi 必填 |
| `clear_debounce_frames` | `5` | danger 退出需要連續非 danger 幀 |
| `lidar_timeout_s` | `1.0` | LiDAR 中斷進 emergency |

注意：
- `front_arc_deg`、`front_offset_rad`、threshold 目前不是完整 runtime mutable；要穩定變更應重啟 node。
- `front_offset_rad` 不等同 TF yaw，但 v8 現況兩個都要 pi。

## Mode 行為圖

```text
zone = danger / emergency
  hold_brake  -> publish 0
  progressive -> publish 0
  released    -> silent
  disabled    -> silent
  standalone  -> publish 0

zone = slow
  hold_brake  -> publish 0
  progressive -> silent
  released    -> silent
  disabled    -> silent
  standalone  -> publish slow_speed

zone = clear
  hold_brake  -> publish 0
  progressive -> silent
  released    -> silent
  disabled    -> silent
  standalone  -> publish normal_speed
```

## Capability Mode 的安全前提

`scripts/start_nav_capability_demo_tmux.sh` 使用：

```bash
ros2 run go2_robot_sdk reactive_stop_node --ros-args \
  -p mode:=progressive \
  -p front_offset_rad:=3.14159 \
  -p danger_distance_m:=1.1 \
  -p slow_distance_m:=1.7
```

這個 mode 的前提：

```text
teleop:=false
joystick:=false
沒有 /cmd_vel_joy hot publisher
Nav2 final output 已 remap 到 /cmd_vel_nav
twist_mux alive 且 /cmd_vel_obstacle 有 subscriber
```

若違反，clear/slow 後 obstacle channel timeout，mux 會選 teleop 100 而不是 nav2 10。

## Safety Hold Mode

`scripts/start_reactive_stop_safety_hold_tmux.sh` 用於「確定 Go2 不會走」：

```bash
ros2 run go2_robot_sdk reactive_stop_node --ros-args \
  -p mode:=hold_brake \
  -p front_offset_rad:=3.14159 \
  -p danger_distance_m:=1.1 \
  -p slow_distance_m:=1.7
```

驗收：

```bash
ros2 topic hz /cmd_vel_obstacle
ros2 topic echo /cmd_vel_obstacle --once
ros2 topic echo /cmd_vel --once
ros2 topic echo /state/reactive_stop/status --once
ros2 topic info /cmd_vel_obstacle -v
```

期望：
- `/cmd_vel_obstacle.linear.x = 0`
- `/cmd_vel.linear.x = 0`
- `mode=hold_brake`
- `/cmd_vel_obstacle` 有 1 publisher reactive + 1 subscriber twist_mux

## Standalone Fallback

`scripts/start_reactive_stop_tmux.sh` 不走 mux，reactive_stop 直發 `/cmd_vel`：

```text
d < 1.1m       -> /cmd_vel.x = 0.0
1.1m-1.7m      -> /cmd_vel.x = 0.45
d >= 1.7m      -> /cmd_vel.x = 0.60
LiDAR timeout  -> /cmd_vel.x = 0.0
```

它和 Nav2/capability mode 互斥，因為它直接控制 driver。

## 常見誤解

### `/cmd_vel_obstacle` 不是限速器

priority 200 代表它是主動命令。發 `0.2m/s` 不是「限制 Nav2 到 0.2」，而是「命令 Go2 走 0.2」。

### `depth_clear=false` 不會讓已經在跑的 Nav2 停

D435 depth gate 只 publish `/capability/depth_clear`。它不 publish `/cmd_vel`，也不 call `/nav/pause`。實際停車主線仍是 RPLIDAR reactive_stop。

### `hold_brake` 不是 release gate

`hold_brake` 是 permanent brake。要釋放：

```bash
ros2 param set /reactive_stop_node mode released
pkill -f teleop_twist_joy
pkill -f teleop_twist_keyboard
# 然後重新送 nav goal
```

### `Damp` 不是移動中急停

移動中的 stop 不要用 `Damp api_id=1001`。急停走 `emergency_stop.py engage` 和 `StopMove api_id=1003`，topic 必須是 `rt/api/sport/request`。
