#!/usr/bin/env python3
"""發 /nav/goto_relative action 給 nav_capability nav_action_server_node。

Phase 9.3 — 從直發 /goal_pose topic 改成 action client，等 result。
v1 注意：server 不發 feedback，CLI 從 send 到 result 之間會靜默（這是預期行為，
不是卡住）。Result 通常 5-15 秒到達取決於 distance 與 Nav2 plan 速度。

6/9 robustness（demo blocker fix）：
- Ctrl-C / SSH 斷線時主動 cancel 在途的 goal，避免 server 留 orphaned active goal
  （否則後續 goto_* 全被 "another goto still active" 拒，需重啟整個 navcap stack）。
- 關閉 rclpy 預設 SIGINT handler，自管 Ctrl-C，讓 cancel 在 context alive 時送出。
- shutdown 只在 finally 走一次，避免 double-shutdown。

用法:
    python3 scripts/send_relative_goal.py --distance 0.5
    python3 scripts/send_relative_goal.py --distance 0.8 --yaw-offset 0.3
    python3 scripts/send_relative_goal.py --distance 0.5 --max-speed 0.4

需先啟 nav_capability stack（含 AMCL 收斂 + /odom 活著）。
"""
import argparse
import signal
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

from go2_interfaces.action import GotoRelative


class SigintRequested(Exception):
    """Raised by the main flow after our SIGINT handler records Ctrl-C."""


class SigintState:
    """Minimal state shared with the Python SIGINT handler."""

    def __init__(self):
        self.requested = False

    def request(self, _signum, _frame):
        self.requested = True


class GotoRelativeClient(Node):
    def __init__(self, sigint_state: SigintState):
        super().__init__("send_relative_goal_cli")
        self._client = ActionClient(self, GotoRelative, "/nav/goto_relative")
        self._sigint_state = sigint_state
        # Handle of the in-flight goal, set once accepted and cleared once terminal.
        # Used by cancel_active_goal() to release the server's active-goal lock on interrupt.
        self._goal_handle = None

    def _raise_if_interrupted(self) -> None:
        if self._sigint_state.requested:
            raise SigintRequested

    def _wait_for_server(self, timeout_sec: float) -> bool:
        deadline = time.monotonic() + timeout_sec
        while True:
            self._raise_if_interrupted()
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            if self._client.wait_for_server(timeout_sec=min(0.1, remaining)):
                return True

    def _spin_until_future_complete(self, future, *, interruptible: bool = True) -> None:
        while not future.done():
            if interruptible:
                self._raise_if_interrupted()
            rclpy.spin_until_future_complete(self, future, timeout_sec=0.1)

    def send(self, distance: float, yaw_offset: float, max_speed: float) -> bool:
        if not self._wait_for_server(timeout_sec=10.0):
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
            f"yaw_offset={yaw_offset:.2f} max_speed={max_speed:.2f} "
            f"(note: nav_action_server v1 does not publish feedback; "
            f"this CLI will appear silent until result arrives)"
        )

        self._raise_if_interrupted()
        send_future = self._client.send_goal_async(goal)
        # Once the request is on the wire, wait for the response even after SIGINT
        # so an accepted goal handle can be recorded and canceled below.
        self._spin_until_future_complete(send_future, interruptible=False)
        handle = send_future.result()
        if not handle.accepted:
            self.get_logger().error("goal rejected by action server")
            return False

        # Track the accepted goal so an interrupt (Ctrl-C / SSH drop) can cancel it.
        self._goal_handle = handle
        self._raise_if_interrupted()

        self.get_logger().info("goal accepted; awaiting result...")
        result_future = handle.get_result_async()
        self._spin_until_future_complete(result_future)
        # Goal is terminal now — no longer cancellable, so drop the handle before
        # honoring any SIGINT that arrived at the same time as the result.
        self._goal_handle = None
        self._raise_if_interrupted()
        result = result_future.result().result
        self.get_logger().info(
            f"result: success={result.success} message={result.message!r} "
            f"actual_distance={result.actual_distance:.3f}"
        )
        return result.success

    def cancel_active_goal(self) -> None:
        """Best-effort cancel of an in-flight goal on interrupt.

        Without this, a Ctrl-C / SSH drop while the goal is executing leaves the server's
        single-goal lock (`_goto_active`) held until its own timeout, so every later goto
        is rejected as "another goto still active".
        """
        if self._goal_handle is None or not rclpy.ok():
            return
        self.get_logger().warn(
            "interrupted; cancelling in-flight goto so nav_action_server releases its "
            "active-goal lock"
        )
        try:
            cancel_future = self._goal_handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, cancel_future, timeout_sec=3.0)
        except Exception as exc:  # best-effort: we are already tearing down
            self.get_logger().warn(f"cancel-on-interrupt failed: {exc}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distance", type=float, required=True,
                        help="forward distance (m); negative for reverse")
    parser.add_argument("--yaw-offset", type=float, default=0.0,
                        help="heading offset relative to current yaw (rad)")
    parser.add_argument("--max-speed", type=float, default=0.5,
                        help="advisory only in v1 (Nav2 controller_server enforces limits)")
    args = parser.parse_args()

    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    sigint_state = SigintState()
    previous_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, sigint_state.request)
    node = None
    exit_code = 1
    shutdown_called = False
    try:
        node = GotoRelativeClient(sigint_state)
        ok = node.send(args.distance, args.yaw_offset, args.max_speed)
        if sigint_state.requested:
            raise SigintRequested
        exit_code = 0 if ok else 1
    except SigintRequested:
        if node is not None:
            node.cancel_active_goal()
        exit_code = 130
    finally:
        try:
            if node is not None:
                node.destroy_node()
        finally:
            try:
                if not shutdown_called and rclpy.ok():
                    shutdown_called = True
                    rclpy.shutdown()
            finally:
                signal.signal(signal.SIGINT, previous_sigint_handler)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
