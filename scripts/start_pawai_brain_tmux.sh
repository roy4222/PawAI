#!/usr/bin/env bash
# Brain MVS dry-run tmux. This intentionally avoids legacy action writers.

set -euo pipefail

SESSION="${SESSION:-pawai_brain}"
WORKSPACE="${WORKSPACE:-$HOME/newLife/elder_and_dog}"
SOURCE_CMD="source /opt/ros/humble/setup.zsh && cd $WORKSPACE && source install/setup.zsh"

tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" -n brain "$SOURCE_CMD; \
  ros2 launch interaction_executive interaction_executive.launch.py; bash"

tmux new-window -t "$SESSION" -n llm_bridge "$SOURCE_CMD; \
  ros2 run speech_processor llm_bridge_node --ros-args -p output_mode:=brain; bash"

tmux new-window -t "$SESSION" -n event_bridge_off "$SOURCE_CMD; \
  ros2 launch vision_perception event_action_bridge.launch.py \
    enable_event_action_bridge:=false; bash"

tmux new-window -t "$SESSION" -n brain_state "$SOURCE_CMD; \
  ros2 topic echo /state/pawai_brain; bash"

tmux new-window -t "$SESSION" -n skill_results "$SOURCE_CMD; \
  ros2 topic echo /brain/skill_result; bash"

cat <<EOF
tmux session '$SESSION' started.
Attach: tmux attach -t $SESSION

Brain-mode runtime notes:
- llm_bridge_node runs with output_mode:=brain, so it emits /brain/chat_candidate.
- event_action_bridge is launched with enable_event_action_bridge:=false.
- vision_perception/interaction_router is intentionally not started.
EOF
