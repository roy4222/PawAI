"""standoff_math: 給目標 (x, y) + robot 當前位置 → 算 stand-off goal pose。"""
import math

from nav_capability.lib.standoff_math import compute_standoff_goal


def test_robot_west_of_target_standoff_1m():
    gx, gy, gyaw = compute_standoff_goal(3.0, 0.0, 0.0, 0.0, 1.0)
    assert abs(gx - 2.0) < 1e-6
    assert abs(gy) < 1e-6
    assert abs(gyaw) < 1e-6


def test_robot_north_of_target_standoff_05m():
    gx, gy, gyaw = compute_standoff_goal(0.0, 0.0, 0.0, 2.0, 0.5)
    assert abs(gx) < 1e-6
    assert abs(gy - 0.5) < 1e-6
    assert abs(gyaw - (-math.pi / 2)) < 1e-6


def test_zero_standoff_at_target():
    gx, gy, _ = compute_standoff_goal(1.0, 1.0, 0.0, 0.0, 0.0)
    assert abs(gx - 1.0) < 1e-6
    assert abs(gy - 1.0) < 1e-6


def test_robot_at_target_returns_target_yaw_zero():
    gx, gy, gyaw = compute_standoff_goal(2.0, 2.0, 2.0, 2.0, 0.5)
    assert abs(gx - 2.0) < 1e-6
    assert abs(gy - 2.0) < 1e-6
    assert abs(gyaw) < 1e-6


def test_diagonal_45deg():
    s = math.sqrt(2) / 2
    gx, gy, gyaw = compute_standoff_goal(1.0, 1.0, 0.0, 0.0, s)
    assert abs(gx - 0.5) < 1e-3
    assert abs(gy - 0.5) < 1e-3
    assert abs(gyaw - math.pi / 4) < 1e-3
