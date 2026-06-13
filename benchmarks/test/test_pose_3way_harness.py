import numpy as np

from benchmarks.scripts import pose_3way_harness as sut


def _standing_keypoints():
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[5] = [200, 200]
    kps[6] = [220, 200]
    kps[11] = [200, 300]
    kps[12] = [220, 300]
    kps[13] = [200, 400]
    kps[14] = [220, 400]
    kps[15] = [200, 500]
    kps[16] = [220, 500]
    kps[0] = [210, 170]
    return kps


def _sitting_keypoints():
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[5] = [200, 200]
    kps[6] = [220, 200]
    kps[11] = [200, 300]
    kps[12] = [220, 300]
    kps[13] = [260, 295]
    kps[14] = [280, 295]
    kps[15] = [260, 380]
    kps[16] = [280, 380]
    kps[0] = [210, 170]
    return kps


def test_classify_keypoint_frame_maps_to_two_class_labels():
    scores = np.ones(17, dtype=np.float32) * 0.9

    standing = sut.classify_keypoint_pose(_standing_keypoints(), scores, min_score=0.2)
    sitting = sut.classify_keypoint_pose(_sitting_keypoints(), scores, min_score=0.2)

    assert standing.pose_name == "standing"
    assert standing.two_class == "standing"
    assert sitting.pose_name == "sitting"
    assert sitting.two_class == "sitting"


def test_three_way_keypoint_comparison_has_all_backend_results():
    scores = np.ones(17, dtype=np.float32) * 0.9
    frame = sut.KeypointFrame(
        frame=3,
        timestamp=0.3,
        keypoints=_sitting_keypoints(),
        scores=scores,
        bbox_ratio=0.6,
    )

    comparison = sut.compare_keypoint_backends([frame], min_score=0.2)[0]

    assert comparison.frame == 3
    assert set(comparison.results) == {"mediapipe", "yolo26n_pose", "478_sc"}
    assert {result.two_class for result in comparison.results.values()} == {"sitting"}
