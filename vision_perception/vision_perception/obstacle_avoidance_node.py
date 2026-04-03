"""ROS2 obstacle avoidance node — subscribes to D435 depth, publishes obstacle events.

Wraps ObstacleDetector with frame-level debounce and rate limiting.
"""
import json
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String

from .obstacle_detector import ObstacleDetector

QOS_EVENT = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_SENSOR = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_STATE = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)


class ObstacleAvoidanceNode(Node):
    def __init__(self):
        super().__init__("obstacle_avoidance_node")

        # Parameters
        self.declare_parameter("threshold_m", 2.0)
        self.declare_parameter("warning_m", 2.5)
        self.declare_parameter("max_range_m", 3.0)
        self.declare_parameter("roi_top_ratio", 0.4)
        self.declare_parameter("roi_bottom_ratio", 0.8)
        self.declare_parameter("roi_left_ratio", 0.2)
        self.declare_parameter("roi_right_ratio", 0.8)
        self.declare_parameter("obstacle_ratio_trigger", 0.15)
        self.declare_parameter("publish_rate_hz", 15.0)
        self.declare_parameter("debounce_frames", 3)
        self.declare_parameter(
            "depth_topic",
            "/camera/camera/aligned_depth_to_color/image_raw",
        )

        self._detector = ObstacleDetector(
            threshold_m=self.get_parameter("threshold_m").value,
            warning_m=self.get_parameter("warning_m").value,
            max_range_m=self.get_parameter("max_range_m").value,
            roi_top_ratio=self.get_parameter("roi_top_ratio").value,
            roi_bottom_ratio=self.get_parameter("roi_bottom_ratio").value,
            roi_left_ratio=self.get_parameter("roi_left_ratio").value,
            roi_right_ratio=self.get_parameter("roi_right_ratio").value,
            obstacle_ratio_trigger=self.get_parameter("obstacle_ratio_trigger").value,
        )

        depth_topic = self.get_parameter("depth_topic").value
        self._pub = self.create_publisher(
            String, "/event/obstacle_detected", QOS_EVENT,
        )
        self._pub_heartbeat = self.create_publisher(
            String, "/state/obstacle/d435_alive", QOS_STATE,
        )
        self.create_subscription(Image, depth_topic, self._on_depth, QOS_SENSOR)

        self._publish_interval = 1.0 / self.get_parameter("publish_rate_hz").value
        self._debounce_needed = int(self.get_parameter("debounce_frames").value)
        self._danger_streak = 0
        self._last_publish_time = 0.0
        self._last_heartbeat_time = 0.0

        self.get_logger().info(
            f"ObstacleAvoidanceNode started — threshold={self._detector.threshold_m}m, "
            f"debounce={self._debounce_needed} frames"
        )

    def _on_depth(self, msg: Image):
        # Convert uint16 mm → float32 meters
        depth_mm = np.frombuffer(msg.data, dtype=np.uint16).reshape(
            msg.height, msg.width,
        )
        depth_m = depth_mm.astype(np.float32) / 1000.0

        result = self._detector.detect(depth_m)

        # Frame-level debounce
        if result.zone == "danger":
            self._danger_streak += 1
        else:
            self._danger_streak = 0

        # Log zone at debug level
        self.get_logger().debug(
            f"zone={result.zone} min={result.distance_min:.2f}m "
            f"ratio={result.obstacle_ratio:.2f} streak={self._danger_streak}"
        )

        # Publish only when debounce threshold met + rate limited
        now = time.monotonic()
        if (
            self._danger_streak >= self._debounce_needed
            and (now - self._last_publish_time) >= self._publish_interval
        ):
            # C3 fix: avoid float("inf") in JSON (non-standard)
            dist_min = round(result.distance_min, 3) if result.distance_min != float("inf") else None
            event = {
                "stamp": time.time(),
                "event_type": "obstacle_detected",
                "distance_min": dist_min,
                "obstacle_ratio": round(result.obstacle_ratio, 3),
                "zone": result.zone,
            }
            out = String()
            out.data = json.dumps(event)
            self._pub.publish(out)
            self._last_publish_time = now
            self.get_logger().info(
                f"OBSTACLE: min={result.distance_min:.2f}m "
                f"ratio={result.obstacle_ratio:.0%}"
            )

        # Heartbeat: signal that this node is alive and processing depth
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
    node = ObstacleAvoidanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
