"""Thin executor: interaction_router processed events -> Go2 actions + TTS.

Subscribes to interaction_router's output topics (NOT raw gesture/pose events).
Does NOT touch speech events or face events (llm_bridge handles those).

TTS guard: non-safety actions are skipped while TTS is playing.
Safety actions (stop, fall_alert) always pass through.

================================================================================
DEMO BRIDGE — pose → /tts (5/12 sprint)
================================================================================

Below the existing router-driven path, this module ALSO acts as a thin
perception → /tts bridge for the 5/12 demo. It subscribes directly to
``/event/pose_detected`` and ``/state/perception/face`` and publishes pose-
specific TTS templates ("會不會太累" / "我在這裡喔" / "請小心喔" / "{name},偵測到
跌倒,請注意安全!").

Constraints (do NOT relax without architecture review):
  • The pose path ONLY publishes /tts. NEVER /webrtc_req or sport API.
  • DO NOT extend GESTURE_ACTION_MAP. Gesture-driven motions stay in
    interaction_executive.state_machine.
  • This is a TEMPORARY shortcut. The long-term path is proper Brain
    skills (sit_along / careful_remind / fallen_alert) consumed via
    /brain/proposal → /skill_result. Migration tracked in plan
    `~/.claude/plans/speech-bright-rivest.md` Phase 2 Stretch #13.
"""
import json
import threading
import rclpy
import time
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import Bool, String

try:
    from go2_interfaces.msg import WebRtcReq
except ImportError:
    WebRtcReq = None

# api_id 權威來源：go2_robot_sdk/domain/constants/robot_commands.py (ROBOT_CMD)
_STOP_MOVE = 1003
_CONTENT = 1020
_SPORT_TOPIC = "rt/api/sport/request"

# Gesture → Go2 action mapping
# Router already handles whitelist filtering and cooldown
GESTURE_ACTION_MAP = {
    "stop":      {"api_id": _STOP_MOVE, "topic": _SPORT_TOPIC, "tts": None},
    "ok":        {"api_id": _CONTENT, "topic": _SPORT_TOPIC, "tts": None},
    "thumbs_up": {"api_id": _CONTENT, "topic": _SPORT_TOPIC, "tts": "謝謝！"},
}

# Fall alert → TTS only (no Go2 sport action)
# 5/8: empty string disables fall TTS broadcast to avoid interrupting
# conversation on false-positive fallen detections (e.g. carts / chairs).
# Studio still surfaces the red alert chip via /event/* trace; behaviour
# only differs on the audible channel. Restore by setting to a non-empty
# string when the pose_classifier ankle filter and pose buffer reach
# acceptable false-positive rate.
FALL_ALERT_TTS = ""

# DEMO BRIDGE — pose → /tts (NO motion). Standing intentionally absent
# (baseline state). akimbo / knee_kneel templates are placeholders.
#
# 5/8: "fallen" template intentionally REMOVED from this map. The same
# demo-silence rationale as FALL_ALERT_TTS above applies — pose-event
# false positives (carts / chairs / bent persons) would still trigger
# TTS via this code path otherwise. _on_pose_event's early return on
# missing template (`if not template: return`) handles the absence
# cleanly. Restore by re-adding "fallen": "{name}，..." once the pose
# classifier ankle filter and pose buffer reach acceptable
# false-positive rate.
POSE_TTS_MAP = {
    "sitting":     "會不會太累？",
    "crouching":   "我在這裡喔",
    "bending":     "請小心喔",
    "akimbo":      "你看起來很有架式喔！",
    "knee_kneel":  "需要我幫忙嗎？",
}
POSE_TTS_COOLDOWN_DEFAULT_S = 5.0
POSE_TTS_COOLDOWN_FALLEN_S = 10.0

# DEMO BRIDGE — selected gestures → /tts (NO motion, NO GESTURE_ACTION_MAP
# extension). Currently only `wave` lives here — it's an Active 5/12 demo
# skill (`wave_hello`) but the proper Brain orchestration isn't wired yet.
# The legacy `interaction_router` filter excludes wave because there's no
# direct action map entry; this bridge fills the gap by listening to the
# raw `/event/gesture_detected` topic and publishing a TTS template.
GESTURE_TTS_MAP = {
    "wave": "Hi！很高興看到你！",
}
GESTURE_TTS_COOLDOWN_S = 4.0


