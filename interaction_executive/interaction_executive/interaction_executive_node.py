"""Interaction Executive v0 — ROS2 thin orchestrator node.

Subscribes to all perception events, routes through state machine,
publishes actions and status. Day 5 scope: listen-only alongside
existing bridges. Day 6 will migrate bridges to this node.
"""
import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from go2_interfaces.msg import WebRtcReq

from .state_machine import (
    ExecutiveStateMachine,
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

        # --- Timers ---
        self._timeout_timer = self.create_timer(1.0, self._check_timeout)
        self._status_timer = self.create_timer(0.5, self._publish_status)
        self._obstacle_clear_timer = self.create_timer(0.5, self._check_obstacle_clear)

        self._last_obstacle_time = 0.0

        self.get_logger().info("Executive v0 started — thin orchestrator mode")

    def _on_face(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        event_type_str = data.get("event_type", "")
        if event_type_str == "identity_stable":
            identity = data.get("identity", "unknown")
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
        self._last_obstacle_time = time.monotonic()
        result = self._sm.handle_event(EventType.OBSTACLE)
        self._execute_result(result)

    def _check_timeout(self):
        result = self._sm.check_timeout()
        if result:
            self._execute_result(result)

    def _check_obstacle_clear(self):
        if self._sm.state.value == "obstacle_stop":
            if (time.monotonic() - self._last_obstacle_time) > 2.0:
                self._sm._obstacle_clear_time = (
                    self._sm._obstacle_clear_time or time.monotonic()
                )
                result = self._sm.try_obstacle_clear()
                if result:
                    self._execute_result(result)
            else:
                self._sm._obstacle_clear_time = None

    def _execute_result(self, result: EventResult):
        if result.tts:
            msg = String()
            msg.data = result.tts
            self._pub_tts.publish(msg)
            self.get_logger().info(f"TTS: {result.tts}")

        if result.action:
            req = WebRtcReq()
            req.api_id = result.action.get("api_id", 0)
            self._pub_webrtc.publish(req)
            self.get_logger().info(f"Action: api_id={req.api_id}")

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
