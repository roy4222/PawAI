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
        from vision_perception.pose_classifier import classify_pose
        # Upright trunk, hip_angle ≈ 120°, trunk ≈ 5°
        kps = _body_from_angles(hip_angle_deg=120, knee_angle_deg=100, trunk_angle_deg=5)
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
