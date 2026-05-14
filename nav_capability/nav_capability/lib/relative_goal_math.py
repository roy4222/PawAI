"""Relative goal math: 從 map-frame current pose + (distance, yaw_offset) 算目標 pose。

純函式，no ROS 依賴。
"""
import math
from typing import Tuple


def compute_relative_goal(
    current_x: float,
    current_y: float,
    current_yaw: float,
    distance: float,
    yaw_offset: float,
) -> Tuple[float, float, float]:
    """Return (goal_x, goal_y, goal_yaw) in same frame as current_*.

    Args:
        current_x, current_y: 當前 map-frame 位置 (m)
        current_yaw: 當前 yaw (rad)
        distance: 沿 (current_yaw + yaw_offset) 走多少 (m)，可為負（後退）
        yaw_offset: 相對當前 heading 的偏移角 (rad)

    Returns:
        (goal_x, goal_y, goal_yaw)，goal_yaw = current_yaw + yaw_offset
    """
    target_heading = current_yaw + yaw_offset
    goal_x = current_x + distance * math.cos(target_heading)
    goal_y = current_y + distance * math.sin(target_heading)
    goal_yaw = target_heading
    return goal_x, goal_y, goal_yaw
