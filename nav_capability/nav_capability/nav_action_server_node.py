"""Nav action server: 提供 /nav/goto_relative action（包裝 Nav2 NavigateToPose）。

Phase 4 implementation of nav_capability spec §3.1 A1.
v1: 一律走 map frame（需要 AMCL 在線）；純 odom path 列入 spec T5。
"""
import asyncio
import math
from typing import Optional, Tuple

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from go2_interfaces.action import GotoRelative
from nav_capability.lib.relative_goal_math import compute_relative_goal
from nav_capability.lib.tf_pose_helper import quat_to_yaw, yaw_to_quat


AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class NavActionServerNode(Node):
    """Action server for /nav/goto_relative (Phase 4)."""

    def __init__(self):
        super().__init__("nav_action_server_node")
        self._cb_group = ReentrantCallbackGroup()

        # Latest AMCL pose
        self._amcl_pose: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl,
            AMCL_QOS,
            callback_group=self._cb_group,
        )

        # Nav2 NavigateToPose client
        self._nav_client = ActionClient(
            self,
            NavigateToPose,
            "/navigate_to_pose",
            callback_group=self._cb_group,
        )

        # GotoRelative action server
        self._relative_server = ActionServer(
            self,
            GotoRelative,
            "/nav/goto_relative",
            execute_callback=self._execute_relative,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
            callback_group=self._cb_group,
        )

        self.get_logger().info("nav_action_server_node ready (/nav/goto_relative)")

    # ── Subscriptions ──
    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl_pose = msg

    # ── Goal callbacks ──
    def _accept_goal(self, _goal):
        return GoalResponse.ACCEPT

    def _cancel_goal(self, _goal):
        return CancelResponse.ACCEPT

    # ── AMCL helpers ──
    def _amcl_covariance_xy(self) -> Optional[float]:
        """σ²x + σ²y from /amcl_pose covariance, or None if pose unavailable."""
        if self._amcl_pose is None:
            return None
        c = self._amcl_pose.pose.covariance
        return c[0] + c[7]  # diagonal x + y

    def _current_map_pose(self) -> Optional[Tuple[float, float, float]]:
        if self._amcl_pose is None:
            return None
        p = self._amcl_pose.pose.pose
        yaw = quat_to_yaw(
            p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w
        )
        return p.position.x, p.position.y, yaw

    # ── Action handler ──
    async def _execute_relative(self, goal_handle):
        goal = goal_handle.request
        result = GotoRelative.Result()

        # max_speed 在 v1 不會 enforce（Nav2 NavigateToPose 沒 per-goal speed override；
        # 速度上限由 nav2_params.yaml controller 設）。明確 warn 告知 caller，避免誤以為已生效。
        # 列入 spec §14 T5 範疇之後升級 (動態 set controller param)。
        if goal.max_speed > 0.0:
            self.get_logger().warn(
                f"goto_relative max_speed={goal.max_speed:.2f} ignored in v1 "
                f"(speed governed by nav2_params controller_server.{{min,max}}_vel_x). "
                f"Use ros2 param set to override controller speed if needed."
            )

        # AMCL gating (spec §8 E1: green / yellow / red)
        cov = self._amcl_covariance_xy()
        if cov is None:
            self.get_logger().warn("amcl_pose not received; rejecting goto_relative")
            goal_handle.abort()
            result.success = False
            result.message = "amcl_lost"
            return result
        if cov > 0.5:
            self.get_logger().warn(
                f"amcl covariance_xy={cov:.3f} > 0.5 (red); rejecting"
            )
            goal_handle.abort()
            result.success = False
            result.message = "amcl_lost"
            return result
        if 0.3 < cov <= 0.5 and abs(goal.distance) > 0.5:
            self.get_logger().warn(
                f"amcl covariance_xy={cov:.3f} (yellow); only ≤0.5m allowed, got {goal.distance}"
            )
            goal_handle.abort()
            result.success = False
            result.message = "amcl_lost"
            return result

        # Compute map-frame goal
        cur = self._current_map_pose()
        if cur is None:
            goal_handle.abort()
            result.success = False
            result.message = "amcl_lost"
            return result
        cx, cy, cyaw = cur
        gx, gy, gyaw = compute_relative_goal(
            cx, cy, cyaw, goal.distance, goal.yaw_offset
        )
        self.get_logger().info(
            f"goto_relative: distance={goal.distance:.2f} yaw_offset={goal.yaw_offset:.2f} "
            f"current=({cx:.2f},{cy:.2f},{cyaw:.2f}) -> goal=({gx:.2f},{gy:.2f},{gyaw:.2f})"
        )

        # Build Nav2 goal
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x = gx
        nav_goal.pose.pose.position.y = gy
        qx, qy, qz, qw = yaw_to_quat(gyaw)
        nav_goal.pose.pose.orientation.x = qx
        nav_goal.pose.pose.orientation.y = qy
        nav_goal.pose.pose.orientation.z = qz
        nav_goal.pose.pose.orientation.w = qw

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            goal_handle.abort()
            result.success = False
            result.message = "nav2_unavailable"
            return result

        send_future = self._nav_client.send_goal_async(nav_goal)
        nav_handle = await send_future
        if not nav_handle.accepted:
            goal_handle.abort()
            result.success = False
            result.message = "nav2_rejected_goal"
            return result

        # Poll nav2 result while watching for client cancellation.
        # 必要的 cancel propagation：caller 取消 /nav/goto_relative 時，
        # 必須真的把 underlying Nav2 goal 也 cancel 掉，否則 Go2 會繼續走。
        nav_result_future = nav_handle.get_result_async()
        while not nav_result_future.done():
            if goal_handle.is_cancel_requested:
                self.get_logger().info("client cancel requested; cancelling Nav2 goal")
                await nav_handle.cancel_goal_async()
                # wait for Nav2 to acknowledge cancel + return final status
                nav_result = await nav_result_future
                goal_handle.canceled()
                result.success = False
                result.message = "cancelled"
                return result
            await asyncio.sleep(0.1)

        nav_result = nav_result_future.result()

        if nav_result.status == GoalStatus.STATUS_SUCCEEDED:
            result.success = True
            result.message = "reached"
            cur_after = self._current_map_pose()
            if cur_after is not None:
                ax, ay, _ = cur_after
                result.actual_distance = float(math.hypot(ax - cx, ay - cy))
            goal_handle.succeed()
        elif nav_result.status == GoalStatus.STATUS_CANCELED:
            # Nav2 reported its own goal as cancelled (e.g. preemption).
            goal_handle.canceled()
            result.success = False
            result.message = "cancelled"
        else:
            result.success = False
            result.message = "nav2_failed"
            goal_handle.abort()
        return result


def main():
    rclpy.init()
    node = NavActionServerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
