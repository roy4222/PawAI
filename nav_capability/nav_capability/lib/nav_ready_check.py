"""Pure-Python helper for capability_publisher_node nav_ready decision (Phase A Step 3).

Basic version: nav_ready iff
  1. /amcl_pose has been seen at least once (latched check)
  2. Last received covariance_xy = c[0]+c[7] < covariance_threshold
  3. Pose age < max_pose_age_s (large safety net — see comment below)

Note on pose age: AMCL is event-driven, not a heartbeat. A stationary robot will
stop republishing /amcl_pose, which would falsely trip a tight age check. Default
max_pose_age_s is therefore deliberately generous (60s) — it's a safety net for
"AMCL has crashed", not an SLA on freshness. Tighter freshness comes from the
deferred Nav2 lifecycle service check (Phase A day 2).

Costmap-healthy gate is also deferred to Phase A day 2 (per plan: "costmap
healthy 留明天").

No rclpy / numpy dependency so unit tests can import directly.
"""
from typing import Optional

DEFAULT_COVARIANCE_THRESHOLD = 0.20
# Very generous: AMCL is event-driven, not heartbeat. A stationary Go2 (e.g. just
# after /initialpose set, before any nav goal) may not republish /amcl_pose for
# minutes. This default is the "AMCL truly crashed" safety net, NOT an SLA on
# freshness. Real freshness check belongs to the deferred Nav2 lifecycle service
# probe (Phase A day 2).
DEFAULT_MAX_POSE_AGE_S = 300.0


def compute_nav_ready(
    pose_age_s: Optional[float],
    covariance_xy: Optional[float],
    covariance_threshold: float = DEFAULT_COVARIANCE_THRESHOLD,
    max_pose_age_s: float = DEFAULT_MAX_POSE_AGE_S,
) -> bool:
    """Decide if the nav stack is ready for new goals.

    Args:
        pose_age_s: seconds since last /amcl_pose received. None = never received.
        covariance_xy: c[0] + c[7] from /amcl_pose covariance matrix. None = unknown.
        covariance_threshold: max acceptable covariance (lower = better localized).
        max_pose_age_s: AMCL truly dead threshold (default 60s, see module docstring).

    Returns:
        True iff AMCL has produced at least one pose, latest cov is acceptable,
        and AMCL hasn't been silent for max_pose_age_s.
    """
    if pose_age_s is None or covariance_xy is None:
        return False
    if pose_age_s > max_pose_age_s:
        return False
    if covariance_xy >= covariance_threshold:
        return False
    return True
