from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    enable_arg = DeclareLaunchArgument(
        "enable_event_action_bridge",
        default_value="true",
        description="Set false to disable in PawAI Brain MVS launches.",
    )
    bridge_node = Node(
        package="vision_perception",
        executable="event_action_bridge",
        name="event_action_bridge",
        output="screen",
        condition=IfCondition(LaunchConfiguration("enable_event_action_bridge")),
    )
    return LaunchDescription([enable_arg, bridge_node])
