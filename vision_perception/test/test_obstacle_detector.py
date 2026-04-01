"""Tests for ObstacleDetector — pure Python/numpy, no ROS2."""
import numpy as np
import pytest

from vision_perception.obstacle_detector import ObstacleDetector, ObstacleResult


class TestObstacleDetectorDefaults:
    """Tests with default parameters (threshold=0.8m, ratio_trigger=0.15)."""

    def setup_method(self):
        self.detector = ObstacleDetector()

    def test_no_obstacle_all_far(self):
        """All pixels at 2.0m → clear, no obstacle."""
        depth = np.full((240, 424), 2.0, dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.is_obstacle is False
        assert result.zone == "clear"
        assert result.distance_min > 1.0

    def test_close_obstacle_triggers(self):
        """Center ROI filled with 0.3m → danger, obstacle detected."""
        depth = np.full((240, 424), 2.0, dtype=np.float32)
        # Fill ROI region (40%-80% height, 20%-80% width) with close obstacle
        depth[96:192, 85:339] = 0.3
        result = self.detector.detect(depth)
        assert result.is_obstacle is True
        assert result.zone == "danger"
        assert result.distance_min < 0.5

    def test_partial_obstacle_below_trigger(self):
        """Only 5% of ROI close → below 15% trigger, no obstacle."""
        depth = np.full((240, 424), 2.0, dtype=np.float32)
        # Fill small portion of ROI
        depth[96:101, 85:100] = 0.3  # ~5 rows x 15 cols = tiny fraction
        result = self.detector.detect(depth)
        assert result.is_obstacle is False

    def test_warning_zone(self):
        """All pixels at 1.0m (between threshold 0.8 and warning 1.2) → warning."""
        depth = np.full((240, 424), 1.0, dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.zone == "warning"
        assert result.is_obstacle is False  # warning doesn't trigger obstacle

    def test_all_invalid_depth(self):
        """All zeros (invalid depth) → clear, no obstacle."""
        depth = np.zeros((240, 424), dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.is_obstacle is False
        assert result.zone == "clear"

    def test_mixed_valid_invalid(self):
        """50% zeros + 50% close → only valid pixels counted for ratio."""
        depth = np.zeros((240, 424), dtype=np.float32)
        # Fill right half of ROI with close obstacle
        depth[96:192, 212:339] = 0.3
        result = self.detector.detect(depth)
        # Should still detect because valid pixels have high obstacle ratio
        assert result.is_obstacle is True
        assert result.distance_min < 0.5


class TestObstacleDetectorCustomParams:
    """Tests with custom parameters."""

    def test_custom_threshold(self):
        """Custom threshold=1.0 → 0.9m triggers obstacle."""
        detector = ObstacleDetector(threshold_m=1.0)
        depth = np.full((240, 424), 0.9, dtype=np.float32)
        result = detector.detect(depth)
        assert result.is_obstacle is True
        assert result.zone == "danger"