class EventActionBridge(Node):
    def __init__(self):
        super().__init__("event_action_bridge")

        # TTS playing state (subscribed from tts_node, latched)
        self._tts_playing = False

        # DEMO BRIDGE state: latest stable face name + per-pose / per-gesture cooldown
        self._face_lock = threading.Lock()
        self._latest_face_name: str | None = None
        self._pose_tts_last_ts: dict[str, float] = {}
        self._gesture_tts_last_ts: dict[str, float] = {}

        # Subscribe to interaction_router's processed events (NOT raw events)
        self.create_subscription(
            String,
            "/event/interaction/gesture_command",
            self._on_gesture_command,
            10,
        )
        self.create_subscription(
            String,
            "/event/interaction/fall_alert",
            self._on_fall_alert,
            10,
        )

        # DEMO BRIDGE: subscribe directly to raw pose events + face state
        # + selected raw gesture events (e.g. wave) — see module docstring
        # for rationale + constraints. NEVER publishes Go2 motion from this
        # path; only /tts.
        self.create_subscription(
            String,
            "/event/pose_detected",
            self._on_pose_event,
            10,
        )
        self.create_subscription(
            String,
            "/event/gesture_detected",
            self._on_gesture_event_demo_bridge,
            10,
        )
        face_state_qos = QoSProfile(depth=1)
        self.create_subscription(
            String,
            "/state/perception/face",
            self._on_face_state,
            face_state_qos,
        )

        # Subscribe to TTS playing state for guard logic
        tts_playing_qos = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        self.create_subscription(
            Bool, "/state/tts_playing", self._on_tts_playing, tts_playing_qos
        )

        # Publish to Go2
        if WebRtcReq is not None:
            self.webrtc_pub = self.create_publisher(WebRtcReq, "/webrtc_req", 10)
        else:
            self.webrtc_pub = None
            self.get_logger().warning(
                "go2_interfaces not available — Go2 actions disabled"
            )
        self.tts_pub = self.create_publisher(String, "/tts", 10)

        self.get_logger().info(
            "EventActionBridge ready (router path + DEMO BRIDGE pose→/tts)"
        )

    # ------------------------------------------------------------------
    # TTS guard
    # ------------------------------------------------------------------
    def _on_tts_playing(self, msg: Bool):
        self._tts_playing = msg.data

    # ------------------------------------------------------------------
    # Action helpers
    # ------------------------------------------------------------------
    def _send_action(self, api_id: int, topic: str = _SPORT_TOPIC):
        """Send Go2 sport action via /webrtc_req."""
        if self.webrtc_pub is None or WebRtcReq is None:
            self.get_logger().warning(
                f"Cannot send action api_id={api_id}: no go2_interfaces"
            )
            return
        msg = WebRtcReq()
        msg.id = 0
        msg.topic = topic
        msg.api_id = api_id
        msg.parameter = ""
        msg.priority = 0
        self.webrtc_pub.publish(msg)
        self.get_logger().info(f"Action: api_id={api_id}")

    def _send_tts(self, text: str):
        """Send TTS text."""
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)
        self.get_logger().info(f"TTS: {text}")

    # ------------------------------------------------------------------
    # Event handlers (from interaction_router)
    # ------------------------------------------------------------------
    def _on_gesture_command(self, msg: String):
        """Handle /event/interaction/gesture_command from router."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().warning(
                f"Invalid JSON in gesture_command: {e}",
                throttle_duration_sec=5.0,
            )
            return

        gesture = data.get("gesture")
        if not gesture:
            return

        mapping = GESTURE_ACTION_MAP.get(gesture)
        if not mapping:
            self.get_logger().debug(
                f"No action mapping for gesture: {gesture}",
                throttle_duration_sec=5.0,
            )
            return

        # Safety: stop always passes through
        if gesture == "stop":
            if mapping["api_id"]:
                self._send_action(mapping["api_id"], mapping["topic"])
            return

        # TTS guard: skip non-safety gestures while TTS is playing
        if self._tts_playing:
            self.get_logger().info(
                f"Gesture '{gesture}' skipped: TTS playing"
            )
            return

        if mapping["api_id"]:
            self._send_action(mapping["api_id"], mapping["topic"])
        if mapping.get("tts"):
            self._send_tts(mapping["tts"])

    def _on_fall_alert(self, msg: String):
        """Handle /event/interaction/fall_alert from router.

        Fall alert is high priority — NOT gated by TTS playing state.
        """
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().warning(
                f"Invalid JSON in fall_alert: {e}",
                throttle_duration_sec=5.0,
            )
            return

        who = data.get("who", "unknown")
        persist = data.get("persist_sec", "?")
        self.get_logger().warning(
            f"FALL_ALERT received: who={who}, persist={persist}s"
        )

        # Guard: empty FALL_ALERT_TTS (5/8 demo silence) skips TTS publish
        # to avoid emitting empty /tts payloads that downstream nodes may
        # log-spam or attempt to synthesise as silence.
        if FALL_ALERT_TTS:
            self._send_tts(FALL_ALERT_TTS)

    # ------------------------------------------------------------------
    # DEMO BRIDGE — pose → /tts (NO motion; see module docstring)
    # ------------------------------------------------------------------
    def _on_face_state(self, msg: String):
        """Cache latest stable face name for {name} interpolation."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        tracks = data.get("tracks") or []
        new_name: str | None = None
        for tr in tracks:
            if not isinstance(tr, dict):
                continue
            mode = tr.get("mode")
            name = tr.get("stable_name")
            if mode == "stable" and isinstance(name, str) and name and name != "unknown":
                new_name = name
                break
        with self._face_lock:
            self._latest_face_name = new_name

    def _on_gesture_event_demo_bridge(self, msg: String):
        """[DEMO BRIDGE] /event/gesture_detected → /tts template (no motion).

        Only handles gestures listed in GESTURE_TTS_MAP. Any other gesture
        is ignored here; legacy router path (gesture_command → /webrtc_req)
        still handles stop / ok / thumbs_up motions independently.
        """
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().warning(
                f"Invalid JSON in gesture_event: {e}",
                throttle_duration_sec=5.0,
            )
            return

        gesture = data.get("gesture")
        template = GESTURE_TTS_MAP.get(gesture) if isinstance(gesture, str) else None
        if not template:
            return  # not a demo-bridge gesture; legacy router handles others

        now = time.time()
        last = self._gesture_tts_last_ts.get(gesture, 0.0)
        if now - last < GESTURE_TTS_COOLDOWN_S:
            return
        self._gesture_tts_last_ts[gesture] = now

        with self._face_lock:
            name = self._latest_face_name or "你"
        text = template.format(name=name)
        self._send_tts(text)
        self.get_logger().info(
            f"[demo-bridge] gesture={gesture} name={name!r} → tts={text!r}"
        )

    def _on_pose_event(self, msg: String):
        """[DEMO BRIDGE] /event/pose_detected → /tts template (no motion)."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().warning(
                f"Invalid JSON in pose_event: {e}",
                throttle_duration_sec=5.0,
            )
            return

        pose = data.get("pose")
        template = POSE_TTS_MAP.get(pose) if isinstance(pose, str) else None
        if not template:
            return  # standing / akimbo / knee_kneel — bridge ignores

        cooldown = (
            POSE_TTS_COOLDOWN_FALLEN_S if pose == "fallen"
            else POSE_TTS_COOLDOWN_DEFAULT_S
        )
        now = time.time()
        last = self._pose_tts_last_ts.get(pose, 0.0)
        if now - last < cooldown:
            return
        self._pose_tts_last_ts[pose] = now

        with self._face_lock:
            name = self._latest_face_name or "你"
        text = template.format(name=name)
        self._send_tts(text)
        self.get_logger().info(
            f"[demo-bridge] pose={pose} name={name!r} → tts={text!r}"
        )


def main():
    rclpy.init()
    node = EventActionBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
