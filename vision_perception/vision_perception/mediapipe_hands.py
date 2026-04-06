"""MediaPipe Hands wrapper for gesture detection.

Provides hand keypoints in pixel coordinates, compatible with gesture_classifier.
Runs on CPU (TFLite XNNPACK), does NOT compete with GPU models.
"""
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MediaPipeHands:
    """Lightweight wrapper around mediapipe.solutions.hands."""

    def __init__(self, max_hands: int = 2, min_confidence: float = 0.5,
                 static_mode: bool = False, model_complexity: int = 1):
        try:
            import mediapipe as mp
        except ImportError:
            raise ImportError(
                "mediapipe not installed. Run: uv pip install mediapipe"
            )

        self._hands = mp.solutions.hands.Hands(
            static_image_mode=static_mode,
            max_num_hands=max_hands,
            model_complexity=model_complexity,
            min_detection_confidence=min_confidence,
        )
        logger.info(f"MediaPipe Hands loaded: max_hands={max_hands}, "
                     f"complexity={model_complexity}, min_conf={min_confidence}")

    def detect(self, image_bgr: np.ndarray) -> tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """Detect hands and return keypoints in pixel coordinates.

        Returns:
            (left_hand_kps, left_hand_scores, right_hand_kps, right_hand_scores)
            Each kps is (21, 2) float32 pixel coords.
            Each scores is (21,) float32 confidence.
            Returns zeros if hand not detected.
        """
        left_kps = np.zeros((21, 2), dtype=np.float32)
        left_scores = np.zeros(21, dtype=np.float32)
        right_kps = np.zeros((21, 2), dtype=np.float32)
        right_scores = np.zeros(21, dtype=np.float32)

        if self._hands is None:
            return left_kps, left_scores, right_kps, right_scores

        h, w = image_bgr.shape[:2]
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        result = self._hands.process(image_rgb)

        if not result.multi_hand_landmarks:
            return left_kps, left_scores, right_kps, right_scores

        for hand_landmarks, handedness_list in zip(
            result.multi_hand_landmarks,
            result.multi_handedness,
        ):
            # Extract 21 keypoints: normalized [0,1] → pixel coords
            kps = np.array([
                [lm.x * w, lm.y * h]
                for lm in hand_landmarks.landmark
            ], dtype=np.float32)

            # Use hand detection confidence as uniform score for all 21 points
            conf = handedness_list.classification[0].score
            scores = np.full(21, conf, dtype=np.float32)

            # MediaPipe labels are mirrored (camera view):
            # "Left" in MediaPipe = viewer's left = actually right hand in image
            label = handedness_list.classification[0].label
            if label == "Left":
                right_kps = kps
                right_scores = scores
            else:
                left_kps = kps
                left_scores = scores

        return left_kps, left_scores, right_kps, right_scores

    def close(self):
        if self._hands is not None:
            self._hands.close()
            self._hands = None
