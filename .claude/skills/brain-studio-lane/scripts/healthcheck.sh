#!/usr/bin/env bash
# brain-studio-lane healthcheck
# Verify topics / openrouter / persona / gateway / frontend
set -uo pipefail

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"
FAILS=0

ros() { ssh $SSH_OPTS "$JETSON_HOST" "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && $1" 2>/dev/null; }

echo "═══ brain-studio-lane healthcheck ═══"

# ── conv_graph ready + openrouter on + persona 6 檔 ────────
# `-J` joins wrapped lines（避免 80 字元換行讓 grep 抓不到 "loaded directory ... 6 files verified"）
LOG=$(ssh $SSH_OPTS "$JETSON_HOST" "tmux capture-pane -t pawai_brain:conv_graph -pJ -S -300 2>/dev/null" || echo "")
echo -n "[1] conversation_graph_node ready ... "
if echo "$LOG" | grep -q "conversation_graph_node ready"; then echo "✅"; else echo "❌"; FAILS=$((FAILS+1)); fi

echo -n "[2] OpenRouter on ... "
if echo "$LOG" | grep -q "openrouter=on"; then
  echo "✅"
elif echo "$LOG" | grep -q "openrouter=off"; then
  echo "⚠️  off → 走 RuleBrain（檢查 .env 是否包含 OPENROUTER_API_KEY 且 SOURCE_CMD 有 source .env）"
else
  echo "?  log 沒抓到 openrouter 狀態"
fi

echo -n "[3] persona 6 檔載入 ... "
if echo "$LOG" | grep -qE "loaded directory.*6 files verified"; then echo "✅"; else echo "❌"; FAILS=$((FAILS+1)); fi

# ── topics ─────────────────────────────────────────────────
echo -n "[4] /brain/chat_candidate 有 publisher ... "
if ros "ros2 topic info /brain/chat_candidate 2>/dev/null | grep -q 'Publisher count: [1-9]'"; then echo "✅"; else echo "❌"; FAILS=$((FAILS+1)); fi

echo -n "[5] /tts 有 publisher ... "
if ros "ros2 topic info /tts 2>/dev/null | grep -q 'Publisher count: [1-9]'"; then
  echo "✅"
else
  echo "⚠️  沒 publisher（minimal mode 是預期，e2e/full 該有）"
fi

# ── tts_node alive（如果有起）──────────────────────────────
echo -n "[6] tts_node 在 node list ... "
if ros "ros2 node list 2>/dev/null | grep -q 'tts_node'"; then echo "✅"; else echo "—  沒起 tts_node（minimal mode 預期）"; fi

# ── Studio gateway ─────────────────────────────────────────
echo -n "[7] Studio gateway /health ... "
GW_RESP=$(ssh $SSH_OPTS "$JETSON_HOST" "curl -s --max-time 3 http://localhost:8080/health" 2>/dev/null || echo "")
if echo "$GW_RESP" | grep -q '"status":"ok"'; then
  WS_CLIENTS=$(echo "$GW_RESP" | grep -oE '"ws_clients":[0-9]+' | grep -oE '[0-9]+$' || echo "?")
  SUB_COUNT=$(echo "$GW_RESP" | grep -oE '"subscriptions":\[[^]]*\]' | grep -oc '"/' || echo "?")
  echo "✅ ws_clients=$WS_CLIENTS subs=$SUB_COUNT"
else
  echo "—  沒起（沒帶 --studio 是預期）"
fi

# ── Frontend ───────────────────────────────────────────────
echo -n "[8] Frontend port 3000/3001 ... "
PORT=$(grep -oE 'http://localhost:[0-9]+' /tmp/studio_frontend.log 2>/dev/null | head -1 | grep -oE '[0-9]+$' || echo "")
if [ -n "$PORT" ] && curl -s --max-time 2 "http://localhost:$PORT/studio" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200"; then
  echo "✅ http://localhost:$PORT/studio"
else
  echo "—  沒起（沒帶 --studio 是預期）"
fi

# ── 總結 ───────────────────────────────────────────────────
echo "═══ healthcheck 結果 ═══"
if [ "$FAILS" = "0" ]; then
  echo "✅ 全綠"
  exit 0
else
  echo "❌ $FAILS 項 fail，brain stack 沒完全 ready"
  exit 1
fi
