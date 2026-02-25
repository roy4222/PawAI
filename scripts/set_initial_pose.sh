#!/usr/bin/env zsh

set -euo pipefail

X="${1:-0.0}"
Y="${2:-0.0}"
YAW="${3:-0.0}"

if [ -z "${ZSH_VERSION:-}" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

set +u
source /opt/ros/humble/setup.zsh
source "$ROOT_DIR/install/setup.zsh"
set -u

read -r QZ QW < <(python3 - <<PY
import math
yaw=float("$YAW")
print(math.sin(yaw/2.0), math.cos(yaw/2.0))
PY
)

zsh "$SCRIPT_DIR/ros2w.sh" topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "{header: {frame_id: map}, pose: {pose: {position: {x: $X, y: $Y, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: $QZ, w: $QW}}, covariance: [0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.06853891945200942]}}"
