#!/usr/bin/env bash
# Brain MVS tmux — OpenClaw-lite persona (Branch B).
# conversation_graph_node replaces legacy llm_bridge_node output_mode:=brain.
#
# Runtime topology (Roy review #5 — Task 9 separate from loader Task 1):
#   interaction_executive   ← brain orchestrator
#   conversation_graph_node ← LangGraph + OpenClaw-lite persona (5 files)
#   event_action_bridge     ← disabled (enable_event_action_bridge:=false)
#
# Smoke: ros2 topic echo /brain/chat_candidate
# Send text: ros2 topic pub --once /brain/text_input std_msgs/msg/String \
#   '{"data": "{\"text\": \"你好\", \"request_id\": \"test-1\", \"source\": \"studio_text\"}"}'

set -euo pipefail

SESSION="${SESSION:-pawai_brain}"
WORKSPACE="${WORKSPACE:-$HOME/newLife/elder_and_dog}"
# 語義：ROS setup / cd / install/setup.zsh 任一失敗整段失敗；.env 不存在沒事；
# .env 存在但內容壞掉會失敗（合理）。用 if-fi 表達 .env optional，避免 `|| true`
# 包到 ROS setup 把錯誤吞掉。
SOURCE_CMD="source /opt/ros/humble/setup.zsh && cd $WORKSPACE && source install/setup.zsh && { if [[ -f $WORKSPACE/.env ]]; then set -a; source $WORKSPACE/.env; set +a; fi; }"

# Resolve install/share path for persona directory; fallback to source path for dev
# ROS2 colcon Python data_files 真實路徑：install/<pkg>/share/<pkg>/...
PERSONA_DIR="${PERSONA_DIR:-$WORKSPACE/install/pawai_brain/share/pawai_brain/personas/v1}"
if [ ! -d "$PERSONA_DIR" ]; then
  # Dev fallback: source tree (before colcon build)
  PERSONA_DIR="$WORKSPACE/pawai_brain/personas/v1"
fi

# 5/12: OpenRouter primary / fallback model slugs (mirror start_full_demo_tmux.sh).
# Override one-liner:
#   PAWAI_LLM_MODEL=google/gemini-3-flash-preview bash scripts/start_pawai_brain_tmux.sh
# Decision: docs/pawai-brain/dev-logs/2026-05-12-llm-naturalness-ab-eval.md
PAWAI_LLM_MODEL="${PAWAI_LLM_MODEL:-openai/gpt-5.4-mini}"
PAWAI_LLM_FALLBACK_MODEL="${PAWAI_LLM_FALLBACK_MODEL:-google/gemini-3-flash-preview}"

tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" -n brain "$SOURCE_CMD; \
  ros2 launch interaction_executive interaction_executive.launch.py; bash"

# conversation_graph_node with OpenClaw-lite persona directory
# Replaces: ros2 run speech_processor llm_bridge_node --ros-args -p output_mode:=brain
tmux new-window -t "$SESSION" -n conv_graph "$SOURCE_CMD; \
  ros2 launch pawai_brain pawai_conversation_graph.launch.py \
    llm_persona_file:=$PERSONA_DIR \
    openrouter_gemini_model:=$PAWAI_LLM_MODEL \
    openrouter_deepseek_model:=$PAWAI_LLM_FALLBACK_MODEL; bash"

tmux new-window -t "$SESSION" -n event_bridge_off "$SOURCE_CMD; \
  ros2 launch vision_perception event_action_bridge.launch.py \
    enable_event_action_bridge:=false; bash"

tmux new-window -t "$SESSION" -n brain_state "$SOURCE_CMD; \
  ros2 topic echo /state/pawai_brain; bash"

tmux new-window -t "$SESSION" -n skill_results "$SOURCE_CMD; \
  ros2 topic echo /brain/skill_result; bash"

tmux new-window -t "$SESSION" -n smoke "$SOURCE_CMD; \
  ros2 topic echo /brain/chat_candidate; bash"

cat <<EOF
tmux session '$SESSION' started.
Attach: tmux attach -t $SESSION

OpenClaw-lite runtime notes:
- conversation_graph_node (LangGraph + 5-file persona) replaces llm_bridge_node.
- Persona directory: $PERSONA_DIR
- Smoke: attach to 'smoke' window to watch /brain/chat_candidate.
- event_action_bridge disabled (enable_event_action_bridge:=false).
- vision_perception/interaction_router intentionally not started.

Send test input:
  ros2 topic pub --once /brain/text_input std_msgs/msg/String \\
    '{"data": "{\"text\": \"你是誰？\", \"request_id\": \"test-1\", \"source\": \"studio_text\"}"}'
EOF
