#!/usr/bin/env bash
# brain-studio-lane start
# Usage: bash start.sh <minimal|e2e|full|demo> [--studio] [--no-clean]
# 包裝既有 scripts/start_*.sh，補 .env source / WORKSPACE override / studio overlay
#
# Modes:
#   minimal  — exec + conv_graph (純文字測 persona)
#   e2e      — minimal + tts (帶 TTS 音訊)
#   full     — go2 + 5 perception + brain + asr/tts/llm + gateway (Jetson tmux 13 windows)
#   demo     — alias for `full --studio` — Roy 5/12 提的「全 perception + brain + Studio frontend」一鍵
#              ← 推薦給「我要直接用 PawAI demo」場景
#
# Auto-cleanup（5/11 N6 review）：start.sh 預設先偵測是否有舊 lane 在跑
# （Jetson tmux session demo/pawai_brain/studio_gw 或本機 frontend next dev）
# 有的話自動呼叫 cleanup.sh 再進 preflight，省去手動 cleanup 一步。
# `--no-clean` 跳過自動清理（debug 用：保留舊 state 進入新一輪 preflight）。

set -uo pipefail

MODE="${1:-}"
STUDIO=0
AUTO_CLEAN=1
shift || true
for arg in "$@"; do
  case "$arg" in
    --studio)   STUDIO=1 ;;
    --no-clean) AUTO_CLEAN=0 ;;
  esac
done

if [[ ! "$MODE" =~ ^(minimal|e2e|full|demo)$ ]]; then
  echo "❌ usage: start.sh <minimal|e2e|full|demo> [--studio] [--no-clean]"
  echo "   demo = full + --studio (一鍵全開：5 感知 + brain + Studio frontend)"
  echo "   --no-clean = 跳過自動 cleanup（debug 用，預設會先清舊 lane）"
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
if [ -z "${JETSON_TAILSCALE_IP:-}" ]; then
  echo "✗ JETSON_TAILSCALE_IP is unset" >&2
  echo "  → set it in .env.local, or run via: pawai demo start" >&2
  echo "  → CLI auto-detects via Tailscale; bare bash invocation must export it first" >&2
  exit 2
fi
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Values below are embedded into SSH command strings. Use bash-safe quoting so
# .env.local values containing spaces, quotes, JSON, or shell metacharacters
# survive the remote shell parse as data, not code.
SAFE_JETSON_REPO=$(printf %q "$JETSON_REPO")
SAFE_PAWAI_LLM_MODEL=$(printf %q "${PAWAI_LLM_MODEL:-}")
SAFE_PAWAI_LLM_FALLBACK_MODEL=$(printf %q "${PAWAI_LLM_FALLBACK_MODEL:-}")
SAFE_TTS_PROVIDER=$(printf %q "${TTS_PROVIDER:-openrouter_gemini}")
SAFE_ASR_PROVIDER_ORDER=$(printf %q "${ASR_PROVIDER_ORDER:-}")

# ── Auto-cleanup（5/11 N6 review）─────────────────────────
# 偵測是否有舊 lane 殘留：Jetson tmux session demo/pawai_brain/studio_gw 任一
# 存在，或本機 frontend `next dev` process 在跑。任一命中就呼叫 cleanup.sh。
if [ "$AUTO_CLEAN" = "1" ]; then
  echo "═══ 偵測舊 lane 狀態 ═══"
  JETSON_OLD=$(ssh $SSH_OPTS "$JETSON_HOST" \
    "tmux ls 2>/dev/null | grep -E '^(demo|pawai_brain|studio_gw|llm-e2e):' | head -3" \
    2>/dev/null || true)
  LOCAL_OLD=$(pgrep -f "next.*dev" 2>/dev/null | head -1 || true)

  if [ -n "$JETSON_OLD" ] || [ -n "$LOCAL_OLD" ]; then
    [ -n "$JETSON_OLD" ] && echo "    🔍 Jetson 殘留 tmux: $(echo "$JETSON_OLD" | tr '\n' ' ')"
    [ -n "$LOCAL_OLD" ] && echo "    🔍 本機 next dev pid: $LOCAL_OLD"
    echo "    ⏳ 自動呼叫 cleanup.sh 清掉舊 lane（--no-clean 可跳過）..."
    bash "$SKILL_DIR/cleanup.sh" --handoff none > /dev/null 2>&1 || true
    sleep 1
    echo "    ✅ cleanup 完成"
  else
    echo "    ✅ 沒有舊 lane 殘留"
  fi
