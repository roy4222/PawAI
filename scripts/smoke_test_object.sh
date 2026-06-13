#!/usr/bin/env bash
# Object Smoke Test - static lane checks plus optional cup HITL evidence.
#
# Preconditions: demo lane is running on the Jetson (pawai demo start), and
# ROS2 environment has been sourced by the caller.
#
# Usage:
#   bash scripts/smoke_test_object.sh             # static-only checks
#   bash scripts/smoke_test_object.sh --with-cup  # wait 60s for a cup event

set -uo pipefail

WITH_CUP=0
PASS=0
FAIL=0

OBJECT_NODE_PATTERN="object_perception"
DEBUG_TOPIC="/perception/object/debug_image"
EVENT_TOPIC="/event/object_detected"
SMOKE_OUT="artifacts/baseline/smoke_object.jsonl"

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
  echo "======================================="
  echo "  RESULT: $PASS passed, $FAIL failed"
  echo "======================================="
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
    --with-cup)
      WITH_CUP=1
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
echo "======================================="
echo "  Object Smoke Test"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================="

# Static check 1: object node alive
echo ""
echo "[STATIC] Checking object node..."
NODES=$(ros2 node list 2>/dev/null || true)
if echo "$NODES" | grep -q "$OBJECT_NODE_PATTERN"; then
  pass "object node found ($OBJECT_NODE_PATTERN)"
else
  fail "object node not found - is the object lane running?"
  finish
fi

# Static check 2: debug image publishes at demo-useful rate
echo ""
echo "[STATIC] Checking debug image rate..."
HZ_OUTPUT=$(timeout 8 ros2 topic hz "$DEBUG_TOPIC" 2>&1 || true)
DEBUG_RATE=$(printf "%s\n" "$HZ_OUTPUT" | awk '/average rate:/ {rate=$3} END {if (rate == "") rate=0; print rate}')
if awk -v rate="$DEBUG_RATE" 'BEGIN {exit !(rate >= 3)}'; then
  pass "$DEBUG_TOPIC average rate: $DEBUG_RATE Hz"
else
  fail "$DEBUG_TOPIC average rate below 3 Hz: $DEBUG_RATE Hz"
fi

# Static check 3: object event topic has a publisher
echo ""
echo "[STATIC] Checking object event publisher..."
INFO=$(ros2 topic info "$EVENT_TOPIC" 2>/dev/null || true)
PUBLISHERS=$(printf "%s\n" "$INFO" | awk -F': ' '/Publisher count:/ {print $2; exit}')
PUBLISHERS="${PUBLISHERS:-0}"
if [ "$PUBLISHERS" -ge 1 ] 2>/dev/null; then
  pass "$EVENT_TOPIC publisher count: $PUBLISHERS"
else
  fail "$EVENT_TOPIC publisher count: $PUBLISHERS"
fi

if [ "$FAIL" -gt 0 ]; then
  finish
fi

if [ "$WITH_CUP" -eq 0 ]; then
  echo ""
  echo "[STATIC] PASS (static-only mode)"
  finish
fi

# HITL check: collect a cup event with gesture isolated out of the measurement.
echo ""
echo "[HITL] Waiting up to 60s for cup object event..."
SCENARIO_ID="smoke_cup_$(date +%s)"
if python3 benchmarks/scripts/capture_baseline_round.py percep \
    --capability object.cup \
    --scenario-id "$SCENARIO_ID" \
    --expected cup \
    --kind positive \
    --window 60 \
    --object-topic /event/object_detected \
    --gesture-topic /__no_gesture__ \
    --out "$SMOKE_OUT"; then
  LATEST_RECORD=$(tail -n 1 "$SMOKE_OUT" 2>/dev/null || true)
  if printf "%s\n" "$LATEST_RECORD" | grep -q '"pass_fail": "pass"' && \
     printf "%s\n" "$LATEST_RECORD" | grep -q '"predicted_label": "cup"' && \
     printf "%s\n" "$LATEST_RECORD" | grep -q "\"scenario_id\": \"$SCENARIO_ID\""; then
    pass "received cup event (scenario_id=$SCENARIO_ID)"
  else
    fail "no cup pass record written to $SMOKE_OUT"
  fi
else
  fail "capture_baseline_round.py cup capture failed"
fi

finish
