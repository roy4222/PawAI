#!/usr/bin/env bash
# Vision Smoke Test — static lane checks plus optional HITL event evidence.
#
# 前提：demo lane 已在 Jetson 上跑（pawai demo start），且已 source ROS2 env。
#
# Usage:
#   bash scripts/smoke_test_vision.sh                  # static-only checks
#   bash scripts/smoke_test_vision.sh --with-events 3  # wait for 3 gesture/pose events

set -uo pipefail

WITH_EVENTS=0
PASS=0
FAIL=0

VISION_NODE_PATTERN="vision_perception"
STATUS_TOPIC="/vision_perception/status_image"
GESTURE_TOPIC="/event/gesture_detected"
POSE_TOPIC="/event/pose_detected"

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
}

pass() {
  echo "  [OK] $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "  [FAIL] $1"
  FAIL=$((FAIL + 1))
}

summary() {
  echo ""
  echo "═══════════════════════════════════════"
  echo "  RESULT: $PASS passed, $FAIL failed"
  echo "═══════════════════════════════════════"
  echo ""
}

finish() {
  summary
  if [ "$FAIL" -gt 0 ]; then
    exit 1
  fi
  exit 0
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --with-events)
      shift
      if [ "$#" -eq 0 ] || ! [[ "$1" =~ ^[0-9]+$ ]]; then
        echo "[FAIL] --with-events requires a non-negative integer"
        usage
        exit 1
      fi
      WITH_EVENTS="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[FAIL] unknown argument: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

echo ""
echo "═══════════════════════════════════════"
echo "  Vision Smoke Test"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════"

# ── Static check 1: vision node alive ──
echo ""
echo "[STATIC] Checking vision node..."
NODES=$(ros2 node list 2>/dev/null || true)
if echo "$NODES" | grep -q "$VISION_NODE_PATTERN"; then
  pass "vision node found ($VISION_NODE_PATTERN)"
else
  fail "vision node not found — is the vision lane running?"
  finish
fi

# ── Static check 2: status image is publishing ──
echo ""
echo "[STATIC] Checking status image rate..."
HZ_OUTPUT=$(timeout 8 ros2 topic hz "$STATUS_TOPIC" 2>&1 || true)
STATUS_RATE=$(printf "%s\n" "$HZ_OUTPUT" | awk '/average rate:/ {rate=$3} END {if (rate == "") rate=0; print rate}')
if awk -v rate="$STATUS_RATE" 'BEGIN {exit !(rate > 0)}'; then
  pass "$STATUS_TOPIC average rate: $STATUS_RATE Hz"
else
  fail "$STATUS_TOPIC has no measurable hz > 0"
fi

# ── Static check 3: event topics exist and have publishers ──
echo ""
echo "[STATIC] Checking event topic publishers..."
TOPICS=$(ros2 topic list 2>/dev/null || true)
check_topic_publisher() {
  local topic="$1"
  local info
  local publishers

  if ! echo "$TOPICS" | grep -Fxq "$topic"; then
    fail "$topic not found"
    return
  fi

  info=$(ros2 topic info "$topic" 2>/dev/null || true)
  publishers=$(printf "%s\n" "$info" | awk -F': ' '/Publisher count:/ {print $2; exit}')
  publishers="${publishers:-0}"
  if [ "$publishers" -ge 1 ] 2>/dev/null; then
    pass "$topic publisher count: $publishers"
  else
    fail "$topic publisher count: $publishers"
  fi
}

check_topic_publisher "$GESTURE_TOPIC"
check_topic_publisher "$POSE_TOPIC"

if [ "$FAIL" -gt 0 ]; then
  finish
fi

if [ "$WITH_EVENTS" -eq 0 ]; then
  echo ""
  echo "[STATIC] PASS (static-only mode)"
  finish
fi

# ── HITL check: wait for live gesture/pose events ──
echo ""
echo "[HITL] Waiting up to 60s for $WITH_EVENTS gesture/pose event(s)..."
EVENT_LOG=$(mktemp)
PIDS=()

cleanup_event_echo() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  rm -f "$EVENT_LOG"
}
trap cleanup_event_echo EXIT

ros2 topic echo "$GESTURE_TOPIC" >>"$EVENT_LOG" 2>/dev/null &
PIDS+=("$!")
ros2 topic echo "$POSE_TOPIC" >>"$EVENT_LOG" 2>/dev/null &
PIDS+=("$!")

EVENT_COUNT=0
DEADLINE=$((SECONDS + 60))
while [ "$SECONDS" -lt "$DEADLINE" ]; do
  EVENT_COUNT=$(grep -c '^---$' "$EVENT_LOG" 2>/dev/null || true)
  if [ "$EVENT_COUNT" -ge "$WITH_EVENTS" ]; then
    pass "received $EVENT_COUNT/$WITH_EVENTS gesture/pose event(s)"
    finish
  fi
  sleep 1
done

fail "received $EVENT_COUNT/$WITH_EVENTS gesture/pose event(s) before timeout"
finish
