"""Launch LiDAR 360-degree reactive obstacle detection."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("safety_distance_m", default_value="0.5"),
        DeclareLaunchArgument("warning_distance_m", default_value="0.8"),
        DeclareLaunchArgument("min_obstacle_points", default_value="2"),
        DeclareLaunchArgument("ignore_behind", default_value="false"),
        DeclareLaunchArgument("publish_rate_hz", default_value="5.0"),
        DeclareLaunchArgument("debounce_frames", default_value="3"),
        DeclareLaunchArgument("scan_topic", default_value="/scan"),
        Node(
            package="vision_perception",
            executable="lidar_obstacle_node",
            name="lidar_obstacle_node",
            parameters=[{
                "safety_distance_m": LaunchConfiguration("safety_distance_m"),
                "warning_distance_m": LaunchConfiguration("warning_distance_m"),
                "min_obstacle_points": LaunchConfiguration("min_obstacle_points"),
                "ignore_behind": LaunchConfiguration("ignore_behind"),
                "publish_rate_hz": LaunchConfiguration("publish_rate_hz"),
                "debounce_frames": LaunchConfiguration("debounce_frames"),
                "scan_topic": LaunchConfiguration("scan_topic"),
            }],
            output="screen",
        ),
    ])
