"""Standoff goal math: stand 在 target 前 N 公尺、面向 target。"""
import math
from typing import Tuple


def compute_standoff_goal(
    target_x: float,
    target_y: float,
    robot_x: float,
    robot_y: float,
    standoff: float,
) -> Tuple[float, float, float]:
    """Return (goal_x, goal_y, goal_yaw) for stand-off positioning.

    goal 在 robot→target 直線上、距離 target 為 standoff。
    goal_yaw 朝向 target。
    Edge case: robot 已在 target → goal=target, yaw=0。
    """
    dx = target_x - robot_x
    dy = target_y - robot_y
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return target_x, target_y, 0.0
    ux = dx / dist
    uy = dy / dist
    goal_x = target_x - ux * standoff
    goal_y = target_y - uy * standoff
    goal_yaw = math.atan2(dy, dx)
    return goal_x, goal_y, goal_yaw
