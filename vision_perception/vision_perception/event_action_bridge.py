"""Thin executor: interaction_router processed events -> Go2 actions + TTS.

Subscribes to interaction_router's output topics (NOT raw gesture/pose events).
Does NOT touch speech events or face events (llm_bridge handles those).

TTS guard: non-safety actions are skipped while TTS is playing.
Safety actions (stop, fall_alert) always pass through.
"""
import json
import rclpy
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
FALL_ALERT_TTS = "偵測到跌倒！請注意安全"


class EventActionBridge(Node):
    def __init__(self):
        super().__init__("event_action_bridge")

        # TTS playing state (subscribed from tts_node, latched)
        self._tts_playing = False

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

        self.get_logger().info("EventActionBridge ready (wired to interaction_router)")

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

        self._send_tts(FALL_ALERT_TTS)


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
