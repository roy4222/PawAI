#!/usr/bin/env zsh
# Step 4 E2E smoke runner — llm_bridge (legacy) + tts_node, no Go2/no ASR.
# Two tmux windows in same session: llm-bridge / tts.
set -e
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
source install/setup.zsh
set -a; source .env 2>/dev/null || true; set +a

SESSION=e2e-smoke
tmux kill-session -t "$SESSION" 2>/dev/null || true
pkill -9 -f llm_bridge_node 2>/dev/null || true
pkill -9 -f tts_node 2>/dev/null || true
sleep 1

tmux new-session -d -s "$SESSION" -n llm \
  "ros2 run speech_processor llm_bridge_node --ros-args \
    -p output_mode:=legacy \
    -p enable_actions:=false \
    -p openrouter_request_timeout_s:=4.0 \
    -p openrouter_overall_budget_s:=5.0 \
    2>&1 | tee /tmp/e2e_llm.log"

tmux new-window -t "$SESSION" -n tts \
  "ros2 run speech_processor tts_node --ros-args \
    -p provider:=edge_tts \
    -p local_playback:=true \
    -p local_output_device:=plughw:2,0 \
    2>&1 | tee /tmp/e2e_tts.log"

echo "Session $SESSION started; tmux ls:"
tmux ls
