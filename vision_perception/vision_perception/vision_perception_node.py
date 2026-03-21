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

import cv2
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
        self.declare_parameter("rtmpose_mode", "balanced")  # "lightweight" or "balanced"
        self.declare_parameter("rtmpose_device", "cuda")    # "cuda" or "cpu"
        self.declare_parameter("gesture_min_score", 0.1)    # hand keypoint confidence threshold
        self.declare_parameter("gesture_backend", "rtmpose")  # "rtmpose" or "mediapipe"
        self.declare_parameter("pose_backend", "rtmpose")      # "rtmpose" or "mediapipe"

        backend = self.get_parameter("inference_backend").value
        self.use_camera = self.get_parameter("use_camera").value
        publish_fps = self.get_parameter("publish_fps").value
        tick_period = self.get_parameter("tick_period").value
        gesture_frames = self.get_parameter("gesture_vote_frames").value
        pose_frames = self.get_parameter("pose_vote_frames").value
        mock_scenario = self.get_parameter("mock_scenario").value
        self.gesture_min_score = self.get_parameter("gesture_min_score").value

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

        # --- Backend configuration ---
        pose_backend = self.get_parameter("pose_backend").value
        gesture_backend = self.get_parameter("gesture_backend").value

        if pose_backend == "mediapipe" and gesture_backend == "rtmpose":
            raise ValueError(
                "pose_backend=mediapipe + gesture_backend=rtmpose is not supported. "
                "Use mediapipe/mediapipe or rtmpose/rtmpose or rtmpose/mediapipe."
            )

        # --- RTMPose adapter (only load if pose_backend needs it) ---
        self.adapter = None
        if backend == "mock":
            self.adapter = MockInference(scenario=mock_scenario)
        elif backend == "rtmpose" and pose_backend == "rtmpose":
            from .rtmpose_inference import RTMPoseInference
            rtmpose_mode = self.get_parameter("rtmpose_mode").value
            rtmpose_device = self.get_parameter("rtmpose_device").value
            self.adapter = RTMPoseInference(
                mode=rtmpose_mode,
                backend="onnxruntime",
                device=rtmpose_device,
            )
        elif pose_backend == "mediapipe":
            pass  # No RTMPose needed — fully MediaPipe
        else:
            raise ValueError(f"Unknown inference_backend: {backend}")

        # --- MediaPipe Pose (only if pose_backend=mediapipe) ---
        self.mp_pose = None
        if pose_backend == "mediapipe":
            from .mediapipe_pose import MediaPipePose
            self.mp_pose = MediaPipePose(complexity=1, min_confidence=0.5)
            self.get_logger().info("Pose backend: MediaPipe Pose (CPU)")
        else:
            self.get_logger().info("Pose backend: RTMPose")

        # --- MediaPipe Hands (only if gesture_backend=mediapipe) ---
        self.mp_hands = None
        if gesture_backend == "mediapipe":
            from .mediapipe_hands import MediaPipeHands
            self.mp_hands = MediaPipeHands(max_hands=2, min_confidence=0.5,
                                            static_mode=False)
            self.get_logger().info("Gesture backend: MediaPipe Hands (CPU)")
        else:
            self.get_logger().info("Gesture backend: RTMPose wholebody")

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
        result = None
        if self.adapter is not None:
            try:
                result = self.adapter.infer(image)
            except Exception as exc:
                self.get_logger().warning(f"Inference failed: {exc}", throttle_duration_sec=1.0)

        # --- Pose keypoints source ---
        if self.mp_pose is not None and image is not None:
            body_kps, body_scores = self.mp_pose.detect(image)
        elif result is not None:
            body_kps, body_scores = result.body_kps, result.body_scores
        else:
            return  # no inference source available

        # --- Pose classification ---
        bbox_ratio = _bbox_ratio_from_kps(body_kps)
        pose_raw, pose_conf = classify_pose(body_kps, body_scores, bbox_ratio)
        if pose_raw is not None:
            self.pose_buffer.append(pose_raw)
        pose_vote = _majority(self.pose_buffer)

        if pose_vote is not None and pose_vote != self.last_pose:
            self.last_pose = pose_vote
            msg = String()
            msg.data = json.dumps(build_pose_event(pose_vote, pose_conf))
            self.pose_pub.publish(msg)

        # --- Gesture classification (dual hand, pick higher confidence) ---
        # Select hand keypoint source: MediaPipe (CPU) or RTMPose (from wholebody)
        if self.mp_hands is not None and image is not None:
            lh_kps, lh_scores, rh_kps, rh_scores = self.mp_hands.detect(image)
        else:
            lh_kps, lh_scores = result.left_hand_kps, result.left_hand_scores
            rh_kps, rh_scores = result.right_hand_kps, result.right_hand_scores

        g_left, c_left = classify_gesture(lh_kps, lh_scores,
                                           min_score=self.gesture_min_score)
        g_right, c_right = classify_gesture(rh_kps, rh_scores,
                                             min_score=self.gesture_min_score)

        if c_left > c_right and g_left is not None:
            gesture_raw, gesture_conf, hand = g_left, c_left, "left"
        elif g_right is not None:
            gesture_raw, gesture_conf, hand = g_right, c_right, "right"
        else:
            gesture_raw, gesture_conf, hand = None, 0.0, self.last_hand

        # Debug log (throttled)
        self.get_logger().info(
            f"hand L={np.mean(lh_scores):.3f} R={np.mean(rh_scores):.3f} "
            f"gesture={gesture_raw} buf={len(self.gesture_buffer)}",
            throttle_duration_sec=5.0,
        )

        if gesture_raw is not None:
            self.gesture_buffer.append(gesture_raw)
            self.last_hand = hand
        gesture_vote = _majority(self.gesture_buffer)

        if gesture_vote is not None and gesture_vote != self.last_gesture:
            self.last_gesture = gesture_vote
            msg = String()
            msg.data = json.dumps(build_gesture_event(gesture_vote, gesture_conf, self.last_hand))
            self.gesture_pub.publish(msg)

        # --- Debug image (keypoint overlay, rate-limited) ---
        if self.use_camera and self.debug_pub is not None and image is not None:
            now = time.time()
            if now - self.last_publish_ts >= self.publish_period:
                self.last_publish_ts = now
                try:
                    debug = image.copy()
                    # Draw body keypoints (from pose source)
                    for i in range(len(body_kps)):
                        if body_scores[i] > 0.3:
                            x, y = int(body_kps[i][0]), int(body_kps[i][1])
                            cv2.circle(debug, (x, y), 4, (0, 255, 0), -1)
                    # Draw hand keypoints + bounding box (from gesture source)
                    for hand_kps, hand_scores, color, label_text in [
                        (lh_kps, lh_scores, (255, 100, 0), "L"),
                        (rh_kps, rh_scores, (0, 100, 255), "R"),
                    ]:
                        valid_pts = []
                        for i in range(len(hand_kps)):
                            if hand_scores[i] > 0.05:
                                x, y = int(hand_kps[i][0]), int(hand_kps[i][1])
                                cv2.circle(debug, (x, y), 5, color, -1)
                                valid_pts.append((x, y))
                        # Draw hand bounding box if enough points
                        if len(valid_pts) >= 5:
                            xs = [p[0] for p in valid_pts]
                            ys = [p[1] for p in valid_pts]
                            cv2.rectangle(debug, (min(xs)-5, min(ys)-5),
                                          (max(xs)+5, max(ys)+5), color, 2)
                            cv2.putText(debug, label_text, (min(xs)-5, min(ys)-15),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    # Labels: pose + gesture + confidence
                    g_label = gesture_vote or gesture_raw or "?"
                    label = f"pose:{pose_vote or '?'}  gesture:{g_label} ({self.last_hand})"
                    cv2.putText(debug, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    self.debug_pub.publish(self.bridge.cv2_to_imgmsg(debug, encoding="bgr8"))
                except Exception as exc:
                    self.get_logger().warning(f"debug_image publish failed: {exc}", throttle_duration_sec=1.0)

    def close(self):
        self.shutting_down = True
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()
        if hasattr(self, "mp_hands") and self.mp_hands is not None:
            self.mp_hands.close()
        if hasattr(self, "mp_pose") and self.mp_pose is not None:
            self.mp_pose.close()


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
