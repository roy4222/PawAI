"""Launch the pawai_brain conversation graph node (primary mode).

Usage:
  ros2 launch pawai_brain pawai_conversation_graph.launch.py

  Override persona dir (default: install/share/pawai_brain/personas/v1):
  llm_persona_file:=/path/to/personas/v1  (directory mode, 5 files)
  llm_persona_file:=/path/to/persona.txt  (legacy single-file mode)

Override any ROS param via launch arg:
  llm_persona_file, openrouter_gemini_model, chat_history_max_turns,
  openrouter_request_timeout_s, openrouter_overall_budget_s, etc.
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    # Roy review #2: use get_package_share_directory (install path), not source path
    try:
        default_persona_dir = str(
            Path(get_package_share_directory("pawai_brain")) / "personas" / "v1"
        )
    except Exception:
        default_persona_dir = ""

    args = [
        DeclareLaunchArgument(
            "llm_persona_file",
            default_value=default_persona_dir,
            description=(
                "Path to persona file (legacy .txt) or directory (5 files: "
                "IDENTITY/STYLE/OUTPUT/EXAMPLES/CAPABILITIES). "
                "Default: install/share/pawai_brain/personas/v1"
            ),
        ),
        DeclareLaunchArgument(
            "openrouter_gemini_model",
            default_value="google/gemini-3-flash-preview",
        ),
        DeclareLaunchArgument(
            "openrouter_deepseek_model",
            default_value="deepseek/deepseek-v4-flash",
        ),
        DeclareLaunchArgument(
            "openrouter_request_timeout_s", default_value="4.0",
        ),
        DeclareLaunchArgument(
            "openrouter_overall_budget_s", default_value="5.0",
        ),
        DeclareLaunchArgument("chat_history_max_turns", default_value="5"),
        DeclareLaunchArgument("llm_max_tokens", default_value="500"),
        DeclareLaunchArgument(
            "llm_temperature",
            default_value="0.6",  # 1E: was 0.2; 0.6 balances JSON stability + naturalness
            description="LLM temperature (0.6 demo main; OpenClaw chat 0.7-1.0)",
        ),
        DeclareLaunchArgument(
            "engine_label", default_value="langgraph",
            description='engine field in chat_candidate / trace payloads',
        ),
    ]

    node = Node(
        package="pawai_brain",
        executable="conversation_graph_node",
        name="conversation_graph_node",
        output="screen",
        parameters=[
            {
                "llm_persona_file": LaunchConfiguration("llm_persona_file"),
                "openrouter_gemini_model": LaunchConfiguration("openrouter_gemini_model"),
                "openrouter_deepseek_model": LaunchConfiguration("openrouter_deepseek_model"),
                "openrouter_request_timeout_s": LaunchConfiguration("openrouter_request_timeout_s"),
                "openrouter_overall_budget_s": LaunchConfiguration("openrouter_overall_budget_s"),
                "chat_history_max_turns": LaunchConfiguration("chat_history_max_turns"),
                "llm_max_tokens": LaunchConfiguration("llm_max_tokens"),
                "llm_temperature": LaunchConfiguration("llm_temperature"),
                "engine_label": LaunchConfiguration("engine_label"),
            }
        ],
    )

    return LaunchDescription([*args, node])
