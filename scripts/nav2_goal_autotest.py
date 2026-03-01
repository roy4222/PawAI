#!/usr/bin/env python3
"""
使用 /amcl_pose 自動推算導航目標並透過 NavigateToPose action 測試單點導航。

操作流程：
1. 先啟動驅動與 `ros2 launch ... nav2:=true`，並在 RViz 設定 Initial Pose。
2. 再執行本腳本，會抓取當前 AMCL 位姿並朝目前朝向前方偏移一段距離（預設 0.4m）。
3. 腳本會等待導航結果並輸出成功/失敗資訊，失敗時會給出 ROS 退出碼 1。
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Quaternion
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def yaw_from_quaternion(q: Quaternion) -> float:
    """回傳 quaternion 的偏航角（rad）。"""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def quaternion_from_yaw(yaw: float) -> Quaternion:
    """用偏航角建立純 yaw 旋轉的 quaternion。"""
    half = yaw * 0.5
    q = Quaternion()
    q.w = math.cos(half)
    q.z = math.sin(half)
    q.x = 0.0
    q.y = 0.0
    return q


class NavGoalAutoTester(Node):
    """透過 action client 發送單點導航並回報結果。"""

    def __init__(
        self,
        distance: float,
        frame_id: str,
        amcl_topic: str,
        timeout: float,
        goal_x: Optional[float],
        goal_y: Optional[float],
        goal_yaw: Optional[float],
    ):
        super().__init__("nav_goal_autotest")
        self._distance = distance
        self._frame = frame_id
        self._amcl_topic = amcl_topic
        self._timeout = timeout
        self._goal_x = goal_x
        self._goal_y = goal_y
        self._goal_yaw = goal_yaw
        self._amcl_pose: Optional[PoseWithCovarianceStamped] = None
        self._last_feedback_log_time = 0.0
        self._last_feedback_x: Optional[float] = None
        self._last_feedback_y: Optional[float] = None

        amcl_qos = QoSProfile(depth=10)
        amcl_qos.reliability = ReliabilityPolicy.RELIABLE
        amcl_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self._amcl_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            self._amcl_topic,
            self._handle_amcl_pose,
            amcl_qos,
        )
        self._action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")

    # ------------------------------------------------------------------ helpers
    def _handle_amcl_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl_pose = msg

    def wait_for_amcl_pose(self) -> PoseWithCovarianceStamped:
        """等待 AMCL 公布最新姿態。"""
        self.get_logger().info("等待 /amcl_pose ...")
        elapsed = 0.0
        interval = 0.1
        while rclpy.ok():
            if self._amcl_pose is not None:
                if self._amcl_pose.header.frame_id != self._frame:
                    self.get_logger().warn(
                        f"收到的 frame_id={self._amcl_pose.header.frame_id} 與預設 {self._frame} 不同"
                    )
                return self._amcl_pose
            rclpy.spin_once(self, timeout_sec=interval)
            elapsed += interval
            if elapsed >= self._timeout:
                raise TimeoutError("等待 /amcl_pose 超過指定秒數")
        raise TimeoutError("rclpy 停止運作，無法取得 AMCL 姿態")

    def wait_for_action_server(self) -> None:
        """確保 NavigateToPose action server 可用。"""
        self.get_logger().info("等待 navigate_to_pose action server ...")
        if not self._action_client.wait_for_server(timeout_sec=self._timeout):
            raise TimeoutError("等待 navigate_to_pose action server 超時")

    def _build_goal(self, pose: PoseWithCovarianceStamped, yaw_offset: float = 0.0) -> NavigateToPose.Goal:
        """建立導航目標：優先使用絕對座標，否則採用相對前進距離。"""
        yaw = yaw_from_quaternion(pose.pose.pose.orientation)
        heading = yaw + yaw_offset

        if self._goal_x is not None and self._goal_y is not None:
            goal_x = self._goal_x
            goal_y = self._goal_y
            goal_yaw = self._goal_yaw if self._goal_yaw is not None else yaw
        else:
            goal_x = pose.pose.pose.position.x + self._distance * math.cos(heading)
            goal_y = pose.pose.pose.position.y + self._distance * math.sin(heading)
            goal_yaw = yaw

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = self._frame
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = goal_x
        goal.pose.pose.position.y = goal_y
        goal.pose.pose.position.z = pose.pose.pose.position.z
        goal.pose.pose.orientation = quaternion_from_yaw(goal_yaw)
        return goal

    def execute(self) -> bool:
        """執行自動測試流程。"""
        amcl_pose = self.wait_for_amcl_pose()
        self.wait_for_action_server()
        goal = self._build_goal(amcl_pose)
        goal_yaw = yaw_from_quaternion(goal.pose.pose.orientation)
        self.get_logger().info(
            f"送出目標 x={goal.pose.pose.position.x:.3f}, y={goal.pose.pose.position.y:.3f}, "
            f"yaw={goal_yaw:.3f} rad (距離 {self._distance:.2f} m)"
        )
        result_future = self._action_client.send_goal_async(goal, feedback_callback=self._feedback_cb)
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=self._timeout)

        goal_handle = result_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error("NavigateToPose goal 被拒絕或送出失敗")
            return False

        self.get_logger().info("已送出目標，等待結果 ...")
        result = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result, timeout_sec=self._timeout * 4)

        if not result.done():
            self.get_logger().error("等待導航結果逾時")
            cancel_future = goal_handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, cancel_future, timeout_sec=2.0)
            self.get_logger().warn("已送出取消導航目標請求")
            return False

        wrapped_result = result.result()
        status = wrapped_result.status
        outcome = wrapped_result.result
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info("✅ NavigateToPose 成功（status=SUCCEEDED）")
            return True
        self.get_logger().error(f"❌ NavigateToPose 失敗，status={status}")
        if hasattr(outcome, "error_msg") and outcome.error_msg:
            self.get_logger().error("Nav2 回報：%s", outcome.error_msg)
        return False

    # ---------------------------------------------------------------- callbacks
    def _feedback_cb(self, feedback: NavigateToPose.Feedback) -> None:  # pragma: no cover - log only
        pose = feedback.feedback.current_pose.pose
        now = time.monotonic()
        if self._last_feedback_x is not None and self._last_feedback_y is not None:
            moved = math.hypot(pose.position.x - self._last_feedback_x, pose.position.y - self._last_feedback_y)
        else:
            moved = float("inf")

        if (now - self._last_feedback_log_time) < 1.0 and moved < 0.02:
            return

        self._last_feedback_log_time = now
        self._last_feedback_x = pose.position.x
        self._last_feedback_y = pose.position.y
        self.get_logger().info(
            f"回饋 - 機器狗位置 x={pose.position.x:.3f}, y={pose.position.y:.3f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nav2 單點導航自動測試腳本")
    parser.add_argument(
        "--distance",
        type=float,
        default=0.4,
        help="沿著 AMCL 朝向前進的距離（公尺）",
    )
    parser.add_argument(
        "--frame-id",
        default="map",
        help="預期的 AMCL/目標參考座標系（預設 map）",
    )
    parser.add_argument(
        "--amcl-topic",
        default="/amcl_pose",
        help="AMCL topic（預設 /amcl_pose；多機器人可改為 /robotX/amcl_pose）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="等待 AMCL / action server / result 的逾時秒數",
    )
    parser.add_argument(
        "--x",
        type=float,
        default=None,
        help="絕對目標點 x（map 座標）；若指定 x/y，會改用絕對座標模式",
    )
    parser.add_argument(
        "--y",
        type=float,
        default=None,
        help="絕對目標點 y（map 座標）；需與 --x 一起使用",
    )
    parser.add_argument(
        "--yaw",
        type=float,
        default=None,
        help="絕對目標 yaw（rad）；未指定時沿用當前 AMCL yaw",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if (args.x is None) ^ (args.y is None):
        raise SystemExit("--x 與 --y 必須同時指定")

    rclpy.init()
    tester = NavGoalAutoTester(
        distance=args.distance,
        frame_id=args.frame_id,
        amcl_topic=args.amcl_topic,
        timeout=args.timeout,
        goal_x=args.x,
        goal_y=args.y,
        goal_yaw=args.yaw,
    )
    try:
        success = tester.execute()
    except TimeoutError as exc:
        tester.get_logger().error(str(exc))
        success = False
    except KeyboardInterrupt:
        tester.get_logger().warn("收到 Ctrl+C，提前結束")
        success = False
    finally:
        tester.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
