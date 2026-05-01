#!/usr/bin/env bash
# scripts/start_scan_only_tmux.sh
# Phase 2 — Scan-only stack（只 TF + sllidar + monitor）
#
# 拓撲：
#   static TF       → base_link → laser（mount 量值 v7（4/30 evening）：x=0.175, y=0, z=0.18, yaw=0；雷達移到脖子前方平台，0° 對齊 Go2 正前（PENDING scan_health_check 物理驗證））
#   sllidar         → /scan_rplidar 10.4Hz
#   monitor         → 手動跑 scan_health_check.py / topic hz / topic echo
#
# 不啟：Go2 driver / Nav2 / reactive_stop / mux / teleop
# 理由：scan health 階段不需要 Go2 動，剝離後不會被 reactive/mux/nav 干擾
set -euo pipefail

SESSION="scan-only"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"

echo "=== Scan-only Stack ==="
echo "Killing any prior session..."
tmux kill-session -t "$SESSION" 2>/dev/null || true
ros2 daemon stop 2>/dev/null || true
sleep 1
ros2 daemon start 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

echo "[1/3] static TF base_link -> laser (x=0.175, y=0, z=0.18, yaw=0)..."
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x 0.175 --y 0 --z 0.18 --yaw 0 --frame-id base_link --child-frame-id laser" Enter
sleep 2

echo "[2/3] sllidar (Standard mode, /scan_rplidar)..."
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 5

echo "[3/3] monitor window（手動跑檢查）..."
tmux new-window -t "$SESSION" -n monitor
tmux send-keys -t "$SESSION:monitor" "$ROS_SETUP" Enter

echo ""
echo "=== Started ==="
echo "Sanity check (在 monitor window 跑):"
echo "  ros2 topic hz /scan_rplidar      # 期望 ≈ 10.4 Hz"
echo "  ros2 run tf2_ros tf2_echo base_link laser"
echo ""
echo "PHANTOM 健康檢查："
echo "  python3 ~/elder_and_dog/scripts/scan_health_check.py --duration 5"
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
