"""Tests for interaction_rules — pure function tests, no ROS2.

TDD RED: These tests are written BEFORE the implementation.
All 14 tests should FAIL on first run (ImportError or AssertionError).
"""
import time


# ---------------------------------------------------------------------------
# TestShouldWelcome (5 tests)
# ---------------------------------------------------------------------------
class TestShouldWelcome:
    def test_identity_stable_known_person_returns_welcome(self):
        from vision_perception.interaction_rules import should_welcome

        face = {
            "event_type": "identity_stable",
            "track_id": 1,
            "stable_name": "Roy",
            "sim": 0.42,
            "distance_m": 1.25,
        }
        result = should_welcome(face, set())
        assert result is not None
        assert result["event_type"] == "welcome"
        assert result["name"] == "Roy"
        assert result["track_id"] == 1
        assert result["sim"] == 0.42
        assert result["distance_m"] == 1.25
        assert "stamp" in result

    def test_identity_stable_unknown_returns_none(self):
        from vision_perception.interaction_rules import should_welcome

        face = {
            "event_type": "identity_stable",
            "track_id": 1,
            "stable_name": "unknown",
            "sim": 0.10,
        }
        assert should_welcome(face, set()) is None

    def test_already_welcomed_track_returns_none(self):
        from vision_perception.interaction_rules import should_welcome

        face = {
            "event_type": "identity_stable",
            "track_id": 1,
            "stable_name": "Roy",
            "sim": 0.42,
        }
        assert should_welcome(face, {1}) is None

    def test_track_started_returns_none(self):
        from vision_perception.interaction_rules import should_welcome

        face = {
            "event_type": "track_started",
            "track_id": 1,
            "stable_name": "unknown",
            "sim": 0.0,
        }
        assert should_welcome(face, set()) is None

    def test_track_lost_returns_none(self):
        from vision_perception.interaction_rules import should_welcome

        face = {
            "event_type": "track_lost",
            "track_id": 1,
            "stable_name": "Roy",
            "sim": 0.0,
        }
        assert should_welcome(face, set()) is None


# ---------------------------------------------------------------------------
# TestShouldGestureCommand (5 tests)
# ---------------------------------------------------------------------------
class TestShouldGestureCommand:
    def test_whitelist_stop_with_known_face(self):
        from vision_perception.interaction_rules import should_gesture_command

        gesture = {"gesture": "stop", "confidence": 0.9, "hand": "right"}
        face_state = {"tracks": [{"track_id": 1, "stable_name": "Roy"}]}
        result = should_gesture_command(gesture, face_state)
        assert result is not None
        assert result["event_type"] == "gesture_command"
        assert result["gesture"] == "stop"
        assert result["who"] == "Roy"
        assert result["face_track_id"] == 1

    def test_whitelist_point_without_face_state(self):
        from vision_perception.interaction_rules import should_gesture_command

        gesture = {"gesture": "point", "confidence": 0.85, "hand": "left"}
        result = should_gesture_command(gesture, None)
        assert result is not None
        assert result["gesture"] == "point"
        assert result["who"] is None
        assert result["face_track_id"] is None

    def test_whitelist_thumbs_up_with_only_unknown_faces(self):
        from vision_perception.interaction_rules import should_gesture_command

        gesture = {"gesture": "thumbs_up", "confidence": 0.8, "hand": "right"}
        face_state = {"tracks": [{"track_id": 2, "stable_name": "unknown"}]}
        result = should_gesture_command(gesture, face_state)
        assert result is not None
        assert result["gesture"] == "thumbs_up"
        assert result["who"] is None
        assert result["face_track_id"] is None

    def test_non_whitelist_gesture_wave_returns_none(self):
        from vision_perception.interaction_rules import should_gesture_command

        gesture = {"gesture": "wave", "confidence": 0.9, "hand": "right"}
        assert should_gesture_command(gesture, None) is None

    def test_empty_gesture_returns_none(self):
        from vision_perception.interaction_rules import should_gesture_command

        assert should_gesture_command({}, None) is None
        assert should_gesture_command({"gesture": ""}, None) is None


# ---------------------------------------------------------------------------
# TestShouldFallAlert (4 tests)
# ---------------------------------------------------------------------------
class TestShouldFallAlert:
    def test_fallen_below_threshold_returns_false(self):
        from vision_perception.interaction_rules import should_fall_alert

        now = time.time()
        # fallen for 1.5s, threshold 2.0s → not yet
        assert should_fall_alert("fallen", now - 1.5, 2.0) is False

    def test_fallen_exceeds_threshold_returns_true(self):
        from vision_perception.interaction_rules import should_fall_alert

        now = time.time()
        # fallen for 2.5s, threshold 2.0s → alert
        assert should_fall_alert("fallen", now - 2.5, 2.0) is True

    def test_non_fallen_returns_false(self):
        from vision_perception.interaction_rules import should_fall_alert

        now = time.time()
        assert should_fall_alert("standing", now - 10.0, 2.0) is False

    def test_fallen_exactly_at_threshold_returns_true(self):
        from vision_perception.interaction_rules import should_fall_alert

        now = time.time()
        # fallen for exactly 2.0s, threshold 2.0s → alert
        assert should_fall_alert("fallen", now - 2.0, 2.0) is True
