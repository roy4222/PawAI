"""Log pose action server: 記錄當前 /amcl_pose 到 named_poses 或 route JSON。

Phase 5.2 implementation of nav_capability spec §3.1 A4.
"""
import json
import os
from datetime import datetime
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy

from go2_interfaces.action import LogPose
from nav_capability.lib.tf_pose_helper import quat_to_yaw

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class LogPoseNode(Node):
    def __init__(self):
        super().__init__("log_pose_node")
        self._cb = ReentrantCallbackGroup()

        self.declare_parameter("named_poses_file", "")
        self.declare_parameter("routes_dir", "")
        self.declare_parameter("map_id", "unknown_map")

        self._amcl: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl,
            AMCL_QOS,
            callback_group=self._cb,
        )

        self._server = ActionServer(
            self,
            LogPose,
            "/log_pose",
            execute_callback=self._execute,
            callback_group=self._cb,
        )

        self.get_logger().info("log_pose_node ready (/log_pose)")

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl = msg

    async def _execute(self, goal_handle):
        goal = goal_handle.request
        result = LogPose.Result()

        if self._amcl is None:
            self.get_logger().warn("amcl_pose not received; cannot log_pose")
            goal_handle.abort()
            result.success = False
            result.saved_path = ""
            return result

        # Extract current pose
        p = self._amcl.pose.pose
        yaw = quat_to_yaw(
            p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w
        )
        recorded_dict = {"x": float(p.position.x), "y": float(p.position.y), "yaw": float(yaw)}
        result.recorded_pose = p

        if goal.log_target == "named_poses":
            path = self.get_parameter("named_poses_file").value
            if not path:
                self.get_logger().warn("named_poses_file param empty; cannot log named")
                goal_handle.abort()
                result.success = False
                result.saved_path = ""
                return result
            self._upsert_named(path, goal.name, recorded_dict)
            result.saved_path = path
            self.get_logger().info(
                f"logged named pose '{goal.name}' = {recorded_dict} -> {path}"
            )
        elif goal.log_target == "route":
            routes_dir = self.get_parameter("routes_dir").value
            if not routes_dir or not goal.route_id:
                self.get_logger().warn(
                    f"routes_dir or route_id empty (dir={routes_dir!r} id={goal.route_id!r})"
                )
                goal_handle.abort()
                result.success = False
                result.saved_path = ""
                return result
            path = os.path.join(routes_dir, f"{goal.route_id}.json")
            self._append_waypoint(
                path, goal.route_id, goal.name, goal.task_type or "normal", recorded_dict
            )
            result.saved_path = path
            self.get_logger().info(
                f"appended waypoint '{goal.name}' (task={goal.task_type or 'normal'}) -> {path}"
            )
        else:
            self.get_logger().warn(
                f"unknown log_target: {goal.log_target!r} (expected 'named_poses' or 'route')"
            )
            goal_handle.abort()
            result.success = False
            result.saved_path = ""
            return result

        result.success = True
        goal_handle.succeed()
        return result

    def _upsert_named(self, path: str, name: str, pose: dict) -> None:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "schema_version": 1,
                "map_id": self.get_parameter("map_id").value,
                "poses": {},
            }
        data.setdefault("poses", {})[name] = pose
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _append_waypoint(
        self, path: str, route_id: str, wp_id: str, task_type: str, pose: dict
    ) -> None:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "schema_version": 1,
                "route_id": route_id,
                "frame_id": "map",
                "map_id": self.get_parameter("map_id").value,
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "initial_pose": pose,
                "waypoints": [],
            }
        wp = {
            "id": wp_id,
            "task": task_type,
            "pose": pose,
            "tolerance": 0.30,
            "timeout_sec": 30,
        }
        data.setdefault("waypoints", []).append(wp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    rclpy.init()
    node = LogPoseNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
