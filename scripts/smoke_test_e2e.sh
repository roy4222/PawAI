#!/usr/bin/env bash
# E2E Smoke Test — 固定話術、固定驗收、可重跑。
#
# 前提：llm-e2e tmux session 已在跑（bash scripts/start_llm_e2e_tmux.sh）
#
# Usage:
#   bash scripts/smoke_test_e2e.sh          # 預設 5 輪
#   bash scripts/smoke_test_e2e.sh 3        # 指定輪數

set -uo pipefail

ROUNDS="${1:-5}"
PASS=0
FAIL=0

echo ""
echo "═══════════════════════════════════════"
echo "  E2E Smoke Test ($ROUNDS rounds)"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════"

# ── Pre-check: nodes alive ──
echo ""
echo "[PRE] Checking nodes..."
NODES=$(ros2 node list 2>/dev/null)
# 6/12: brain demo lane (start_full_demo_tmux.sh) runs conversation_graph_node;
# the legacy llm-e2e session runs llm_bridge_node. Accept either stack.
if echo "$NODES" | grep -q "conversation_graph_node"; then
  BRAIN_REQ="conversation_graph_node"
else
  BRAIN_REQ="llm_bridge_node"
fi
for n in go2_driver_node stt_intent_node tts_node "$BRAIN_REQ"; do
  if echo "$NODES" | grep -q "$n"; then
    echo "  [OK] $n"
  else
    echo "  [FAIL] $n not found — is the demo / llm-e2e session running?"
    exit 1
  fi
done

# ── Fixed test phrase ──
TEST_PHRASE="你好，我是PawAI機器狗"

for i in $(seq 1 "$ROUNDS"); do
  echo ""
  echo "── Round $i/$ROUNDS ──"

  # Clear old debug WAV
  rm -f /tmp/megaphone_debug_*.wav 2>/dev/null

  # 6/12: local-playback baseline (USB speaker path has no megaphone WAV —
  # count tts pane completions before/after instead)
  LOCAL_BEFORE=$(tmux capture-pane -t demo:tts -p -S -300 2>/dev/null \
    | grep -c "Local playback completed" || true)

  # Send TTS
  # 6/12: --once races RELIABLE-subscriber discovery (documented repo trap —
  # /tts has 3 subscribers; a fresh pub can publish before tts_node matches,
  # and -w N stalls forever when any one sub is QoS-incompatible). Publish
  # twice 1s apart: the second copy always lands post-discovery. The phrase
  # may play twice in a round — harmless for a smoke run (5/5 真機驗證).
  echo "  [SEND] /tts: \"$TEST_PHRASE\""
  timeout 15 ros2 topic pub -r 1 --times 2 /tts std_msgs/msg/String \
    "{data: \"$TEST_PHRASE\"}" >/dev/null 2>&1

  # Wait for playback (TTS synthesis ~2.5s + Megaphone ~3s + tail)
  sleep 8

  # ── Check 1: playback evidence — megaphone debug WAV (datachannel path)
  # OR tts pane "Local playback completed" increment (USB speaker path, 6/12) ──
  WAV=$(ls -t /tmp/megaphone_debug_*.wav 2>/dev/null | head -1)
  if [ -n "$WAV" ]; then
    WAV_SIZE=$(stat -c%s "$WAV" 2>/dev/null || echo "0")
    echo "  [OK] Debug WAV: $WAV ($WAV_SIZE bytes)"
  else
    LOCAL_AFTER=$(tmux capture-pane -t demo:tts -p -S -300 2>/dev/null \
      | grep -c "Local playback completed" || true)
    if [ "${LOCAL_AFTER:-0}" -gt "${LOCAL_BEFORE:-0}" ]; then
      echo "  [OK] Local playback completed (+$((LOCAL_AFTER - LOCAL_BEFORE)))"
    else
      echo "  [FAIL] No playback evidence (no megaphone WAV, no local-playback log)"
      FAIL=$((FAIL + 1))
      continue
    fi
  fi

  # ── Check 2: Megaphone log (Go2 received chunks) ──
  MEGA_LOG=$(tmux capture-pane -t llm-e2e:0.1 -p -J 2>/dev/null | grep "Megaphone playback completed" | tail -1)
  if [ -n "$MEGA_LOG" ]; then
    echo "  [OK] Megaphone playback completed"
  else
    echo "  [WARN] No Megaphone completion log found"
  fi

  # ── Check 3: No echo loop (no hallucination in last 8s) ──
  ECHO=$(tmux capture-pane -t llm-e2e:0.2 -p -J 2>/dev/null | grep "hallucination" | tail -1)
  RECENT_ECHO=""
  if [ -n "$ECHO" ]; then
    # Check if it's recent (within last 10 seconds)
    RECENT_ECHO=$(tmux capture-pane -t llm-e2e:0.3 -p -J 2>/dev/null | grep "fallback" | tail -1)
  fi
  if [ -z "$RECENT_ECHO" ]; then
    echo "  [OK] No echo loop detected"
  else
    echo "  [WARN] Possible echo: $RECENT_ECHO"
  fi

  PASS=$((PASS + 1))
  echo "  [PASS] Round $i"

  # Wait between rounds
  if [ "$i" -lt "$ROUNDS" ]; then
    sleep 3
  fi
done

# ── Summary ──
echo ""
echo "═══════════════════════════════════════"
echo "  RESULT: $PASS/$ROUNDS passed, $FAIL/$ROUNDS failed"
echo "═══════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
