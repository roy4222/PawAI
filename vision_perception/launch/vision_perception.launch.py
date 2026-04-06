"""Launch vision_perception_node with config."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_dir = get_package_share_directory("vision_perception")
    default_config = os.path.join(pkg_dir, "config", "vision_perception.yaml")

    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value=default_config),
        DeclareLaunchArgument("inference_backend", default_value="mock"),
        DeclareLaunchArgument("use_camera", default_value="false"),
        DeclareLaunchArgument("mock_scenario", default_value="standing_idle"),
        DeclareLaunchArgument("gesture_backend", default_value="rtmpose"),
        DeclareLaunchArgument("pose_backend", default_value="rtmpose"),
        DeclareLaunchArgument("rtmpose_mode", default_value="balanced"),
        DeclareLaunchArgument("pose_complexity", default_value="0"),
        DeclareLaunchArgument("max_hands", default_value="1"),
        DeclareLaunchArgument("hands_complexity", default_value="0"),
        DeclareLaunchArgument("publish_fps", default_value="8.0"),
        DeclareLaunchArgument("gesture_every_n_ticks", default_value="3"),
        DeclareLaunchArgument("gesture_recognizer_model",
                              default_value="~/face_models/gesture_recognizer.task"),
        Node(
            package="vision_perception",
            executable="vision_perception_node",
            name="vision_perception_node",
            parameters=[
                LaunchConfiguration("config_file"),
                {"inference_backend": LaunchConfiguration("inference_backend")},
                {"use_camera": ParameterValue(LaunchConfiguration("use_camera"), value_type=bool)},
                {"mock_scenario": LaunchConfiguration("mock_scenario")},
                {"gesture_backend": LaunchConfiguration("gesture_backend")},
                {"pose_backend": LaunchConfiguration("pose_backend")},
                {"rtmpose_mode": LaunchConfiguration("rtmpose_mode")},
                {"pose_complexity": ParameterValue(LaunchConfiguration("pose_complexity"), value_type=int)},
                {"max_hands": ParameterValue(LaunchConfiguration("max_hands"), value_type=int)},
                {"hands_complexity": ParameterValue(LaunchConfiguration("hands_complexity"), value_type=int)},
                {"publish_fps": ParameterValue(LaunchConfiguration("publish_fps"), value_type=float)},
                {"gesture_every_n_ticks": ParameterValue(LaunchConfiguration("gesture_every_n_ticks"), value_type=int)},
                {"gesture_recognizer_model": LaunchConfiguration("gesture_recognizer_model")},
            ],
            output="screen",
        ),
    ])
