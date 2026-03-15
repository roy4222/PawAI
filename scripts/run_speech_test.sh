#!/usr/bin/env bash
# Orchestrate 30-round speech validation test.
# Usage: scripts/run_speech_test.sh [--yaml path] [--skip-build] [--skip-driver]

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CT2_LIB_PATH="$HOME/.local/ctranslate2-cuda/lib"
YAML_FILE="${WORKDIR}/test_scripts/speech_30round.yaml"
SKIP_BUILD=0
SKIP_DRIVER=0
NODES_RUNNING=0

# Parse args (while+shift, not for loop)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build) SKIP_BUILD=1; shift ;;
    --skip-driver) SKIP_DRIVER=1; shift ;;
    --nodes-running) NODES_RUNNING=1; SKIP_BUILD=1; SKIP_DRIVER=1; shift ;;
    --yaml=*) YAML_FILE="${1#*=}"; shift ;;
    --yaml) YAML_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [ ! -f "$YAML_FILE" ]; then
  echo "[ERROR] YAML file not found: $YAML_FILE"
  exit 1
fi

echo "=== Speech 30-Round Validation ==="
echo "YAML: $YAML_FILE"

if [ "$NODES_RUNNING" = "1" ]; then
  echo "[1-3/7] Skipped (--nodes-running: using existing nodes)"
  # Only kill stale observer
  pkill -f speech_test_observer 2>/dev/null || true
  sleep 1
  SESSION_NAME="speech-test-observer"
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
else
  # Step 1: Clean environment (only speech-test session; preserve driver session if --skip-driver)
  echo "[1/7] Cleaning environment..."
  tmux kill-session -t speech-test 2>/dev/null || true
  for proc in stt_intent_node intent_tts_bridge_node tts_node speech_test_observer; do
    pkill -f "$proc" 2>/dev/null || true
  done
  # Stop PulseAudio to release ALSA device for PortAudio
  if command -v pulseaudio >/dev/null 2>&1; then
    systemctl --user stop pulseaudio.socket pulseaudio.service 2>/dev/null || true
    pulseaudio --kill 2>/dev/null || true
    systemctl --user mask pulseaudio.socket pulseaudio.service 2>/dev/null || true
  fi
  sleep 1
  echo "[OK] Clean done"

  # Step 2: Build (optional)
  if [ "$SKIP_BUILD" = "0" ]; then
    echo "[2/7] Building..."
    cd "$WORKDIR"
    zsh -lc "source /opt/ros/humble/setup.zsh && colcon build --packages-select speech_processor go2_robot_sdk"
  else
    echo "[2/7] Build skipped"
  fi

  cd "$WORKDIR"

  # Step 3: Launch main nodes in tmux
  echo "[3/7] Starting main nodes..."
  SESSION_NAME="speech-test"
  ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
  CONN_TYPE="${CONN_TYPE:-webrtc}"

  if [ "$SKIP_DRIVER" = "0" ]; then
    tmux new-session -d -s "$SESSION_NAME" \
      "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
       export ROBOT_IP=$ROBOT_IP CONN_TYPE=$CONN_TYPE && \
       ros2 launch go2_robot_sdk robot.launch.py enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false'"
  else
    echo "  [skip-driver] go2_driver_node skipped — assuming already running"
    tmux new-session -d -s "$SESSION_NAME" "echo 'Driver skipped — this pane is a placeholder'; sleep 999999"
  fi

  tmux split-window -h -t "$SESSION_NAME" \
    "zsh -lc 'setopt nonomatch; cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
     export LD_LIBRARY_PATH=$CT2_LIB_PATH:\${LD_LIBRARY_PATH:-} && \
     ros2 run speech_processor stt_intent_node --ros-args \
     -p provider_order:=\"[\\\"whisper_local\\\"]\" \
     -p whisper_local.model_name:=small \
     -p whisper_local.device:=cuda \
     -p whisper_local.compute_type:=float16 \
     -p input_device:=0 \
     -p sample_rate:=16000 \
     -p capture_sample_rate:=44100'"

  tmux split-window -v -t "$SESSION_NAME" \
    "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
     ros2 run speech_processor intent_tts_bridge_node'"

  PIPER_MODEL="/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
  PIPER_CONFIG="/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json"
  tmux split-window -v -t "$SESSION_NAME" \
    "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
     export PATH=\"\$HOME/.local/bin:\$PATH\" && \
     ros2 run speech_processor tts_node --ros-args \
     -p provider:=piper \
     -p piper_model_path:=$PIPER_MODEL \
     -p piper_config_path:=$PIPER_CONFIG'"
fi

