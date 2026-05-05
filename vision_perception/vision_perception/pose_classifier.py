# vision_perception/vision_perception/pose_classifier.py
"""Single-frame pose classifier.

Pure Python — no ROS2, no camera, no GPU.
Input: COCO body keypoints (17, 2) + scores (17,) + optional bbox_ratio.
Output: (pose_name, confidence) or (None, 0.0).

Classification order (first match wins):
1. fallen (safety priority)
2. standing
3. akimbo (雙手叉腰 — wrists at hips, elbows externally bent)
4. knee_kneel (單膝跪地 — one knee bent, that knee at/below hip y)
5. bending (trunk forward, legs straight)
6. crouching
7. sitting
8. None (ambiguous)
"""
from __future__ import annotations

import math

import numpy as np

POSES = (
    "standing",
    "sitting",
    "crouching",
    "fallen",
    "bending",
    "akimbo",
    "knee_kneel",
)

# COCO body keypoint indices
_L_SHOULDER, _R_SHOULDER = 5, 6
_L_ELBOW, _R_ELBOW = 7, 8
_L_WRIST, _R_WRIST = 9, 10
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

    # 2. standing — checked FIRST among non-safety so we can detect akimbo
    #    (which is a standing variant) below without re-running standing logic.
    is_standing = hip_angle > 155 and knee_angle > 155

    # 3. akimbo (雙手叉腰) — only meaningful while otherwise standing.
    #    Both wrists land near the hip line + elbows bent outward.
    #    Requires KP scores for wrist + elbow + hip.
    if is_standing and _is_akimbo(body_kps, body_scores, hip):
        return "akimbo", avg_score

    if is_standing:
        return "standing", avg_score

    # 4. knee_kneel (單膝跪地) — one knee deeply bent + that knee y >= hip y,
    #    other leg straighter. Run BEFORE crouching/sitting which would
    #    otherwise swallow it (both knees bent). bbox_ratio guard avoids
    #    misclassifying lying/fallen as kneel.
    if (bbox_ratio is None or bbox_ratio <= 1.0):
        kneel = _is_knee_kneel(body_kps, body_scores, hip)
        if kneel:
            return "knee_kneel", avg_score

    # 5. bending (trunk leaning forward, legs mostly straight)
    if (trunk_angle > 35 and hip_angle < 140 and knee_angle > 130
            and (bbox_ratio is None or bbox_ratio <= 1.0)):
        return "bending", avg_score

    # 6. crouching (relaxed thresholds + forward lean guard)
    if hip_angle < 145 and knee_angle < 145 and trunk_angle > 10:
        return "crouching", avg_score

    # 7. sitting (wider hip range, upright trunk)
    if 100 < hip_angle < 150 and trunk_angle < 35:
        return "sitting", avg_score

    # 8. ambiguous
    return None, 0.0


def _is_akimbo(
    body_kps: np.ndarray,
    body_scores: np.ndarray,
    hip_mid: np.ndarray,
) -> bool:
    """Detect 雙手叉腰 (hands on hips, both arms triangular).

    Heuristic:
      • both wrists within `hip_width * 0.6` of their respective hip
      • both wrists at or above hip Y (not dangling at sides)
      • both elbows bent (shoulder-elbow-wrist angle 60..130°)
      • all 6 KP scores ≥ _MIN_SCORE so we don't trigger on partial body
    """
    needed = (_L_SHOULDER, _R_SHOULDER, _L_ELBOW, _R_ELBOW,
              _L_WRIST, _R_WRIST, _L_HIP, _R_HIP)
    for idx in needed:
        if body_scores[idx] < _MIN_SCORE:
            return False

    hip_width = float(np.linalg.norm(body_kps[_L_HIP] - body_kps[_R_HIP]))
    if hip_width < 1e-6:
        return False
    threshold = hip_width * 0.6

    for wrist_idx, hip_idx, shoulder_idx, elbow_idx in (
        (_L_WRIST, _L_HIP, _L_SHOULDER, _L_ELBOW),
        (_R_WRIST, _R_HIP, _R_SHOULDER, _R_ELBOW),
    ):
        wrist = body_kps[wrist_idx]
        hip_pt = body_kps[hip_idx]
        # 1. proximity to hip
        if float(np.linalg.norm(wrist - hip_pt)) > threshold:
            return False
        # 2. wrist not significantly below hip (hands on hips, not dangling).
        #    image y grows downward → wrist.y > hip.y * 1.15 means hanging.
        if wrist[1] > hip_pt[1] + threshold * 0.5:
            return False
        # 3. elbow externally bent
        elbow_angle = _angle_deg(body_kps[shoulder_idx],
                                  body_kps[elbow_idx],
                                  body_kps[wrist_idx])
        if not (60.0 <= elbow_angle <= 135.0):
            return False
    # 4. wrists higher than hip midpoint (extra guard against arms-down)
    avg_wrist_y = (body_kps[_L_WRIST][1] + body_kps[_R_WRIST][1]) * 0.5
    if avg_wrist_y > hip_mid[1] + threshold * 0.4:
        return False
    return True


def _is_knee_kneel(
    body_kps: np.ndarray,
    body_scores: np.ndarray,
    hip_mid: np.ndarray,
) -> bool:
    """Detect 單膝跪地 (one knee on the ground).

    Heuristic (image y grows downward):
      • exactly ONE knee qualifies as "kneeling":
          - that knee's y is at or below hip y (knee dropped to floor)
          - that knee's hip-knee-ankle angle < 100° (deeply bent)
      • the OTHER leg is "standing":
          - knee angle > 130°
      • all 6 leg KP scores ≥ _MIN_SCORE
    """
    needed = (_L_HIP, _R_HIP, _L_KNEE, _R_KNEE, _L_ANKLE, _R_ANKLE)
    for idx in needed:
        if body_scores[idx] < _MIN_SCORE:
            return False

    legs = []
    for hip_idx, knee_idx, ankle_idx in (
        (_L_HIP, _L_KNEE, _L_ANKLE),
        (_R_HIP, _R_KNEE, _R_ANKLE),
    ):
        knee = body_kps[knee_idx]
        knee_angle = _angle_deg(body_kps[hip_idx], knee, body_kps[ankle_idx])
        knee_below_hip = knee[1] >= hip_mid[1] - 4.0  # small tolerance
        legs.append({
            "knee": knee,
            "angle": knee_angle,
            "below_hip": knee_below_hip,
        })

    kneeling = [leg for leg in legs
                if leg["below_hip"] and leg["angle"] < 100.0]
    standing = [leg for leg in legs if leg["angle"] > 130.0]
    return len(kneeling) == 1 and len(standing) == 1
