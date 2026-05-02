# PawAI Studio Live View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/studio/live` 三欄即時影像展示頁，取代 Foxglove 作為 Demo 觀測牆。

**Architecture:** Gateway 訂閱 3 個 ROS2 `sensor_msgs/Image` topic，用 cv_bridge + OpenCV JPEG 壓縮後透過獨立 WebSocket binary endpoint 送到瀏覽器。前端用 `createObjectURL` 渲染影像，overlay 從現有 state store 取數值。影像流和事件流完全分離。

**Tech Stack:** FastAPI WebSocket (binary) / cv_bridge + OpenCV / Next.js React / Zustand / Tailwind CSS

**Spec:** `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-07-studio-live-view-design.md`

---

## File Structure

| 動作 | 路徑 | 職責 |
|------|------|------|
| Create | `pawai-studio/gateway/video_bridge.py` | ROS2 Image → JPEG → WebSocket binary bridge（獨立模組） |
| Create | `pawai-studio/gateway/test_video_bridge.py` | video bridge 單元測試 |
| Modify | `pawai-studio/gateway/studio_gateway.py` | 掛載 3 個 `/ws/video/{source}` endpoint |
| Modify | `pawai-studio/gateway/test_gateway.py` | 補 video endpoint 整合測試 |
| Create | `pawai-studio/frontend/hooks/use-video-stream.ts` | WebSocket binary → objectURL hook |
| Create | `pawai-studio/frontend/components/live/live-feed-card.tsx` | 單欄影像卡片（stream + overlay + status） |
| Create | `pawai-studio/frontend/components/live/event-ticker.tsx` | 底部事件滾動條 |
| Create | `pawai-studio/frontend/app/(studio)/studio/live/page.tsx` | `/studio/live` 三欄頁面 |

---

## Task 1: Gateway Video Bridge 模組

**Files:**
- Create: `pawai-studio/gateway/video_bridge.py`
- Create: `pawai-studio/gateway/test_video_bridge.py`

### Step 1.1: 寫 video bridge 測試

- [ ] 建立 `pawai-studio/gateway/test_video_bridge.py`

```python
"""Tests for video_bridge — ROS2 Image → JPEG encoding + throttle."""
import time
import numpy as np
import pytest


class TestJpegEncode:
    def test_bgr8_to_jpeg(self):
        from video_bridge import encode_jpeg
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:200, 100:200] = [0, 255, 0]  # green square
        jpeg = encode_jpeg(frame, quality=70)
        assert isinstance(jpeg, bytes)
        assert len(jpeg) > 0
        # JPEG magic bytes
        assert jpeg[:2] == b"\xff\xd8"

    def test_quality_affects_size(self):
        from video_bridge import encode_jpeg
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        low = encode_jpeg(frame, quality=30)
        high = encode_jpeg(frame, quality=90)
        assert len(low) < len(high)

    def test_invalid_frame_returns_none(self):
        from video_bridge import encode_jpeg
        assert encode_jpeg(None, quality=70) is None
        assert encode_jpeg(np.array([]), quality=70) is None


class TestFrameThrottle:
    def test_first_frame_allowed(self):
        from video_bridge import FrameThrottle
        t = FrameThrottle(fps=5)
        assert t.should_send() is True

    def test_immediate_second_frame_dropped(self):
        from video_bridge import FrameThrottle
        t = FrameThrottle(fps=5)
        t.should_send()  # first: allowed
        assert t.should_send() is False  # too soon

    def test_frame_after_interval_allowed(self):
        from video_bridge import FrameThrottle
        t = FrameThrottle(fps=5)
        t.should_send()
        t._last_send -= 0.21  # simulate 210ms passing
        assert t.should_send() is True


class TestVideoClients:
    def test_add_remove_client(self):
        from video_bridge import VideoClients
        vc = VideoClients()
        vc.add("face", "client1")
        assert vc.get("face") == ["client1"]
        vc.remove("face", "client1")
        assert vc.get("face") == []

    def test_get_unknown_source_empty(self):
        from video_bridge import VideoClients
        vc = VideoClients()
        assert vc.get("nonexistent") == []
```

