# vision_perception/vision_perception/obstacle_debug_overlay.py
"""Depth debug overlay — draws ROI, min_depth, ratio, zone on depth image.

Publishes to /obstacle/debug_image for Foxglove visualization.
Subscribes to depth image + obstacle event.
"""
from __future__ import annotations

import json
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String

# Camera-to-bumper offset (meters) — D435 on Go2 head, body extends ~0.25m forward
CAMERA_TO_BUMPER_M = 0.25

# Colors (BGR)
_GREEN = (0, 255, 0)
_YELLOW = (0, 255, 255)
_RED = (0, 0, 255)
_WHITE = (255, 255, 255)


class ObstacleDebugOverlay(Node):
    def __init__(self):
        super().__init__("obstacle_debug_overlay")

        self.declare_parameter("threshold_m", 2.0)
        self.declare_parameter("warning_m", 2.5)
        self.declare_parameter("max_range_m", 3.0)
        self.declare_parameter("roi_top_ratio", 0.4)
        self.declare_parameter("roi_bottom_ratio", 0.8)
        self.declare_parameter("roi_left_ratio", 0.2)
        self.declare_parameter("roi_right_ratio", 0.8)
        self.declare_parameter("camera_to_bumper_m", CAMERA_TO_BUMPER_M)
        self.declare_parameter(
            "depth_topic",
            "/camera/camera/aligned_depth_to_color/image_raw",
        )

        self._threshold = self.get_parameter("threshold_m").value
        self._warning = self.get_parameter("warning_m").value
        self._max_range = self.get_parameter("max_range_m").value
        self._roi_top = self.get_parameter("roi_top_ratio").value
        self._roi_bot = self.get_parameter("roi_bottom_ratio").value
        self._roi_left = self.get_parameter("roi_left_ratio").value
        self._roi_right = self.get_parameter("roi_right_ratio").value
        self._cam_offset = self.get_parameter("camera_to_bumper_m").value
        depth_topic = self.get_parameter("depth_topic").value

        # Latest obstacle event data
        self._last_event: dict = {}
        self._last_event_time = 0.0

        # Subscribers
        best_effort = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(Image, depth_topic, self._on_depth, best_effort)
        obstacle_qos = QoSProfile(
            depth=10, reliability=ReliabilityPolicy.BEST_EFFORT
        )
        self.create_subscription(
            String, "/event/obstacle_detected", self._on_obstacle, obstacle_qos
        )

        # Publisher
        self._pub = self.create_publisher(Image, "/obstacle/debug_image", 1)

        self.get_logger().info(
            f"ObstacleDebugOverlay started — threshold={self._threshold}m, "
            f"warning={self._warning}m, cam_offset={self._cam_offset}m"
        )

    def _on_obstacle(self, msg: String):
        try:
            self._last_event = json.loads(msg.data)
            self._last_event_time = time.monotonic()
        except json.JSONDecodeError:
            pass

    def _on_depth(self, msg: Image):
        # Decode depth (uint16 mm → float32 m)
        depth_mm = np.frombuffer(msg.data, dtype=np.uint16).reshape(
            msg.height, msg.width
        )
        depth_m = depth_mm.astype(np.float32) / 1000.0

        h, w = depth_m.shape

        # Compute ROI bounds
        y1, y2 = int(h * self._roi_top), int(h * self._roi_bot)
        x1, x2 = int(w * self._roi_left), int(w * self._roi_right)

        # Extract ROI stats
        roi = depth_m[y1:y2, x1:x2]
        valid = roi[(roi > 0.1) & (roi < self._max_range)]
        if len(valid) > 0:
            min_depth = float(np.min(valid))
            ratio = float(np.sum(valid < self._threshold) / len(valid))
        else:
            min_depth = float("inf")
            ratio = 0.0

        # Determine zone
        if min_depth < self._threshold and ratio >= 0.15:
            zone = "DANGER"
            color = _RED
        elif min_depth < self._warning:
            zone = "WARNING"
            color = _YELLOW
        else:
            zone = "CLEAR"
            color = _GREEN

        front_clearance = max(0.0, min_depth - self._cam_offset)

        # Normalize depth to 8-bit for visualization
        depth_vis = np.clip(depth_m / self._max_range * 255, 0, 255).astype(np.uint8)
        frame = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)

        # Draw ROI rectangle
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Text overlay
        lines = [
            f"zone: {zone}",
            f"min_depth: {min_depth:.2f}m",
            f"ratio: {ratio:.0%}",
            f"threshold: {self._threshold}m / warn: {self._warning}m",
            f"front_clearance: ~{front_clearance:.2f}m",
        ]
        for i, line in enumerate(lines):
            y_pos = 25 + i * 22
            # Shadow for readability
            cv2.putText(frame, line, (11, y_pos + 1), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(frame, line, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, _WHITE, 1, cv2.LINE_AA)

        # Zone indicator bar at top
        bar_color = color
        cv2.rectangle(frame, (0, 0), (w, 8), bar_color, -1)

        # Publish as ROS2 Image
        out = Image()
        out.header = msg.header
        out.height, out.width = frame.shape[:2]
        out.encoding = "bgr8"
        out.step = frame.shape[1] * 3
        out.data = frame.tobytes()
        self._pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleDebugOverlay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
