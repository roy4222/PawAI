"""State broadcaster: 持續發 heartbeat + status + safety JSON。

Phase 6.1 implementation of nav_capability spec §3.4.

Subscribes:
  /amcl_pose                       (covariance for safety)
  /scan_rplidar                    (LiDAR alive watchdog)
  /event/nav/internal/status       (custom feed from nav_action / route_runner)

Publishes:
  /state/nav/heartbeat (1Hz, std_msgs/Header)
  /state/nav/status    (10Hz, std_msgs/String JSON)
  /state/nav/safety    (10Hz, std_msgs/String JSON)
"""
import json
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Header, String

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)
SCAN_QOS = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)


class StateBroadcasterNode(Node):
    def __init__(self):
        super().__init__("state_broadcaster_node")

        # Internal status payload — updated by /event/nav/internal/status feeds.
        self._status_payload: dict = {
            "state": "idle",
            "active_goal": None,
            "distance_to_goal": 0.0,
            "eta_sec": 0.0,
            "amcl_covariance_xy": 0.0,
        }
        self._latest_amcl_cov: Optional[float] = None
        self._last_scan_ns: int = 0
        self._last_odom_ns: int = 0  # Phase 8 driver liveness
        # Phase 7-bugfix #5: cache reactive_stop self-reported status; None until first
        # /state/reactive_stop/status arrives. Without this, state_broadcaster used to
        # hardcode reactive_stop_active=false / obstacle_zone=normal even during danger.
        self._latest_reactive_status: Optional[dict] = None

        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl,
            AMCL_QOS,
        )
        self.create_subscription(
            LaserScan,
            "/scan_rplidar",
            self._on_scan,
            SCAN_QOS,
        )
        self.create_subscription(
            String,
            "/event/nav/internal/status",
            self._on_internal_status,
            10,
        )
        self.create_subscription(
            String,
            "/state/reactive_stop/status",
            self._on_reactive_status,
            10,
        )
        self.create_subscription(
            Odometry,
            "/odom",
            self._on_odom,
            QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT),
        )

        self._heartbeat_pub = self.create_publisher(Header, "/state/nav/heartbeat", 10)
        self._status_pub = self.create_publisher(String, "/state/nav/status", 10)
        self._safety_pub = self.create_publisher(String, "/state/nav/safety", 10)

        self.create_timer(1.0, self._tick_heartbeat)
        self.create_timer(0.1, self._tick_status_safety)

        self.get_logger().info("state_broadcaster_node ready (heartbeat/status/safety)")

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        c = msg.pose.covariance
        # spec §8 E1: covariance_xy = sigma_x^2 + sigma_y^2 (diagonal [0]+[7])
        self._latest_amcl_cov = float(c[0] + c[7])
        self._status_payload["amcl_covariance_xy"] = self._latest_amcl_cov

    def _on_scan(self, _msg: LaserScan) -> None:
        self._last_scan_ns = self.get_clock().now().nanoseconds

    def _on_internal_status(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
            self._status_payload.update(payload)
        except json.JSONDecodeError:
            self.get_logger().warn(f"bad internal status JSON: {msg.data!r}")

    def _on_reactive_status(self, msg: String) -> None:
        try:
            self._latest_reactive_status = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f"bad reactive_stop status JSON: {msg.data!r}")

    def _on_odom(self, _msg: Odometry) -> None:
        self._last_odom_ns = self.get_clock().now().nanoseconds

    def _driver_alive(self) -> bool:
        if self._last_odom_ns == 0:
            return False
        now_ns = self.get_clock().now().nanoseconds
        return (now_ns - self._last_odom_ns) < 2_000_000_000

    def _amcl_health(self) -> str:
        cov = self._latest_amcl_cov
        if cov is None:
            return "red"
        if cov < 0.3:
            return "green"
        if cov <= 0.5:
            return "yellow"
        return "red"

    def _lidar_alive(self) -> bool:
        if self._last_scan_ns == 0:
            return False
        now_ns = self.get_clock().now().nanoseconds
        return (now_ns - self._last_scan_ns) < 1_000_000_000  # 1s

    def _tick_heartbeat(self) -> None:
        h = Header()
        h.stamp = self.get_clock().now().to_msg()
        h.frame_id = "nav_capability"
        self._heartbeat_pub.publish(h)

    def _tick_status_safety(self) -> None:
        s = String()
        s.data = json.dumps(self._status_payload)
        self._status_pub.publish(s)

        # Phase 7-bugfix #5: when reactive_stop status hasn't arrived yet, surface
        # 'unknown' rather than fake 'normal'/false to avoid lying to UI/diagnostics.
        if self._latest_reactive_status is None:
            reactive_active = None  # unknown
            obstacle_distance = None
            obstacle_zone = "unknown"
        else:
            r = self._latest_reactive_status
            reactive_active = bool(r.get("reactive_stop_active", False))
            obstacle_distance = r.get("obstacle_distance")  # may be None when inf
            obstacle_zone = r.get("zone", "unknown")

        safety = {
            "reactive_stop_active": reactive_active,
            "obstacle_distance": obstacle_distance,
            "obstacle_zone": obstacle_zone,
            "lidar_alive": self._lidar_alive(),
            "driver_alive": self._driver_alive(),  # Phase 8 — /odom watchdog
            "amcl_health": self._amcl_health(),
            "pause_count_recent_10s": 0,  # TODO Phase 9+: track from /nav/pause calls
        }
        sf = String()
        sf.data = json.dumps(safety)
        self._safety_pub.publish(sf)


def main():
    rclpy.init()
    node = StateBroadcasterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
