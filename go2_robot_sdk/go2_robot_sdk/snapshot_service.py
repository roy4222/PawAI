#!/usr/bin/env python3
# Copyright (c) 2025, Elder and Dog Project
# SPDX-License-Identifier: BSD-3-Clause
"""
Snapshot Service for MCP Integration.

Provides /capture_snapshot service to capture camera images
and return them as base64-encoded JPEG for LLM analysis.
"""

import base64
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image
from std_srvs.srv import Trigger
from cv_bridge import CvBridge
import cv2


class SnapshotService(Node):
    """ROS2 Node that provides camera snapshot capture service."""

    def __init__(self):
        super().__init__('snapshot_service')

        self.bridge = CvBridge()
        self.latest_image = None
        self.image_timestamp = None

        # Parameters
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('jpeg_quality', 60)
        self.declare_parameter('resize_width', 640)
        self.declare_parameter('resize_height', 480)

        image_topic = self.get_parameter('image_topic').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value
        self.resize_width = self.get_parameter('resize_width').value
        self.resize_height = self.get_parameter('resize_height').value

        # QoS profile matching Go2 driver (BEST_EFFORT)
        best_effort_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Subscribe to camera with matching QoS
        self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            best_effort_qos
        )

        # Create service
        self.create_service(
            Trigger,
            '/capture_snapshot',
            self.capture_callback
        )

        self.get_logger().info(
            f'Snapshot service ready. Subscribed to: {image_topic}'
        )
        self.get_logger().info(
            f'Output: {self.resize_width}x{self.resize_height} '
            f'JPEG (quality={self.jpeg_quality})'
        )

    def image_callback(self, msg: Image):
        """Store the latest image."""
        self.latest_image = msg
        self.image_timestamp = self.get_clock().now()

    def capture_callback(self, request, response):
        """Handle /capture_snapshot service call."""
        if self.latest_image is None:
            response.success = False
            response.message = 'No image available. Check camera topic.'
            self.get_logger().warn('Capture failed: No image received yet')
            return response

        try:
            # Convert to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(
                self.latest_image, 'bgr8'
            )

            # Resize
            resized = cv2.resize(
                cv_image,
                (self.resize_width, self.resize_height)
            )

            # Encode to JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
            _, jpeg_data = cv2.imencode('.jpg', resized, encode_params)

            # Base64 encode
            b64_string = base64.b64encode(jpeg_data.tobytes()).decode('utf-8')

            response.success = True
            response.message = b64_string

            self.get_logger().info(
                f'Captured snapshot: {len(b64_string)} bytes (base64)'
            )

        except Exception as e:
            response.success = False
            response.message = f'Error: {str(e)}'
            self.get_logger().error(f'Capture failed: {e}')

        return response


def main(args=None):
    """Entry point."""
    rclpy.init(args=args)
    node = SnapshotService()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
