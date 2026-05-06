# vision_perception/test/test_pose_classifier.py
"""Tests for pose_classifier — pure Python, no ROS2."""
import math
import numpy as np


def _body_from_angles(hip_angle_deg: float, knee_angle_deg: float,
                      trunk_angle_deg: float) -> np.ndarray:
    """Generate (17, 2) body keypoints that produce the given angles.
    Uses a simplified stick figure: shoulder at top, hip at middle, knee/ankle below.
    """
    kps = np.zeros((17, 2), dtype=np.float32)

    # Fixed reference: hip at (200, 300)
    hip = np.array([200.0, 300.0])
    kps[11] = hip  # left_hip
    kps[12] = hip + [20, 0]  # right_hip

    # Shoulder: trunk_angle from vertical
    trunk_rad = math.radians(trunk_angle_deg)
    shoulder_offset = np.array([math.sin(trunk_rad) * 100, -math.cos(trunk_rad) * 100])
    kps[5] = hip + shoulder_offset  # left_shoulder
    kps[6] = hip + shoulder_offset + [20, 0]  # right_shoulder

    # Knee: hip_angle from shoulder-hip line
    hip_rad = math.radians(180 - hip_angle_deg)  # angle at hip joint
    knee_offset = np.array([math.sin(hip_rad + trunk_rad) * 80,
                            math.cos(hip_rad + trunk_rad) * 80])
    kps[13] = hip + knee_offset  # left_knee
    kps[14] = hip + knee_offset + [20, 0]  # right_knee

    # Ankle: knee_angle from hip-knee line
    knee_rad = math.radians(180 - knee_angle_deg)
    knee_to_hip_angle = math.atan2(knee_offset[1], knee_offset[0])
    ankle_offset = knee_offset + np.array([
        math.cos(knee_to_hip_angle + knee_rad) * 70,
        math.sin(knee_to_hip_angle + knee_rad) * 70,
    ])
    kps[15] = hip + ankle_offset  # left_ankle
    kps[16] = hip + ankle_offset + [20, 0]  # right_ankle

    # Nose above shoulder
    kps[0] = kps[5] + [10, -30]

    return kps


