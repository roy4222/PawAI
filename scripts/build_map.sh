#!/usr/bin/env bash
# scripts/build_map.sh — SLAM 建圖助手 (Gate P0-B)
# Usage: bash scripts/build_map.sh [map_name]
# Example: bash scripts/build_map.sh home_living_room
#
# 拓撲（v3 — 4/29 修正）：
#   Cartographer pure scan-matching（**不啟 Go2 driver、無外部 odom**）
#   + RPLIDAR (/scan_rplidar) + base_link→laser static TF + foxglove_bridge
# 詳見 scripts/start_lidar_slam_tmux.sh

set -euo pipefail

MAP_NAME="${1:-home_living_room}"
MAP_DIR="/home/jetson/maps"
OUTPUT_PATH="${MAP_DIR}/${MAP_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$MAP_DIR"

echo "=== SLAM 建圖 — ${MAP_NAME} ==="
echo ""
echo "本腳本會啟 5-window tmux session 'lidar-slam'（pure scan-matching，無 Go2 driver）:"
echo "  tf          static_transform_publisher base_link → laser (x=-0.035, y=0, z=0.15, yaw=-1.5708)"
echo "  sllidar     RPLIDAR → /scan_rplidar 10.4Hz"
echo "  carto       cartographer_node (pure scan-matching，自 own odom→base_link TF)"
echo "  carto_grid  cartographer_occupancy_grid_node (發 /map from /submap_list)"
echo "  fox         foxglove_bridge port 8765"
echo ""
echo "操作步驟:"
echo "  1. 啟動後等 ~10s，5 個 window 全部就緒"
echo "  2. Foxglove (ws://JETSON_IP:8765) 訂閱 /map /scan_rplidar /tf"
echo "  3. 跑 sanity check（見 start_lidar_slam_tmux.sh 結尾提示）"
echo "  4. Unitree 遙控器走 Go2 慢速繞客廳一圈（≤0.15 m/s, 30-60s, 含閉環回原點）"
echo "     注意：scan-matching 對速轉 / 動態障礙物入鏡敏感，請穩走"
echo "  5. 另開 terminal 存圖（cartographer 三步驟順序很重要）:"
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
echo "  6. 產出 ${OUTPUT_PATH}.pgm + ${OUTPUT_PATH}.yaml + ${OUTPUT_PATH}.pbstream"
echo "  7. 結束 session: tmux kill-session -t lidar-slam"
echo ""
read -p "確認 RPLIDAR USB 已接 + Go2 開機 + 在 192.168.123.161 reachable，按 Enter 啟動..."

bash "${SCRIPT_DIR}/start_lidar_slam_tmux.sh"
