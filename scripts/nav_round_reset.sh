#!/usr/bin/env bash
# Reset one navigation obstacle-test round without restarting the stack.
#
# Usage:
#   bash scripts/nav_round_reset.sh
#   bash scripts/nav_round_reset.sh --quick   # skip /cmd_vel quiet wait

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SERVICE_TIMEOUT="${SERVICE_TIMEOUT:-5}"
TOPIC_TIMEOUT="${TOPIC_TIMEOUT:-4}"
QUIET_TIMEOUT="${QUIET_TIMEOUT:-10}"
QUIET_WINDOW="${QUIET_WINDOW:-2.0}"
QUIET_EPS="${QUIET_EPS:-0.01}"

QUICK=0
if [[ "${1:-}" == "--quick" ]]; then
    QUICK=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: bash scripts/nav_round_reset.sh [--quick]"
    exit 2
fi

FAILURES=()

EMERGENCY_LOCK_RELEASED="FAIL"
NAV_RESUMED="FAIL"
LOCAL_COSTMAP_CLEARED="FAIL"
GLOBAL_COSTMAP_CLEARED="FAIL"
NAV_READY="unknown"
DEPTH_CLEAR="unknown"
NAV_PAUSED="unknown"
CMD_VEL_QUIET="SKIPPED"

source_ros_env() {
    # Running from the nav demo monitor window already has this sourced. These
    # fallbacks make cold validation and direct SSH usage less brittle.
    export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/nav_round_reset_ros_log}"
    mkdir -p "$ROS_LOG_DIR"

    set +u
    if ! command -v ros2 >/dev/null 2>&1; then
        # shellcheck disable=SC1091
        [[ -f /opt/ros/humble/setup.bash ]] && source /opt/ros/humble/setup.bash
    fi
    # shellcheck disable=SC1091
    [[ -f "$REPO_ROOT/install/setup.bash" ]] && source "$REPO_ROOT/install/setup.bash"
    set -u
}

record_failure() {
    FAILURES+=("$1")
}

run_best_effort() {
    local label="$1"
    shift
    local output

    set +e
    output="$("$@" 2>&1)"
    local rc=$?
    set -e

    if [[ $rc -eq 0 ]]; then
        echo "  OK: $label"
        return 0
    fi

    echo "  FAIL: $label: ${output//$'\n'/ }"
    return "$rc"
}

call_service() {
    local service="$1"
    local type="$2"
    local request="${3:-}"
    if [[ -z "$request" ]]; then
        request="{}"
    fi

    timeout "$SERVICE_TIMEOUT" ros2 service call "$service" "$type" "$request"
}

read_bool_topic() {
    local topic="$1"
    local value

    set +e
    value="$(
        timeout "$TOPIC_TIMEOUT" ros2 topic echo --once \
            --qos-durability transient_local \
            --qos-reliability reliable \
            "$topic" std_msgs/msg/Bool 2>/dev/null \
            | awk '/data:/ {print $2; exit}'
    )"
    local rc=$?
    set -e

    if [[ $rc -eq 0 && "$value" =~ ^(true|false)$ ]]; then
        printf "%s" "$value"
    else
        printf "unknown"
        return 1
    fi
}

wait_cmd_vel_quiet() {
    python3 - "$QUIET_TIMEOUT" "$QUIET_WINDOW" "$QUIET_EPS" <<'PY'
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist

timeout_s = float(sys.argv[1])
quiet_window_s = float(sys.argv[2])
eps = float(sys.argv[3])

rclpy.init()
node = rclpy.create_node("nav_round_reset_quiet_check")

start = time.monotonic()
last_motion = start

def on_cmd_vel(msg: Twist) -> None:
    global last_motion
    x = float(msg.linear.x)
    az = float(msg.angular.z)
    if not math.isfinite(x) or not math.isfinite(az):
        last_motion = time.monotonic()
        return
    if abs(x) >= eps or abs(az) >= eps:
        last_motion = time.monotonic()

node.create_subscription(Twist, "/cmd_vel", on_cmd_vel, 10)

try:
    while rclpy.ok():
        now = time.monotonic()
        if now - last_motion >= quiet_window_s:
            print("quiet")
            sys.exit(0)
        if now - start >= timeout_s:
            print("timeout")
            sys.exit(1)
        rclpy.spin_once(node, timeout_sec=0.05)
finally:
    node.destroy_node()
    rclpy.shutdown()
PY
}

echo "=== nav_round_reset ==="
source_ros_env

echo "[1/6] Release emergency lock..."
if run_best_effort "emergency release" \
    python3 "$REPO_ROOT/nav_capability/scripts/emergency_stop.py" release; then
    EMERGENCY_LOCK_RELEASED="OK"
else
    record_failure "emergency_lock_released"
fi

echo "[2/6] Resume nav (/state/nav/paused=false)..."
if run_best_effort "nav resume" \
    call_service /nav/resume std_srvs/srv/Trigger "{}"; then
    NAV_RESUMED="OK"
else
    record_failure "nav_resumed"
fi

echo "[3/6] Clear costmaps..."
if run_best_effort "local costmap clear" \
    call_service /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap "{}"; then
    LOCAL_COSTMAP_CLEARED="OK"
else
    record_failure "local_costmap_cleared"
fi

if run_best_effort "global costmap clear" \
    call_service /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap "{}"; then
    GLOBAL_COSTMAP_CLEARED="OK"
else
    record_failure "global_costmap_cleared"
fi

echo "[4/6] Snapshot capability gates..."
NAV_READY="$(read_bool_topic /capability/nav_ready || true)"
echo "  nav_ready=$NAV_READY"
DEPTH_CLEAR="$(read_bool_topic /capability/depth_clear || true)"
echo "  depth_clear=$DEPTH_CLEAR"
NAV_PAUSED="$(read_bool_topic /state/nav/paused || true)"
echo "  nav_paused=$NAV_PAUSED"

[[ "$NAV_READY" == "true" ]] || record_failure "nav_ready=$NAV_READY"
[[ "$DEPTH_CLEAR" == "true" ]] || record_failure "depth_clear=$DEPTH_CLEAR"
[[ "$NAV_PAUSED" == "false" ]] || record_failure "nav_paused=$NAV_PAUSED"

echo "[5/6] Wait /cmd_vel quiet ${QUIET_WINDOW}s..."
if [[ "$QUICK" -eq 1 ]]; then
    echo "  SKIPPED (--quick)"
else
    if run_best_effort "cmd_vel quiet" wait_cmd_vel_quiet; then
        CMD_VEL_QUIET="OK"
    else
        CMD_VEL_QUIET="TIMEOUT"
        record_failure "cmd_vel_quiet"
    fi
fi

echo "[6/6] Summary"
echo "===== nav_round_reset ====="
printf "emergency_lock_released : %s\n" "$EMERGENCY_LOCK_RELEASED"
printf "nav_resumed             : %s\n" "$NAV_RESUMED"
printf "local_costmap_cleared   : %s\n" "$LOCAL_COSTMAP_CLEARED"
printf "global_costmap_cleared  : %s\n" "$GLOBAL_COSTMAP_CLEARED"
printf "nav_ready               : %s\n" "$NAV_READY"
printf "depth_clear             : %s\n" "$DEPTH_CLEAR"
printf "nav_paused              : %s\n" "$NAV_PAUSED"
printf "cmd_vel_quiet           : %s\n" "$CMD_VEL_QUIET"
echo "---"

if [[ ${#FAILURES[@]} -eq 0 ]]; then
    echo "READY"
    exit 0
fi

echo "NOT-READY: ${FAILURES[*]}"
exit 1
