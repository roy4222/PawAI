#!/bin/bash
# scripts/start_full_demo_tmux.sh
# 四功能整合 Demo 一鍵啟動：face + vision + speech + Go2
# 用途：展示用全功能 session
#
# Environment overrides (same as start_llm_e2e_tmux.sh):
#   INPUT_DEVICE        — mic device index (default: 24=USB, 0=HyperX)
#   CHANNELS            — mic channels (default: 1=USB mono, 2=HyperX stereo)
#   CAPTURE_SAMPLE_RATE — mic native rate (default: 48000=USB, 44100=HyperX)
#   LOCAL_PLAYBACK      — true=USB speaker, false=Go2 Megaphone (default: true)
#   LOCAL_OUTPUT_DEVICE  — ALSA device (default: plughw:3,0)
#   TTS_PROVIDER        — edge_tts or piper (default: edge_tts)
#   ROBOT_IP            — Go2 IP (default: 192.168.123.161)
set -euo pipefail

SESSION="demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="/home/jetson/elder_and_dog"
CT2_LIB_PATH="$HOME/.local/ctranslate2-cuda/lib"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source $WORKDIR/install/setup.zsh && export LD_LIBRARY_PATH=$CT2_LIB_PATH:\${LD_LIBRARY_PATH:-}"

# ── Go2 ──
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
CONN_TYPE="${CONN_TYPE:-webrtc}"

# ── LLM ──
LLM_ENDPOINT="${LLM_ENDPOINT:-http://localhost:8000/v1/chat/completions}"
LLM_MODEL="${LLM_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
LLM_TIMEOUT="${LLM_TIMEOUT:-5.0}"
ENABLE_LOCAL_LLM="${ENABLE_LOCAL_LLM:-true}"
LOCAL_LLM_ENDPOINT="${LOCAL_LLM_ENDPOINT:-http://localhost:11434/v1/chat/completions}"
LOCAL_LLM_MODEL="${LOCAL_LLM_MODEL:-qwen2.5:1.5b}"

# ── ASR ──
ASR_PROVIDER_ORDER="${ASR_PROVIDER_ORDER:-'[\"qwen_cloud\",\"sensevoice_local\",\"whisper_local\"]'}"
QWEN_ASR_BASE_URL="${QWEN_ASR_BASE_URL:-http://127.0.0.1:8001/v1/audio/transcriptions}"
QWEN_ASR_TIMEOUT="${QWEN_ASR_TIMEOUT:-3.0}"
INPUT_DEVICE="${INPUT_DEVICE:-24}"
CHANNELS="${CHANNELS:-1}"
CAPTURE_SAMPLE_RATE="${CAPTURE_SAMPLE_RATE:-48000}"
MIC_GAIN="${MIC_GAIN:-8.0}"

# ── Actions ──
ENABLE_ACTIONS="${ENABLE_ACTIONS:-true}"

# ── TTS ──
TTS_PROVIDER="${TTS_PROVIDER:-edge_tts}"
EDGE_TTS_VOICE="${EDGE_TTS_VOICE:-zh-CN-XiaoxiaoNeural}"
PIPER_MODEL_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
PIPER_CONFIG_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json"
LOCAL_PLAYBACK="${LOCAL_PLAYBACK:-true}"
LOCAL_OUTPUT_DEVICE="${LOCAL_OUTPUT_DEVICE:-plughw:CD002AUDIO,0}"

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
pkill -f interaction_executive 2>/dev/null || true
pkill -f stt_intent_node 2>/dev/null || true
pkill -f tts_node 2>/dev/null || true
pkill -f llm_bridge_node 2>/dev/null || true
tmux kill-session -t "$SESSION" 2>/dev/null || true
sleep 2

# Preflight: LLM endpoint reachability
LLM_HEALTH_URL="${LLM_ENDPOINT%/chat/completions}/models"
echo "[preflight] Checking LLM endpoint: $LLM_HEALTH_URL ..."
if ! curl -sf --max-time 3 "$LLM_HEALTH_URL" >/dev/null 2>&1; then
  echo "[WARN] LLM endpoint unreachable: $LLM_HEALTH_URL"
  echo "[HINT] Start SSH tunnel: ssh -f -N -L 8000:localhost:8000 \$USER@<server>"
  echo "[HINT] Ollama fallback will be used if enabled (ENABLE_LOCAL_LLM=$ENABLE_LOCAL_LLM)"
fi

