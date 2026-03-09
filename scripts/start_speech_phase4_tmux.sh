#!/usr/bin/env bash

set -euo pipefail

SESSION_NAME="speech-phase4"
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

TTS_API_KEY="${TTS_API_KEY:-${ELEVENLABS_API_KEY:-}}"
TTS_VOICE_NAME="${TTS_VOICE_NAME:-XrExE9yKIg1WjnnlVkGX}"
TTS_PROVIDER="${TTS_PROVIDER:-elevenlabs}"
MELO_LANGUAGE="${MELO_LANGUAGE:-ZH}"
MELO_SPEAKER="${MELO_SPEAKER:-ZH}"
MELO_SPEED="${MELO_SPEED:-0.92}"
MELO_DEVICE="${MELO_DEVICE:-auto}"
PIPER_MODEL_PATH="${PIPER_MODEL_PATH:-}"
PIPER_CONFIG_PATH="${PIPER_CONFIG_PATH:-}"
PIPER_SPEAKER_ID="${PIPER_SPEAKER_ID:-0}"
PIPER_LENGTH_SCALE="${PIPER_LENGTH_SCALE:-1.0}"
PIPER_NOISE_SCALE="${PIPER_NOISE_SCALE:-0.667}"
PIPER_NOISE_W="${PIPER_NOISE_W:-0.8}"
PIPER_USE_CUDA="${PIPER_USE_CUDA:-false}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "[ERROR] tmux not found. Please install tmux first."
  exit 1
fi

if [ ! -d "$WORKDIR" ]; then
  echo "[ERROR] Workdir not found: $WORKDIR"
  exit 1
fi

if [ "$TTS_PROVIDER" = "elevenlabs" ] && [ -z "$TTS_API_KEY" ]; then
  echo "[WARN] TTS_API_KEY/ELEVENLABS_API_KEY is empty. tts_node may fail to synthesize audio."
fi

if [ "$TTS_PROVIDER" = "piper" ] && [ -z "$PIPER_MODEL_PATH" ]; then
  echo "[WARN] PIPER_MODEL_PATH is empty. tts_node may fail to synthesize audio."
fi

zsh -lc "cd $WORKDIR && source /opt/ros/humble/setup.zsh && colcon build --packages-select speech_processor && source install/setup.zsh"

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

tmux new-session -d -s "$SESSION_NAME" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor vad_node --ros-args -p input_device:=$INPUT_DEVICE -p channels:=$CHANNELS -p sample_rate:=$SAMPLE_RATE -p capture_sample_rate:=$CAPTURE_SAMPLE_RATE -p frame_samples:=$FRAME_SAMPLES -p vad_threshold:=$VAD_THRESHOLD -p min_silence_ms:=$MIN_SILENCE_MS'"

VAD_PANE="$(tmux list-panes -t "$SESSION_NAME":0 -F '#{pane_id}')"
ASR_PANE="$(tmux split-window -h -P -F '#{pane_id}' -t "$VAD_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor asr_node --ros-args -p model_name:=$ASR_MODEL_NAME -p language:=$ASR_LANGUAGE'")"
INTENT_PANE="$(tmux split-window -v -P -F '#{pane_id}' -t "$ASR_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor intent_node --ros-args -p min_confidence:=$INTENT_MIN_CONFIDENCE'")"
TTS_PANE="$(tmux split-window -v -P -F '#{pane_id}' -t "$INTENT_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor tts_node --ros-args -p api_key:=$TTS_API_KEY -p provider:=$TTS_PROVIDER -p voice_name:=$TTS_VOICE_NAME -p melo_language:=$MELO_LANGUAGE -p melo_speaker:=$MELO_SPEAKER -p melo_speed:=$MELO_SPEED -p melo_device:=$MELO_DEVICE -p piper_model_path:=$PIPER_MODEL_PATH -p piper_config_path:=$PIPER_CONFIG_PATH -p piper_speaker_id:=$PIPER_SPEAKER_ID -p piper_length_scale:=$PIPER_LENGTH_SCALE -p piper_noise_scale:=$PIPER_NOISE_SCALE -p piper_noise_w:=$PIPER_NOISE_W -p piper_use_cuda:=$PIPER_USE_CUDA'")"
BRIDGE_PANE="$(tmux split-window -v -P -F '#{pane_id}' -t "$VAD_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor intent_tts_bridge_node'")"
INTENT_EVENT_PANE="$(tmux split-window -h -P -F '#{pane_id}' -t "$BRIDGE_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && while true; do ros2 topic echo /event/speech_intent_recognized; sleep 1; done'")"
TTS_TOPIC_PANE="$(tmux split-window -v -P -F '#{pane_id}' -t "$INTENT_EVENT_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && while true; do ros2 topic echo /tts; sleep 1; done'")"
tmux split-window -v -t "$TTS_TOPIC_PANE" "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && while true; do ros2 topic echo /webrtc_req; sleep 1; done'"

tmux select-layout -t "$SESSION_NAME" tiled
tmux set-option -t "$SESSION_NAME" mouse on >/dev/null
tmux set-option -t "$SESSION_NAME" remain-on-exit on >/dev/null

echo "[OK] tmux session '$SESSION_NAME' started."
echo "[INFO] panes: vad_node | asr_node | intent_node | tts_node | intent_tts_bridge_node | /event/speech_intent_recognized | /tts | /webrtc_req"
echo "[INFO] attach with: tmux attach -t $SESSION_NAME"

tmux attach -t "$SESSION_NAME"
