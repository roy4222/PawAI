#!/usr/bin/env zsh
# Stage 3 smoke runner — tts_node with OpenRouter Gemini Despina + USB speaker.
set -e
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
source install/setup.zsh
set -a; source .env 2>/dev/null || true; set +a
exec ros2 run speech_processor tts_node --ros-args \
  -p provider:=openrouter_gemini \
  -p openrouter_gemini_voice:=Despina \
  -p local_playback:=true \
  -p local_output_device:=plughw:2,0
