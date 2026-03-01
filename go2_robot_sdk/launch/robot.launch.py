# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

import os
from typing import List
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, AndSubstitution, NotSubstitution
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import (
    FrontendLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)


class Go2LaunchConfig:
    """Configuration container for Go2 robot launch parameters"""

    def __init__(self):
        # Environment variables
        self.robot_token = os.getenv("ROBOT_TOKEN", "")
        self.robot_ip = os.getenv("ROBOT_IP", "")
        self.robot_ip_list = self._parse_ip_list(self.robot_ip)
        self.map_name = os.getenv("MAP_NAME", "3d_map")
        self.save_map = os.getenv("MAP_SAVE", "true")
        self.conn_type = os.getenv("CONN_TYPE", "webrtc")

        # Derived configurations
        self.conn_mode = self._determine_connection_mode()
        self.rviz_config = self._get_rviz_config()
        self.urdf_file = self._get_urdf_file()

        # Package paths
        self.package_dir = get_package_share_directory("go2_robot_sdk")
        self.config_paths = self._get_config_paths()

        print(f"� Go2 Launch Configuration:")
        print(f"   Robot IPs: {self.robot_ip_list}")
        print(f"   Connection: {self.conn_type} ({self.conn_mode})")
        print(f"   URDF: {self.urdf_file}")

    def _parse_ip_list(self, robot_ip: str) -> List[str]:
        """Parse robot IP addresses from environment variable"""
        return robot_ip.replace(" ", "").split(",") if robot_ip else []

    def _determine_connection_mode(self) -> str:
        """Determine connection mode based on IP list and connection type"""
        return (
            "single"
            if len(self.robot_ip_list) == 1 and self.conn_type != "cyclonedx"
            else "multi"
        )

    def _get_rviz_config(self) -> str:
        """Get appropriate RViz configuration file"""
        if self.conn_type == "cyclonedx":
            return "cyclonedx_config.rviz"
        elif self.conn_mode == "single":
            return "single_robot_conf.rviz"
        else:
            return "multi_robot_conf.rviz"

    def _get_urdf_file(self) -> str:
        """Get appropriate URDF file"""
        return "go2.urdf" if self.conn_mode == "single" else "multi_go2.urdf"

    def _get_config_paths(self) -> dict:
        """Get all configuration file paths"""
        return {
            "joystick": os.path.join(self.package_dir, "config", "joystick.yaml"),
            "twist_mux": os.path.join(self.package_dir, "config", "twist_mux.yaml"),
            "slam": os.path.join(
                self.package_dir, "config", "mapper_params_online_async.yaml"
            ),
            "nav2": os.path.join(self.package_dir, "config", "nav2_params.yaml"),
            "rviz": os.path.join(self.package_dir, "config", self.rviz_config),
            "urdf": os.path.join(self.package_dir, "urdf", self.urdf_file),
        }


