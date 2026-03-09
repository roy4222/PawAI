#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


@dataclass
class IntentMatch:
    intent: str
    confidence: float
    matched_keywords: List[str]


class IntentClassifier:
    def __init__(self) -> None:
        self.rules: Dict[str, List[Tuple[str, float]]] = {
            "stand": [("站起來", 1.0), ("起立", 0.9), ("站", 0.5)],
            "sit": [("坐下", 1.0), ("坐", 0.6)],
            "hello": [("打招呼", 1.0), ("哈囉", 0.9), ("你好", 0.9), ("hello", 0.8)],
            "stop": [("停止", 1.0), ("停下", 1.0), ("stop", 1.0)],
            "chat": [
                ("你是誰", 1.0),
                ("做什麼", 0.8),
                ("介紹", 0.7),
                ("who are you", 0.8),
            ],
        }

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def classify(self, text: str) -> IntentMatch:
        normalized = self._normalize(text)
        if not normalized:
            return IntentMatch(intent="unknown", confidence=0.0, matched_keywords=[])

        best_intent = "unknown"
        best_score = 0.0
        best_keywords: List[str] = []

        for intent, entries in self.rules.items():
            score = 0.0
            matched: List[str] = []
            for keyword, weight in entries:
                if keyword in normalized:
                    score += weight
                    matched.append(keyword)

            if matched:
                normalized_score = min(1.0, score / max(1.0, len(matched)))
                if normalized_score > best_score:
                    best_intent = intent
                    best_score = normalized_score
                    best_keywords = matched

        return IntentMatch(
            intent=best_intent, confidence=best_score, matched_keywords=best_keywords
        )


class IntentNode(Node):
    def __init__(self) -> None:
        super().__init__("intent_node")

        self._declare_parameters()

        self.asr_result_topic = str(
            self.get_parameter("asr_result_topic").get_parameter_value().string_value
        )
        self.intent_topic = str(
            self.get_parameter("intent_topic").get_parameter_value().string_value
        )
        self.intent_event_topic = str(
            self.get_parameter("intent_event_topic").get_parameter_value().string_value
        )
        self.state_topic = str(
            self.get_parameter("state_topic").get_parameter_value().string_value
        )
        self.min_confidence = float(
            self.get_parameter("min_confidence").get_parameter_value().double_value
        )
        self.state_publish_hz = float(
            self.get_parameter("state_publish_hz").get_parameter_value().double_value
        )

        self.classifier = IntentClassifier()
        self.intent_pub = self.create_publisher(String, self.intent_topic, 10)
        self.intent_event_pub = self.create_publisher(
            String, self.intent_event_topic, 10
        )
        self.state_pub = self.create_publisher(String, self.state_topic, 10)

        self.asr_sub = self.create_subscription(
            String, self.asr_result_topic, self._on_asr_result, 10
        )

        self.last_session_id = ""
        self.last_text = ""
        self.last_intent = "unknown"
        self.last_confidence = 0.0
        self.last_error = ""

        self.state_timer = self.create_timer(
            1.0 / self.state_publish_hz, self._publish_state
        )
        self.get_logger().info(f"intent_node ready (asr_topic={self.asr_result_topic})")

    def _declare_parameters(self) -> None:
        self.declare_parameter("asr_result_topic", "/asr_result")
        self.declare_parameter("intent_topic", "/intent")
        self.declare_parameter("intent_event_topic", "/event/speech_intent_recognized")
        self.declare_parameter("state_topic", "/state/interaction/intent")
        self.declare_parameter("min_confidence", 0.55)
        self.declare_parameter("state_publish_hz", 5.0)

    def _on_asr_result(self, msg: String) -> None:
        session_id = ""
        text = ""
        try:
            payload = json.loads(msg.data)
            if isinstance(payload, dict):
                text = str(payload.get("text", "")).strip()
                session_id = str(payload.get("session_id", "")).strip()
            else:
                text = str(msg.data).strip()
        except json.JSONDecodeError:
            text = str(msg.data).strip()

        if not text:
            self.last_error = "empty transcript"
            return

        match = self.classifier.classify(text)
        if match.confidence < self.min_confidence:
            match = IntentMatch(
                intent="unknown",
                confidence=match.confidence,
                matched_keywords=match.matched_keywords,
            )

        self.last_session_id = session_id
        self.last_text = text
        self.last_intent = match.intent
        self.last_confidence = match.confidence
        self.last_error = ""

        intent_msg = String()
        intent_msg.data = match.intent
        self.intent_pub.publish(intent_msg)

        event = String()
        event.data = json.dumps(
            {
                "event": "speech_intent_recognized",
                "session_id": session_id,
                "intent": match.intent,
                "confidence": round(match.confidence, 3),
                "matched_keywords": match.matched_keywords,
                "text": text,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "node": "intent_node",
            },
            ensure_ascii=True,
        )
        self.intent_event_pub.publish(event)

    def _publish_state(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "state": "RUNNING",
                "last_session_id": self.last_session_id,
                "last_intent": self.last_intent,
                "last_confidence": round(self.last_confidence, 3),
                "last_text": self.last_text,
                "last_error": self.last_error,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            ensure_ascii=True,
        )
        self.state_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node: Optional[IntentNode] = None
    try:
        node = IntentNode()
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
