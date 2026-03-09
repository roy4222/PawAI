#!/usr/bin/env bash

set -euo pipefail

SESSION_NAME="speech-mvp"
WORKDIR="/home/jetson/elder_and_dog"

INPUT_DEVICE="${INPUT_DEVICE:-0}"
CHANNELS="${CHANNELS:-1}"
SAMPLE_RATE="${SAMPLE_RATE:-16000}"
CAPTURE_SAMPLE_RATE="${CAPTURE_SAMPLE_RATE:-44100}"
FRAME_SAMPLES="${FRAME_SAMPLES:-512}"
VAD_THRESHOLD="${VAD_THRESHOLD:-0.25}"
MIN_SILENCE_MS="${MIN_SILENCE_MS:-150}"

ASR_MODEL_NAME="${ASR_MODEL_NAME:-tiny}"
ASR_LANGUAGE="${ASR_LANGUAGE:-zh}"

INTENT_MIN_CONFIDENCE="${INTENT_MIN_CONFIDENCE:-0.55}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "[ERROR] tmux not found. Please install tmux first."
  exit 1
fi

if [ ! -d "$WORKDIR" ]; then
  echo "[ERROR] Workdir not found: $WORKDIR"
  exit 1
fi

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

zsh -lc "cd $WORKDIR && source /opt/ros/humble/setup.zsh && colcon build --packages-select speech_processor && source install/setup.zsh"

tmux new-session -d -s "$SESSION_NAME" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor vad_node --ros-args -p input_device:=$INPUT_DEVICE -p channels:=$CHANNELS -p sample_rate:=$SAMPLE_RATE -p capture_sample_rate:=$CAPTURE_SAMPLE_RATE -p frame_samples:=$FRAME_SAMPLES -p vad_threshold:=$VAD_THRESHOLD -p min_silence_ms:=$MIN_SILENCE_MS'"

VAD_PANE="$(tmux list-panes -t "$SESSION_NAME":0 -F '#{pane_id}')"
ASR_PANE="$(tmux split-window -h -P -F '#{pane_id}' -t "$VAD_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor asr_node --ros-args -p model_name:=$ASR_MODEL_NAME -p language:=$ASR_LANGUAGE'")"
INTENT_PANE="$(tmux split-window -v -P -F '#{pane_id}' -t "$ASR_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor intent_node --ros-args -p min_confidence:=$INTENT_MIN_CONFIDENCE'")"
ASR_RESULT_PANE="$(tmux split-window -v -P -F '#{pane_id}' -t "$VAD_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && while true; do ros2 topic echo /asr_result; sleep 1; done'")"
INTENT_TOPIC_PANE="$(tmux split-window -h -P -F '#{pane_id}' -t "$ASR_RESULT_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && while true; do ros2 topic echo /intent; sleep 1; done'")"
tmux split-window -v -t "$INTENT_TOPIC_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && while true; do ros2 topic echo /event/speech_intent_recognized; sleep 1; done'"

tmux select-layout -t "$SESSION_NAME" tiled
tmux set-option -t "$SESSION_NAME" mouse on >/dev/null
tmux set-option -t "$SESSION_NAME" remain-on-exit on >/dev/null

echo "[OK] tmux session '$SESSION_NAME' started."
echo "[INFO] panes: vad_node | asr_node | intent_node | /asr_result | /intent | /event/speech_intent_recognized"
echo "[INFO] attach with: tmux attach -t $SESSION_NAME"

tmux attach -t "$SESSION_NAME"