# Health check helper + ROS2 env for orchestrator shell
wait_for_topic() {
  local TOPIC="$1"
  local TIMEOUT="$2"
  local ELAPSED=0
  local OUT
  while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    OUT=$(ros2 topic info "$TOPIC" 2>/dev/null || true)
    if echo "$OUT" | grep -q "Publisher count: [1-9]"; then
      return 0
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
  done
  return 1
}

# Source ROS2 env (unset nounset-hostile vars first)
unset AMENT_TRACE_SETUP_FILES 2>/dev/null || true
source /opt/ros/humble/setup.bash
source "$WORKDIR/install/setup.bash"

# Health checks for speech nodes (observer not started yet)
echo "[4/7] Health checks..."

# /event/speech_intent_recognized has publisher when stt_intent_node is ready (model loaded)
# Allow 60s for Whisper CUDA model load
echo "  Waiting for stt_intent_node (/event/speech_intent_recognized, 60s)..."
if ! wait_for_topic "/event/speech_intent_recognized" 60; then
  echo "[ERROR] stt_intent_node not ready — check tmux pane for errors"
  echo "  Hint: tmux attach -t $SESSION_NAME"
  exit 1
fi
echo "  OK stt_intent_node ready"

# Check /webrtc_req subscriber (go2_driver_node)
echo "  Waiting for go2_driver_node (/webrtc_req subscriber, 15s)..."
WAITED=0
while [ "$WAITED" -lt 15 ]; do
  WR_OUT=$(ros2 topic info /webrtc_req 2>/dev/null || true)
  if echo "$WR_OUT" | grep -q "Subscription count: [1-9]"; then
    break
  fi
  sleep 1
  WAITED=$((WAITED + 1))
done
if [ "$WAITED" -ge 15 ]; then
  echo "[WARN] go2_driver_node not subscribing to /webrtc_req — TTS playback may not work"
else
  echo "  OK go2_driver_node ready"
fi

# Step 5: Warmup round BEFORE observer starts (so warmup is not recorded)
echo ""
echo "=== WARMUP (不計分) ==="
echo "請說任意一句話做暖機（observer 尚未啟動，此輪不會進入統計）..."
read -rp "（完成後按 Enter）"
echo ""

# Step 4b: Launch observer AFTER warmup (clean start, no warmup pollution)
echo "[4b/7] Starting observer..."
OBSERVER_SESSION="speech-test-observer"
tmux kill-session -t "$OBSERVER_SESSION" 2>/dev/null || true
tmux new-session -d -s "$OBSERVER_SESSION" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   ros2 run speech_processor speech_test_observer --ros-args \
   -p output_dir:=$WORKDIR/test_results'"

# Wait for observer to be ready
echo "  Waiting for observer..."
if ! wait_for_topic "/speech_test_observer/round_meta_ack" 15; then
  echo "[ERROR] Observer not ready"
  tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
  exit 1
fi
echo "  OK observer ready"

# Parse YAML into tab-separated lines (one python3 call for all rounds)
echo "[5/7] Running test rounds..."

