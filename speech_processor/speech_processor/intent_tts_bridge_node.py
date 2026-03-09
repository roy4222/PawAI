#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

import json
from datetime import datetime, timezone
from typing import Dict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class IntentTtsBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("intent_tts_bridge_node")

        self._declare_parameters()

        self.intent_event_topic = str(
            self.get_parameter("intent_event_topic").get_parameter_value().string_value
        )
        self.tts_topic = str(
            self.get_parameter("tts_topic").get_parameter_value().string_value
        )
        self.state_topic = str(
            self.get_parameter("state_topic").get_parameter_value().string_value
        )
        self.enable_unknown_reply = bool(
            self.get_parameter("enable_unknown_reply").get_parameter_value().bool_value
        )
        self.state_publish_hz = float(
            self.get_parameter("state_publish_hz").get_parameter_value().double_value
        )

        self.reply_templates: Dict[str, str] = {
            "hello": "哈囉，我在這裡。",
            "sit": "收到，請坐下。",
            "stand": "收到，請站起來。",
            "stop": "好的，停止動作。",
            "chat": "我正在進行語音互動測試。",
            "unknown": "我沒聽清楚，請再說一次。",
        }

        self.tts_pub = self.create_publisher(String, self.tts_topic, 10)
        self.state_pub = self.create_publisher(String, self.state_topic, 10)
        self.intent_sub = self.create_subscription(
            String,
            self.intent_event_topic,
            self._on_intent_event,
            10,
        )

        self.last_session_id = ""
        self.last_intent = ""
        self.last_reply = ""
        self.last_error = ""

        self._seen_sessions = set()
        self.state_timer = self.create_timer(
            1.0 / self.state_publish_hz, self._publish_state
        )
        self.get_logger().info(
            f"intent_tts_bridge_node ready (intent_event={self.intent_event_topic}, tts_topic={self.tts_topic})"
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("intent_event_topic", "/event/speech_intent_recognized")
        self.declare_parameter("tts_topic", "/tts")
        self.declare_parameter("state_topic", "/state/interaction/tts_bridge")
        self.declare_parameter("enable_unknown_reply", True)
        self.declare_parameter("state_publish_hz", 5.0)

    def _on_intent_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.last_error = "malformed intent event"
            return

        session_id = str(payload.get("session_id", "")).strip()
        intent = str(payload.get("intent", "unknown")).strip() or "unknown"

        if session_id and session_id in self._seen_sessions:
            return

        if intent == "unknown" and not self.enable_unknown_reply:
            return

        reply = self.reply_templates.get(intent, self.reply_templates["unknown"])

        out = String()
        out.data = reply
        self.tts_pub.publish(out)

        if session_id:
            self._seen_sessions.add(session_id)
            if len(self._seen_sessions) > 200:
                self._seen_sessions = set(list(self._seen_sessions)[-100:])

        self.last_session_id = session_id
        self.last_intent = intent
        self.last_reply = reply
        self.last_error = ""

    def _publish_state(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "state": "RUNNING",
                "last_session_id": self.last_session_id,
                "last_intent": self.last_intent,
                "last_reply": self.last_reply,
                "last_error": self.last_error,
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            ensure_ascii=True,
        )
        self.state_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = IntentTtsBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
