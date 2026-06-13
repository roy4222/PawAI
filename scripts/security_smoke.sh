#!/usr/bin/env bash
#
# Security smoke script for manual HITL penetration checks against a live Studio gateway.
# CI does NOT run this script; pre-commit should only run `bash -n scripts/security_smoke.sh`.
#
# Auth-on gateway launch example:
#   GATEWAY_AUTH_TOKEN='replace-me' \
#   GATEWAY_ALLOWED_ORIGINS='http://127.0.0.1:3000,http://localhost:3000' \
#   GATEWAY_HOST='0.0.0.0' GATEWAY_PORT='8080' \
#   python3 pawai-studio/gateway/studio_gateway.py
#
# Usage:
#   HOST=127.0.0.1 PORT=8080 GATEWAY_AUTH_TOKEN='replace-me' scripts/security_smoke.sh
#   scripts/security_smoke.sh 127.0.0.1 8080
#
# Each check maps to a security finding id and prints that id in its result line.
# The A-11 trace export check expects a token-system-OFF gateway instance because
# export_access must reject redact=0 with HTTP 403 when no auth token system exists.
#
# This script only curls a running gateway and prints ROS2 HITL commands. It does
# not modify source code, robot configuration, or ROS topics/actions by itself.

set -u

HOST="${1:-${HOST:-127.0.0.1}}"
PORT="${2:-${PORT:-8080}}"
BASE_URL="http://${HOST}:${PORT}"
TOKEN="${GATEWAY_AUTH_TOKEN:-}"
FAILURES=0

pass() {
  printf 'PASS [%s] %s\n' "$1" "$2"
}

fail() {
  printf 'FAIL [%s] %s\n' "$1" "$2"
  FAILURES=$((FAILURES + 1))
}

info() {
  printf 'INFO [%s] %s\n' "$1" "$2"
}

expect_http_code() {
  local finding="$1"
  local expected="$2"
  local actual="$3"
  local msg="$4"

  if [[ "$actual" == "$expected" ]]; then
    pass "$finding" "${msg}: got HTTP ${actual}"
  else
    fail "$finding" "${msg}: expected HTTP ${expected}, got HTTP ${actual}"
  fi
}

expect_not_http_code() {
  local finding="$1"
  local rejected="$2"
  local actual="$3"
  local msg="$4"

  if [[ "$actual" != "$rejected" ]]; then
    pass "$finding" "${msg}: got HTTP ${actual}, not ${rejected}"
  else
    fail "$finding" "${msg}: expected anything except HTTP ${rejected}, got HTTP ${actual}"
  fi
}

printf 'Security smoke target: %s\n' "$BASE_URL"
if [[ -n "$TOKEN" ]]; then
  info "setup" "GATEWAY_AUTH_TOKEN is set in this shell; no-token checks intentionally omit it"
else
  info "setup" "GATEWAY_AUTH_TOKEN is not set in this shell"
fi

# [MOT-01 + GW-02] No-token state-changing skill request must be rejected in auth-on mode.
skill_code="$(
  curl -o /dev/null -s -w '%{http_code}' \
    --max-time 5 \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{}' \
    "${BASE_URL}/api/skill_request"
)"
expect_http_code \
  "MOT-01 + GW-02" \
  "401" \
  "$skill_code" \
  "no-token POST /api/skill_request is rejected in auth-on mode"

# [GW-06/GW-07/EXP-04] Forged Origin websocket upgrade must not reach 101 Switching Protocols.
ws_events_code="$(
  curl -o /dev/null -s -w '%{http_code}' \
    --max-time 5 \
    --http1.1 \
    -H 'Connection: Upgrade' \
    -H 'Upgrade: websocket' \
    -H 'Origin: http://evil.example' \
    "${BASE_URL}/ws/events"
)"
expect_not_http_code \
  "GW-06/GW-07/EXP-04" \
  "101" \
  "$ws_events_code" \
  "forged-Origin websocket handshake to /ws/events is rejected"

# [A-11 trace export] Token-system-OFF export_access must reject unredacted export with HTTP 403.
trace_export_code="$(
  curl -o /dev/null -s -w '%{http_code}' \
    --max-time 5 \
    "${BASE_URL}/api/trace/export?redact=0"
)"
expect_http_code \
  "A-11 trace export" \
  "403" \
  "$trace_export_code" \
  "GET /api/trace/export?redact=0 with no token while token system is OFF"

printf '\nManual HITL-on-Jetson checks; these are informational and do not affect exit status.\n'

# [MOT-01 whitelist] Publish a banned WebRTC api_id and verify driver rejection log.
info "MOT-01 whitelist" "manual ROS2 command for banned api_id 1030:"
printf '%s\n' \
  "  ros2 topic pub --once /webrtc_req go2_interfaces/msg/WebRtcReq \"{id: 0, topic: 'rt/api/sport/request', api_id: 1030, parameter: '{}', priority: 0}\""
info "MOT-01 whitelist" "expected go2_driver log: Rejected WebRTC request api_id=1030 robot_id=0: blacklisted"

# [MOT-04] Send a route_id path traversal attempt and verify rejection.
info "MOT-04" "manual ROS2 action command for route_id path traversal:"
printf '%s\n' \
  "  ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \"{route_id: '../evil', loop: false}\""
info "MOT-04" "expected rejection: route_id '../evil' is rejected and no route file outside the route root is opened"

if (( FAILURES > 0 )); then
  printf '\nSecurity smoke completed with %d failure(s).\n' "$FAILURES"
  exit 1
fi

printf '\nSecurity smoke completed with all HTTP-checkable assertions passing.\n'
