#!/usr/bin/env bash
# E2E Health Check — layered diagnostic for ASR → LLM → TTS → Go2 pipeline.
#
# Usage: bash scripts/e2e_health_check.sh [--llm-endpoint URL]
#
# Checks each layer and reports [OK] / [FAIL] with actionable messages.
# Designed to run in ~3 seconds.

set -uo pipefail

LLM_ENDPOINT="${LLM_ENDPOINT:-http://localhost:8000/v1/chat/completions}"

for arg in "$@"; do
  case "$arg" in
    --llm-endpoint=*) LLM_ENDPOINT="${arg#*=}" ;;
  esac
done

LLM_HEALTH_URL="${LLM_ENDPOINT%/chat/completions}/models"

PASS=0
FAIL=0
TOTAL=5

ok()   { echo "  [OK]   $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  [WARN] $1"; }
info() { echo "  [INFO] $1"; }

echo ""
echo "═══════════════════════════════════════"
echo "  E2E Health Check ($(date '+%H:%M:%S'))"
echo "═══════════════════════════════════════"

# ── Layer 0: LLM API ──
echo ""
echo "── Layer 0: LLM API ──"
if curl -sf --max-time 3 "$LLM_HEALTH_URL" >/dev/null 2>&1; then
  MODEL_INFO=$(curl -sf --max-time 3 "$LLM_HEALTH_URL" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['id'] if d.get('data') else 'unknown')" 2>/dev/null || echo "unknown")
  ok "LLM reachable ($LLM_HEALTH_URL) — model: $MODEL_INFO"
else
  fail "LLM unreachable: $LLM_HEALTH_URL"
  info "Try: ssh -f -N -L 8000:localhost:8000 YOUR_USER@YOUR_GPU_HOST"
fi

# ── Layer 1: ROS2 Nodes ──
echo ""
echo "── Layer 1: ROS2 Nodes ──"
EXPECTED_NODES=("go2_driver_node" "stt_intent_node" "tts_node" "llm_bridge_node")
ACTIVE_NODES=$(ros2 node list 2>/dev/null || echo "")

if [ -z "$ACTIVE_NODES" ]; then
  fail "No ROS2 nodes active (ros2 daemon may be down)"
else
  ALL_PRESENT=true
  for node in "${EXPECTED_NODES[@]}"; do
    if echo "$ACTIVE_NODES" | grep -q "$node"; then
      info "$node — running"
    else
      warn "$node — NOT FOUND"
      ALL_PRESENT=false
    fi
  done
  if $ALL_PRESENT; then
    ok "All 4 expected nodes running"
  else
    fail "Some nodes missing (check tmux panes for errors)"
  fi
fi

# ── Layer 2: Topic Wiring ──
echo ""
echo "── Layer 2: Topic Wiring ──"
TOPICS_OK=true
check_topic() {
  local topic="$1"
  local expect_pub="${2:-1}"
  local topic_info
  topic_info=$(ros2 topic info "$topic" 2>/dev/null || echo "")
  if [ -z "$topic_info" ]; then
    warn "$topic — not found"
    TOPICS_OK=false
    return
  fi
  local pub_count sub_count
  pub_count=$(echo "$topic_info" | grep -oP 'Publisher count: \K\d+' || echo "0")
  sub_count=$(echo "$topic_info" | grep -oP 'Subscriber count: \K\d+' || echo "0")
  if [ "$pub_count" -ge "$expect_pub" ] && [ "$sub_count" -ge 1 ]; then
    info "$topic — ${pub_count} pub / ${sub_count} sub"
  else
    warn "$topic — ${pub_count} pub / ${sub_count} sub (expected ≥${expect_pub} pub, ≥1 sub)"
    TOPICS_OK=false
  fi
}

check_topic "/event/speech_intent_recognized"
check_topic "/tts"
check_topic "/webrtc_req"
check_topic "/tts_audio_raw"

