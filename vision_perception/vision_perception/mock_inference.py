"""Mock inference adapter — returns scenario-based fake keypoints.

No GPU, no model, no camera required. Used for Phase 1 development.
"""
from __future__ import annotations

import numpy as np

from .inference_adapter import InferenceAdapter, InferenceResult

# Pre-built keypoint scenarios
_SCENARIOS: dict[str, dict] = {}


def _register(name: str, body: np.ndarray, left_hand: np.ndarray, right_hand: np.ndarray):
    _SCENARIOS[name] = {"body": body, "left_hand": left_hand, "right_hand": right_hand}


def _standing_body() -> np.ndarray:
    """Upright standing pose — hip/knee angles ~175 deg, trunk ~5 deg."""
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[0] = [320, 50]    # nose
    kps[5] = [290, 120]   # l_shoulder
    kps[6] = [350, 120]   # r_shoulder
    kps[11] = [300, 280]  # l_hip
    kps[12] = [340, 280]  # r_hip
    kps[13] = [300, 380]  # l_knee
    kps[14] = [340, 380]  # r_knee
    kps[15] = [300, 460]  # l_ankle
    kps[16] = [340, 460]  # r_ankle
    return kps


def _sitting_body() -> np.ndarray:
    """Seated pose — hip ~90 deg, trunk ~15 deg."""
    kps = _standing_body().copy()
    kps[13] = [380, 280]  # knees forward
    kps[14] = [420, 280]
    kps[15] = [380, 380]  # ankles down
    kps[16] = [420, 380]
    return kps


def _fallen_body() -> np.ndarray:
    """Horizontal body — trunk > 60 deg, bbox_ratio > 1."""
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[0] = [100, 400]
    kps[5] = [150, 380]
    kps[6] = [150, 420]
    kps[11] = [300, 380]
    kps[12] = [300, 420]
    kps[13] = [400, 380]
    kps[14] = [400, 420]
    kps[15] = [480, 380]
    kps[16] = [480, 420]
    return kps


def _stop_hand() -> np.ndarray:
    """Open palm — all fingers extended."""
    kps = np.zeros((21, 2), dtype=np.float32)
    kps[0] = [0, 0]       # wrist
    kps[4] = [80, -60]    # thumb tip
    kps[8] = [40, -150]   # index tip
    kps[12] = [0, -160]   # middle tip
    kps[16] = [-40, -150] # ring tip
    kps[20] = [-80, -130] # pinky tip
    kps[5] = [30, -50]    # index MCP
    kps[9] = [0, -50]     # middle MCP
    kps[13] = [-30, -50]  # ring MCP
    kps[17] = [-60, -50]  # pinky MCP
    return kps


def _fist_hand() -> np.ndarray:
    """Closed fist — all fingers curled."""
    kps = np.zeros((21, 2), dtype=np.float32)
    kps[0] = [0, 0]
    kps[4] = [15, -25]
    kps[8] = [10, -35]
    kps[12] = [0, -35]
    kps[16] = [-10, -35]
    kps[20] = [-20, -30]
    kps[5] = [20, -40]
    kps[9] = [0, -40]
    kps[13] = [-20, -40]
    kps[17] = [-40, -35]
    return kps


def _point_hand() -> np.ndarray:
    """Point — only index extended."""
    kps = _fist_hand().copy()
    kps[8] = [40, -150]  # index tip far
    return kps


def _bending_body() -> np.ndarray:
    """Bending forward — trunk ~50 deg, hip ~110 deg, legs straight ~170 deg."""
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[0] = [400, 200]   # nose (forward)
    kps[5] = [370, 220]   # l_shoulder (leaning forward)
    kps[6] = [430, 220]   # r_shoulder
    kps[11] = [300, 280]  # l_hip
    kps[12] = [340, 280]  # r_hip
    kps[13] = [300, 380]  # l_knee (straight down)
    kps[14] = [340, 380]  # r_knee
    kps[15] = [300, 460]  # l_ankle
    kps[16] = [340, 460]  # r_ankle
    return kps


def _idle_hand() -> np.ndarray:
    return np.zeros((21, 2), dtype=np.float32)


# Register scenarios
_register("standing_idle", _standing_body(), _idle_hand(), _idle_hand())
_register("sitting", _sitting_body(), _idle_hand(), _idle_hand())
_register("fallen", _fallen_body(), _idle_hand(), _idle_hand())
_register("bending", _bending_body(), _idle_hand(), _idle_hand())
_register("stop", _standing_body(), _stop_hand(), _idle_hand())
_register("fist", _standing_body(), _fist_hand(), _idle_hand())
_register("point", _standing_body(), _point_hand(), _idle_hand())


class MockInference(InferenceAdapter):
    """Returns pre-configured keypoints for a given scenario.

    Args:
        scenario: Key from _SCENARIOS dict. Default "standing_idle".
    """

    def __init__(self, scenario: str = "standing_idle"):
        if scenario not in _SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario}'. Available: {sorted(_SCENARIOS)}"
            )
        self._scenario = _SCENARIOS[scenario]

    def infer(self, image_bgr: np.ndarray | None) -> InferenceResult:
        """Return scenario keypoints. image_bgr is ignored (can be None)."""
        high = np.ones(17, dtype=np.float32) * 0.9
        hand_high = np.ones(21, dtype=np.float32) * 0.9
        hand_zero = np.zeros(21, dtype=np.float32)

        left = self._scenario["left_hand"]
        right = self._scenario["right_hand"]

        return InferenceResult(
            body_kps=self._scenario["body"].copy(),
            body_scores=high.copy(),
            left_hand_kps=left.copy(),
            left_hand_scores=hand_high.copy() if np.any(left) else hand_zero.copy(),
            right_hand_kps=right.copy(),
            right_hand_scores=hand_high.copy() if np.any(right) else hand_zero.copy(),
        )