class Go2NodeFactory:
    """Factory for creating Go2 robot nodes"""

    def __init__(self, config: Go2LaunchConfig):
        self.config = config

    def create_launch_arguments(self) -> List[DeclareLaunchArgument]:
        """Create all launch arguments"""
        return [
            DeclareLaunchArgument(
                "rviz2", default_value="true", description="Launch RViz2"
            ),
            DeclareLaunchArgument(
                "nav2", default_value="true", description="Launch Nav2"
            ),
            DeclareLaunchArgument(
                "slam", default_value="true", description="Launch SLAM"
            ),
            DeclareLaunchArgument(
                "foxglove", default_value="true", description="Launch Foxglove Bridge"
            ),
            DeclareLaunchArgument(
                "joystick", default_value="true", description="Launch joystick"
            ),
            DeclareLaunchArgument(
                "teleop", default_value="true", description="Launch teleoperation"
            ),
            DeclareLaunchArgument(
                "mcp_mode",
                default_value="false",
                description="MCP mode: enables snapshot_service, disables SLAM/Nav2",
            ),
            DeclareLaunchArgument(
                "enable_video", default_value="false", description="Enable camera stream"
            ),
            DeclareLaunchArgument(
                "decode_lidar", default_value="true", description="Decode lidar frames"
            ),
            DeclareLaunchArgument(
                "publish_raw_image",
                default_value="false",
                description="Publish raw camera image",
            ),
            DeclareLaunchArgument(
                "publish_compressed_image",
                default_value="false",
                description="Publish compressed camera image",
            ),
            DeclareLaunchArgument(
                "publish_raw_voxel",
                default_value="false",
                description="Publish raw voxel map",
            ),
            DeclareLaunchArgument(
                "lidar_processing",
                default_value="false",
                description="Enable lidar post-processing nodes",
            ),
            DeclareLaunchArgument(
                "enable_tts", default_value="false", description="Enable TTS node"
            ),
            DeclareLaunchArgument(
                "minimal_state_topics",
                default_value="false",
                description="Subscribe only odometry + lidar RTC topics",
            ),
            DeclareLaunchArgument(
                "lidar_point_stride",
                default_value="1",
                description="Keep every Nth lidar point before PointCloud2 publish",
            ),
            DeclareLaunchArgument(
                "map",
                default_value=os.getenv("MAP_YAML", "/home/jetson/go2_map.yaml"),
                description="Map YAML path used by Nav2 localization",
            ),
            DeclareLaunchArgument(
                "autostart",
                default_value="true",
                description="Autostart Nav2 lifecycle nodes",
            ),
        ]

    def create_robot_state_nodes(self) -> List[Node]:
        """Create robot state publisher nodes"""
        nodes = []
        use_sim_time = LaunchConfiguration("use_sim_time", default="false")

        if self.config.conn_mode == "single":
            # Single robot configuration
            robot_desc = self._load_urdf_content(self.config.config_paths["urdf"])

            nodes.extend(
                [
                    Node(
                        package="robot_state_publisher",
                        executable="robot_state_publisher",
                        name="go2_robot_state_publisher",
                        output="screen",
                        parameters=[
                            {
                                "use_sim_time": use_sim_time,
                                "robot_description": robot_desc,
                            }
                        ],
                        arguments=[self.config.config_paths["urdf"]],
                    ),
                    self._create_pointcloud_to_laserscan_node(),
                ]
            )
        else:
            # Multi-robot configuration
            base_urdf = self._load_urdf_content(self.config.config_paths["urdf"])

            for i, _ in enumerate(self.config.robot_ip_list):
                robot_desc = base_urdf.format(robot_num=f"robot{i}")

                nodes.extend(
                    [
                        Node(
                            package="robot_state_publisher",
                            executable="robot_state_publisher",
                            name="go2_robot_state_publisher",
                            output="screen",
                            namespace=f"robot{i}",
                            parameters=[
                                {
                                    "use_sim_time": use_sim_time,
                                    "robot_description": robot_desc,
                                }
                            ],
                            arguments=[self.config.config_paths["urdf"]],
                        ),
                        self._create_pointcloud_to_laserscan_node(f"robot{i}"),
                    ]
                )

        return nodes

    def _load_urdf_content(self, urdf_path: str) -> str:
        """Load URDF file content"""
        with open(urdf_path, "r") as file:
            return file.read()

    def _create_pointcloud_to_laserscan_node(
        self, namespace: str | None = None
    ) -> Node:
        """Create pointcloud to laserscan conversion node"""
        if namespace:
            # Multi-robot setup
            return Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name=f"{namespace}_pointcloud_to_laserscan",
                remappings=[
                    ("cloud_in", f"{namespace}/point_cloud2"),
                    ("scan", f"{namespace}/scan"),
                ],
                parameters=[
                    {
                        "target_frame": f"{namespace}/base_link",
                        "queue_size": 8,
                        "transform_tolerance": 0.05,
                        "min_height": -1.0,
                        "max_height": 0.5,
                        "angle_increment": 0.0349,
                        "scan_time": 0.1,
                        "range_min": 0.2,
                        "range_max": 12.0,
                    }
                ],
                output="screen",
            )
        else:
            # Single robot setup
            return Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="go2_pointcloud_to_laserscan",
                remappings=[
                    ("cloud_in", "point_cloud2"),
                    ("scan", "scan"),
                ],
                parameters=[
                    {
                        "target_frame": "base_link",
                        "queue_size": 8,
                        "transform_tolerance": 0.05,
                        "min_height": -1.0,
                        "max_height": 0.5,
                        "angle_increment": 0.0349,
                        "scan_time": 0.1,
                        "range_min": 0.2,
                        "range_max": 12.0,
                    }
                ],
                output="screen",
            )

    def create_core_nodes(self) -> List[Node]:
        """Create core Go2 robot nodes"""
        with_mcp_mode = LaunchConfiguration("mcp_mode", default="false")
        with_map = LaunchConfiguration("map", default="/home/jetson/go2_map.yaml")
        with_enable_video = LaunchConfiguration("enable_video", default="false")
        with_decode_lidar = LaunchConfiguration("decode_lidar", default="true")
        with_publish_raw_image = LaunchConfiguration("publish_raw_image", default="false")
        with_publish_compressed_image = LaunchConfiguration(
            "publish_compressed_image", default="false"
        )
        with_publish_raw_voxel = LaunchConfiguration("publish_raw_voxel", default="false")
        with_lidar_processing = LaunchConfiguration("lidar_processing", default="false")
        with_enable_tts = LaunchConfiguration("enable_tts", default="false")
        with_minimal_state_topics = LaunchConfiguration(
            "minimal_state_topics", default="false"
        )
        with_lidar_point_stride = LaunchConfiguration("lidar_point_stride", default="1")

        return [
            # Main robot driver (clean architecture)
            Node(
                package="go2_robot_sdk",
                executable="go2_driver_node",
                name="go2_driver_node",
                output="screen",
                parameters=[
                    {
                        "robot_ip": self.config.robot_ip,
                        "token": self.config.robot_token,
                        "conn_type": self.config.conn_type,
                        "enable_video": with_enable_video,
                        "decode_lidar": with_decode_lidar,
                        "publish_raw_image": with_publish_raw_image,
                        "publish_compressed_image": with_publish_compressed_image,
                        "publish_raw_voxel": with_publish_raw_voxel,
                        "minimal_state_topics": with_minimal_state_topics,
                        "lidar_point_stride": with_lidar_point_stride,
                    }
                ],
            ),
            Node(
                package="lidar_processor",
                executable="lidar_to_pointcloud",
                name="lidar_to_pointcloud",
                condition=IfCondition(with_lidar_processing),
                parameters=[
                    {
                        "robot_ip_lst": self.config.robot_ip_list
                        if self.config.robot_ip_list
                        else [""],
                        "map_name": self.config.map_name,
                        "map_save": self.config.save_map,
                    }
                ],
            ),
            Node(
                package="lidar_processor",
                executable="pointcloud_aggregator",
                name="pointcloud_aggregator",
                condition=IfCondition(with_lidar_processing),
                parameters=[
                    {
                        "max_range": 20.0,
                        "min_range": 0.1,
                        "height_filter_min": -0.25,
                        "height_filter_max": 2.0,
                        "downsample_rate": 5,
                        "publish_rate": 10.0,
                    }
                ],
            ),
            Node(
                package="speech_processor",
                executable="tts_node",
                name="tts_node",
                condition=IfCondition(with_enable_tts),
                parameters=[
                    {
                        "api_key": os.getenv("ELEVENLABS_API_KEY", ""),
                        "provider": "elevenlabs",
                        "voice_name": "XrExE9yKIg1WjnnlVkGX",
                        "local_playback": False,
                        "use_cache": True,
                        "audio_quality": "standard",
                    }
                ],
            ),
            # Snapshot service for MCP mode (captures camera images)
            Node(
                package="go2_robot_sdk",
                executable="snapshot_service",
                name="snapshot_service",
                output="screen",
                condition=IfCondition(with_mcp_mode),
            ),
        ]

    def create_teleop_nodes(self) -> List[Node]:
        """Create teleoperation and joystick nodes"""
        use_sim_time = LaunchConfiguration("use_sim_time", default="false")
        with_joystick = LaunchConfiguration("joystick", default="true")
        with_teleop = LaunchConfiguration("teleop", default="true")

        return [
            # Joystick node
            Node(
                package="joy",
                executable="joy_node",
                condition=IfCondition(with_joystick),
                parameters=[self.config.config_paths["joystick"]],
            ),
            # Teleop twist joy node
            Node(
                package="teleop_twist_joy",
                executable="teleop_node",
                name="go2_teleop_node",
                condition=IfCondition(with_joystick),
                parameters=[self.config.config_paths["twist_mux"]],
            ),
            # Twist multiplexer
            Node(
                package="twist_mux",
                executable="twist_mux",
                output="screen",
                condition=IfCondition(with_teleop),
                parameters=[
                    {"use_sim_time": use_sim_time},
                    self.config.config_paths["twist_mux"],
                ],
            ),
        ]

    def create_visualization_nodes(self) -> List[Node]:
        """Create visualization nodes (RViz, Foxglove)"""
        with_rviz2 = LaunchConfiguration("rviz2", default="true")

        return [
            # RViz2
            Node(
                package="rviz2",
                executable="rviz2",
                condition=IfCondition(with_rviz2),
                name="go2_rviz2",
                output="screen",
                arguments=["-d", self.config.config_paths["rviz"]],
                parameters=[{"use_sim_time": False}],
            ),
        ]

    def create_include_launches(self) -> List[IncludeLaunchDescription]:
        """Create included launch descriptions"""
        use_sim_time = LaunchConfiguration("use_sim_time", default="false")
        with_foxglove = LaunchConfiguration("foxglove", default="true")
        with_slam = LaunchConfiguration("slam", default="true")
        with_nav2 = LaunchConfiguration("nav2", default="true")
        with_mcp_mode = LaunchConfiguration("mcp_mode", default="false")
        with_map = LaunchConfiguration("map", default="/home/jetson/go2_map.yaml")
        with_autostart = LaunchConfiguration("autostart", default="true")

        # SLAM/Nav2 enabled when: (slam/nav2=true) AND (mcp_mode=false)
        # Uses AndSubstitution for robust boolean handling (works with True/true/1)
        slam_enabled = AndSubstitution(with_slam, NotSubstitution(with_mcp_mode))
        nav2_enabled = AndSubstitution(with_nav2, NotSubstitution(with_mcp_mode))
        nav2_localization_enabled = AndSubstitution(
            AndSubstitution(with_nav2, NotSubstitution(with_slam)),
            NotSubstitution(with_mcp_mode),
        )

        foxglove_launch = os.path.join(
            get_package_share_directory("foxglove_bridge"),
            "launch",
            "foxglove_bridge_launch.xml",
        )

        return [
            # Foxglove Bridge
            IncludeLaunchDescription(
                FrontendLaunchDescriptionSource(foxglove_launch),
                condition=IfCondition(with_foxglove),
            ),
            # SLAM Toolbox (enabled when slam=true AND mcp_mode=false)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    [
                        os.path.join(
                            get_package_share_directory("slam_toolbox"),
                            "launch",
                            "online_async_launch.py",
                        )
                    ]
                ),
                condition=IfCondition(slam_enabled),
                launch_arguments={
                    "slam_params_file": self.config.config_paths["slam"],
                    "use_sim_time": use_sim_time,
                }.items(),
            ),
            # Nav2 (enabled when nav2=true AND mcp_mode=false)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    [
                        os.path.join(
                            get_package_share_directory("nav2_bringup"),
                            "launch",
                            "navigation_launch.py",
                        )
                    ]
                ),
                condition=IfCondition(nav2_enabled),
                launch_arguments={
                        "map": with_map,
                        "params_file": self.config.config_paths["nav2"],
                        "use_sim_time": use_sim_time,
                        "autostart": with_autostart,
                    }.items(),
            ),
            # Nav2 localization (AMCL + map_server) when nav2=true and slam=false
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    [
                        os.path.join(
                            get_package_share_directory("nav2_bringup"),
                            "launch",
                            "localization_launch.py",
                        )
                    ]
                ),
                condition=IfCondition(nav2_localization_enabled),
                launch_arguments={
                        "map": with_map,
                        "params_file": self.config.config_paths["nav2"],
                        "use_sim_time": use_sim_time,
                        "autostart": with_autostart,
                    }.items(),
            ),
        ]


def generate_launch_description():
    """Generate the launch description for Go2 robot system"""

    # Initialize configuration and factory
    config = Go2LaunchConfig()
    factory = Go2NodeFactory(config)

    # Create all components
    launch_args = factory.create_launch_arguments()
    robot_state_nodes = factory.create_robot_state_nodes()
    core_nodes = factory.create_core_nodes()
    teleop_nodes = factory.create_teleop_nodes()
    visualization_nodes = factory.create_visualization_nodes()
    include_launches = factory.create_include_launches()

    # Combine all elements
    launch_entities = (
        launch_args
        + robot_state_nodes
        + core_nodes
        + teleop_nodes
        + visualization_nodes
        + include_launches
    )

    return LaunchDescription(launch_entities)
