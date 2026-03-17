#!/usr/bin/env bash
# LLM E2E tmux launcher — ASR + LLM Bridge + TTS (audio_track) + Go2 Driver
#
# Usage:
#   bash scripts/start_llm_e2e_tmux.sh
#
# Environment overrides:
#   LLM_ENDPOINT  — LLM API URL (default: http://localhost:8000/v1/chat/completions)
#   LLM_MODEL     — Model name  (default: Qwen/Qwen3.5-9B)
#   LLM_TIMEOUT   — Request timeout in seconds (default: 5.0)
#   ROBOT_IP      — Go2 IP (default: 192.168.123.161)
#
# Requires SSH tunnel if using localhost:
#   ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5

set -euo pipefail

SESSION_NAME="llm-e2e"
WORKDIR="/home/jetson/elder_and_dog"
TMUX_COLS="240"
TMUX_ROWS="72"
CT2_LIB_PATH="$HOME/.local/ctranslate2-cuda/lib"

# ── Go2 ──
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
CONN_TYPE="${CONN_TYPE:-webrtc}"

# ── LLM ──
LLM_ENDPOINT="${LLM_ENDPOINT:-http://localhost:8000/v1/chat/completions}"
LLM_MODEL="${LLM_MODEL:-Qwen/Qwen3.5-9B}"
LLM_TIMEOUT="${LLM_TIMEOUT:-5.0}"

# ── ASR ──
ASR_PROVIDER_ORDER='["whisper_local"]'
ASR_MODEL="small"
ASR_DEVICE="cuda"
ASR_COMPUTE_TYPE="float16"
ASR_CPU_THREADS="4"
INPUT_DEVICE="0"
SAMPLE_RATE="16000"
CAPTURE_SAMPLE_RATE="44100"
MAX_RECORD_SECONDS="10.0"
SPEECH_END_GRACE_MS="250"

# ── TTS ──
TTS_PROVIDER="piper"
PIPER_MODEL_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
PIPER_CONFIG_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json"
PIPER_SPEAKER_ID="0"
PIPER_LENGTH_SCALE="1.20"
PIPER_NOISE_SCALE="0.45"
PIPER_NOISE_W="0.55"
PLAYBACK_METHOD="datachannel"
ROBOT_CHUNK_INTERVAL_SEC="0.06"
ROBOT_PLAYBACK_TAIL_SEC="0.5"
ROBOT_VOLUME="80"

# ════════════════════════════════════════════════════
# Pre-flight checks
# ════════════════════════════════════════════════════

if ! command -v tmux >/dev/null 2>&1; then
  echo "[ERROR] tmux not found."
  exit 1
fi

if [ ! -d "$WORKDIR" ]; then
  echo "[ERROR] Workdir not found: $WORKDIR"
  exit 1
fi

if [ ! -f "$PIPER_MODEL_PATH" ]; then
  echo "[ERROR] Piper model not found: $PIPER_MODEL_PATH"
  exit 1
fi

if [ ! -f "$PIPER_CONFIG_PATH" ]; then
  echo "[ERROR] Piper config not found: $PIPER_CONFIG_PATH"
  exit 1
fi

# Check LLM endpoint reachability
LLM_HEALTH_URL="${LLM_ENDPOINT%/chat/completions}/models"
echo "[PRE] Checking LLM endpoint: $LLM_HEALTH_URL ..."
if ! curl -sf --max-time 3 "$LLM_HEALTH_URL" >/dev/null 2>&1; then
  echo "[WARN] LLM endpoint unreachable: $LLM_HEALTH_URL"
  echo "[HINT] Start SSH tunnel: ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5"
  echo "[HINT] Or set LLM_ENDPOINT=http://140.136.155.5:8000/v1/chat/completions for direct connection"
  read -rp "Continue anyway? (y/N) " CONT
  [ "$CONT" = "y" ] || exit 1
fi

# ════════════════════════════════════════════════════
# Clean environment
# ════════════════════════════════════════════════════

cd "$WORKDIR"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/clean_all.sh" ]; then
  bash "$SCRIPT_DIR/clean_all.sh" || { echo "[ERROR] clean_all failed"; exit 1; }
