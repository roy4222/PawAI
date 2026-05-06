# vision_perception/vision_perception/pose_classifier.py
"""Single-frame pose classifier.

Pure Python — no ROS2, no camera, no GPU.
Input: COCO body keypoints (17, 2) + scores (17,) + optional bbox_ratio.
Output: (pose_name, confidence) or (None, 0.0).

Classification order (first match wins):
1. fallen           (safety priority — vertical_ratio gates against false positive)
2. standing / akimbo (akimbo is a standing variant, tested first)
3. knee_kneel       (must precede sitting/crouching, otherwise swallowed)
4. sitting          (y-geometry; must precede crouching/bending)
5. crouching
6. bending
7. None
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
        body_kps: (17, 2) COCO body keypoints in pixel coords (image y grows down).
        body_scores: (17,) confidence per keypoint.
        bbox_ratio: width/height of person bounding box (from Node layer).
            Used only as a fallen confidence bonus, not as a gating condition.

    Returns:
        (pose_name, confidence) or (None, 0.0).
    """
    if body_kps.shape != (17, 2) or body_scores.shape != (17,):
        return None, 0.0

    avg_score = float(np.mean(body_scores))
    if avg_score < _MIN_SCORE:
        return None, 0.0

    shoulder = _mid(body_kps[_L_SHOULDER], body_kps[_R_SHOULDER])
    hip = _mid(body_kps[_L_HIP], body_kps[_R_HIP])
    knee = _mid(body_kps[_L_KNEE], body_kps[_R_KNEE])
    ankle = _mid(body_kps[_L_ANKLE], body_kps[_R_ANKLE])

    # Guard: if key joints are at origin (all zeros), bail out.
    if np.linalg.norm(hip) < 1e-6 and np.linalg.norm(shoulder) < 1e-6:
        return None, 0.0

    hip_angle = _angle_deg(shoulder, hip, knee)
    knee_angle = _angle_deg(hip, knee, ankle)
    trunk_angle = _trunk_angle_deg(shoulder, hip)

    torso_len = float(np.linalg.norm(hip - shoulder))
    # vertical_ratio ≈ 1.0 when standing/upright, ≈ 0 when lying flat.
    # Equivalent to "shoulder-hip y delta / torso length" — guards fallen
    # against sitting/bending false positives without requiring straight legs
    # (so curled fall poses, e.g. elderly with bent knees, are still caught).
    vertical_ratio = (hip[1] - shoulder[1]) / torso_len if torso_len > 1e-6 else 1.0

    # 1. fallen (safety priority).
    #    Primary gate: trunk near horizontal AND torso projection vertical small.
    #    bbox_ratio > 1.0 only adds a small confidence bonus, not a hard gate —
    #    keypoint-derived bbox can be < 1.0 for curled-up fallen poses.
    #
    #    Deep-bending guard: when bbox isn't wide AND the lower body
    #    (hip→ankle vector) is still pointing nearly straight down, this is
    #    a deep bend / toe-touch, not a fall. Skip fallen and fall through
    #    to bending. This guard does NOT trigger when bbox_ratio > 1.0
    #    (truly horizontal silhouette) so real fallen-with-spread-arms still
    #    classifies correctly.
    if trunk_angle > 60 and 0.0 <= vertical_ratio < 0.4:
        # Per-keypoint sanity gate: MediaPipe at awkward viewpoints (akimbo,
        # half-kneel, partial body in frame) often produces hallucinated
        # shoulder/hip positions where shoulders read BELOW hips. We require
        # the four torso landmarks to have decent visibility before trusting
        # a fallen verdict — otherwise drop through to the rest of the
        # classifier (will most likely return None, letting the buffer hold).
        torso_visibility = float(np.mean([
            body_scores[_L_SHOULDER], body_scores[_R_SHOULDER],
            body_scores[_L_HIP], body_scores[_R_HIP],
        ]))
        if torso_visibility >= 0.5:
            # Deep-bending guard: when bbox isn't wide AND the lower body
            # (hip→ankle vector) is still pointing nearly straight down, this
            # is a deep bend / toe-touch, not a fall. Skip fallen and fall
            # through to bending. This guard does NOT trigger when
            # bbox_ratio > 1.0 (truly horizontal silhouette) so real
            # fallen-with-spread-arms still classifies correctly.
            is_deep_bending = False
            if bbox_ratio is None or bbox_ratio <= 1.0:
                lower_body_vec = ankle - hip
                lb_norm = float(np.linalg.norm(lower_body_vec))
                if lb_norm > 0.5 * torso_len:
                    cos_down = float(lower_body_vec[1]) / lb_norm  # +1 = down
                    lower_body_angle = math.degrees(
                        math.acos(np.clip(cos_down, -1.0, 1.0))
                    )
                    if lower_body_angle < 30.0:
                        is_deep_bending = True
            if not is_deep_bending:
                bonus = 0.05 if (bbox_ratio is not None and bbox_ratio > 1.0) else 0.0
                return "fallen", float(min(avg_score + bonus, 1.0))

    # 2. standing — checked before akimbo so akimbo (standing variant) can branch.
    is_standing = hip_angle > 155 and knee_angle > 155

    if is_standing and _is_akimbo(body_kps, body_scores, hip):
        return "akimbo", avg_score

    if is_standing:
        return "standing", avg_score

    # 3. knee_kneel — must precede sitting/crouching, both of which would
    #    otherwise swallow it. bbox_ratio guard avoids misclassifying lying.
    if (bbox_ratio is None or bbox_ratio <= 1.0):
        if _is_knee_kneel(body_kps, body_scores, hip, torso_len):
            return "knee_kneel", avg_score

    # 4. sitting — y-geometry (the previous angle-only test overlapped with
    #    bending/crouching). Image y grows downward.
    #    Requirements:
    #      - trunk upright
    #      - hip ≈ knee in y (high chair) OR knee above hip (low stool)
    #      - hip clearly above ankle (seated, not standing)
    #      - knee actually bent
    if torso_len > 1e-6:
        hip_knee_y_diff = abs(hip[1] - knee[1])
        ankle_above_hip = ankle[1] - hip[1]
        is_seated_geometry = (
            (hip_knee_y_diff < 0.12 * torso_len or knee[1] < hip[1])
            and ankle_above_hip > 0.5 * torso_len
        )
        if (trunk_angle < 35
                and is_seated_geometry
                and knee_angle < 145):
            return "sitting", avg_score

    # 5. crouching (relaxed thresholds + forward-lean guard)
    if hip_angle < 145 and knee_angle < 145 and trunk_angle > 10:
        return "crouching", avg_score

    # 6. bending (trunk leaning forward, legs mostly straight).
    #    sitting now eats upright cases; remaining trunk-forward + straight-legs
    #    is bending. Wide bbox excluded so fallen-like silhouettes don't slip in.
    if (trunk_angle > 30
            and knee_angle > 130
            and hip_angle < 160
            and (bbox_ratio is None or bbox_ratio <= 1.0)):
        return "bending", avg_score

    # 7. ambiguous
    return None, 0.0


