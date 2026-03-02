#!/usr/bin/env zsh

set -euo pipefail

MODE="${1:-prelaunch}"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"
export COLCON_TRACE="${COLCON_TRACE:-}"

if [ "$MODE" != "prelaunch" ] && [ "$MODE" != "postlaunch" ]; then
  echo "Usage: zsh scripts/go2_ros_preflight.sh [prelaunch|postlaunch]"
  exit 1
fi

if [ "$MODE" = "prelaunch" ]; then
  echo "[prelaunch] Cleaning stale ROS launch/node processes..."

  cleanup_patterns=(
    "ros2 launch go2_robot_sdk"
    "go2_driver_node"
    "pointcloud_to_laserscan_node"
    "lidar_to_pointcloud_node"
    "pointcloud_aggregator_node"
    "async_slam_toolbox_node"
  )

  for pattern in "${cleanup_patterns[@]}"; do
    pkill -f "$pattern" || true
  done
  sleep 2

  for pattern in "${cleanup_patterns[@]}"; do
    if pgrep -f "$pattern" > /dev/null 2>&1; then
      echo "[prelaunch] Force killing leftover: $pattern"
      pkill -9 -f "$pattern" || true
    fi
  done

  sleep 2
fi

if [ -f /opt/ros/humble/setup.zsh ]; then
  set +u
  source /opt/ros/humble/setup.zsh
  set -u
fi

if [ -f install/setup.zsh ]; then
  set +u
  source install/setup.zsh
  set -u
fi

echo "[$MODE] Restarting ROS daemon..."
ros2 daemon stop > /dev/null 2>&1 || true
sleep 1
ros2 daemon start > /dev/null 2>&1
sleep 1

if ping -c 1 "$ROBOT_IP" > /dev/null 2>&1; then
  echo "[$MODE] Robot reachable at $ROBOT_IP"
else
  echo "[$MODE] WARN: cannot ping $ROBOT_IP"
fi

get_publisher_count() {
  local topic="$1"
  local max_attempts="${2:-1}"
  local attempt=1
  local output
  local count

  while [ "$attempt" -le "$max_attempts" ]; do
    output=$(ros2 topic info -v "$topic" 2>/dev/null || true)
    count=$(printf "%s\n" "$output" | awk -F': ' '/Publisher count/ {print $2; exit}')

    if [ -n "$count" ]; then
      echo "$count"
      return
    fi

    sleep 1
    attempt=$((attempt + 1))
  done

  echo "-1"
}

topic_has_messages() {
  local topic="$1"
  timeout 4 zsh "$SCRIPT_DIR/ros2w.sh" topic echo "$topic" --qos-profile sensor_data --once > /dev/null 2>&1
}

INFO_RETRIES=2
if [ "$MODE" = "postlaunch" ]; then
  INFO_RETRIES=6
fi

POINT_CLOUD_PUBS=$(get_publisher_count "/point_cloud2" "$INFO_RETRIES")
SCAN_PUBS=$(get_publisher_count "/scan" "$INFO_RETRIES")

if [ "$MODE" = "postlaunch" ]; then
  if [ "$POINT_CLOUD_PUBS" = "-1" ] && topic_has_messages "/point_cloud2"; then
    POINT_CLOUD_PUBS="1"
  fi
  if [ "$SCAN_PUBS" = "-1" ] && topic_has_messages "/scan"; then
    SCAN_PUBS="1"
  fi
fi

echo "[$MODE] /point_cloud2 publisher count: $POINT_CLOUD_PUBS"
echo "[$MODE] /scan publisher count: $SCAN_PUBS"

if [ "$MODE" = "prelaunch" ]; then
  if [ "$POINT_CLOUD_PUBS" != "-1" ] || [ "$SCAN_PUBS" != "-1" ]; then
    echo "[prelaunch] WARN: publishers still present before launch; stale processes may exist."
  fi
  echo "[prelaunch] Expected before launch: publisher count <= 0 (or topic absent)."
  echo "[prelaunch] Next: zsh /home/jetson/elder_and_dog/start_go2_wired_webrtc.sh minimal"
  exit 0
fi

if [ "$POINT_CLOUD_PUBS" = "1" ] && [ "$SCAN_PUBS" = "1" ]; then
  echo "[postlaunch] OK: exactly one publisher on /point_cloud2 and /scan."
  exit 0
fi

echo "[postlaunch] FAIL: expected exactly one publisher on both topics."
echo "[postlaunch] Action: rerun prelaunch cleanup and relaunch."
exit 1
