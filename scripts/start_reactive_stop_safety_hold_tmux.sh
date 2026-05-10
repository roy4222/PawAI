#!/usr/bin/env bash
# scripts/start_reactive_stop_safety_hold_tmux.sh
# B5 safety hold mode — 純停車驗證用，不允許 nav 驅動 Go2
#
# 拓撲（4 windows，與 nav2-amcl / nav_capability 互斥）：
#   tf            base_link → laser static TF
#   sllidar       RPLIDAR /scan_rplidar
#   driver        Go2 driver
#   reactive      reactive_stop_node mode=hold_brake → /cmd_vel_obstacle @ 10Hz
#
# Mode = hold_brake（5/11 night 設計）：
#   - **永遠 publish 0** 到 /cmd_vel_obstacle（priority 200）
#   - mux 永遠用 obstacle channel 蓋掉 teleop / nav
#   - 即使障礙物清掉，也不會自動恢復前進
#   - 操作員必須主動切 mode（ros2 param set /reactive_stop_node mode released）
#     才能讓 nav / teleop 接管
#
# 使用情境：
#   - B5 stop verification（驗證 reactive_stop 鎖死真的鎖得住）
#   - Demo emergency hold
#   - 想要「絕對安全的站立狀態」時的 default
#
# ⚠️ 跟 start_nav_capability_demo_tmux.sh 不能同跑（cmd_vel_obstacle 雙 publisher 衝突）
# ⚠️ 跟 start_reactive_stop_tmux.sh 也不能同跑（standalone 直發 /cmd_vel，跟 hold_brake 直接搶 driver）
#
# Threshold（5/11 B0.3 enlarged）：danger=1.1m / slow=1.7m（LiDAR 視距）
#
# Audit：docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0
set -euo pipefail

SESSION="reactive-stop-hold"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"

echo "=== reactive_stop hold_brake mode session ==="
tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "[1/4] base_link → laser static TF (yaw=π for v8 mount)"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" \
    "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x 0.175 --y 0 --z 0.18 --yaw 3.14159 --frame-id base_link --child-frame-id laser" Enter

echo "[2/4] sllidar (RPLIDAR → /scan_rplidar)"
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" \
    "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 2

echo "[3/4] go2_driver_node (minimal — no sport mode handshake)"
tmux new-window -t "$SESSION" -n driver
tmux send-keys -t "$SESSION:driver" \
    "$ROS_SETUP && export ROBOT_IP=$ROBOT_IP && ros2 run go2_robot_sdk go2_driver_node --ros-args -p robot_ip:=$ROBOT_IP -p conn_type:=webrtc -p enable_lidar:=false -p decode_lidar:=false -p publish_raw_voxel:=false -p minimal_state_topics:=true -p enable_video:=false" Enter
echo "  Waiting 8s for WebRTC handshake..."
sleep 8

echo "[4/4] reactive_stop_node (mode=hold_brake → /cmd_vel_obstacle, ALWAYS 0)"
# hold_brake: ALWAYS publishes 0 regardless of zone — permanent brake.
# This holds mux priority 200 forever, preventing 0.5s timeout from handing
# /cmd_vel back to anyone. Nav / teleop are LOCKED OUT until operator switches
# mode via:  ros2 param set /reactive_stop_node mode released
tmux new-window -t "$SESSION" -n reactive
tmux send-keys -t "$SESSION:reactive" \
    "$ROS_SETUP && ros2 run go2_robot_sdk reactive_stop_node --ros-args -p mode:=hold_brake -p front_offset_rad:=3.14159 -p danger_distance_m:=1.1 -p slow_distance_m:=1.7" Enter
sleep 2

echo ""
echo "=== Started — mode=hold_brake, Go2 鎖死狀態 ==="
echo ""
echo "Sanity:"
echo "  ros2 topic hz /scan_rplidar             # ~10 Hz (sllidar)"
echo "  ros2 topic hz /cmd_vel_obstacle         # ~10 Hz (reactive @ hold_brake)"
echo "  ros2 topic echo /cmd_vel_obstacle --once  # linear.x = 0 always"
echo "  ros2 topic echo /state/reactive_stop/status --once  # mode=hold_brake"
echo ""
echo "B5 safety verification 驗收 4 場景（mode=hold_brake）:"
echo "  1. 物體放 Go2 前 1.0m（danger zone）→ /cmd_vel_obstacle.x = 0"
echo "  2. 物體放 Go2 前 1.5m（slow zone）  → /cmd_vel_obstacle.x = 0（hold_brake 不放）"
echo "  3. 物體放 Go2 前 2.0m（clear zone） → /cmd_vel_obstacle.x = 0（hold_brake 不放）"
echo "  4. 拔 RPLIDAR USB                   → /cmd_vel_obstacle.x = 0（emergency）"
echo ""
echo "釋放給 nav 接管："
echo "  ros2 param set /reactive_stop_node mode released  # reactive 安靜，但 zone 仍更新"
echo "  ros2 param set /reactive_stop_node mode disabled  # 完全 off"
echo ""
echo "切回 hold_brake："
echo "  ros2 param set /reactive_stop_node mode hold_brake"
echo ""
echo "停止 session:"
echo "  tmux kill-session -t $SESSION"
echo ""
