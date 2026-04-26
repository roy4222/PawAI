#!/usr/bin/env python3
"""發 Go2 機器人前方 d 公尺的相對 goal 給 Nav2。

讀 /amcl_pose 拿當前 pose，計算前方 d 公尺的 map 座標，發到 /goal_pose × 5 次（BEST_EFFORT mitigation）。

用法：
    python3 scripts/send_relative_goal.py --distance 0.5
    python3 scripts/send_relative_goal.py --distance 1.5

需先 source ROS2 + Nav2 stack 啟動 + AMCL 收斂。
"""
import argparse
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


def yaw_from_quat(qx, qy, qz, qw):
    """Quaternion → yaw (rad)，僅 z-axis 旋轉的扁平機器人適用。"""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


class RelativeGoalSender(Node):
    def __init__(self, distance_m: float, repeat: int = 1, rate_hz: float = 0.5):
        super().__init__("send_relative_goal")
        self._distance = distance_m
        self._repeat = repeat
        self._rate_hz = rate_hz
        self._got_pose = False

        amcl_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, amcl_qos,
        )
        # bt_navigator 訂閱 /goal_pose 用 BEST_EFFORT — publisher QoS 必須匹配
        goal_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self._goal_pub = self.create_publisher(PoseStamped, "/goal_pose", goal_qos)

    def _wait_for_subscriber(self, timeout_s: float = 3.0):
        """等 bt_navigator 透過 DDS discovery 連上 publisher。"""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._goal_pub.get_subscription_count() >= 1:
                return True
            time.sleep(0.1)
        return False

        self.get_logger().info(f"等 /amcl_pose（distance={distance_m}m）...")

    def _on_amcl(self, msg: PoseWithCovarianceStamped):
        if self._got_pose:
            return
        self._got_pose = True
        cur = msg.pose.pose
        yaw = yaw_from_quat(
            cur.orientation.x, cur.orientation.y, cur.orientation.z, cur.orientation.w,
        )
        gx = cur.position.x + self._distance * math.cos(yaw)
        gy = cur.position.y + self._distance * math.sin(yaw)

        self.get_logger().info(
            f"當前 ({cur.position.x:.2f}, {cur.position.y:.2f}) yaw={math.degrees(yaw):.1f}° → "
            f"goal ({gx:.2f}, {gy:.2f})"
        )

        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.pose.position.x = gx
        goal.pose.position.y = gy
        # 朝向保持與當前相同
        goal.pose.orientation = cur.orientation

        # DDS discovery 給 bt_navigator 連上 publisher 的時間（避免訊息丟失）
        if not self._wait_for_subscriber(timeout_s=3.0):
            self.get_logger().warn("等不到 /goal_pose subscriber — bt_navigator 是否運行？")

        for i in range(self._repeat):
            goal.header.stamp = self.get_clock().now().to_msg()
            self._goal_pub.publish(goal)
            self.get_logger().info(f"發 goal {i+1}/{self._repeat}")
            time.sleep(1.0 / self._rate_hz)

        self.get_logger().info("done")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--distance", type=float, default=0.5,
                        help="前方距離 (m)，預設 0.5")
    parser.add_argument("--repeat", type=int, default=1,
                        help="重發次數，預設 1（避免 preemption 干擾）")
    parser.add_argument("--rate", type=float, default=0.5,
                        help="重發 Hz，預設 0.5（每 2s 一次）")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="等 amcl_pose 的 timeout (s)")
    args = parser.parse_args()

    rclpy.init()
    node = RelativeGoalSender(distance_m=args.distance, repeat=args.repeat, rate_hz=args.rate)
    deadline = time.monotonic() + args.timeout
    try:
        while rclpy.ok() and not node._got_pose and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.5)
        if not node._got_pose:
            node.get_logger().error(
                f"timeout {args.timeout}s 未收到 /amcl_pose — AMCL 是否收斂？"
            )
            sys.exit(1)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
