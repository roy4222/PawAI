# vision_perception/test/test_gesture_classifier.py
"""Tests for gesture_classifier — pure Python, no ROS2."""
import numpy as np


def _make_hand(positions: dict[int, tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
    """Helper: build (21,2) kps + (21,) scores from sparse dict."""
    kps = np.zeros((21, 2), dtype=np.float32)
    scores = np.ones(21, dtype=np.float32) * 0.9
    for idx, (x, y) in positions.items():
        kps[idx] = [x, y]
    return kps, scores


class TestClassifyGesture:
    """Each test builds keypoints that unambiguously match one gesture."""

    def test_stop_all_fingers_extended(self):
        from vision_perception.gesture_classifier import classify_gesture
        # Wrist at origin, all fingertips far away (spread hand)
        kps, scores = _make_hand({
            0: (0, 0),       # wrist
            4: (80, -60),    # thumb tip
            8: (40, -150),   # index tip
            12: (0, -160),   # middle tip
            16: (-40, -150), # ring tip
            20: (-80, -130), # pinky tip
            # MCP joints closer to wrist
            5: (30, -50), 9: (0, -50), 13: (-30, -50), 17: (-60, -50),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture == "stop"
        assert conf > 0.5

    def test_point_only_index_extended(self):
        from vision_perception.gesture_classifier import classify_gesture
        # Index extended, others curled into fist
        kps, scores = _make_hand({
            0: (0, 0),
            4: (20, -20),    # thumb curled
            8: (40, -150),   # index tip far = extended
            12: (0, -30),    # middle curled
            16: (-20, -30),  # ring curled
            20: (-40, -30),  # pinky curled
            5: (30, -50), 9: (0, -50), 13: (-30, -50), 17: (-60, -50),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture == "point"
        assert conf > 0.5

    def test_fist_all_fingers_curled(self):
        from vision_perception.gesture_classifier import classify_gesture
        # All fingertips clearly CLOSER to wrist than MCPs (curled behind MCPs)
        kps, scores = _make_hand({
            0: (0, 0),
            4: (8, -12),     # thumb tip very close to wrist
            8: (5, -15),     # index tip: dist ~15.8, MCP dist ~44.7 → ratio 0.35 < 0.8
            12: (0, -15),    # middle tip: dist 15, MCP dist 40 → ratio 0.38
            16: (-5, -15),   # ring tip
            20: (-8, -12),   # pinky tip
            5: (20, -40), 9: (0, -40), 13: (-20, -40), 17: (-40, -35),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture == "fist"
        assert conf > 0.5

    def test_ambiguous_returns_none(self):
        from vision_perception.gesture_classifier import classify_gesture
        # Random mid-range positions — no clear gesture
        kps, scores = _make_hand({
            0: (0, 0),
            4: (30, -40), 8: (20, -80), 12: (0, -60),
            16: (-20, -70), 20: (-30, -50),
            5: (20, -40), 9: (0, -40), 13: (-20, -40), 17: (-40, -35),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture is None
        assert conf == 0.0

    def test_zero_keypoints_returns_none(self):
        from vision_perception.gesture_classifier import classify_gesture
        kps = np.zeros((21, 2), dtype=np.float32)
        scores = np.zeros(21, dtype=np.float32)
        gesture, conf = classify_gesture(kps, scores)
        assert gesture is None

    def test_low_scores_returns_none(self):
        from vision_perception.gesture_classifier import classify_gesture
        kps, _ = _make_hand({
            0: (0, 0), 4: (80, -60), 8: (40, -150),
            12: (0, -160), 16: (-40, -150), 20: (-80, -130),
            5: (30, -50), 9: (0, -50), 13: (-30, -50), 17: (-60, -50),
        })
        scores = np.ones(21, dtype=np.float32) * 0.05  # very low
        gesture, conf = classify_gesture(kps, scores)
        assert gesture is None
