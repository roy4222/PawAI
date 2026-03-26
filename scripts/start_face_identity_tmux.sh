#!/usr/bin/env bash
# start_face_identity_tmux.sh — 一鍵啟動人臉辨識 pipeline (tmux)
# 用法: bash scripts/start_face_identity_tmux.sh
#
# 啟動 3 個 pane:
#   0: RealSense D435 camera
#   1: face_identity_node (ROS2 package)
#   2: foxglove_bridge
set -euo pipefail

SESSION="face_identity"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Preflight checks ---
echo "=== Preflight checks ==="

# Check ROS2
if ! command -v ros2 &>/dev/null; then
    echo "ERROR: ros2 not found. Source ROS2 setup first."
    exit 1
fi

# Check D435 connected
if ! ros2 pkg list 2>/dev/null | grep -q realsense2_camera; then
    echo "WARNING: realsense2_camera package not found. Camera launch may fail."
fi

# Check model files
YUNET="/home/jetson/face_models/face_detection_yunet_2023mar.onnx"
SFACE="/home/jetson/face_models/face_recognition_sface_2021dec.onnx"
FACE_DB="/home/jetson/face_db"

for f in "$YUNET" "$SFACE"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Model file not found: $f"
        exit 1
    fi
done

if [[ ! -d "$FACE_DB" ]]; then
    echo "ERROR: Face DB directory not found: $FACE_DB"
    exit 1
fi

# Check face_perception package is built
if ! ros2 pkg list 2>/dev/null | grep -q face_perception; then
    echo "ERROR: face_perception package not found."
    echo "  Run: colcon build --packages-select face_perception && source install/setup.zsh"
    exit 1
fi

echo "=== Preflight OK ==="

# --- Clean previous session ---
bash "$REPO_DIR/scripts/clean_face_env.sh" --all 2>/dev/null || true

# --- ROS2 source preamble (Jetson 用 zsh，不可混用 setup.bash) ---
PREAMBLE="source /opt/ros/humble/setup.zsh && cd $REPO_DIR && source install/setup.zsh"

# --- Create tmux session ---
echo "=== Starting tmux session: $SESSION ==="

# Pane 0: RealSense D435 camera
tmux new-session -d -s "$SESSION" -n main
tmux send-keys -t "$SESSION:main" \
    "$PREAMBLE && echo '--- Starting D435 camera ---' && ros2 launch realsense2_camera rs_launch.py depth_module.profile:=640x480x30 rgb_camera.profile:=640x480x30 align_depth.enable:=true" Enter

sleep 3  # Wait for camera to initialize

# Pane 1: face_identity_node
tmux split-window -v -t "$SESSION:main"
tmux send-keys -t "$SESSION:main.1" \
    "$PREAMBLE && echo '--- Starting face_identity_node ---' && ros2 launch face_perception face_perception.launch.py" Enter

# Pane 2: foxglove_bridge
tmux split-window -v -t "$SESSION:main"
tmux send-keys -t "$SESSION:main.2" \
    "$PREAMBLE && echo '--- Starting foxglove_bridge ---' && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter

# Layout: even vertical split
tmux select-layout -t "$SESSION:main" even-vertical

echo ""
echo "=== Face identity pipeline started ==="
echo "  tmux attach -t $SESSION"
echo "  Foxglove: ws://<jetson-ip>:8765"
echo "  Topics:"
echo "    /state/perception/face"
echo "    /event/face_identity"
echo "    /face_identity/debug_image"
echo ""
echo "  Stop: bash scripts/clean_face_env.sh --all"
