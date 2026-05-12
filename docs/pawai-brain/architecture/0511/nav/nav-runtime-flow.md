# Navigation Runtime Flow

## 一句話

目前導航避障主線是：

```text
RPLIDAR 建圖/定位/避障 + AMCL/Nav2 規劃 + reactive_stop 止損 + twist_mux 仲裁 + Go2 driver
```

D435 目前不是 Nav2 costmap 主線，只作 `depth_clear` safety gate。

## 全架構圖

```text
Sensors
  ├─ RPLIDAR A2M12
  │    └─ /scan_rplidar
  │         ├─ Cartographer mapping
  │         ├─ AMCL localization
  │         ├─ Nav2 local/global costmap
  │         ├─ reactive_stop_node
  │         └─ state_broadcaster lidar watchdog
  │
  ├─ D435 aligned depth
  │    └─ /camera/camera/aligned_depth_to_color/image_raw
  │         └─ depth_safety_node
  │              └─ /capability/depth_clear
  │
  └─ Go2 driver odom
       ├─ /odom
       └─ TF odom -> base_link

Localization / Planning
  ├─ static TF base_link -> laser
  ├─ AMCL
  │    ├─ /amcl_pose
  │    └─ TF map -> odom
  └─ Nav2
       ├─ /navigate_to_pose
       ├─ controller_server cmd_vel
       ├─ velocity_smoother
       └─ /cmd_vel_nav

Safety / Arbitration
  ├─ reactive_stop_node
  │    ├─ /cmd_vel_obstacle
  │    └─ /state/reactive_stop/status
  ├─ emergency_stop.py
  │    └─ /cmd_vel_emergency
  ├─ teleop
  │    └─ /cmd_vel_joy
  └─ twist_mux
       ├─ emergency 255
       ├─ obstacle 200
       ├─ teleop 100
       └─ nav2 10
       └─ /cmd_vel -> go2_driver

Capability Layer
  ├─ nav_action_server_node
  │    ├─ /nav/goto_relative
  │    └─ /nav/goto_named
  ├─ route_runner_node
  │    ├─ /nav/run_route
  │    └─ /nav/pause|resume|cancel
  ├─ capability_publisher_node
  │    └─ /capability/nav_ready
  └─ state_broadcaster_node
       ├─ /state/nav/heartbeat
       ├─ /state/nav/status
       └─ /state/nav/safety
```

## TF Tree

Runtime 主要 TF：

```text
map
  └─ odom              AMCL publishes map -> odom
      └─ base_link     Go2 driver publishes odom -> base_link
          └─ laser     static_transform_publisher
```

目前 RPLIDAR static TF：

```bash
ros2 run tf2_ros static_transform_publisher \
  --x 0.175 --y 0 --z 0.18 --yaw 3.14159 \
  --frame-id base_link --child-frame-id laser
```

注意：
- v8 mount 是 yaw=pi。
- `reactive_stop_node` 也要設 `front_offset_rad:=3.14159`。
- TF yaw 和 `front_offset_rad` 是兩個不同層面的補正，現況兩個都要填 pi。

## Command Velocity Chain

```text
Nav2 controller_server
  -> cmd_vel_unsmoothed
  -> velocity_smoother
  -> /cmd_vel_nav

reactive_stop_node
  -> /cmd_vel_obstacle

teleop_twist_joy
  -> /cmd_vel_joy

emergency_stop.py
  -> /cmd_vel_emergency

twist_mux
  -> /cmd_vel
  -> go2_driver_node
  -> RobotControlService
  -> WebRTC Sport Move / StopMove
```

`nav_capability/launch/navigation_remap.launch.py` 是關鍵：它把 Nav2 final output remap 成 `/cmd_vel_nav`，使 Nav2 不會直接打 `/cmd_vel`，而是交給 `twist_mux` 仲裁。

## twist_mux Priority

來源：

```text
go2_robot_sdk/config/twist_mux.yaml
```

| Input | Topic | Priority | Timeout |
|------|-------|----------|---------|
| emergency | `/cmd_vel_emergency` | 255 | 0.5s |
| obstacle | `/cmd_vel_obstacle` | 200 | 0.5s |
| teleop | `/cmd_vel_joy` | 100 | 0.5s |
| nav2 | `/cmd_vel_nav` | 10 | 0.5s |

結論：
- obstacle 不是「限速器」，是高優先權主動命令通道。
- `/cmd_vel_obstacle` 發正速度會主動命令 Go2 前進，不是限制 Nav2。
- progressive mode 依賴 obstacle channel 在 clear/slow 沉默後 timeout，讓 nav2 priority 10 接管。
- 若 teleop 還在 hot publish，teleop 100 會贏 nav2 10。

## 主要啟動組合

| Mode | Script | 啟動內容 | 用途 |
|------|--------|----------|------|
| mapping | `scripts/start_lidar_slam_tmux.sh` | TF + RPLIDAR + Cartographer + Foxglove | 建圖，不啟 driver/Nav2/reactive |
| amcl | `scripts/start_nav2_amcl_demo_tmux.sh` | TF + RPLIDAR + driver + Nav2 + Foxglove | 基本 AMCL/Nav2 測試 |
| capability | `scripts/start_nav_capability_demo_tmux.sh` | TF + RPLIDAR + D435 + driver/Nav2/mux + reactive progressive + nav_capability | 主 demo / 場測 |
| safety hold | `scripts/start_reactive_stop_safety_hold_tmux.sh` | TF + RPLIDAR + driver/mux + reactive hold_brake | 純停車驗證 |
| fallback | `scripts/start_reactive_stop_tmux.sh` | TF + RPLIDAR + driver + reactive standalone | Nav2 失敗時 fallback |

## Topic Cheat Sheet

| 類型 | Topic |
|------|-------|
| LiDAR | `/scan_rplidar` |
| D435 depth | `/camera/camera/aligned_depth_to_color/image_raw` |
| AMCL | `/amcl_pose` |
| Driver odom | `/odom` |
| Nav2 action | `/navigate_to_pose` |
| PawAI nav actions | `/nav/goto_relative`, `/nav/goto_named`, `/nav/run_route` |
| Nav pause | `/nav/pause`, `/nav/resume`, `/nav/cancel`, `/state/nav/paused` |
| Mux inputs | `/cmd_vel_emergency`, `/cmd_vel_obstacle`, `/cmd_vel_joy`, `/cmd_vel_nav` |
| Final command | `/cmd_vel` |
| Reactive status | `/state/reactive_stop/status` |
| Nav status | `/state/nav/heartbeat`, `/state/nav/status`, `/state/nav/safety` |
| Capability gates | `/capability/nav_ready`, `/capability/depth_clear` |
