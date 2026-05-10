#!/usr/bin/env bash
# brain-studio-lane cleanup
# Usage: bash cleanup.sh [--handoff nav|none]
#
# ⚠️ Driver reuse 機制尚未實作 — 兩個 handoff 值都會清 go2_driver。
# --handoff 旗標目前只影響 cleanup 完的提示文字（hint 給下一步該跑啥）。
#   --handoff nav  : 清全部 + 提示「下一步建議 nav-avoidance-lane start」
#   --handoff none : 清全部 + 提示「完整清理完成」（預設）

set -uo pipefail

HANDOFF="none"
for arg in "$@"; do
  case "$arg" in
    --handoff) shift; HANDOFF="${1:-none}" ;;
    --handoff=*) HANDOFF="${arg#*=}" ;;
    nav|none|brain) HANDOFF="$arg" ;;
  esac
done

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"

echo "═══ brain-studio-lane cleanup (handoff=$HANDOFF) ═══"

# ── 殺 frontend (local) ────────────────────────────────────
echo "[1] 殺 frontend (next dev) ..."
pkill -f "next.*dev" 2>/dev/null && echo "    ✅ frontend killed" || echo "    — 沒在跑"

# ── 殺 brain tmux + studio_gw + tts_node ──────────────────
echo "[2] 殺 Jetson tmux sessions ..."
ssh $SSH_OPTS "$JETSON_HOST" "tmux kill-session -t pawai_brain 2>/dev/null; \
                    tmux kill-session -t studio_gw 2>/dev/null; \
                    tmux kill-session -t demo 2>/dev/null; \
                    tmux kill-session -t llm-e2e 2>/dev/null"
echo "    ✅ tmux cleared (pawai_brain / studio_gw / demo / llm-e2e)"

# ── pkill brain-only processes（保險）──────────────────────
echo "[3] pkill brain-only processes ..."
ssh $SSH_OPTS "$JETSON_HOST" "pkill -9 -f conversation_graph_node 2>/dev/null; \
                    pkill -9 -f tts_node 2>/dev/null; \
                    pkill -9 -f studio_gateway 2>/dev/null; \
                    pkill -9 -f stt_intent_node 2>/dev/null; \
                    pkill -9 -f llm_bridge_node 2>/dev/null; \
                    pkill -9 -f interaction_executive 2>/dev/null"
echo "    ✅ brain processes killed"

# ── 一律清 go2_driver（reuse driver 設計尚未實作）─────────
# 注意：handoff 旗標目前**不影響 driver 是否清**，只影響 cleanup 後的提示。
# 真正 reuse 既有 driver 需要 nav lane start 改成偵測+skip，目前 nav start
# 直接呼叫 start_*_tmux.sh 都會自啟 driver instance。為避免雙 driver 衝突，
# 兩個 lane cleanup 一律清 driver。
echo "[4] 清 go2_driver + 相關 C++ 子 process ..."
ssh $SSH_OPTS "$JETSON_HOST" "pkill -9 -f go2_driver 2>/dev/null; \
                    pkill -9 -f robot_state 2>/dev/null; \
                    pkill -9 -f pointcloud 2>/dev/null; \
                    pkill -9 -f joy_node 2>/dev/null; \
                    pkill -9 -f teleop 2>/dev/null; \
                    pkill -9 -f twist_mux 2>/dev/null"
echo "    ✅ go2_driver + 相關 process killed"

case "$HANDOFF" in
  nav)
    echo "    💡 下一步建議：bash .claude/skills/nav-avoidance-lane/scripts/start.sh <mode>"
    ;;
  none|brain|*)
    echo "    💡 完整清理完成"
    ;;
esac

# ── 確認 ───────────────────────────────────────────────────
sleep 1
RESIDUAL=$(ssh $SSH_OPTS "$JETSON_HOST" "ps aux 2>/dev/null | grep -E 'conversation_graph|tts_node|studio_gateway|llm_bridge' | grep -v grep | wc -l" 2>/dev/null || echo "?")
echo "═══ cleanup 完成 (殘留 brain process: $RESIDUAL) ═══"
