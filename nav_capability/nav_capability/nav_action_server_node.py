"""Nav action server: 提供 /nav/goto_relative + /nav/goto_named action。

Phase 4-5 implementation of nav_capability spec §3.1 A1+A2.
v1: 一律走 map frame（需要 AMCL 在線）；純 odom path 列入 spec T5。
"""
import asyncio
import math
import os
import time
from typing import Optional, Tuple

import rclpy
from ament_index_python.packages import get_package_share_directory
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import Bool

from go2_interfaces.action import GotoRelative, GotoNamed
from nav_capability.lib.named_pose_store import NamedPoseNotFound, NamedPoseStore
from nav_capability.lib.progress_check import (
    PROGRESS_THRESHOLD_M,
    PROGRESS_TIMEOUT_S,
    has_progress,
)
from nav_capability.lib.relative_goal_math import compute_relative_goal
from nav_capability.lib.standoff_math import compute_standoff_goal
from nav_capability.lib.tf_pose_helper import quat_to_yaw, yaw_to_quat


AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

PAUSED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class NavActionServerNode(Node):
    """Action server for /nav/goto_relative (Phase 4)."""

    def __init__(self):
        super().__init__("nav_action_server_node")
        self._cb_group = ReentrantCallbackGroup()

        # Active-goal guard — only one goto_relative or goto_named at a time.
        # Without this, two concurrent goals send Nav2 NavigateToPose in parallel; the
        # second goal preempts the first at the Nav2 layer but the wrapper action of
        # the first goal keeps awaiting its (now-canceled) result, causing stuck states.
        self._goto_active = False

        # Phase 8 — /odom watchdog as proxy for driver liveness.
        # If /odom hasn't been heard for >2s, refuse new goto goals (driver disconnected).
        self._last_odom_ns: int = 0

        # Latest AMCL pose
        self._amcl_pose: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl,
            AMCL_QOS,
            callback_group=self._cb_group,
        )

        # /state/nav/paused subscription (BUG #2 fix). When True, in-flight Nav2 goal
        # is cancelled and re-sent on resume. Latched (TRANSIENT_LOCAL) so a late
        # subscriber still gets the last known state from route_runner.
        self._paused: bool = False
        self.create_subscription(
            Bool,
            "/state/nav/paused",
            self._on_paused,
            PAUSED_QOS,
            callback_group=self._cb_group,
        )

        # /odom subscription for driver-liveness watchdog (Phase 8)
        self.create_subscription(
            Odometry,
            "/odom",
            self._on_odom,
            QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT),
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

        # Named pose store (Phase 5.1) — load from share/nav_capability or override param
        self.declare_parameter("named_poses_file", "")
        named_file = self.get_parameter("named_poses_file").value
        if not named_file:
            named_file = os.path.join(
                get_package_share_directory("nav_capability"),
                "config",
                "named_poses",
                "sample.json",
            )
        try:
            self._named_store: Optional[NamedPoseStore] = NamedPoseStore.from_file(named_file)
            self.get_logger().info(
                f"named_poses loaded from {named_file}: "
                f"{sorted(self._named_store.list_names())} (map_id={self._named_store.map_id})"
            )
        except (FileNotFoundError, ValueError) as exc:
            self.get_logger().warn(f"failed to load named_poses ({named_file}): {exc}")
            self._named_store = None

        # GotoNamed action server (Phase 5.1)
        self._named_server = ActionServer(
            self,
            GotoNamed,
            "/nav/goto_named",
            execute_callback=self._execute_named,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
            callback_group=self._cb_group,
        )

        self.get_logger().info(
            "nav_action_server_node ready (/nav/goto_relative + /nav/goto_named)"
        )

    # ── Subscriptions ──
    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl_pose = msg

    def _on_paused(self, msg: Bool) -> None:
        new_state = bool(msg.data)
        if new_state != self._paused:
            self.get_logger().info(f"/state/nav/paused -> {new_state}")
        self._paused = new_state

    def _on_odom(self, _msg: Odometry) -> None:
        self._last_odom_ns = self.get_clock().now().nanoseconds

    def _odom_alive(self) -> bool:
        if self._last_odom_ns == 0:
            return False
        now_ns = self.get_clock().now().nanoseconds
        return (now_ns - self._last_odom_ns) < 2_000_000_000  # 2s

    async def _wait_for_odom(self, timeout_s: float = 3.0) -> bool:
        """Phase 9 review #4: 剛啟 stack 時 /odom 可能還沒 publish；給 timeout warmup
        而非立刻 reject，避免 K1/K4 假失敗。"""
        if self._odom_alive():
            return True
        deadline_ns = self.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.get_clock().now().nanoseconds < deadline_ns:
            time.sleep(0.1)  # rclpy action callback not in asyncio loop; blocking sleep OK with MultiThreadedExecutor
            if self._odom_alive():
                return True
        return False

    # ── Goal callbacks ──
    def _accept_goal(self, _goal):
        if self._goto_active:
            self.get_logger().warn(
                "rejecting goto_* goal — another goto_relative/goto_named is still active"
            )
            return GoalResponse.REJECT
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

    def _current_xy(self) -> Optional[Tuple[float, float]]:
        if self._amcl_pose is None:
            return None
        p = self._amcl_pose.pose.pose.position
        return (p.x, p.y)

    # ── Pause/Progress-aware Nav2 goal execution ──
    async def _execute_nav_goal_with_pause_aware(self, goal_handle, nav_goal):
        """Send nav_goal to Nav2; handle pause→cancel→re-send + progress-timeout + client cancel.

        Returns (success: bool, message: str). Does NOT call goal_handle.succeed/abort/canceled —
        caller is responsible for that based on the returned tuple.

        Behaviour:
          * /state/nav/paused goes True → cancel current Nav2 goal, wait for paused→False,
            then re-send the same nav_goal. Caller's max_speed / target unchanged.
          * AMCL pose hasn't moved >= PROGRESS_THRESHOLD_M for PROGRESS_TIMEOUT_S → fail.
          * goal_handle.is_cancel_requested → propagate cancel to Nav2, return cancelled.
        """
        while True:  # outer loop = pause/resume cycle
            # If paused at entry, wait until resumed (or client cancel)
            while self._paused:
                if goal_handle.is_cancel_requested:
                    return (False, "cancelled")
                time.sleep(0.1)

            send_future = self._nav_client.send_goal_async(nav_goal)
            nav_handle = await send_future
            if not nav_handle.accepted:
                return (False, "nav2_rejected_goal")

            nav_result_future = nav_handle.get_result_async()
            last_progress_ns = self.get_clock().now().nanoseconds
            prev_xy = self._current_xy()
            paused_during_run = False

            while not nav_result_future.done():
                if goal_handle.is_cancel_requested:
                    self.get_logger().info("client cancel requested; cancelling Nav2 goal")
                    await nav_handle.cancel_goal_async()
                    await nav_result_future
                    return (False, "cancelled")

                if self._paused:
                    self.get_logger().info(
                        "paused detected; cancelling Nav2 goal, will re-send on resume"
                    )
                    paused_during_run = True
                    await nav_handle.cancel_goal_async()
                    await nav_result_future
                    break  # exit inner while → outer loop will wait for resume + re-send

                # Progress check via /amcl_pose
                curr_xy = self._current_xy()
                if has_progress(prev_xy, curr_xy, PROGRESS_THRESHOLD_M):
                    last_progress_ns = self.get_clock().now().nanoseconds
                    prev_xy = curr_xy
                else:
                    elapsed_ns = self.get_clock().now().nanoseconds - last_progress_ns
                    if elapsed_ns > int(PROGRESS_TIMEOUT_S * 1e9):
                        self.get_logger().warn(
                            f"no progress in {PROGRESS_TIMEOUT_S:.1f}s "
                            f"(threshold={PROGRESS_THRESHOLD_M:.2f}m); aborting"
                        )
                        await nav_handle.cancel_goal_async()
                        await nav_result_future
                        return (False, "no_progress_timeout")

                time.sleep(0.1)  # rclpy action callback not in asyncio loop; OK with MultiThreadedExecutor

            if not paused_during_run:
                nav_result = nav_result_future.result()
                if nav_result.status == GoalStatus.STATUS_SUCCEEDED:
                    return (True, "reached")
                if nav_result.status == GoalStatus.STATUS_CANCELED:
                    return (False, "cancelled")
                return (False, "nav2_failed")
            # else: paused_during_run → outer loop iterates → wait for paused=False → re-send

    # ── Action handler ──
    async def _execute_relative(self, goal_handle):
        self._goto_active = True
        try:
            return await self._execute_relative_inner(goal_handle)
        finally:
            self._goto_active = False

    async def _execute_relative_inner(self, goal_handle):
        goal = goal_handle.request
        result = GotoRelative.Result()

        # PR1a measurement — log goal-accept-time pose for offline analysis.
        # Pure observation; not used for actual_distance computation (that still
        # references cx,cy captured after AMCL gating, line ~354).
        accept_xy = self._current_xy()
        accept_ns = self.get_clock().now().nanoseconds
        self.get_logger().info(
            f"[PR1a] goto_relative ACCEPT distance={goal.distance:.3f} "
            f"max_speed_req={goal.max_speed:.3f} "
            f"accept_pose={accept_xy if accept_xy else 'None'} "
            f"accept_ns={accept_ns}"
        )

        # Phase 8 — driver liveness watchdog (E5) with 3s warmup (Phase 9 review #4).
        if not await self._wait_for_odom(timeout_s=3.0):
            self.get_logger().warn(
                "rejecting goto_relative — /odom not received within 3s warmup; "
                "driver may be disconnected"
            )
            goal_handle.abort()
            result.success = False
            result.message = "odom_lost_driver_disconnected"
            return result

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

        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
        end_ns = self.get_clock().now().nanoseconds
        if success:
            result.success = True
            result.message = msg
            cur_after = self._current_map_pose()
            if cur_after is not None:
                ax, ay, _ = cur_after
                # Existing computation — reference cx,cy captured at line ~354 (after AMCL gating).
                result.actual_distance = float(math.hypot(ax - cx, ay - cy))
                # PR1a measurement — also compute from accept_xy for divergence check.
                accept_displacement = (
                    float(math.hypot(ax - accept_xy[0], ay - accept_xy[1]))
                    if accept_xy is not None else float('nan')
                )
                duration_s = (end_ns - accept_ns) / 1e9
                self.get_logger().info(
                    f"[PR1a] goto_relative DONE goal={goal.distance:.3f} "
                    f"actual_dist_from_cxcy={result.actual_distance:.3f} "
                    f"actual_dist_from_accept={accept_displacement:.3f} "
                    f"duration_s={duration_s:.2f} "
                    f"end_pose=({ax:.3f},{ay:.3f}) "
                    f"cxcy=({cx:.3f},{cy:.3f}) "
                    f"accept_xy={accept_xy}"
                )
            goal_handle.succeed()
        else:
            # cancelled / nav2_failed / no_progress_timeout
            cur_after = self._current_map_pose()
            if cur_after is not None and accept_xy is not None:
                ax, ay, _ = cur_after
                accept_displacement = float(math.hypot(ax - accept_xy[0], ay - accept_xy[1]))
                duration_s = (end_ns - accept_ns) / 1e9
                self.get_logger().info(
                    f"[PR1a] goto_relative END({msg}) goal={goal.distance:.3f} "
                    f"actual_dist_from_accept={accept_displacement:.3f} "
                    f"duration_s={duration_s:.2f} "
                    f"end_pose=({ax:.3f},{ay:.3f})"
                )
            result.success = False
            result.message = msg
            if msg == "cancelled":
                goal_handle.canceled()
            else:
                goal_handle.abort()
        return result


    # ── GotoNamed handler (Phase 5.1) ──
    async def _execute_named(self, goal_handle):
        self._goto_active = True
        try:
            return await self._execute_named_inner(goal_handle)
        finally:
            self._goto_active = False

    async def _execute_named_inner(self, goal_handle):
        goal = goal_handle.request
        result = GotoNamed.Result()

        # Phase 8 — driver liveness watchdog (E5) with 3s warmup (Phase 9 review #4).
        if not await self._wait_for_odom(timeout_s=3.0):
            self.get_logger().warn(
                "rejecting goto_named — /odom not received within 3s warmup; "
                "driver may be disconnected"
            )
            goal_handle.abort()
            result.success = False
            result.message = "odom_lost_driver_disconnected"
            return result

        if self._named_store is None:
            self.get_logger().warn("named_pose_store not loaded; rejecting goto_named")
            goal_handle.abort()
            result.success = False
            result.message = "named_pose_store_not_loaded"
            return result

        # Lookup named pose
        try:
            named = self._named_store.lookup(goal.name)
        except NamedPoseNotFound as exc:
            self.get_logger().warn(str(exc))
            goal_handle.abort()
            result.success = False
            result.message = str(exc)
            return result

        # max_speed advisory (same v1 caveat as goto_relative)
        if goal.max_speed > 0.0:
            self.get_logger().warn(
                f"goto_named max_speed={goal.max_speed:.2f} ignored in v1 "
                f"(speed governed by nav2_params controller_server)."
            )

        # AMCL gating (spec §8 E1: green / yellow / red)
        cov = self._amcl_covariance_xy()
        if cov is None or cov > 0.5:
            self.get_logger().warn(
                f"amcl covariance unavailable or > 0.5 (got {cov}); rejecting"
            )
            goal_handle.abort()
            result.success = False
            result.message = "amcl_lost"
            return result

        # Determine final goal: with optional standoff transform
        target_x, target_y, target_yaw = named.x, named.y, named.yaw
        if goal.standoff > 0.0:
            cur = self._current_map_pose()
            if cur is None:
                goal_handle.abort()
                result.success = False
                result.message = "amcl_lost"
                return result
            rx, ry, _ = cur
            sgx, sgy, sgyaw_face = compute_standoff_goal(
                target_x, target_y, rx, ry, goal.standoff
            )
            final_yaw = sgyaw_face if goal.align_yaw_to_target else target_yaw
            final_x, final_y = sgx, sgy
            self.get_logger().info(
                f"goto_named '{goal.name}' standoff={goal.standoff:.2f} "
                f"target=({target_x:.2f},{target_y:.2f}) -> goal=({final_x:.2f},{final_y:.2f},{final_yaw:.2f})"
            )
        else:
            final_x, final_y, final_yaw = target_x, target_y, target_yaw
            self.get_logger().info(
                f"goto_named '{goal.name}' direct -> ({final_x:.2f},{final_y:.2f},{final_yaw:.2f})"
            )

        # Yellow gate: when covariance is borderline, reject long approaches
        if 0.3 < cov <= 0.5:
            cur = self._current_map_pose()
            if cur is not None:
                rx, ry, _ = cur
                approach = math.hypot(final_x - rx, final_y - ry)
                if approach > 0.5:
                    self.get_logger().warn(
                        f"amcl covariance_xy={cov:.3f} (yellow); approach {approach:.2f}m > 0.5m allowed; rejecting"
                    )
                    goal_handle.abort()
                    result.success = False
                    result.message = "amcl_lost"
                    return result

        # Build Nav2 goal
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x = float(final_x)
        nav_goal.pose.pose.position.y = float(final_y)
        qx, qy, qz, qw = yaw_to_quat(final_yaw)
        nav_goal.pose.pose.orientation.x = qx
        nav_goal.pose.pose.orientation.y = qy
        nav_goal.pose.pose.orientation.z = qz
        nav_goal.pose.pose.orientation.w = qw

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            goal_handle.abort()
            result.success = False
            result.message = "nav2_unavailable"
            return result

        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
        if success:
            result.success = True
            result.message = msg
            result.final_pose.position.x = float(final_x)
            result.final_pose.position.y = float(final_y)
            qx, qy, qz, qw = yaw_to_quat(final_yaw)
            result.final_pose.orientation.x = qx
            result.final_pose.orientation.y = qy
            result.final_pose.orientation.z = qz
            result.final_pose.orientation.w = qw
            goal_handle.succeed()
        elif msg == "cancelled":
            result.success = False
            result.message = msg
            goal_handle.canceled()
        else:
            result.success = False
            result.message = msg
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