- [ ] 執行測試確認失敗

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_video_bridge.py -v
```

Expected: FAIL（`video_bridge` 不存在）

### Step 1.2: 實作 video bridge 模組

- [ ] 建立 `pawai-studio/gateway/video_bridge.py`

```python
"""Video Bridge — ROS2 Image → JPEG encoding + client management.

This module provides:
- encode_jpeg(): Convert BGR8 numpy frame to JPEG bytes
- FrameThrottle: FPS limiter per source
- VideoClients: Track WebSocket clients per video source
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── JPEG Encoding ─────────────────────────────────────────────

def encode_jpeg(frame: Any, quality: int = 70) -> bytes | None:
    """Encode a BGR8 numpy array to JPEG bytes.

    Returns None if frame is invalid.
    """
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

    def __init__(self, fps: int = 5):
        self._interval = 1.0 / fps
        self._last_send = 0.0

    def should_send(self) -> bool:
        now = time.monotonic()
        if now - self._last_send >= self._interval:
            self._last_send = now
            return True
        return False


# ── Client Registry ───────────────────────────────────────────

class VideoClients:
    """Track WebSocket clients per video source."""

    def __init__(self) -> None:
        self._clients: dict[str, list] = {}

    def add(self, source: str, ws: Any) -> None:
        self._clients.setdefault(source, []).append(ws)

    def remove(self, source: str, ws: Any) -> None:
        if source in self._clients:
            try:
                self._clients[source].remove(ws)
            except ValueError:
                pass

    def get(self, source: str) -> list:
        return self._clients.get(source, [])

    async def broadcast_bytes(self, source: str, data: bytes) -> None:
        """Send binary data to all clients of a source. Remove dead ones."""
        for ws in list(self.get(source)):
            try:
                await ws.send_bytes(data)
            except Exception:
                self.remove(source, ws)
```

- [ ] 執行測試確認全部通過

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_video_bridge.py -v
```

Expected: 8 passed

### Step 1.3: Commit

- [ ] Commit

```bash
git add pawai-studio/gateway/video_bridge.py pawai-studio/gateway/test_video_bridge.py
git commit -m "feat(gateway): video bridge module — JPEG encode + throttle + client registry"
```

---

## Task 2: Gateway 掛載 `/ws/video/{source}` — 先通 face 單路

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py`
- Modify: `pawai-studio/gateway/test_gateway.py`

### Step 2.1: 寫 video endpoint 測試

- [ ] 在 `pawai-studio/gateway/test_gateway.py` 末尾新增測試 class

```python
class TestVideoEndpointConfig:
    """Test video source → ROS2 topic mapping."""

    def test_video_topic_map_has_three_sources(self):
        # Validate the mapping exists and is correct
        VIDEO_TOPIC_MAP = {
            "face": "/face_identity/debug_image",
            "vision": "/vision_perception/debug_image",
            "object": "/perception/object/debug_image",
        }
        assert len(VIDEO_TOPIC_MAP) == 3
        assert "face" in VIDEO_TOPIC_MAP
        assert "vision" in VIDEO_TOPIC_MAP
        assert "object" in VIDEO_TOPIC_MAP

    def test_valid_source_names(self):
        VALID_SOURCES = {"face", "vision", "object"}
        for name in VALID_SOURCES:
            assert name.isalpha()
```

- [ ] 執行測試確認通過

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py::TestVideoEndpointConfig -v
```

Expected: 2 passed

### Step 2.2: 在 Gateway 新增 video endpoint 和 ROS2 Image 訂閱

- [ ] 修改 `pawai-studio/gateway/studio_gateway.py`

在檔案頂部 import 區塊加入：

```python
from video_bridge import encode_jpeg, FrameThrottle, VideoClients
```

在 `TOPIC_MAP` 下方加入 video 常數：

```python
# Video: ROS2 Image topic → WebSocket source name
VIDEO_TOPIC_MAP: dict[str, str] = {
    "face": "/face_identity/debug_image",
    "vision": "/vision_perception/debug_image",
    "object": "/perception/object/debug_image",
}

JPEG_QUALITY = 70
VIDEO_FPS = 5
```

在 `ws_manager = ConnectionManager()` 下方加入：

```python
video_clients = VideoClients()
```

在 `GatewayNode.__init__` 中，在現有 subscribers 迴圈之後加入：

```python
        # Video subscribers — ROS2 Image → JPEG → WebSocket binary
        self._video_throttles: dict[str, FrameThrottle] = {}
        self._cv_bridge_ok = True
        try:
            from cv_bridge import CvBridge
            self._cv_bridge = CvBridge()
        except ImportError:
            self._cv_bridge = None
            self._cv_bridge_ok = False
            self.get_logger().warn(
                "cv_bridge not available — video endpoints will show NO SIGNAL"
            )

        if self._cv_bridge_ok:
            from sensor_msgs.msg import Image as RosImage
            from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
            video_qos = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.VOLATILE,
                depth=1,
            )
            for source, topic in VIDEO_TOPIC_MAP.items():
                self._video_throttles[source] = FrameThrottle(fps=VIDEO_FPS)
                self.create_subscription(
                    RosImage, topic,
                    lambda msg, s=source: self._on_video_frame(s, msg),
                    video_qos,
                )
            self.get_logger().info(
                f"Video bridge ready — subscribed to {len(VIDEO_TOPIC_MAP)} image topics"
            )
```

在 `GatewayNode` 中加入 `_on_video_frame` 方法：

```python
    def _on_video_frame(self, source: str, msg) -> None:
        """ROS2 Image callback → JPEG encode → broadcast to video clients."""
        # Throttle
        throttle = self._video_throttles.get(source)
        if throttle and not throttle.should_send():
            return

        # No clients → skip encoding
        if not video_clients.get(source):
            return

        try:
            frame = self._cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"cv_bridge convert failed for {source}: {e}")
            return

        jpeg = encode_jpeg(frame, quality=JPEG_QUALITY)
        if jpeg is None:
            return

        asyncio.run_coroutine_threadsafe(
            video_clients.broadcast_bytes(source, jpeg), self._loop
        )
```

在 `ws_events` endpoint 之後加入 3 個 video endpoint：

```python
# ── WebSocket: Video Streams (ROS2 Image → Browser) ──────────

@app.websocket("/ws/video/{source}")
async def ws_video(ws: WebSocket, source: str):
    """Stream JPEG frames for a specific video source."""
    if source not in VIDEO_TOPIC_MAP:
        await ws.close(code=4004, reason=f"Unknown source: {source}")
        return
    await ws.accept()
    video_clients.add(source, ws)
    try:
        while True:
            await ws.receive_text()  # keepalive / ping
    except WebSocketDisconnect:
        video_clients.remove(source, ws)
```

- [ ] 語法檢查

```bash
python3 -c "import py_compile; py_compile.compile('pawai-studio/gateway/studio_gateway.py', doraise=True)"
```

Expected: 無錯誤

### Step 2.3: Commit

- [ ] Commit

```bash
git add pawai-studio/gateway/studio_gateway.py pawai-studio/gateway/test_gateway.py
git commit -m "feat(gateway): add /ws/video/{source} endpoints — 3-channel JPEG streaming"
```

---

## Task 3: 前端 `useVideoStream` Hook

**Files:**
- Create: `pawai-studio/frontend/hooks/use-video-stream.ts`

### Step 3.1: 建立 hook

- [ ] 建立 `pawai-studio/frontend/hooks/use-video-stream.ts`

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";

type VideoSource = "face" | "vision" | "object";
type StreamStatus = "connected" | "no_signal" | "disconnected";

const RECONNECT_DELAY_MS = 3000;
const NO_SIGNAL_TIMEOUT_MS = 10_000;
const FPS_BUFFER_SIZE = 10;

interface UseVideoStreamOptions {
  source: VideoSource;
  enabled?: boolean;
}

interface UseVideoStreamResult {
  imageUrl: string | null;
  fps: number;
  isConnected: boolean;
  status: StreamStatus;
}

function getWsUrl(source: VideoSource): string {
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.hostname}:8080/ws/video/${source}`;
  }
  return `ws://localhost:8080/ws/video/${source}`;
}

export function useVideoStream({
  source,
  enabled = true,
}: UseVideoStreamOptions): UseVideoStreamResult {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [status, setStatus] = useState<StreamStatus>("disconnected");

  const prevUrlRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const noSignalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameTimestamps = useRef<number[]>([]);
  const unmountedRef = useRef(false);

  // Calculate FPS from frame timestamp buffer
  const updateFps = useCallback(() => {
    const buf = frameTimestamps.current;
    if (buf.length < 2) {
      setFps(0);
      return;
    }
    const n = buf.length;
    const elapsed = buf[n - 1] - buf[0];
    if (elapsed <= 0) {
      setFps(0);
      return;
    }
    setFps(Math.round(((n - 1) * 1000) / elapsed * 10) / 10);
  }, []);

  // Reset NO SIGNAL timer
  const resetNoSignalTimer = useCallback(() => {
    if (noSignalTimer.current) clearTimeout(noSignalTimer.current);
    noSignalTimer.current = setTimeout(() => {
      if (!unmountedRef.current) setStatus("no_signal");
    }, NO_SIGNAL_TIMEOUT_MS);
  }, []);

  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (unmountedRef.current || !enabled) return;

    const url = getWsUrl(source);
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      setStatus("connected");
      frameTimestamps.current = [];
      resetNoSignalTimer();
    };

    ws.onmessage = (ev) => {
      if (unmountedRef.current) return;

      // Binary frame → objectURL
      const blob = new Blob([ev.data], { type: "image/jpeg" });
      const newUrl = URL.createObjectURL(blob);

      // Revoke previous URL to prevent memory leak
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
      }
      prevUrlRef.current = newUrl;
      setImageUrl(newUrl);

      // FPS tracking
      const now = performance.now();
      frameTimestamps.current.push(now);
      if (frameTimestamps.current.length > FPS_BUFFER_SIZE) {
        frameTimestamps.current.shift();
      }
      updateFps();

      // Reset NO SIGNAL
      setStatus("connected");
      resetNoSignalTimer();
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setStatus("disconnected");
      if (noSignalTimer.current) clearTimeout(noSignalTimer.current);
      reconnectTimer.current = setTimeout(
        () => connectRef.current(),
        RECONNECT_DELAY_MS
      );
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [source, enabled, updateFps, resetNoSignalTimer]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;

    if (enabled) {
      connect();
    }

    return () => {
      unmountedRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (noSignalTimer.current) clearTimeout(noSignalTimer.current);
      wsRef.current?.close();
      // Revoke final URL on unmount
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = null;
      }
    };
  }, [connect, enabled]);

  return {
    imageUrl,
    fps,
    isConnected: status === "connected",
    status,
  };
}
```

- [ ] TypeScript 語法檢查

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend && npx tsc --noEmit --strict hooks/use-video-stream.ts 2>&1 | head -20
```

Expected: 無錯誤（或只有 path alias 相關，不影響）

### Step 3.2: Commit

- [ ] Commit

```bash
git add pawai-studio/frontend/hooks/use-video-stream.ts
git commit -m "feat(frontend): useVideoStream hook — WebSocket binary → objectURL with FPS + NO SIGNAL"
```

---

## Task 4: `LiveFeedCard` 元件

**Files:**
- Create: `pawai-studio/frontend/components/live/live-feed-card.tsx`

### Step 4.1: 建立元件

- [ ] 建立 `pawai-studio/frontend/components/live/live-feed-card.tsx`

```tsx
"use client";

import { useVideoStream } from "@/hooks/use-video-stream";

type VideoSource = "face" | "vision" | "object";
type StreamStatus = "connected" | "no_signal" | "disconnected";

interface LiveFeedCardProps {
  source: VideoSource;
  title: string;
  children?: React.ReactNode; // overlay content
}

const STATUS_LABEL: Record<StreamStatus, string> = {
  connected: "",
  no_signal: "NO SIGNAL",
  disconnected: "DISCONNECTED",
};

function FpsBadge({ fps }: { fps: number }) {
  const color =
    fps >= 2
      ? "text-emerald-400"
      : fps > 0
        ? "text-amber-400"
        : "text-red-400";
  return (
    <span className={`font-mono text-[10px] ${color}`}>
      {fps.toFixed(1)} fps
    </span>
  );
}

export function LiveFeedCard({ source, title, children }: LiveFeedCardProps) {
  const { imageUrl, fps, status } = useVideoStream({ source });

  const showOverlay = status !== "connected";

  return (
    <div className="flex flex-col gap-1.5 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              status === "connected" ? "bg-emerald-400" : "bg-zinc-600"
            }`}
          />
          <span className="text-xs font-medium text-zinc-300 uppercase tracking-wider">
            {title}
          </span>
        </div>
        <FpsBadge fps={fps} />
      </div>

      {/* Video frame */}
      <div className="relative aspect-[4/3] bg-zinc-950 rounded-lg border border-zinc-800 overflow-hidden">
        {imageUrl && (
          <img
            src={imageUrl}
            alt={`${source} feed`}
            className="absolute inset-0 w-full h-full object-contain"
          />
        )}

        {/* Topic name — top left */}
        <div className="absolute top-2 left-2">
          <span className="text-[9px] font-mono text-zinc-500">
            {source === "face" && "/face_identity/debug_image"}
            {source === "vision" && "/vision_perception/debug_image"}
            {source === "object" && "/perception/object/debug_image"}
          </span>
        </div>

        {/* NO SIGNAL / DISCONNECTED overlay */}
        {showOverlay && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
            <span className="text-2xl font-bold text-zinc-400 tracking-widest">
              {STATUS_LABEL[status]}
            </span>
          </div>
        )}
      </div>

      {/* Overlay data — below image */}
      <div className="px-1 min-h-[2.5rem]">
        {children}
      </div>
    </div>
  );
}
```

### Step 4.2: Commit

- [ ] Commit

```bash
mkdir -p pawai-studio/frontend/components/live
git add pawai-studio/frontend/components/live/live-feed-card.tsx
git commit -m "feat(frontend): LiveFeedCard — video stream frame with status overlay"
```

---

## Task 5: `/studio/live` 三欄頁面 + Overlay

**Files:**
- Create: `pawai-studio/frontend/app/(studio)/studio/live/page.tsx`

### Step 5.1: 建立頁面

- [ ] 建立 `pawai-studio/frontend/app/(studio)/studio/live/page.tsx`

```tsx
"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { useStateStore } from "@/stores/state-store";
import { LiveFeedCard } from "@/components/live/live-feed-card";
import { LiveIndicator } from "@/components/shared/live-indicator";
import Link from "next/link";
import { PawPrint, ArrowLeft } from "lucide-react";

// ── Overlay Components ───────────────────────────────────────

function FaceOverlay() {
  const face = useStateStore((s) => s.faceState);
  if (!face) return <p className="text-xs text-zinc-600">waiting...</p>;

  const top = face.tracks?.slice(0, 3) ?? [];
  return (
    <div className="space-y-0.5">
      {top.map((t) => (
        <div key={t.track_id} className="flex items-center gap-2 text-xs">
          <span className="text-zinc-200 font-medium">
            {t.stable_name || "unknown"}
          </span>
          <span className="text-emerald-400 font-mono">
            {Math.round(t.sim * 100)}%
          </span>
          {t.distance_m != null && (
            <span className="text-zinc-500 font-mono">
              {t.distance_m.toFixed(1)}m
            </span>
          )}
          <span className="text-zinc-600 text-[10px]">{t.mode}</span>
        </div>
      ))}
      <div className="text-[10px] text-zinc-500">
        {face.face_count} face{face.face_count !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

function VisionOverlay() {
  const pose = useStateStore((s) => s.poseState);
  const gesture = useStateStore((s) => s.gestureState);

  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-zinc-400">Pose:</span>
        <span className="text-zinc-200 font-medium">
          {pose?.current_pose ?? "—"}
        </span>
        {pose?.confidence != null && (
          <span className="text-emerald-400 font-mono">
            {Math.round(pose.confidence * 100)}%
          </span>
        )}
        {pose?.current_pose === "fallen" && (
          <span className="text-red-400 font-bold animate-pulse">ALERT</span>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="text-zinc-400">Gesture:</span>
        <span className="text-zinc-200 font-medium">
          {gesture?.current_gesture ?? "—"}
        </span>
        {gesture?.hand && (
          <span className="text-zinc-500 text-[10px]">{gesture.hand}</span>
        )}
      </div>
    </div>
  );
}

function ObjectOverlay() {
  const obj = useStateStore((s) => s.objectState);
  const items = obj?.detected_objects?.slice(0, 3) ?? [];

  if (items.length === 0)
    return <p className="text-xs text-zinc-600">no objects</p>;

  return (
    <div className="space-y-0.5">
      {items.map((d, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="text-zinc-200 font-medium">{d.class_name}</span>
          <span className="text-emerald-400 font-mono">
            {Math.round(d.confidence * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────

export default function LiveViewPage() {
  const { isConnected } = useEventStream();
  const systemHealth = useStateStore((s) => s.systemHealth);
  const temp = systemHealth?.jetson?.temperature_c;

  return (
    <div className="flex flex-col h-screen bg-[#0a0f1a] text-zinc-100">
      {/* ── Status Bar ── */}
      <header className="flex items-center justify-between h-11 px-4 border-b border-zinc-800/60 shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href="/studio"
            className="flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </Link>
          <PawPrint className="h-4 w-4 text-emerald-400" />
          <span className="text-sm font-semibold tracking-tight">
            PawAI Live View
          </span>
          <span className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">
            monitor
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-zinc-500">Gateway</span>
            <LiveIndicator active={isConnected} />
          </div>
          {temp != null && (
            <span
              className={`text-[10px] font-mono ${
                temp > 75 ? "text-red-400" : temp > 60 ? "text-amber-400" : "text-zinc-500"
              }`}
            >
              Jetson {temp}°C
            </span>
          )}
        </div>
      </header>

      {/* ── Three-Column Grid ── */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 min-h-0">
        <LiveFeedCard source="face" title="Face Identity">
          <FaceOverlay />
        </LiveFeedCard>

        <LiveFeedCard source="vision" title="Gesture + Pose">
          <VisionOverlay />
        </LiveFeedCard>

        <LiveFeedCard source="object" title="Object Perception">
          <ObjectOverlay />
        </LiveFeedCard>
      </main>

      {/* ── Event Ticker ── */}
      <EventTicker />
    </div>
  );
}

// ── Event Ticker (inline) ─────────────────────────────────────

function EventTicker() {
  const events = useStateStore.getState; // We'll use event store below
  return <EventTickerInner />;
}

function EventTickerInner() {
  // Import here to keep the component self-contained in this file for now
  // Will be extracted to components/live/event-ticker.tsx in Task 6
  const { useEventStore } = require("@/stores/event-store");
  const events = useEventStore((s: { events: Array<{ timestamp: string; source: string; event_type: string }> }) => s.events);
  const recent = events.slice(0, 20);

  return (
    <div className="h-10 border-t border-zinc-800/60 flex items-center px-4 overflow-hidden shrink-0">
      <span className="text-[10px] text-zinc-600 mr-3 shrink-0">EVENTS</span>
      <div className="flex gap-4 overflow-x-auto no-scrollbar">
        {recent.map((e: { timestamp: string; source: string; event_type: string }, i: number) => {
          const time = new Date(e.timestamp).toLocaleTimeString("zh-TW", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });
          return (
            <span key={i} className="text-[10px] font-mono text-emerald-400/70 whitespace-nowrap">
              {time} {e.source}.{e.event_type}
            </span>
          );
        })}
        {recent.length === 0 && (
          <span className="text-[10px] text-zinc-700">waiting for events...</span>
        )}
      </div>
    </div>
  );
}
```

### Step 5.2: 語法檢查

- [ ] 確認 Next.js 可以找到頁面

```bash
ls -la pawai-studio/frontend/app/\(studio\)/studio/live/
```

Expected: `page.tsx` 存在

### Step 5.3: Commit

- [ ] Commit

```bash
git add pawai-studio/frontend/app/\(studio\)/studio/live/page.tsx
git commit -m "feat(frontend): /studio/live — three-column live view with overlays + event ticker"
```

---

## Task 6: 提取 Event Ticker 元件

**Files:**
- Create: `pawai-studio/frontend/components/live/event-ticker.tsx`
- Modify: `pawai-studio/frontend/app/(studio)/studio/live/page.tsx`

### Step 6.1: 建立獨立 event ticker 元件

- [ ] 建立 `pawai-studio/frontend/components/live/event-ticker.tsx`

```tsx
"use client";

import { useEventStore } from "@/stores/event-store";
import type { PawAIEvent } from "@/contracts/types";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("zh-TW", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "--:--:--";
  }
}

export function EventTicker() {
  const events = useEventStore((s) => s.events);
  const recent = events.slice(0, 20);

  return (
    <div className="h-10 border-t border-zinc-800/60 flex items-center px-4 overflow-hidden shrink-0">
      <span className="text-[10px] text-zinc-600 mr-3 shrink-0">EVENTS</span>
      <div className="flex gap-4 overflow-x-auto no-scrollbar">
        {recent.map((e: PawAIEvent, i: number) => (
          <span
            key={`${e.id}-${i}`}
            className="text-[10px] font-mono text-emerald-400/70 whitespace-nowrap"
          >
            {formatTime(e.timestamp)} {e.source}.{e.event_type}
          </span>
        ))}
        {recent.length === 0 && (
          <span className="text-[10px] text-zinc-700">
            waiting for events...
          </span>
        )}
      </div>
    </div>
  );
}
```

### Step 6.2: 更新 page.tsx 使用獨立元件

- [ ] 修改 `pawai-studio/frontend/app/(studio)/studio/live/page.tsx`

移除檔案底部的 `EventTicker` 和 `EventTickerInner` 兩個 inline 函式（整個區塊），並在檔案頂部 import 區加入：

```typescript
import { EventTicker } from "@/components/live/event-ticker";
```

### Step 6.3: Commit

- [ ] Commit

```bash
git add pawai-studio/frontend/components/live/event-ticker.tsx pawai-studio/frontend/app/\(studio\)/studio/live/page.tsx
git commit -m "refactor(frontend): extract EventTicker to standalone component"
```

---

## Task 7: 首頁加入 Live View 入口

**Files:**
- Modify: `pawai-studio/frontend/app/(studio)/studio/page.tsx`
- Modify: `pawai-studio/frontend/components/layout/topbar.tsx`

### Step 7.1: Topbar 加 Live View 連結

- [ ] 修改 `pawai-studio/frontend/components/layout/topbar.tsx`

在 `import { PawPrint } from "lucide-react"` 旁加入：

```typescript
import { Monitor } from "lucide-react"
```

在 `<div className="flex items-center gap-2">` 內（`<LiveIndicator>` 之前）加入：

```tsx
        <Link
          href="/studio/live"
          className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800/50 transition-colors"
        >
          <Monitor className="h-3 w-3" />
          LIVE
        </Link>
```

### Step 7.2: Commit

- [ ] Commit

```bash
git add pawai-studio/frontend/components/layout/topbar.tsx
git commit -m "feat(frontend): add Live View link to topbar"
```

---

## Task 8: Gateway 測試補全

**Files:**
- Modify: `pawai-studio/gateway/test_gateway.py`

### Step 8.1: 補 video bridge 整合測試

- [ ] 在 `pawai-studio/gateway/test_gateway.py` 末尾新增

```python
class TestVideoBridgeIntegration:
    """Integration tests for video_bridge used by gateway."""

    def test_encode_jpeg_from_realistic_frame(self):
        """Simulate a D435 640x480 BGR8 frame."""
        import numpy as np
        from video_bridge import encode_jpeg
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        jpeg = encode_jpeg(frame, quality=70)
        assert jpeg is not None
        assert jpeg[:2] == b"\xff\xd8"
        # Typical JPEG size for a random 640x480 frame at q70
        assert 30_000 < len(jpeg) < 300_000

    def test_throttle_respects_fps(self):
        from video_bridge import FrameThrottle
        t = FrameThrottle(fps=5)
        assert t.should_send() is True
        assert t.should_send() is False
        # Simulate 201ms passing
        t._last_send -= 0.201
        assert t.should_send() is True

    def test_video_clients_broadcast_removes_dead(self):
        import asyncio
        from video_bridge import VideoClients

        vc = VideoClients()

        class FakeWs:
            def __init__(self, fail=False):
                self.fail = fail
                self.sent = []
            async def send_bytes(self, data):
                if self.fail:
                    raise ConnectionError("dead")
                self.sent.append(data)

        good = FakeWs(fail=False)
        dead = FakeWs(fail=True)
        vc.add("face", good)
        vc.add("face", dead)

        asyncio.run(vc.broadcast_bytes("face", b"jpeg_data"))
        assert good.sent == [b"jpeg_data"]
        # Dead client should be removed
        assert dead not in vc.get("face")
        assert good in vc.get("face")
```

- [ ] 執行全部 gateway 測試

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py pawai-studio/gateway/test_video_bridge.py -v
```

Expected: 全部通過

### Step 8.2: Commit

- [ ] Commit

```bash
git add pawai-studio/gateway/test_gateway.py
git commit -m "test(gateway): add video bridge integration tests"
```

---

## Task 9: no-scrollbar CSS utility

**Files:**
- Modify: `pawai-studio/frontend/app/globals.css`

### Step 9.1: 加入 no-scrollbar utility

Event ticker 用了 `no-scrollbar` class 隱藏橫向捲軸。需在 globals.css 加入：

- [ ] 在 `pawai-studio/frontend/app/globals.css` 的 `@layer utilities` 區塊（如果沒有就在檔案末尾）加入：

```css
@layer utilities {
  .no-scrollbar::-webkit-scrollbar {
    display: none;
  }
  .no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
}
```

> 如果 `@layer utilities` 已存在，把內容加入即可，不要重複宣告。

### Step 9.2: Commit

- [ ] Commit

```bash
git add pawai-studio/frontend/app/globals.css
git commit -m "style(frontend): add no-scrollbar utility for event ticker"
```

---

## Summary

| Task | 內容 | 檔案數 |
|:----:|------|:------:|
| 1 | Video bridge 模組（encode + throttle + clients） | 2 new |
| 2 | Gateway 掛載 `/ws/video/{source}` | 2 modify |
| 3 | `useVideoStream` hook | 1 new |
| 4 | `LiveFeedCard` 元件 | 1 new |
| 5 | `/studio/live` 三欄頁面 + overlay | 1 new |
| 6 | 提取 EventTicker 元件 | 1 new, 1 modify |
| 7 | Topbar 加 Live View 入口 | 1 modify |
| 8 | Gateway 測試補全 | 1 modify |
| 9 | CSS utility | 1 modify |

**總計**：6 new files, 5 modifications, 9 commits
