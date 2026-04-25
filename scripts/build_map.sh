#!/usr/bin/env bash
# scripts/build_map.sh — SLAM 建圖助手 (Gate P0-B)
# Usage: bash scripts/build_map.sh [map_name]
# Example: bash scripts/build_map.sh home_living_room
#
# 拓撲: Go2 driver minimal (無 pointcloud_to_laserscan) + RPLIDAR (/scan_rplidar)
#       + base_link→laser static TF + slam_toolbox + foxglove_bridge
# 詳見 scripts/start_lidar_slam_tmux.sh

set -euo pipefail

MAP_NAME="${1:-home_living_room}"
MAP_DIR="/home/jetson/maps"
OUTPUT_PATH="${MAP_DIR}/${MAP_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$MAP_DIR"

echo "=== SLAM 建圖 — ${MAP_NAME} ==="
echo ""
echo "本腳本會啟 6-window tmux session 'lidar-slam':"
echo "  go2drv      Go2 driver minimal (只取 /odom + odom→base_link TF)"
echo "  tf          static_transform_publisher base_link → laser (z=0.10)"
echo "  sllidar     RPLIDAR → /scan_rplidar 10Hz"
echo "  carto       cartographer_node (訂 /scan_rplidar + /odom，發 map→odom + /submap_list)"
echo "  carto_grid  cartographer_occupancy_grid_node (發 /map from /submap_list)"
echo "  fox         foxglove_bridge port 8765"
echo ""
echo "操作步驟:"
echo "  1. 啟動後等 ~10s，5 個 window 全部就緒"
echo "  2. Foxglove (ws://JETSON_IP:8765) 訂閱 /map /scan_rplidar /tf /odom"
echo "  3. 跑 sanity check（見另一 terminal 提示）"
echo "  4. 30cm odom 差異測試：ros2 topic echo /odom --field pose.pose.position"
echo "     用 Unitree 遙控器走 30cm，看 x/y 是否即時變化"
echo "  5. 通過後，Unitree 遙控器走 Go2 慢速繞客廳一圈（≤0.15 m/s, 30-60s, 回原點）"
echo "  6. 另開 terminal 存圖（cartographer 三步驟順序很重要）:"
echo ""
echo "     # Step 1: finish trajectory"
echo "     ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory \\"
echo "       \"{trajectory_id: 0}\""
echo ""
echo "     # Step 2: 序列化 pbstream（保險，未來可重 load）"
echo "     ros2 service call /write_state cartographer_ros_msgs/srv/WriteState \\"
echo "       \"{filename: '${OUTPUT_PATH}.pbstream', include_unfinished_submaps: true}\""
echo ""
echo "     # Step 3: 抓 occupancy grid → pgm + yaml"
echo "     ros2 run nav2_map_server map_saver_cli -f ${OUTPUT_PATH} \\"
echo "       --ros-args -p map_subscribe_transient_local:=true"
echo ""
echo "  7. 產出 ${OUTPUT_PATH}.pgm + ${OUTPUT_PATH}.yaml + ${OUTPUT_PATH}.pbstream"
echo "  8. 結束 session: tmux kill-session -t lidar-slam"
echo ""
read -p "確認 RPLIDAR USB 已接 + Go2 開機 + 在 192.168.123.161 reachable，按 Enter 啟動..."

bash "${SCRIPT_DIR}/start_lidar_slam_tmux.sh"
