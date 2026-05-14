"""Depth Safety Node — D435 depth → /capability/depth_clear.

Phase A capability gate. Subscribes to the aligned-depth image stream from
RealSense (PawAI uses the double `/camera/camera/...` namespace) and publishes
a latched Bool on `/capability/depth_clear`:

  true  = recent depth frame seen AND ROI in front of robot has no obstacle
  false = no obstacle data (camera silent / dead) OR obstacle detected in ROI

**Fail-closed semantics**: this is a safety gate. Initial state = false (no
data). Publishes false if depth frame is older than max_frame_age_s (default
1.0s) — camera unplug / driver crash / topic stall must NOT leave the gate
stuck at the previous true value.

This is intentionally a *capability gate* — not a controller. It does NOT
publish /cmd_vel and does NOT pause Nav2. Brain Executive / SafetyLayer is
responsible for consulting /capability/depth_clear before launching nav skills,
and reactive_stop_node handles the actual emergency stop on LiDAR.

Manual launch (no integration into interaction_executive.launch.py yet):

    ros2 run go2_robot_sdk depth_safety_node

Validate:

    ros2 topic echo /capability/depth_clear --once
    # hand 30cm in front of D435 → false
    # remove → true
    # unplug D435 → false within max_frame_age_s
"""
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import Image
from std_msgs.msg import Bool

from go2_robot_sdk.depth_geometry import (
    DEFAULT_DANGER_PIXEL_RATIO,
    DEFAULT_MIN_VALID_DEPTH_M,
    DEFAULT_ROI_HEIGHT_RATIO,
    DEFAULT_ROI_WIDTH_RATIO,
    DEFAULT_STOP_DISTANCE_M,
    compute_depth_clear,
)


# Latched + reliable so late subscribers (Brain, Executive) immediately get the
# last known clear state instead of waiting for the next 5Hz tick.
DEPTH_CLEAR_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# Camera depth often comes in as BEST_EFFORT (RealSense default). Match it.
DEPTH_IMAGE_QOS = QoSProfile(
    depth=5,
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
)


