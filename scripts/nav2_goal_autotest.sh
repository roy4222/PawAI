#!/usr/bin/env zsh

set -euo pipefail

if [ -z "${ZSH_VERSION:-}" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
MEMORY_GUARD_SCRIPT="$SCRIPT_DIR/nav_memory_guard.sh"
ENABLE_MEMORY_GUARD="${ENABLE_MEMORY_GUARD:-true}"

if [ -f "$MEMORY_GUARD_SCRIPT" ]; then
  set +u
  source "$MEMORY_GUARD_SCRIPT"
  set -u
fi

if [ ! -f /opt/ros/humble/setup.zsh ]; then
  echo "FAIL: missing /opt/ros/humble/setup.zsh"
  exit 1
fi

if [ ! -f "$WORKSPACE_ROOT/install/setup.zsh" ]; then
  echo "FAIL: missing $WORKSPACE_ROOT/install/setup.zsh"
  echo "Build workspace first: colcon build"
  exit 1
fi

set +u
source /opt/ros/humble/setup.zsh
source "$WORKSPACE_ROOT/install/setup.zsh"
set -u

if [ "$ENABLE_MEMORY_GUARD" = "true" ] && command -v nav_memory_guard_check > /dev/null 2>&1; then
  nav_memory_guard_check
fi

exec python3 "$SCRIPT_DIR/nav2_goal_autotest.py" "$@"
