#!/usr/bin/env bash
# scripts/act1_forward.sh — Act1 operator/voice trigger（demo_forward standalone /cmd_vel）。
#
# ⚠️ NEEDS_ROY_ESTOP_TEST（6/15 重做）：配套 start_reactive_forward_demo.sh 已從撞過車的
#    整合 mux 路徑改回 standalone /cmd_vel 直連。force-stop 也改成直發 0 到 /cmd_vel
#    （→ driver StopMove），不再靠 mux 的 /cmd_vel_emergency（standalone 無 mux）。
#    第一次 live 必須 Roy 手持實體 e-stop + Go2 確認無損。
#
# 用法：
#   act1_forward.sh          → enable=true（放行）→ 監看 reactive zone → 遇障/超時
#                              → force-stop（enable=false + 直發 0 到 /cmd_vel）+ 鎖回
#   act1_forward.sh hold     → 立即 force-stop + 鎖回（operator 軟急停）
#
# 前提：start_reactive_forward_demo.sh 已跑（/reactive_stop_node 在、發 /cmd_vel）、且
#       /cmd_vel 唯一 publisher（看 start 腳本 verify window）。
#
# ⚠️ 安全分層：
#   - 移動中最終急停永遠是「實體 e-stop 遙控器」。本腳本 force-stop 是 operator 軟急停。
#   - 真正的 runtime 安全停＝ reactive_stop_node 本身：danger 時它持續發 0 到 /cmd_vel →
#     driver StopMove（這是 6/15 standalone 驗證會停的機制）。本腳本只負責「放行 + 限時 +
#     收尾鎖回」，不是唯一的停車來源。
#   - 撞車誘因＝上一輪「enable=true 開太久（~5s）結尾才 force-stop」→ 本版 MAX 大幅縮短
#     + 監看到 danger 立即收手。
set -euo pipefail

# bash 腳本 → source setup.bash（與 setup.zsh 不可混用）。已 sourced 則無害。
source /opt/ros/humble/setup.bash 2>/dev/null || true
source ~/elder_and_dog/install/setup.bash 2>/dev/null || true

NODE="/reactive_stop_node"
CMD_VEL_TOPIC="${ACT1_CMD_VEL_TOPIC:-/cmd_vel}"   # 必須與 start_reactive_forward_demo.sh 一致
MODE="${1:-go}"
# 限制 clear-path 連續前進距離：12 * 0.2s ≈ 2.4s @0.6m/s ≈ 1.4m 上限（比舊 4.2s 短很多）。
MAX_TICKS="${ACT1_MAX_TICKS:-12}"
POLL_S="${ACT1_POLL_S:-0.2}"

force_stop() {
  # 1) 先讓 reactive 停止 publish（enable=false），避免和我們的 0 在 /cmd_vel 上打架。
  ros2 param set "$NODE" enable false >/dev/null 2>&1 || true
  sleep 0.15
  # 2) 直發 0 到 /cmd_vel（8 筆 @10Hz ≈ 0.8s）→ driver post-deadband zero → StopMove(1003)。
  #    standalone 無 mux，故不用 /cmd_vel_emergency。
  ros2 topic pub -r 10 -t 8 "$CMD_VEL_TOPIC" geometry_msgs/msg/Twist "{}" >/dev/null 2>&1 || true
}

if [ "$MODE" = "hold" ] || [ "$MODE" = "stop" ]; then
  echo "[act1] HOLD — force-stop + lock"
  force_stop
  echo "[act1] enable = $(ros2 param get "$NODE" enable 2>/dev/null | tail -1)"
  exit 0
fi

echo "[act1] FORWARD — enable=true（盯著狗、實體 e-stop 在手；MAX≈$(awk "BEGIN{print ${MAX_TICKS}*${POLL_S}}")s）"
ros2 param set "$NODE" enable true >/dev/null
stopped=0
for i in $(seq 1 "$MAX_TICKS"); do
  zone=$(ros2 topic echo /state/reactive_stop/status --once 2>/dev/null | grep -oE '"zone": "[a-z]+"' | head -1)
  echo "  t${i}: ${zone:-<no status>}"
  case "$zone" in
    *danger*|*emergency*) echo "[act1] 正前障礙 → reactive 已停"; stopped=1; break;;
  esac
  sleep "$POLL_S"
done
[ "$stopped" = "0" ] && echo "[act1] 超時（clear-path 無障礙）→ 強制停"
echo "[act1] force-stop + lock"
force_stop
echo "[act1] done. enable = $(ros2 param get "$NODE" enable 2>/dev/null | tail -1)"
