#!/usr/bin/env zsh

set -euo pipefail

if [ -z "${ZSH_VERSION:-}" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

export ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
export CONN_TYPE="${CONN_TYPE:-webrtc}"
export GO2_LIDAR_DECODER="${GO2_LIDAR_DECODER:-wasm}"
export LIDAR_POINT_STRIDE="${LIDAR_POINT_STRIDE:-8}"
MAP_YAML="${MAP_YAML:-/home/jetson/go2_map.yaml}"
REQUESTED_MAP_YAML="$MAP_YAML"
RVIZ2="${RVIZ2:-false}"
FOXGLOVE="${FOXGLOVE:-false}"
ENABLE_VIDEO="${ENABLE_VIDEO:-false}"
PUBLISH_RAW_IMAGE="${PUBLISH_RAW_IMAGE:-false}"
PUBLISH_COMPRESSED_IMAGE="${PUBLISH_COMPRESSED_IMAGE:-false}"
AUTO_BUILD="${AUTO_BUILD:-true}"
BUILD_PACKAGES="${BUILD_PACKAGES:-go2_robot_sdk}"

for arg in "$@"; do
  case "$arg" in
    --skip-build)
      AUTO_BUILD="false"
      ;;
  esac
done

if [ "$ENABLE_VIDEO" = "false" ] && { [ "$PUBLISH_RAW_IMAGE" = "true" ] || [ "$PUBLISH_COMPRESSED_IMAGE" = "true" ]; }; then
  echo "WARN: publish_*_image=true requires enable_video=true, forcing enable_video=true"
  ENABLE_VIDEO="true"
fi

resolve_map_yaml() {
  local requested="$1"

  if [ -f "$requested" ]; then
    printf "%s\n" "$requested"
    return 0
  fi

  local candidates=(
    "/home/jetson/elder_and_dog/src/go2_robot_sdk/maps/phase1.yaml"
    "/home/jetson/elder_and_dog/src/go2_robot_sdk/maps/phase1_test.yaml"
  )

  for candidate in "${candidates[@]}"; do
    if [ -f "$candidate" ]; then
      echo "WARN: MAP_YAML not found: $requested" >&2
      echo "WARN: fallback to detected map: $candidate" >&2
      printf "%s\n" "$candidate"
      return 0
    fi
  done

  return 1
}

if ! ping -c 1 "$ROBOT_IP" > /dev/null 2>&1; then
  echo "FAIL: cannot reach $ROBOT_IP"
  echo "Please verify cable/NIC and ROBOT_IP"
  exit 1
fi

if ! MAP_YAML=$(resolve_map_yaml "$MAP_YAML"); then
  echo "FAIL: map yaml not found: $REQUESTED_MAP_YAML"
  echo "Checked fallback candidates:"
  echo "  - /home/jetson/elder_and_dog/src/go2_robot_sdk/maps/phase1.yaml"
  echo "  - /home/jetson/elder_and_dog/src/go2_robot_sdk/maps/phase1_test.yaml"
  echo "Set MAP_YAML=/absolute/path/to/map.yaml"
  exit 1
fi

if [ ! -f /opt/ros/humble/setup.zsh ]; then
  echo "FAIL: missing /opt/ros/humble/setup.zsh"
  exit 1
fi

echo "Running prelaunch cleanup..."
zsh "$WORKSPACE_ROOT/scripts/go2_ros_preflight.sh" prelaunch

set +u
source /opt/ros/humble/setup.zsh
set -u

if [ "$AUTO_BUILD" = "true" ]; then
  echo "Building workspace packages before launch: $BUILD_PACKAGES"
  colcon build --packages-select $BUILD_PACKAGES
else
  echo "Skipping colcon build (AUTO_BUILD=$AUTO_BUILD)"
fi

if [ ! -f "$WORKSPACE_ROOT/install/setup.zsh" ]; then
  echo "FAIL: missing $WORKSPACE_ROOT/install/setup.zsh"
  echo "Build workspace first: colcon build"
  exit 1
fi

set +u
source "$WORKSPACE_ROOT/install/setup.zsh"
set -u

if ! command -v ros2 > /dev/null 2>&1; then
  echo "FAIL: ros2 command unavailable after sourcing environment"
  exit 1
fi

echo "Launching Gate C (Nav2-only): slam:=false nav2:=true map:=$MAP_YAML"
echo "Visualization: rviz2:=$RVIZ2 foxglove:=$FOXGLOVE"
echo "Camera: enable_video:=$ENABLE_VIDEO raw:=$PUBLISH_RAW_IMAGE compressed:=$PUBLISH_COMPRESSED_IMAGE"
ros2 launch go2_robot_sdk robot.launch.py \
  slam:=false \
  nav2:=true \
  autostart:=true \
  map:="$MAP_YAML" \
  rviz2:=$RVIZ2 \
  foxglove:=$FOXGLOVE \
  joystick:=false \
  teleop:=false \
  enable_video:=$ENABLE_VIDEO \
  decode_lidar:=true \
  publish_raw_image:=$PUBLISH_RAW_IMAGE \
  publish_compressed_image:=$PUBLISH_COMPRESSED_IMAGE \
  lidar_processing:=false \
  minimal_state_topics:=true \
  lidar_point_stride:=$LIDAR_POINT_STRIDE \
  enable_tts:=false
