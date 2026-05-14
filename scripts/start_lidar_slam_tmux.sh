#!/usr/bin/env bash
# scripts/start_lidar_slam_tmux.sh
# 一鍵啟動 RPLIDAR + Cartographer pure scan-matching 建圖環境（Gate P0-B）
#
# 拓撲：
#   static TF       → base_link → laser (x=0.175, y=0, z=0.18, yaw=3.14159)
#   sllidar         → /scan_rplidar 10.4Hz（避開 Go2 內建 /scan）
#   cartographer    → pure scan-matching，無外部 odom
#   foxglove_bridge → ws://JETSON_IP:8765 可視化
#
# 注意：本建圖 stack 不啟 Go2 driver / Nav2 / reactive / mux。
set -euo pipefail

SESSION="lidar-slam"
# 注意：sllidar_ros2 不在 apt，裝在 ~/rplidar_ws/，必須 source 該 overlay
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
CARTO_CONFIG_DIR="$HOME/elder_and_dog/go2_robot_sdk/config"
CARTO_CONFIG_BASENAME="cartographer_lidar.lua"

echo "=== Lidar SLAM Mapping Session ==="
echo "Killing any prior session + clearing DDS daemon..."
tmux kill-session -t "$SESSION" 2>/dev/null || true
ros2 daemon stop 2>/dev/null || true
sleep 1
ros2 daemon start 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

echo "[1/5] Publishing static TF base_link -> laser (x=0.175, y=0, z=0.18, yaw=3.14159) FIRST..."
echo "       v3: 不啟 Go2 driver，cartographer pure scan-matching 自己 own odom→base_link TF"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x 0.175 --y 0 --z 0.18 --yaw 3.14159 --frame-id base_link --child-frame-id laser" Enter
echo "  Waiting 3s for /tf_static TRANSIENT_LOCAL to settle in DDS..."
sleep 3

echo "[2/5] Starting RPLIDAR (sllidar Standard mode, remap /scan_rplidar)..."
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
echo "  Waiting 5s for scan stream to stabilise (TF + scan both ready before slam)..."
sleep 5

echo "[3/5] Starting cartographer_node (pure scan-matching, 無外部 odom) — TF + scan 已 ready..."
tmux new-window -t "$SESSION" -n carto
tmux send-keys -t "$SESSION:carto" "$ROS_SETUP && ros2 run cartographer_ros cartographer_node -configuration_directory $CARTO_CONFIG_DIR -configuration_basename $CARTO_CONFIG_BASENAME --ros-args -r scan:=/scan_rplidar" Enter
sleep 4

echo "[4/5] Starting cartographer_occupancy_grid_node (publishes /map from submaps)..."
tmux new-window -t "$SESSION" -n carto_grid
tmux send-keys -t "$SESSION:carto_grid" "$ROS_SETUP && ros2 run cartographer_ros cartographer_occupancy_grid_node -resolution 0.05 -publish_period_sec 1.0" Enter
sleep 2

echo "[5/5] Starting foxglove_bridge..."
tmux new-window -t "$SESSION" -n fox
tmux send-keys -t "$SESSION:fox" "$ROS_SETUP && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter
sleep 2

echo ""
echo "=== All started ==="
JETSON_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "JETSON_IP")
echo "Foxglove: ws://$JETSON_IP:8765"
echo ""
echo "Sanity check (run in another terminal):"
echo "  ros2 topic hz /scan_rplidar      # 期望 ≈ 10.4 Hz"
echo "  ros2 topic list | grep scan      # 應只見 /scan_rplidar，無 /scan"
echo "  ros2 run tf2_tools view_frames   # 確認 map / odom / base_link / laser TF tree"
echo "  ros2 run tf2_ros tf2_echo base_link laser"
echo ""
echo "走客廳繞一圈後 save map（cartographer 三步驟，順序很重要）:"
echo "  # 1. finish trajectory（觸發最終 loop closure）"
echo "  ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory \\"
echo "    \"{trajectory_id: 0}\""
echo ""
echo "  # 2. 序列化 internal state 到 pbstream（保險）"
echo "  ros2 service call /write_state cartographer_ros_msgs/srv/WriteState \\"
echo "    \"{filename: '/home/jetson/maps/home_living_room.pbstream', include_unfinished_submaps: true}\""
echo ""
echo "  # 3. 從 /map topic 抓 occupancy grid → pgm + yaml"
echo "  ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/home_living_room \\"
echo "    --ros-args -p map_subscribe_transient_local:=true"
echo ""
echo "To attach: tmux attach -t $SESSION"
echo "To kill:   tmux kill-session -t $SESSION"
