"""Launch interaction_executive_node."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("interaction_executive")
    config = os.path.join(pkg_dir, "config", "executive.yaml")

    return LaunchDescription([
        DeclareLaunchArgument("enable_fallen", default_value="true"),
        Node(
            package="interaction_executive",
            executable="interaction_executive_node",
            name="interaction_executive_node",
            parameters=[config, {"enable_fallen": LaunchConfiguration("enable_fallen")}],
            output="screen",
        ),
    ])
