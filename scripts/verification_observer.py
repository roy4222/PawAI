#!/usr/bin/env python3
"""Day 3 verification observer — subscribes to 5 event topics, appends JSONL."""

import argparse
import json
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String

# --- Config -----------------------------------------------------------

TOPICS = [
    "/event/face_identity",
    "/event/interaction/welcome",
    "/event/speech_intent_recognized",
    "/event/gesture_detected",
    "/event/pose_detected",
]

SOURCE_MAP = {
    "/event/face_identity": "face_identity_node",
    "/event/interaction/welcome": "interaction_router",
    "/event/speech_intent_recognized": "stt_intent_node",
    "/event/gesture_detected": "vision_perception_node",
    "/event/pose_detected": "vision_perception_node",
}

EVENT_TYPE_FIELD = {
    "/event/face_identity": "event_type",
    "/event/interaction/welcome": "event_type",
    "/event/speech_intent_recognized": "event_type",
    "/event/gesture_detected": "gesture",
    "/event/pose_detected": "pose",
}


class VerificationObserver(Node):
    def __init__(self, output_path):
        super().__init__("verification_observer")
        self._output_path = output_path
        self._file = open(output_path, "a")
        self._counts = defaultdict(int)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10,
        )

        for topic in TOPICS:
            self.create_subscription(
                String,
                topic,
                lambda msg, t=topic: self._on_event(t, msg),
                qos,
            )

        self.get_logger().info(f"Observer started — writing to {output_path}")
        self.get_logger().info(f"Subscribed topics: {TOPICS}")

    def _on_event(self, topic, msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            payload = {"raw": msg.data}

        event_type_field = EVENT_TYPE_FIELD.get(topic, "event_type")
        event_type = payload.get(event_type_field, "unknown")
        source = payload.get("source", SOURCE_MAP.get(topic, "unknown"))

        record = {
            "ts": time.time(),
            "topic": topic,
            "source": source,
            "event_type": event_type,
            "payload": payload,
        }

        line = json.dumps(record, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()
        self._counts[topic] += 1

        self.get_logger().info(
            f"[{topic}] event_type={event_type} (total: {self._counts[topic]})"
        )

    def print_summary(self):
        self.get_logger().info("--- Summary ---")
        total = 0
        for topic in TOPICS:
            count = self._counts[topic]
            total += count
            self.get_logger().info(f"  {topic}: {count}")
        self.get_logger().info(f"  TOTAL: {total}")
        self.get_logger().info(f"  Output: {self._output_path}")

    def destroy_node(self):
        self._file.close()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description="Day 3 verification observer")
    default_name = f"day3-verification-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("logs") / default_name),
        help="Output JSONL path",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    node = VerificationObserver(output_path)

    def shutdown(sig, frame):
        node.print_summary()
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.print_summary()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
