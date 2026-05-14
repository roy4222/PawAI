#!/usr/bin/env bash
# nav-avoidance-lane cleanup
# Usage: bash cleanup.sh [--handoff brain|none]
#
# ⚠️ Driver reuse 機制尚未實作 — 兩個 handoff 值都會清 go2_driver + D435 + TF。
# --handoff 旗標目前只影響 cleanup 完的提示文字（hint 給下一步該跑啥）。
#   --handoff brain : 清全部 + 提示「下一步建議 brain-studio-lane start」
#   --handoff none  : 清全部 + 提示「完整清理完成」（預設）
set -uo pipefail

HANDOFF="none"
for arg in "$@"; do
  case "$arg" in
    --handoff) shift; HANDOFF="${1:-none}" ;;
    --handoff=*) HANDOFF="${arg#*=}" ;;
    brain|none|nav) HANDOFF="$arg" ;;
  esac
done

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"

echo "═══ nav-avoidance-lane cleanup (handoff=$HANDOFF) ═══"

# ── 殺 nav tmux sessions ───────────────────────────────────
echo "[1] 殺 nav tmux sessions ..."
ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t lidar-slam 2>/dev/null; \
                    tmux kill-session -t nav2-amcl 2>/dev/null; \
                    tmux kill-session -t nav-cap-demo 2>/dev/null; \
                    tmux kill-session -t reactive-stop 2>/dev/null; \
                    for s in b5-driver b5-foxglove b5-reactive b5-sllidar b5-tf; do \
                      tmux kill-session -t \$s 2>/dev/null; \
                    done"
echo "    ✅ tmux cleared"

# ── pkill nav-only processes ───────────────────────────────
echo "[2] pkill nav-only processes ..."
ssh $SSH_OPTS "$JETSON_HOST" "pkill -9 -f sllidar_node 2>/dev/null; \
                    pkill -9 -f reactive_stop_node 2>/dev/null; \
                    pkill -9 -f cartographer 2>/dev/null; \
                    pkill -9 -f amcl 2>/dev/null; \
                    pkill -9 -f map_server 2>/dev/null; \
                    pkill -9 -f bt_navigator 2>/dev/null; \
                    pkill -9 -f planner_server 2>/dev/null; \
                    pkill -9 -f controller_server 2>/dev/null; \
                    pkill -9 -f nav_action_server 2>/dev/null; \
                    pkill -9 -f route_runner 2>/dev/null; \
                    pkill -9 -f log_pose_node 2>/dev/null; \
                    pkill -9 -f state_broadcaster 2>/dev/null; \
                    pkill -9 -f capability_publisher 2>/dev/null; \
                    pkill -9 -f depth_safety 2>/dev/null"
echo "    ✅ nav processes killed"

# ── 一律清 go2_driver / D435 / TF（reuse driver 設計尚未實作）──
# 注意：handoff 旗標目前**不影響 driver 是否清**，只影響 cleanup 後的提示。
# brain lane start 也會自啟 driver（如果該 mode 需要），不會 reuse 既有的。
echo "[3] 清 go2_driver + D435 + TF + 相關 C++ 子 process ..."
ssh $SSH_OPTS "$JETSON_HOST" "pkill -9 -f go2_driver 2>/dev/null; \
                    pkill -9 -f robot_state 2>/dev/null; \
                    pkill -9 -f pointcloud 2>/dev/null; \
                    pkill -9 -f joy_node 2>/dev/null; \
                    pkill -9 -f teleop 2>/dev/null; \
                    pkill -9 -f twist_mux 2>/dev/null; \
                    pkill -9 -f realsense2_camera 2>/dev/null; \
                    pkill -9 -f static_transform_publisher 2>/dev/null"
echo "    ✅ driver + D435 + TF killed"

case "$HANDOFF" in
  brain)
    echo "    💡 下一步建議：bash .claude/skills/brain-studio-lane/scripts/start.sh <mode> [--studio]"
    ;;
  none|nav|*)
    echo "    💡 完整清理完成"
    ;;
esac

# ── 確認 ───────────────────────────────────────────────────
sleep 1
RESIDUAL=$(ssh $SSH_OPTS "$JETSON_HOST" "ps aux 2>/dev/null | grep -E 'sllidar|reactive_stop|cartographer|amcl|nav_action' | grep -v grep | wc -l" 2>/dev/null || echo "?")
echo "═══ cleanup 完成 (殘留 nav process: $RESIDUAL) ═══"
