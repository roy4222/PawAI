#!/usr/bin/env bash
# PawAI Studio 正式站啟動（連接 Jetson Gateway）
# Usage: bash pawai-studio/start-live.sh
#        GATEWAY_HOST=192.168.123.100 bash pawai-studio/start-live.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# ── Gateway 位置 ───────────────────────────────────────────────
GATEWAY_HOST="${GATEWAY_HOST:-100.83.109.89}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
GATEWAY_URL="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

# ── 前置檢查 ──────────────────────────────────────────────────
echo "[1/3] 檢查環境..."

if ! command -v node &>/dev/null; then
  echo "❌ node 未安裝（需要 >= 18）"; exit 1
fi

NODE_MAJOR=$(node --version | sed 's/v\([0-9]*\).*/\1/')
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "❌ Node 版本太舊（$(node --version)），需要 >= 18"; exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "[1/3] 前端未安裝依賴，執行 npm install..."
  cd "$FRONTEND_DIR" && npm install
fi

# ── 確認 Gateway 可連 ─────────────────────────────────────────
echo "[2/3] 檢查 Jetson Gateway ($GATEWAY_URL)..."
if curl -sf --max-time 3 "$GATEWAY_URL/health" >/dev/null 2>&1; then
  HEALTH=$(curl -sf --max-time 3 "$GATEWAY_URL/health")
  echo "✅ Gateway OK: $HEALTH"
else
  echo "⚠️  Gateway 未回應 ($GATEWAY_URL/health)"
  echo "   確認 Jetson 上 full demo 已啟動: bash scripts/start_full_demo_tmux.sh"
  echo "   繼續啟動前端（Gateway 連上後會自動重連）..."
fi

# ── 清理舊 process ────────────────────────────────────────────
pkill -f "next dev" 2>/dev/null || true
sleep 1

# ── 啟動 Frontend ─────────────────────────────────────────────
echo "[3/3] 啟動 Frontend (port 3000) → Gateway: $GATEWAY_URL..."
cd "$FRONTEND_DIR"
NEXT_PUBLIC_GATEWAY_URL="$GATEWAY_URL" npm run dev &
FRONT_PID=$!
sleep 5

if ! kill -0 $FRONT_PID 2>/dev/null; then
  echo "❌ Frontend 啟動失敗"; exit 1
fi

echo ""
echo "════════════════════════════════════════════════"
echo "  PawAI Studio (Live)"
echo ""
echo "  🌐 Studio:     http://localhost:3000/studio"
echo "  📺 Live View:  http://localhost:3000/studio/live"
echo "  🔧 Gateway:    $GATEWAY_URL"
echo "  📡 Events WS:  ws://${GATEWAY_HOST}:${GATEWAY_PORT}/ws/events"
echo "  🎥 Video WS:   ws://${GATEWAY_HOST}:${GATEWAY_PORT}/ws/video/{face,vision,object}"
echo ""
echo "  停止: Ctrl+C"
echo "════════════════════════════════════════════════"

trap 'echo ""; echo "Stopping..."; kill $FRONT_PID 2>/dev/null; exit 0' INT TERM
wait
