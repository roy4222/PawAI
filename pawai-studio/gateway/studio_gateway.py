#!/usr/bin/env python3
"""Studio Gateway — ROS2 Bridge + Speech Bridge server.

Runs on Jetson. Subscribes to ROS2 perception topics, broadcasts to
browser via WebSocket. Also handles browser push-to-talk → ASR → ROS2.

Usage:
    source /opt/ros/humble/setup.zsh
    source install/setup.zsh
    python3 pawai-studio/gateway/studio_gateway.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String

from asr_client import resample_to_wav16k, transcribe

# Intent classifier — reuse from speech_processor (pure Python, no ROS2 dep)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "speech_processor" / "speech_processor"))
from intent_classifier import IntentClassifier

# ── Config ───────────────────────────────────────────────────────
PORT = 8080
ASR_URL = "http://127.0.0.1:8001/v1/audio/transcriptions"
STATIC_DIR = Path(__file__).parent / "static"

QOS_EVENT = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    depth=10,
)

# ROS2 topic → frontend source mapping
TOPIC_MAP: dict[str, str] = {
    "/state/perception/face":          "face",
    "/event/gesture_detected":         "gesture",
    "/event/pose_detected":            "pose",
    "/event/speech_intent_recognized": "speech",
    "/event/object_detected":          "object",
}

FACE_THROTTLE_S = 0.5  # 10Hz → 2Hz
MAX_AUDIO_BYTES = 5 * 1024 * 1024  # 5MB payload cap for speech


# ── WebSocket Connection Manager ────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                if ws in self.active:
                    self.active.remove(ws)


ws_manager = ConnectionManager()


# ── ROS2 Node ────────────────────────────────────────────────────
class GatewayNode(Node):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__("studio_gateway_node")
        self._loop = loop
        self._last_face_broadcast = 0.0

        # Publisher — speech intent (browser → ROS2)
        self.speech_pub = self.create_publisher(
            String, "/event/speech_intent_recognized", QOS_EVENT
        )

        # Subscribers — ROS2 → browser
        for topic, source in TOPIC_MAP.items():
            self.create_subscription(
                String, topic,
                lambda msg, s=source: self._on_ros2_msg(s, msg),
                QOS_EVENT,
            )

        self.get_logger().info(
            f"Studio Gateway ROS2 node ready — subscribed to {len(TOPIC_MAP)} topics"
        )

    def publish_speech_event(self, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=True)
        self.speech_pub.publish(msg)
        self.get_logger().info(
            f"Published speech event: intent={payload.get('intent')} "
            f"text={payload.get('text')!r}"
        )

    def _on_ros2_msg(self, source: str, msg: String) -> None:
        """Transform ROS2 JSON → PawAIEvent envelope and broadcast."""
        try:
            payload = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError):
            return

        # Face throttle: 10Hz → 2Hz
        if source == "face":
            now = time.monotonic()
            if now - self._last_face_broadcast < FACE_THROTTLE_S:
                return
            self._last_face_broadcast = now

        data = dict(payload)
        event_type = data.pop("event_type", f"{source}_update")

        # ── Field transforms for frontend dispatch rules ──
        # gesture: frontend checks "status" in data
        if source == "gesture" and "gesture" in data:
            data.setdefault("current_gesture", data.get("gesture"))
            data.setdefault("active", True)
            data.setdefault("status", "active")

        # pose: frontend checks "current_pose" or "status" in data
        if source == "pose" and "pose" in data:
            data.setdefault("current_pose", data.get("pose"))
            data.setdefault("active", True)
            data.setdefault("status", "active")

        # speech: frontend checks "phase" in data
        if source == "speech":
            data.setdefault("phase", "listening")

        # face: pass-through (already has face_count, tracks)
        # object: pass-through (P1 adds frontend dispatch)

        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().astimezone().isoformat(),
            "source": source,
            "event_type": event_type,
            "data": data,
        }

        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(envelope), self._loop
        )


# ── FastAPI App ──────────────────────────────────────────────────
node: GatewayNode | None = None
classifier: IntentClassifier | None = None


def _spin_ros2(ros_node: Node) -> None:
    try:
        rclpy.spin(ros_node)
    except Exception:
        pass  # ExternalShutdownException on clean exit


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global node, classifier
    rclpy.init()
    loop = asyncio.get_running_loop()
    node = GatewayNode(loop)
    classifier = IntentClassifier()
    spin_thread = threading.Thread(target=_spin_ros2, args=(node,), daemon=True)
    spin_thread.start()
    yield
    if node:
        node.destroy_node()
    rclpy.try_shutdown()


app = FastAPI(title="PawAI Studio Gateway", lifespan=lifespan)


# ── Static & Health ─────────────────────────────────────────────

@app.get("/speech")
async def speech_page():
    return FileResponse(STATIC_DIR / "speech.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "node": node is not None,
        "ws_clients": len(ws_manager.active),
        "subscriptions": list(TOPIC_MAP.keys()),
    }


# ── WebSocket: Event Broadcast (ROS2 → Browser) ────────────────

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """Broadcast ROS2 perception events to all connected browsers."""
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive / ping
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ── WebSocket: Text Input (Browser → ROS2) ─────────────────────

@app.websocket("/ws/text")
async def ws_text(ws: WebSocket):
    """Text-only mode: receive text, classify intent, publish to ROS2."""
    await ws.accept()
    try:
        while True:
            text = await ws.receive_text()
            text = text.strip()
            if not text:
                await ws.send_json({"error": "empty_text", "published": False})
                continue
            session_id = str(uuid.uuid4())[:8]
            started = time.monotonic()
            match = classifier.classify(text)
            intent = match.intent if match.intent != "unknown" else "chat"
            total_latency = (time.monotonic() - started) * 1000

            payload = {
                "stamp": time.time(),
                "event_type": "intent_recognized",
                "intent": intent,
                "text": text,
                "confidence": round(match.confidence, 3),
                "provider": "text_input",
                "source": "web_bridge",
                "session_id": session_id,
                "matched_keywords": match.matched_keywords,
                "latency_ms": round(total_latency, 2),
                "degraded": False,
                "timestamp": datetime.now().isoformat(),
            }
            node.publish_speech_event(payload)
            await ws.send_json({
                "asr": text,
                "intent": intent,
                "confidence": round(match.confidence, 3),
                "latency_ms": round(total_latency, 2),
                "published": True,
            })
    except WebSocketDisconnect:
        pass


# ── WebSocket: Speech Input (Browser → ROS2) ───────────────────

@app.websocket("/ws/speech")
async def ws_speech(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            audio_bytes = await ws.receive_bytes()

            # Payload cap — reject oversized audio
            if len(audio_bytes) > MAX_AUDIO_BYTES:
                await ws.send_json({"error": "audio_too_large", "published": False})
                continue

            session_id = str(uuid.uuid4())[:8]
            started = time.monotonic()

            try:
                # 1. Resample to 16kHz mono WAV
                print(f"[gateway] Received audio: {len(audio_bytes)} bytes", flush=True)
                wav16k = await asyncio.to_thread(resample_to_wav16k, audio_bytes)
                print(f"[gateway] Resampled WAV: {len(wav16k)} bytes", flush=True)

                # 2. ASR
                asr_result = await asyncio.to_thread(transcribe, wav16k, ASR_URL)
                text = asr_result["text"].strip()
                asr_latency = asr_result["latency_ms"]
                print(f"[gateway] ASR result: text={text!r} latency={asr_latency}ms", flush=True)

                if not text:
                    await ws.send_json({"error": "empty_asr", "published": False})
                    continue

                # 3. Intent classification
                match = classifier.classify(text)
                intent = match.intent if match.intent != "unknown" else "chat"
                total_latency = (time.monotonic() - started) * 1000

                # 4. Contract-compliant payload (interaction_contract.md v2.4 §4.2)
                payload = {
                    "stamp": time.time(),
                    "event_type": "intent_recognized",
                    "intent": intent,
                    "text": text,
                    "confidence": round(match.confidence, 3),
                    "provider": "sensevoice_cloud",
                    "source": "web_bridge",
                    "session_id": session_id,
                    "matched_keywords": match.matched_keywords,
                    "latency_ms": round(total_latency, 2),
                    "degraded": False,
                    "timestamp": datetime.now().isoformat(),
                }

                # 5. Publish to ROS2
                node.publish_speech_event(payload)

                # 6. Reply to browser
                await ws.send_json({
                    "asr": text,
                    "intent": intent,
                    "confidence": round(match.confidence, 3),
                    "latency_ms": round(total_latency, 2),
                    "published": True,
                })

            except Exception as e:
                print(f"[gateway] Speech error: {e}", flush=True)
                await ws.send_json({"error": "processing_failed", "published": False})

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, ws="wsproto")
