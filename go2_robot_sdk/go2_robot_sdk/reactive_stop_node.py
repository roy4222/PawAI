"""Reactive Stop Node — RPLIDAR 反應式停障，4-mode state machine。

訂閱 /scan_rplidar、發布 cmd_vel @ 10Hz（topic 由 cmd_vel_topic param 決定）。

Modes（透過 ROS param `mode`，runtime 可切換）：

  **`hold_brake`** — 永遠 publish 0（permanent brake）
      用途：B5 safety 驗證、demo emergency hold。
      副作用：mux priority 200 永遠贏，nav/teleop 都驅不動 Go2。
      操作員必須主動切 `released` / `disabled` mode 才能讓 Go2 走。
      cmd_vel_topic=/cmd_vel_obstacle 必填（依賴 mux 200）。

  **`progressive`** — danger 發 0、slow/clear 沉默
      用途：搭配 nav stack（priority 10）做漸進避障。
      ⚠️ 已知 mux timeout 風險：clear 後 0.5s 內若 teleop priority 100 還在
      hot-publish，會接管 — 必須搭配「kill teleop / 用 nav goal 不用
      hot-publisher」demo discipline。對應 5/11 B0 fix 前行為。

  **`released`** — 不 publish 但 LiDAR + zone state 仍更新
      用途：操作員主動釋放給 nav 接管。zone 狀態仍在 status JSON 顯示。
      切回 `hold_brake` / `progressive` 才會重新介入控制。

  **`disabled`** — 完全 off，不 publish 也不更新 zone
      用途：全停 reactive_stop 影響，連 LiDAR processing 都跳過。

Standalone fallback（mode="" or unset, safety_only=false legacy）：
  reactive_stop 直接驅動 Go2（nav stack 不在時的 demo 備援）。發 0 / slow /
  normal 三段速。cmd_vel_topic=/cmd_vel。

Backwards compat：`safety_only=True` 等於 mode="hold_brake" 自動 promote。

Phase 7.2 bridge: enable_nav_pause=true → zone transitions trigger /nav/{pause,resume}.
  ⚠️ 在 `hold_brake` mode 下不發 /nav/resume — 因為 nav 仍被 mux 鎖死，發
  resume 會造成 nav state 與實際 mux 輸出矛盾（5/11 night Roy review fix）。
Phase 7-bugfix #5: also publish /state/reactive_stop/status JSON for state_broadcaster.

5/11 B5 burndown 完整 audit + 修法路線圖：
docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0。
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
        # safety_only=true 是 backwards-compat alias，等同 mode="hold_brake"。
        # 推薦直接用 mode param（5/11 night Roy review fix — release gate 不是
        # 永久 brake，需要明確 mode 區分）。
        self.declare_parameter("safety_only", False)
        # Mode：4-state machine（5/11 night redesign）
        #   "hold_brake"  - 永遠 publish 0（B5 safety / demo emergency）
        #   "progressive" - danger=0, slow/clear silent（搭配 nav，需 teleop discipline）
        #   "released"    - 不 publish 但 LiDAR + zone 仍更新（操作員主動釋放）
        #   "disabled"    - 完全 off
        #   ""（預設）    - standalone fallback（reactive 直接驅動 Go2）
        # safety_only=True 會在 init 時 promote 到 "hold_brake" 維持向後相容。
        self.declare_parameter("mode", "")

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
        # Mode resolution: explicit `mode` param wins; safety_only=True promotes
        # to "hold_brake"; otherwise empty → standalone fallback.
        explicit_mode = self.get_parameter("mode").value
        if explicit_mode:
            self._mode = explicit_mode
        elif self._safety_only:
            self._mode = "hold_brake"
        else:
            self._mode = ""  # standalone fallback
        valid_modes = ("hold_brake", "progressive", "released", "disabled", "")
        if self._mode not in valid_modes:
            self.get_logger().warn(
                f"unrecognized mode={self._mode!r}, falling back to 'hold_brake' for safety"
            )
            self._mode = "hold_brake"
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

        mode_label = self._mode if self._mode else "standalone (legacy)"
        self.get_logger().info(
            f"reactive_stop_node started — mode={mode_label}; "
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
                # Promote to mode="hold_brake" if safety_only flipped True
                if self._safety_only and self._mode in ("", "progressive"):
                    self._mode = "hold_brake"
                self.get_logger().info(
                    f"safety_only runtime override -> {self._safety_only} (mode={self._mode!r})"
                )
            elif p.name == "mode":
                new_mode = str(p.value)
                if new_mode not in ("hold_brake", "progressive", "released", "disabled", ""):
                    self.get_logger().warn(f"reject invalid mode={new_mode!r}")
                    continue
                self._mode = new_mode
                self.get_logger().info(
                    f"mode runtime override -> {self._mode!r}"
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
            # `enable=false` runtime override — same as mode=disabled
            return

        # Mode "disabled" / "released" — early exit (no LiDAR processing for
        # disabled; released still updates zone via _on_scan but doesn't publish).
        if self._mode == "disabled":
            return

        # Warmup applies only to standalone mode (Go2 sport handshake settle).
        # Other modes: no warmup needed — driver handles its own handshake or
        # operator orchestrates manually.
        if not self._warmup_sent and self._mode == "":
            self._publish(0.0)
            self._warmup_sent = True
            return
        self._warmup_sent = True  # flip for non-standalone modes too

        # Emergency stop on LiDAR timeout — publish 0 in EVERY active mode
        # (genuine safety override regardless of mode). Skip in released/disabled
        # since those explicitly relinquish control.
        if self._last_scan_time == 0.0 or (time.monotonic() - self._last_scan_time) > self._lidar_timeout:
            self._update_zone("emergency")
            if self._mode != "released":
                self._publish(0.0)
            return

        instant = self._classify(self._front_min_dist)

        # Hysteresis: only clear danger after N consecutive non-danger frames.
        # During hysteresis countdown we still want to keep stopping (we are
        # still effectively in danger). hold_brake / progressive both publish 0
        # here; standalone publishes 0; released doesn't publish.
        if self._zone == "danger" and instant != "danger":
            self._clear_streak += 1
            if self._clear_streak < self._clear_needed:
                if self._mode != "released":
                    self._publish(0.0)
                return
            self._clear_streak = 0
        else:
            self._clear_streak = 0

        self._update_zone(instant)

        # Publish gate delegated to pure helper. decide_velocity returns:
        #   - float (0.0 / slow_speed / normal_speed) → publish that
        #   - None → don't publish (silent)
        vel = decide_velocity(instant, self._mode,
                              self._slow_speed, self._normal_speed)
        if vel is not None:
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
            # B1.6 diagnostic fields (5/11 burndown follow-up + 5/11 night mode redesign)
            "mode": self._mode if self._mode else "standalone",
            "safety_only_legacy": self._safety_only,  # backwards-compat indicator
            "publishes_zero_continuously": self._mode == "hold_brake",  # mux 200 lock indicator
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
        """When enable_nav_pause, call /nav/pause on entering danger and /nav/resume on leaving.

        ⚠️ 5/11 night Roy review fix：在 `hold_brake` mode 下 nav 仍被 mux 鎖死，
        所以發 /nav/resume 會造成 nav state（已 resume）vs 實際輸出（仍被 reactive
        鎖 0）矛盾。`hold_brake` mode 下只發 /nav/pause（保險），不發 /nav/resume。
        """
        if not self._enable_nav_pause:
            return
        # Entering danger — pause nav (always safe, regardless of mode)
        if now_zone == "danger" and prev_zone != "danger" and not self._nav_paused:
            if self._pause_client.service_is_ready():
                self._pause_client.call_async(Trigger.Request())
                self._nav_paused = True
                self.get_logger().info("triggered /nav/pause (obstacle danger)")
            else:
                self.get_logger().debug("/nav/pause service not ready; skipping pause call")
        # Leaving danger — resume nav, BUT skip if hold_brake (mux still locked)
        elif prev_zone == "danger" and now_zone in ("slow", "clear") and self._nav_paused:
            if self._mode == "hold_brake":
                self.get_logger().info(
                    "obstacle cleared but mode=hold_brake → NOT calling /nav/resume "
                    "(would create nav state vs mux output mismatch). Operator must "
                    "switch mode=released or disabled to release reactive_stop, then "
                    "send fresh nav goal."
                )
                # Keep _nav_paused = True until operator releases — reflects reality
                return
            if self._resume_client.service_is_ready():
                self._resume_client.call_async(Trigger.Request())
                self._nav_paused = False
                self.get_logger().info(
                    f"triggered /nav/resume (obstacle cleared, now_zone={now_zone}, mode={self._mode!r})"
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
