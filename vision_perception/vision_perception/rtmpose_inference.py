"""RTMPose wholebody inference adapter via rtmlib.

Runs RTMPose wholebody (133 keypoints) on Jetson with onnxruntime-gpu.
Requires: pip install rtmlib onnxruntime-gpu

Keypoint index mapping (verified on Jetson 2026-03-18):
  body:       0-16  (17 COCO body keypoints)
  foot:       17-22 (6 foot keypoints)
  left_hand:  23-43 (21 COCO-WholeBody hand keypoints)
  right_hand: 44-64 (21 COCO-WholeBody hand keypoints)
  face:       65-132 (68 face keypoints)
"""
from __future__ import annotations

import logging
import time

import numpy as np

from .inference_adapter import InferenceAdapter, InferenceResult

logger = logging.getLogger(__name__)

# Verified keypoint slices (rtmlib Wholebody, 133 total)
_BODY_SLICE = slice(0, 17)
_LEFT_HAND_SLICE = slice(23, 44)
_RIGHT_HAND_SLICE = slice(44, 65)


class RTMPoseInference(InferenceAdapter):
    """RTMPose wholebody inference via rtmlib.

    Args:
        mode: rtmlib mode — "lightweight" (fastest) or "balanced" (recommended).
        backend: "onnxruntime" (recommended for Jetson).
        device: "cuda" for GPU, "cpu" for fallback.
    """

    def __init__(
        self,
        mode: str = "balanced",
        backend: str = "onnxruntime",
        device: str = "cuda",
    ):
        from rtmlib import Wholebody

        logger.info(
            f"RTMPoseInference starting: mode={mode}, backend={backend}, device={device}"
        )
        logger.info(
            f"Keypoint slices: body={_BODY_SLICE}, "
            f"left_hand={_LEFT_HAND_SLICE}, right_hand={_RIGHT_HAND_SLICE}"
        )

        t0 = time.time()
        self._wholebody = Wholebody(mode=mode, backend=backend, device=device)
        init_time = time.time() - t0
        logger.info(f"RTMPoseInference ready in {init_time:.1f}s (includes model download if first run)")

        # Verify provider
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            logger.info(f"onnxruntime providers: {providers}")
        except ImportError:
            logger.warning("Cannot check onnxruntime providers")

        self._warmup_done = False

    def infer(self, image_bgr: np.ndarray | None) -> InferenceResult:
        """Run wholebody inference on a BGR image.

        Args:
            image_bgr: BGR image from camera. Must not be None.

        Returns:
            InferenceResult with body, left_hand, right_hand keypoints.
        """
        if image_bgr is None:
            raise ValueError("RTMPoseInference requires image_bgr (use MockInference for no-camera mode)")

        t0 = time.time()
        keypoints, scores = self._wholebody(image_bgr)
        elapsed = time.time() - t0

        if not self._warmup_done:
            logger.info(f"First inference (warmup): {elapsed:.1f}s")
            self._warmup_done = True

        # No person detected
        if keypoints is None or len(keypoints) == 0:
            return self._empty_result()

        # Take the first person (rtmlib returns sorted by detection confidence)
        person_kps = keypoints[0]   # (133, 2)
        person_scores = scores[0]   # (133,)

        return InferenceResult(
            body_kps=person_kps[_BODY_SLICE].astype(np.float32),
            body_scores=person_scores[_BODY_SLICE].astype(np.float32),
            left_hand_kps=person_kps[_LEFT_HAND_SLICE].astype(np.float32),
            left_hand_scores=person_scores[_LEFT_HAND_SLICE].astype(np.float32),
            right_hand_kps=person_kps[_RIGHT_HAND_SLICE].astype(np.float32),
            right_hand_scores=person_scores[_RIGHT_HAND_SLICE].astype(np.float32),
        )

    @staticmethod
    def _empty_result() -> InferenceResult:
        return InferenceResult(
            body_kps=np.zeros((17, 2), dtype=np.float32),
            body_scores=np.zeros(17, dtype=np.float32),
            left_hand_kps=np.zeros((21, 2), dtype=np.float32),
            left_hand_scores=np.zeros(21, dtype=np.float32),
            right_hand_kps=np.zeros((21, 2), dtype=np.float32),
            right_hand_scores=np.zeros(21, dtype=np.float32),
        )
