# vision_perception/test/test_gesture_recognizer_backend.py
"""Tests for gesture_recognizer_backend — label mapping and filtering."""


class TestGestureMap:
    def test_all_builtin_gestures_mapped(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        expected = {"Open_Palm", "Closed_Fist", "Pointing_Up",
                    "Thumb_Up", "Victory", "Thumb_Down", "ILoveYou"}
        assert expected == set(_GESTURE_MAP.keys())

    def test_stop_mapping(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert _GESTURE_MAP["Open_Palm"] == "stop"

    def test_fist_mapping(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert _GESTURE_MAP["Closed_Fist"] == "fist"

    def test_point_mapping(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert _GESTURE_MAP["Pointing_Up"] == "point"

    def test_unknown_not_in_map(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert "Unknown" not in _GESTURE_MAP

    def test_no_duplicate_project_names(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        values = list(_GESTURE_MAP.values())
        assert len(values) == len(set(values)), "Duplicate project gesture names"