fi

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
      WORKSPACE=$SAFE_JETSON_REPO \
      PAWAI_LLM_MODEL=$SAFE_PAWAI_LLM_MODEL \
      PAWAI_LLM_FALLBACK_MODEL=$SAFE_PAWAI_LLM_FALLBACK_MODEL \
      ASR_PROVIDER_ORDER=$SAFE_ASR_PROVIDER_ORDER \
      bash $SAFE_JETSON_REPO/scripts/start_pawai_brain_tmux.sh > /dev/null 2>&1"
    sleep 10
    ;;
  e2e)
    # minimal + tts_node window（新 brain + 語音輸出）
    ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t pawai_brain 2>/dev/null; \
      WORKSPACE=$SAFE_JETSON_REPO \
      PAWAI_LLM_MODEL=$SAFE_PAWAI_LLM_MODEL \
      PAWAI_LLM_FALLBACK_MODEL=$SAFE_PAWAI_LLM_FALLBACK_MODEL \
      ASR_PROVIDER_ORDER=$SAFE_ASR_PROVIDER_ORDER \
      bash $SAFE_JETSON_REPO/scripts/start_pawai_brain_tmux.sh > /dev/null 2>&1"
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
      WORKSPACE=$SAFE_JETSON_REPO \
      PAWAI_LLM_MODEL=$SAFE_PAWAI_LLM_MODEL \
      PAWAI_LLM_FALLBACK_MODEL=$SAFE_PAWAI_LLM_FALLBACK_MODEL \
      TTS_PROVIDER=$SAFE_TTS_PROVIDER \
      ASR_PROVIDER_ORDER=$SAFE_ASR_PROVIDER_ORDER \
      bash $SAFE_JETSON_REPO/scripts/start_full_demo_tmux.sh > /dev/null 2>&1 &"
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

  # 1) .env.local 不存在 → 自動從 example 生（替換 Tailscale IP）
  if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
    if [ -f "$FRONTEND_DIR/.env.local.example" ]; then
      sed "s|NEXT_PUBLIC_GATEWAY_HOST=.*|NEXT_PUBLIC_GATEWAY_HOST=$JETSON_TAILSCALE_IP|" \
        "$FRONTEND_DIR/.env.local.example" > "$FRONTEND_DIR/.env.local"
      echo "    ✅ 寫入 $FRONTEND_DIR/.env.local (gateway=$JETSON_TAILSCALE_IP)"
    fi
  fi

  # 2) node_modules 不存在 → 主動跑 npm install（block 直到完成）
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "    ⏳ $FRONTEND_DIR/node_modules 不存在，跑 npm install（首次約 2 分鐘）..."
    if ! (cd "$FRONTEND_DIR" && npm install --no-audit --no-fund > /tmp/studio_npm_install.log 2>&1); then
      echo "    ❌ npm install 失敗，看 /tmp/studio_npm_install.log"
      echo "    ⚠️  Jetson stack 已啟動，但 Studio frontend 未起 — 修完 npm install 後可單獨 rerun"
      exit 1
    fi
    echo "    ✅ npm install 完成"
  fi

  # 3) 起 frontend（用 node_modules/.bin/next 直接呼叫，繞 npm/pnpm wrapper 的 pre-hook）
  pkill -f "next.*dev" 2>/dev/null || true
  sleep 1
  cd "$FRONTEND_DIR"
  if [ ! -x "$FRONTEND_DIR/node_modules/.bin/next" ]; then
    echo "    ❌ node_modules/.bin/next 不存在（install 不完整？）"
    exit 1
  fi
  NEXT_PUBLIC_GATEWAY_URL="http://$JETSON_TAILSCALE_IP:8080" \
    nohup "$FRONTEND_DIR/node_modules/.bin/next" dev > /tmp/studio_frontend.log 2>&1 &
  disown
  sleep 8
  PORT=$(grep -oE 'http://localhost:[0-9]+' /tmp/studio_frontend.log | head -1 | grep -oE '[0-9]+$' || echo "3000")

  # 4) Healthcheck from local — gateway 必須從 Mac browser 端可達
  GW_LOCAL=$(curl -s --max-time 3 "http://$JETSON_TAILSCALE_IP:8080/health" 2>/dev/null || echo "")
  if echo "$GW_LOCAL" | grep -q '"status":"ok"'; then
    echo "    ✅ Gateway reachable from local: http://$JETSON_TAILSCALE_IP:8080"
  else
    echo "    ⚠️  Gateway 從本機連不到 http://$JETSON_TAILSCALE_IP:8080 — 檢查 Tailscale + JETSON_TAILSCALE_IP"
  fi

  # 5) Frontend port probe
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/studio" --max-time 5 | grep -q "200"; then
    echo "    ✅ Frontend: http://localhost:$PORT/studio"
  else
    echo "    ⚠️  Frontend port $PORT 沒回 200，看 /tmp/studio_frontend.log"
  fi
fi

echo "═══ 啟動完成 ═══"
echo "建議下一步: bash $SKILL_DIR/healthcheck.sh"
