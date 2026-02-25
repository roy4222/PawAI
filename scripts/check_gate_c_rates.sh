#!/usr/bin/env zsh

set -euo pipefail

if [ -z "${ZSH_VERSION:-}" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

WARMUP_SEC="${1:-5}"
MEASURE_SEC="${2:-10}"

echo "[Gate C rate check] warmup=${WARMUP_SEC}s measure=${MEASURE_SEC}s"
echo "[1/4] Wait for first /point_cloud2 message"
timeout "$((WARMUP_SEC + 10))" zsh "$SCRIPT_DIR/ros2w.sh" topic echo /point_cloud2 --once > /dev/null

echo "[2/4] Measure /point_cloud2"
timeout "${MEASURE_SEC}" zsh "$SCRIPT_DIR/ros2w.sh" topic hz /point_cloud2 || true

echo "[3/4] Wait for first /scan message"
timeout "$((WARMUP_SEC + 10))" zsh "$SCRIPT_DIR/ros2w.sh" topic echo /scan --once > /dev/null

echo "[4/4] Measure /scan"
timeout "${MEASURE_SEC}" zsh "$SCRIPT_DIR/ros2w.sh" topic hz /scan || true
