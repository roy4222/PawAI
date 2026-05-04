#!/usr/bin/env zsh
# Temporary smoke runner for tts_node — sync once to use on Jetson
set -e
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
source install/setup.zsh
set -a; source .env 2>/dev/null || true; set +a
exec ros2 run speech_processor tts_node --ros-args \
  -p provider:=edge_tts \
  -p local_playback:=true \
  -p local_output_device:=plughw:2,0
