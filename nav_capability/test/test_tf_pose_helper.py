"""Tests for tf_pose_helper: quaternion ↔ yaw conversion (pure math, no ROS)."""
import math

from nav_capability.lib.tf_pose_helper import quat_to_yaw, yaw_to_quat


def test_yaw_zero_to_quat():
    qx, qy, qz, qw = yaw_to_quat(0.0)
    assert abs(qz) < 1e-6
    assert abs(qw - 1.0) < 1e-6


def test_yaw_pi_over_2_to_quat():
    qx, qy, qz, qw = yaw_to_quat(math.pi / 2)
    assert abs(qz - math.sin(math.pi / 4)) < 1e-6
    assert abs(qw - math.cos(math.pi / 4)) < 1e-6


def test_quat_to_yaw_zero():
    yaw = quat_to_yaw(0.0, 0.0, 0.0, 1.0)
    assert abs(yaw) < 1e-6


def test_quat_to_yaw_pi():
    yaw = quat_to_yaw(0.0, 0.0, 1.0, 0.0)
    assert abs(abs(yaw) - math.pi) < 1e-6


def test_round_trip():
    for yaw in [0.0, 0.5, -1.2, math.pi / 3, -math.pi / 4]:
        q = yaw_to_quat(yaw)
        yaw_back = quat_to_yaw(*q)
        assert abs(yaw_back - yaw) < 1e-6
