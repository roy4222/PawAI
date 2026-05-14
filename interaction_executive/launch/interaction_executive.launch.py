"""Launch PawAI Brain MVS nodes."""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution(
        [FindPackageShare("interaction_executive"), "config", "executive.yaml"]
    )
    return LaunchDescription(
        [
            Node(
                package="interaction_executive",
                executable="brain_node",
                name="brain_node",
                parameters=[config],
                output="screen",
            ),
            Node(
                package="interaction_executive",
                executable="interaction_executive_node",
                name="interaction_executive_node",
                parameters=[config],
                output="screen",
            ),
        ]
    )
