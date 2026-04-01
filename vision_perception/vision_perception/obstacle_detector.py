"""Reactive obstacle detector — pure Python/numpy, no ROS2 dependency.

Extracts a center-band ROI from D435 depth frame, counts pixels
closer than threshold, and returns an ObstacleResult.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class ObstacleResult:
    """Result of a single obstacle detection frame."""

    is_obstacle: bool
    distance_min: float       # meters (inf if no valid pixels)
    obstacle_ratio: float     # 0.0~1.0
    zone: str                 # "clear" / "warning" / "danger"


class ObstacleDetector:
    """Stateless depth-ROI obstacle detector.

    Parameters are constructor args so the class stays pure and testable.
    """

    def __init__(
        self,
        threshold_m: float = 0.8,
        warning_m: float = 1.2,
        max_range_m: float = 3.0,
        roi_top_ratio: float = 0.4,
        roi_bottom_ratio: float = 0.8,
        roi_left_ratio: float = 0.2,
        roi_right_ratio: float = 0.8,
        obstacle_ratio_trigger: float = 0.15,
    ):
        self.threshold_m = threshold_m
        self.warning_m = warning_m
        self.max_range_m = max_range_m
        self.roi_top = roi_top_ratio
        self.roi_bottom = roi_bottom_ratio
        self.roi_left = roi_left_ratio
        self.roi_right = roi_right_ratio
        self.ratio_trigger = obstacle_ratio_trigger

    def detect(self, depth: np.ndarray) -> ObstacleResult:
        """Analyze a depth frame and return obstacle status.

        Args:
            depth: (H, W) float32 array, depth in meters.
                   0.0 = invalid / no reading.
        """
        h, w = depth.shape[:2]
        roi = depth[
            int(h * self.roi_top): int(h * self.roi_bottom),
            int(w * self.roi_left): int(w * self.roi_right),
        ]

        # Filter valid pixels (non-zero and within max range)
        valid_mask = (roi > 0) & (roi <= self.max_range_m)
        valid = roi[valid_mask]

        if valid.size == 0:
            return ObstacleResult(
                is_obstacle=False, distance_min=float("inf"),
                obstacle_ratio=0.0, zone="clear",
            )

        distance_min = float(np.min(valid))
        close_count = int(np.sum(valid < self.threshold_m))
        obstacle_ratio = close_count / valid.size

        # Zone is based on distance_min + ratio
        # Danger: enough close pixels AND nearest is within threshold
        # Warning: nearest is between threshold and warning_m (regardless of ratio)
        # Clear: everything else
        if obstacle_ratio >= self.ratio_trigger and distance_min < self.threshold_m:
            zone = "danger"
        elif distance_min < self.warning_m:
            zone = "warning"
        else:
            zone = "clear"

        is_obstacle = zone == "danger"

        return ObstacleResult(
            is_obstacle=is_obstacle,
            distance_min=distance_min,
            obstacle_ratio=obstacle_ratio,
            zone=zone,
        )
