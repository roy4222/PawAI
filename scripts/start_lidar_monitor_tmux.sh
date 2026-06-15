#!/usr/bin/env bash
# scripts/start_lidar_monitor_tmux.sh
# 6/14 B5 — raw LiDAR monitor「證據窗」（與 brain demo 並存，不啟 nav）
#
# 拓撲（2 windows，session 名 lidarmon）：
#   tf       base_link → laser static TF（x=0.175 y=0 z=0.18 yaw=π；LiDAR 反裝）
#   sllidar  RPLIDAR → /scan_rplidar
#
# 設計界線（pre-6/18 最小整合，default-off）：
#   - 只起 static TF + sllidar，產 /scan_rplidar 當證據 topic。
#   - **絕不**啟 nav2 / amcl / nav_action_server / 第二個 go2_driver。
#   - **絕不**發 motion（無 reactive_stop、無 cmd_vel publisher）。
#   - brain demo（scripts/start_full_demo_tmux.sh）裡的單一 go2_driver 不受影響。
#
# 啟動者：`pawai demo start --with-lidar`（或 PAWAI_DEMO_WITH_LIDAR=1），在 brain
#         demo healthy 後額外 SSH 到 Jetson 跑本腳本。手動跑也可（須先有 ROS env）。
# 清理：  `pawai demo stop` 會 kill lidarmon session + pkill sllidar/static_transform_publisher。
#
# ROS env source 參照 scripts/start_reactive_stop_tmux.sh：
#   /opt/ros/humble + ~/rplidar_ws + ~/elder_and_dog install，皆用 setup.zsh。
set -euo pipefail

SESSION="lidarmon"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
SERIAL_PORT="${RPLIDAR_SERIAL_PORT:-/dev/rplidar}"
SERIAL_BAUD="${RPLIDAR_SERIAL_BAUD:-256000}"

echo "=== LiDAR Monitor Session (raw /scan_rplidar evidence window) ==="
echo "    NO nav2 / amcl / nav_action_server / 2nd go2_driver / motion"

# 已在跑就先清掉，避免雙 sllidar 搶 serial port
tmux kill-session -t "$SESSION" 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

echo "[1/2] static TF base_link → laser (x=0.175, y=0, z=0.18, yaw=3.14159)"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x 0.175 --y 0 --z 0.18 --yaw 3.14159 --frame-id base_link --child-frame-id laser" Enter
sleep 3

echo "[2/2] RPLIDAR (/scan -> /scan_rplidar @ ${SERIAL_PORT}:${SERIAL_BAUD})"
tmux new-window -t "$SESSION" -n sllidar
# 6/15: 必須帶 --ros-args，否則 -p key:=val 會被當成 remap rule（deprecation WARN
# "Found remap rule 'serial_port:=...'"）→ serial_baudrate 256000 等參數根本不套用
# → 用預設 baud 跟 A2M12 通訊 → SL_RESULT_OPERATION_TIMEOUT。沿用
# start_scan_only_tmux.sh 已驗證的完整參數（含 frame_id/angle_compensate/scan_mode），
# 實機 scan-only 隔離測得 /scan_rplidar 11.3Hz、health OK。
tmux send-keys -t "$SESSION:sllidar" "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=${SERIAL_PORT} -p serial_baudrate:=${SERIAL_BAUD} -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 4

echo ""
echo "=== LiDAR Monitor Started ==="
echo ""
echo "Sanity（Roy 上機驗）:"
echo "  ros2 topic hz /scan_rplidar          # 預期 9-13 Hz"
echo "  ros2 node list | grep -c go2_driver  # 預期 1（brain demo 的，不應變 2）"
echo "  ros2 node list | grep -E 'nav2|amcl|nav_action' # 預期空"
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
