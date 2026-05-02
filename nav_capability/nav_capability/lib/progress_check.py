"""Progress check helper for nav_action_server timeout (BUG #2 / A2).

Pure-Python module — no rclpy / ROS dependencies — so unit tests can import it
without bringing in the full ROS2 stack.

Used by `nav_action_server_node._execute_nav_goal_with_pause_aware` to decide
whether the robot is still making forward progress, or whether to abort with
no_progress_timeout.
"""
import math
from typing import Optional, Tuple

# Default thresholds. Imported by both the node and tests so they stay in sync.
PROGRESS_THRESHOLD_M = 0.05
PROGRESS_TIMEOUT_S = 10.0


def has_progress(
    prev_xy: Optional[Tuple[float, float]],
    curr_xy: Optional[Tuple[float, float]],
    threshold: float = PROGRESS_THRESHOLD_M,
) -> bool:
    """True if Euclidean XY distance between two (x, y) tuples is >= threshold.

    Returns False if either input is None — treated as "no info, assume no progress".
    """
    if prev_xy is None or curr_xy is None:
        return False
    return math.hypot(curr_xy[0] - prev_xy[0], curr_xy[1] - prev_xy[1]) >= threshold
