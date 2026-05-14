#!/usr/bin/env bash
# brain-studio-lane start
set -uo pipefail

MODE="${1:-}"
STUDIO=0
AUTO_CLEAN=1
shift || true
for arg in "$@"; do
  case "$arg" in
    --studio) STUDIO=1 ;;
    --no-clean) AUTO_CLEAN=0 ;;
  esac
done

if [[ ! "$MODE" =~ ^(minimal|e2e|full|demo)$ ]]; then
  echo "usage: start.sh <minimal|e2e|full|demo> [--studio] [--no-clean]"
  exit 1
fi

if [ "$MODE" = "demo" ]; then
  MODE="full"
  STUDIO=1
fi

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
JETSON_REPO="${JETSON_REPO:-/home/jetson/elder_and_dog}"
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"
LOCAL_STUDIO_HOST="${LOCAL_STUDIO_HOST:-127.0.0.1}"

wait_for_http() {
  local url="$1"
  local timeout_s="$2"
  local elapsed=0
  local body=""
  while [ "$elapsed" -lt "$timeout_s" ]; do
    body=$(curl -s --max-time 3 "$url" 2>/dev/null || true)
    if [ -n "$body" ]; then
      printf '%s' "$body"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

wait_for_status_200() {
  local url="$1"
  local timeout_s="$2"
  local elapsed=0
  local code=""
  while [ "$elapsed" -lt "$timeout_s" ]; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" --max-time 5 2>/dev/null || true)
    if [ "$code" = "200" ]; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

echo "═══ 偵測舊 lane 狀態 ═══"
if [ "$AUTO_CLEAN" = "1" ]; then
  JETSON_OLD=$(ssh $SSH_OPTS "$JETSON_HOST" \
    "tmux ls 2>/dev/null | grep -E '^(demo|pawai_brain|studio_gw|llm-e2e):' | head -3" \
    2>/dev/null || true)
  LOCAL_OLD=$(pgrep -f "next.*dev" 2>/dev/null | head -1 || true)

  if [ -n "$JETSON_OLD" ] || [ -n "$LOCAL_OLD" ]; then
    [ -n "$JETSON_OLD" ] && echo "    🔍 Jetson 舊 tmux: $(echo "$JETSON_OLD" | tr '\n' ' ')"
    [ -n "$LOCAL_OLD" ] && echo "    🔍 本機 next dev pid: $LOCAL_OLD"
    echo "    ⏳ 自動呼叫 cleanup.sh 清掉舊 lane（--no-clean 可跳過）..."
    bash "$SCRIPT_DIR/cleanup.sh" --handoff none > /dev/null 2>&1 || true
    sleep 1
    echo "    ✅ cleanup 完成"
  else
    echo "    ✅ 沒有舊 lane 殘留"
  fi
fi

echo "═══ 跑 preflight ═══"
if ! bash "$SCRIPT_DIR/preflight.sh" "$MODE" $([ "$STUDIO" = "1" ] && echo "--studio"); then
  echo "❌ preflight 失敗，停止啟動"
  exit 1
fi

echo "═══ 啟動 brain stack (mode=$MODE) on jetson ═══"
case "$MODE" in
  minimal)
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t pawai_brain 2>/dev/null; \
      WORKSPACE=$JETSON_REPO PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' \
      bash $JETSON_REPO/scripts/start_pawai_brain_tmux.sh > /dev/null 2>&1"
    sleep 10
    ;;
  e2e)
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t pawai_brain 2>/dev/null; \
      WORKSPACE=$JETSON_REPO PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' \
      bash $JETSON_REPO/scripts/start_pawai_brain_tmux.sh > /dev/null 2>&1"
    sleep 10
    SPEAKER_NAME=$(ssh $SSH_OPTS "$JETSON_HOST" \
      "aplay -l 2>/dev/null | grep -i 'cd002' | head -1 | sed -E 's/.*\\[([^]]+)\\].*/\\1/' | tr -d '[:space:]' | head -c 16" \
      2>/dev/null || true)
    if [ -n "$SPEAKER_NAME" ]; then
      SPEAKER_DEVICE="plughw:CD002AUDIO,0"
    else
      SPEAKER_DEVICE="plughw:0,0"
      echo "    ⚠️  CD002 喇叭沒抓到，退回 plughw:0,0"
    fi
    ssh $SSH_OPTS "$JETSON_HOST" "tmux new-window -t pawai_brain -n tts \
      'cd $JETSON_REPO && set -a && source .env && set +a && \
       source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
       ros2 run speech_processor tts_node --ros-args \
         -p provider:=edge_tts \
         -p local_playback:=true \
         -p local_output_device:=$SPEAKER_DEVICE; bash'"
    sleep 6
    echo "    tts_node 已起在 $SPEAKER_DEVICE"
    ;;
  full)
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t demo 2>/dev/null; \
      WORKSPACE=$JETSON_REPO \
      PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' \
      PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' \
      TTS_PROVIDER='${TTS_PROVIDER:-openrouter_gemini}' \
      bash $JETSON_REPO/scripts/start_full_demo_tmux.sh > /dev/null 2>&1 &"
    sleep 30
    ;;
