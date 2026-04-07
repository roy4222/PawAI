"""Tests for video_bridge — JPEG encoding, throttle, and client management."""
import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest

# Allow importing from gateway directory
sys.path.insert(0, str(Path(__file__).parent))


class TestJpegEncode:
    def test_bgr8_to_jpeg(self):
        from video_bridge import encode_jpeg
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:200, 100:200] = [0, 255, 0]
        jpeg = encode_jpeg(frame, quality=70)
        assert isinstance(jpeg, bytes)
        assert len(jpeg) > 0
        assert jpeg[:2] == b"\xff\xd8"

    def test_quality_affects_size(self):
        from video_bridge import encode_jpeg
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        low = encode_jpeg(frame, quality=30)
        high = encode_jpeg(frame, quality=90)
        assert len(low) < len(high)

    def test_realistic_d435_frame(self):
        from video_bridge import encode_jpeg
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        jpeg = encode_jpeg(frame, quality=70)
        assert jpeg is not None
        assert jpeg[:2] == b"\xff\xd8"
        assert 30_000 < len(jpeg) < 300_000

    def test_invalid_frame_returns_none(self):
        from video_bridge import encode_jpeg
        assert encode_jpeg(None) is None
        assert encode_jpeg(np.array([])) is None


class TestFrameThrottle:
    def test_first_frame_allowed(self):
        from video_bridge import FrameThrottle
        t = FrameThrottle(fps=5)
        assert t.should_send() is True

    def test_immediate_second_frame_dropped(self):
        from video_bridge import FrameThrottle
        t = FrameThrottle(fps=5)
        t.should_send()
        assert t.should_send() is False

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

    def test_get_returns_copy(self):
        from video_bridge import VideoClients
        vc = VideoClients()
        vc.add("face", "client1")
        copy = vc.get("face")
        copy.append("intruder")
        assert vc.get("face") == ["client1"]

    def test_broadcast_removes_dead_clients(self):
        from video_bridge import VideoClients

        class FakeWs:
            def __init__(self, fail=False):
                self.fail = fail
                self.sent = []
            async def send_bytes(self, data):
                if self.fail:
                    raise ConnectionError("dead")
                self.sent.append(data)

        vc = VideoClients()
        good = FakeWs(fail=False)
        dead = FakeWs(fail=True)
        vc.add("face", good)
        vc.add("face", dead)

        asyncio.run(vc.broadcast_bytes("face", b"jpeg_data"))
        assert good.sent == [b"jpeg_data"]
        assert dead not in vc.get("face")
        assert good in vc.get("face")


class TestVideoTopicMap:
    def test_has_three_sources(self):
        from video_bridge import VIDEO_TOPIC_MAP
        assert len(VIDEO_TOPIC_MAP) == 3
        assert "face" in VIDEO_TOPIC_MAP
        assert "vision" in VIDEO_TOPIC_MAP
        assert "object" in VIDEO_TOPIC_MAP

    def test_topics_are_ros2_paths(self):
        from video_bridge import VIDEO_TOPIC_MAP
        for topic in VIDEO_TOPIC_MAP.values():
            assert topic.startswith("/")