class DepthSafetyNode(Node):
    def __init__(self):
        super().__init__("depth_safety_node")

        # ── Params ──
        self.declare_parameter(
            "depth_topic", "/camera/camera/aligned_depth_to_color/image_raw"
        )
        self.declare_parameter("stop_distance_m", DEFAULT_STOP_DISTANCE_M)
        self.declare_parameter("min_valid_depth_m", DEFAULT_MIN_VALID_DEPTH_M)
        self.declare_parameter("roi_width_ratio", DEFAULT_ROI_WIDTH_RATIO)
        self.declare_parameter("roi_height_ratio", DEFAULT_ROI_HEIGHT_RATIO)
        self.declare_parameter("danger_pixel_ratio", DEFAULT_DANGER_PIXEL_RATIO)
        self.declare_parameter("publish_rate_hz", 5.0)
        # Fail-closed safety: if no fresh depth frame within this window, force
        # depth_clear=false. Catches camera unplug / driver crash / topic stall.
        self.declare_parameter("max_frame_age_s", 1.0)

        self._stop_distance_m = float(self.get_parameter("stop_distance_m").value)
        self._min_valid_depth_m = float(self.get_parameter("min_valid_depth_m").value)
        self._roi_width_ratio = float(self.get_parameter("roi_width_ratio").value)
        self._roi_height_ratio = float(self.get_parameter("roi_height_ratio").value)
        self._danger_pixel_ratio = float(self.get_parameter("danger_pixel_ratio").value)
        self._max_frame_age_s = float(self.get_parameter("max_frame_age_s").value)
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        depth_topic = self.get_parameter("depth_topic").value

        # ── State ──
        self._latest_depth_m = None  # numpy float32, units meters
        self._latest_info = None
        self._latest_frame_ns: int = 0  # 0 = no frame ever received
        self._last_clear_published = None  # for change-only logging
        self._frame_count = 0

        # ── I/O ──
        self.create_subscription(
            Image, depth_topic, self._on_depth, DEPTH_IMAGE_QOS
        )
        self._pub = self.create_publisher(
            Bool, "/capability/depth_clear", DEPTH_CLEAR_QOS
        )

        # Fail-closed initial state: no depth data yet → not clear.
        self._publish(False)
        self._last_clear_published = False

        # Periodic tick — re-evaluate latest frame and publish.
        period_s = 1.0 / max(0.1, publish_rate_hz)
        self.create_timer(period_s, self._tick)

        self.get_logger().info(
            f"depth_safety_node ready; subscribing {depth_topic} @ {publish_rate_hz}Hz tick"
            f" (stop={self._stop_distance_m}m roi={self._roi_width_ratio}x{self._roi_height_ratio}"
            f" danger_ratio={self._danger_pixel_ratio} max_frame_age={self._max_frame_age_s}s)"
        )

    # ── Subscriptions ──
    def _on_depth(self, msg: Image) -> None:
        """Decode incoming 16UC1 (mm) or 32FC1 (m) depth image to float32 metres."""
        if msg.encoding == "16UC1":
            # uint16 millimetres
            arr = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)
            depth_m = arr.astype(np.float32) / 1000.0
        elif msg.encoding == "32FC1":
            # float32 metres
            depth_m = np.frombuffer(msg.data, dtype=np.float32).reshape(
                msg.height, msg.width
            )
        else:
            self.get_logger().warn(
                f"unsupported depth encoding '{msg.encoding}'; expected 16UC1 or 32FC1"
            )
            return
        # Zero in 16UC1 means "no reading" — treat as NaN to be filtered as invalid.
        depth_m = np.where(depth_m <= 0.0, np.nan, depth_m)
        self._latest_depth_m = depth_m
        self._latest_frame_ns = self.get_clock().now().nanoseconds
        self._frame_count += 1

    # ── Tick ──
    def _tick(self) -> None:
        # Fail-closed: never received a frame → false.
        if self._latest_depth_m is None or self._latest_frame_ns == 0:
            self._publish(False)
            if self._last_clear_published is not False:
                self.get_logger().warn(
                    "/capability/depth_clear -> False (no depth frame received yet)"
                )
                self._last_clear_published = False
            return

        # Fail-closed: depth frame stale (camera unplugged / driver crashed) → false.
        frame_age_s = (self.get_clock().now().nanoseconds - self._latest_frame_ns) / 1e9
        if frame_age_s > self._max_frame_age_s:
            self._publish(False)
            if self._last_clear_published is not False:
                self.get_logger().warn(
                    f"/capability/depth_clear -> False "
                    f"(depth frame stale: {frame_age_s:.2f}s > {self._max_frame_age_s:.2f}s)"
                )
                self._last_clear_published = False
            return

        try:
            clear, info = compute_depth_clear(
                self._latest_depth_m,
                stop_distance_m=self._stop_distance_m,
                min_valid_depth_m=self._min_valid_depth_m,
                roi_width_ratio=self._roi_width_ratio,
                roi_height_ratio=self._roi_height_ratio,
                danger_pixel_ratio=self._danger_pixel_ratio,
            )
        except Exception as exc:
            # Fail-closed: any compute error → false.
            self.get_logger().error(f"compute_depth_clear failed: {exc}; forcing depth_clear=false")
            self._publish(False)
            if self._last_clear_published is not False:
                self._last_clear_published = False
            return
        self._latest_info = info
        self._publish(clear)
        if clear != self._last_clear_published:
            self.get_logger().info(
                f"/capability/depth_clear -> {clear} "
                f"(min_depth={info['min_depth_m']:.2f}m valid={info['valid_count']}"
                f" danger={info['danger_count']} ratio={info['ratio']:.3f})"
            )
            self._last_clear_published = clear

    def _publish(self, clear: bool) -> None:
        msg = Bool()
        msg.data = bool(clear)
        self._pub.publish(msg)


def main():
    rclpy.init()
    node = DepthSafetyNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
