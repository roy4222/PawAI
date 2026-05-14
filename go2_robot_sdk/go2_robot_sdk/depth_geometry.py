"""Depth-image safety helper for D435 → /capability/depth_clear.

Pure-Python (numpy) — no rclpy / ROS dependencies — so unit tests can import it
without bringing in the full ROS2 stack. Used by `depth_safety_node`.

Conservative v1 logic (kept deliberately simple for 5/2 demo base):
  1. Take a centred ROI of the depth image.
  2. Treat depths < min_valid_depth_m as noise (sensor floor / NaN holes); ignore.
  3. Among the remaining valid pixels, count how many are within stop_distance_m.
  4. If that ratio ≥ danger_pixel_ratio, declare NOT clear.

Returning "clear" when the ROI has no valid pixels at all is conservative-safe:
nav_action_server / executive should already be gating on /capability/nav_ready
(AMCL + costmap healthy), so a totally blank depth frame doesn't grant motion.
"""
from typing import Tuple

import numpy as np

# Defaults (overridable via ROS params on the node)
DEFAULT_STOP_DISTANCE_M = 0.4
DEFAULT_MIN_VALID_DEPTH_M = 0.15
DEFAULT_ROI_WIDTH_RATIO = 0.5
DEFAULT_ROI_HEIGHT_RATIO = 0.5
DEFAULT_DANGER_PIXEL_RATIO = 0.05


def compute_depth_clear(
    depth_m: np.ndarray,
    stop_distance_m: float = DEFAULT_STOP_DISTANCE_M,
    min_valid_depth_m: float = DEFAULT_MIN_VALID_DEPTH_M,
    roi_width_ratio: float = DEFAULT_ROI_WIDTH_RATIO,
    roi_height_ratio: float = DEFAULT_ROI_HEIGHT_RATIO,
    danger_pixel_ratio: float = DEFAULT_DANGER_PIXEL_RATIO,
) -> Tuple[bool, dict]:
    """Decide if the depth frame is clear of close obstacles.

    Args:
        depth_m: HxW float depth image, units METERS. Zeros / NaN treated as invalid.
        stop_distance_m: depths strictly below this count as danger.
        min_valid_depth_m: depths strictly below this are treated as noise/invalid.
        roi_width_ratio / roi_height_ratio: centred ROI as fraction of frame size.
        danger_pixel_ratio: fraction of *valid* ROI pixels that must be danger to
            flip clear=false.

    Returns:
        (clear: bool, info: dict). info has valid_count, danger_count, ratio,
        and min_depth_m for debug logging.
    """
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be 2D, got shape {depth_m.shape}")

    h, w = depth_m.shape
    rh = max(1, int(h * roi_height_ratio))
    rw = max(1, int(w * roi_width_ratio))
    cy, cx = h // 2, w // 2
    y0, y1 = cy - rh // 2, cy - rh // 2 + rh
    x0, x1 = cx - rw // 2, cx - rw // 2 + rw
    roi = depth_m[y0:y1, x0:x1]

    # Valid = finite + above noise floor
    finite_mask = np.isfinite(roi)
    valid_mask = finite_mask & (roi >= min_valid_depth_m)
    valid_count = int(valid_mask.sum())

    if valid_count == 0:
        # No usable readings → conservative: report clear (don't block on no info).
        # Other gates (nav_ready, AMCL, reactive_stop_node LiDAR) catch this case.
        return True, {
            "valid_count": 0,
            "danger_count": 0,
            "ratio": 0.0,
            "min_depth_m": float("inf"),
        }

    danger_mask = valid_mask & (roi < stop_distance_m)
    danger_count = int(danger_mask.sum())
    danger_ratio = danger_count / valid_count

    valid_depths = roi[valid_mask]
    min_depth = float(valid_depths.min())

    clear = danger_ratio < danger_pixel_ratio
    return clear, {
        "valid_count": valid_count,
        "danger_count": danger_count,
        "ratio": danger_ratio,
        "min_depth_m": min_depth,
    }
