#!/usr/bin/env bash
# scripts/start_nav2_demo_tmux.sh
# Gate P0-C + P0-D 第一版：cartographer pure-localization + Nav2 single-goal navigation
#
# 拓撲：
#   tf            base_link → laser static TF
#   sllidar       RPLIDAR /scan_rplidar
#   driver        Go2 driver (env GO2_PUBLISH_ODOM_TF=0 跳 odom TF 給 cartographer own)
#   carto_loc     cartographer pure-localization 載 .pbstream
#   carto_grid    occupancy_grid_node 發 /map
#   nav2          nav2_bringup/navigation_launch.py（無 amcl/map_server）
#   fox           foxglove_bridge port 8765
#
# 前提：
#   - 已 colcon build go2_robot_sdk（含 patch 後的 ros2_publisher.py）
#   - /home/jetson/maps/home_living_room.pbstream 存在
#   - cartographer_lidar_localize.lua 已 sync 到 ~/elder_and_dog/go2_robot_sdk/config/
#   - nav2_params.yaml 已含 P0 改動（controller 10Hz、max_vel_x 0.15、xy_tol 0.30、scan_rplidar、behavior []）
set -euo pipefail

SESSION="nav2-demo"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
CARTO_DIR="$HOME/elder_and_dog/go2_robot_sdk/config"
PBSTREAM="/home/jetson/maps/home_living_room.pbstream"
NAV2_PARAMS="$HOME/elder_and_dog/go2_robot_sdk/config/nav2_params.yaml"

echo "=== Nav2 Demo Session ==="
tmux kill-session -t "$SESSION" 2>/dev/null || true
ros2 daemon stop 2>/dev/null || true
sleep 1
ros2 daemon start 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

# Sanity 前置檢查
if [ ! -f "$PBSTREAM" ]; then
  echo "ERROR: $PBSTREAM 不存在，請先建圖" >&2
  exit 1
fi
if [ ! -f "$CARTO_DIR/cartographer_lidar_localize.lua" ]; then
  echo "ERROR: $CARTO_DIR/cartographer_lidar_localize.lua 不存在" >&2
  exit 1
fi
if [ ! -f "$NAV2_PARAMS" ]; then
  echo "ERROR: $NAV2_PARAMS 不存在" >&2
  exit 1
fi

echo "[1/7] static TF base_link → laser (z=0.10)"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x -0.035 --y 0 --z 0.15 --yaw -1.5708 --frame-id base_link --child-frame-id laser" Enter
sleep 3

echo "[2/7] RPLIDAR (Standard mode, remap /scan_rplidar)"
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 4

echo "[3/7] Go2 driver (GO2_PUBLISH_ODOM_TF=0, no launch.py to skip pcl2ls)"
tmux new-window -t "$SESSION" -n driver
tmux send-keys -t "$SESSION:driver" "$ROS_SETUP && export ROBOT_IP=$ROBOT_IP GO2_PUBLISH_ODOM_TF=0 && ros2 run go2_robot_sdk go2_driver_node --ros-args -p robot_ip:=$ROBOT_IP -p conn_type:=webrtc -p enable_lidar:=false -p decode_lidar:=false -p publish_raw_voxel:=false -p minimal_state_topics:=true -p enable_video:=false" Enter
echo "  Waiting 8s for WebRTC ICE handshake..."
sleep 8

echo "[4/7] cartographer pure-localization (load .pbstream)"
tmux new-window -t "$SESSION" -n carto_loc
tmux send-keys -t "$SESSION:carto_loc" "$ROS_SETUP && ros2 run cartographer_ros cartographer_node -configuration_directory $CARTO_DIR -configuration_basename cartographer_lidar_localize.lua -load_state_filename $PBSTREAM --ros-args -r scan:=/scan_rplidar" Enter
echo "  Waiting 6s for pbstream deserialize + first scan-match..."
sleep 6

echo "[5/7] cartographer_occupancy_grid_node (publishes /map)"
tmux new-window -t "$SESSION" -n carto_grid
tmux send-keys -t "$SESSION:carto_grid" "$ROS_SETUP && ros2 run cartographer_ros cartographer_occupancy_grid_node -resolution 0.05 -publish_period_sec 1.0" Enter
sleep 3

echo "[6/7] Nav2 navigation_launch.py (無 amcl/map_server)"
tmux new-window -t "$SESSION" -n nav2
tmux send-keys -t "$SESSION:nav2" "$ROS_SETUP && ros2 launch nav2_bringup navigation_launch.py params_file:=$NAV2_PARAMS use_sim_time:=false autostart:=true" Enter
echo "  Waiting 12s for Nav2 lifecycle activation..."
sleep 12

echo "[7/7] foxglove_bridge"
tmux new-window -t "$SESSION" -n fox
tmux send-keys -t "$SESSION:fox" "$ROS_SETUP && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter
sleep 2

echo ""
echo "=== Started ==="
JETSON_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "JETSON_IP")
echo "Foxglove: ws://$JETSON_IP:8765"
echo ""
echo "Sanity:"
echo "  ros2 topic hz /scan_rplidar       # ~10 Hz"
echo "  ros2 topic hz /map                # ~1 Hz"
echo "  ros2 topic hz /odom               # ~18 Hz (driver topic 仍發，TF 沒發)"
echo "  ros2 run tf2_ros tf2_echo map base_link        # cartographer own"
echo "  ros2 topic info /tf | head -5     # 確認只有 cartographer + sllidar 在發 TF"
echo "  ros2 lifecycle list /controller_server          # 期望 active"
echo "  ros2 topic info /cmd_vel -v       # 期望 driver 是 Subscriber"
echo ""
echo "0.5m goal 測試："
echo "  ros2 topic pub --once /goal_pose geometry_msgs/PoseStamped \\"
echo "    \"{header: {frame_id: 'map'}, pose: {position: {x: 0.5, y: 0.0}, orientation: {w: 1.0}}}\""
echo ""
echo "Foxglove: 3D panel + Publish 工具 → topic /goal_pose, schema PoseStamped, frame map"
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
