#!/usr/bin/env bash
# brain-studio-lane preflight
# Usage: bash preflight.sh <mode> [--studio]
#   mode: minimal | e2e | full
# Exit 0: OK to start (P1 warnings allowed)
# Exit 1: P0 fail, do not start

set -uo pipefail  # 不用 -e；要自己處理每個 check 的 exit code

MODE="${1:-}"
STUDIO=0
shift || true
for arg in "$@"; do
  [ "$arg" = "--studio" ] && STUDIO=1
done

if [[ ! "$MODE" =~ ^(minimal|e2e|full)$ ]]; then
  echo "❌ usage: preflight.sh <minimal|e2e|full> [--studio]"
  exit 1
fi

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
JETSON_REPO="${JETSON_REPO:-/home/jetson/elder_and_dog}"
P0_FAIL=0
P1_WARN=0

echo "═══ brain-studio-lane preflight (mode=$MODE studio=$STUDIO) ═══"

# ── P0: SSH 通 ─────────────────────────────────────────────
echo -n "[P0] SSH to $JETSON_HOST ... "
if ssh $SSH_OPTS -o BatchMode=yes "$JETSON_HOST" "echo ok" >/dev/null 2>&1; then
  echo "✅"
else
  echo "❌ SSH 不通，檢查 Tailscale / hosts"
  P0_FAIL=1
fi

# ── P0: .env 存在 ───────────────────────────────────────────
echo -n "[P0] $JETSON_REPO/.env 存在 ... "
if ssh $SSH_OPTS "$JETSON_HOST" "[ -f $JETSON_REPO/.env ]" 2>/dev/null; then
  echo "✅"
else
  echo "❌ Jetson 上 $JETSON_REPO/.env 不存在 → conversation_graph 會 fallback RuleBrain"
  P0_FAIL=1
fi

# ── P0: persona 6 檔（minimal/e2e）──────────────────────────
# 跟 start_pawai_brain_tmux.sh 同一套 resolve：先 install path，找不到 fallback source tree
if [[ "$MODE" =~ ^(minimal|e2e)$ ]]; then
  echo -n "[P0] persona 6 檔（install or source tree）... "
  COUNT=$(ssh $SSH_OPTS "$JETSON_HOST" "
    INSTALL_DIR=$JETSON_REPO/install/pawai_brain/share/pawai_brain/personas/v1
    SOURCE_DIR=$JETSON_REPO/pawai_brain/personas/v1
    if [ -d \"\$INSTALL_DIR\" ]; then ls \$INSTALL_DIR/*.md 2>/dev/null | wc -l;
    elif [ -d \"\$SOURCE_DIR\" ]; then ls \$SOURCE_DIR/*.md 2>/dev/null | wc -l;
    else echo 0; fi
  " 2>/dev/null || echo 0)
  if [ "$COUNT" -ge 6 ]; then
    echo "✅ ($COUNT 檔)"
  else
    echo "❌ 只有 $COUNT 檔（需要 6）→ source tree 也沒有 → 檢查 git pull / colcon build pawai_brain"
    P0_FAIL=1
  fi
fi

# ── P0: port 8080 沒被占用（--studio 才檢）─────────────────
if [ "$STUDIO" = "1" ]; then
  echo -n "[P0] Jetson port 8080 空閒 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "ss -tln 2>/dev/null | grep -q ':8080 '" 2>/dev/null; then
    echo "❌ 8080 被占用 → 先 cleanup"
    P0_FAIL=1
  else
    echo "✅"
  fi
fi

# ── P1: OPENROUTER_KEY / OPENROUTER_API_KEY 在 .env ────────
# resolve_openrouter_key() 兩個 key name 都接受 (`OPENROUTER_KEY` 優先)
echo -n "[P1] .env 包含 OPENROUTER_KEY 或 OPENROUTER_API_KEY ... "
if ssh $SSH_OPTS "$JETSON_HOST" "grep -qE '^OPENROUTER(_API)?_KEY=' $JETSON_REPO/.env 2>/dev/null"; then
  echo "✅"
else
  echo "⚠️  缺 → conv_graph 會 fallback RuleBrain（仍可跑）"
  P1_WARN=1
fi

# ── P1: LLM tunnel ─────────────────────────────────────────
echo -n "[P1] LLM tunnel localhost:8000/health ... "
if ssh $SSH_OPTS "$JETSON_HOST" "curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://localhost:8000/health 2>/dev/null | grep -q 200"; then
  echo "✅"
else
  echo "⚠️  tunnel 沒通 → cloud LLM 失敗 fallback local"
  P1_WARN=1
fi

# ── P1: ASR tunnel（e2e/full）──────────────────────────────
if [[ "$MODE" =~ ^(e2e|full)$ ]]; then
  echo -n "[P1] ASR tunnel localhost:8001 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "ss -tln 2>/dev/null | grep -q ':8001 '"; then
    echo "✅"
  else
    echo "⚠️  ASR tunnel 沒通 → fallback whisper_local"
    P1_WARN=1
  fi
fi

# ── P1: USB 喇叭（e2e/full）────────────────────────────────
if [[ "$MODE" =~ ^(e2e|full)$ ]]; then
  echo -n "[P1] CD002-AUDIO USB 喇叭 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "aplay -l 2>/dev/null | grep -qi 'cd002'"; then
    echo "✅"
  else
    echo "⚠️  找不到外接喇叭 → TTS 仍會 publish 但無實體聲音"
    P1_WARN=1
  fi
fi

# ── P1: 沒有 nav_* tmux session ────────────────────────────
echo -n "[P1] 沒有 nav_* tmux session ... "
NAV_SESSIONS=$(ssh $SSH_OPTS "$JETSON_HOST" "tmux ls 2>/dev/null | grep -E '^(nav|lidar|reactive|b5)-' | wc -l" 2>/dev/null || echo 0)
if [ "$NAV_SESSIONS" = "0" ]; then
  echo "✅"
else
  echo "⚠️  $NAV_SESSIONS 個 nav 相關 session 在跑 → 建議先 nav-avoidance-lane cleanup --handoff brain"
  P1_WARN=1
fi

# ── 總結 ───────────────────────────────────────────────────
echo "═══ preflight 結果 ═══"
if [ "$P0_FAIL" = "1" ]; then
  echo "❌ P0 FAIL — 不可啟動，請先修復"
  exit 1
fi
if [ "$P1_WARN" = "1" ]; then
  echo "⚠️  P1 warning（可啟動，已知 fallback 路徑）"
fi
echo "✅ Preflight pass — 可啟動 mode=$MODE"
exit 0
