#!/usr/bin/env bash
# Full environment cleanup — speech nodes + Go2 driver + ROS2 daemon.
# Usage: bash scripts/clean_all.sh
#
# Combines clean_speech_env.sh --with-go2-driver with Go2 launch residual
# C++ process cleanup and ROS2 daemon restart.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Step 1: Clean speech nodes + go2_driver_node (reuse existing script) ──
echo "[1/5] Cleaning speech environment (with go2_driver)..."
bash "$SCRIPT_DIR/clean_speech_env.sh" --with-go2-driver || true

# ── Step 2: Kill Go2 launch residual C++ subprocesses ──
# ros2 launch spawns C++ children that survive parent kill.
# See CLAUDE.md: "多 driver instance 殘留"
echo "[2/5] Killing Go2 launch residual C++ processes..."
# Pattern list from CLAUDE.md + actual Jetson `ps aux` observations.
# Use short substrings so pkill -f matches regardless of full binary name.
GO2_CPP_PROCS=(
  "robot_state_publisher"
  "pointcloud_to_laserscan"
  "joy_node"
  "teleop"
  "twist_mux"
  "go2_driver_node"
)
for proc in "${GO2_CPP_PROCS[@]}"; do
  pkill -9 -f "$proc" 2>/dev/null || true
done

# ── Step 3: Kill residual ros2 CLI processes ──
echo "[3/5] Killing residual ros2 CLI processes..."
pkill -9 -f "ros2 launch go2_robot_sdk" 2>/dev/null || true
pkill -9 -f "ros2 run speech_processor" 2>/dev/null || true
pkill -9 -f "ros2 topic echo" 2>/dev/null || true
pkill -9 -f "ros2 topic pub" 2>/dev/null || true

# ── Step 4: Kill all related tmux sessions ──
echo "[4/5] Cleaning tmux sessions..."
TMUX_SESSIONS=(
  "asr-tts-no-vad"
  "speech-e2e"
  "speech-test"
  "speech-test-observer"
  "speech-phase4"
  "speech-stable-debug"
  "llm-e2e"
)
for sess in "${TMUX_SESSIONS[@]}"; do
  tmux kill-session -t "$sess" 2>/dev/null || true
done

# ── Step 5: Stop ROS2 daemon (clear discovery cache) ──
echo "[5/5] Stopping ROS2 daemon..."
ros2 daemon stop 2>/dev/null || true

sleep 1

# ── Verify ──
# Verify pattern matches actual process names observed on Jetson:
#   robot_state_publisher, pointcloud_to_laserscan_node, go2_driver_node,
#   joy_node, teleop_twist_joy_node, twist_mux,
#   stt_intent_node, tts_node, llm_bridge_node, intent_tts_bridge_node
VERIFY_PATTERN='(robot_state_publisher|pointcloud_to_laserscan|go2_driver_node|joy_node|teleop|twist_mux|stt_intent_node|tts_node|llm_bridge_node|intent_tts_bridge_node)'
RESIDUAL=$(ps aux | grep -E "$VERIFY_PATTERN" | grep -v grep | wc -l || true)
if [ "$RESIDUAL" -gt 0 ]; then
  echo "[WARN] $RESIDUAL residual process(es) remain:"
  ps aux | grep -E "$VERIFY_PATTERN" | grep -v grep
  exit 1
fi

echo "[OK] Full environment clean (speech + Go2 driver + daemon)"
