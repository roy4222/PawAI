"""Reactive Stop Node — RPLIDAR 反應式停障。

訂閱 /scan_rplidar、發布 cmd_vel @ 10Hz（topic 由 cmd_vel_topic param 決定）。

Two operating modes:

  Standalone fallback (default; safety_only=false, cmd_vel_topic=/cmd_vel):
    Drive Go2 directly. Always publish:
      danger    → 0.0
      slow      → slow_speed (0.45)
      normal    → normal_speed (0.60)
    For demo backup when nav stack is down.

  Safety mode (safety_only=true, cmd_vel_topic=/cmd_vel_obstacle):
    **ALWAYS publish 0** to keep mux priority 200 alive. This prevents the
    0.5s mux timeout from handing control back to stale teleop / nav cmd_vel
    that may still be hot-publishing at e.g. 0.5 m/s.

      ANY zone → 0.0  (mux priority 200 永遠蓋住 teleop 100 / nav 10)

    Why ALWAYS-0 (not "silent in clear"): On 5/11 B5 burndown Go2 walked into
    a 1.5m obstacle because reactive_stop went silent on clear, mux 0.5s
    timeout, and the still-hot-publishing /cmd_vel_joy=0.5 took over. With
    always-0 the operator MUST actively kill teleop or send a fresh nav goal
    to make Go2 move — clear is "解除煞車" not "安全恢復前進".

    Tradeoff: nav (priority 10) cannot drive Go2 while reactive_stop is up
    in safety_only mode. Demo operator must explicitly disable reactive_stop
    or configure mux differently when nav is the desired driver. Acceptable
    for demo because we're focused on safety, not autonomy depth.

Phase 7.2 bridge: enable_nav_pause=true → zone transitions trigger /nav/{pause,resume}.
Phase 7-bugfix #5: also publish /state/reactive_stop/status JSON for state_broadcaster.

5/11 B5 burndown fix: see
docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0.
"""
import json
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from std_srvs.srv import Trigger

from go2_robot_sdk.lidar_geometry import (
    classify_zone,
    compute_front_min_distance,
    decide_velocity,
)

