#!/usr/bin/env bash
# brain-studio-lane start
# Usage: bash start.sh <minimal|e2e|full|demo> [--studio]
# 包裝既有 scripts/start_*.sh，補 .env source / WORKSPACE override / studio overlay
#
# Modes:
#   minimal  — exec + conv_graph (純文字測 persona)
#   e2e      — minimal + tts (帶 TTS 音訊)
#   full     — go2 + 5 perception + brain + asr/tts/llm + gateway (Jetson tmux 13 windows)
#   demo     — alias for `full --studio` — Roy 5/12 提的「全 perception + brain + Studio frontend」一鍵
#              ← 推薦給「我要直接用 PawAI demo」場景

set -uo pipefail

MODE="${1:-}"
STUDIO=0
shift || true
for arg in "$@"; do
  [ "$arg" = "--studio" ] && STUDIO=1
done

if [[ ! "$MODE" =~ ^(minimal|e2e|full|demo)$ ]]; then
  echo "❌ usage: start.sh <minimal|e2e|full|demo> [--studio]"
  echo "   demo = full + --studio (一鍵全開：5 感知 + brain + Studio frontend)"
  exit 1
fi

# `demo` mode = full + studio overlay baked in
if [ "$MODE" = "demo" ]; then
  MODE="full"
  STUDIO=1
fi

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
JETSON_REPO="${JETSON_REPO:-/home/jetson/elder_and_dog}"
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Preflight ──────────────────────────────────────────────
echo "═══ 跑 preflight ═══"
if ! bash "$SKILL_DIR/preflight.sh" "$MODE" $([ "$STUDIO" = "1" ] && echo "--studio"); then
  echo "❌ preflight 失敗，啟動中止"
  exit 1
fi

# ── Start brain stack on Jetson ────────────────────────────
echo "═══ 啟動 brain stack (mode=$MODE) on $JETSON_HOST ═══"

case "$MODE" in
  minimal)
    # 純 brain（exec + conv_graph），新 6 檔 persona
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t pawai_brain 2>/dev/null; \
      WORKSPACE=$JETSON_REPO PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' bash $JETSON_REPO/scripts/start_pawai_brain_tmux.sh > /dev/null 2>&1"
    sleep 10
    ;;
  e2e)
    # minimal + tts_node window（新 brain + 語音輸出）
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t pawai_brain 2>/dev/null; \
      WORKSPACE=$JETSON_REPO PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' bash $JETSON_REPO/scripts/start_pawai_brain_tmux.sh > /dev/null 2>&1"
    sleep 10
    # 補 tts window — 用 ALSA card name `plughw:CD002AUDIO,0` 不受 card# 漂移影響
    # 偵測 card name 確認 USB 喇叭存在；fallback plughw:0,0
    SPEAKER_NAME=$(ssh $SSH_OPTS "$JETSON_HOST" "aplay -l 2>/dev/null | grep -i 'cd002' | head -1 | sed -E 's/.*\\[([^]]+)\\].*/\\1/' | tr -d '[:space:]' | head -c 16" 2>/dev/null || true)
    if [ -n "$SPEAKER_NAME" ]; then
      SPEAKER_DEVICE="plughw:CD002AUDIO,0"
    else
      SPEAKER_DEVICE="plughw:0,0"
      echo "    ⚠️  CD002 喇叭沒偵測到，fallback plughw:0,0"
    fi
    ssh $SSH_OPTS "$JETSON_HOST" "tmux new-window -t pawai_brain -n tts \
      'cd $JETSON_REPO && set -a && source .env && set +a && \
       source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
       ros2 run speech_processor tts_node --ros-args \
         -p provider:=edge_tts \
         -p local_playback:=true \
         -p local_output_device:=$SPEAKER_DEVICE; bash'"
    sleep 6
    echo "    tts_node 啟在 $SPEAKER_DEVICE"
    ;;
  full)
    # 5/12 update: full mode 走 langgraph engine (CONVERSATION_ENGINE default 已是
    # langgraph since 2fd4aec)，6 檔 persona brain 也會生效。Stale warning 移除。
    # TTS_PROVIDER=openrouter_gemini → quality lane 走 Gemini 3.1 Flash TTS Despina
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t demo 2>/dev/null; \
      WORKSPACE=$JETSON_REPO \
      PAWAI_LLM_MODEL='${PAWAI_LLM_MODEL:-}' \
      PAWAI_LLM_FALLBACK_MODEL='${PAWAI_LLM_FALLBACK_MODEL:-}' \
      TTS_PROVIDER='${TTS_PROVIDER:-openrouter_gemini}' \
      bash $JETSON_REPO/scripts/start_full_demo_tmux.sh > /dev/null 2>&1 &"
    sleep 30  # full demo 啟動較久
    ;;
esac

# ── Studio overlay（gateway + frontend）────────────────────
if [ "$STUDIO" = "1" ]; then
  echo "═══ 啟動 Studio overlay ═══"

  # Gateway on Jetson（除非 full mode 已內含 gateway）
  if [ "$MODE" != "full" ]; then
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t studio_gw 2>/dev/null; \
      tmux new-session -d -s studio_gw -n gateway \
      'cd $JETSON_REPO && set -a && source .env && set +a && \
       source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
       python3 pawai-studio/gateway/studio_gateway.py 2>&1 | tee /tmp/gw.log; bash'"
    sleep 6
    GW_HEALTH=$(ssh $SSH_OPTS "$JETSON_HOST" "curl -s --max-time 3 http://localhost:8080/health" || echo "")
    if echo "$GW_HEALTH" | grep -q '"status":"ok"'; then
      echo "    ✅ Gateway alive at http://$JETSON_TAILSCALE_IP:8080"
    else
      echo "    ⚠️  Gateway health check 失敗，繼續但 frontend 可能連不到"
    fi
  fi

  # Frontend on local（WSL/Mac）
  # SKILL_DIR = .claude/skills/brain-studio-lane/scripts
  # 往上 4 層才到 repo root（scripts → brain-studio-lane → skills → .claude → repo）
  REPO_ROOT="$(cd "$SKILL_DIR/../../../.." && pwd)"
  FRONTEND_DIR="$REPO_ROOT/pawai-studio/frontend"
  if [ -d "$FRONTEND_DIR/node_modules" ]; then
    pkill -f "next.*dev" 2>/dev/null || true
    sleep 1
    cd "$FRONTEND_DIR"
    NEXT_PUBLIC_GATEWAY_URL="http://$JETSON_TAILSCALE_IP:8080" \
      nohup npm run dev > /tmp/studio_frontend.log 2>&1 &
    disown
    sleep 8
    PORT=$(grep -oE 'http://localhost:[0-9]+' /tmp/studio_frontend.log | head -1 | grep -oE '[0-9]+$' || echo "3000")
    echo "    ✅ Frontend at http://localhost:$PORT/studio"
  else
    echo "    ⚠️  $FRONTEND_DIR/node_modules 不存在，跳過 frontend（先 npm install）"
  fi
fi

echo "═══ 啟動完成 ═══"
echo "建議下一步: bash $SKILL_DIR/healthcheck.sh"
