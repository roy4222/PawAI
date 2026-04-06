"""MediaPipe Pose wrapper with COCO 17-point compatibility layer.

Outputs (17, 2) body keypoints + (17,) scores in COCO format,
so pose_classifier works without any changes.

Runs on CPU (TFLite XNNPACK), does NOT use GPU.
"""
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# MediaPipe 33-point → COCO 17-point index mapping.
# 13 of 17 COCO points are mapped (nose + upper/lower body).
# Eyes and ears (COCO 1-4) are omitted — not needed for classification or visualization.
_MP_TO_COCO = {
    0: 0,    # NOSE: MediaPipe index 0
    5: 11,   # L_SHOULDER: MediaPipe index 11
    6: 12,   # R_SHOULDER: MediaPipe index 12
    7: 13,   # L_ELBOW: MediaPipe index 13
    8: 14,   # R_ELBOW: MediaPipe index 14
    9: 15,   # L_WRIST: MediaPipe index 15
    10: 16,  # R_WRIST: MediaPipe index 16
    11: 23,  # L_HIP: MediaPipe index 23
    12: 24,  # R_HIP: MediaPipe index 24
    13: 25,  # L_KNEE: MediaPipe index 25
    14: 26,  # R_KNEE: MediaPipe index 26
    15: 27,  # L_ANKLE: MediaPipe index 27
    16: 28,  # R_ANKLE: MediaPipe index 28
}


class MediaPipePose:
    """MediaPipe Pose → COCO 17-point format for pose_classifier."""

    def __init__(self, complexity: int = 1, min_confidence: float = 0.5):
        try:
            import mediapipe as mp
        except ImportError:
            raise ImportError(
                "mediapipe not installed. Run: uv pip install mediapipe"
            )

        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=complexity,
            min_detection_confidence=min_confidence,
        )
        logger.info(f"MediaPipe Pose loaded: complexity={complexity}, "
                     f"min_conf={min_confidence}")

    def detect(self, image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Detect pose and return COCO 17-point format.

        Returns:
            (body_kps, body_scores) — (17, 2) pixel coords + (17,) visibility.
            Compatible with pose_classifier.classify_pose().
        """
        h, w = image_bgr.shape[:2]
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        body_kps = np.zeros((17, 2), dtype=np.float32)
        body_scores = np.zeros(17, dtype=np.float32)

        if self._pose is None:
            return body_kps, body_scores
        result = self._pose.process(image_rgb)

        if result.pose_landmarks is None:
            return body_kps, body_scores

        landmarks = result.pose_landmarks.landmark

        for coco_idx, mp_idx in _MP_TO_COCO.items():
            lm = landmarks[mp_idx]
            body_kps[coco_idx] = [lm.x * w, lm.y * h]
            body_scores[coco_idx] = lm.visibility

        return body_kps, body_scores

    def close(self):
        if self._pose is not None:
            self._pose.close()
            self._pose = None
