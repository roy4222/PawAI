"""ROS2 node: gesture + pose classification from shared inference.

Two modes:
- use_camera=false (Phase 1): timer-driven, MockInference, no camera needed.
- use_camera=true (Phase 2+): subscribes to D435 camera topics.

Reference: face_perception/face_identity_node.py for error handling patterns.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .event_builder import build_gesture_event, build_pose_event
from .gesture_classifier import classify_gesture
from .inference_adapter import InferenceResult
from .mock_inference import MockInference
from .pose_classifier import classify_pose


def _majority(buffer: deque) -> str | None:
    """Return most common non-None element, or None if empty."""
    items = [x for x in buffer if x is not None]
    if not items:
        return None
    return max(set(items), key=items.count)


def _bbox_ratio_from_kps(body_kps: np.ndarray) -> float | None:
    """Compute width/height ratio from body keypoints bounding box."""
    valid = body_kps[body_kps.sum(axis=1) != 0]
    if len(valid) < 2:
        return None
    mins = valid.min(axis=0)
    maxs = valid.max(axis=0)
    w = maxs[0] - mins[0]
    h = maxs[1] - mins[1]
    if h < 1e-6:
        return None
    return float(w / h)


class VisionPerceptionNode(Node):
    def __init__(self):
        super().__init__("vision_perception_node")

        # --- Parameters ---
        self.declare_parameter("inference_backend", "mock")
        self.declare_parameter("use_camera", False)
        self.declare_parameter("publish_fps", 8.0)
        self.declare_parameter("tick_period", 0.05)
        self.declare_parameter("color_topic", "/camera/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/camera/aligned_depth_to_color/image_raw")
        self.declare_parameter("gesture_vote_frames", 5)
        self.declare_parameter("pose_vote_frames", 20)
        self.declare_parameter("mock_scenario", "standing_idle")

        backend = self.get_parameter("inference_backend").value
        self.use_camera = self.get_parameter("use_camera").value
        publish_fps = self.get_parameter("publish_fps").value
        tick_period = self.get_parameter("tick_period").value
        gesture_frames = self.get_parameter("gesture_vote_frames").value
        pose_frames = self.get_parameter("pose_vote_frames").value
        mock_scenario = self.get_parameter("mock_scenario").value

        # --- State ---
        self.shutting_down = False
        self.lock = threading.Lock()
        self.color = None
        self.publish_period = 1.0 / max(0.1, float(publish_fps))
        self.last_publish_ts = 0.0

        # Temporal buffers (node-managed, not in classifiers)
        self.gesture_buffer: deque[str | None] = deque(maxlen=gesture_frames)
        self.pose_buffer: deque[str | None] = deque(maxlen=pose_frames)
        self.last_gesture: str | None = None
        self.last_pose: str | None = None
        self.last_hand: str = "right"

        # --- Inference adapter ---
        if backend == "mock":
            self.adapter = MockInference(scenario=mock_scenario)
        else:
            raise ValueError(f"Unknown inference_backend: {backend}. Phase 2 will add 'rtmpose'.")

        # --- Camera subscription (only if use_camera=true) ---
        if self.use_camera:
            from cv_bridge import CvBridge
            from sensor_msgs.msg import Image
            self.bridge = CvBridge()
            color_topic = self.get_parameter("color_topic").value
            self.create_subscription(Image, color_topic, self._cb_color, 10)

        # --- Publishers (QoS: Reliable, Volatile, depth=10) ---
        self.gesture_pub = self.create_publisher(String, "/event/gesture_detected", 10)
        self.pose_pub = self.create_publisher(String, "/event/pose_detected", 10)

        if self.use_camera:
            from sensor_msgs.msg import Image as ImageMsg
            self.debug_pub = self.create_publisher(ImageMsg, "/vision_perception/debug_image", 1)
        else:
            self.debug_pub = None

        # --- Timer ---
        self.timer = self.create_timer(tick_period, self._tick)

        self.get_logger().info(
            f"VisionPerceptionNode ready: backend={backend}, use_camera={self.use_camera}, "
            f"scenario={mock_scenario}"
        )

    def _cb_color(self, msg):
        with self.lock:
            self.color = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def _tick(self):
        if self.shutting_down or not rclpy.ok():
            return

        # Get image (None in no-camera mode)
        image = None
        if self.use_camera:
            with self.lock:
                image = self.color.copy() if self.color is not None else None
            if image is None:
                return  # no frame yet

        # --- Inference ---
        try:
            result: InferenceResult = self.adapter.infer(image)
        except Exception as exc:
            self.get_logger().warning(f"Inference failed: {exc}", throttle_duration_sec=1.0)
            return

        # --- Pose classification ---
        bbox_ratio = _bbox_ratio_from_kps(result.body_kps)
        pose_raw, pose_conf = classify_pose(result.body_kps, result.body_scores, bbox_ratio)
        if pose_raw is not None:
            self.pose_buffer.append(pose_raw)
        pose_vote = _majority(self.pose_buffer)

        if pose_vote is not None and pose_vote != self.last_pose:
            self.last_pose = pose_vote
            msg = String()
            msg.data = json.dumps(build_pose_event(pose_vote, pose_conf))
            self.pose_pub.publish(msg)

        # --- Gesture classification (dual hand, pick higher confidence) ---
        g_left, c_left = classify_gesture(result.left_hand_kps, result.left_hand_scores)
        g_right, c_right = classify_gesture(result.right_hand_kps, result.right_hand_scores)

        if c_left > c_right and g_left is not None:
            gesture_raw, gesture_conf, hand = g_left, c_left, "left"
        elif g_right is not None:
            gesture_raw, gesture_conf, hand = g_right, c_right, "right"
        else:
            gesture_raw, gesture_conf, hand = None, 0.0, self.last_hand

        if gesture_raw is not None:
            self.gesture_buffer.append(gesture_raw)
            self.last_hand = hand
        gesture_vote = _majority(self.gesture_buffer)

        if gesture_vote is not None and gesture_vote != self.last_gesture:
            self.last_gesture = gesture_vote
            msg = String()
            msg.data = json.dumps(build_gesture_event(gesture_vote, gesture_conf, self.last_hand))
            self.gesture_pub.publish(msg)

    def close(self):
        self.shutting_down = True
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()


def main():
    rclpy.init()
    node = VisionPerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
