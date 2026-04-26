#!/usr/bin/env python3
"""發 /nav/goto_relative action 給 nav_capability nav_action_server_node。

Phase 9.3 — 從直發 /goal_pose topic 改成 action client，正確等 result + 收 feedback。

用法:
    python3 scripts/send_relative_goal.py --distance 0.5
    python3 scripts/send_relative_goal.py --distance 0.8 --yaw-offset 0.3
    python3 scripts/send_relative_goal.py --distance 0.5 --max-speed 0.4

需先啟 nav_capability stack（含 AMCL 收斂 + /odom 活著）。
"""
import argparse
import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from go2_interfaces.action import GotoRelative


class GotoRelativeClient(Node):
    def __init__(self):
        super().__init__("send_relative_goal_cli")
        self._client = ActionClient(self, GotoRelative, "/nav/goto_relative")

    def send(self, distance: float, yaw_offset: float, max_speed: float) -> bool:
        if not self._client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error(
                "/nav/goto_relative action server not available within 10s; "
                "is nav_action_server_node running?"
            )
            return False

        goal = GotoRelative.Goal()
        goal.distance = float(distance)
        goal.yaw_offset = float(yaw_offset)
        goal.max_speed = float(max_speed)

        self.get_logger().info(
            f"sending goto_relative distance={distance:.2f} "
            f"yaw_offset={yaw_offset:.2f} max_speed={max_speed:.2f}"
        )

        send_future = self._client.send_goal_async(
            goal, feedback_callback=self._on_feedback
        )
        rclpy.spin_until_future_complete(self, send_future)
        handle = send_future.result()
        if not handle.accepted:
            self.get_logger().error("goal rejected by action server")
            return False

        self.get_logger().info("goal accepted; awaiting result...")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result
        self.get_logger().info(
            f"result: success={result.success} message={result.message!r} "
            f"actual_distance={result.actual_distance:.3f}"
        )
        return result.success

    def _on_feedback(self, feedback_msg) -> None:
        fb = feedback_msg.feedback
        self.get_logger().info(
            f"feedback: progress={fb.progress:.2f} "
            f"distance_to_goal={fb.distance_to_goal:.2f}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distance", type=float, required=True,
                        help="forward distance (m); negative for reverse")
    parser.add_argument("--yaw-offset", type=float, default=0.0,
                        help="heading offset relative to current yaw (rad)")
    parser.add_argument("--max-speed", type=float, default=0.5,
                        help="advisory only in v1 (Nav2 controller_server enforces limits)")
    args = parser.parse_args()

    rclpy.init()
    try:
        node = GotoRelativeClient()
        ok = node.send(args.distance, args.yaw_offset, args.max_speed)
        node.destroy_node()
        sys.exit(0 if ok else 1)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
