"""RTMPose wholebody benchmark adapter.
Wraps rtmlib.Wholebody for benchmarking pose + gesture inference.
Reference: vision_perception/vision_perception/rtmpose_inference.py
"""
import logging
from typing import Any, Optional

import cv2
import numpy as np

from benchmarks.adapters.base import BenchAdapter

logger = logging.getLogger(__name__)


class PoseRTMPoseAdapter(BenchAdapter):
    """Benchmark adapter for RTMPose wholebody via rtmlib."""

    def __init__(self):
        self._wholebody = None
        self._mode = "balanced"

    def load(self, config: dict) -> None:
        try:
            from rtmlib import Wholebody
        except ImportError:
            raise ImportError("rtmlib not installed. Run: pip install --no-deps rtmlib")

        self._mode = config.get("mode", "balanced")
        device = config.get("device", "cuda")
        backend = config.get("backend", "onnxruntime")

        self._wholebody = Wholebody(
            mode=self._mode,
            backend=backend,
            device=device,
        )
        logger.info(f"RTMPose loaded: mode={self._mode}, backend={backend}, device={device}")

    def prepare_input(self, input_ref: str) -> np.ndarray:
        img = cv2.imread(input_ref)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {input_ref}")
        return img

    def infer(self, input_data: np.ndarray) -> dict:
        if self._wholebody is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        keypoints, scores = self._wholebody(input_data)

        n_persons = keypoints.shape[0] if keypoints is not None and len(keypoints.shape) > 1 else 0

        return {
            "n_persons": n_persons,
            "keypoints_shape": list(keypoints.shape) if keypoints is not None else [],
            "mode": self._mode,
        }

    def cleanup(self) -> None:
        self._wholebody = None
