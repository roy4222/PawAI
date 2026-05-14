"""Pure-numpy tests for depth_geometry.compute_depth_clear (Phase A Step 2).

Real D435 frame validation is on Jetson (manual hand-block test); these tests
guard the ROI math and edge cases that would otherwise show up as silent
false-positives / false-negatives in front of obstacles.
"""
import os
import sys

import numpy as np
import pytest

# Direct file import bypassing package __init__ (which requires aioice submodule on Jetson)
_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "go2_robot_sdk")
sys.path.insert(0, _HELPERS_DIR)
from depth_geometry import (  # noqa: E402
    DEFAULT_DANGER_PIXEL_RATIO,
    DEFAULT_MIN_VALID_DEPTH_M,
    DEFAULT_ROI_HEIGHT_RATIO,
    DEFAULT_ROI_WIDTH_RATIO,
    DEFAULT_STOP_DISTANCE_M,
    compute_depth_clear,
)


def _frame(value: float, h: int = 480, w: int = 640) -> np.ndarray:
    return np.full((h, w), value, dtype=np.float32)


# ── Core 3 cases mandated by Phase A plan ──

def test_clear_when_roi_far():
    """ROI 全部 > stop_distance → clear=true."""
    depth = _frame(2.0)  # 2m everywhere
    clear, info = compute_depth_clear(depth)
    assert clear is True
    assert info["danger_count"] == 0
    assert info["min_depth_m"] == pytest.approx(2.0)


def test_not_clear_when_center_obstacle():
    """ROI 中心放 0.3m 障礙(占整個 ROI)→ clear=false."""
    depth = _frame(2.0, h=480, w=640)
    # ROI 50%×50% = 240×320 centred at (240,320). Fill the *whole ROI* with 0.3m.
    cy, cx = 240, 320
    rh, rw = 240, 320
    depth[cy - rh // 2 : cy + rh // 2, cx - rw // 2 : cx + rw // 2] = 0.3
    clear, info = compute_depth_clear(depth)
    assert clear is False
    assert info["min_depth_m"] == pytest.approx(0.3)
    assert info["ratio"] == pytest.approx(1.0)


def test_clear_when_only_noise():
    """ROI 全部 < min_valid_depth_m(噪點/零值)→ clear=true(保守)."""
    depth = _frame(0.05)  # below 0.15 floor everywhere
    clear, info = compute_depth_clear(depth)
    assert clear is True
    assert info["valid_count"] == 0
    assert info["danger_count"] == 0


# ── Extra guard cases ──

def test_partial_obstacle_below_ratio_is_clear():
    """少數 danger 像素(< danger_pixel_ratio)→ clear=true."""
    depth = _frame(2.0)
    # Put a tiny 10x10 obstacle in centre → 100 danger / (240*320=76800) valid ≈ 0.001 < 0.05
    cy, cx = 240, 320
    depth[cy - 5 : cy + 5, cx - 5 : cx + 5] = 0.3
    clear, info = compute_depth_clear(depth)
    assert clear is True
    assert info["danger_count"] == 100
    assert info["ratio"] < DEFAULT_DANGER_PIXEL_RATIO


def test_partial_obstacle_above_ratio_is_not_clear():
    """超過 danger_pixel_ratio 的 danger pixel → clear=false."""
    depth = _frame(2.0)
    # Big patch ~10% of ROI → above 5% threshold
    cy, cx = 240, 320
    rh, rw = 100, 100  # 10000 pixels ≈ 13% of 76800
    depth[cy - rh // 2 : cy + rh // 2, cx - rw // 2 : cx + rw // 2] = 0.3
    clear, info = compute_depth_clear(depth)
    assert clear is False
    assert info["ratio"] > DEFAULT_DANGER_PIXEL_RATIO


def test_nan_treated_as_invalid():
    """NaN holes (no reading) treated as invalid, not as zero distance."""
    depth = _frame(2.0)
    depth[100:200, 100:200] = np.nan
    clear, info = compute_depth_clear(depth)
    assert clear is True
    # Valid count should exclude the NaN region inside ROI overlap
    assert info["valid_count"] > 0


def test_obstacle_outside_roi_ignored():
    """Obstacle in the corner (outside centred ROI) does NOT trigger danger."""
    depth = _frame(2.0)
    depth[0:50, 0:50] = 0.2  # top-left corner — outside 50% centred ROI
    clear, info = compute_depth_clear(depth)
    assert clear is True
    assert info["danger_count"] == 0


def test_default_constants_match_plan():
    """Plan-fixed defaults; bumping them should be intentional + flag the test."""
    assert DEFAULT_STOP_DISTANCE_M == 0.4
    assert DEFAULT_MIN_VALID_DEPTH_M == 0.15
    assert DEFAULT_ROI_WIDTH_RATIO == 0.5
    assert DEFAULT_ROI_HEIGHT_RATIO == 0.5
    assert DEFAULT_DANGER_PIXEL_RATIO == 0.05


def test_rejects_non_2d_input():
    with pytest.raises(ValueError):
        compute_depth_clear(np.zeros((3, 4, 5)))


# ── Fail-closed semantics (node-level, not helper-level) ──
# These tests document the contract the node must enforce. The helper itself
# returns clear=true for an all-zero/noise frame because it has no concept of
# "no frame" vs "all noise". The NODE must distinguish:
#   * No frame ever received → publish False
#   * Frame older than max_frame_age_s → publish False
#   * Compute exception → publish False
# See depth_safety_node._tick(). These are guard tests on the *helper* shape so
# changes to it don't silently break the node's fail-closed wrapper.

def test_helper_does_not_distinguish_no_frame():
    """All-zero input is computed as clear=true; node MUST add fail-closed logic
    on top (no-frame / stale-frame / exception → false)."""
    depth = np.zeros((480, 640), dtype=np.float32)
    clear, info = compute_depth_clear(depth)
    # Helper says "clear" because zeros are below min_valid → no valid pixels
    assert clear is True
    assert info["valid_count"] == 0
    # Node must NOT trust this when it means "no frame received";
    # see test_depth_safety_node tick logic for the wrapper.
