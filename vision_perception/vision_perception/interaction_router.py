"""Thin interaction router: fuses face + gesture + pose into high-level events.

NOT a full executive/brain. Only applies three simple rules:
  - welcome: known face appears
  - gesture_command: whitelisted gesture detected
  - fall_alert: fallen pose persists N seconds

Downstream nodes (event_action_bridge or future brain) consume these events.
"""
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .interaction_rules import (
    GESTURE_WHITELIST,
    should_fall_alert,
    should_gesture_command,
    should_welcome,
)


class InteractionRouter(Node):
    def __init__(self):
        super().__init__("interaction_router")

        # Parameters
        self.declare_parameter("fallen_persist_sec", 2.0)
        self.declare_parameter("gesture_cooldown", 2.0)
        self.declare_parameter("fall_alert_cooldown", 15.0)

        self._fallen_persist = float(
            self.get_parameter("fallen_persist_sec").value or 2.0
        )
        self._gesture_cooldown = float(
            self.get_parameter("gesture_cooldown").value or 2.0
        )
        self._fall_alert_cooldown = float(
            self.get_parameter("fall_alert_cooldown").value or 15.0
        )

        self._welcome_name_cooldown = 30.0  # same name within 30s → skip

        # State
        self._latest_face_state: dict | None = None
        self._welcomed_tracks: set[int] = set()
        self._welcome_name_ts: dict[str, float] = {}  # name → last welcome timestamp
        self._fallen_first_ts: float | None = None
        self._fallen_timer = None  # ROS2 Timer, at most one
        self._last_action_ts: dict[str, float] = {}

        # Subscriptions
        self.create_subscription(
            String, "/event/face_identity", self._on_face_event, 10
        )
        self.create_subscription(
            String, "/state/perception/face", self._on_face_state, 10
        )
        self.create_subscription(
            String, "/event/gesture_detected", self._on_gesture, 10
        )
        self.create_subscription(
            String, "/event/pose_detected", self._on_pose, 10
        )

        # Publishers
        self._welcome_pub = self.create_publisher(
            String, "/event/interaction/welcome", 10
        )
        self._gesture_cmd_pub = self.create_publisher(
            String, "/event/interaction/gesture_command", 10
        )
        self._fall_alert_pub = self.create_publisher(
            String, "/event/interaction/fall_alert", 10
        )

        self.get_logger().info("InteractionRouter ready")

    # ------------------------------------------------------------------
    # Cooldown (same pattern as event_action_bridge)
    # ------------------------------------------------------------------
    def _check_cooldown(self, key: str, cooldown: float) -> bool:
        now = time.time()
        last = self._last_action_ts.get(key, 0.0)
        if now - last < cooldown:
            return False
        self._last_action_ts[key] = now
        return True

    # ------------------------------------------------------------------
    # Face callbacks
    # ------------------------------------------------------------------
    def _on_face_state(self, msg: String):
        """Cache latest face state (10Hz)."""
        try:
            self._latest_face_state = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _on_face_event(self, msg: String):
        """Handle face identity events."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        # track_lost → remove from welcomed set so re-entry triggers welcome
        if data.get("event_type") == "track_lost":
            track_id = data.get("track_id")
            self._welcomed_tracks.discard(track_id)
            return

        result = should_welcome(data, self._welcomed_tracks)
        if result is not None:
            name = result["name"]
            # Name-based debounce: same person within 30s → skip
            now = time.time()
            last_ts = self._welcome_name_ts.get(name, 0.0)
            if now - last_ts < self._welcome_name_cooldown:
                self.get_logger().debug(
                    f"Welcome skipped (name cooldown): {name}",
                    throttle_duration_sec=5.0,
                )
                return
            self._welcomed_tracks.add(result["track_id"])
            self._welcome_name_ts[name] = now
            out = String()
            out.data = json.dumps(result)
            self._welcome_pub.publish(out)
            self.get_logger().info(
                f"WELCOME: {name} (track {result['track_id']})"
            )

    # ------------------------------------------------------------------
    # Gesture callback
    # ------------------------------------------------------------------
    def _on_gesture(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        gesture = data.get("gesture", "")

        # Non-whitelist: debug log only
        if gesture and gesture not in GESTURE_WHITELIST:
            self.get_logger().debug(
                f"Ignored non-whitelist gesture: {gesture}",
                throttle_duration_sec=5.0,
            )
            return

        result = should_gesture_command(data, self._latest_face_state)
        if result is None:
            return

        # stop bypasses cooldown (safety)
        if gesture != "stop":
            if not self._check_cooldown(
                f"gesture_{gesture}", self._gesture_cooldown
            ):
                return

        out = String()
        out.data = json.dumps(result)
        self._gesture_cmd_pub.publish(out)
        self.get_logger().info(
            f"GESTURE_CMD: {result['gesture']} by {result['who']}"
        )

    # ------------------------------------------------------------------
    # Pose callback + fallen timer
    # ------------------------------------------------------------------
    def _on_pose(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        pose = data.get("pose", "")

        if pose == "fallen":
            # Only create timer if one doesn't exist yet
            if self._fallen_timer is None:
                self._fallen_first_ts = data.get("stamp", time.time())
                self._fallen_timer = self.create_timer(
                    1.0, self._check_fallen
                )
                self.get_logger().info("Fallen detected — timer started")
        else:
            # Non-fallen: cancel timer and reset
            if self._fallen_timer is not None:
                self._fallen_timer.cancel()
                self._fallen_timer = None
                self.get_logger().debug("Fallen timer cancelled — pose reset")
            self._fallen_first_ts = None

    def _check_fallen(self):
        """Timer callback (1Hz): check if fallen has persisted long enough."""
        if self._fallen_first_ts is None:
            # Safety: shouldn't happen, but cancel timer
            if self._fallen_timer is not None:
                self._fallen_timer.cancel()
                self._fallen_timer = None
            return

        if not should_fall_alert(
            "fallen", self._fallen_first_ts, self._fallen_persist
        ):
            return  # not yet

        # Persisted long enough — emit alert (with cooldown)
        if self._check_cooldown("fall_alert", self._fall_alert_cooldown):
            elapsed = time.time() - self._fallen_first_ts

            # Enrich with face context
            who = None
            face_track_id = None
            if self._latest_face_state:
                for track in self._latest_face_state.get("tracks", []):
                    if track.get("stable_name", "unknown") != "unknown":
                        who = track["stable_name"]
                        face_track_id = track.get("track_id")
                        break

            event = {
                "stamp": time.time(),
                "event_type": "fall_alert",
                "pose": "fallen",
                "confidence": 1.0,
                "persist_sec": round(elapsed, 2),
                "who": who,
                "face_track_id": face_track_id,
            }
            out = String()
            out.data = json.dumps(event)
            self._fall_alert_pub.publish(out)
            self.get_logger().warning(
                f"FALL_ALERT: persist={event['persist_sec']}s who={who}"
            )

        # One-shot: cancel timer after firing
        if self._fallen_timer is not None:
            self._fallen_timer.cancel()
            self._fallen_timer = None


def main():
    rclpy.init()
    node = InteractionRouter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
