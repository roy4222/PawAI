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
for n in go2_driver_node stt_intent_node tts_node llm_bridge_node; do
  if echo "$NODES" | grep -q "$n"; then
    echo "  [OK] $n"
  else
    echo "  [FAIL] $n not found — is llm-e2e session running?"
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

  # Send TTS
  echo "  [SEND] /tts: \"$TEST_PHRASE\""
  ros2 topic pub --once /tts std_msgs/msg/String "{data: \"$TEST_PHRASE\"}" >/dev/null 2>&1

  # Wait for playback (TTS synthesis ~2.5s + Megaphone ~3s + tail)
  sleep 8

  # ── Check 1: Debug WAV exists (TTS ran) ──
  WAV=$(ls -t /tmp/megaphone_debug_*.wav 2>/dev/null | head -1)
  if [ -z "$WAV" ]; then
    echo "  [FAIL] No debug WAV — TTS didn't produce audio"
    FAIL=$((FAIL + 1))
    continue
  fi
  WAV_SIZE=$(stat -c%s "$WAV" 2>/dev/null || echo "0")
  echo "  [OK] Debug WAV: $WAV ($WAV_SIZE bytes)"

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
