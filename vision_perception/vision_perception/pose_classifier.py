# vision_perception/vision_perception/pose_classifier.py
"""Single-frame pose classifier.

Pure Python — no ROS2, no camera, no GPU.
Input: COCO body keypoints (17, 2) + scores (17,) + optional bbox_ratio.
Output: (pose_name, confidence) or (None, 0.0).

Classification order (first match wins):
1. fallen (safety priority)
2. standing
3. bending (trunk forward, legs straight)
4. crouching
5. sitting
6. None (ambiguous)
"""
from __future__ import annotations

import math

import numpy as np

POSES = ("standing", "sitting", "crouching", "fallen", "bending")

# COCO body keypoint indices
_L_SHOULDER, _R_SHOULDER = 5, 6
_L_HIP, _R_HIP = 11, 12
_L_KNEE, _R_KNEE = 13, 14
_L_ANKLE, _R_ANKLE = 15, 16

_MIN_SCORE = 0.2


def _angle_deg(a: np.ndarray, vertex: np.ndarray, b: np.ndarray) -> float:
    """Angle at vertex in degrees, formed by vectors vertex->a and vertex->b."""
    va = a - vertex
    vb = b - vertex
    cos_val = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-8)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    return float(math.degrees(math.acos(cos_val)))


def _trunk_angle_deg(shoulder: np.ndarray, hip: np.ndarray) -> float:
    """Angle between shoulder-hip line and vertical (downward Y direction)."""
    vec = shoulder - hip  # points upward from hip to shoulder
    # Vertical reference: straight up = (0, -1) in image coords
    vertical = np.array([0.0, -1.0])
    cos_val = np.dot(vec, vertical) / (np.linalg.norm(vec) + 1e-8)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    return float(math.degrees(math.acos(cos_val)))


def _mid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2.0


def classify_pose(
    body_kps: np.ndarray,
    body_scores: np.ndarray,
    bbox_ratio: float | None = None,
) -> tuple[str | None, float]:
    """Single-frame pose classification.

    Args:
        body_kps: (17, 2) COCO body keypoints.
        body_scores: (17,) confidence per keypoint.
        bbox_ratio: width/height of person bounding box (from Node layer).

    Returns:
        (pose_name, confidence) or (None, 0.0).
    """
    if body_kps.shape != (17, 2) or body_scores.shape != (17,):
        return None, 0.0

    avg_score = float(np.mean(body_scores))
    if avg_score < _MIN_SCORE:
        return None, 0.0

    # Compute midpoints for left/right averaging
    shoulder = _mid(body_kps[_L_SHOULDER], body_kps[_R_SHOULDER])
    hip = _mid(body_kps[_L_HIP], body_kps[_R_HIP])
    knee = _mid(body_kps[_L_KNEE], body_kps[_R_KNEE])
    ankle = _mid(body_kps[_L_ANKLE], body_kps[_R_ANKLE])

    # Guard: if key joints are at origin (all zeros), bail out
    if np.linalg.norm(hip) < 1e-6 and np.linalg.norm(shoulder) < 1e-6:
        return None, 0.0

    hip_angle = _angle_deg(shoulder, hip, knee)
    knee_angle = _angle_deg(hip, knee, ankle)
    trunk_angle = _trunk_angle_deg(shoulder, hip)

    # 1. fallen (safety priority)
    #    Extra guard: vertical_ratio = (hip_y - shoulder_y) / torso_length
    #    Standing frontal ≈ 0.85-1.0; lying flat ≈ 0.0-0.17
    #    Threshold 0.4 prevents frontal-standing misdetection at any distance
    torso_len = float(np.linalg.norm(hip - shoulder))
    vertical_ratio = (hip[1] - shoulder[1]) / torso_len if torso_len > 1e-6 else 1.0
    if (bbox_ratio is not None and bbox_ratio > 1.0
            and trunk_angle > 60
            and vertical_ratio < 0.4):
        return "fallen", avg_score

    # 2. standing
    if hip_angle > 155 and knee_angle > 155:
        return "standing", avg_score

    # 3. bending (trunk leaning forward, legs mostly straight)
    if (trunk_angle > 35 and hip_angle < 140 and knee_angle > 130
            and (bbox_ratio is None or bbox_ratio <= 1.0)):
        return "bending", avg_score

    # 4. crouching (relaxed thresholds + forward lean guard)
    if hip_angle < 145 and knee_angle < 145 and trunk_angle > 10:
        return "crouching", avg_score

    # 5. sitting (wider hip range, upright trunk)
    if 100 < hip_angle < 150 and trunk_angle < 35:
        return "sitting", avg_score

    # 6. ambiguous
    return None, 0.0
