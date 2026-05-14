"""Tests for relative_goal_math: 從 map-frame current pose + (distance, yaw_offset) 算目標。"""
import math

from nav_capability.lib.relative_goal_math import compute_relative_goal


def test_forward_no_yaw_offset_zero_heading():
    gx, gy, gyaw = compute_relative_goal(0.0, 0.0, 0.0, 1.0, 0.0)
    assert abs(gx - 1.0) < 1e-6
    assert abs(gy) < 1e-6
    assert abs(gyaw) < 1e-6


def test_forward_heading_pi_over_2():
    gx, gy, gyaw = compute_relative_goal(0.0, 0.0, math.pi / 2, 1.0, 0.0)
    assert abs(gx) < 1e-6
    assert abs(gy - 1.0) < 1e-6
    assert abs(gyaw - math.pi / 2) < 1e-6


def test_negative_distance_means_backward():
    gx, _, _ = compute_relative_goal(0.0, 0.0, 0.0, -0.5, 0.0)
    assert abs(gx - (-0.5)) < 1e-6


def test_yaw_offset_rotates_direction_and_final_heading():
    gx, gy, gyaw = compute_relative_goal(1.0, 2.0, 0.0, 1.0, math.pi / 2)
    assert abs(gx - 1.0) < 1e-6
    assert abs(gy - 3.0) < 1e-6
    assert abs(gyaw - math.pi / 2) < 1e-6


def test_offset_origin_added_correctly():
    gx, gy, _ = compute_relative_goal(5.0, -3.0, 0.0, 2.0, 0.0)
    assert abs(gx - 7.0) < 1e-6
    assert abs(gy - (-3.0)) < 1e-6
