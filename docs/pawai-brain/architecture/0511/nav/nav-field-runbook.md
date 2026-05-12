# Navigation Field Runbook

## 到學校第一件事

先不要直接跑長距離 nav。依序做：

1. 確認同步與 build。
2. fresh restart capability stack。
3. 立即測 F7：`goto_relative` 是否會產生 `/cmd_vel_nav`。
4. 確認 mux topology。
5. 確認 reactive_stop progressive stop。
6. 再測 0.3m / 0.5m 短距離。

## 啟動前 Preflight

在 Jetson：

```bash
cd /home/jetson/elder_and_dog
source /opt/ros/humble/setup.zsh
source ~/rplidar_ws/install/setup.zsh
source install/setup.zsh
```

檢查硬體：

```bash
test -e /dev/rplidar
ping -c 2 192.168.123.161
ls /home/jetson/maps/home_living_room_v8.yaml
```

檢查不要有殘留 publisher：

```bash
ros2 topic info /cmd_vel_joy
ros2 node list | grep -E 'teleop|joy|reactive|twist_mux|go2_driver|nav2|amcl'
```

若在 capability mode，`/cmd_vel_joy` 應該沒有 hot publisher。

## 主線啟動：Capability Mode

```bash
ROBOT_IP=192.168.123.161 \
MAP=/home/jetson/maps/home_living_room_v8.yaml \
bash scripts/start_nav_capability_demo_tmux.sh
```

這會啟：

```text
tf
sllidar
d435
robot.launch.py nav2=true teleop=false joystick=false
reactive_stop mode=progressive
nav_capability 6 nodes
pause-enable
foxglove
monitor
```

等 30 秒 lifecycle 起來，再在 Foxglove 設 `/initialpose`。

## Healthcheck

在 monitor window：

```bash
ros2 topic hz /scan_rplidar
ros2 run tf2_ros tf2_echo base_link laser
ros2 run tf2_ros tf2_echo map base_link
ros2 topic echo /amcl_pose --once
ros2 topic echo /capability/nav_ready --once
ros2 topic echo /capability/depth_clear --once
ros2 topic echo /state/reactive_stop/status --once
ros2 topic echo /state/nav/safety --once
```

Mux topology：

```bash
ros2 node list | grep twist_mux
ros2 topic info /cmd_vel_obstacle -v
ros2 topic info /cmd_vel_nav -v
ros2 topic info /cmd_vel_joy -v
ros2 topic echo /cmd_vel --once
```

期望：
- `/cmd_vel_obstacle` 有 reactive publisher 和 twist_mux subscriber。
- `/cmd_vel_nav` 在 nav goal active 時有 publisher。
- `/cmd_vel_joy` 沒有 publisher。
- `/cmd_vel` 是 mux final output。

## F7 Debug：Goal accepted 但不動

5/12 night 的 P0 問題：

```text
/nav/goto_relative accepted
10s no_progress_timeout
/cmd_vel_nav 沒 publisher
/cmd_vel = 0
Go2 完全不動
```

第一輪 fresh stack 測：

```bash
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
  "{distance: 0.3, yaw_offset: 0.0, max_speed: 0.0}"
```

同時看：

```bash
ros2 topic info /cmd_vel_nav -v
ros2 topic hz /cmd_vel_nav
ros2 topic hz /cmd_vel
ros2 action list | grep navigate
ros2 lifecycle get /controller_server
ros2 lifecycle get /planner_server
ros2 lifecycle get /bt_navigator
```

判斷：

| 現象 | 可能原因 | 下一步 |
|------|----------|--------|
| `/cmd_vel_nav` 有 publisher + `/cmd_vel` 仍 0 | mux 或 higher priority input 擋住 | 查 `/cmd_vel_obstacle`, `/cmd_vel_joy`, `/cmd_vel_emergency` |
| `/cmd_vel_nav` 沒 publisher | Nav2 controller/BT 沒出 cmd | 看 Nav2 logs、BT、planner result |
| `/nav/goto_relative` reject | AMCL/odom gate 未過 | 查 `/odom`, `/amcl_pose`, covariance |
| `/cmd_vel_nav` 有速度但 Go2 不走 | driver/WebRTC 或 Go2 sport threshold | 查 `/cmd_vel`, driver logs, min_vel_x |

如果 fresh stack 成功，代表 5/12 可能是 stale/DDS/長時間 runtime 問題。現場先採用「demo 前重啟 stack」策略，再補 watchdog。

## 短距離 Nav 驗收

先 0.3m：

```bash
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
  "{distance: 0.3, yaw_offset: 0.0, max_speed: 0.0}"
```

再 0.5m：

```bash
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
  "{distance: 0.5, yaw_offset: 0.0, max_speed: 0.0}"
```

不要一開始測 1.0m。5/12 night 1.0m 曾出現 F7/no_progress。

## Reactive Stop 驗收

看 status：

```bash
ros2 topic echo /state/reactive_stop/status
```

把障礙物放到 Go2 前方：

```text
< 1.1m     -> zone=danger, /cmd_vel_obstacle should publish 0
1.1-1.7m  -> zone=slow, progressive mode silent
> 1.7m    -> zone=clear, progressive mode silent
```

在 capability mode，真正 stop 來自 danger/emergency 時 obstacle priority 200 發 0。slow/clear 應讓 Nav2 接管。

## Safety Hold 驗收

如果只是要確認「停得住」：

```bash
bash scripts/start_reactive_stop_safety_hold_tmux.sh
```

期望不管障礙在何處：

```bash
ros2 topic echo /cmd_vel_obstacle --once
ros2 topic echo /cmd_vel --once
```

都是 `linear.x = 0`。

## Standalone Fallback

Nav2 不穩時，用：

```bash
bash scripts/start_reactive_stop_tmux.sh
```

這不是 Nav2。它是直接 reactive forward control：

```text
clear -> 0.60
slow  -> 0.45
danger/emergency -> 0
```

不要和 capability/amcl mode 同跑。

## Mapping

建圖：

```bash
bash scripts/start_lidar_slam_tmux.sh
```

走完場地後依序：

```bash
ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory \
  "{trajectory_id: 0}"

ros2 service call /write_state cartographer_ros_msgs/srv/WriteState \
  "{filename: '/home/jetson/maps/classroom.pbstream', include_unfinished_submaps: true}"

ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/classroom \
  --ros-args -p map_subscribe_transient_local:=true
```

## 不要做

- 不要直接跑 detour script。
- 不要在 capability mode 留 `/cmd_vel_joy` hot publisher。
- 不要把 `safety_only=true` 當 nav demo 設定；它會變 hold_brake。
- 不要用 `Damp` 當移動中急停。
- 不要只設 `teleop:=false` 卻忘了 `joystick:=false`。
- 不要直接依賴 D435 `depth_clear=false` 讓 Go2 停；它只是 gate。
