#!/usr/bin/env bash
# PawAI Studio 一鍵啟動（Backend + Frontend）
# Usage: bash pawai-studio/start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# ── 前置檢查 ────────────────────────────────────────────────────────────
echo "[1/4] 檢查環境..."

if ! command -v python3 &>/dev/null; then
  echo "❌ python3 未安裝"; exit 1
fi

if ! command -v node &>/dev/null; then
  echo "❌ node 未安裝（需要 >= 18）"; exit 1
fi

NODE_MAJOR=$(node --version | sed 's/v\([0-9]*\).*/\1/')
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "❌ Node 版本太舊（$(node --version)），需要 >= 18"; exit 1
fi

python3 -c "import fastapi, uvicorn, pydantic, wsproto" 2>/dev/null || {
  echo "❌ Python 缺依賴，安裝中..."
  pip3 install --user fastapi uvicorn pydantic wsproto
}

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "[1/4] 前端未安裝依賴，執行 npm install..."
  cd "$FRONTEND_DIR" && npm install
fi

# ── 清理舊 process ──────────────────────────────────────────────────────
echo "[2/4] 清理舊 process..."
pkill -f "uvicorn mock_server:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 1

# ── 啟動 Backend ────────────────────────────────────────────────────────
echo "[3/4] 啟動 Mock Server (port 8080)..."
cd "$BACKEND_DIR"
python3 -m uvicorn mock_server:app --port 8080 --host 0.0.0.0 --ws wsproto &
BACK_PID=$!
sleep 2

if ! kill -0 $BACK_PID 2>/dev/null; then
  echo "❌ Mock Server 啟動失敗"; exit 1
fi
echo "✅ Mock Server running (PID=$BACK_PID)"

# ── 啟動 Frontend ───────────────────────────────────────────────────────
echo "[4/4] 啟動 Frontend (port 3000)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONT_PID=$!
sleep 5

echo ""
echo "════════════════════════════════════════════"
echo "  PawAI Studio 已啟動"
echo ""
echo "  🌐 Studio:      http://localhost:3000/studio"
echo "  🔧 Mock Server:  http://localhost:8080"
echo "  📡 WebSocket:    ws://localhost:8080/ws/events"
echo ""
echo "  觸發 Demo A:  curl -X POST http://localhost:8080/mock/scenario/demo_a"
echo ""
echo "  停止: Ctrl+C 或 bash pawai-studio/stop.sh"
echo "════════════════════════════════════════════"

# 前景等待，Ctrl+C 停止全部
trap 'echo ""; echo "Stopping..."; kill $BACK_PID $FRONT_PID 2>/dev/null; exit 0' INT TERM
wait
