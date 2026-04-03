"""Launch obstacle avoidance node with configurable parameters."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("threshold_m", default_value="2.0"),
            DeclareLaunchArgument("warning_m", default_value="2.5"),
            DeclareLaunchArgument("max_range_m", default_value="3.0"),
            DeclareLaunchArgument("roi_top_ratio", default_value="0.4"),
            DeclareLaunchArgument("roi_bottom_ratio", default_value="0.8"),
            DeclareLaunchArgument("roi_left_ratio", default_value="0.2"),
            DeclareLaunchArgument("roi_right_ratio", default_value="0.8"),
            DeclareLaunchArgument("obstacle_ratio_trigger", default_value="0.15"),
            DeclareLaunchArgument("publish_rate_hz", default_value="15.0"),
            DeclareLaunchArgument("debounce_frames", default_value="3"),
            DeclareLaunchArgument(
                "depth_topic",
                default_value="/camera/camera/aligned_depth_to_color/image_raw",
            ),
            Node(
                package="vision_perception",
                executable="obstacle_avoidance_node",
                name="obstacle_avoidance_node",
                parameters=[
                    {
                        "threshold_m": LaunchConfiguration("threshold_m"),
                        "warning_m": LaunchConfiguration("warning_m"),
                        "max_range_m": LaunchConfiguration("max_range_m"),
                        "roi_top_ratio": LaunchConfiguration("roi_top_ratio"),
                        "roi_bottom_ratio": LaunchConfiguration("roi_bottom_ratio"),
                        "roi_left_ratio": LaunchConfiguration("roi_left_ratio"),
                        "roi_right_ratio": LaunchConfiguration("roi_right_ratio"),
                        "obstacle_ratio_trigger": LaunchConfiguration(
                            "obstacle_ratio_trigger"
                        ),
                        "publish_rate_hz": LaunchConfiguration("publish_rate_hz"),
                        "debounce_frames": LaunchConfiguration("debounce_frames"),
                        "depth_topic": LaunchConfiguration("depth_topic"),
                    }
                ],
                output="screen",
            ),
        ]
    )
