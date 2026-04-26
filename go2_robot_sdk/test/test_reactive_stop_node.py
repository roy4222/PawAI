"""Unit tests for reactive_stop_node 純邏輯（不啟動 ROS）。

測 compute_front_min_distance + classify_zone 兩個 module-level helper。
從 lidar_geometry 直接 import（pure Python，避開 package __init__ 的 aioice 檢查）。
"""
import math
import os
import sys

import pytest

# Direct file import bypassing package __init__ (which requires aioice submodule)
_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "go2_robot_sdk")
sys.path.insert(0, _HELPERS_DIR)
from lidar_geometry import classify_zone, compute_front_min_distance  # noqa: E402

# --- Helpers ---

NUM_POINTS = 360


def make_ranges(default_range=5.0):
    """Return ranges array with 1 deg / point, angle_min=0 (sllidar 預設)。"""
    return [default_range] * NUM_POINTS


def deg_index(deg):
    """deg → ranges index（0=front, CCW）。"""
    return int(round(deg / 360.0 * NUM_POINTS)) % NUM_POINTS


ANGLE_MIN = 0.0
ANGLE_INC = 2 * math.pi / NUM_POINTS
FRONT_HALF_RAD = math.radians(30.0)
RANGE_MIN = 0.10
RANGE_MAX = 8.0


# --- compute_front_min_distance ---

class TestFrontMinDistance:
    def test_all_far_returns_default(self):
        ranges = make_ranges(default_range=5.0)
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 5.0

    def test_obstacle_at_front_zero_deg(self):
        ranges = make_ranges()
        ranges[deg_index(0)] = 0.5
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 0.5

    def test_obstacle_at_front_25deg_inside_arc(self):
        ranges = make_ranges()
        ranges[deg_index(25)] = 0.4
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 0.4

    def test_obstacle_at_45deg_outside_arc_ignored(self):
        ranges = make_ranges()
        ranges[deg_index(45)] = 0.3
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 5.0  # 45° 在 ±30° 之外，忽略

    def test_obstacle_behind_180deg_ignored(self):
        ranges = make_ranges()
        ranges[deg_index(180)] = 0.2
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 5.0

    def test_wrap_around_350deg_inside_arc(self):
        """350° 經 atan2 normalize 後 = -10°，落在 ±30° 扇形內。"""
        ranges = make_ranges()
        ranges[deg_index(350)] = 0.6
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 0.6

    def test_inf_skipped(self):
        ranges = make_ranges()
        ranges[deg_index(0)] = float("inf")
        ranges[deg_index(10)] = 0.7
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 0.7

    def test_below_range_min_skipped(self):
        """< 0.10m 視為自身遮蔽，跳過。"""
        ranges = make_ranges()
        ranges[deg_index(0)] = 0.05  # below range_min
        ranges[deg_index(5)] = 1.5
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 1.5

    def test_above_range_max_skipped(self):
        ranges = make_ranges()
        ranges[deg_index(0)] = 10.0  # > range_max
        ranges[deg_index(5)] = 2.0
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 2.0

    def test_no_valid_returns_inf(self):
        ranges = [float("inf")] * NUM_POINTS
        d = compute_front_min_distance(
            ranges, ANGLE_MIN, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == float("inf")

    def test_works_with_negative_angle_min(self):
        """sllidar 也可能 angle_min = -π，扇形仍要正確。"""
        angle_min_neg = -math.pi
        ranges = [5.0] * NUM_POINTS
        # i=180 → angle = -π + 180 * (2π/360) = 0 → 前方
        ranges[180] = 0.4
        d = compute_front_min_distance(
            ranges, angle_min_neg, ANGLE_INC, FRONT_HALF_RAD, RANGE_MIN, RANGE_MAX,
        )
        assert d == 0.4


# --- classify_zone ---

class TestClassifyZone:
    def test_danger_below_danger(self):
        assert classify_zone(0.5, danger_m=0.6, slow_m=1.0) == "danger"

    def test_slow_between(self):
        assert classify_zone(0.8, danger_m=0.6, slow_m=1.0) == "slow"

    def test_clear_above_slow(self):
        assert classify_zone(2.0, danger_m=0.6, slow_m=1.0) == "clear"

    def test_boundary_danger_inclusive_below(self):
        assert classify_zone(0.59, danger_m=0.6, slow_m=1.0) == "danger"

    def test_boundary_at_danger_is_slow(self):
        """d == danger_m 時不算 danger（嚴格小於）。"""
        assert classify_zone(0.6, danger_m=0.6, slow_m=1.0) == "slow"

    def test_inf_is_clear(self):
        assert classify_zone(float("inf"), danger_m=0.6, slow_m=1.0) == "clear"


# --- Phase 1.3 regression: publisher topic + enable_nav_pause param defaults ---


class TestReactiveStopNodeSourceContract:
    """Source-level regression: 驗 reactive_stop_node.py 宣告了正確的 cmd_vel_topic 預設與 enable_nav_pause 參數。

    不啟動 rclpy（與既有 test 風格一致：純邏輯 + source 驗證，避開 aioice 依賴）。
    完整 instantiation 測試留 Phase 10 實機驗收。
    """

    NODE_PATH = os.path.join(
        os.path.dirname(__file__), "..", "go2_robot_sdk", "reactive_stop_node.py"
    )

    def _read_source(self):
        with open(self.NODE_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_declares_cmd_vel_topic_param_default_obstacle(self):
        src = self._read_source()
        assert 'declare_parameter("cmd_vel_topic", "/cmd_vel_obstacle")' in src

    def test_declares_enable_nav_pause_param_default_false(self):
        src = self._read_source()
        assert 'declare_parameter("enable_nav_pause", False)' in src

    def test_publisher_uses_cmd_vel_topic_param(self):
        """publisher must read from cmd_vel_topic param, not hardcoded /cmd_vel."""
        src = self._read_source()
        # No hardcoded /cmd_vel publisher
        assert 'self.create_publisher(Twist, "/cmd_vel"' not in src
        # Uses param-driven topic
        assert "cmd_vel_topic" in src and "self._cmd_pub" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
