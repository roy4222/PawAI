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
from .gesture_classifier import classify_gesture, detect_ok_circle
from .mock_inference import MockInference
from .pose_classifier import (
    classify_pose,
    _angle_deg,
    _trunk_angle_deg,
    _mid,
    _L_SHOULDER,
    _R_SHOULDER,
    _L_HIP,
    _R_HIP,
    _L_KNEE,
    _R_KNEE,
    _L_ANKLE,
    _R_ANKLE,
)

# COCO 17-point skeleton pairs for stick figure visualization
_SKELETON = [
    (0, 5), (0, 6),       # nose → shoulders
    (5, 7), (7, 9),       # L shoulder → elbow → wrist
    (6, 8), (8, 10),      # R shoulder → elbow → wrist
    (5, 6),               # shoulder span
    (5, 11), (6, 12),     # shoulders → hips
    (11, 12),             # hip span
    (11, 13), (13, 15),   # L hip → knee → ankle
    (12, 14), (14, 16),   # R hip → knee → ankle
]

# MediaPipe 21-point hand skeleton connections
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # index
    (0, 9), (9, 10), (10, 11), (11, 12),   # middle
    (0, 13), (13, 14), (14, 15), (15, 16), # ring
    (0, 17), (17, 18), (18, 19), (19, 20), # pinky
    (5, 9), (9, 13), (13, 17),             # palm
]


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
        self.declare_parameter("gesture_backend", "rtmpose")  # "rtmpose", "mediapipe", or "recognizer"
        self.declare_parameter("gesture_recognizer_model", "~/face_models/gesture_recognizer.task")
        self.declare_parameter("pose_backend", "rtmpose")      # "rtmpose" or "mediapipe"
        self.declare_parameter("pose_complexity", 0)            # 0=lite(fast), 1=full, 2=heavy
        self.declare_parameter("max_hands", 1)                  # 1=single(fast), 2=dual (launch: max_hands:=2)
        self.declare_parameter("hands_complexity", 0)          # 0=lite(fast), 1=full
        self.declare_parameter("gesture_every_n_ticks", 3)      # run hands every N ticks (1=every tick)
        # MOC §3 「穩定性要求」— gesture must hold for this many seconds before
        # /event/gesture_detected is published. Default 0.5 per MOC; set 0.0
        # for live-debug bypass (`ros2 param set ... gesture_stable_s 0.0`).
        self.declare_parameter("gesture_stable_s", 0.5)

        backend = str(self.get_parameter("inference_backend").value or "mock")
        self.use_camera = bool(self.get_parameter("use_camera").value)
        publish_fps = float(self.get_parameter("publish_fps").value or 8.0)
        tick_period = float(self.get_parameter("tick_period").value or 0.05)
        gesture_frames = int(self.get_parameter("gesture_vote_frames").value or 5)
        pose_frames = int(self.get_parameter("pose_vote_frames").value or 20)
        mock_scenario = str(self.get_parameter("mock_scenario").value or "standing_idle")
        self.gesture_min_score = float(self.get_parameter("gesture_min_score").value or 0.1)

        # --- State ---
        self.shutting_down = False
        self.lock = threading.Lock()
        self.color = None
        self.publish_period = 1.0 / max(1.0, publish_fps)
        self.last_publish_ts = 0.0

        # Temporal buffers (node-managed, not in classifiers)
        self.gesture_buffer: deque[str | None] = deque(maxlen=gesture_frames)
        self.pose_buffer: deque[str | None] = deque(maxlen=pose_frames)
        self.last_gesture: str | None = None
        # 0.5s stable gate (MOC §3) — track when current vote winner first appeared.
        stable_s = self.get_parameter("gesture_stable_s").value
        self._gesture_stable_s = 0.5 if stable_s is None else max(0.0, float(stable_s))
        self._gesture_hold_label: str | None = None
        self._gesture_hold_ts: float = 0.0
        self.last_pose: str | None = None
        self.last_hand: str = "right"
        self._tick_counter: int = 0
        self._gesture_every_n = int(self.get_parameter("gesture_every_n_ticks").value or 3)
        self._cached_lh = (np.zeros((21, 2), dtype=np.float32), np.zeros(21, dtype=np.float32))
        self._cached_rh = (np.zeros((21, 2), dtype=np.float32), np.zeros(21, dtype=np.float32))

        # --- Backend configuration ---
        pose_backend = str(self.get_parameter("pose_backend").value or "rtmpose")
        gesture_backend = str(self.get_parameter("gesture_backend").value or "rtmpose")

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
            rtmpose_mode = str(self.get_parameter("rtmpose_mode").value or "balanced")
            rtmpose_device = str(self.get_parameter("rtmpose_device").value or "cuda")
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
            pose_complexity = int(self.get_parameter("pose_complexity").value or 0)
            self.mp_pose = MediaPipePose(complexity=pose_complexity, min_confidence=0.5)
            self.get_logger().info(f"Pose backend: MediaPipe Pose (CPU, complexity={pose_complexity})")
        else:
            self.get_logger().info("Pose backend: RTMPose")

        # --- Gesture backend selection ---
        self.mp_hands = None
        self.gesture_recognizer = None
        if gesture_backend == "mediapipe":
            from .mediapipe_hands import MediaPipeHands
            max_hands = int(self.get_parameter("max_hands").value or 1)
            hands_complexity = int(self.get_parameter("hands_complexity").value or 0)
            self.mp_hands = MediaPipeHands(max_hands=max_hands, min_confidence=0.5,
                                            static_mode=False, model_complexity=hands_complexity)
            self.get_logger().info(f"Gesture backend: MediaPipe Hands (CPU, max_hands={max_hands}, complexity={hands_complexity})")
        elif gesture_backend == "recognizer":
            from .gesture_recognizer_backend import GestureRecognizerBackend
            model_path = str(self.get_parameter("gesture_recognizer_model").value
                             or "~/face_models/gesture_recognizer.task")
            max_hands = int(self.get_parameter("max_hands").value or 2)
            self.gesture_recognizer = GestureRecognizerBackend(
                model_path=model_path, max_hands=max_hands)
            self.get_logger().info(f"Gesture backend: Gesture Recognizer Task API (max_hands={max_hands})")
        else:
            self.get_logger().info("Gesture backend: RTMPose wholebody")

        # --- Camera subscription (only if use_camera=true) ---
        if self.use_camera:
            from cv_bridge import CvBridge
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
            from sensor_msgs.msg import Image
            self.bridge = CvBridge()
            color_topic = str(self.get_parameter("color_topic").value or "/camera/camera/color/image_raw")
            # depth=1 + KEEP_LAST: only process latest frame, drop stale ones
            image_qos = QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
            )
            self.create_subscription(Image, color_topic, self._cb_color, image_qos)

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
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warning(f"imgmsg_to_cv2 failed: {e}")
            return
        with self.lock:
            self.color = frame

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

        # Pose debug log: print angles every ~1s (20 ticks)
        if self._tick_counter % 20 == 0:
            avg_score = float(np.mean(body_scores))
            if avg_score >= 0.2:
                shoulder = _mid(body_kps[_L_SHOULDER], body_kps[_R_SHOULDER])
                hip = _mid(body_kps[_L_HIP], body_kps[_R_HIP])
                knee = _mid(body_kps[_L_KNEE], body_kps[_R_KNEE])
                ankle = _mid(body_kps[_L_ANKLE], body_kps[_R_ANKLE])
                h_a = _angle_deg(shoulder, hip, knee)
                k_a = _angle_deg(hip, knee, ankle)
                t_a = _trunk_angle_deg(shoulder, hip)
                br = bbox_ratio if bbox_ratio is not None else 0.0
                self.get_logger().info(
                    f"pose: raw={pose_raw} hip={h_a:.0f} knee={k_a:.0f} "
                    f"trunk={t_a:.0f} bbox_r={br:.2f} vote={pose_vote}"
                )

        if pose_vote is not None and pose_vote != self.last_pose:
            self.last_pose = pose_vote
            # Use vote ratio as confidence (semantic match with majority vote)
            pose_vote_count = sum(1 for x in self.pose_buffer if x == pose_vote)
            pose_vote_conf = round(pose_vote_count / len(self.pose_buffer), 4) if self.pose_buffer else 0.0
            msg = String()
            msg.data = json.dumps(build_pose_event(pose_vote, pose_vote_conf))
            self.pose_pub.publish(msg)

        # --- Gesture classification ---
        # Recognizer runs every tick (single-pass, no separate hand detection).
        # MediaPipe Hands + classifier skips ticks via gesture_every_n_ticks.
        self._tick_counter += 1
        run_hands = (self.gesture_recognizer is not None
                     or self._tick_counter % self._gesture_every_n == 0)

        if run_hands:
            gesture_raw: str | None = None
            hand = self.last_hand

            if self.gesture_recognizer is not None and image is not None:
                # --- Gesture Recognizer path (single-pass: detect + classify) ---
                detections, lh_kps, lh_scores, rh_kps, rh_scores = \
                    self.gesture_recognizer.detect(image)
                self._cached_lh = (lh_kps, lh_scores)
                self._cached_rh = (rh_kps, rh_scores)
                if detections:
                    best = max(detections, key=lambda d: d[1])
                    gesture_raw, _, hand = best

                # 5/5 OK gesture override (MOC §3 group 1) — geometric rule on
                # KPs takes priority over MediaPipe Recognizer label, since
                # Recognizer doesn't ship OK natively. Run on whichever hand
                # the recognizer favoured (or both if no detection).
                ok_hands = []
                if hand == "left" or not detections:
                    ok_left, ok_conf_left = detect_ok_circle(lh_kps, lh_scores)
                    if ok_left:
                        ok_hands.append(("left", ok_conf_left))
                if hand == "right" or not detections:
                    ok_right, ok_conf_right = detect_ok_circle(rh_kps, rh_scores)
                    if ok_right:
                        ok_hands.append(("right", ok_conf_right))
                if ok_hands:
                    best_ok = max(ok_hands, key=lambda x: x[1])
                    gesture_raw, hand = "ok", best_ok[0]

                self.get_logger().info(
                    f"recognizer: {len(detections)} hands, "
                    f"gesture={gesture_raw} buf={len(self.gesture_buffer)}",
                    throttle_duration_sec=5.0,
                )
            else:
                # --- MediaPipe Hands + classifier path ---
                if self.mp_hands is not None and image is not None:
                    lh_kps, lh_scores, rh_kps, rh_scores = self.mp_hands.detect(image)
                elif result is not None:
                    lh_kps, lh_scores = result.left_hand_kps, result.left_hand_scores
                    rh_kps, rh_scores = result.right_hand_kps, result.right_hand_scores
                else:
                    lh_kps, lh_scores = self._cached_lh
                    rh_kps, rh_scores = self._cached_rh

                self._cached_lh = (lh_kps, lh_scores)
                self._cached_rh = (rh_kps, rh_scores)

                g_left, c_left = classify_gesture(lh_kps, lh_scores,
                                                   min_score=self.gesture_min_score)
                g_right, c_right = classify_gesture(rh_kps, rh_scores,
                                                     min_score=self.gesture_min_score)

                if c_left > c_right and g_left is not None:
                    gesture_raw, hand = g_left, "left"
                elif g_right is not None:
                    gesture_raw, hand = g_right, "right"

                self.get_logger().info(
                    f"hand L={np.mean(lh_scores):.3f} R={np.mean(rh_scores):.3f} "
                    f"gesture={gesture_raw} buf={len(self.gesture_buffer)}",
                    throttle_duration_sec=5.0,
                )

            if gesture_raw is not None:
                self.gesture_buffer.append(gesture_raw)
                self.last_hand = hand
            else:
                self.gesture_buffer.append(None)
            gesture_vote = _majority(self.gesture_buffer)

            # 5/5 MOC §3 0.5s temporal stable gate (param `gesture_stable_s`).
            # Only emit an event when the vote winner has held steady for at
            # least gesture_stable_s seconds; set 0.0 to bypass for debug.
            now_ts = time.time()
            stable_s = self.get_parameter("gesture_stable_s").value
            self._gesture_stable_s = 0.5 if stable_s is None else max(0.0, float(stable_s))

            if gesture_vote is None:
                self._gesture_hold_label = None
                self._gesture_hold_ts = now_ts
                self.last_gesture = None
            else:
                if gesture_vote != self._gesture_hold_label:
                    self._gesture_hold_label = gesture_vote
                    self._gesture_hold_ts = now_ts
                held_long_enough = (
                    self._gesture_stable_s <= 0.0
                    or now_ts - self._gesture_hold_ts >= self._gesture_stable_s
                )

                if held_long_enough and gesture_vote != self.last_gesture:
                    self.last_gesture = gesture_vote
                    # Use vote ratio as confidence (semantic match with majority vote)
                    vote_count = sum(1 for x in self.gesture_buffer if x == gesture_vote)
                    vote_conf = round(vote_count / len(self.gesture_buffer), 4) if self.gesture_buffer else 0.0
                    msg = String()
                    msg.data = json.dumps(build_gesture_event(gesture_vote, vote_conf, self.last_hand))
                    self.gesture_pub.publish(msg)

        # --- Debug image (keypoint overlay, rate-limited) ---
        if self.use_camera and self.debug_pub is not None and image is not None:
            now = time.time()
            if now - self.last_publish_ts >= self.publish_period:
                self.last_publish_ts = now
                # Use cached hand data for drawing (may be from previous tick)
                lh_kps, lh_scores = self._cached_lh
                rh_kps, rh_scores = self._cached_rh
                try:
                    debug = image.copy()
                    # Draw body skeleton lines
                    for i, j in _SKELETON:
                        if body_scores[i] > 0.3 and body_scores[j] > 0.3:
                            pt1 = (int(body_kps[i][0]), int(body_kps[i][1]))
                            pt2 = (int(body_kps[j][0]), int(body_kps[j][1]))
                            cv2.line(debug, pt1, pt2, (0, 255, 0), 2)
                    # Draw body keypoints
                    for i in range(len(body_kps)):
                        if body_scores[i] > 0.3:
                            x, y = int(body_kps[i][0]), int(body_kps[i][1])
                            cv2.circle(debug, (x, y), 4, (0, 255, 0), -1)
                    # Draw hand skeleton + keypoints + bounding box
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
                        # Draw hand skeleton lines
                        if len(valid_pts) >= 5:
                            for i, j in _HAND_CONNECTIONS:
                                if hand_scores[i] > 0.05 and hand_scores[j] > 0.05:
                                    pt1 = (int(hand_kps[i][0]), int(hand_kps[i][1]))
                                    pt2 = (int(hand_kps[j][0]), int(hand_kps[j][1]))
                                    cv2.line(debug, pt1, pt2, color, 1)
                            xs = [p[0] for p in valid_pts]
                            ys = [p[1] for p in valid_pts]
                            cv2.rectangle(debug, (min(xs)-5, min(ys)-5),
                                          (max(xs)+5, max(ys)+5), color, 2)
                            cv2.putText(debug, label_text, (min(xs)-5, min(ys)-15),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    # Labels: pose + gesture (use last known values)
                    g_label = self.last_gesture or "?"
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
        if hasattr(self, "gesture_recognizer") and self.gesture_recognizer is not None:
            self.gesture_recognizer.close()
        if hasattr(self, "adapter") and self.adapter is not None and hasattr(self.adapter, "close"):
            self.adapter.close()


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