if $TOPICS_OK; then
  ok "All critical topics wired"
else
  fail "Topic wiring incomplete"
fi

# ── Layer 3: State Topics (live data) ──
echo ""
echo "── Layer 3: State Topics ──"
STATES_OK=true

# LLM Bridge state
LLM_STATE=$(timeout 3 ros2 topic echo --once /state/interaction/llm_bridge std_msgs/msg/String 2>/dev/null | head -5 || echo "")
if [ -n "$LLM_STATE" ]; then
  LLM_STATUS=$(echo "$LLM_STATE" | python3 -c "
import sys, json
for line in sys.stdin:
  line = line.strip()
  if line.startswith(\"data:\"):
    d = json.loads(line[6:].strip().strip(\"'\").strip('\"'))
    state = d.get('state', '?')
    err = d.get('last_error', '')
    reply = d.get('last_reply', '')[:40]
    print(f'state={state} err={err} last_reply={reply}')
    break
" 2>/dev/null || echo "parse error")
  info "llm_bridge: $LLM_STATUS"
else
  warn "llm_bridge state: no data within 3s"
  STATES_OK=false
fi

# Speech state
SPEECH_STATE=$(timeout 3 ros2 topic echo --once /state/interaction/speech std_msgs/msg/String 2>/dev/null | head -5 || echo "")
if [ -n "$SPEECH_STATE" ]; then
  SPEECH_STATUS=$(echo "$SPEECH_STATE" | python3 -c "
import sys, json
for line in sys.stdin:
  line = line.strip()
  if line.startswith(\"data:\"):
    d = json.loads(line[6:].strip().strip(\"'\").strip('\"'))
    state = d.get('state', '?')
    provider = d.get('last_provider', '?')
    err = d.get('last_error', '')
    print(f'state={state} provider={provider} err={err}')
    break
" 2>/dev/null || echo "parse error")
  info "speech: $SPEECH_STATUS"
else
  warn "speech state: no data within 3s"
  STATES_OK=false
fi

if $STATES_OK; then
  ok "State topics publishing"
else
  fail "Some state topics not publishing"
fi

# ── Layer 4: Audio Pipeline ──
echo ""
echo "── Layer 4: Audio Pipeline ──"
DEBUG_WAVS=$(ls -lt /tmp/tts_debug_*.wav 2>/dev/null | head -3)
if [ -n "$DEBUG_WAVS" ]; then
  ok "Audio track active — recent debug WAVs:"
  echo "$DEBUG_WAVS" | while read -r line; do
    info "  $line"
  done
else
  LAST_TTS=$(timeout 2 ros2 topic echo --once /state/tts_playing std_msgs/msg/Bool 2>/dev/null | grep "data:" | head -1 || echo "")
  if [ -n "$LAST_TTS" ]; then
    warn "TTS topic exists but no debug WAVs in /tmp/ (audio track may not have played yet)"
  else
    warn "No debug WAVs and no TTS state — audio pipeline not yet exercised"
  fi
  fail "No audio track evidence"
fi

# ── Summary ──
echo ""
echo "═══════════════════════════════════════"
if [ "$FAIL" -eq 0 ]; then
  echo "  RESULT: $PASS/$TOTAL layers OK"
else
  echo "  RESULT: $PASS/$TOTAL OK, $FAIL/$TOTAL FAIL"
  echo ""
  echo "  Troubleshooting:"
  echo "    Layer 0 FAIL → SSH tunnel or vLLM down"
  echo "    Layer 1 FAIL → Node crashed, check tmux panes"
  echo "    Layer 2 FAIL → Topic wiring broken, clean_all + restart"
  echo "    Layer 3 FAIL → Node alive but not publishing state"
  echo "    Layer 4 FAIL → Try: ros2 topic pub --once /tts std_msgs/msg/String '{data: \"測試\"}'"
fi
echo "═══════════════════════════════════════"
echo ""
