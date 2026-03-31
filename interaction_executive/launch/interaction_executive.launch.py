"""Launch interaction_executive_node."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("interaction_executive")
    config = os.path.join(pkg_dir, "config", "executive.yaml")

    return LaunchDescription([
        Node(
            package="interaction_executive",
            executable="interaction_executive_node",
            name="interaction_executive_node",
            parameters=[config],
            output="screen",
        ),
    ])
