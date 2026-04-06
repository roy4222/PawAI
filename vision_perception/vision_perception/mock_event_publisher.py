"""Standalone mock event publisher — bypasses inference + classifier entirely.

Cycles through gesture and pose scenarios, publishing events via event_builder.
Used for frontend development (PawAI Studio GesturePanel / PosePanel).
Does NOT use vision_perception_node — completely independent path.
"""
from __future__ import annotations

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .event_builder import build_gesture_event, build_pose_event

# (event_type, name, duration_sec)
_SEQUENCE = [
    ("gesture", "wave", 2.0),
    ("gesture", "stop", 2.0),
    ("gesture", "point", 2.0),
    ("gesture", "fist", 2.0),
    ("pose", "standing", 3.0),
    ("pose", "sitting", 2.0),
    ("pose", "crouching", 2.0),
    ("pose", "fallen", 2.0),
]


class MockEventPublisher(Node):
    def __init__(self):
        super().__init__("mock_event_publisher")

        self.declare_parameter("interval", 0.5)  # publish interval within each scenario
        self.interval = float(self.get_parameter("interval").value or 0.5)

        self.gesture_pub = self.create_publisher(String, "/event/gesture_detected", 10)
        self.pose_pub = self.create_publisher(String, "/event/pose_detected", 10)

        self._seq_idx = 0
        self._phase_start = time.time()
        self.timer = self.create_timer(self.interval, self._tick)

        self.get_logger().info("MockEventPublisher started — cycling through scenarios")

    def _tick(self):
        now = time.time()
        kind, name, duration = _SEQUENCE[self._seq_idx]

        if now - self._phase_start > duration:
            self._seq_idx = (self._seq_idx + 1) % len(_SEQUENCE)
            self._phase_start = now
            kind, name, duration = _SEQUENCE[self._seq_idx]
            self.get_logger().info(f"Scenario: {kind}/{name}")

        msg = String()
        if kind == "gesture":
            msg.data = json.dumps(build_gesture_event(name, 0.85, "right"))
            self.gesture_pub.publish(msg)
        else:
            msg.data = json.dumps(build_pose_event(name, 0.90))
            self.pose_pub.publish(msg)


def main():
    rclpy.init()
    node = MockEventPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
