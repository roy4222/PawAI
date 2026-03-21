"""Launch vision_perception_node with config."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


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
        Node(
            package="vision_perception",
            executable="vision_perception_node",
            name="vision_perception_node",
            parameters=[
                LaunchConfiguration("config_file"),
                {"inference_backend": LaunchConfiguration("inference_backend")},
                {"use_camera": LaunchConfiguration("use_camera")},
                {"mock_scenario": LaunchConfiguration("mock_scenario")},
                {"gesture_backend": LaunchConfiguration("gesture_backend")},
                {"pose_backend": LaunchConfiguration("pose_backend")},
                {"rtmpose_mode": LaunchConfiguration("rtmpose_mode")},
            ],
            output="screen",
        ),
    ])
