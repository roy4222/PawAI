"""Reactive Stop Node — RPLIDAR 反應式停障。

訂閱 /scan_rplidar、發布 /cmd_vel @ 10Hz。
前方 ±30° 扇形最小距離 → stop / slow / normal。
LiDAR 中斷 > 1s 進 emergency stop。
"""
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_srvs.srv import Trigger

from go2_robot_sdk.lidar_geometry import classify_zone, compute_front_min_distance

QOS_SCAN = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_CMD = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class ReactiveStopNode(Node):
    def __init__(self):
        super().__init__("reactive_stop_node")

        self.declare_parameter("scan_topic", "/scan_rplidar")
        self.declare_parameter("danger_distance_m", 0.6)
        self.declare_parameter("slow_distance_m", 1.0)
        self.declare_parameter("slow_speed", 0.45)
        self.declare_parameter("normal_speed", 0.60)
        self.declare_parameter("front_arc_deg", 30.0)
        self.declare_parameter("range_min_m", 0.10)
        self.declare_parameter("range_max_m", 8.0)
        self.declare_parameter("lidar_timeout_s", 1.0)
        self.declare_parameter("clear_debounce_frames", 3)
        self.declare_parameter("publish_rate_hz", 10.0)
        self.declare_parameter("enable", True)
        self.declare_parameter("cmd_vel_topic", "/cmd_vel_obstacle")
        self.declare_parameter("enable_nav_pause", False)

        self._danger_m = self.get_parameter("danger_distance_m").value
        self._slow_m = self.get_parameter("slow_distance_m").value
        self._slow_speed = self.get_parameter("slow_speed").value
        self._normal_speed = self.get_parameter("normal_speed").value
        self._front_half_rad = math.radians(self.get_parameter("front_arc_deg").value)
        self._range_min = self.get_parameter("range_min_m").value
        self._range_max = self.get_parameter("range_max_m").value
        self._lidar_timeout = self.get_parameter("lidar_timeout_s").value
        self._clear_needed = int(self.get_parameter("clear_debounce_frames").value)
        publish_hz = self.get_parameter("publish_rate_hz").value

        scan_topic = self.get_parameter("scan_topic").value
        cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
        self._enable_nav_pause = self.get_parameter("enable_nav_pause").value
        self.create_subscription(LaserScan, scan_topic, self._on_scan, QOS_SCAN)
        self._cmd_pub = self.create_publisher(Twist, cmd_vel_topic, QOS_CMD)
        self.create_timer(1.0 / publish_hz, self._tick)

        # Phase 7.2 — bridge to /nav/pause /nav/resume when enable_nav_pause=true.
        # 預設 false → standalone fallback / no nav stack 安全（不會誤觸 service）。
        self._pause_client = self.create_client(Trigger, "/nav/pause")
        self._resume_client = self.create_client(Trigger, "/nav/resume")
        self._nav_paused = False

        self._last_scan_time = 0.0
        self._front_min_dist = float("inf")
        self._zone = "init"  # init / danger / slow / clear
        self._clear_streak = 0
        self._last_zone_logged = ""
        self._warmup_sent = False

        self.get_logger().info(
            f"reactive_stop_node started — danger<{self._danger_m}m, slow<{self._slow_m}m, "
            f"normal={self._normal_speed} slow_speed={self._slow_speed}, "
            f"front=±{math.degrees(self._front_half_rad):.0f}°, timeout={self._lidar_timeout}s"
        )

    def _on_scan(self, msg: LaserScan):
        self._front_min_dist = compute_front_min_distance(
            list(msg.ranges), msg.angle_min, msg.angle_increment,
            self._front_half_rad, self._range_min, self._range_max,
        )
        self._last_scan_time = time.monotonic()

    def _classify(self, d: float) -> str:
        return classify_zone(d, self._danger_m, self._slow_m)

    def _tick(self):
        if not self.get_parameter("enable").value:
            self._publish(0.0)
            return

        # Warmup: first cmd_vel = 0 to settle Go2 sport mode handshake
        if not self._warmup_sent:
            self._publish(0.0)
            self._warmup_sent = True
            return

        # Emergency stop on LiDAR timeout
        if self._last_scan_time == 0.0 or (time.monotonic() - self._last_scan_time) > self._lidar_timeout:
            self._update_zone("emergency")
            self._publish(0.0)
            return

        instant = self._classify(self._front_min_dist)

        # Hysteresis: only clear danger after N consecutive non-danger frames
        if self._zone == "danger" and instant != "danger":
            self._clear_streak += 1
            if self._clear_streak < self._clear_needed:
                self._publish(0.0)
                return
            self._clear_streak = 0
        else:
            self._clear_streak = 0

        self._update_zone(instant)
        if instant == "danger":
            self._publish(0.0)
        elif instant == "slow":
            self._publish(self._slow_speed)
        else:
            self._publish(self._normal_speed)

    def _publish(self, vx: float):
        cmd = Twist()
        cmd.linear.x = float(vx)
        cmd.angular.z = 0.0
        self._cmd_pub.publish(cmd)

    def _update_zone(self, zone: str):
        prev = self._zone
        self._zone = zone
        if zone != self._last_zone_logged:
            d = self._front_min_dist
            d_str = f"{d:.2f}m" if math.isfinite(d) else "inf"
            self.get_logger().info(f"zone: {self._last_zone_logged or 'init'} → {zone} (front_min={d_str})")
            self._last_zone_logged = zone
        # Phase 7.2: bridge zone transitions to /nav/pause /nav/resume
        self._maybe_call_nav_pause(prev, zone)

    def _maybe_call_nav_pause(self, prev_zone: str, now_zone: str) -> None:
        """When enable_nav_pause, call /nav/pause on entering danger and /nav/resume on leaving."""
        if not self._enable_nav_pause:
            return
        # Entering danger from any non-danger zone (init/clear/slow/emergency)
        if now_zone == "danger" and prev_zone != "danger" and not self._nav_paused:
            if self._pause_client.service_is_ready():
                self._pause_client.call_async(Trigger.Request())
                self._nav_paused = True
                self.get_logger().info("triggered /nav/pause (obstacle danger)")
            else:
                self.get_logger().debug("/nav/pause service not ready; skipping pause call")
        # Leaving danger after _tick's hysteresis already gated the transition
        elif prev_zone == "danger" and now_zone != "danger" and self._nav_paused:
            if self._resume_client.service_is_ready():
                self._resume_client.call_async(Trigger.Request())
                self._nav_paused = False
                self.get_logger().info("triggered /nav/resume (obstacle cleared)")
            else:
                self.get_logger().debug("/nav/resume service not ready; skipping resume call")


def main(args=None):
    rclpy.init(args=args)
    node = ReactiveStopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