def _is_akimbo(
    body_kps: np.ndarray,
    body_scores: np.ndarray,
    hip_mid: np.ndarray,
) -> bool:
    """Detect 雙手叉腰 (hands on hips, both arms triangular).

    Primary signal is **elbow bowed outward + elbow at hip-level y**, NOT
    wrist position. Community trap (BleedAI / MediaPipe issue #4462):
    when hands rest behind the body MediaPipe wrist visibility drops and
    landmarks drift; relying on wrist position misses real akimbo.

    Heuristic:
      • shoulder + elbow + hip visibility ≥ 0.5 (per practitioner gate;
        higher than _MIN_SCORE because these landmarks are critical)
      • elbow bowed outward beyond shoulder by hip_width * 0.4 on both sides
      • avg elbow y is below shoulder y AND not far below hip y
      • when wrist is visible (>= 0.3): elbow angle in [60°, 140°]
        (akimbo elbow is ~90°; loose bound covers natural variation)
    """
    # Phase 1: critical visibility gate.
    needed = (_L_SHOULDER, _R_SHOULDER, _L_ELBOW, _R_ELBOW, _L_HIP, _R_HIP)
    for idx in needed:
        if body_scores[idx] < 0.5:
            return False

    hip_width = float(np.linalg.norm(body_kps[_L_HIP] - body_kps[_R_HIP]))
    if hip_width < 1e-6:
        return False

    l_shoulder = body_kps[_L_SHOULDER]
    r_shoulder = body_kps[_R_SHOULDER]
    l_elbow = body_kps[_L_ELBOW]
    r_elbow = body_kps[_R_ELBOW]

    # Phase 2: elbows bowed outward — image L is smaller x, R is larger x.
    elbow_out_threshold = hip_width * 0.4
    l_elbow_out = (l_shoulder[0] - l_elbow[0]) > elbow_out_threshold
    r_elbow_out = (r_elbow[0] - r_shoulder[0]) > elbow_out_threshold
    if not (l_elbow_out and r_elbow_out):
        return False

    # Phase 3: elbow y level — between shoulder and "hip + half hip_width".
    # Filters T-pose (elbow ≈ shoulder y) and high-arm poses.
    shoulder_y = (l_shoulder[1] + r_shoulder[1]) * 0.5
    avg_elbow_y = (l_elbow[1] + r_elbow[1]) * 0.5
    if avg_elbow_y < shoulder_y:
        return False
    if avg_elbow_y > hip_mid[1] + hip_width * 0.5:
        return False

    # Phase 4: when wrist visible, validate elbow angle is bent.
    # Wrist invisibility is itself OK — that's the akimbo trap.
    for wrist_idx, shoulder_idx, elbow_idx in (
        (_L_WRIST, _L_SHOULDER, _L_ELBOW),
        (_R_WRIST, _R_SHOULDER, _R_ELBOW),
    ):
        if body_scores[wrist_idx] >= 0.3:
            elbow_angle = _angle_deg(body_kps[shoulder_idx],
                                      body_kps[elbow_idx],
                                      body_kps[wrist_idx])
            if not (60.0 <= elbow_angle <= 140.0):
                return False
    return True