else
  bash "$SCRIPT_DIR/clean_speech_env.sh" --with-go2-driver || { echo "[ERROR] clean_speech_env failed"; exit 1; }
fi

# ════════════════════════════════════════════════════
# Launch tmux session (4 panes)
# ════════════════════════════════════════════════════
#
# ┌──────────────────────┬───────────────────────┐
# │  Go2 Driver          │  stt_intent_node      │
# │  (WebRTC launch)     │  (ASR + VAD)          │
# ├──────────────────────┼───────────────────────┤
# │  tts_node            │  llm_bridge_node      │
# │  (Piper+audio_track) │  (Qwen3.5-9B)        │
# └──────────────────────┴───────────────────────┘

# Pane 1: Go2 Driver (WebRTC)
tmux new-session -d -x "$TMUX_COLS" -y "$TMUX_ROWS" -s "$SESSION_NAME" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && export ROBOT_IP=$ROBOT_IP && export CONN_TYPE=$CONN_TYPE && ros2 launch go2_robot_sdk robot.launch.py enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false'"

GO2_PANE="$(tmux list-panes -t "$SESSION_NAME":0 -F '#{pane_id}')"

# Pane 2: STT Intent Node (ASR)
STT_PANE="$(tmux split-window -h -P -F '#{pane_id}' -t "$GO2_PANE" \
  "zsh -lc 'setopt nonomatch; cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && export LD_LIBRARY_PATH=$CT2_LIB_PATH:\${LD_LIBRARY_PATH:-} && ros2 run speech_processor stt_intent_node --ros-args -p provider_order:=\"$ASR_PROVIDER_ORDER\" -p whisper_local.model_name:=$ASR_MODEL -p whisper_local.device:=$ASR_DEVICE -p whisper_local.compute_type:=$ASR_COMPUTE_TYPE -p whisper_local.cpu_threads:=$ASR_CPU_THREADS -p input_device:=$INPUT_DEVICE -p sample_rate:=$SAMPLE_RATE -p capture_sample_rate:=$CAPTURE_SAMPLE_RATE -p max_record_seconds:=$MAX_RECORD_SECONDS -p speech_end_grace_ms:=$SPEECH_END_GRACE_MS'")"

# Pane 3: LLM Bridge Node (replaces intent_tts_bridge_node)
tmux split-window -v -t "$STT_PANE" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor llm_bridge_node --ros-args -p llm_endpoint:=\"$LLM_ENDPOINT\" -p llm_model:=\"$LLM_MODEL\" -p llm_timeout:=$LLM_TIMEOUT'"

# Pane 4: TTS Node (Piper + audio_track)
tmux split-window -v -t "$GO2_PANE" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && export PATH=\"$HOME/.local/bin:\$PATH\" && ros2 run speech_processor tts_node --ros-args -p provider:=$TTS_PROVIDER -p piper_model_path:=$PIPER_MODEL_PATH -p piper_config_path:=$PIPER_CONFIG_PATH -p piper_speaker_id:=$PIPER_SPEAKER_ID -p piper_length_scale:=$PIPER_LENGTH_SCALE -p piper_noise_scale:=$PIPER_NOISE_SCALE -p piper_noise_w:=$PIPER_NOISE_W -p playback_method:=$PLAYBACK_METHOD -p robot_chunk_interval_sec:=$ROBOT_CHUNK_INTERVAL_SEC -p robot_playback_tail_sec:=$ROBOT_PLAYBACK_TAIL_SEC -p robot_volume:=$ROBOT_VOLUME'"

# ════════════════════════════════════════════════════
# Layout & options
# ════════════════════════════════════════════════════

tmux select-layout -t "$SESSION_NAME" tiled
tmux set-option -t "$SESSION_NAME" mouse on >/dev/null
tmux set-option -t "$SESSION_NAME" remain-on-exit on >/dev/null

echo "[OK] Started $SESSION_NAME (LLM E2E)"
echo "[INFO] LLM endpoint: $LLM_ENDPOINT"
echo "[INFO] Model: $LLM_MODEL"
echo "[INFO] Playback: $PLAYBACK_METHOD"
echo "[INFO] Verify: bash scripts/e2e_health_check.sh"

tmux attach -t "$SESSION_NAME"
