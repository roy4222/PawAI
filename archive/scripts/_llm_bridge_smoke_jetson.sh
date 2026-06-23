#!/usr/bin/env zsh
# Temporary smoke runner for llm_bridge_node (brain output mode)
set -e
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
source install/setup.zsh
set -a; source .env 2>/dev/null || true; set +a
exec ros2 run speech_processor llm_bridge_node --ros-args \
  -p output_mode:=brain \
  -p openrouter_request_timeout_s:=4.0 \
  -p openrouter_overall_budget_s:=5.0
