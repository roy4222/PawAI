# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import json
import logging
import os
from typing import Dict, Any

from aiortc import MediaStreamTrack
from cv_bridge import CvBridge

from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSReliabilityPolicy
from rclpy.qos_overriding_options import QoSOverridingOptions
from rcl_interfaces.msg import SetParametersResult
from tf2_ros import TransformBroadcaster

from geometry_msgs.msg import Twist, PoseStamped

# Hook 測試：修改 src/ 下的檔案，應該會觸發 flake8 檢查
from go2_interfaces.msg import Go2State, IMU
from go2_interfaces.msg import LowState, VoxelMapCompressed, WebRtcReq
from sensor_msgs.msg import (
    PointCloud2,
    JointState,
    Joy,
    Image,
    CameraInfo,
    CompressedImage,
)
from nav_msgs.msg import Odometry

from ..domain.entities import RobotConfig, RobotData, CameraData
from ..domain.constants import RTC_TOPIC
from ..application.services import RobotDataService, RobotControlService
from ..infrastructure.ros2 import ROS2Publisher
from ..infrastructure.webrtc import WebRTCAdapter

logging.basicConfig(
    level=logging.DEBUG,  # 允許所有日誌級別通過
    format="%(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 設定 go2_driver_node 為 DEBUG 級別


class Go2DriverNode(Node):
    """Main Go2 driver node - entry point to the application"""

    def __init__(self, event_loop=None):
        super().__init__("go2_driver_node")  # Clean architecture main driver
        self.event_loop = event_loop

        # Configuration initialization
        self.config = self._setup_configuration()

        # Infrastructure initialization
        self.publishers_dict = self._setup_publishers()
        self.broadcaster = TransformBroadcaster(self, qos=QoSProfile(depth=10))
        self.bridge = CvBridge()

        # Architecture layers initialization
        self.ros2_publisher = ROS2Publisher(
            node=self,
            config=self.config,
            publishers=self.publishers_dict,
            broadcaster=self.broadcaster,
        )

        self.robot_data_service = RobotDataService(self.ros2_publisher)

        self.webrtc_adapter = WebRTCAdapter(
            config=self.config,
            on_validated_callback=self._on_robot_validated,
            on_video_frame_callback=self._on_video_frame
            if self.config.enable_video
            else None,
            event_loop=self.event_loop,
        )

        self.robot_control_service = RobotControlService(self.webrtc_adapter)

        # Set callback for data
        self.webrtc_adapter.set_data_callback(self._on_robot_data_received)

        # Subscribers initialization
        self._setup_subscribers()

        # State
        self.joy_state = Joy()

    def _setup_configuration(self) -> RobotConfig:
        """Configuration setup"""
        robot_ip = os.getenv("ROBOT_IP", os.getenv("GO2_IP", ""))
        token = os.getenv("ROBOT_TOKEN", os.getenv("GO2_TOKEN", ""))
        conn_type = os.getenv("CONN_TYPE", "")

        # Declare parameters
        self.declare_parameters(
            namespace="",
            parameters=[
                ("robot_ip", robot_ip),
                ("token", token),
                ("conn_type", conn_type),
                ("enable_video", True),
                ("decode_lidar", True),
                ("publish_raw_voxel", False),
                ("obstacle_avoidance", False),
                ("publish_raw_image", False),
                ("publish_compressed_image", True),
                ("jpeg_quality", 80),
                ("enable_lidar", True),
            ],
        )

        self.add_on_set_parameters_callback(self._on_set_parameters)

        # Get parameter values
        config = RobotConfig.from_params(
            robot_ip=self.get_parameter("robot_ip").get_parameter_value().string_value,
            token=self.get_parameter("token").get_parameter_value().string_value,
            conn_type=self.get_parameter("conn_type")
            .get_parameter_value()
            .string_value,
            enable_video=self.get_parameter("enable_video")
            .get_parameter_value()
            .bool_value,
            decode_lidar=self.get_parameter("decode_lidar")
            .get_parameter_value()
            .bool_value,
            publish_raw_voxel=self.get_parameter("publish_raw_voxel")
            .get_parameter_value()
            .bool_value,
            obstacle_avoidance=self.get_parameter("obstacle_avoidance")
            .get_parameter_value()
            .bool_value,
            publish_raw_image=self.get_parameter("publish_raw_image")
            .get_parameter_value()
            .bool_value,
            publish_compressed_image=(
                self.get_parameter("publish_compressed_image")
                .get_parameter_value()
                .bool_value
            ),
            jpeg_quality=self.get_parameter("jpeg_quality")
            .get_parameter_value()
            .integer_value,
            enable_lidar=self.get_parameter("enable_lidar")
            .get_parameter_value()
            .bool_value,
        )

        # Log configuration
        self.get_logger().info(f"Robot IPs: {config.robot_ip_list}")
        self.get_logger().info(f"Connection type: {config.conn_type}")
        self.get_logger().info(f"Connection mode: {config.conn_mode}")
        self.get_logger().info(f"Enable video: {config.enable_video}")
        self.get_logger().info(f"Decode lidar: {config.decode_lidar}")
        self.get_logger().info(f"Publish raw voxel: {config.publish_raw_voxel}")
        self.get_logger().info(f"Obstacle avoidance: {config.obstacle_avoidance}")
        self.get_logger().info(f"Publish raw image: {config.publish_raw_image}")
        self.get_logger().info(
            f"Publish compressed image: {config.publish_compressed_image}"
        )
        self.get_logger().info(f"JPEG quality: {config.jpeg_quality}")
        self.get_logger().info(f"Enable lidar: {config.enable_lidar}")

        return config

    def _setup_publishers(self) -> Dict[str, list]:
        """ROS2 publishers setup"""
        qos_profile = QoSProfile(depth=10)
        best_effort_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )

        publishers = {
            "joint_state": [],
            "robot_state": [],
            "lidar": [],
            "odometry": [],
            "imu": [],
            "camera": [],
            "camera_info": [],
            "camera_compressed": [],
            "voxel": [],
        }

        num_robots = len(self.config.robot_ip_list)

        for i in range(num_robots):
            # Define topics depending on connection mode
            if self.config.conn_mode == "single":
                joint_topic = "joint_states"
                robot_state_topic = "go2_states"
                lidar_topic = "point_cloud2"
                odom_topic = "odom"
                imu_topic = "imu"
                camera_topic = "camera/image_raw"
                camera_info_topic = "camera/camera_info"
                camera_compressed_topic = "camera/image_raw/compressed"
                voxel_topic = "/utlidar/voxel_map_compressed"
            else:
                prefix = f"robot{i}"
                joint_topic = f"{prefix}/joint_states"
                robot_state_topic = f"{prefix}/go2_states"
                lidar_topic = f"{prefix}/point_cloud2"
                odom_topic = f"{prefix}/odom"
                imu_topic = f"{prefix}/imu"
                camera_topic = f"{prefix}/camera/image_raw"
                camera_info_topic = f"{prefix}/camera/camera_info"
                camera_compressed_topic = f"{prefix}/camera/image_raw/compressed"
                voxel_topic = f"{prefix}/utlidar/voxel_map_compressed"

            # Create publishers
            publishers["joint_state"].append(
                self.create_publisher(JointState, joint_topic, qos_profile)
            )
            publishers["robot_state"].append(
                self.create_publisher(Go2State, robot_state_topic, qos_profile)
            )
            publishers["lidar"].append(
                self.create_publisher(
                    PointCloud2,
                    lidar_topic,
                    best_effort_qos,
                    qos_overriding_options=QoSOverridingOptions.with_default_policies(),
                )
            )
            publishers["odometry"].append(
                self.create_publisher(Odometry, odom_topic, qos_profile)
            )
            publishers["imu"].append(self.create_publisher(IMU, imu_topic, qos_profile))

            if self.config.enable_video and self.config.publish_raw_image:
                publishers["camera"].append(
                    self.create_publisher(
                        Image,
                        camera_topic,
                        best_effort_qos,
                        qos_overriding_options=QoSOverridingOptions.with_default_policies(),
                    )
                )

            if self.config.enable_video and self.config.publish_compressed_image:
                publishers["camera_compressed"].append(
                    self.create_publisher(
                        CompressedImage,
                        camera_compressed_topic,
                        best_effort_qos,
                        qos_overriding_options=QoSOverridingOptions.with_default_policies(),
                    )
                )

            if self.config.enable_video and (
                self.config.publish_raw_image or self.config.publish_compressed_image
            ):
                publishers["camera_info"].append(
                    self.create_publisher(
                        CameraInfo,
                        camera_info_topic,
                        best_effort_qos,
                        qos_overriding_options=QoSOverridingOptions.with_default_policies(),
                    )
                )

            if self.config.publish_raw_voxel:
                publishers["voxel"].append(
                    self.create_publisher(
                        VoxelMapCompressed, voxel_topic, best_effort_qos
                    )
                )

        return publishers

    def _setup_subscribers(self) -> None:
        """ROS2 subscribers setup"""
        qos_profile = QoSProfile(depth=10)

        # Command subscribers
        num_robots = len(self.config.robot_ip_list)

        if self.config.conn_mode == "single":
            self.create_subscription(
                Twist, "cmd_vel", lambda msg: self._on_cmd_vel(msg, "0"), qos_profile
            )
            self.create_subscription(
                WebRtcReq,
                "webrtc_req",
                lambda msg: self._on_webrtc_req(msg, "0"),
                qos_profile,
            )
        else:
            for i in range(num_robots):
                self.create_subscription(
                    Twist,
                    f"robot{i}/cmd_vel",
                    lambda msg, robot_id=str(i): self._on_cmd_vel(msg, robot_id),
                    qos_profile,
                )
                self.create_subscription(
                    WebRtcReq,
                    f"robot{i}/webrtc_req",
                    lambda msg, robot_id=str(i): self._on_webrtc_req(msg, robot_id),
                    qos_profile,
                )

        # Joystick subscriber
        self.create_subscription(Joy, "joy", self._on_joy, qos_profile)

        # CycloneDDS support
        if self.config.conn_type == "cyclonedds":
            self.create_subscription(
                LowState, "lowstate", self._on_cyclonedds_low_state, qos_profile
            )
            self.create_subscription(
                PoseStamped,
                "/utlidar/robot_pose",
                self._on_cyclonedds_pose,
                qos_profile,
            )
            self.create_subscription(
                PointCloud2, "/utlidar/cloud", self._on_cyclonedds_lidar, qos_profile
            )

    def _on_set_parameters(self, params) -> SetParametersResult:
        """Callback for parameter changes"""
        result = SetParametersResult(successful=True)

        try:
            for p in params:
                if p.name == "obstacle_avoidance":
                    self.get_logger().info(f"New obstacle_avoidance value: {p.value}")
                    self.config.obstacle_avoidance = p.value

                    try:
                        self.robot_control_service.set_obstacle_avoidance(p.value, "0")
                    except Exception as e:
                        self.get_logger().error(
                            f"Failed to set obstacle avoidance: {e}"
                        )
                        result.successful = False
                        result.reason = str(e)
                        break

                    result.successful = True
                    result.reason = "Updated obstacle_avoidance"
                    break
        except Exception as e:
            self.get_logger().error(f"Error setting parameters: {e}")
            result.successful = False
            result.reason = str(e)

        return result

    def _on_cmd_vel(self, msg: Twist, robot_id: str) -> None:
        """Callback for movement commands"""
        self.get_logger().info(
            f"_on_cmd_vel called: x={msg.linear.x}, y={msg.linear.y}, z={msg.angular.z}, robot_id={robot_id}"
        )
        self.robot_control_service.handle_cmd_vel(
            msg.linear.x,
            msg.linear.y,
            msg.angular.z,
            robot_id,
            self.config.obstacle_avoidance,
        )

    def _on_webrtc_req(self, msg: WebRtcReq, robot_id: str) -> None:
        """Callback for WebRTC requests"""
        self.robot_control_service.handle_webrtc_request(
            msg.api_id, msg.parameter, msg.topic, msg.id, robot_id
        )

    def _on_joy(self, msg: Joy) -> None:
        """Callback for joystick"""
        self.joy_state = msg

    def _on_robot_validated(self, robot_id: str) -> None:
        """Callback after robot validation"""
        self.get_logger().info(f"Robot {robot_id} validated and ready")

        if self.config.enable_lidar:
            self.get_logger().info("Enabling LiDAR stream via WebRTC")
            self.robot_control_service.handle_webrtc_request(
                api_id=0,
                parameter_str=json.dumps("on"),
                topic=RTC_TOPIC["ULIDAR_SWITCH"],
                msg_id="0",
                robot_id=robot_id,
            )

    def _on_robot_data_received(self, msg: Dict[str, Any], robot_id: str) -> None:
        """Callback for receiving data from robot"""
        self.robot_data_service.process_webrtc_message(msg, robot_id)

    async def _on_video_frame(self, track: MediaStreamTrack, robot_id: str) -> None:
        """Callback for processing video frames"""
        logger.info(f"Video frame received for robot {robot_id}")

        while True:
            try:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")

                # Create camera data
                camera_data = CameraData(
                    image=img, height=img.shape[0], width=img.shape[1], encoding="bgr8"
                )

                robot_data = RobotData(
                    robot_id=robot_id, timestamp=0.0, camera_data=camera_data
                )

                # Publish via ROS2Publisher
                self.ros2_publisher.publish_camera_data(robot_data)
                await asyncio.sleep(0)

            except Exception as e:
                logger.error(f"Error processing video frame: {e}")
                break

    # CycloneDDS callbacks
    def _on_cyclonedds_low_state(self, msg: LowState) -> None:
        """Processing LowState for CycloneDDS"""
        # You can add processing for CycloneDDS here if needed
        pass

    def _on_cyclonedds_pose(self, msg: PoseStamped) -> None:
        """Processing pose for CycloneDDS"""
        # You can add processing for CycloneDDS here if needed
        pass

    def _on_cyclonedds_lidar(self, msg: PointCloud2) -> None:
        """Processing lidar for CycloneDDS"""
        # You can add processing for CycloneDDS here if needed
        pass

    async def connect_robots(self) -> None:
        """Connect to robots"""
        if self.config.conn_type == "webrtc":
            for i, robot_ip in enumerate(self.config.robot_ip_list):
                try:
                    await self.webrtc_adapter.connect(str(i))
                except Exception as e:
                    self.get_logger().error(f"Failed to connect to robot {i}: {e}")
                    raise

    async def run_robot_control_loop(self, robot_id: str) -> None:
        """Main robot control loop"""
        while True:
            try:
                # Process joystick commands
                if self.joy_state.buttons:
                    self.robot_control_service.handle_joy_command(
                        self.joy_state.buttons, robot_id
                    )

                # Process WebRTC commands
                self.webrtc_adapter.process_webrtc_commands(robot_id)

                await asyncio.sleep(0.1)

            except Exception as e:
                self.get_logger().error(
                    f"Error in control loop for robot {robot_id}: {e}"
                )
                raise
