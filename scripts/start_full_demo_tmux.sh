#!/bin/bash
# scripts/start_full_demo_tmux.sh
# 四功能整合 Demo 一鍵啟動：face + vision + speech + Go2
# 用途：展示用全功能 session
set -euo pipefail

SESSION="demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh"

echo "============================================================"
echo "  PawAI 四功能 Demo"
echo "  face + gesture + pose + speech + Go2"
echo "============================================================"

# --- Preflight ---
echo "[preflight] 清理殘留..."
bash "$SCRIPT_DIR/clean_face_env.sh" --all 2>/dev/null || true
pkill -f vision_perception_node 2>/dev/null || true
pkill -f vision_status_display 2>/dev/null || true
pkill -f interaction_router 2>/dev/null || true
pkill -f event_action_bridge 2>/dev/null || true
pkill -f stt_intent_node 2>/dev/null || true
pkill -f tts_node 2>/dev/null || true
pkill -f llm_bridge_node 2>/dev/null || true
tmux kill-session -t "$SESSION" 2>/dev/null || true
sleep 2

# === Phase 1: 基礎設施 ===

# --- Window 0: Go2 Driver ---
echo "[1/8] Starting Go2 Driver..."
tmux new-session -d -s "$SESSION" -n go2
tmux send-keys -t "$SESSION:go2" \
  "$ROS_SETUP && export ROBOT_IP=192.168.123.161 && export CONN_TYPE=webrtc && \
  ros2 launch go2_robot_sdk robot.launch.py \
    enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false" Enter
sleep 10

# --- Window 1: D435 Camera ---
echo "[2/8] Starting D435 camera..."
tmux new-window -t "$SESSION" -n camera
tmux send-keys -t "$SESSION:camera" \
  "$ROS_SETUP && ros2 launch realsense2_camera rs_launch.py \
    depth_module.depth_profile:=640x480x15 \
    rgb_camera.color_profile:=640x480x15 \
    pointcloud.enable:=false \
    align_depth.enable:=true" Enter
sleep 8

# === Phase 2: 感知層 ===

# --- Window 2: Face ---
echo "[3/8] Starting face_identity_node..."
tmux new-window -t "$SESSION" -n face
tmux send-keys -t "$SESSION:face" \
  "$ROS_SETUP && ros2 launch face_perception face_perception.launch.py" Enter
sleep 5

# --- Window 3: Vision (Gesture Recognizer + MediaPipe Pose) ---
echo "[4/8] Starting vision_perception_node..."
tmux new-window -t "$SESSION" -n vision
tmux send-keys -t "$SESSION:vision" \
  "$ROS_SETUP && ros2 launch vision_perception vision_perception.launch.py \
    inference_backend:=rtmpose use_camera:=true \
    pose_backend:=mediapipe gesture_backend:=recognizer \
    max_hands:=2 publish_fps:=8" Enter
sleep 5

# --- Window 4: ASR + Intent ---
echo "[5/8] Starting stt_intent_node..."
tmux new-window -t "$SESSION" -n asr
tmux send-keys -t "$SESSION:asr" \
  "$ROS_SETUP && ros2 run speech_processor stt_intent_node --ros-args \
    -p provider_order:='[\"whisper_local\"]' \
    -p input_device:=0 -p sample_rate:=16000 -p capture_sample_rate:=44100" Enter
sleep 3

# === Phase 3: 決策/執行層 ===

# --- Window 5: TTS ---
echo "[6/8] Starting tts_node..."
tmux new-window -t "$SESSION" -n tts
# TODO: 外接喇叭到貨後改 playback_method:=local
tmux send-keys -t "$SESSION:tts" \
  "$ROS_SETUP && ros2 run speech_processor tts_node --ros-args -p provider:=piper \
    -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx \
    -p playback_method:=datachannel" Enter
sleep 3

# --- Window 6: LLM Bridge ---
echo "[7/8] Starting llm_bridge_node..."
tmux new-window -t "$SESSION" -n llm
tmux send-keys -t "$SESSION:llm" \
  "$ROS_SETUP && ros2 run speech_processor llm_bridge_node --ros-args \
    -p llm_endpoint:='http://localhost:8000/v1/chat/completions' \
    -p llm_model:='Qwen/Qwen2.5-7B-Instruct'" Enter
sleep 3

# --- Window 7: Event Action Bridge ---
echo "[8/8] Starting event_action_bridge..."
tmux new-window -t "$SESSION" -n bridge
tmux send-keys -t "$SESSION:bridge" \
  "$ROS_SETUP && ros2 launch vision_perception event_action_bridge.launch.py" Enter
sleep 2

# === Optional: interaction_router + foxglove ===

# Interaction router (高層事件觀測)
tmux new-window -t "$SESSION" -n router
tmux send-keys -t "$SESSION:router" \
  "$ROS_SETUP && ros2 launch vision_perception interaction_router.launch.py" Enter

# Foxglove bridge
tmux new-window -t "$SESSION" -n fox
tmux send-keys -t "$SESSION:fox" \
  "$ROS_SETUP && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter

echo ""
echo "=== All started ==="
echo ""
echo "Windows:"
echo "  go2     — Go2 Driver (WebRTC)"
echo "  camera  — D435 Camera"
echo "  face    — Face Identity"
echo "  vision  — Gesture + Pose (Recognizer + MediaPipe)"
echo "  asr     — ASR + Intent"
echo "  tts     — TTS (Piper)"
echo "  llm     — LLM Bridge"
echo "  bridge  — Event → Action Bridge"
echo "  router  — Interaction Router (觀測)"
echo "  fox     — Foxglove (ws://$(hostname -I | awk '{print $1}'):8765)"
echo ""
echo "To attach: tmux attach -t $SESSION"
echo "To kill:   tmux kill-session -t $SESSION"
echo ""
echo "⚠️  確認事項："
echo "  1. SSH tunnel 到 RTX 8000: ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5"
echo "  2. Go2 Ethernet 已連接 (192.168.123.161)"
echo "  3. 外接 mic/speaker（到貨後改 tts playback_method）"
