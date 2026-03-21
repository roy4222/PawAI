"""SCRFD face detection benchmark adapter.
Uses onnxruntime directly (no insightface dependency).
SCRFD-500M is ~2.4MB, supports CUDAExecutionProvider.
"""
import logging
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

from benchmarks.adapters.base import BenchAdapter

logger = logging.getLogger(__name__)


class FaceSCRFDAdapter(BenchAdapter):
    """Benchmark adapter for SCRFD face detection via onnxruntime."""

    def __init__(self):
        self._session: Optional[ort.InferenceSession] = None
        self._input_name = None
        self._input_size = (640, 640)

    def load(self, config: dict) -> None:
        model_path = config.get(
            "model_path",
            "/home/jetson/face_models/det_500m.onnx",
        )
        providers = config.get("providers", [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ])
        self._input_size = tuple(config.get("input_size", [640, 640]))

        self._session = ort.InferenceSession(model_path, providers=providers)
        self._input_name = self._session.get_inputs()[0].name
        actual_providers = self._session.get_providers()
        logger.info(f"SCRFD loaded: {model_path} (providers={actual_providers}, "
                     f"input_size={self._input_size})")

    def prepare_input(self, input_ref: str) -> np.ndarray:
        img = cv2.imread(input_ref)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {input_ref}")
        return img

    def infer(self, input_data: np.ndarray) -> dict:
        if self._session is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Preprocess: resize + normalize + CHW + batch
        h, w = self._input_size
        img_resized = cv2.resize(input_data, (w, h))
        img_float = img_resized.astype(np.float32)
        # SCRFD expects BGR, normalized to [0,1] range or mean-subtracted
        # Standard InsightFace preprocessing: (img - 127.5) / 128.0
        img_float = (img_float - 127.5) / 128.0
        img_chw = img_float.transpose(2, 0, 1)  # HWC -> CHW
        img_batch = np.expand_dims(img_chw, axis=0)  # Add batch dim

        outputs = self._session.run(None, {self._input_name: img_batch})

        # SCRFD outputs: multiple stride tensors (scores + bboxes + keypoints)
        # WARNING: No bbox decode or NMS here — raw anchor count only.
        # This value is NOT comparable to YuNet's n_faces (which has NMS).
        raw_count = 0
        scores_list = []
        for out in outputs:
            if out.ndim == 3 and out.shape[-1] == 1:
                score_flat = out[0, :, 0]
                raw_count += int(np.sum(score_flat > 0.5))
                scores_list.extend(score_flat[score_flat > 0.5].tolist())

        return {
            "raw_anchor_count": raw_count,  # NOT real face count (no NMS)
            "scores": scores_list[:10],
            "n_faces": -1,  # placeholder — needs decode+NMS for real count
        }

    def cleanup(self) -> None:
        self._session = None
