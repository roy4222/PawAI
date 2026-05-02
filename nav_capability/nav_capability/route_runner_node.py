"""Route Runner: 跑 multi-waypoint route，FSM 驅動，遇 wait/tts 暫停執行。

Phase 7 implementation of nav_capability spec §3.1 A3 + §3.2 services + §3.3 event.

Node API:
  Action  /nav/run_route        (RunRoute) — load route_id, iterate waypoints
  Service /nav/pause            (std_srvs/Trigger) — cancel current Nav2 goal,
                                                     remember waypoint, latch zero
  Service /nav/resume           (std_srvs/Trigger) — re-send current waypoint goal
  Service /nav/cancel           (Cancel) — cancel route entirely
  Topic   /event/nav/waypoint_reached  (std_msgs/String JSON) — fires on each wp hit
  Topic   /event/nav/internal/status   (std_msgs/String JSON) — feeds state_broadcaster
  Topic   /tts                          (std_msgs/String) — fires on task=tts wp
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger

from go2_interfaces.action import RunRoute
from go2_interfaces.srv import Cancel
from nav_capability.lib.route_fsm import IllegalTransition, RouteFSM, RouteState
from nav_capability.lib.route_validator import RouteValidationError, validate_route
from nav_capability.lib.tf_pose_helper import yaw_to_quat

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# Latched semantics for /state/nav/paused so late subscribers (e.g.
# nav_action_server starting after route_runner) still see the last known state.
PAUSED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class RouteRunnerNode(Node):
    def __init__(self):
        super().__init__("route_runner_node")
        self._cb = ReentrantCallbackGroup()

        self.declare_parameter("routes_dir", "")

        # FSM + runtime state
        self._fsm = RouteFSM()
        self._current_route: Optional[dict] = None
        self._current_nav_handle = None
        # asyncio.Event used to gate the route loop on pause; default 'set' = not paused.
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        # Subscriptions
        self._amcl: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl,
            AMCL_QOS,
            callback_group=self._cb,
        )
        # Phase 8 — driver liveness watchdog
        self._last_odom_ns: int = 0
        self.create_subscription(
            Odometry,
            "/odom",
            self._on_odom,
            QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT),
            callback_group=self._cb,
        )

        # Nav2 client
        self._nav_client = ActionClient(
            self,
            NavigateToPose,
            "/navigate_to_pose",
            callback_group=self._cb,
        )

        # Publishers
        self._tts_pub = self.create_publisher(String, "/tts", 10)
        self._waypoint_event_pub = self.create_publisher(
            String, "/event/nav/waypoint_reached", 10
        )
        self._internal_status_pub = self.create_publisher(
            String, "/event/nav/internal/status", 10
        )
        # /state/nav/paused (BUG #2 fix): latched Bool consumed by nav_action_server.
        # Published from _svc_pause/_svc_resume/_svc_cancel/_reset_fsm so that goto_relative
        # and goto_named also honour pause, not just /nav/run_route.
        self._paused_pub = self.create_publisher(Bool, "/state/nav/paused", PAUSED_QOS)
        self._publish_paused(False)  # initial latched state = not paused

        # RunRoute action server
        self._run_server = ActionServer(
            self,
            RunRoute,
            "/nav/run_route",
            execute_callback=self._execute_run_route,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
            callback_group=self._cb,
        )

        # Pause / Resume / Cancel services
        self.create_service(
            Trigger, "/nav/pause", self._svc_pause, callback_group=self._cb
        )
        self.create_service(
            Trigger, "/nav/resume", self._svc_resume, callback_group=self._cb
        )
        self.create_service(
            Cancel, "/nav/cancel", self._svc_cancel, callback_group=self._cb
        )

        self.get_logger().info(
            "route_runner_node ready (/nav/run_route + /nav/{pause,resume,cancel})"
        )

    # ── Subscriptions ──
    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl = msg

    def _on_odom(self, _msg: Odometry) -> None:
        self._last_odom_ns = self.get_clock().now().nanoseconds

    def _odom_alive(self) -> bool:
        if self._last_odom_ns == 0:
            return False
        now_ns = self.get_clock().now().nanoseconds
        return (now_ns - self._last_odom_ns) < 2_000_000_000  # 2s

    async def _wait_for_odom(self, timeout_s: float = 3.0) -> bool:
        """Phase 9 review #4: warmup wait so just-launched stack doesn't false-reject."""
        if self._odom_alive():
            return True
        deadline_ns = self.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.get_clock().now().nanoseconds < deadline_ns:
            await asyncio.sleep(0.1)
            if self._odom_alive():
                return True
        return False

    # ── Goal callbacks ──
    def _accept_goal(self, _g):
        # Reject when an active route is still in flight; caller must /nav/cancel first
        # or wait for SUCCEEDED/FAILED. Prevents two run_route goals racing on the same
        # FSM / Nav2 client / pause_event.
        if self._fsm.state not in (
            RouteState.IDLE, RouteState.SUCCEEDED, RouteState.FAILED,
        ):
            self.get_logger().warn(
                f"rejecting /nav/run_route — existing route still in state "
                f"{self._fsm.state.name} (call /nav/cancel first or wait)"
            )
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_goal(self, _g):
        return CancelResponse.ACCEPT

    # ── Status publishing ──
    def _publish_internal_status(self, **extra) -> None:
        payload = {
            "state": self._fsm.state.name.lower(),
        }
        payload.update(extra)
        m = String()
        m.data = json.dumps(payload)
        self._internal_status_pub.publish(m)

    def _publish_paused(self, paused: bool) -> None:
        msg = Bool()
        msg.data = bool(paused)
        self._paused_pub.publish(msg)

    def _emit_waypoint_reached(self, route_id: str, wp: dict) -> None:
        payload = {
            "route_id": route_id,
            "waypoint_id": wp["id"],
            "task": wp["task"],
            "pose": wp["pose"],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        m = String()
        m.data = json.dumps(payload)
        self._waypoint_event_pub.publish(m)

    # ── Helpers ──
    def _load_route(self, route_id: str) -> dict:
        routes_dir = self.get_parameter("routes_dir").value
        if not routes_dir:
            routes_dir = os.path.join(
                get_package_share_directory("nav_capability"),
                "config",
                "routes",
            )
        path = os.path.join(routes_dir, f"{route_id}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate_route(data)
        return data

    def _build_nav_goal(self, wp: dict) -> NavigateToPose.Goal:
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x = float(wp["pose"]["x"])
        nav_goal.pose.pose.position.y = float(wp["pose"]["y"])
        qx, qy, qz, qw = yaw_to_quat(wp["pose"]["yaw"])
        nav_goal.pose.pose.orientation.x = qx
        nav_goal.pose.pose.orientation.y = qy
        nav_goal.pose.pose.orientation.z = qz
        nav_goal.pose.pose.orientation.w = qw
        return nav_goal

    def _reset_fsm(self) -> None:
        self._fsm = RouteFSM()
        self._current_nav_handle = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._publish_paused(False)

    # ── Action handler ──
    async def _execute_run_route(self, goal_handle):
        result = RunRoute.Result()
        feedback = RunRoute.Feedback()

        # Phase 8 — driver liveness watchdog with 3s warmup (Phase 9 review #4)
        if not await self._wait_for_odom(timeout_s=3.0):
            self.get_logger().warn(
                "rejecting run_route — /odom not received within 3s warmup; "
                "driver may be disconnected"
            )
            goal_handle.abort()
            result.success = False
            result.message = "odom_lost_driver_disconnected"
            return result

        # Reset FSM in case prior run left state non-IDLE
        if self._fsm.state != RouteState.IDLE:
            self._reset_fsm()

        # Load + validate route
        try:
            route = self._load_route(goal_handle.request.route_id)
        except (FileNotFoundError, RouteValidationError) as exc:
            self.get_logger().warn(f"bad route '{goal_handle.request.route_id}': {exc}")
            goal_handle.abort()
            result.success = False
            result.message = f"bad_route: {exc}"
            return result

        self._current_route = route
        waypoints = route["waypoints"]
        try:
            self._fsm.start_route(total_waypoints=len(waypoints))
        except IllegalTransition as exc:
            self.get_logger().warn(f"start_route illegal: {exc}")
            goal_handle.abort()
            result.success = False
            result.message = "fsm_illegal"
            return result

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            goal_handle.abort()
            result.success = False
            result.message = "nav2_unavailable"
            return result

        self.get_logger().info(
            f"run_route '{route['route_id']}' starting with {len(waypoints)} waypoints"
        )
        self._publish_internal_status(
            active_goal={
                "type": "route",
                "id": route["route_id"],
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )

        # Main loop — keep iterating until SUCCEEDED or FAILED
        while self._fsm.state not in (RouteState.SUCCEEDED, RouteState.FAILED):
            # Block here while paused
            await self._pause_event.wait()

            # Re-check after wait: caller may have cancelled while paused
            if self._fsm.state == RouteState.FAILED:
                break

            # Phase 8 — mid-route driver disconnect → cancel
            if not self._odom_alive():
                self.get_logger().warn(
                    "active route aborted — /odom timeout mid-flight"
                )
                self._fsm.cancel()
                if self._current_nav_handle is not None:
                    await self._current_nav_handle.cancel_goal_async()
                result.message = "odom_lost_driver_disconnected"
                break

            # External /nav/run_route cancel (vs /nav/cancel service)
            if goal_handle.is_cancel_requested:
                self.get_logger().info("run_route action cancel requested")
                self._fsm.cancel()
                if self._current_nav_handle is not None:
                    await self._current_nav_handle.cancel_goal_async()
                break

            idx = self._fsm.current_waypoint_index
            wp = waypoints[idx]

            feedback.current_waypoint_index = idx
            feedback.current_waypoint_id = wp["id"]
            feedback.current_state = self._fsm.state.name.lower()
            goal_handle.publish_feedback(feedback)
            self._publish_internal_status(
                active_goal={
                    "type": "route",
                    "id": route["route_id"],
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                current_waypoint_index=idx,
                current_waypoint_id=wp["id"],
            )

            # PLANNING → MOVING
            nav_goal = self._build_nav_goal(wp)
            nav_handle = await self._nav_client.send_goal_async(nav_goal)
            if not nav_handle.accepted:
                self.get_logger().warn(f"nav2 rejected goal for waypoint {wp['id']}")
                self._fsm.cancel()
                continue

            self._current_nav_handle = nav_handle
            try:
                self._fsm.goal_accepted()
            except IllegalTransition:
                # Could happen if pause raced; tolerate.
                pass

            timeout_sec = float(wp.get("timeout_sec", 30))
            nav_result_future = nav_handle.get_result_async()

            # Poll: respect pause + cancel + per-waypoint timeout
            start_ns = self.get_clock().now().nanoseconds
            timed_out = False
            while not nav_result_future.done():
                # External action cancel
                if goal_handle.is_cancel_requested:
                    self.get_logger().info("run_route cancel during waypoint")
                    await nav_handle.cancel_goal_async()
                    break
                # /nav/pause was just called → cancel underlying nav goal
                if self._fsm.state == RouteState.PAUSED:
                    self.get_logger().info("pause active during waypoint; cancelling Nav2 goal")
                    await nav_handle.cancel_goal_async()
                    break
                # Timeout
                elapsed_ns = self.get_clock().now().nanoseconds - start_ns
                if elapsed_ns > int(timeout_sec * 1e9):
                    timed_out = True
                    self.get_logger().warn(
                        f"waypoint {wp['id']} timeout after {timeout_sec}s; cancelling"
                    )
                    await nav_handle.cancel_goal_async()
                    break
                await asyncio.sleep(0.1)

            # Drain the result so Nav2 client doesn't leak.
            try:
                nav_result = await asyncio.wait_for(nav_result_future, timeout=2.0)
            except asyncio.TimeoutError:
                nav_result = None

            self._current_nav_handle = None

            # Decide next FSM action
            if self._fsm.state == RouteState.PAUSED:
                # Stay paused; next loop iteration will await pause_event
                continue
            if self._fsm.state == RouteState.FAILED:
                break
            if timed_out:
                self._fsm.cancel()
                result.message = "waypoint_timeout"
                continue
            if goal_handle.is_cancel_requested:
                self._fsm.cancel()
                result.message = "cancelled"
                continue

            if nav_result is None or nav_result.status != GoalStatus.STATUS_SUCCEEDED:
                self._fsm.cancel()
                result.message = "nav2_failed"
                continue

            # Waypoint reached — emit event then transition by task type
            self._emit_waypoint_reached(route["route_id"], wp)
            try:
                self._fsm.waypoint_reached(task=wp["task"])
            except IllegalTransition:
                self._fsm.cancel()
                continue

            if self._fsm.state == RouteState.WAITING:
                wait_sec = float(wp.get("wait_sec", 0))
                self.get_logger().info(f"waypoint {wp['id']} wait {wait_sec}s")
                await asyncio.sleep(wait_sec)
                self._fsm.task_complete()
            elif self._fsm.state == RouteState.TTS:
                tts_text = wp.get("tts_text", "")
                self.get_logger().info(f"waypoint {wp['id']} tts: {tts_text!r}")
                tts_msg = String()
                tts_msg.data = tts_text
                self._tts_pub.publish(tts_msg)
                # 0.5s grace for tts pipeline to consume
                await asyncio.sleep(0.5)
                self._fsm.task_complete()

        # Loop exited — finalize result
        self._publish_internal_status()
        completed = self._fsm.current_waypoint_index
        if self._fsm.state == RouteState.SUCCEEDED:
            result.success = True
            result.waypoints_completed = completed
            result.waypoints_total = len(waypoints)
            result.message = "completed"
            goal_handle.succeed()
        else:
            result.success = False
            result.waypoints_completed = completed
            result.waypoints_total = len(waypoints)
            if not result.message:
                result.message = "cancelled_or_failed"
            # Distinguish cancel vs abort
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
            else:
                goal_handle.abort()

        # Reset FSM so next run_route call starts cleanly
        self._reset_fsm()
        return result

    # ── Services ──
    def _svc_pause(self, _req, resp):
        # /state/nav/paused is a GLOBAL pause state (BUG #2 fix). Publish unconditionally
        # so goto_relative / goto_named also halt — they don't have their own FSM and
        # rely solely on the latched Bool. Then attempt route-FSM pause; if no route is
        # active that's fine, the goto_* paths still get paused via the topic.
        self._publish_paused(True)
        # Cancel any in-flight Nav2 goal owned by route_runner. (goto_relative cancels
        # its own Nav2 handle when it observes /state/nav/paused -> True.)
        if self._current_nav_handle is not None:
            self._current_nav_handle.cancel_goal_async()
        fsm_paused = False
        try:
            self._fsm.pause()
            self._pause_event.clear()
            fsm_paused = True
        except IllegalTransition:
            pass  # no active route — that's OK, /state/nav/paused still True for goto_*
        self._publish_internal_status()
        if fsm_paused:
            self.get_logger().info(
                "paused (route at waypoint %d + global paused=true)"
                % self._fsm.current_waypoint_index
            )
            resp.message = "paused"
        else:
            self.get_logger().info(
                "global paused=true (no active route; goto_relative/named will halt)"
            )
            resp.message = "paused_no_route"
        resp.success = True
        return resp

    def _svc_resume(self, _req, resp):
        # Mirror of _svc_pause: clear /state/nav/paused unconditionally so goto_* can
        # re-send their cached goal. Route-FSM resume is best-effort.
        self._publish_paused(False)
        fsm_resumed = False
        try:
            self._fsm.resume()
            self._pause_event.set()
            fsm_resumed = True
        except IllegalTransition:
            pass
        self._publish_internal_status()
        if fsm_resumed:
            self.get_logger().info("resumed (route + global paused=false)")
            resp.message = "resumed"
        else:
            self.get_logger().info("global paused=false (no route to resume)")
            resp.message = "resumed_no_route"
        resp.success = True
        return resp

    def _svc_cancel(self, _req, resp):
        try:
            self._fsm.cancel()
        except IllegalTransition:
            pass  # already non-active is OK
        if self._current_nav_handle is not None:
            self._current_nav_handle.cancel_goal_async()
        self._pause_event.set()  # unblock the loop so it can exit
        self._publish_paused(False)
        self._publish_internal_status()
        self.get_logger().info("route cancelled by /nav/cancel service")
        resp.success = True
        return resp


def main():
    rclpy.init()
    node = RouteRunnerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
