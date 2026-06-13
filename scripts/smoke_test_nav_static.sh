#!/usr/bin/env bash
# Nav Static Smoke Test - read-only stack checks.
#
# Preconditions: nav capability lane is running on the Jetson, and the caller
# has sourced the ROS2 environment.
#
# Usage:
#   bash scripts/smoke_test_nav_static.sh

set -uo pipefail

PASS=0
FAIL=0

SCAN_TOPIC="/scan_rplidar"
AMCL_TOPIC="/amcl_pose"
REACTIVE_TOPIC="/state/reactive_stop/status"
NODE_PATTERN="/(nav_action_server_node|amcl|reactive_stop_node|bt_navigator)$"
REQUIRED_ACTIONS=(
  "/nav/goto_relative"
  "/nav/goto_named"
  "/nav/run_route"
  "/log_pose"
)

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

publisher_count() {
  local topic="$1"
  local info
  local publishers

  info=$(ros2 topic info "$topic" 2>/dev/null || true)
  publishers=$(printf "%s\n" "$info" | awk -F': ' '/Publisher count:/ {print $2; exit}')
  publishers="${publishers:-0}"
  printf "%s" "$publishers"
}

echo ""
echo "======================================="
echo "  Nav Static Smoke Test"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================="

# Static check 1: nav stack has at least one expected node.
echo ""
echo "[STATIC] Checking nav nodes..."
NODES=$(ros2 node list 2>/dev/null || true)
if printf "%s\n" "$NODES" | grep -Eq "$NODE_PATTERN"; then
  FOUND_NODES=$(printf "%s\n" "$NODES" | grep -E "$NODE_PATTERN" | tr '\n' ' ')
  pass "nav node(s) found: $FOUND_NODES"
else
  fail "expected nav node not found"
fi

# Static check 2: RPLIDAR scan rate is high enough for nav safety gates.
echo ""
echo "[STATIC] Checking $SCAN_TOPIC rate..."
HZ_OUTPUT=$(timeout 8 ros2 topic hz "$SCAN_TOPIC" 2>&1 || true)
SCAN_RATE=$(printf "%s\n" "$HZ_OUTPUT" | awk '/average rate:/ {rate=$3} END {if (rate == "") rate=0; print rate}')
if awk -v rate="$SCAN_RATE" 'BEGIN {exit !(rate >= 10)}'; then
  pass "$SCAN_TOPIC average rate: $SCAN_RATE Hz"
else
  fail "$SCAN_TOPIC average rate below 10 Hz: $SCAN_RATE Hz"
fi

# Static check 3: AMCL pose is exposed by the localization stack.
echo ""
echo "[STATIC] Checking $AMCL_TOPIC publisher..."
AMCL_PUBLISHERS=$(publisher_count "$AMCL_TOPIC")
if [ "$AMCL_PUBLISHERS" -ge 1 ] 2>/dev/null; then
  pass "$AMCL_TOPIC publisher count: $AMCL_PUBLISHERS"
else
  fail "$AMCL_TOPIC publisher count: $AMCL_PUBLISHERS"
fi

# Static check 4: nav capability action servers are discoverable.
echo ""
echo "[STATIC] Checking nav action servers..."
ACTIONS=$(ros2 action list 2>/dev/null || true)
for action in "${REQUIRED_ACTIONS[@]}"; do
  if printf "%s\n" "$ACTIONS" | grep -Fxq "$action"; then
    pass "action found: $action"
  else
    fail "action missing: $action"
  fi
done

# Static check 5: reactive stop status is visible.
echo ""
echo "[STATIC] Checking $REACTIVE_TOPIC publisher..."
REACTIVE_PUBLISHERS=$(publisher_count "$REACTIVE_TOPIC")
if [ "$REACTIVE_PUBLISHERS" -ge 1 ] 2>/dev/null; then
  pass "$REACTIVE_TOPIC publisher count: $REACTIVE_PUBLISHERS"
else
  fail "$REACTIVE_TOPIC publisher count: $REACTIVE_PUBLISHERS"
fi

finish
