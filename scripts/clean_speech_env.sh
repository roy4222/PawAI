#!/usr/bin/env bash
# Clean speech test environment — kill sessions, nodes, verify clean.
# Usage: bash scripts/clean_speech_env.sh [--with-go2-driver]

set -euo pipefail

WITH_GO2_DRIVER=0
for arg in "$@"; do
  case "$arg" in
    --with-go2-driver) WITH_GO2_DRIVER=1 ;;
  esac
done

SPEECH_SESSIONS=("asr-tts-no-vad" "speech-e2e" "speech-test")
SPEECH_PROCS=("stt_intent_node" "intent_tts_bridge_node" "llm_bridge_node" "tts_node" "speech_test_observer")

if [ "$WITH_GO2_DRIVER" = "1" ]; then
  SPEECH_PROCS+=("go2_driver_node")
fi

KILLED_SESSIONS=0
KILLED_PROCS=0

# Step 1: Kill tmux sessions
for sess in "${SPEECH_SESSIONS[@]}"; do
  if tmux has-session -t "$sess" 2>/dev/null; then
    tmux kill-session -t "$sess" 2>/dev/null || true
    KILLED_SESSIONS=$((KILLED_SESSIONS + 1))
  fi
done

# Step 2: pkill speech nodes
for proc in "${SPEECH_PROCS[@]}"; do
  if pkill -f "$proc" 2>/dev/null; then
    KILLED_PROCS=$((KILLED_PROCS + 1))
  fi
done

# Step 3: Wait for processes to exit (max 5s)
WAITED=0
while [ $WAITED -lt 50 ]; do
  STILL_ALIVE=0
  for proc in "${SPEECH_PROCS[@]}"; do
    if pgrep -f "$proc" >/dev/null 2>&1; then
      STILL_ALIVE=1
      break
    fi
  done
  if [ "$STILL_ALIVE" = "0" ]; then
    break
  fi
  sleep 0.1
  WAITED=$((WAITED + 1))
done

# Step 4: Check for residual processes
RESIDUAL=0
for proc in "${SPEECH_PROCS[@]}"; do
  PIDS=$(pgrep -f "$proc" 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "[WARN] Residual process: $proc (PIDs: $PIDS)"
    RESIDUAL=1
  fi
done

# Step 5: Stop PulseAudio to release ALSA device for PortAudio
# PulseAudio holds /dev/snd/pcmC0D0c which blocks PortAudio ALSA backend (-9985)
if command -v pulseaudio >/dev/null 2>&1; then
  systemctl --user stop pulseaudio.socket pulseaudio.service 2>/dev/null || true
  pulseaudio --kill 2>/dev/null || true
  # Prevent auto-respawn during this session
  systemctl --user mask pulseaudio.socket pulseaudio.service 2>/dev/null || true
fi

# Step 6: Output status
echo "[clean_speech_env] Killed $KILLED_SESSIONS sessions, $KILLED_PROCS process groups"

if [ "$RESIDUAL" = "1" ]; then
  echo "[WARN] Some processes could not be killed. Check manually."
  exit 1
fi

echo "[OK] Speech environment clean"
exit 0
