"""ROS2 LiDAR obstacle node — subscribes to /scan, publishes obstacle events.

Wraps LidarObstacleDetector with frame-level debounce and rate limiting.
"""
import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

from .lidar_obstacle_detector import LidarObstacleDetector

QOS_EVENT = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_SENSOR = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_STATE = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)


class LidarObstacleNode(Node):
    def __init__(self):
        super().__init__("lidar_obstacle_node")

        # Parameters
        self.declare_parameter("safety_distance_m", 0.5)
        self.declare_parameter("warning_distance_m", 0.8)
        self.declare_parameter("min_obstacle_points", 2)
        self.declare_parameter("ignore_behind", False)
        self.declare_parameter("publish_rate_hz", 5.0)
        self.declare_parameter("debounce_frames", 3)
        self.declare_parameter("scan_topic", "/scan")

        self._detector = LidarObstacleDetector(
            safety_distance_m=self.get_parameter("safety_distance_m").value,
            warning_distance_m=self.get_parameter("warning_distance_m").value,
            min_obstacle_points=int(self.get_parameter("min_obstacle_points").value),
            ignore_behind=self.get_parameter("ignore_behind").value,
        )

        scan_topic = self.get_parameter("scan_topic").value
        self._pub = self.create_publisher(
            String, "/event/obstacle_detected", QOS_EVENT,
        )
        self._pub_heartbeat = self.create_publisher(
            String, "/state/obstacle/lidar_alive", QOS_STATE,
        )
        self.create_subscription(LaserScan, scan_topic, self._on_scan, QOS_SENSOR)

        self._publish_interval = 1.0 / self.get_parameter("publish_rate_hz").value
        self._debounce_needed = int(self.get_parameter("debounce_frames").value)
        self._danger_streak = 0
        self._last_publish_time = 0.0
        self._last_heartbeat_time = 0.0

        self.get_logger().info(
            f"LidarObstacleNode started — safety={self._detector.safety_distance_m}m, "
            f"debounce={self._debounce_needed} frames, topic={scan_topic}"
        )

    def _on_scan(self, msg: LaserScan):
        result = self._detector.detect(
            ranges=list(msg.ranges),
            angle_min=msg.angle_min,
            angle_increment=msg.angle_increment,
            range_min=msg.range_min,
            range_max=msg.range_max,
        )

        # Frame-level debounce
        if result.zone == "danger":
            self._danger_streak += 1
        else:
            self._danger_streak = 0

        self.get_logger().debug(
            f"zone={result.zone} min={result.distance_min:.2f}m "
            f"dir={result.direction_deg:.0f}deg "
            f"count={result.obstacle_count} streak={self._danger_streak}"
        )

        # Publish only when debounce threshold met + rate limited
        now = time.monotonic()
        if (
            self._danger_streak >= self._debounce_needed
            and (now - self._last_publish_time) >= self._publish_interval
        ):
            event = {
                "stamp": time.time(),
                "event_type": "obstacle_detected",
                "source": "lidar",
                "distance_min": round(result.distance_min, 3),
                "obstacle_ratio": round(result.obstacle_ratio, 3),
                "zone": result.zone,
                "direction_deg": round(result.direction_deg, 1),
            }
            out = String()
            out.data = json.dumps(event)
            self._pub.publish(out)
            self._last_publish_time = now
            self.get_logger().info(
                f"OBSTACLE(lidar): min={result.distance_min:.2f}m "
                f"dir={result.direction_deg:.0f}deg "
                f"count={result.obstacle_count}"
            )

        # Heartbeat: signal that this node is alive and processing scans
        now_hb = time.monotonic()
        if (now_hb - self._last_heartbeat_time) >= 0.5:
            hb = String()
            hb.data = json.dumps({
                "stamp": time.time(), "zone": result.zone,
            })
            self._pub_heartbeat.publish(hb)
            self._last_heartbeat_time = now_hb


def main(args=None):
    rclpy.init(args=args)
    node = LidarObstacleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
