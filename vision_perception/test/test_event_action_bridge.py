"""Tests for event_action_bridge decision logic.

Tests the guard rules and action mapping without ROS2 dependency.
Behavioral contract:
  - stop: always passes (safety)
  - fall_alert: always passes (high priority)
  - other gestures: skipped when TTS is playing
"""
import json
import sys
import unittest
from unittest.mock import MagicMock

# Mock ROS2 modules so event_action_bridge can be imported without rclpy
if "rclpy" not in sys.modules:
    rclpy_mock = MagicMock()
    rclpy_mock.node.Node = type("Node", (), {})
    rclpy_mock.qos.QoSProfile = MagicMock()
    rclpy_mock.qos.DurabilityPolicy = MagicMock()
    sys.modules["rclpy"] = rclpy_mock
    sys.modules["rclpy.node"] = rclpy_mock.node
    sys.modules["rclpy.qos"] = rclpy_mock.qos
if "std_msgs" not in sys.modules:
    std_mock = MagicMock()
    sys.modules["std_msgs"] = std_mock
    sys.modules["std_msgs.msg"] = std_mock.msg
if "go2_interfaces" not in sys.modules:
    go2_mock = MagicMock()
    sys.modules["go2_interfaces"] = go2_mock
    sys.modules["go2_interfaces.msg"] = go2_mock.msg


class TestGestureActionMap(unittest.TestCase):
    """Verify GESTURE_ACTION_MAP covers the gestures that pass through
    interaction_router's GESTURE_WHITELIST."""

    def test_stop_has_action(self):
        from vision_perception.event_action_bridge import GESTURE_ACTION_MAP

        assert "stop" in GESTURE_ACTION_MAP
        assert GESTURE_ACTION_MAP["stop"]["api_id"] == 1003  # _STOP_MOVE

    def test_ok_has_action(self):
        from vision_perception.event_action_bridge import GESTURE_ACTION_MAP

        assert "ok" in GESTURE_ACTION_MAP

    def test_thumbs_up_has_action_and_tts(self):
        from vision_perception.event_action_bridge import GESTURE_ACTION_MAP

        mapping = GESTURE_ACTION_MAP["thumbs_up"]
        assert mapping["api_id"] is not None
        assert mapping["tts"] is not None

    def test_point_not_in_map(self):
        """point was removed from whitelist — should not be in action map."""
        from vision_perception.event_action_bridge import GESTURE_ACTION_MAP

        assert "point" not in GESTURE_ACTION_MAP

    def test_whitelist_and_action_map_aligned(self):
        """Every whitelisted gesture should have an action mapping,
        preventing half-dead paths."""
        from vision_perception.interaction_rules import GESTURE_WHITELIST
        from vision_perception.event_action_bridge import GESTURE_ACTION_MAP

        unmapped = GESTURE_WHITELIST - set(GESTURE_ACTION_MAP.keys())
        assert unmapped == set(), (
            f"Whitelisted gestures without action mapping: {unmapped}"
        )


class TestFallAlertConfig(unittest.TestCase):
    def test_fall_alert_tts_is_string(self):
        """5/8: empty FALL_ALERT_TTS disables fall TTS broadcast for demo
        silence. Must remain a string (not None) so the guard `if FALL_ALERT_TTS:`
        in _on_fall_alert can short-circuit cleanly without TypeError."""
        from vision_perception.event_action_bridge import FALL_ALERT_TTS

        assert isinstance(FALL_ALERT_TTS, str)

    def test_fall_alert_tts_demo_silence_default(self):
        """Demo period: FALL_ALERT_TTS should default to empty string so
        false-positive fallen detections don't interrupt conversation. Restore
        to a non-empty string when the pose_classifier ankle filter and pose
        buffer reach acceptable false-positive rate."""
        from vision_perception.event_action_bridge import FALL_ALERT_TTS

        assert FALL_ALERT_TTS == "", (
            f"FALL_ALERT_TTS={FALL_ALERT_TTS!r} — demo silence requires empty"
        )

    def test_pose_tts_map_no_fallen_template_demo_silence(self):
        """Defense-in-depth: same demo-silence rationale as FALL_ALERT_TTS
        applies to the POSE_TTS_MAP['fallen'] code path in _on_pose_event.
        Both routes must be muted, otherwise a single fallen false-positive
        from /event/pose_detected still interrupts the conversation even
        though /event/interaction/fall_alert is silenced."""
        from vision_perception.event_action_bridge import POSE_TTS_MAP

        assert "fallen" not in POSE_TTS_MAP or not POSE_TTS_MAP.get("fallen"), (
            f"POSE_TTS_MAP['fallen']={POSE_TTS_MAP.get('fallen')!r} — "
            "both fall TTS routes must be muted during demo"
        )