QOS_SCAN = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_CMD = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class ReactiveStopNode(Node):
    def __init__(self):
        super().__init__("reactive_stop_node")

        self.declare_parameter("scan_topic", "/scan_rplidar")
        # 5/11 B5 burndown fix: thresholds enlarged from 0.6/1.0 to 1.1/1.7
        # because previous values were LiDAR-frame distances (LiDAR mounted
        # base_link+0.175m); Go2 nose at base_link+~0.40m, so LiDAR at 0.6m
        # = nose at 0.2m + 0.5m/s × 0.3s reaction → guaranteed collision.
        # New 1.1m gives ~0.7m nose buffer for braking + body inertia.
        # See docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0.3.
        self.declare_parameter("danger_distance_m", 1.1)
        self.declare_parameter("slow_distance_m", 1.7)
        self.declare_parameter("slow_speed", 0.45)
        self.declare_parameter("normal_speed", 0.60)
        self.declare_parameter("front_arc_deg", 30.0)
        # v8 mount yaw=π → laser frame 0° = Go2 後方；要 detect Go2 前方需設 π。
        # 預設 0（傳統 mount：laser 0° = Go2 前方）。向後相容。
        # 5/11 B1.5 note: this param 與 base_link→laser TF yaw 是雙重套用設計,
        # 兩者必須一致（TF yaw=π 時此 param 也設 π）。改 mount 角度時兩處都要改。
        # See lidar_geometry.compute_front_min_distance docstring.
        self.declare_parameter("front_offset_rad", 0.0)
        self.declare_parameter("range_min_m", 0.10)
        self.declare_parameter("range_max_m", 8.0)
        self.declare_parameter("lidar_timeout_s", 1.0)
        # 5/11 B0.4: bumped 3 → 5 frames (~0.5s @ 10Hz) for stability against
        # boundary jitter at 1.1m danger threshold (sensor noise zone).
        self.declare_parameter("clear_debounce_frames", 5)
        self.declare_parameter("publish_rate_hz", 10.0)
        self.declare_parameter("enable", True)
        self.declare_parameter("cmd_vel_topic", "/cmd_vel_obstacle")
        self.declare_parameter("enable_nav_pause", False)
        # safety_only=true: ALWAYS publish 0 (5/11 B5 burndown fix).
        # Previously slow/clear were silent → mux 0.5s timeout handed control
        # back to stale teleop/nav. Now mux priority 200 is held forever
        # while reactive_stop is up; operator must explicitly disable to allow
        # nav/teleop. See top-of-file docstring for tradeoff.
        self.declare_parameter("safety_only", False)

        self._danger_m = self.get_parameter("danger_distance_m").value
        self._slow_m = self.get_parameter("slow_distance_m").value
        self._slow_speed = self.get_parameter("slow_speed").value
        self._normal_speed = self.get_parameter("normal_speed").value
        self._front_half_rad = math.radians(self.get_parameter("front_arc_deg").value)
        self._front_offset = self.get_parameter("front_offset_rad").value
        self._range_min = self.get_parameter("range_min_m").value
        self._range_max = self.get_parameter("range_max_m").value
        self._lidar_timeout = self.get_parameter("lidar_timeout_s").value
        self._clear_needed = int(self.get_parameter("clear_debounce_frames").value)
        publish_hz = self.get_parameter("publish_rate_hz").value

        scan_topic = self.get_parameter("scan_topic").value
        cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
        self._enable_nav_pause = self.get_parameter("enable_nav_pause").value
        self._safety_only = self.get_parameter("safety_only").value
        self.create_subscription(LaserScan, scan_topic, self._on_scan, QOS_SCAN)
        self._cmd_pub = self.create_publisher(Twist, cmd_vel_topic, QOS_CMD)
        # Phase 7-bugfix #5: status JSON for state_broadcaster to consume
        self._status_pub = self.create_publisher(
            String, "/state/reactive_stop/status", 10
        )
        self.create_timer(1.0 / publish_hz, self._tick)
        self.create_timer(0.1, self._tick_status)  # 10Hz status broadcast

        # Phase 7.2 — bridge to /nav/pause /nav/resume when enable_nav_pause=true.
        # 預設 false → standalone fallback / no nav stack 安全（不會誤觸 service）。
        self._pause_client = self.create_client(Trigger, "/nav/pause")
        self._resume_client = self.create_client(Trigger, "/nav/resume")
        self._nav_paused = False
        # Runtime override: ros2 param set /reactive_stop_node enable_nav_pause true
        self.add_on_set_parameters_callback(self._on_param_change)

        self._last_scan_time = 0.0
        self._front_min_dist = float("inf")
        self._zone = "init"  # init / danger / slow / clear / emergency
        self._clear_streak = 0
        self._last_zone_logged = ""
        self._last_zone_change_t = time.monotonic()  # B1.6 status diagnostics
        self._warmup_sent = False

        mode = "safety_only (ALWAYS publish 0 — hold mux priority 200)" if self._safety_only \
               else "standalone (always publish 0/slow/normal)"
        self.get_logger().info(
            f"reactive_stop_node started — mode={mode}; "
            f"danger<{self._danger_m}m, slow<{self._slow_m}m, "
            f"normal={self._normal_speed} slow_speed={self._slow_speed}, "
            f"front=±{math.degrees(self._front_half_rad):.0f}° (offset={math.degrees(self._front_offset):+.0f}°), timeout={self._lidar_timeout}s; "
            f"publish_topic={cmd_vel_topic}, clear_debounce={self._clear_needed} frames"
        )

    def _on_param_change(self, params):
        for p in params:
            if p.name == "enable_nav_pause":
                self._enable_nav_pause = bool(p.value)
                self.get_logger().info(
                    f"enable_nav_pause runtime override -> {self._enable_nav_pause}"
                )
            elif p.name == "safety_only":
                self._safety_only = bool(p.value)
                self.get_logger().info(
                    f"safety_only runtime override -> {self._safety_only}"
                )
        return SetParametersResult(successful=True)

    def _on_scan(self, msg: LaserScan):
        self._front_min_dist = compute_front_min_distance(
            list(msg.ranges), msg.angle_min, msg.angle_increment,
            self._front_half_rad, self._range_min, self._range_max,
            self._front_offset,
        )
        self._last_scan_time = time.monotonic()

    def _classify(self, d: float) -> str:
        return classify_zone(d, self._danger_m, self._slow_m)

    def _tick(self):
        if not self.get_parameter("enable").value:
            # Disabled — publish 0 in standalone (driver expects regular cmd_vel)
            # but stay silent in safety_only (don't shadow nav).
            if not self._safety_only:
                self._publish(0.0)
            return

        # Warmup applies only to standalone mode (Go2 sport handshake settle).
        # safety_only: no warmup needed — nav stack handles its own driver handshake.
        if not self._warmup_sent and not self._safety_only:
            self._publish(0.0)
            self._warmup_sent = True
            return
        self._warmup_sent = True  # also flip in safety_only so guard is consistent

        # Emergency stop on LiDAR timeout — publish 0 in BOTH modes (genuine override)
        if self._last_scan_time == 0.0 or (time.monotonic() - self._last_scan_time) > self._lidar_timeout:
            self._update_zone("emergency")
            self._publish(0.0)
            return

        instant = self._classify(self._front_min_dist)

        # Hysteresis: only clear danger after N consecutive non-danger frames.
        # During hysteresis countdown we still want to keep stopping in BOTH modes
        # (we are still effectively in danger).
        if self._zone == "danger" and instant != "danger":
            self._clear_streak += 1
            if self._clear_streak < self._clear_needed:
                self._publish(0.0)
                return
            self._clear_streak = 0
        else:
            self._clear_streak = 0

        self._update_zone(instant)

        # Publish gate decision delegated to pure helper for testability.
        # safety_only=True → ALWAYS 0 (B0.1 release gate fix, 5/11 B5 burndown).
        # standalone → 0 / slow / normal by zone.
        vel = decide_velocity(instant, self._safety_only,
                              self._slow_speed, self._normal_speed)
        self._publish(vel)

    def _publish(self, vx: float):
        cmd = Twist()
        cmd.linear.x = float(vx)
        cmd.angular.z = 0.0
        self._cmd_pub.publish(cmd)

    def _tick_status(self):
        d = self._front_min_dist
        now = time.monotonic()
        payload = {
            "zone": self._zone,
            "obstacle_distance": float(d) if math.isfinite(d) else None,
            "reactive_stop_active": self._zone in ("danger", "emergency"),
            "nav_paused": self._nav_paused,
            "enable_nav_pause": self._enable_nav_pause,
            # B1.6 diagnostic fields (5/11 burndown follow-up)
            "safety_only": self._safety_only,
            "always_publishing_zero": self._safety_only,  # B0.1 indicator
            "danger_threshold_m": self._danger_m,
            "slow_threshold_m": self._slow_m,
            "clear_streak": self._clear_streak,
            "since_last_zone_change_sec": round(now - self._last_zone_change_t, 2),
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._status_pub.publish(msg)

    def _update_zone(self, zone: str):
        prev = self._zone
        self._zone = zone
        if zone != self._last_zone_logged:
            d = self._front_min_dist
            d_str = f"{d:.2f}m" if math.isfinite(d) else "inf"
            self.get_logger().info(f"zone: {self._last_zone_logged or 'init'} → {zone} (front_min={d_str})")
            self._last_zone_logged = zone
            self._last_zone_change_t = time.monotonic()  # B1.6: track for status diagnostics
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
        # Leaving danger to a *safe* zone (slow / clear).
        # Explicitly NOT resuming on emergency or init — emergency means LiDAR is dead,
        # which is unsafe for nav to continue; init is a startup transient (only seen
        # before _tick runs).
        elif prev_zone == "danger" and now_zone in ("slow", "clear") and self._nav_paused:
            if self._resume_client.service_is_ready():
                self._resume_client.call_async(Trigger.Request())
                self._nav_paused = False
                self.get_logger().info(
                    f"triggered /nav/resume (obstacle cleared, now_zone={now_zone})"
                )
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
