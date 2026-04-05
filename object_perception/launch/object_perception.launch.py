"""Launch object_perception_node with config."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_dir = get_package_share_directory("object_perception")
    default_config = os.path.join(pkg_dir, "config", "object_perception.yaml")

    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value=default_config),
        DeclareLaunchArgument("model_path",
                              default_value="/home/jetson/models/yolo26n.onnx"),
        DeclareLaunchArgument("confidence_threshold", default_value="0.5"),
        DeclareLaunchArgument("publish_fps", default_value="8.0"),
        DeclareLaunchArgument("tick_period", default_value="0.067"),
        Node(
            package="object_perception",
            executable="object_perception_node",
            name="object_perception_node",
            parameters=[
                LaunchConfiguration("config_file"),
                {"model_path": LaunchConfiguration("model_path")},
                {"confidence_threshold": ParameterValue(
                    LaunchConfiguration("confidence_threshold"),
                    value_type=float,
                )},
                {"publish_fps": ParameterValue(
                    LaunchConfiguration("publish_fps"),
                    value_type=float,
                )},
                {"tick_period": ParameterValue(
                    LaunchConfiguration("tick_period"),
                    value_type=float,
                )},
            ],
            output="screen",
        ),
    ])
