"""TF / quaternion helpers (pure math, no ROS)."""
import math
from typing import Tuple


def yaw_to_quat(yaw: float) -> Tuple[float, float, float, float]:
    """Yaw (rad, around z-axis) → (qx, qy, qz, qw)."""
    half = yaw / 2.0
    return 0.0, 0.0, math.sin(half), math.cos(half)


def quat_to_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    """Quaternion → yaw (rad). z-axis only (planar)."""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)
