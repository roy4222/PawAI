# vision_perception/vision_perception/gesture_classifier.py
"""Single-frame static gesture classifier.

Pure Python — no ROS2, no camera, no GPU.
Input: COCO-WholeBody hand keypoints (21, 2) + scores (21,).
Output: (gesture_name, confidence) or (None, 0.0).

Does NOT return "wave" — wave requires temporal analysis done by the Node layer.
"""
from __future__ import annotations

import numpy as np

STATIC_GESTURES = ("stop", "point", "fist")

# COCO-WholeBody hand keypoint indices
_WRIST = 0
_FINGERTIPS = (4, 8, 12, 16, 20)  # thumb, index, middle, ring, pinky
_INDEX_TIP = 8
_THUMB_TIP = 4
_MCPS = (5, 9, 13, 17)  # index, middle, ring, pinky MCP

# Thresholds (pixel-space, tuned for ~640x480 input)
_MIN_SCORE = 0.2          # minimum average keypoint confidence
_EXTEND_RATIO = 1.8       # fingertip-to-wrist / MCP-to-wrist ratio for "extended"
_CURL_RATIO = 0.8         # fingertip-to-wrist / MCP-to-wrist ratio for "curled"

# OK gesture (MOC §3 group 1) — thumb tip + index tip touch (forming a circle),
# while middle/ring/pinky are extended (or relaxed). MediaPipe Gesture
# Recognizer doesn't ship OK natively, so we run this geometric check on top
# of the recognizer output and override the label when matched.
_OK_TOUCH_RATIO = 0.30    # thumb-tip ↔ index-tip distance / hand width ≤ this


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _finger_extended(kps: np.ndarray, tip_idx: int, mcp_idx: int, wrist: np.ndarray) -> bool:
    """True if fingertip is significantly farther from wrist than its MCP joint."""
    tip_dist = _dist(kps[tip_idx], wrist)
    mcp_dist = _dist(kps[mcp_idx], wrist)
    if mcp_dist < 1e-6:
        return tip_dist > 10.0  # fallback: absolute distance
    return tip_dist / mcp_dist > _EXTEND_RATIO


def _finger_curled(kps: np.ndarray, tip_idx: int, mcp_idx: int, wrist: np.ndarray) -> bool:
    """True if fingertip is close to or behind its MCP joint relative to wrist."""
    tip_dist = _dist(kps[tip_idx], wrist)
    mcp_dist = _dist(kps[mcp_idx], wrist)
    if mcp_dist < 1e-6:
        return tip_dist < 10.0
    return tip_dist / mcp_dist < _CURL_RATIO


def classify_gesture(
    hand_kps: np.ndarray,
    hand_scores: np.ndarray,
    min_score: float | None = None,
) -> tuple[str | None, float]:
    """Single-frame static gesture classification.

    Args:
        min_score: Override for _MIN_SCORE. Pass from ROS parameter for runtime tuning.

    Returns:
        ("stop" | "point" | "fist", confidence) or (None, 0.0).
    """
    if hand_kps.shape != (21, 2) or hand_scores.shape != (21,):
        return None, 0.0

    threshold = min_score if min_score is not None else _MIN_SCORE
    avg_score = float(np.mean(hand_scores))
    if avg_score < threshold:
        return None, 0.0

    wrist = hand_kps[_WRIST]

    # Check finger extension state (index through pinky; thumb uses tip only)
    # MCP pairs: (tip, mcp) — thumb has no MCP in our check, use simple distance
    finger_pairs = list(zip(_FINGERTIPS[1:], _MCPS))  # index, middle, ring, pinky
    extended = [_finger_extended(hand_kps, t, m, wrist) for t, m in finger_pairs]
    curled = [_finger_curled(hand_kps, t, m, wrist) for t, m in finger_pairs]

    # Thumb: extended if tip is far from wrist
    thumb_dist = _dist(hand_kps[4], wrist)
    avg_mcp_dist = np.mean([_dist(hand_kps[m], wrist) for m in _MCPS])
    thumb_extended = thumb_dist > avg_mcp_dist * 1.2 if avg_mcp_dist > 1e-6 else thumb_dist > 10.0

    n_extended = sum(extended) + (1 if thumb_extended else 0)
    n_curled = sum(curled)

    # stop: all 5 fingers extended (or at least 4 + thumb)
    if n_extended >= 4 and thumb_extended:
        return "stop", avg_score

    # point: only index extended, rest curled
    if extended[0] and sum(curled[1:]) >= 2 and not extended[1] and not extended[2]:
        return "point", avg_score

    # fist: all 4 non-thumb fingers curled
    if n_curled >= 3 and not any(extended):
        return "fist", avg_score

    return None, 0.0


def detect_ok_circle(
    hand_kps: np.ndarray,
    hand_scores: np.ndarray,
    min_score: float | None = None,
) -> tuple[bool, float]:
    """Detect MOC OK 👌 gesture (thumb-index pinch + other fingers free).

    Geometric rule (independent of MediaPipe Gesture Recognizer output):
      • thumb tip (4) and index tip (8) within `_OK_TOUCH_RATIO * hand_width`
      • middle (12), ring (16), pinky (20) NOT curled (extended or relaxed)

    Hand width is approximated by the wrist→middle-MCP distance (a stable
    reference that scales with how far the hand is from camera).

    Args:
        hand_kps: (21, 2) pixel coords (COCO-WholeBody / MediaPipe Hands).
        hand_scores: (21,) per-keypoint confidence.
        min_score: override for _MIN_SCORE.

    Returns:
        (is_ok, confidence). confidence is the inverse of the touch
        distance ratio (1.0 = fingers touching, ~0 at threshold).
        Returns (False, 0.0) if input invalid or below score threshold.
    """
    if hand_kps.shape != (21, 2) or hand_scores.shape != (21,):
        return False, 0.0

    threshold = min_score if min_score is not None else _MIN_SCORE
    avg_score = float(np.mean(hand_scores))
    if avg_score < threshold:
        return False, 0.0

    wrist = hand_kps[_WRIST]
    middle_mcp = hand_kps[9]
    hand_width = _dist(wrist, middle_mcp)
    if hand_width < 1e-6:
        return False, 0.0

    # Thumb-index touch check
    thumb_tip = hand_kps[_THUMB_TIP]
    index_tip = hand_kps[_INDEX_TIP]
    touch_dist = _dist(thumb_tip, index_tip)
    touch_ratio = touch_dist / hand_width
    if touch_ratio > _OK_TOUCH_RATIO:
        return False, 0.0

    # Other 3 fingers should NOT be all curled (avoid clash with fist+thumb_up)
    finger_pairs = list(zip(_FINGERTIPS[2:], _MCPS[1:]))  # middle, ring, pinky
    n_other_curled = sum(_finger_curled(hand_kps, t, m, wrist) for t, m in finger_pairs)
    if n_other_curled >= 3:
        # Closed fist with thumb touching index = not OK, keep as fist
        return False, 0.0

    # Confidence: 1.0 when fingers fully touching, drop linearly to 0 at threshold
    confidence = max(0.0, 1.0 - touch_ratio / _OK_TOUCH_RATIO)
    return True, float(min(avg_score, confidence))
