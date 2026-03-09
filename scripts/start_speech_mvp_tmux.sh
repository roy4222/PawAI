#!/usr/bin/env bash

set -euo pipefail

SESSION_NAME="speech-mvp"
WORKDIR="/home/jetson/elder_and_dog"

INPUT_DEVICE="${INPUT_DEVICE:-0}"
SAMPLE_RATE="${SAMPLE_RATE:-16000}"
CAPTURE_SAMPLE_RATE="${CAPTURE_SAMPLE_RATE:-44100}"
FRAME_SAMPLES="${FRAME_SAMPLES:-512}"
VAD_THRESHOLD="${VAD_THRESHOLD:-0.25}"
MIN_SILENCE_MS="${MIN_SILENCE_MS:-150}"

ASR_MODEL_NAME="${ASR_MODEL_NAME:-tiny}"
ASR_LANGUAGE="${ASR_LANGUAGE:-zh}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "[ERROR] tmux not found. Please install tmux first."
  exit 1
fi

if [ ! -d "$WORKDIR" ]; then
  echo "[ERROR] Workdir not found: $WORKDIR"
  exit 1
fi

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

tmux new-session -d -s "$SESSION_NAME" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && colcon build --packages-select speech_processor && source install/setup.zsh && ros2 run speech_processor vad_node --ros-args -p input_device:=$INPUT_DEVICE -p sample_rate:=$SAMPLE_RATE -p capture_sample_rate:=$CAPTURE_SAMPLE_RATE -p frame_samples:=$FRAME_SAMPLES -p vad_threshold:=$VAD_THRESHOLD -p min_silence_ms:=$MIN_SILENCE_MS'"

tmux split-window -h -t "$SESSION_NAME":0 "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor asr_node --ros-args -p model_name:=$ASR_MODEL_NAME -p language:=$ASR_LANGUAGE'"

tmux split-window -v -t "$SESSION_NAME":0.0 "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /asr_result'"

tmux split-window -v -t "$SESSION_NAME":0.1 "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /state/interaction/asr'"

tmux select-layout -t "$SESSION_NAME" tiled
tmux set-option -t "$SESSION_NAME" mouse on >/dev/null

echo "[OK] tmux session '$SESSION_NAME' started."
echo "[INFO] panes: vad_node | asr_node | /asr_result | /state/interaction/asr"
echo "[INFO] attach with: tmux attach -t $SESSION_NAME"

tmux attach -t "$SESSION_NAME"
