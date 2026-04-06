# vision_perception/test/test_mediapipe_pose_mapping.py
"""Tests for MediaPipe Pose → COCO mapping integrity."""


class TestMPToCOCOMapping:
    def test_all_coco_indices_in_range(self):
        from vision_perception.mediapipe_pose import _MP_TO_COCO
        for coco_idx in _MP_TO_COCO.keys():
            assert 0 <= coco_idx <= 16, f"COCO index {coco_idx} out of range [0, 16]"

    def test_all_mediapipe_indices_in_range(self):
        from vision_perception.mediapipe_pose import _MP_TO_COCO
        for mp_idx in _MP_TO_COCO.values():
            assert 0 <= mp_idx <= 32, f"MediaPipe index {mp_idx} out of range [0, 32]"

    def test_classifier_critical_points_preserved(self):
        """The 8 points used by pose_classifier must remain mapped."""
        from vision_perception.mediapipe_pose import _MP_TO_COCO
        # COCO indices used by pose_classifier: L/R shoulder, hip, knee, ankle
        critical = {5, 6, 11, 12, 13, 14, 15, 16}
        mapped = set(_MP_TO_COCO.keys())
        missing = critical - mapped
        assert not missing, f"Critical classifier points missing from mapping: {missing}"

    def test_new_visualization_points_mapped(self):
        """Nose, elbows, wrists should be mapped for skeleton visualization."""
        from vision_perception.mediapipe_pose import _MP_TO_COCO
        visualization_points = {
            0: 0,    # nose → MP nose
            7: 13,   # L_ELBOW → MP L_ELBOW
            8: 14,   # R_ELBOW → MP R_ELBOW
            9: 15,   # L_WRIST → MP L_WRIST
            10: 16,  # R_WRIST → MP R_WRIST
        }
        for coco_idx, expected_mp_idx in visualization_points.items():
            assert coco_idx in _MP_TO_COCO, f"COCO {coco_idx} not in mapping"
            assert _MP_TO_COCO[coco_idx] == expected_mp_idx, \
                f"COCO {coco_idx} maps to MP {_MP_TO_COCO[coco_idx]}, expected {expected_mp_idx}"

    def test_no_duplicate_coco_indices(self):
        from vision_perception.mediapipe_pose import _MP_TO_COCO
        coco_indices = list(_MP_TO_COCO.keys())
        assert len(coco_indices) == len(set(coco_indices)), "Duplicate COCO indices in mapping"

    def test_no_duplicate_mediapipe_indices(self):
        from vision_perception.mediapipe_pose import _MP_TO_COCO
        mp_indices = list(_MP_TO_COCO.values())
        assert len(mp_indices) == len(set(mp_indices)), "Duplicate MediaPipe indices in mapping"
