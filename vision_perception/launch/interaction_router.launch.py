"""Launch interaction_router node."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="vision_perception",
                executable="interaction_router",
                name="interaction_router",
                parameters=[
                    {
                        "fallen_persist_sec": 2.0,
                        "gesture_cooldown": 2.0,
                        "fall_alert_cooldown": 15.0,
                    }
                ],
                output="screen",
            ),
        ]
    )
