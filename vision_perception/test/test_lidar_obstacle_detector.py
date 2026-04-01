"""Unit tests for LidarObstacleDetector — TDD RED→GREEN."""
import math

import pytest

from vision_perception.lidar_obstacle_detector import (
    LidarObstacleDetector,
    LidarObstacleResult,
)

# --- Helpers ---

def make_scan(num_points=120, default_range=5.0):
    """Return (ranges, angle_min, angle_increment, range_min, range_max).

    Full 360-degree scan starting at 0 rad (front).
    """
    angle_min = 0.0
    angle_increment = 2 * math.pi / num_points
    ranges = [default_range] * num_points
    return ranges, angle_min, angle_increment, 0.25, 8.0


def index_for_deg(deg, num_points=120):
    """Return the range index closest to the given degree (0=front, CW)."""
    return round(deg / 360.0 * num_points) % num_points


# --- Default parameters ---

class TestLidarObstacleDetectorDefaults:
    """Tests with default parameters: safety=0.5, warning=0.8, min_points=2."""

    def setup_method(self):
        self.det = LidarObstacleDetector()

    def test_all_far_clear(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan(default_range=5.0)
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is False
        assert result.zone == "clear"

    def test_close_obstacle_front(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        # 3 points near front (indices 0, 1, 2)
        for i in range(3):
            ranges[i] = 0.3
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is True
        assert result.zone == "danger"
        assert result.distance_min == pytest.approx(0.3, abs=0.01)
        # direction should be near 0 degrees (front)
        assert abs(result.direction_deg) < 10.0

    def test_close_obstacle_left(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        idx = index_for_deg(90)
        for i in range(idx - 1, idx + 2):
            ranges[i % 120] = 0.3
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is True
        assert result.zone == "danger"
        assert 80.0 < result.direction_deg < 100.0

    def test_close_obstacle_behind(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        idx = index_for_deg(180)
        for i in range(idx - 1, idx + 2):
            ranges[i % 120] = 0.3
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is True
        assert result.zone == "danger"
        # direction near +-180
        assert abs(abs(result.direction_deg) - 180.0) < 10.0

    def test_single_point_noise_filtered(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        ranges[10] = 0.3  # only 1 point
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is False
        assert result.obstacle_count == 1

    def test_all_inf_ranges(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        ranges = [float("inf")] * 120
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is False
        assert result.zone == "clear"
        assert result.distance_min == float("inf")

    def test_all_zero_ranges(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        ranges = [0.0] * 120
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is False
        assert result.zone == "clear"

    def test_warning_zone(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        # 3 points at 0.6m (between safety 0.5 and warning 0.8)
        for i in range(3):
            ranges[i] = 0.6
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is False
        assert result.zone == "warning"

    def test_mixed_valid_invalid(self):
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        # First 5: 2 inf + 3 close
        ranges[0] = float("inf")
        ranges[1] = 0.0
        ranges[2] = 0.3
        ranges[3] = 0.3
        ranges[4] = 0.3
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is True
        assert result.obstacle_count == 3

    def test_obstacle_ratio_calculation(self):
        num = 100
        ranges, a_min, a_inc, r_min, r_max = make_scan(num_points=num)
        # Set 10 points close
        for i in range(10):
            ranges[i] = 0.3
        result = self.det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.obstacle_ratio == pytest.approx(0.1, abs=0.01)


# --- Custom parameters ---

class TestLidarObstacleDetectorCustomParams:

    def test_custom_safety_distance(self):
        det = LidarObstacleDetector(safety_distance_m=1.0, warning_distance_m=1.5)
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        for i in range(3):
            ranges[i] = 0.9
        result = det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is True
        assert result.zone == "danger"

    def test_ignore_behind_enabled(self):
        det = LidarObstacleDetector(ignore_behind=True)
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        # obstacle only behind (180 deg)
        idx = index_for_deg(180)
        for i in range(idx - 1, idx + 2):
            ranges[i % 120] = 0.3
        result = det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is False

    def test_ignore_behind_disabled(self):
        det = LidarObstacleDetector(ignore_behind=False)
        ranges, a_min, a_inc, r_min, r_max = make_scan()
        idx = index_for_deg(180)
        for i in range(idx - 1, idx + 2):
            ranges[i % 120] = 0.3
        result = det.detect(ranges, a_min, a_inc, r_min, r_max)
        assert result.is_obstacle is True
