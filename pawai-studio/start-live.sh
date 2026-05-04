#!/usr/bin/env bash
# PawAI Studio 啟動腳本
#
# 三種模式：
#   1. live   — 連接 Jetson 上的真 gateway（Tailscale 或本機 LAN）
#   2. mock   — 啟本機 mock_server (port 8080)，frontend 對它打 API
#   3. auto   (預設) — 先試 Jetson gateway，失敗自動切 mock
#
# Usage:
#   bash pawai-studio/start-live.sh                    # auto（推薦）
#   bash pawai-studio/start-live.sh --live             # 強制 live（要 Jetson 起來）
#   bash pawai-studio/start-live.sh --mock             # 強制 mock（本機開發/測試）
#   GATEWAY_HOST=192.168.123.100 bash pawai-studio/start-live.sh --live

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"

MODE="auto"
case "${1:-}" in
  --live) MODE="live" ;;
  --mock) MODE="mock" ;;
  --auto|"") MODE="auto" ;;
  -h|--help)
    grep -E '^#' "$0" | sed 's/^# \?//'
    exit 0
    ;;
  *) echo "Unknown flag: $1  (use --live / --mock / --auto)"; exit 1 ;;
esac

# ── Gateway 位置（live / auto 用） ─────────────────────────────
GATEWAY_HOST="${GATEWAY_HOST:-100.83.109.89}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
GATEWAY_URL="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

# ── 前置檢查 ──────────────────────────────────────────────────
echo "[1/4] 檢查環境..."

if ! command -v node &>/dev/null; then
  echo "❌ node 未安裝（需要 >= 18）"; exit 1
fi
NODE_MAJOR=$(node --version | sed 's/v\([0-9]*\).*/\1/')
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "❌ Node 版本太舊（$(node --version)），需要 >= 18"; exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "    前端未安裝依賴，執行 npm install..."
  (cd "$FRONTEND_DIR" && npm install)
fi

need_python_deps() {
  if ! command -v python3 &>/dev/null; then
    echo "❌ python3 未安裝（mock 模式需要）"; exit 1
  fi
  python3 -c "import fastapi, uvicorn, pydantic, wsproto" 2>/dev/null || {
    echo "    Python 缺依賴，安裝中..."
    pip3 install --user fastapi uvicorn pydantic wsproto
  }
}

# ── 模式選擇 ──────────────────────────────────────────────────
echo "[2/4] 模式：$MODE"

probe_gateway() {
  curl -sf --max-time 3 "$GATEWAY_URL/health" >/dev/null 2>&1
}

if [ "$MODE" = "auto" ]; then
  echo "    探測 Jetson gateway ($GATEWAY_URL)..."
  if probe_gateway; then
    echo "    ✅ Jetson gateway 通，使用 live 模式"
    MODE="live"
  else
    echo "    ⚠️  Jetson gateway 未回應，降級為 mock 模式"
    MODE="mock"
  fi
fi

# ── 清理舊 process ────────────────────────────────────────────
echo "[3/4] 清理舊 process..."
pkill -f "next dev" 2>/dev/null || true
pkill -f "uvicorn mock_server" 2>/dev/null || true
sleep 1

# ── 啟動 Backend (mock 模式) ─────────────────────────────────
BACK_PID=""
if [ "$MODE" = "mock" ]; then
  need_python_deps
  echo "    啟動 mock_server (port 8080)..."
  cd "$BACKEND_DIR"
  python3 -m uvicorn mock_server:app --port 8080 --host 0.0.0.0 --ws wsproto --log-level warning &
  BACK_PID=$!
  sleep 3
  if ! kill -0 $BACK_PID 2>/dev/null; then
    echo "❌ mock_server 啟動失敗"; exit 1
  fi
  if ! curl -sf --max-time 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
    echo "❌ mock_server 啟動但 /api/health 沒回應"; kill $BACK_PID; exit 1
  fi
  TOTAL=$(curl -sf http://127.0.0.1:8080/api/skill_registry 2>/dev/null \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])' 2>/dev/null || echo "?")
  echo "    ✅ mock_server up — /api/skill_registry total=$TOTAL"
else
  # live 模式 — Jetson gateway 必須要起
  if ! probe_gateway; then
    echo "❌ live 模式但 Jetson gateway 沒回應 ($GATEWAY_URL/health)"
    echo "   選項："
    echo "     1. 在 Jetson 上跑 bash scripts/start_full_demo_tmux.sh"
    echo "     2. 或重新跑：bash $0 --mock"
    exit 1
  fi
  echo "    ✅ Jetson gateway OK"
  # Phase B 新 endpoint 探測（不阻擋啟動，只警告）
  if curl -sf --max-time 3 "$GATEWAY_URL/api/skill_registry" >/dev/null 2>&1; then
    TOTAL=$(curl -sf "$GATEWAY_URL/api/skill_registry" 2>/dev/null \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])' 2>/dev/null || echo "?")
    echo "    ✅ /api/skill_registry total=$TOTAL"
  else
    echo "    ⚠️  Jetson gateway 缺 /api/skill_registry — 可能是舊版（Phase B Day 1 之前）"
  fi
fi

# ── 啟動 Frontend ─────────────────────────────────────────────
echo "[4/4] 啟動 Frontend (port 3000)..."

if [ "$MODE" = "mock" ]; then
  TARGET="http://localhost:8080"
else
  TARGET="$GATEWAY_URL"
fi

cd "$FRONTEND_DIR"
NEXT_PUBLIC_GATEWAY_URL="$TARGET" npm run dev &
FRONT_PID=$!
sleep 5

if ! kill -0 $FRONT_PID 2>/dev/null; then
  echo "❌ Frontend 啟動失敗"
  [ -n "$BACK_PID" ] && kill $BACK_PID 2>/dev/null
  exit 1
fi

echo
echo "════════════════════════════════════════════════"
echo "  PawAI Studio ($MODE)"
echo
echo "  🌐 Studio:     http://localhost:3000/studio"
echo "  📺 Live View:  http://localhost:3000/studio/live"
echo "  🔧 Backend:    $TARGET"
echo "  📡 Events WS:  ${TARGET/http/ws}/ws/events"
if [ "$MODE" = "mock" ]; then
  echo
  echo "  Mock 控制（curl）："
  echo "    觸發 self_introduce:"
  echo "      curl -X POST http://localhost:8080/mock/scenario/self_introduce"
  echo "    切 Nav Gate 紅燈:"
  echo "      curl -X POST -H 'Content-Type: application/json' \\"
  echo "        -d '{\"name\":\"nav_ready\",\"state\":\"false\"}' \\"
  echo "        http://localhost:8080/api/capability"
  echo "    切 Plan B:"
  echo "      curl -X POST -H 'Content-Type: application/json' \\"
  echo "        -d '{\"mode\":\"B\"}' http://localhost:8080/api/plan_mode"
fi
echo
echo "  停止: Ctrl+C"
echo "════════════════════════════════════════════════"

cleanup() {
  echo
  echo "Stopping..."
  [ -n "$BACK_PID" ] && kill $BACK_PID 2>/dev/null
  kill $FRONT_PID 2>/dev/null
  exit 0
}
trap cleanup INT TERM
wait
