#!/usr/bin/env bash
# brain-studio-lane healthcheck
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source /dev/stdin <<< "$(tr -d '\r' < "$REPO_ROOT/.env")"
  set +a
fi

if [ -f "$REPO_ROOT/.env.local" ]; then
  set -a
  # shellcheck disable=SC1090
  source /dev/stdin <<< "$(tr -d '\r' < "$REPO_ROOT/.env.local")"
  set +a
fi

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"
LOCAL_STUDIO_HOST="${LOCAL_STUDIO_HOST:-127.0.0.1}"
FAILS=0

ros() {
  ssh $SSH_OPTS "$JETSON_HOST" \
    "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && $1" \
    2>/dev/null
}

brain_log() {
  ssh $SSH_OPTS "$JETSON_HOST" "\
    tmux capture-pane -t demo:llm -pJ -S -300 2>/dev/null || \
    tmux capture-pane -t pawai_brain:conv_graph -pJ -S -300 2>/dev/null" \
    2>/dev/null || true
}

echo "=== brain-studio-lane healthcheck ==="

LOG="$(brain_log)"

echo -n "[1] conversation_graph_node ready ... "
if echo "$LOG" | grep -q "conversation_graph_node ready"; then
  echo "OK"
else
  echo "FAIL"
  FAILS=$((FAILS+1))
fi

echo -n "[2] OpenRouter on ... "
if echo "$LOG" | grep -q "openrouter=on"; then
  echo "OK"
elif echo "$LOG" | grep -q "openrouter=off"; then
  echo "WARN off -> RuleBrain fallback path active"
else
  echo "WARN status not found in log"
fi

echo -n "[3] persona load ... "
if echo "$LOG" | grep -qE "loaded directory.*files verified"; then
  echo "OK"
else
  echo "FAIL"
  FAILS=$((FAILS+1))
fi

echo -n "[4] /brain/chat_candidate publisher ... "
if ros "ros2 topic info /brain/chat_candidate 2>/dev/null | grep -q 'Publisher count: [1-9]'"; then
  echo "OK"
else
  echo "FAIL"
  FAILS=$((FAILS+1))
fi

echo -n "[5] /tts publisher ... "
if ros "ros2 topic info /tts 2>/dev/null | grep -q 'Publisher count: [1-9]'"; then
  echo "OK"
else
  echo "WARN no publisher (expected in minimal mode)"
fi

echo -n "[6] tts_node in node list ... "
if ros "ros2 node list 2>/dev/null | grep -q 'tts_node'"; then
  echo "OK"
else
  echo "WARN missing tts_node (expected in minimal mode)"
fi

echo -n "[7] Studio gateway /health ... "
GW_RESP=$(ssh $SSH_OPTS "$JETSON_HOST" "curl -s --max-time 3 http://localhost:8080/health" 2>/dev/null || echo "")
if echo "$GW_RESP" | grep -q '"status":"ok"'; then
  WS_CLIENTS=$(echo "$GW_RESP" | grep -oE '"ws_clients":[0-9]+' | grep -oE '[0-9]+$' || echo "?")
  SUB_COUNT=$(echo "$GW_RESP" | grep -oE '"subscriptions":\[[^]]*\]' | grep -oc '"/' || echo "?")
  echo "OK ws_clients=$WS_CLIENTS subs=$SUB_COUNT"
else
  echo "WARN missing (expected when --studio is off)"
fi

echo -n "[8] Frontend port 3000/3001 ... "
PORT=$(grep -oE 'http://localhost:[0-9]+' /tmp/studio_frontend.log 2>/dev/null | head -1 | grep -oE '[0-9]+$' || echo "")
if [ -n "$PORT" ] && curl -s --max-time 20 "http://$LOCAL_STUDIO_HOST:$PORT/studio" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200"; then
  echo "OK http://localhost:$PORT/studio"
else
  echo "WARN missing or still compiling"
fi

echo "=== healthcheck result ==="
if [ "$FAILS" = "0" ]; then
  echo "PASS"
  exit 0
else
  echo "FAIL $FAILS blocking checks"
  exit 1
fi
