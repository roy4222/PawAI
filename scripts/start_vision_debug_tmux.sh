#!/bin/bash
# scripts/start_vision_debug_tmux.sh
# 一鍵啟動 vision-only debug 環境（不含語音）
# 用途：手勢/姿勢單功能驗證 + Foxglove 可視化
set -euo pipefail

SESSION="vision-debug"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh"

echo "=== Vision Debug Session ==="
echo "Killing existing session..."
tmux kill-session -t "$SESSION" 2>/dev/null || true
sleep 1

echo "Starting D435..."
tmux new-session -d -s "$SESSION" -n camera
tmux send-keys -t "$SESSION:camera" "$ROS_SETUP && ros2 launch realsense2_camera rs_launch.py depth_module.depth_profile:=640x480x15 rgb_camera.color_profile:=640x480x15 pointcloud.enable:=false" Enter
sleep 8

echo "Starting vision_perception (full MediaPipe)..."
tmux new-window -t "$SESSION" -n vision
tmux send-keys -t "$SESSION:vision" "$ROS_SETUP && ros2 launch vision_perception vision_perception.launch.py inference_backend:=rtmpose use_camera:=true pose_backend:=mediapipe gesture_backend:=mediapipe publish_fps:=15 max_hands:=2" Enter
sleep 5

echo "Starting vision_status_display..."
tmux new-window -t "$SESSION" -n status
tmux send-keys -t "$SESSION:status" "$ROS_SETUP && ros2 run vision_perception vision_status_display" Enter
sleep 2

echo "Starting foxglove_bridge..."
tmux new-window -t "$SESSION" -n fox
tmux send-keys -t "$SESSION:fox" "$ROS_SETUP && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter
sleep 3

echo ""
echo "=== All started ==="
echo "Foxglove: ws://$(hostname -I | awk '{print $1}'):8765"
echo "Topics to watch:"
echo "  /vision_perception/debug_image  — keypoints overlay"
echo "  /vision_perception/status_image — status dashboard"
echo "  /event/gesture_detected         — gesture events"
echo "  /event/pose_detected            — pose events"
echo ""
echo "To attach: tmux attach -t $SESSION"
echo "To kill:   tmux kill-session -t $SESSION"