class TestClassifyPose:
    def test_standing(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=175, knee_angle_deg=175, trunk_angle_deg=5)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.4)
        assert pose == "standing"
        assert conf > 0.5

    def test_sitting(self):
        """Sitting now requires y-geometry: hip≈knee in y, ankle far below hip,
        upright trunk. The angle-only stick figure can't satisfy this, so use
        explicit keypoints reflecting a chair-sitting silhouette."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Upright torso
        kps[5] = [200, 200]    # L_SHOULDER
        kps[6] = [220, 200]    # R_SHOULDER
        kps[11] = [200, 300]   # L_HIP
        kps[12] = [220, 300]   # R_HIP
        # Hips and knees at roughly the same y (chair height)
        kps[13] = [260, 295]   # L_KNEE (same level as hip)
        kps[14] = [280, 295]   # R_KNEE
        # Ankles dropped down (shins vertical)
        kps[15] = [260, 380]   # L_ANKLE
        kps[16] = [280, 380]   # R_ANKLE
        kps[0] = [210, 170]    # NOSE
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose == "sitting"
        assert conf > 0.5

    def test_crouching(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=60, knee_angle_deg=60, trunk_angle_deg=40)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose == "crouching"
        assert conf > 0.5

    def test_fallen_horizontal(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=170, knee_angle_deg=170, trunk_angle_deg=80)
        scores = np.ones(17, dtype=np.float32) * 0.9
        # bbox wider than tall = horizontal body
        pose, conf = classify_pose(kps, scores, bbox_ratio=1.5)
        assert pose == "fallen"
        assert conf > 0.5

    def test_fallen_priority_over_standing(self):
        """fallen check runs before standing — even if angles look upright,
        bbox_ratio > 1.0 + trunk > 60deg = fallen."""
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=170, knee_angle_deg=170, trunk_angle_deg=70)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=1.3)
        assert pose == "fallen"

    def test_ambiguous_returns_none(self):
        from vision_perception.pose_classifier import classify_pose
        # Use direct keypoints to control exact angles.
        # Target: hip≈153, trunk≈3 → gap between standing(>155) and sitting(<150)
        # trunk < 10 → not crouching
        kps = np.zeros((17, 2), dtype=np.float32)
        kps[5] = [205, 200]   # l_shoulder (nearly straight above hip)
        kps[6] = [225, 200]
        kps[11] = [200, 300]  # l_hip
        kps[12] = [220, 300]
        kps[13] = [140, 400]  # l_knee (offset left → hip≈152°)
        kps[14] = [160, 400]
        kps[15] = [140, 500]  # l_ankle (straight down from knee)
        kps[16] = [160, 500]
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose is None
        assert conf == 0.0

    def test_zero_keypoints_returns_none(self):
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        scores = np.zeros(17, dtype=np.float32)
        pose, conf = classify_pose(kps, scores, bbox_ratio=None)
        assert pose is None

    def test_no_bbox_ratio_still_classifies(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=175, knee_angle_deg=175, trunk_angle_deg=5)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=None)
        assert pose == "standing"

    def test_bending(self):
        from vision_perception.pose_classifier import classify_pose
        # trunk forward 50°, hip bent 110°, legs straight 170°
        kps = _body_from_angles(hip_angle_deg=110, knee_angle_deg=170, trunk_angle_deg=50)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose == "bending"
        assert conf > 0.5

    def test_bending_vs_crouching(self):
        from vision_perception.pose_classifier import classify_pose
        # trunk forward but knees bent → not bending (knee < 130)
        kps = _body_from_angles(hip_angle_deg=110, knee_angle_deg=60, trunk_angle_deg=50)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose != "bending"

    def test_bending_vs_fallen(self):
        from vision_perception.pose_classifier import classify_pose
        # trunk forward + wide bbox → fallen takes priority
        kps = _body_from_angles(hip_angle_deg=110, knee_angle_deg=170, trunk_angle_deg=70)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=1.5)
        assert pose == "fallen"

    def test_frontal_standing_near_not_fallen(self):
        """Near distance (~1m): shoulders spread wide, bbox_ratio > 1.0,
        but shoulder clearly above hip → vertical_ratio high → NOT fallen."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Wide shoulders (frontal view, near camera)
        kps[5] = [100, 200]    # L_SHOULDER
        kps[6] = [350, 200]    # R_SHOULDER
        kps[11] = [180, 350]   # L_HIP
        kps[12] = [270, 350]   # R_HIP
        kps[13] = [180, 480]   # L_KNEE
        kps[14] = [270, 480]   # R_KNEE
        kps[15] = [180, 600]   # L_ANKLE
        kps[16] = [270, 600]   # R_ANKLE
        kps[0] = [225, 150]    # NOSE
        scores = np.ones(17, dtype=np.float32) * 0.9
        # bbox width=250, height=400 → ratio=0.625, but test with forced ratio
        pose, _ = classify_pose(kps, scores, bbox_ratio=1.25)
        assert pose != "fallen", "Frontal standing near camera must not be fallen"

    def test_frontal_standing_far_not_fallen(self):
        """Far distance (~3m): smaller keypoints but same proportions.
        vertical_ratio is scale-invariant → still NOT fallen."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Scaled-down version (far from camera)
        kps[5] = [290, 200]    # L_SHOULDER
        kps[6] = [370, 200]    # R_SHOULDER
        kps[11] = [310, 250]   # L_HIP
        kps[12] = [350, 250]   # R_HIP
        kps[13] = [310, 295]   # L_KNEE
        kps[14] = [350, 295]   # R_KNEE
        kps[15] = [310, 335]   # L_ANKLE
        kps[16] = [350, 335]   # R_ANKLE
        kps[0] = [330, 185]    # NOSE
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=1.1)
        assert pose != "fallen", "Frontal standing far from camera must not be fallen"

    def test_actual_fallen_still_detected(self):
        """Person lying flat: shoulder and hip at same Y level → fallen."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Lying horizontally: all joints at roughly same Y
        kps[5] = [100, 300]    # L_SHOULDER
        kps[6] = [140, 305]    # R_SHOULDER
        kps[11] = [250, 310]   # L_HIP
        kps[12] = [290, 308]   # R_HIP
        kps[13] = [370, 305]   # L_KNEE
        kps[14] = [410, 310]   # R_KNEE
        kps[15] = [470, 300]   # L_ANKLE
        kps[16] = [510, 305]   # R_ANKLE
        kps[0] = [60, 295]     # NOSE
        scores = np.ones(17, dtype=np.float32) * 0.9
        # Wide bbox (person lying across frame)
        pose, _ = classify_pose(kps, scores, bbox_ratio=2.5)
        assert pose == "fallen", "Person lying flat must be detected as fallen"

    # ── New tests (5/6 pose classifier improvements) ──────────────────

    def test_fallen_no_bbox_required(self):
        """fallen must trigger from trunk + vertical_ratio alone, even when
        bbox_ratio is None — keypoint-derived bbox can be unreliable for
        curled-up fallen poses."""
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=170, knee_angle_deg=170, trunk_angle_deg=80)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=None)
        assert pose == "fallen"

    def test_fallen_curled_legs_bent(self):
        """Old rule (bbox-gated) AND any future rule must NOT require straight
        legs for fallen — elderly often fall with knees flexed."""
        from vision_perception.pose_classifier import classify_pose
        # Trunk near horizontal, legs flexed at 90°, no bbox passed.
        kps = _body_from_angles(hip_angle_deg=90, knee_angle_deg=90, trunk_angle_deg=80)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=None)
        assert pose == "fallen"

    def test_sitting_not_fallen_when_curled(self):
        """A seated person leaning forward (trunk 40°, legs flexed) with
        bbox_ratio > 1.0 must NOT be classified as fallen — vertical_ratio
        keeps fallen out, even though bbox is wide."""
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=90, knee_angle_deg=90, trunk_angle_deg=40)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=1.1)
        assert pose != "fallen", "Curled sitting must not trigger fallen"
        # Geometry here matches crouching, not sitting (trunk 40° > 35°).
        assert pose in ("sitting", "crouching")

    def test_sitting_y_geometry(self):
        """Sitting recognised by hip≈knee y + ankle far below hip + upright
        trunk, even when knee is just slightly below hip (high chair)."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        kps[5] = [200, 200]    # L_SHOULDER
        kps[6] = [220, 200]    # R_SHOULDER
        kps[11] = [200, 300]   # L_HIP
        kps[12] = [220, 300]   # R_HIP
        # Knees just above hip in y (low stool)
        kps[13] = [255, 290]   # L_KNEE
        kps[14] = [275, 290]   # R_KNEE
        # Ankles below hip (shins angled forward and down)
        kps[15] = [260, 380]   # L_ANKLE
        kps[16] = [280, 380]   # R_ANKLE
        kps[0] = [210, 170]    # NOSE
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose == "sitting"

    def test_akimbo_basic(self):
        """雙手叉腰: wrists at hip y, elbows externally bent, otherwise standing."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Standing torso (legs straight, trunk vertical)
        kps[5] = [180, 200]    # L_SHOULDER
        kps[6] = [220, 200]    # R_SHOULDER
        kps[11] = [180, 300]   # L_HIP
        kps[12] = [220, 300]   # R_HIP
        kps[13] = [180, 400]   # L_KNEE
        kps[14] = [220, 400]   # R_KNEE
        kps[15] = [180, 500]   # L_ANKLE
        kps[16] = [220, 500]   # R_ANKLE
        kps[0] = [200, 170]    # NOSE
        # Akimbo arms: elbow bowed outward, wrist back at hip
        kps[7] = [140, 270]    # L_ELBOW (out left, slightly above hip)
        kps[8] = [260, 270]    # R_ELBOW (out right)
        kps[9] = [180, 300]    # L_WRIST (on L_HIP)
        kps[10] = [220, 300]   # R_WRIST (on R_HIP)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose == "akimbo"

    def test_akimbo_arms_dangling(self):
        """Same standing torso but arms hanging down → standing, NOT akimbo."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        kps[5] = [180, 200]
        kps[6] = [220, 200]
        kps[11] = [180, 300]
        kps[12] = [220, 300]
        kps[13] = [180, 400]
        kps[14] = [220, 400]
        kps[15] = [180, 500]
        kps[16] = [220, 500]
        kps[0] = [200, 170]
        # Arms straight down
        kps[7] = [180, 280]    # L_ELBOW
        kps[8] = [220, 280]    # R_ELBOW
        kps[9] = [180, 380]    # L_WRIST (well below hip)
        kps[10] = [220, 380]   # R_WRIST
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose == "standing"

    def test_knee_kneel_left(self):
        """單膝跪地 — left knee dropped near floor (larger y), right leg
        supporting at ~90° (sitting-like). Must classify as knee_kneel,
        not crouching/standing."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Upright torso
        kps[5] = [180, 200]    # L_SHOULDER
        kps[6] = [220, 200]    # R_SHOULDER
        kps[11] = [180, 300]   # L_HIP
        kps[12] = [220, 300]   # R_HIP
        # Asymmetric knees: L low (kneeling), R supporting at hip-level
        kps[13] = [230, 400]   # L_KNEE  (kneel side: below)
        kps[14] = [260, 290]   # R_KNEE  (support side: hip level)
        # Ankles: L tucked behind (kneeling), R planted below (supporting)
        kps[15] = [170, 420]   # L_ANKLE (back, knee bent)
        kps[16] = [280, 380]   # R_ANKLE (planted)
        kps[0] = [200, 170]    # NOSE
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose == "knee_kneel"

    def test_knee_kneel_both_bent_no_y_diff(self):
        """Both knees bent at the same height = crouching, NOT knee_kneel.
        Ensures knee_y_diff gate prevents shallow crouches from being
        misread as half-kneeling."""
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=70, knee_angle_deg=70, trunk_angle_deg=20)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose != "knee_kneel"

    def test_knee_kneel_ankle_hidden(self):
        """Kneel-side ankle occluded (score < _MIN_SCORE) must NOT block
        knee_kneel detection — foot tucked under the body or hidden by floor
        is the dominant real-world case. Standing-side ankle still required."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        kps[5] = [180, 200]    # L_SHOULDER
        kps[6] = [220, 200]    # R_SHOULDER
        kps[11] = [180, 300]   # L_HIP
        kps[12] = [220, 300]   # R_HIP
        # L knee on floor (low), R knee at hip level (support)
        kps[13] = [230, 400]   # L_KNEE  (kneel side)
        kps[14] = [260, 290]   # R_KNEE  (support side)
        # L ankle position is anything — score will mark it hidden
        kps[15] = [170, 420]   # L_ANKLE (occluded)
        kps[16] = [280, 380]   # R_ANKLE (planted)
        kps[0] = [200, 170]
        scores = np.ones(17, dtype=np.float32) * 0.9
        scores[15] = 0.05  # L_ANKLE hidden — would fail the old uniform gate
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose == "knee_kneel"

    def test_fallen_rejected_when_shoulder_below_hip(self):
        """MediaPipe sometimes hallucinates shoulder landmarks BELOW the hip
        (negative vertical_ratio) at awkward viewpoints — akimbo, half-kneel,
        partial body. Such frames must NOT trigger fallen; the new gate
        requires `vertical_ratio >= 0` so the rest of the classifier (or
        buffer-hold via None) decides instead."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Shoulders BELOW hips (anatomically impossible standing pose) —
        # exactly the garbage MediaPipe occasionally produces.
        kps[5] = [200, 320]    # L_SHOULDER (y > hip y)
        kps[6] = [220, 320]    # R_SHOULDER
        kps[11] = [200, 280]   # L_HIP
        kps[12] = [220, 280]   # R_HIP
        kps[13] = [200, 380]   # L_KNEE
        kps[14] = [220, 380]   # R_KNEE
        kps[15] = [200, 480]   # L_ANKLE
        kps[16] = [220, 480]   # R_ANKLE
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.4)
        assert pose != "fallen", "negative vertical_ratio must not trigger fallen"

    def test_fallen_rejected_when_torso_visibility_low(self):
        """Even when geometry says fallen, low shoulder/hip visibility means
        MediaPipe is unsure — drop the verdict to avoid false alarms."""
        from vision_perception.pose_classifier import classify_pose
        # Real fallen geometry from test_actual_fallen_still_detected
        kps = np.zeros((17, 2), dtype=np.float32)
        kps[5] = [100, 300]
        kps[6] = [140, 305]
        kps[11] = [250, 310]
        kps[12] = [290, 308]
        kps[13] = [370, 305]
        kps[14] = [410, 310]
        kps[15] = [470, 300]
        kps[16] = [510, 305]
        kps[0] = [60, 295]
        scores = np.ones(17, dtype=np.float32) * 0.9
        # Shoulder + hip visibility low (MediaPipe unsure)
        scores[5] = 0.2
        scores[6] = 0.2
        scores[11] = 0.3
        scores[12] = 0.3
        pose, _ = classify_pose(kps, scores, bbox_ratio=2.5)
        assert pose != "fallen", "Low torso visibility must NOT trigger fallen"

    def test_deep_bending_not_fallen(self):
        """Bending forward to touch the floor: trunk near horizontal but legs
        still going straight down → must classify as bending, NOT fallen."""
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        # Shoulders projected forward + slightly down (head down to toes)
        kps[5] = [100, 295]    # L_SHOULDER
        kps[6] = [140, 290]    # R_SHOULDER
        # Hips upright
        kps[11] = [195, 300]   # L_HIP
        kps[12] = [225, 300]   # R_HIP
        # Knees + ankles vertically below hips (legs straight)
        kps[13] = [195, 400]   # L_KNEE
        kps[14] = [225, 400]   # R_KNEE
        kps[15] = [195, 500]   # L_ANKLE
        kps[16] = [225, 500]   # R_ANKLE
        kps[0] = [80, 285]     # NOSE (well forward)
        scores = np.ones(17, dtype=np.float32) * 0.9
        # Narrow bbox (tall body silhouette).
        pose, _ = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose != "fallen", "Deep bending with legs vertical must not be fallen"
        assert pose == "bending"