# Preflight: SenseVoice ASR endpoint reachability
ASR_HEALTH_URL="${QWEN_ASR_BASE_URL%/v1/audio/transcriptions}/health"
echo "[preflight] Checking ASR endpoint: $ASR_HEALTH_URL ..."
if ! curl -sf --max-time 3 "$ASR_HEALTH_URL" >/dev/null 2>&1; then
  echo "[WARN] SenseVoice ASR unreachable — will fallback to local Whisper"
  echo "[HINT] Start SSH tunnel: ssh -f -N -L 8001:localhost:8001 \$USER@<server>"
fi

# === Phase 1: 基礎設施 ===

# --- Window 0: Go2 Driver ---
echo "[1/10] Starting Go2 Driver..."
tmux new-session -d -s "$SESSION" -n go2
tmux send-keys -t "$SESSION:go2" \
  "$ROS_SETUP && export ROBOT_IP=$ROBOT_IP && export CONN_TYPE=$CONN_TYPE && \
  ros2 launch go2_robot_sdk robot.launch.py \
    enable_lidar:=true decode_lidar:=true \
    enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false" Enter
sleep 10

# --- Window 1: D435 Camera ---
echo "[2/10] Starting D435 camera..."
tmux new-window -t "$SESSION" -n camera
tmux send-keys -t "$SESSION:camera" \
  "$ROS_SETUP && ros2 launch realsense2_camera rs_launch.py \
    depth_module.depth_profile:=640x480x15 \
    rgb_camera.color_profile:=640x480x15 \
    pointcloud.enable:=false \
    align_depth.enable:=true" Enter
sleep 5

# === Phase 2: 感知層 ===

# --- Window 2: Face ---
echo "[3/10] Starting face_identity_node..."
tmux new-window -t "$SESSION" -n face
tmux send-keys -t "$SESSION:face" \
  "$ROS_SETUP && ros2 launch face_perception face_perception.launch.py" Enter
sleep 5

# --- Window 3: Vision (Gesture Recognizer + MediaPipe Pose) ---
echo "[4/10] Starting vision_perception_node..."
tmux new-window -t "$SESSION" -n vision
tmux send-keys -t "$SESSION:vision" \
  "$ROS_SETUP && ros2 launch vision_perception vision_perception.launch.py \
    use_camera:=true \
    pose_backend:=mediapipe gesture_backend:=recognizer \
    max_hands:=2 publish_fps:=8" Enter
sleep 5

# --- Window 4a: D435 Obstacle Avoidance ---
echo "[5a/11] Starting D435 obstacle_avoidance_node..."
tmux new-window -t "$SESSION" -n d435obs
tmux send-keys -t "$SESSION:d435obs" \
  "$ROS_SETUP && ros2 launch vision_perception obstacle_avoidance.launch.py" Enter
sleep 2

# --- Window 4b: LiDAR Obstacle ---
echo "[5b/11] Starting LiDAR lidar_obstacle_node..."
tmux new-window -t "$SESSION" -n lidarobs
tmux send-keys -t "$SESSION:lidarobs" \
  "$ROS_SETUP && ros2 run vision_perception lidar_obstacle_node" Enter
sleep 2

# --- Window 5: Interaction Executive v0 (replaces router + bridge) ---
echo "[6/11] Starting interaction_executive..."
tmux new-window -t "$SESSION" -n executive
tmux send-keys -t "$SESSION:executive" \
  "$ROS_SETUP && ros2 launch interaction_executive interaction_executive.launch.py" Enter
sleep 2

# --- Window 5: ASR + Intent ---
echo "[6/9] Starting stt_intent_node (Whisper CUDA warmup ~12s)..."
tmux new-window -t "$SESSION" -n asr
tmux send-keys -t "$SESSION:asr" \
  "$ROS_SETUP && \
  ros2 run speech_processor stt_intent_node --ros-args \
    -p provider_order:=$ASR_PROVIDER_ORDER \
    -p qwen_asr.base_url:='$QWEN_ASR_BASE_URL' \
    -p qwen_asr.timeout_sec:=$QWEN_ASR_TIMEOUT \
    -p qwen_asr.model_name:=sensevoice \
    -p whisper_local.device:=cuda -p whisper_local.compute_type:=float16 \
    -p input_device:=$INPUT_DEVICE -p channels:=$CHANNELS \
    -p sample_rate:=16000 -p capture_sample_rate:=$CAPTURE_SAMPLE_RATE \
    -p mic_gain:=$MIC_GAIN \
    -p energy_vad.start_threshold:=0.02 \
    -p energy_vad.stop_threshold:=0.015 \
    -p energy_vad.silence_duration_ms:=1000 \
    -p energy_vad.min_speech_ms:=500" Enter