ROUND_DATA=$(python3 -c "
import yaml, json, sys
with open('$YAML_FILE') as f:
    d = yaml.safe_load(f)
rounds = d.get('rounds', d.get('fixed_rounds', []))
total = len(rounds)
for r in rounds:
    print('\t'.join([str(r['round_id']), r.get('mode','fixed'),
          r['expected_intent'], r.get('utterance',''), str(total)]))
")

# Wait until TTS finishes playing. /state/tts_playing is latched (transient_local),
# ros2 topic echo --once returns immediately with the last value.
wait_tts_done() {
  local MAX_WAIT=15
  local WAITED=0
  while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    local TTS_OUT
    TTS_OUT=$(timeout 2 ros2 topic echo --once /state/tts_playing std_msgs/msg/Bool 2>/dev/null || true)
    if echo "$TTS_OUT" | grep -q "data: false"; then
      return 0
    fi
    # Empty = topic unreachable or QoS mismatch; keep waiting, don't assume idle
    sleep 0.5
    WAITED=$((WAITED + 1))
  done
  # Fallback: max wait reached, proceed anyway
}

# Read rounds using here-string (not pipe) to keep stdin for operator interaction
while IFS=$'\t' read -r ROUND_ID MODE EXPECTED UTTERANCE TOTAL; do
  echo ""
  echo "[Round $ROUND_ID/$TOTAL] 請說：「$UTTERANCE」"
  echo "  expected_intent: $EXPECTED"

  # Step A: Operator reads prompt, presses Enter (don't speak yet)
  read -rp "  按 Enter 準備（先不要說話）" INPUT </dev/tty
  if [ "$INPUT" = "q" ]; then
    echo "[INFO] 測試提前結束"
    break
  fi

  # Step B: Start round_done listener FIRST (before meta, before speech)
  DONE_TMPFILE=$(mktemp /tmp/round_done_XXXXXX)
  ( timeout 45 ros2 topic echo /speech_test_observer/round_done_ack std_msgs/msg/String 2>/dev/null > "$DONE_TMPFILE" ) &
  DONE_PID=$!
  sleep 0.3

  # Step C: Send round_meta
  META_JSON="{\"round_id\":$ROUND_ID,\"mode\":\"$MODE\",\"expected_intent\":\"$EXPECTED\",\"utterance_text\":\"$UTTERANCE\"}"
  timeout 5 ros2 topic echo --once /speech_test_observer/round_meta_ack std_msgs/msg/String 2>/dev/null &
  ACK_PID=$!
  sleep 0.2
  ros2 topic pub --once /speech_test_observer/round_meta_req std_msgs/msg/String "{data: '$META_JSON'}" >/dev/null 2>&1
  wait $ACK_PID 2>/dev/null || echo "  [WARN] meta ack timeout"

  # Step D: Tell operator to speak
  echo "  🎤 現在請說！"
  read -rp "  （說完後按 Enter）" INPUT2 </dev/tty

  # Step E: Wait for round_done_ack with matching round_id (or meta timeout from observer)
  echo "  ⏳ 等待處理..."
  ROUND_DONE=0
  WAIT_ELAPSED=0
  while [ "$WAIT_ELAPSED" -lt 40 ]; do
    if grep -q "\"round_id\": $ROUND_ID" "$DONE_TMPFILE" 2>/dev/null; then
      ROUND_DONE=1
      break
    fi
    sleep 0.5
    WAIT_ELAPSED=$((WAIT_ELAPSED + 1))
  done
  kill $DONE_PID 2>/dev/null; wait $DONE_PID 2>/dev/null || true

  if [ "$ROUND_DONE" = "1" ]; then
    DONE_INTENT=$(grep "\"round_id\": $ROUND_ID" "$DONE_TMPFILE" | grep -o '"intent": "[^"]*"' | head -1 || true)
    echo "  [Round $ROUND_ID] ✓ ($DONE_INTENT)"
    # Wait for TTS playback to finish before next round
    wait_tts_done
  else
    echo "  [Round $ROUND_ID] ⚠ no ack (20s)"
  fi
  rm -f "$DONE_TMPFILE"

done <<< "$ROUND_DATA"

# Step 6: Wait for last round to finish, then generate report
echo ""
echo "[6/7] Waiting for last round to finish..."
sleep 8  # drain: let TTS + webrtc playback complete for the final round
echo "Generating report..."

# Start listening for ack BEFORE publishing (avoid race condition)
timeout 10 ros2 topic echo --once /speech_test_observer/generate_report_ack std_msgs/msg/String 2>/dev/null &
REPORT_ACK_PID=$!
sleep 0.2
ros2 topic pub --once /speech_test_observer/generate_report_req std_msgs/msg/String "{data: '{}'}" >/dev/null 2>&1
wait $REPORT_ACK_PID 2>/dev/null && echo "[OK] Report generated" || echo "[WARN] Report ack timeout"

# Step 7: Display summary
echo ""
echo "[7/7] Done!"
echo "Results in: $WORKDIR/test_results/"
ls -la "$WORKDIR/test_results/" 2>/dev/null || echo "(no results yet)"

# Show summary JSON if available
LATEST_SUMMARY=$(ls -t "$WORKDIR/test_results/"*_summary.json 2>/dev/null | head -1)
if [ -n "$LATEST_SUMMARY" ]; then
  echo ""
  echo "=== Summary ==="
  python3 -c "
import json, sys
with open('$LATEST_SUMMARY') as f:
    s = json.load(f)
print(f'Grade: {s[\"grade\"]}')
print(f'Completed: {s[\"completed\"]}/{s[\"total_rounds\"]}')
fr = s.get('fixed_rounds', {})
print(f'Fixed accuracy: {fr.get(\"hit\",0)}/{fr.get(\"total\",0)} = {fr.get(\"accuracy\",0):.1%}')
lat = s.get('latency', {})
print(f'E2E median: {lat.get(\"e2e_median_ms\",0):.0f}ms, max: {lat.get(\"e2e_max_ms\",0):.0f}ms')
print(f'Play OK rate: {lat.get(\"play_ok_rate\",0):.1%}')
for k, v in s.get('pass_criteria', {}).items():
    mark = 'PASS' if v['pass'] else 'FAIL'
    print(f'  {k}: {v[\"actual\"]} (threshold: {v[\"threshold\"]}) [{mark}]')
"
fi

echo ""
echo "=== Test Complete ==="
