"""Tests for event_builder — validates contract v2.0 alignment."""


class TestBuildGestureEvent:
    def test_contains_all_contract_fields(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("stop", 0.87, "right")
        assert set(evt.keys()) == {"stamp", "event_type", "gesture", "confidence", "hand"}

    def test_event_type_is_gesture_detected(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("stop", 0.87, "right")
        assert evt["event_type"] == "gesture_detected"

    def test_fist_compat_map(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("fist", 0.9, "left")
        assert evt["gesture"] == "ok"  # v2.0 contract

    def test_stop_passes_through(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("stop", 0.85, "right")
        assert evt["gesture"] == "stop"

    def test_confidence_rounded(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("point", 0.87654321, "right")
        assert evt["confidence"] == 0.8765


class TestBuildPoseEvent:
    def test_contains_all_contract_fields(self):
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("standing", 0.92)
        assert set(evt.keys()) == {"stamp", "event_type", "pose", "confidence", "track_id"}

    def test_event_type_is_pose_detected(self):
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("fallen", 0.95)
        assert evt["event_type"] == "pose_detected"

    def test_phase1_internal_track_id_is_zero(self):
        """Phase 1 internal convention — NOT a contract guarantee."""
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("standing", 0.9)
        assert evt["track_id"] == 0

    def test_stamp_is_float(self):
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("sitting", 0.8)
        assert isinstance(evt["stamp"], float)
