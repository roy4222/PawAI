#!/usr/bin/env bash
# scripts/start_nav2_amcl_demo_tmux.sh (v3.7)
# Gate P0-D: AMCL + Go2 odom + RPLIDAR + Nav2 single-goal navigation
#
# 拓撲（**v3.7 切 AMCL，不用 cartographer pure-localization**）：
#   tf            base_link → laser static TF
#   sllidar       RPLIDAR /scan_rplidar
#   driver        Go2 driver (恢復發 odom→base_link TF，無 GO2_PUBLISH_ODOM_TF env)
#   nav2          nav2_bringup/bringup_launch.py（含 amcl + map_server + nav2 全套）
#   fox           foxglove_bridge port 8765
#
# 前提：
#   - Step 0 已確認 cmd_vel MIN_X = 0.50（4/25 19:55 calibration）
#   - /home/jetson/maps/home_living_room_v5.{yaml,pgm} 存在
#   - nav2_params.yaml 含 v3.7 改動（AMCL scan_topic /scan_rplidar、alpha 0.4、initial_pose false）
#
# 操作流程：
#   1. bash 此 script 啟 5 windows
#   2. 等 ~30s nav2 lifecycle 全 active
#   3. Foxglove Publish 工具點 /initialpose 設 Go2 真實位置 + 朝向
#   4. AMCL 收斂後（covariance 變小）發 /goal_pose
set -euo pipefail

SESSION="nav2-amcl"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
MAP_YAML="/home/jetson/maps/home_living_room_v5.yaml"
NAV2_PARAMS="$HOME/elder_and_dog/go2_robot_sdk/config/nav2_params.yaml"

echo "=== Nav2 AMCL Demo Session (v3.7) ==="
tmux kill-session -t "$SESSION" 2>/dev/null || true
ros2 daemon stop 2>/dev/null || true
sleep 1
ros2 daemon start 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

# 前置檢查
if [ ! -f "$MAP_YAML" ]; then
  echo "ERROR: $MAP_YAML 不存在" >&2
  exit 1
fi
if [ ! -f "$NAV2_PARAMS" ]; then
  echo "ERROR: $NAV2_PARAMS 不存在" >&2
  exit 1
fi

echo "[1/5] static TF base_link → laser (z=0.10)"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x -0.035 --y 0 --z 0.15 --yaw -1.5708 --frame-id base_link --child-frame-id laser" Enter
sleep 3

echo "[2/5] RPLIDAR (Standard mode, /scan_rplidar)"
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 4

echo "[3/5] Go2 driver (恢復發 odom TF)"
tmux new-window -t "$SESSION" -n driver
tmux send-keys -t "$SESSION:driver" "$ROS_SETUP && export ROBOT_IP=$ROBOT_IP && ros2 run go2_robot_sdk go2_driver_node --ros-args -p robot_ip:=$ROBOT_IP -p conn_type:=webrtc -p enable_lidar:=false -p decode_lidar:=false -p publish_raw_voxel:=false -p minimal_state_topics:=true -p enable_video:=false" Enter
echo "  Waiting 8s for WebRTC handshake..."
sleep 8

echo "[4/5] Nav2 bringup (amcl + map_server + navigation)"
tmux new-window -t "$SESSION" -n nav2
tmux send-keys -t "$SESSION:nav2" "$ROS_SETUP && ros2 launch nav2_bringup bringup_launch.py map:=$MAP_YAML params_file:=$NAV2_PARAMS use_sim_time:=false slam:=False autostart:=true" Enter
echo "  Waiting 15s for nav2 lifecycle activation..."
sleep 15

echo "[5/5] foxglove_bridge"
tmux new-window -t "$SESSION" -n fox
tmux send-keys -t "$SESSION:fox" "$ROS_SETUP && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter
sleep 2

echo ""
echo "=== Started ==="
JETSON_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "JETSON_IP")
echo "Foxglove: ws://$JETSON_IP:8765"
echo ""
echo "Sanity:"
echo "  ros2 lifecycle get /amcl                # active"
echo "  ros2 lifecycle get /map_server          # active"
echo "  ros2 lifecycle get /controller_server   # active"
echo "  ros2 run tf2_ros tf2_echo odom base_link  # Go2 driver 發"
echo "  ros2 run tf2_ros tf2_echo map odom        # AMCL 發"
echo ""
echo "Foxglove 設 initial pose:"
echo "  - 加 3D panel + Map panel"
echo "  - Publish 工具：topic /initialpose, schema PoseWithCovarianceStamped, frame map"
echo "  - 在地圖上點 Go2 真實位置 + 拖曳設朝向"
echo ""
echo "發 0.5m goal:"
echo "  ros2 topic pub --once /goal_pose geometry_msgs/PoseStamped \\"
echo "    \"{header: {frame_id: 'map'}, pose: {position: {x: 0.5, y: 0.0}, orientation: {w: 1.0}}}\""
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
