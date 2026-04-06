#!/bin/bash
# scripts/start_stress_test_tmux.sh
# 三感知模組同跑壓力測試：face + vision (pose+gesture) + D435
# 用途：驗證 Jetson 上三模組同時運行的 RAM/CPU/溫度/FPS
# 純觀測，不做自動 pass/fail 判定
set -euo pipefail

SESSION="stress-test"
DURATION="${1:-60}"  # 預設 60 秒，可指定參數
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh"

echo "============================================================"
echo "  三感知壓力測試 (face + pose + gesture)"
echo "  持續時間: ${DURATION}s"
echo "============================================================"

# --- Preflight ---
echo "[preflight] 清理殘留..."
bash "$SCRIPT_DIR/clean_face_env.sh" --all 2>/dev/null || true
pkill -f vision_perception_node 2>/dev/null || true
pkill -f vision_status_display 2>/dev/null || true
pkill -f interaction_router 2>/dev/null || true
tmux kill-session -t "$SESSION" 2>/dev/null || true
sleep 2

# --- Window 0: Camera ---
echo "[1/4] Starting D435 camera..."
tmux new-session -d -s "$SESSION" -n camera
tmux send-keys -t "$SESSION:camera" \
  "$ROS_SETUP && ros2 launch realsense2_camera rs_launch.py \
    depth_module.depth_profile:=640x480x15 \
    rgb_camera.color_profile:=640x480x15 \
    pointcloud.enable:=false \
    align_depth.enable:=true" Enter
sleep 8

# --- Window 1: Face ---
echo "[2/4] Starting face_identity_node..."
tmux new-window -t "$SESSION" -n face
tmux send-keys -t "$SESSION:face" \
  "$ROS_SETUP && ros2 launch face_perception face_perception.launch.py" Enter
sleep 5

# --- Window 2: Vision (MediaPipe pose + gesture, CPU only) ---
echo "[3/4] Starting vision_perception_node (full MediaPipe)..."
tmux new-window -t "$SESSION" -n vision
tmux send-keys -t "$SESSION:vision" \
  "$ROS_SETUP && ros2 launch vision_perception vision_perception.launch.py \
    inference_backend:=rtmpose use_camera:=true \
    pose_backend:=mediapipe gesture_backend:=mediapipe \
    max_hands:=2 publish_fps:=8" Enter
sleep 5

# --- Window 3: Monitor (external script, no quoting hell) ---
echo "[4/4] Starting monitor (${DURATION}s)..."
tmux new-window -t "$SESSION" -n monitor
tmux send-keys -t "$SESSION:monitor" \
  "bash $SCRIPT_DIR/stress_test_monitor.sh $DURATION" Enter

echo ""
echo "=== All started ==="
echo "Monitor running for ${DURATION}s in tmux window 'monitor'"
echo ""
echo "To attach: tmux attach -t $SESSION"
echo "To kill:   tmux kill-session -t $SESSION"
