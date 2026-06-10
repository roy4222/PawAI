# vision_perception/test/test_gesture_recognizer_backend.py
"""Tests for gesture_recognizer_backend — label mapping and filtering.

Also hosts the 6/9 HITL gesture-misfire fix tests (gesture_min_conf +
majority_vote min_votes) — kept here (not a new test file) because CI
(.github/workflows/ros_build.yaml) lists test files explicitly.
"""
import inspect
from types import SimpleNamespace

import numpy as np


class TestGestureMap:
    def test_all_builtin_gestures_mapped(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        expected = {"Open_Palm", "Closed_Fist", "Pointing_Up", "Thumb_Up", "Victory"}
        assert expected == set(_GESTURE_MAP.keys())

    def test_palm_mapping(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert _GESTURE_MAP["Open_Palm"] == "palm"

    def test_fist_mapping(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert _GESTURE_MAP["Closed_Fist"] == "fist"

    def test_index_mapping(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert _GESTURE_MAP["Pointing_Up"] == "index"

    def test_non_moc_builtin_gestures_are_dropped(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert "Thumb_Down" not in _GESTURE_MAP
        assert "ILoveYou" not in _GESTURE_MAP

    def test_unknown_not_in_map(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        assert "Unknown" not in _GESTURE_MAP

    def test_no_duplicate_project_names(self):
        from vision_perception.gesture_recognizer_backend import _GESTURE_MAP
        values = list(_GESTURE_MAP.values())
        assert len(values) == len(set(values)), "Duplicate project gesture names"


# ── 6/9 HITL gesture_min_conf filtering (Roy 拍板, demo-blocking) ──────────
# Recognizer score 從未被檢查 → 低信心誤判直接進投票（OK 也誤觸）。
# detect() 加 gesture_min_conf 門檻；keypoints 仍記錄（OK-circle / wave 不受影響）。

class _FakeImageFormat:
    SRGB = "SRGB"


class _FakeMp:
    """Stands in for the mediapipe module attribute used inside detect()."""
    ImageFormat = _FakeImageFormat

    @staticmethod
    def Image(image_format=None, data=None):
        return data


class _FakeRecognizer:
    def __init__(self, result):
        self._result = result

    def recognize_for_video(self, mp_image, timestamp_ms):
        return self._result


def _fake_result(mp_name: str, score: float, hand: str = "Right"):
    """Build a minimal GestureRecognizer result with one hand."""
    gesture = SimpleNamespace(category_name=mp_name, score=score)
    handed = SimpleNamespace(category_name=hand, score=0.9)
    landmarks = [SimpleNamespace(x=0.5, y=0.5) for _ in range(21)]
    return SimpleNamespace(
        gestures=[[gesture]],
        handedness=[[handed]],
        hand_landmarks=[landmarks],
    )


def _make_backend(result, gesture_min_conf: float):
    """Instantiate the backend without mediapipe / model file (mock pattern:
    __new__ + hand-set attributes, recognize_for_video stubbed)."""
    from vision_perception.gesture_recognizer_backend import GestureRecognizerBackend
    backend = GestureRecognizerBackend.__new__(GestureRecognizerBackend)
    backend._gesture_min_conf = float(gesture_min_conf)
    backend._t0 = 0.0
    backend._mp = _FakeMp
    backend._recognizer = _FakeRecognizer(result)
    return backend


_IMG = np.zeros((48, 64, 3), dtype=np.uint8)


class TestGestureMinConfFilter:
    def test_constructor_default_is_zero(self):
        """Default gesture_min_conf=0.0 = 現行行為（不過濾）。"""
        from vision_perception.gesture_recognizer_backend import GestureRecognizerBackend
        sig = inspect.signature(GestureRecognizerBackend.__init__)
        assert sig.parameters["gesture_min_conf"].default == 0.0

    def test_zero_threshold_keeps_low_confidence(self):
        backend = _make_backend(_fake_result("Open_Palm", 0.3), gesture_min_conf=0.0)
        detections, *_ = backend.detect(_IMG)
        assert detections == [("palm", 0.3, "right")]

    def test_below_threshold_dropped(self):
        backend = _make_backend(_fake_result("Open_Palm", 0.6), gesture_min_conf=0.7)
        detections, *_ = backend.detect(_IMG)
        assert detections == []

    def test_above_threshold_kept(self):
        backend = _make_backend(_fake_result("Thumb_Up", 0.85), gesture_min_conf=0.7)
        detections, *_ = backend.detect(_IMG)
        assert detections == [("thumbs_up", 0.85, "right")]

    def test_keypoints_preserved_when_gesture_dropped(self):
        """Filtered-out gesture must still record hand keypoints so the
        OK-circle override and wave detector keep working."""
        backend = _make_backend(_fake_result("Open_Palm", 0.6, hand="Right"),
                                gesture_min_conf=0.7)
        detections, lh_kps, lh_scores, rh_kps, rh_scores = backend.detect(_IMG)
        assert detections == []
        assert float(rh_scores[0]) > 0.0          # right hand seen
        assert float(np.sum(np.abs(rh_kps))) > 0  # pixel coords filled

    def test_unknown_still_dropped_regardless_of_conf(self):
        backend = _make_backend(_fake_result("Unknown", 0.99), gesture_min_conf=0.0)
        detections, *_ = backend.detect(_IMG)
        assert detections == []


# ── 6/9 HITL majority_vote min_votes (Roy 拍板, demo-blocking) ─────────────
# 投票贏家票數須 >= min_votes（demo N3）— 防單幀誤判直接奪冠。

class TestMajorityVoteMinVotes:
    def test_default_single_vote_wins(self):
        """min_votes 預設 1 = 現行行為（單票即可奪冠）。"""
        from vision_perception.voting import majority_vote
        assert majority_vote([None, None, "ok", None]) == "ok"

    def test_empty_buffer_returns_none(self):
        from vision_perception.voting import majority_vote
        assert majority_vote([]) is None

    def test_all_none_returns_none(self):
        from vision_perception.voting import majority_vote
        assert majority_vote([None] * 10, min_votes=3) is None

    def test_winner_below_min_votes_rejected(self):
        from vision_perception.voting import majority_vote
        buf = [None] * 8 + ["ok"] * 2
        assert majority_vote(buf, min_votes=3) is None

    def test_winner_meets_min_votes(self):
        from vision_perception.voting import majority_vote
        buf = [None] * 7 + ["ok"] * 3
        assert majority_vote(buf, min_votes=3) == "ok"

    def test_min_votes_counts_winner_not_total(self):
        """palm×2 + fist×3：總票 5 但贏家 fist 只有 3 票 → min_votes=4 否決。"""
        from vision_perception.voting import majority_vote
        buf = ["palm", "palm", "fist", "fist", "fist"]
        assert majority_vote(buf, min_votes=3) == "fist"
        assert majority_vote(buf, min_votes=4) is None

    def test_min_votes_below_one_clamped(self):
        from vision_perception.voting import majority_vote
        assert majority_vote(["ok"], min_votes=0) == "ok"
        assert majority_vote(["ok"], min_votes=-5) == "ok"

    def test_signature_default_is_one(self):
        from vision_perception.voting import majority_vote
        sig = inspect.signature(majority_vote)
        assert sig.parameters["min_votes"].default == 1
