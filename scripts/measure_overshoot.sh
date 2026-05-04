#!/usr/bin/env bash
# PR1a — Measure overshoot under different controller_server.FollowPath.max_vel_x.
#
# Usage (run on Jetson, after start_nav_capability_demo_tmux.sh has Nav2 active and
# Foxglove initialpose set):
#
#   bash scripts/measure_overshoot.sh <label> <max_vel_x|keep>
#
# Examples:
#   bash scripts/measure_overshoot.sh baseline keep    # use yaml default
#   bash scripts/measure_overshoot.sh slow_30 0.30
#   bash scripts/measure_overshoot.sh slow_45 0.45
#
# Output:
#   logs/overshoot/<UTC>-<label>/
#     bag/run/  (ros2 bag record of /amcl_pose /cmd_vel /cmd_vel_obstacle
#                /tf /tf_static /odom /scan_rplidar
#                /parameter_events (global)
#                /capability/nav_ready /state/nav/paused)
#     run_<n>.json (action send_goal stdout/stderr)
#     params_before.txt / params_after.txt
#
# Tunables (env):
#   RUNS=3                # number of goto_relative runs per label
#   DISTANCE=0.5          # action goal distance (meters)
#   MAX_SPEED_FIELD=0.0   # action goal max_speed field; 0 = unset
#   PAUSE_BETWEEN_RUNS=0  # if 1, prompt operator to reset Go2 to start mark
#                         # before each run (recommended for small rooms)
#
set -euo pipefail

LABEL="${1:?label required, e.g. baseline | slow_30 | slow_45}"
TARGET="${2:?max_vel_x value or 'keep' required}"
RUNS="${RUNS:-3}"
DISTANCE="${DISTANCE:-0.5}"
MAX_SPEED_FIELD="${MAX_SPEED_FIELD:-0.0}"
PAUSE_BETWEEN_RUNS="${PAUSE_BETWEEN_RUNS:-0}"

OUT_DIR="logs/overshoot/$(date -u +%Y%m%dT%H%M%SZ)-${LABEL}"
mkdir -p "${OUT_DIR}/bag"

echo "[measure] OUT=${OUT_DIR} target_max_vel_x=${TARGET} runs=${RUNS} distance=${DISTANCE} pause=${PAUSE_BETWEEN_RUNS}"

# Pre-declare so cleanup trap can reference safely
BAG_PID=""
ORIG=""

cleanup() {
    # Always-runs cleanup: stop bag + restore param. Safe to call multiple times.
    if [[ -n "${BAG_PID}" ]]; then
        kill -INT "${BAG_PID}" 2>/dev/null || true
        wait "${BAG_PID}" 2>/dev/null || true
        BAG_PID=""
    fi
    if [[ "${TARGET}" != "keep" && -n "${ORIG}" ]]; then
        echo "[measure-cleanup] restoring max_vel_x to ${ORIG}" >&2
        ros2 param set /controller_server FollowPath.max_vel_x "${ORIG}" \
            > /dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

# Snapshot pre-test params
ros2 param get /controller_server FollowPath.max_vel_x \
    > "${OUT_DIR}/params_before.txt" 2>&1 || true
ros2 param get /controller_server FollowPath.xy_goal_tolerance \
    >> "${OUT_DIR}/params_before.txt" 2>&1 || true

# Extract original numeric value for restore (best-effort)
ORIG="$(grep -oE '[0-9]+\.[0-9]+' "${OUT_DIR}/params_before.txt" | head -1 || echo 0.5)"

# Override if requested
if [[ "${TARGET}" != "keep" ]]; then
    echo "[measure] ros2 param set FollowPath.max_vel_x ${TARGET} (orig=${ORIG})"
    ros2 param set /controller_server FollowPath.max_vel_x "${TARGET}"
    sleep 1
fi

# Start bag in background.
# Note: /parameter_events is the GLOBAL parameter event topic (not per-node).
TOPICS=(
    /amcl_pose
    /cmd_vel
    /cmd_vel_obstacle
    /tf
    /tf_static
    /odom
    /scan_rplidar
    /parameter_events
    /capability/nav_ready
    /state/nav/paused
)
ros2 bag record -o "${OUT_DIR}/bag/run" "${TOPICS[@]}" &
BAG_PID=$!
sleep 2

# Send goals
for i in $(seq 1 "${RUNS}"); do
    if [[ "${PAUSE_BETWEEN_RUNS}" == "1" ]]; then
        echo ""
        echo "[measure] >>> 把 Go2 放回地板膠帶起點,Foxglove 重設 initialpose 後按 Enter 繼續(run ${i}/${RUNS})"
        # shellcheck disable=SC2034
        read -r _ack
    fi
    echo "[measure] === run ${i} ==="
    ros2 action send_goal /nav/goto_relative \
        go2_interfaces/action/GotoRelative \
        "{distance: ${DISTANCE}, max_speed: ${MAX_SPEED_FIELD}}" \
        > "${OUT_DIR}/run_${i}.txt" 2>&1 || true
    sleep 5  # let robot settle + AMCL re-converge between goals
done

# Stop bag (cleanup trap also handles this if we exit early)
sleep 1
kill -INT "${BAG_PID}" 2>/dev/null || true
wait "${BAG_PID}" 2>/dev/null || true
BAG_PID=""  # mark so cleanup trap doesn't double-kill

# Restore param (cleanup trap also handles this)
if [[ "${TARGET}" != "keep" ]]; then
    echo "[measure] restoring max_vel_x to ${ORIG}"
    ros2 param set /controller_server FollowPath.max_vel_x "${ORIG}"
fi
ros2 param get /controller_server FollowPath.max_vel_x \
    > "${OUT_DIR}/params_after.txt" 2>&1 || true

echo "[measure] DONE: ${OUT_DIR}"
ls -la "${OUT_DIR}"
ros2 bag info "${OUT_DIR}/bag/run" 2>&1 | head -20 || true