def _is_knee_kneel(
    body_kps: np.ndarray,
    body_scores: np.ndarray,
    hip_mid: np.ndarray,
    torso_len: float,
) -> bool:
    """Detect 單膝跪地 (one knee on the ground).

    Score requirements are split: hips + knees are mandatory (need them to
    pick the kneel side); the **standing-side ankle is mandatory** (used to
    verify foot planted); the **kneel-side ankle is optional** — a low score
    is itself signal that the foot is hidden under the body / occluded by
    floor and we trust the kneel-side knee position alone.

    Heuristic (image y grows downward):
      • two knees must differ in y by >= 0.07 * torso_len (one knee on floor)
      • kneeling side (lower knee, larger y):
          - if ankle visible: hip-knee-ankle angle < 140°, OR
            ankle within 0.08 * torso_len of the knee y (foot flat)
          - if ankle hidden (score < _MIN_SCORE): treat as kneel
      • standing side:
          - knee_angle > 130°, OR
          - "sitting-like support": hip-knee y diff < 0.12 * torso_len AND
            knee_angle in (70, 130) AND ankle below knee (foot planted)
    """
    # Phase 1: hips + knees mandatory — needed to determine kneel side.
    # Visibility 0.5 (per practitioner gate) — these are critical landmarks.
    for idx in (_L_HIP, _R_HIP, _L_KNEE, _R_KNEE):
        if body_scores[idx] < 0.5:
            return False

    if torso_len < 1e-6:
        return False

    l_knee = body_kps[_L_KNEE]
    r_knee = body_kps[_R_KNEE]

    # Two-knee y diff must be material — distinguishes one-knee kneeling
    # from a deep crouch where both knees drop together.
    knee_y_diff = abs(l_knee[1] - r_knee[1])
    if knee_y_diff < 0.07 * torso_len:
        return False

    # Lower y-coord (larger value) = closer to floor in image space.
    if l_knee[1] > r_knee[1]:
        kneel_hip_idx, kneel_knee_idx, kneel_ankle_idx = _L_HIP, _L_KNEE, _L_ANKLE
        stand_hip_idx, stand_knee_idx, stand_ankle_idx = _R_HIP, _R_KNEE, _R_ANKLE
    else:
        kneel_hip_idx, kneel_knee_idx, kneel_ankle_idx = _R_HIP, _R_KNEE, _R_ANKLE
        stand_hip_idx, stand_knee_idx, stand_ankle_idx = _L_HIP, _L_KNEE, _L_ANKLE

    # Phase 2: standing-side ankle mandatory (need it for support check).
    if body_scores[stand_ankle_idx] < 0.5:
        return False

    kneel_knee = body_kps[kneel_knee_idx]
    stand_knee = body_kps[stand_knee_idx]
    stand_ankle = body_kps[stand_ankle_idx]

    # Kneel-side ankle: visibility-gated.
    # Per fall-detection / yoga-pose research, the strongest kneel-vs-lunge
    # discriminator is "kneel-side ankle.y ≈ knee.y" (shin flat on ground).
    # Threshold loosened to 0.20 * torso_len (was 0.08) to match real
    # MediaPipe noise — synthetic-only thresholds were too strict.
    if body_scores[kneel_ankle_idx] < 0.5:
        # Hidden ankle = often kneeling with foot tucked under body.
        kneel_ok = True
    else:
        kneel_ankle = body_kps[kneel_ankle_idx]
        kneel_angle = _angle_deg(body_kps[kneel_hip_idx], kneel_knee, kneel_ankle)
        ankle_near_knee = abs(kneel_ankle[1] - kneel_knee[1]) < 0.20 * torso_len
        # Either signal: shin flat (Y close), OR knee deeply bent (angle small).
        kneel_ok = ankle_near_knee or kneel_angle < 130.0

    stand_angle = _angle_deg(body_kps[stand_hip_idx], stand_knee, stand_ankle)
    standing_ok = stand_angle > 130.0
    if not standing_ok:
        # Sitting-like support leg: hip≈knee in y, knee bent moderately,
        # ankle planted below knee. Covers half-kneeling postures where
        # the front leg looks like a sitting leg.
        hip_knee_y_diff = abs(body_kps[stand_hip_idx][1] - stand_knee[1])
        sitting_like = (hip_knee_y_diff < 0.12 * torso_len
                        and 70.0 < stand_angle < 130.0
                        and stand_ankle[1] > stand_knee[1])
        standing_ok = sitting_like

    return bool(kneel_ok and standing_ok)
