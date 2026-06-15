#!/usr/bin/env bash
# scripts/act1_forward.sh — Act1 operator/voice trigger（demo_forward standalone /cmd_vel）。
#
# ⚠️ NEEDS_ROY_ESTOP_TEST（6/15 重做 + 對抗複查強化）：配套 start_reactive_forward_demo.sh
#    走 standalone /cmd_vel 直連。第一次 live 必須 Roy 手持實體 e-stop + Go2 確認無損。
#
# 安全設計（6/15 對抗複查 A-2 修正）：
#   - **force_stop 由 `trap ... EXIT/TERM/INT` 保證執行**：不論正常結束、被 SIGTERM、Ctrl-C、
#     或 set -e 中斷，退出前一定先 enable=false + 直發 0 到 /cmd_vel → driver StopMove。
#     （舊版靠迴圈尾呼叫 force_stop，若 voice 的 subprocess timeout 砍掉 bash 就留 enable=true
#       讓狗續走 — 已用 trap 堵死。）
#   - **固定時間放行、不輪詢**：enable=true → sleep 固定秒數 → force_stop。runtime 的 danger 停
#     由 reactive_stop_node 自己負責（它持續讀 /scan、danger 時發 0 到 /cmd_vel），不靠本腳本
#     輪詢 zone（舊版 `ros2 topic echo --once` 在忙碌 Jetson 會慢/在 reactive 死掉時永久 hang）。
#   - 移動中最終急停永遠是「實體 e-stop 遙控器」。本腳本 force_stop 是 operator 軟急停。
#
# 用法：
#   act1_forward.sh          → enable=true 放行 ${ACT1_FORWARD_S:-2.0}s → force_stop + 鎖回
#   act1_forward.sh hold     → 立即 force_stop + 鎖回（軟急停）
#
# 前提：start_reactive_forward_demo.sh 已跑（/reactive_stop_node 發 /cmd_vel、且 /cmd_vel
#       唯一 publisher — 該腳本預設殺競爭者 + 啟動後驗 publisher 數）。
set -euo pipefail

# bash 腳本 → source setup.bash（與 setup.zsh 不可混用）。已 sourced 則無害。
source /opt/ros/humble/setup.bash 2>/dev/null || true
source ~/elder_and_dog/install/setup.bash 2>/dev/null || true

NODE="/reactive_stop_node"
CMD_VEL_TOPIC="${ACT1_CMD_VEL_TOPIC:-/cmd_vel}"   # 必須與 start_reactive_forward_demo.sh 一致
MODE="${1:-go}"
# clear-path 前進時間上限（reactive 會在 danger 自動停）。2.0s @0.6m/s ≈ 1.2m。短＝第一次驗安全。
FORWARD_S="${ACT1_FORWARD_S:-2.0}"

force_stop() {
  # 1) 先讓 reactive 停止 publish（enable=false），避免和我們的 0 在 /cmd_vel 上打架。
  ros2 param set "$NODE" enable false >/dev/null 2>&1 || true
  sleep 0.15
  # 2) 直發 0 到 /cmd_vel（8 筆 @10Hz）→ driver post-deadband zero → StopMove(1003, discrete)。
  ros2 topic pub -r 10 -t 8 "$CMD_VEL_TOPIC" geometry_msgs/msg/Twist "{}" >/dev/null 2>&1 || true
}

# ★ 任何退出路徑都保證 force_stop（A-2 修正：subprocess SIGTERM / Ctrl-C / set -e / 正常結束）。
trap 'force_stop' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

if [ "$MODE" = "hold" ] || [ "$MODE" = "stop" ]; then
  echo "[act1] HOLD — force-stop + lock"
  exit 0   # → EXIT trap → force_stop
fi

echo "[act1] FORWARD — enable=true 放行 ${FORWARD_S}s（reactive 於 danger 自動停；實體 e-stop 在手）"
ros2 param set "$NODE" enable true >/dev/null
sleep "$FORWARD_S"
echo "[act1] 時間到 → force-stop + lock（EXIT trap）"
# 正常落到 EXIT trap → force_stop；enable 最終 = false。
