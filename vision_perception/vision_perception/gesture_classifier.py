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
_MCPS = (5, 9, 13, 17)  # index, middle, ring, pinky MCP

# Thresholds (pixel-space, tuned for ~640x480 input)
_MIN_SCORE = 0.2          # minimum average keypoint confidence
_EXTEND_RATIO = 1.8       # fingertip-to-wrist / MCP-to-wrist ratio for "extended"
_CURL_RATIO = 0.8         # fingertip-to-wrist / MCP-to-wrist ratio for "curled"


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
