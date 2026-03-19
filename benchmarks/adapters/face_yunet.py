"""YuNet face detection benchmark adapter.
Wraps OpenCV's FaceDetectorYN for benchmarking.
Reference: face_perception/face_perception/face_identity_node.py:147-157
"""
import logging
from typing import Optional

import cv2
import numpy as np

from benchmarks.adapters.base import BenchAdapter

logger = logging.getLogger(__name__)


class FaceYuNetAdapter(BenchAdapter):
    """Benchmark adapter for YuNet face detection via OpenCV."""

    def __init__(self):
        self._detector: Optional[cv2.FaceDetectorYN] = None

    def load(self, config: dict) -> None:
        model_path = config.get(
            "model_path",
            "/home/jetson/face_models/face_detection_yunet_legacy.onnx",
        )
        score_threshold = config.get("score_threshold", 0.35)
        nms_threshold = config.get("nms_threshold", 0.3)
        top_k = config.get("top_k", 5000)
        input_size = tuple(config.get("input_size", [320, 320]))

        if not hasattr(cv2, "FaceDetectorYN"):
            raise ImportError(
                "OpenCV face module not available. "
                "Need OpenCV >= 4.8 with contrib (face module)."
            )

        self._detector = cv2.FaceDetectorYN.create(
            str(model_path), "", input_size,
            score_threshold, nms_threshold, top_k,
        )
        self._input_size = input_size
        logger.info(f"YuNet loaded: {model_path} (input={input_size})")

    def prepare_input(self, input_ref: str) -> np.ndarray:
        img = cv2.imread(input_ref)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {input_ref}")
        return img

    def infer(self, input_data: np.ndarray) -> dict:
        if self._detector is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        h, w = input_data.shape[:2]
        self._detector.setInputSize((w, h))
        retval, faces = self._detector.detect(input_data)

        n_faces = faces.shape[0] if faces is not None else 0
        boxes = []
        scores = []
        if faces is not None:
            for face in faces:
                x, y, fw, fh = face[:4].astype(int).tolist()
                score = float(face[14]) if face.shape[0] > 14 else 0.0
                boxes.append([x, y, fw, fh])
                scores.append(score)

        return {"boxes": boxes, "scores": scores, "n_faces": n_faces}

    def cleanup(self) -> None:
        self._detector = None