esac

if [ "$STUDIO" = "1" ]; then
  echo "═══ 啟動 Studio overlay ═══"

  if [ "$MODE" != "full" ]; then
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t studio_gw 2>/dev/null; \
      tmux new-session -d -s studio_gw -n gateway \
      'cd $JETSON_REPO && set -a && source .env && set +a && \
       source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
       python3 pawai-studio/gateway/studio_gateway.py 2>&1 | tee /tmp/gw.log; bash'"
    sleep 6
  fi

  FRONTEND_DIR="$REPO_ROOT/pawai-studio/frontend"

  if [ ! -f "$FRONTEND_DIR/.env.local" ] && [ -f "$FRONTEND_DIR/.env.local.example" ]; then
    sed "s|NEXT_PUBLIC_GATEWAY_HOST=.*|NEXT_PUBLIC_GATEWAY_HOST=$JETSON_TAILSCALE_IP|" \
      "$FRONTEND_DIR/.env.local.example" > "$FRONTEND_DIR/.env.local"
    echo "    ✅ 寫入 $FRONTEND_DIR/.env.local (gateway=$JETSON_TAILSCALE_IP)"
  fi

  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "    ⏳ node_modules 不存在，先跑 npm install ..."
    if ! (cd "$FRONTEND_DIR" && npm install --no-audit --no-fund > /tmp/studio_npm_install.log 2>&1); then
      echo "    ❌ npm install 失敗，請看 /tmp/studio_npm_install.log"
      exit 1
    fi
    echo "    ✅ npm install 完成"
  fi

  pkill -f "next.*dev" 2>/dev/null || true
  sleep 1
  cd "$FRONTEND_DIR"
  if [ ! -x "$FRONTEND_DIR/node_modules/.bin/next" ]; then
    echo "    ❌ node_modules/.bin/next 不存在"
    exit 1
  fi

  NEXT_PUBLIC_GATEWAY_URL="http://$JETSON_TAILSCALE_IP:8080" \
    nohup "$FRONTEND_DIR/node_modules/.bin/next" dev > /tmp/studio_frontend.log 2>&1 &
  disown
  sleep 8

  PORT=$(grep -oE 'http://localhost:[0-9]+' /tmp/studio_frontend.log | head -1 | grep -oE '[0-9]+$' || echo "3000")

  GW_REMOTE=$(ssh $SSH_OPTS "$JETSON_HOST" "curl -s --max-time 3 http://localhost:8080/health" 2>/dev/null || echo "")
  GW_LOCAL=$(wait_for_http "http://$JETSON_TAILSCALE_IP:8080/health" 15 || echo "")
  if echo "$GW_LOCAL" | grep -q '"status":"ok"'; then
    echo "    ✅ Gateway reachable from local: http://$JETSON_TAILSCALE_IP:8080"
  elif echo "$GW_REMOTE" | grep -q '"status":"ok"'; then
    echo "    ✅ Gateway alive on Jetson: http://$JETSON_TAILSCALE_IP:8080"
  else
    echo "    ⚠️  Gateway health probe failed on Jetson and local path，請看 demo:gateway"
  fi

  if wait_for_status_200 "http://$LOCAL_STUDIO_HOST:$PORT/studio" 30; then
    echo "    ✅ Frontend: http://localhost:$PORT/studio"
  elif grep -q "Ready in" /tmp/studio_frontend.log 2>/dev/null; then
    echo "    ✅ Frontend dev server ready: http://localhost:$PORT/studio"
  else
    echo "    ⚠️  Frontend dev server did not become ready，請看 /tmp/studio_frontend.log"
  fi
fi

echo "═══ 啟動完成 ═══"
echo "建議下一步: bash $SCRIPT_DIR/healthcheck.sh"
