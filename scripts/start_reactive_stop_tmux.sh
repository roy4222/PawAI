#!/usr/bin/env bash
# scripts/start_reactive_stop_tmux.sh
# 反應式停障 fallback (5/13 Demo backup)
#
# 拓撲（4 windows，與 nav2-amcl 互斥使用）：
#   tf            base_link → laser static TF
#   sllidar       RPLIDAR /scan_rplidar
#   driver        Go2 driver（無 GO2_PUBLISH_ODOM_TF env）
#   reactive      reactive_stop_node 訂 /scan_rplidar → /cmd_vel @ 10Hz
#
# 使用情境：
#   - Nav2 demo 失敗時的 fallback
#   - 純展示 RPLIDAR 雷達避障基礎防護
#
# 行為：
#   - 前方 ±30°、d < 0.6m → cmd_vel = 0（stop）
#   - 0.6m ≤ d < 1.0m → cmd_vel = 0.45（slow）
#   - d ≥ 1.0m → cmd_vel = 0.60（normal）
#   - LiDAR 中斷 > 1s → emergency stop
set -euo pipefail

SESSION="reactive-stop"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"

echo "=== Reactive Stop Demo Session ==="
tmux kill-session -t "$SESSION" 2>/dev/null || true
ros2 daemon stop 2>/dev/null || true
sleep 1
ros2 daemon start 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

echo "[1/4] static TF base_link → laser (z=0.10)"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x 0 --y 0 --z 0.10 --frame-id base_link --child-frame-id laser" Enter
sleep 3

echo "[2/4] RPLIDAR (Standard mode, /scan_rplidar)"
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 4

echo "[3/4] Go2 driver"
tmux new-window -t "$SESSION" -n driver
tmux send-keys -t "$SESSION:driver" "$ROS_SETUP && export ROBOT_IP=$ROBOT_IP && ros2 run go2_robot_sdk go2_driver_node --ros-args -p robot_ip:=$ROBOT_IP -p conn_type:=webrtc -p enable_lidar:=false -p decode_lidar:=false -p publish_raw_voxel:=false -p minimal_state_topics:=true -p enable_video:=false" Enter
echo "  Waiting 8s for WebRTC handshake..."
sleep 8

echo "[4/4] reactive_stop_node (standalone fallback — publishes /cmd_vel directly, NOT through mux)"
# 此 script 是 nav2-amcl 失敗時的 standalone fallback，不啟 twist_mux 也不啟 nav_capability。
# reactive_stop_node 預設 cmd_vel_topic=/cmd_vel_obstacle (跟 nav stack 同跑時用 mux)，
# 但 standalone 模式下 driver 訂 /cmd_vel，必須覆寫 param 讓 reactive 直發 /cmd_vel。
tmux new-window -t "$SESSION" -n reactive
tmux send-keys -t "$SESSION:reactive" "$ROS_SETUP && ros2 run go2_robot_sdk reactive_stop_node --ros-args -p cmd_vel_topic:=/cmd_vel" Enter
sleep 2

echo ""
echo "=== Started ==="
echo ""
echo "Sanity:"
echo "  ros2 topic hz /scan_rplidar          # ~10 Hz (sllidar)"
echo "  ros2 topic hz /cmd_vel               # ~10 Hz (reactive_stop_node)"
echo "  ros2 topic echo /cmd_vel --once      # check linear.x value"
echo ""
echo "驗收 4 場景:"
echo "  1. Go2 站客廳前方 2m 空地 → cmd_vel.linear.x ≈ 0.60"
echo "  2. 人走到 Go2 前方 80cm → cmd_vel.linear.x = 0"
echo "  3. 人退開到 1.5m → cmd_vel.linear.x ≈ 0.60"
echo "  4. 拔 RPLIDAR USB → 1s 內 cmd_vel.linear.x = 0"
echo ""
echo "Demo 中關閉 reactive (留 stand mode):"
echo "  ros2 param set /reactive_stop_node enable false"
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
