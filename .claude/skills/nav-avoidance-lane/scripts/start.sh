#!/usr/bin/env bash
# nav-avoidance-lane start
# Usage: bash start.sh <mapping|amcl|capability|fallback>
set -uo pipefail

MODE="${1:-}"
if [[ ! "$MODE" =~ ^(mapping|amcl|capability|fallback)$ ]]; then
  echo "❌ usage: start.sh <mapping|amcl|capability|fallback>"
  exit 1
fi

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
JETSON_REPO="${JETSON_REPO:-/home/jetson/elder_and_dog}"
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Preflight ──────────────────────────────────────────────
echo "═══ 跑 preflight ═══"
if ! bash "$SKILL_DIR/preflight.sh" "$MODE"; then
  echo "❌ preflight 失敗，啟動中止"
  exit 1
fi

# ── Start nav stack on Jetson ──────────────────────────────
echo "═══ 啟動 nav stack (mode=$MODE) on $JETSON_HOST ═══"

case "$MODE" in
  mapping)
    # Cartographer pure scan-matching，無 driver
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t lidar-slam 2>/dev/null; \
      bash $JETSON_REPO/scripts/start_lidar_slam_tmux.sh > /dev/null 2>&1"
    sleep 12
    echo "    ✅ lidar-slam session 啟動"
    echo "    建圖完成後跑：bash $JETSON_REPO/scripts/build_map.sh <map_name>"
    ;;
  amcl)
    # nav2 + amcl + driver（恢復發 odom→base_link TF）
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t nav2-amcl 2>/dev/null; \
      bash $JETSON_REPO/scripts/start_nav2_amcl_demo_tmux.sh > /dev/null 2>&1"
    sleep 30
    echo "    ✅ nav2-amcl session 啟動"
    echo "    下一步：Foxglove 設 /initialpose（Go2 真實位置）"
    echo "          發 goal: ros2 topic pub /goal_pose geometry_msgs/PoseStamped ... -r 2 --times 5"
    ;;
  capability)
    # nav_capability 9 windows，含 d435 + reactive_stop(mode=progressive) +
    # 6 navcap nodes。Reactive 在 obstacle priority 200，danger 發 0、
    # slow/clear 沉默。⚠️ progressive 安全前提是「**沒有 teleop hot publisher
    # 在跑**」— mux priority: emergency 255 / obstacle 200 / teleop 100 /
    # nav 10。obstacle 沉默 0.5s 後若 teleop 100 還在送，會贏 nav 10 接管。
    # 純 B5 停車驗證請改用 start_reactive_stop_safety_hold_tmux.sh (hold_brake)。
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t nav-cap-demo 2>/dev/null; \
      bash $JETSON_REPO/scripts/start_nav_capability_demo_tmux.sh > /dev/null 2>&1"
    sleep 50
    echo "    ✅ nav-cap-demo session 啟動"
    echo "    下一步："
    echo "      ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative '{distance: 0.5}'"
    echo "      ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute '{route_id: sample}'"
    ;;
  fallback)
    # standalone reactive_stop (mode="" + safety_only=false 預設)
    # 直發 /cmd_vel 3 段速：danger=0 / slow=0.45 / normal=0.60 m/s
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t reactive-stop 2>/dev/null; \
      bash $JETSON_REPO/scripts/start_reactive_stop_tmux.sh > /dev/null 2>&1"
    sleep 15
    echo "    ✅ reactive-stop session 啟動"
    echo "    下一步：發 cmd_vel 測試（紙箱靠近應停）"
    ;;
esac

echo "═══ 啟動完成 ═══"
echo "建議下一步: bash $SKILL_DIR/healthcheck.sh"
