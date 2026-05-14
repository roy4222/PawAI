#!/usr/bin/env bash
# pawai-studio/start-school-live.sh — Mac 操作端 demo 啟動 wrapper（學校場地）
#
# 跟 start-live.sh 不同：
#   - GATEWAY_HOST 必填（不允許 silent default 成家裡 Tailscale IP 100.83.109.89）
#   - ping + /health pre-check 必過才啟動
#   - 失敗給可執行的 Jetson 端啟動指令提示
#
# Usage（Mac）：
#   GATEWAY_HOST=192.168.1.42 bash pawai-studio/start-school-live.sh
#   # 或先 source env 檔：
#   JETSON_IP=192.168.1.42 source ../config/school_demo.env
#   bash pawai-studio/start-school-live.sh
#
# 之後 Mac 開 http://localhost:3000/studio
set -euo pipefail

# ── 必填硬檢查 ──────────────────────────────────────────────
if [[ -z "${GATEWAY_HOST:-}" ]]; then
  cat >&2 <<'EOF'
❌ ERROR: GATEWAY_HOST 未設定

用法（兩擇一）：
  # 法 A：直接帶 env
  GATEWAY_HOST=<學校 Jetson IP> bash pawai-studio/start-school-live.sh

  # 法 B：先 source 環境檔
  JETSON_IP=<學校 Jetson IP> source config/school_demo.env
  bash pawai-studio/start-school-live.sh

取 Jetson IP（在 Jetson 端跑）：
  hostname -I | awk '{print $1}'

或用 mDNS / Tailscale 名：
  GATEWAY_HOST=jetson-school bash pawai-studio/start-school-live.sh
EOF
  exit 1
fi

GATEWAY_PORT="${GATEWAY_PORT:-8080}"
GATEWAY_URL="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

echo "[start-school-live] GATEWAY_HOST=$GATEWAY_HOST"
echo "[start-school-live] GATEWAY_PORT=$GATEWAY_PORT"
echo "[start-school-live] target URL: $GATEWAY_URL"
echo ""

# ── ping pre-check ──────────────────────────────────────────
echo "[pre-check] ping $GATEWAY_HOST..."
if ! ping -c 1 -W 2 "$GATEWAY_HOST" > /dev/null 2>&1; then
  cat >&2 <<EOF
❌ ping $GATEWAY_HOST 失敗

可能原因：
  1. Jetson 沒開機 / 沒接電
  2. Mac 與 Jetson 不在同網段（檢查 Wi-Fi / Ethernet）
  3. GATEWAY_HOST 寫錯（IP 拼字、Tailscale 名稱錯）

確認 Mac 連在哪個 Wi-Fi：
  $(if [[ "$(uname)" == "Darwin" ]]; then echo "networksetup -getairportnetwork en0"; else echo "iwgetid -r"; fi)

確認 Jetson 在哪個 IP（在 Jetson 上跑）：
  hostname -I
EOF
  exit 2
fi
echo "[pre-check] ping ✅"

# ── /health pre-check ───────────────────────────────────────
echo "[pre-check] curl $GATEWAY_URL/health..."
if ! curl -sf -m 3 "$GATEWAY_URL/health" > /dev/null 2>&1; then
  cat >&2 <<EOF
❌ Gateway 沒回應 ($GATEWAY_URL/health)

Jetson 端要先啟動 demo stack：
  ssh $GATEWAY_HOST   # 或 ssh jetson@$GATEWAY_HOST
  cd ~/elder_and_dog
  source /opt/ros/humble/setup.zsh && source install/setup.zsh
  source config/school_demo.env   # 注意要先 export JETSON_IP 或 GATEWAY_HOST
  bash scripts/start_full_demo_tmux.sh

啟動完約 30s 後再跑本腳本。
EOF
  exit 3
fi
echo "[pre-check] /health ✅"
echo ""

# ── exec live mode ──────────────────────────────────────────
echo "[start-school-live] all green — launching Studio frontend (live mode)..."
echo ""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env GATEWAY_HOST="$GATEWAY_HOST" GATEWAY_PORT="$GATEWAY_PORT" \
  bash "$SCRIPT_DIR/start-live.sh" --live
