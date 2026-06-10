"""Launch object_perception_node with config."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_dir = get_package_share_directory("object_perception")
    default_config = os.path.join(pkg_dir, "config", "object_perception.yaml")

    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value=default_config),
        # 2026-06-10 model A/B: OBJECT_MODEL / OBJECT_INPUT_SIZE env 可一行切換模型，
        # 不用改 launch（candidates: yolo26n.onnx@640 主線 / yolo26s_640.onnx@640 /
        # yolo26n_960.onnx@960 / yolo26s_960.onnx@960）。input_size 必須和該 ONNX
        # export 時的 imgsz 一致（fixed-shape，餵錯直接 inference fail）。
        # 用法: OBJECT_MODEL=/home/jetson/models/yolo26s_640.onnx ros2 launch ...
        #       OBJECT_MODEL=.../yolo26n_960.onnx OBJECT_INPUT_SIZE=960 ros2 launch ...
        DeclareLaunchArgument(
            "model_path",
            default_value=EnvironmentVariable(
                "OBJECT_MODEL", default_value="/home/jetson/models/yolo26n.onnx"
            ),
        ),
        DeclareLaunchArgument(
            "input_size",
            default_value=EnvironmentVariable("OBJECT_INPUT_SIZE", default_value="640"),
        ),
        # Default matches config/object_perception.yaml (0.35). This launch arg is
        # ordered AFTER config_file in the Node parameters list below, so it OVERRIDES
        # the yaml value — a 0.5 default silently shadowed yaml's 0.35 and dropped
        # low-conf classes (cup/bottle). Keep in sync with the yaml.
        DeclareLaunchArgument("confidence_threshold", default_value="0.35"),
        DeclareLaunchArgument("publish_fps", default_value="8.0"),
        DeclareLaunchArgument("tick_period", default_value="0.067"),
        Node(
            package="object_perception",
            executable="object_perception_node",
            name="object_perception_node",
            parameters=[
                LaunchConfiguration("config_file"),
                {"model_path": LaunchConfiguration("model_path")},
                {"input_size": ParameterValue(
                    LaunchConfiguration("input_size"),
                    value_type=int,
                )},
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
