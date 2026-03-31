#!/usr/bin/env bash
# Clean all processes and tmux sessions started by start_full_demo_tmux.sh.
# Usage: bash scripts/clean_full_demo.sh
#
# Kill patterns are derived 1:1 from start_full_demo_tmux.sh launch commands.
# If you add a window to the demo script, add the corresponding pattern here.

set -euo pipefail

echo "=== PawAI Demo 全環境清理 ==="

# ── Step 1: Kill tmux session ──
echo "[1/5] Killing tmux sessions..."
DEMO_SESSIONS=("demo" "full-demo" "llm-e2e" "face-identity")
for sess in "${DEMO_SESSIONS[@]}"; do
    if tmux has-session -t "$sess" 2>/dev/null; then
        tmux kill-session -t "$sess" 2>/dev/null || true
        echo "  killed session: $sess"
    fi
done
sleep 1

# ── Step 2: Kill ROS2 node processes ──
# Patterns map to start_full_demo_tmux.sh windows:
#   go2     → go2_driver_node + C++ children
#   camera  → realsense2_camera + rs_launch.py
#   face    → face_identity
#   vision  → vision_perception_node, vision_status_display
#   router  → interaction_router
#   asr     → stt_intent_node
#   tts     → tts_node
#   llm     → llm_bridge_node
#   bridge  → event_action_bridge
#   fox     → foxglove_bridge
echo "[2/5] Killing node processes..."
NODE_PROCS=(
    # Window 0: Go2 Driver + C++ children
    "go2_driver_node"
    "robot_state_publisher"
    "pointcloud_to_laserscan"
    "joy_node"
    "teleop"
    "twist_mux"
    # Window 1: D435 Camera
    "realsense2_camera"
    "rs_launch.py"
    # Window 2: Face
    "face_identity"
    # Window 3: Vision
    "vision_perception_node"
    "vision_status_display"
    # Window 4: Router
    "interaction_router"
    # Window 5: ASR
    "stt_intent_node"
    # Window 6: TTS
    "tts_node"
    # Window 7: LLM
    "llm_bridge_node"
    # Window 8: Bridge
    "event_action_bridge"
    # Window 9: Foxglove
    "foxglove_bridge"
    # Future: Executive (Day 5+)
    "interaction_executive"
    # Future: Obstacle (Day 6+)
    "obstacle_avoidance"
)
for proc in "${NODE_PROCS[@]}"; do
    if pgrep -f "$proc" >/dev/null 2>&1; then
        pkill -9 -f "$proc" 2>/dev/null || true
        echo "  killed: $proc"
    fi
done

# ── Step 3: Kill ros2 launch wrapper residuals ──
echo "[3/5] Killing ros2 launch wrappers..."
LAUNCH_PATTERNS=(
    "ros2 launch go2_robot_sdk"
    "ros2 launch realsense2_camera"
    "ros2 launch face_perception"
    "ros2 launch vision_perception"
    "ros2 launch foxglove_bridge"
    "ros2 launch interaction_executive"
    "ros2 run speech_processor"
)
for pat in "${LAUNCH_PATTERNS[@]}"; do
    if pgrep -f "$pat" >/dev/null 2>&1; then
        pkill -9 -f "$pat" 2>/dev/null || true
        echo "  killed: $pat"
    fi
done

# ── Step 4: Stop ROS2 daemon ──
echo "[4/5] Stopping ROS2 daemon..."
ros2 daemon stop 2>/dev/null || true

sleep 1

# ── Step 5: Verify ──
echo "[5/5] Verifying..."
VERIFY_PATTERN='(go2_driver_node|robot_state_publisher|pointcloud_to_laserscan|joy_node|teleop|twist_mux|realsense2_camera|rs_launch\.py|face_identity|face_perception\.launch|vision_perception_node|vision_status_display|interaction_router|stt_intent_node|tts_node|llm_bridge_node|event_action_bridge|foxglove_bridge|interaction_executive|obstacle_avoidance|ros2 launch go2_robot_sdk|ros2 launch realsense2_camera|ros2 launch face_perception|ros2 launch vision_perception|ros2 launch foxglove_bridge|ros2 launch interaction_executive|ros2 run speech_processor)'
RESIDUAL=$(ps aux | grep -E "$VERIFY_PATTERN" | grep -v grep | wc -l || true)
if [ "$RESIDUAL" -gt 0 ]; then
    echo ""
    echo "[WARN] $RESIDUAL residual process(es) remain:"
    ps aux | grep -E "$VERIFY_PATTERN" | grep -v grep || true
    echo ""
    echo "Try: sudo pkill -9 -f '<process_name>'"
    exit 1
fi

echo ""
echo "[OK] Demo environment clean. Ready to restart."