sleep 15

# === Phase 3: 決策/執行層 ===

# --- Window 6: TTS ---
echo "[7/9] Starting tts_node ($TTS_PROVIDER)..."
tmux new-window -t "$SESSION" -n tts
tmux send-keys -t "$SESSION:tts" \
  "$ROS_SETUP && amixer -c 3 set PCM 147 >/dev/null 2>&1; \
  ros2 run speech_processor tts_node --ros-args \
    -p provider:=$TTS_PROVIDER \
    -p edge_tts_voice:=$EDGE_TTS_VOICE \
    -p piper_model_path:=$PIPER_MODEL_PATH \
    -p piper_config_path:=$PIPER_CONFIG_PATH \
    -p local_playback:=$LOCAL_PLAYBACK \
    -p local_output_device:=$LOCAL_OUTPUT_DEVICE \
    -p playback_method:=datachannel" Enter
sleep 3

# --- Window 7: LLM Bridge ---
echo "[8/9] Starting llm_bridge_node (Cloud + Ollama fallback, face=executive)..."
tmux new-window -t "$SESSION" -n llm
tmux send-keys -t "$SESSION:llm" \
  "$ROS_SETUP && ros2 run speech_processor llm_bridge_node --ros-args \
    -p llm_endpoint:='$LLM_ENDPOINT' \
    -p llm_model:='$LLM_MODEL' \
    -p llm_timeout:=$LLM_TIMEOUT \
    -p enable_local_llm:=$ENABLE_LOCAL_LLM \
    -p local_llm_endpoint:='$LOCAL_LLM_ENDPOINT' \
    -p local_llm_model:='$LOCAL_LLM_MODEL' \
    -p enable_actions:=$ENABLE_ACTIONS \
    -p subscribe_face:=false" Enter
sleep 3

# --- Static TF: base_link → camera_link (D435 mounted on Go2) ---
echo "[9/10] Publishing base_link → camera_link static TF..."
tmux new-window -t "$SESSION" -n camtf
tmux send-keys -t "$SESSION:camtf" \
  "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher 0.15 0 0.1 0 0 0 base_link camera_link" Enter
sleep 1

# --- Window 9: Foxglove Bridge ---
echo "[10/10] Starting Foxglove bridge..."
tmux new-window -t "$SESSION" -n fox
tmux send-keys -t "$SESSION:fox" \
  "$ROS_SETUP && ros2 run foxglove_bridge foxglove_bridge --ros-args -p port:=8765 -p best_effort_qos_topic_whitelist:='[\"/(point_cloud2|scan|camera/.*/image_raw)\"]'" Enter

# === Options ===
tmux set-option -t "$SESSION" remain-on-exit on >/dev/null

echo ""
echo "=== All started ==="
echo ""
echo "Windows:"
echo "  go2       — Go2 Driver (WebRTC + LiDAR)"
echo "  camera    — D435 Camera"
echo "  face      — Face Identity (YuNet 2023mar + SFace)"
echo "  vision    — Gesture + Pose (Recognizer + MediaPipe CPU)"
echo "  d435obs   — D435 Obstacle Avoidance (front depth)"
echo "  lidarobs  — LiDAR Obstacle (360° safety)"
echo "  executive — Interaction Executive v0 (face/gesture/pose/obstacle → action)"
echo "  asr       — ASR + Intent (SenseVoice + Whisper fallback)"
echo "  tts       — TTS ($TTS_PROVIDER + ${LOCAL_PLAYBACK:+USB speaker}${LOCAL_PLAYBACK:-Megaphone})"
echo "  llm       — LLM Bridge (speech → Cloud→Ollama→RuleBrain)"
echo "  camtf     — Static TF: base_link → camera_link (D435)"
echo "  fox       — Foxglove (ws://$(hostname -I | awk '{print $1}'):8765, best_effort QoS)"
echo ""
echo "To attach: tmux attach -t $SESSION"
echo "To kill:   tmux kill-session -t $SESSION"
echo ""
echo "Verify: bash scripts/e2e_health_check.sh"
echo ""
echo "Config:"
echo "  Mic: device=$INPUT_DEVICE channels=$CHANNELS rate=$CAPTURE_SAMPLE_RATE gain=$MIC_GAIN"
echo "  TTS: $TTS_PROVIDER local_playback=$LOCAL_PLAYBACK device=$LOCAL_OUTPUT_DEVICE"
echo "  LLM: $LLM_MODEL (local fallback=$ENABLE_LOCAL_LLM: $LOCAL_LLM_MODEL)"