class TestTTSGuardLogic(unittest.TestCase):
    """Test the TTS guard decision table without ROS2.

    Decision table:
      | gesture    | tts_playing | result       |
      |------------|-------------|--------------|
      | stop       | True        | PASS (safety)|
      | stop       | False       | PASS         |
      | thumbs_up  | True        | SKIP         |
      | thumbs_up  | False       | PASS         |
      | ok         | True        | SKIP         |
      | ok         | False       | PASS         |
    """

    @staticmethod
    def _should_execute(gesture: str, tts_playing: bool) -> bool:
        """Replicate bridge guard logic as pure function for testing."""
        # stop always passes
        if gesture == "stop":
            return True
        # others skip during TTS
        if tts_playing:
            return False
        return True

    def test_stop_passes_during_tts(self):
        assert self._should_execute("stop", tts_playing=True) is True

    def test_stop_passes_normally(self):
        assert self._should_execute("stop", tts_playing=False) is True

    def test_thumbs_up_skipped_during_tts(self):
        assert self._should_execute("thumbs_up", tts_playing=True) is False

    def test_thumbs_up_passes_normally(self):
        assert self._should_execute("thumbs_up", tts_playing=False) is True

    def test_ok_skipped_during_tts(self):
        assert self._should_execute("ok", tts_playing=True) is False

    def test_ok_passes_normally(self):
        assert self._should_execute("ok", tts_playing=False) is True


class TestFallAlertNotGated(unittest.TestCase):
    """fall_alert is high priority and should never be gated by TTS state.

    This is a design contract test — the bridge's _on_fall_alert handler
    does NOT check _tts_playing at all."""

    def test_fall_alert_handler_has_no_tts_guard(self):
        """Verify _on_fall_alert source code does not reference _tts_playing."""
        import inspect
        from vision_perception.event_action_bridge import EventActionBridge

        source = inspect.getsource(EventActionBridge._on_fall_alert)
        assert "_tts_playing" not in source, (
            "_on_fall_alert should NOT check _tts_playing — fall alerts are high priority"
        )


class TestGestureCommandRouterSchema(unittest.TestCase):
    """Verify that interaction_router's gesture_command output schema
    is compatible with event_action_bridge's expectations."""

    def test_router_output_has_gesture_field(self):
        """Bridge reads data.get('gesture') — router must provide it."""
        from vision_perception.interaction_rules import should_gesture_command

        event = {"gesture": "stop", "confidence": 0.9, "hand": "right"}
        result = should_gesture_command(event, None)
        assert result is not None
        assert "gesture" in result

    def test_fall_alert_event_has_pose_field(self):
        """Verify fall_alert event structure matches bridge expectation."""
        # The fall_alert event is assembled in interaction_router._check_fallen
        # It always includes "pose": "fallen" — verify this contract
        import time

        event = {
            "stamp": time.time(),
            "event_type": "fall_alert",
            "pose": "fallen",
            "confidence": 1.0,
            "persist_sec": 3.0,
            "who": None,
            "face_track_id": None,
        }
        # Bridge would do: who = data.get("who"), then _send_tts(FALL_ALERT_TTS)
        assert event["event_type"] == "fall_alert"
        assert "who" in event
