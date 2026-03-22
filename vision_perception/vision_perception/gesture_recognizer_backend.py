"""MediaPipe Gesture Recognizer Task API backend.

Replaces MediaPipe Hands + gesture_classifier.py with a single model
that handles hand detection + gesture classification in one pass.

Built-in gestures: Open_Palm, Closed_Fist, Pointing_Up, Thumb_Up,
Thumb_Down, Victory, ILoveYou (+ Unknown).

Custom gestures can be added via MediaPipe Model Maker (train on x86,
deploy .task file to Jetson).
"""
from __future__ import annotations

import logging
import os
import time
import urllib.request

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
)

# Map MediaPipe gesture labels → project event names
_GESTURE_MAP = {
    "Open_Palm": "stop",
    "Closed_Fist": "fist",       # → event_builder COMPAT_MAP → "ok"
    "Pointing_Up": "point",
    "Thumb_Up": "thumbs_up",
    "Victory": "victory",
    "Thumb_Down": "thumbs_down",
    "ILoveYou": "i_love_you",
}


class GestureRecognizerBackend:
    """MediaPipe Gesture Recognizer Task API wrapper.

    Provides the same interface as MediaPipeHands + gesture_classifier
    but in a single model call with better classification quality.
    """

    def __init__(self, model_path: str, max_hands: int = 2,
                 min_confidence: float = 0.5):
        model_path = os.path.expanduser(model_path)

        if not os.path.exists(model_path):
            logger.info(f"Model not found at {model_path}, downloading...")
            try:
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                urllib.request.urlretrieve(_MODEL_URL, model_path)
                logger.info(f"Downloaded gesture_recognizer.task to {model_path}")
            except Exception as e:
                raise RuntimeError(
                    f"Gesture Recognizer model not found at {model_path} "
                    f"and download failed: {e}. "
                    f"Please download manually from: {_MODEL_URL}"
                ) from e

        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=min_confidence,
            min_hand_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)
        self._mp = mp
        self._t0 = time.monotonic()
        logger.info(f"GestureRecognizerBackend loaded: max_hands={max_hands}, "
                     f"model={model_path}")

    def detect(self, image_bgr: np.ndarray) -> tuple[
        list[tuple[str, float, str]],
        np.ndarray, np.ndarray, np.ndarray, np.ndarray,
    ]:
        """Detect gestures from BGR image.

        Returns:
            (detections, lh_kps, lh_scores, rh_kps, rh_scores)
            detections: list of (gesture_name, confidence, hand_label).
            lh/rh_kps: (21, 2) pixel coords for left/right hand.
            lh/rh_scores: (21,) confidence for left/right hand.
        """
        h, w = image_bgr.shape[:2]
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=image_rgb
        )

        timestamp_ms = int((time.monotonic() - self._t0) * 1000)
        result = self._recognizer.recognize_for_video(mp_image, timestamp_ms)

        detections: list[tuple[str, float, str]] = []
        lh_kps = np.zeros((21, 2), dtype=np.float32)
        lh_scores = np.zeros(21, dtype=np.float32)
        rh_kps = np.zeros((21, 2), dtype=np.float32)
        rh_scores = np.zeros(21, dtype=np.float32)

        if not result.gestures:
            return detections, lh_kps, lh_scores, rh_kps, rh_scores

        for gestures, handedness, landmarks in zip(
            result.gestures, result.handedness, result.hand_landmarks
        ):
            top_gesture = gestures[0]
            mp_name = top_gesture.category_name
            confidence = top_gesture.score
            hand_label = handedness[0].category_name.lower()

            # Convert normalized landmarks → pixel coords
            kps = np.array([[lm.x * w, lm.y * h] for lm in landmarks],
                           dtype=np.float32)
            scores = np.full(21, confidence, dtype=np.float32)

            if hand_label == "left":
                lh_kps, lh_scores = kps, scores
            else:
                rh_kps, rh_scores = kps, scores

            if mp_name == "Unknown" or mp_name not in _GESTURE_MAP:
                continue

            project_name = _GESTURE_MAP[mp_name]
            detections.append((project_name, confidence, hand_label))

        return detections, lh_kps, lh_scores, rh_kps, rh_scores

    def close(self):
        if self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None
