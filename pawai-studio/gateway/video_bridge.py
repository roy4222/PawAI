"""Video Bridge — ROS2 Image → JPEG encoding + client management.

Provides:
- encode_jpeg(): Convert BGR8 numpy frame to JPEG bytes
- FrameThrottle: FPS limiter per source
- VideoClients: Thread-safe WebSocket client registry per video source
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ROS2 Image topic → WebSocket source name
VIDEO_TOPIC_MAP: dict[str, str] = {
    "face": "/face_identity/debug_image",
    "vision": "/vision_perception/debug_image",
    "object": "/perception/object/debug_image",
}

JPEG_QUALITY = 70
VIDEO_FPS = 5


# ── JPEG Encoding ─────────────────────────────────────────────

def encode_jpeg(frame: Any, quality: int = JPEG_QUALITY) -> bytes | None:
    """Encode a BGR8 numpy array to JPEG bytes. Returns None if invalid."""
    if frame is None:
        return None
    if not isinstance(frame, np.ndarray) or frame.size == 0:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return None
    return buf.tobytes()


# ── Frame Throttle ────────────────────────────────────────────

class FrameThrottle:
    """Allow at most `fps` frames per second."""

    def __init__(self, fps: int = VIDEO_FPS):
        self._interval = 1.0 / fps
        self._last_send = 0.0

    def should_send(self) -> bool:
        now = time.monotonic()
        if now - self._last_send >= self._interval:
            self._last_send = now
            return True
        return False


# ── Client Registry (thread-safe) ─────────────────────────────

class VideoClients:
    """Thread-safe WebSocket client registry per video source.

    ROS2 callback thread calls broadcast_bytes(); FastAPI endpoint
    thread calls add()/remove(). Lock protects the mutable dict.
    """

    def __init__(self) -> None:
        self._clients: dict[str, list] = {}
        self._lock = threading.Lock()

    def add(self, source: str, ws: Any) -> None:
        with self._lock:
            self._clients.setdefault(source, []).append(ws)

    def remove(self, source: str, ws: Any) -> None:
        with self._lock:
            if source in self._clients:
                try:
                    self._clients[source].remove(ws)
                except ValueError:
                    pass

    def get(self, source: str) -> list:
        with self._lock:
            return list(self._clients.get(source, []))

    async def broadcast_bytes(self, source: str, data: bytes) -> None:
        """Send binary data to all clients of a source. Remove dead ones."""
        clients = self.get(source)
        for ws in clients:
            try:
                await ws.send_bytes(data)
            except Exception:
                self.remove(source, ws)
