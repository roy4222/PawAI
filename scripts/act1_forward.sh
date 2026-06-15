#!/usr/bin/env bash
# scripts/act1_forward.sh — Act1 operator trigger（demo_forward reactive_stop）。
# ⚠️⚠️ NOT_DEMO_SAFE（6/15 撞車）：整合 brain stack（/cmd_vel_obstacle→twist_mux）時
#     reactive danger-stop 沒攔截、狗撞牆。motion 鎖 fallback，待查清 mux 路徑才可再用。
#
# 用法：
#   act1_forward.sh          → enable=true（放行）→ 監看 reactive zone → 遇障停 or 超時
#                              → force-stop（/cmd_vel_emergency 0，priority 255）+ enable=false 鎖回
#   act1_forward.sh hold     → 立即 force-stop + 鎖回（operator 急停鈕，獨立於實體 e-stop）
#
# 前提：start_reactive_forward_demo.sh 已跑（/reactive_stop_node 在），且 brain demo
#       twist_mux + 單一 go2_driver 在（pawai demo start --with-lidar）。
#
# ⚠️ 安全：移動中最終急停永遠是「實體 e-stop 遙控器」。本腳本的 force-stop 透過
#         /cmd_vel_emergency(255)→mux→StopMove，是 operator 軟急停，不取代實體 e-stop。
#         enable=false 不能停移動中的狗（會 sport-timeout 滑行），故 force-stop 用 emergency 0。
set -euo pipefail

# bash 腳本 → source setup.bash（與 setup.zsh 不可混用）。已 sourced 則無害。
source /opt/ros/humble/setup.bash 2>/dev/null || true
source ~/elder_and_dog/install/setup.bash 2>/dev/null || true

NODE="/reactive_stop_node"
MODE="${1:-go}"
MAX_TICKS="${ACT1_MAX_TICKS:-12}"     # 12 * 0.35s ≈ 4.2s 上限（限制 clear-path 連續前進距離）

force_stop() {
  # emergency 0（twist_mux priority 255）→ driver StopMove；再鎖 reactive。
  ros2 topic pub -r 10 -t 6 /cmd_vel_emergency geometry_msgs/msg/Twist "{}" >/dev/null 2>&1 || true
  ros2 param set "$NODE" enable false >/dev/null 2>&1 || true
}

if [ "$MODE" = "hold" ] || [ "$MODE" = "stop" ]; then
  echo "[act1] HOLD — force-stop + lock"
  force_stop
  echo "[act1] enable = $(ros2 param get "$NODE" enable 2>/dev/null | tail -1)"
  exit 0
fi

echo "[act1] FORWARD — enable=true（盯著狗、實體 e-stop 在手）"
ros2 param set "$NODE" enable true >/dev/null
stopped=0
for i in $(seq 1 "$MAX_TICKS"); do
  zone=$(ros2 topic echo /state/reactive_stop/status --once 2>/dev/null | grep -oE '"zone": "[a-z]+"' | head -1)
  echo "  t${i}: ${zone:-<no status>}"
  case "$zone" in
    *danger*|*emergency*) echo "[act1] 正前障礙 → reactive 已停"; stopped=1; break;;
  esac
  sleep 0.35
done
[ "$stopped" = "0" ] && echo "[act1] 超時（clear-path 無障礙）→ 強制停"
echo "[act1] force-stop + lock"
force_stop
echo "[act1] done. enable = $(ros2 param get "$NODE" enable 2>/dev/null | tail -1)"
