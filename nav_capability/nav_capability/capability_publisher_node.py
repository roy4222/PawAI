"""Capability Publisher — publishes /capability/nav_ready (Phase A Step 3 basic version).

Aggregates AMCL freshness + covariance into a single latched Bool that downstream
skills (Brain Executive, SafetyLayer) consult before launching nav skills.

This is the BASIC version per Phase A plan. Conditions:
  /amcl_pose received at least once within max_pose_age_s (default 300s — large
    safety net for "AMCL truly dead", NOT an SLA on freshness; AMCL is event-
    driven and won't republish for a stationary robot. Real freshness comes
    from the deferred Nav2 lifecycle service probe.)  AND
  covariance_xy < covariance_threshold (default 0.20)

Deferred to Phase A day 2 (NOT in this version):
  * Nav2 lifecycle active gate (use /lifecycle_manager_navigation/get_state)
  * local_costmap healthy gate (last_seen ≤ 2s)
  * target-cell cost check (skill-dispatch-time, not capability-gate-time)

**Threshold note**: default covariance_threshold=0.20 is the spec target, but
empirical Go2 + v8 map after `/initialpose` settles around 0.30-0.40. For demo
stack startup pass --ros-args -p covariance_threshold:=0.40 until AMCL has
moved enough to converge. See docs/navigation/CLAUDE.md for runbook.

Manual launch (no integration into interaction_executive.launch.py yet):

    ros2 run nav_capability capability_publisher_node \\
        --ros-args -p covariance_threshold:=0.40

Validate:

    ros2 topic echo /capability/nav_ready --once
    # set /initialpose, wait for AMCL → covariance < threshold → flips true
"""
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from std_msgs.msg import Bool

from nav_capability.lib.nav_ready_check import (
    DEFAULT_COVARIANCE_THRESHOLD,
    DEFAULT_MAX_POSE_AGE_S,
    compute_nav_ready,
)


# AMCL publishes /amcl_pose with TRANSIENT_LOCAL durability.
AMCL_QOS = QoSProfile(
    depth=10,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# Latched + reliable so late subscribers (Brain, Executive) immediately see state.
NAV_READY_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class CapabilityPublisherNode(Node):
    def __init__(self):
        super().__init__("capability_publisher_node")

        # ── Params ──
        self.declare_parameter("covariance_threshold", DEFAULT_COVARIANCE_THRESHOLD)
        self.declare_parameter("max_pose_age_s", DEFAULT_MAX_POSE_AGE_S)
        self.declare_parameter("publish_rate_hz", 1.0)
        self._cov_threshold = float(self.get_parameter("covariance_threshold").value)
        self._max_pose_age_s = float(self.get_parameter("max_pose_age_s").value)
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        # ── State ──
        self._last_pose_ns: Optional[int] = None
        self._last_cov_xy: Optional[float] = None
        self._last_ready_published: Optional[bool] = None

        # ── I/O ──
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl_pose, AMCL_QOS
        )
        self._pub = self.create_publisher(
            Bool, "/capability/nav_ready", NAV_READY_QOS
        )

        # Initial value (conservative: false until we have evidence)
        self._publish(False)
        self._last_ready_published = False

        period_s = 1.0 / max(0.1, publish_rate_hz)
        self.create_timer(period_s, self._tick)

        self.get_logger().info(
            f"capability_publisher_node ready @ {publish_rate_hz}Hz tick "
            f"(cov_threshold={self._cov_threshold} max_pose_age={self._max_pose_age_s}s)"
        )

    # ── Subscriptions ──
    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self._last_pose_ns = self.get_clock().now().nanoseconds
        c = msg.pose.covariance
        self._last_cov_xy = float(c[0] + c[7])  # σ²x + σ²y diagonal

    # ── Tick ──
    def _tick(self) -> None:
        if self._last_pose_ns is None:
            pose_age_s = None
        else:
            pose_age_s = (self.get_clock().now().nanoseconds - self._last_pose_ns) / 1e9

        ready = compute_nav_ready(
            pose_age_s=pose_age_s,
            covariance_xy=self._last_cov_xy,
            covariance_threshold=self._cov_threshold,
            max_pose_age_s=self._max_pose_age_s,
        )
        self._publish(ready)

        if ready != self._last_ready_published:
            cov_str = (
                f"{self._last_cov_xy:.3f}" if self._last_cov_xy is not None else "?"
            )
            age_str = f"{pose_age_s:.2f}s" if pose_age_s is not None else "never"
            self.get_logger().info(
                f"/capability/nav_ready -> {ready} (cov_xy={cov_str} pose_age={age_str})"
            )
            self._last_ready_published = ready

    def _publish(self, ready: bool) -> None:
        msg = Bool()
        msg.data = bool(ready)
        self._pub.publish(msg)


def main():
    rclpy.init()
    node = CapabilityPublisherNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
