"""Interaction Executive v0 — ROS2 thin orchestrator node.

Subscribes to all perception events, routes through state machine,
publishes actions and status. Day 5 scope: listen-only alongside
existing bridges. Day 6 will migrate bridges to this node.
"""
import json
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from go2_interfaces.msg import WebRtcReq

from .state_machine import (
    ExecutiveStateMachine,
    ExecutiveState,
    EventType,
    EventResult,
)

QOS_EVENT = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_STATE = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class InteractionExecutiveNode(Node):
    def __init__(self):
        super().__init__("interaction_executive_node")

        self._sm = ExecutiveStateMachine()

        # --- Publishers ---
        self._pub_tts = self.create_publisher(String, "/tts", 10)
        self._pub_webrtc = self.create_publisher(WebRtcReq, "/webrtc_req", 10)
        self._pub_cmd_vel = self.create_publisher(Twist, "/cmd_vel", 10)
        self._pub_status = self.create_publisher(String, "/executive/status", QOS_STATE)

        # --- Subscribers ---
        self.create_subscription(
            String, "/event/face_identity", self._on_face, QOS_EVENT
        )
        self.create_subscription(
            String, "/event/speech_intent_recognized", self._on_speech, QOS_EVENT
        )
        self.create_subscription(
            String, "/event/gesture_detected", self._on_gesture, QOS_EVENT
        )
        self.create_subscription(
            String, "/event/pose_detected", self._on_pose, QOS_EVENT
        )
        self.create_subscription(
            String, "/event/obstacle_detected", self._on_obstacle, QOS_EVENT
        )
        self.create_subscription(
            String, "/state/obstacle/d435_alive", self._on_d435_heartbeat, QOS_EVENT
        )
        self.create_subscription(
            String, "/event/object_detected", self._on_object, QOS_EVENT
        )

        # --- Timers ---
        self._timeout_timer = self.create_timer(1.0, self._check_timeout)
        self._status_timer = self.create_timer(0.5, self._publish_status)
        self._obstacle_clear_timer = self.create_timer(0.5, self._check_obstacle_clear)

        self._lock = threading.Lock()  # C1 fix: protect shared state
        self._last_obstacle_time = 0.0
        self._last_d435_heartbeat = 0.0  # Sensor guard for forward motion
        self._forward_cmd = None  # Active forward command {x, y, z} or None
        self._forward_timer = self.create_timer(0.1, self._send_forward)  # 10Hz cmd_vel

        self.get_logger().info("Executive v0 started — thin orchestrator mode")

    def _on_face(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        event_type_str = data.get("event_type", "")
        if event_type_str == "identity_stable":
            identity = data.get("stable_name", "unknown")
            if identity != "unknown":
                result = self._sm.handle_event(
                    EventType.FACE_WELCOME, source=identity, data=data
                )
                self._execute_result(result)

    def _on_speech(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        result = self._sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data=data
        )
        self._execute_result(result)

    def _on_gesture(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        gesture = data.get("gesture", "")
        result = self._sm.handle_event(
            EventType.GESTURE, source="cam", data={"gesture": gesture}
        )
        self._execute_result(result)

    def _on_pose(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        pose = data.get("pose", "")
        if pose == "fallen":
            result = self._sm.handle_event(EventType.POSE_FALLEN)
            self._execute_result(result)

    def _on_obstacle(self, msg: String):
        with self._lock:
            self._last_obstacle_time = time.monotonic()
        result = self._sm.handle_event(EventType.OBSTACLE)
        self._execute_result(result)

    def _on_object(self, msg: String):
        """Handle /event/object_detected — dispatch first object to state machine.

        Schema: {"stamp": float, "event_type": "object_detected",
                 "objects": [{"class_name": str, "confidence": float, "bbox": [4]}]}
        Only the first object in the array is routed (keeps Executive simple).
        Only P0 classes in OBJECT_TTS_MAP trigger TTS; others silently ignored.
        """
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        objects = data.get("objects", [])
        if not objects:
            return
        first = objects[0]
        class_name = first.get("class_name", "")
        if not class_name:
            return
        result = self._sm.handle_event(
            EventType.OBJECT_DETECTED,
            source=f"obj:{class_name}",
            data={"class_name": class_name},
        )
        self._execute_result(result)

    def _on_d435_heartbeat(self, msg: String):
        with self._lock:
            self._last_d435_heartbeat = time.monotonic()

    def _check_timeout(self):
        result = self._sm.check_timeout()
        if result:
            self._execute_result(result)

    def _check_obstacle_clear(self):
        if self._sm.state.value == "obstacle_stop":
            with self._lock:
                elapsed = time.monotonic() - self._last_obstacle_time
            if elapsed > 2.0:
                result = self._sm.try_obstacle_clear()
                if result:
                    self._execute_result(result)
            else:
                self._sm.reset_obstacle_clear()

    def _send_forward(self):
        """10Hz timer — publish cmd_vel while forward command is active."""
        with self._lock:
            if self._forward_cmd is None:
                return

            # Guard 1: state check
            state = self._sm.state
            if state in (ExecutiveState.OBSTACLE_STOP, ExecutiveState.IDLE):
                self.get_logger().info(
                    f"Forward stopped — state={state.value}"
                )
                self._forward_cmd = None
                self._pub_cmd_vel.publish(Twist())
                return

            # Guard 2: never received D435 heartbeat → refuse forward
            if self._last_d435_heartbeat == 0.0:
                self.get_logger().warn(
                    "D435 obstacle chain not detected — refusing forward"
                )
                self._forward_cmd = None
                self._pub_cmd_vel.publish(Twist())
                return

            # Guard 3: D435 heartbeat stale > 1s → emergency stop forward
            now = time.monotonic()
            if (now - self._last_d435_heartbeat) > 1.0:
                self.get_logger().warn(
                    "D435 obstacle chain stale >1s — stopping forward for safety"
                )
                self._forward_cmd = None
                self._pub_cmd_vel.publish(Twist())
                return

            # All guards passed — safe to move
            twist = Twist()
            twist.linear.x = self._forward_cmd["x"]
            twist.linear.y = self._forward_cmd["y"]
            twist.angular.z = self._forward_cmd["z"]
            self._pub_cmd_vel.publish(twist)

    def _execute_result(self, result: EventResult):
        if result.tts:
            msg = String()
            msg.data = result.tts
            self._pub_tts.publish(msg)
            self.get_logger().info(f"TTS: {result.tts}")

        if result.action:
            if result.action.get("cmd_vel"):
                # Continuous movement command
                with self._lock:
                    self._forward_cmd = {
                        "x": result.action.get("x", 0.0),
                        "y": result.action.get("y", 0.0),
                        "z": result.action.get("z", 0.0),
                    }
                self.get_logger().info(
                    f"Forward: x={self._forward_cmd['x']} y={self._forward_cmd['y']}"
                )
            else:
                # One-shot WebRtcReq action
                # Stop any forward movement when a one-shot action fires
                with self._lock:
                    was_forward = self._forward_cmd is not None
                    self._forward_cmd = None
                if was_forward:
                    self._pub_cmd_vel.publish(Twist())
                req = WebRtcReq()
                req.id = 0
                req.topic = result.action.get("topic", "rt/api/sport/request")
                req.api_id = result.action.get("api_id", 0)
                req.parameter = result.action.get("parameter", "")
                req.priority = result.action.get("priority", 0)
                self._pub_webrtc.publish(req)
                self.get_logger().info(
                    f"Action: api_id={req.api_id} priority={req.priority}"
                )

    def _publish_status(self):
        status = self._sm.get_status()
        msg = String()
        msg.data = json.dumps(status)
        self._pub_status.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = InteractionExecutiveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
