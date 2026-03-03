#!/usr/bin/env zsh

set -euo pipefail

if [ -z "${ZSH_VERSION:-}" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

nav_memory_guard_check() {
  local min_available_mb="${MEM_AVAILABLE_MIN_MB:-1024}"
  local max_swap_used_mb="${SWAP_USED_MAX_MB:-1024}"
  local mem_available_kb
  local swap_total_kb
  local swap_free_kb
  local swap_used_kb
  local mem_available_mb
  local swap_used_mb

  mem_available_kb=$(awk '/MemAvailable:/ {print $2; exit}' /proc/meminfo)
  swap_total_kb=$(awk '/SwapTotal:/ {print $2; exit}' /proc/meminfo)
  swap_free_kb=$(awk '/SwapFree:/ {print $2; exit}' /proc/meminfo)

  if [ -z "$mem_available_kb" ] || [ -z "$swap_total_kb" ] || [ -z "$swap_free_kb" ]; then
    echo "WARN: cannot read /proc/meminfo, skip memory guard"
    return 0
  fi

  swap_used_kb=$((swap_total_kb - swap_free_kb))
  mem_available_mb=$((mem_available_kb / 1024))
  swap_used_mb=$((swap_used_kb / 1024))

  echo "[memory-guard] available=${mem_available_mb}MB swap_used=${swap_used_mb}MB"

  if [ "$mem_available_mb" -lt "$min_available_mb" ] || [ "$swap_used_mb" -gt "$max_swap_used_mb" ]; then
    echo "FAIL: memory pressure too high for reliable nav tests"
    echo "  required: available >= ${min_available_mb}MB and swap_used <= ${max_swap_used_mb}MB"
    echo "  actual:   available=${mem_available_mb}MB swap_used=${swap_used_mb}MB"
    echo "Run cleanup: zsh scripts/go2_ros_preflight.sh prelaunch"
    echo "Then close heavy tools (rviz2/foxglove/rosbag) or reboot before retrying."
    return 1
  fi

  return 0
}
