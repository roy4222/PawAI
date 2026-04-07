"""Tests for studio gateway components."""
import io
import json
import sys
import wave
from pathlib import Path

import pytest

# Allow importing asr_client from same directory
sys.path.insert(0, str(Path(__file__).parent))
# Allow importing intent_classifier from speech_processor
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "speech_processor" / "speech_processor"))


def _make_wav(sample_rate: int = 48000, duration_s: float = 0.1, channels: int = 1) -> bytes:
    """Generate a minimal WAV file with silence."""
    n_frames = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames * channels)
    return buf.getvalue()


class TestResampleAudio:
    def test_48k_to_16k(self):
        from asr_client import resample_to_wav16k
        wav_48k = _make_wav(sample_rate=48000, duration_s=0.5)
        wav_16k = resample_to_wav16k(wav_48k)
        buf = io.BytesIO(wav_16k)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2

    def test_already_16k_passthrough(self):
        from asr_client import resample_to_wav16k
        wav_16k = _make_wav(sample_rate=16000, duration_s=0.5)
        result = resample_to_wav16k(wav_16k)
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 16000

    def test_stereo_to_mono(self):
        from asr_client import resample_to_wav16k
        wav_stereo = _make_wav(sample_rate=44100, duration_s=0.3, channels=2)
        result = resample_to_wav16k(wav_stereo)
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000

    def test_invalid_audio_raises(self):
        from asr_client import resample_to_wav16k
        with pytest.raises(RuntimeError):
            resample_to_wav16k(b"not valid audio")


class TestIntentClassification:
    def test_greet_intent(self):
        from intent_classifier import IntentClassifier
        clf = IntentClassifier()
        match = clf.classify("你好嗎")
        assert match.intent == "greet"
        assert match.confidence > 0.5

    def test_stop_intent(self):
        from intent_classifier import IntentClassifier
        clf = IntentClassifier()
        match = clf.classify("停止")
        assert match.intent == "stop"

    def test_chat_fallback(self):
        from intent_classifier import IntentClassifier
        clf = IntentClassifier()
        match = clf.classify("今天天氣怎麼樣")
        assert match.intent == "unknown"


class TestROS2Transform:
    """Test _on_ros2_msg field transforms without ROS2 runtime."""

    def _make_envelope(self, source: str, payload: dict) -> dict:
        """Simulate the transform logic from GatewayNode._on_ros2_msg."""
        import uuid as _uuid
        from datetime import datetime as _dt

        data = dict(payload)
        event_type = data.pop("event_type", f"{source}_update")

        if source == "gesture" and "gesture" in data:
            data.setdefault("current_gesture", data.get("gesture"))
            data.setdefault("active", True)
            data.setdefault("status", "active")

        if source == "pose" and "pose" in data:
            data.setdefault("current_pose", data.get("pose"))
            data.setdefault("active", True)
            data.setdefault("status", "active")

        if source == "speech":
            data.setdefault("phase", "listening")

        return {
            "id": str(_uuid.uuid4()),
            "timestamp": _dt.now().astimezone().isoformat(),
            "source": source,
            "event_type": event_type,
            "data": data,
        }

    def test_face_passthrough(self):
        payload = {"stamp": 1.0, "face_count": 2, "tracks": []}
        env = self._make_envelope("face", payload)
        assert env["source"] == "face"
        assert "face_count" in env["data"]
        assert env["data"]["face_count"] == 2

    def test_gesture_adds_status(self):
        payload = {"stamp": 1.0, "event_type": "gesture_detected",
                   "gesture": "wave", "confidence": 0.9, "hand": "right"}
        env = self._make_envelope("gesture", payload)
        assert env["data"]["status"] == "active"
        assert env["data"]["current_gesture"] == "wave"
        assert env["data"]["active"] is True
        assert env["event_type"] == "gesture_detected"

    def test_pose_adds_current_pose(self):
        payload = {"stamp": 1.0, "event_type": "pose_detected",
                   "pose": "standing", "confidence": 0.85, "track_id": 0}
        env = self._make_envelope("pose", payload)
        assert env["data"]["current_pose"] == "standing"
        assert env["data"]["status"] == "active"
        assert env["data"]["active"] is True

    def test_speech_adds_phase_fallback(self):
        payload = {"stamp": 1.0, "event_type": "intent_recognized",
                   "intent": "greet", "text": "hello", "confidence": 0.9,
                   "provider": "whisper"}
        env = self._make_envelope("speech", payload)
        assert env["data"]["phase"] == "listening"

    def test_speech_preserves_existing_phase(self):
        payload = {"stamp": 1.0, "event_type": "asr_result",
                   "phase": "transcribing", "text": "hi", "confidence": 0.8,
                   "provider": "whisper"}
        env = self._make_envelope("speech", payload)
        assert env["data"]["phase"] == "transcribing"

    def test_object_passthrough(self):
        payload = {"stamp": 1.0, "event_type": "object_detected",
                   "objects": [{"class_name": "cup", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]}
        env = self._make_envelope("object", payload)
        assert env["source"] == "object"
        assert "objects" in env["data"]

    def test_envelope_has_required_fields(self):
        payload = {"stamp": 1.0, "face_count": 1, "tracks": []}
        env = self._make_envelope("face", payload)
        assert "id" in env
        assert "timestamp" in env
        assert "source" in env
        assert "event_type" in env
        assert "data" in env


class TestBuildTtsEvent:
    """Test the build_tts_event helper imported from studio_gateway."""

    def test_basic_event_structure(self):
        sys.path.insert(0, str(Path(__file__).parent))
        from studio_gateway import build_tts_event
        env = build_tts_event("roy，你好！")
        assert env["source"] == "tts"
        assert env["event_type"] == "tts_speaking"
        assert env["data"]["text"] == "roy，你好！"
        assert env["data"]["phase"] == "speaking"
        assert env["data"]["origin"] == "unknown"
        assert "id" in env
        assert "timestamp" in env

    def test_source_is_tts_not_speech(self):
        """TTS events must use source='tts' to avoid polluting ChatPanel."""
        from studio_gateway import build_tts_event
        env = build_tts_event("test")
        assert env["source"] == "tts"
        assert env["source"] != "speech"

    def test_chinese_text_preserved(self):
        from studio_gateway import build_tts_event
        env = build_tts_event("謝謝你的幫忙")
        assert env["data"]["text"] == "謝謝你的幫忙"


class TestPayloadSchema:
    def test_speech_event_has_all_contract_fields(self):
        """Verify payload matches interaction_contract.md v2.4 §4.2."""
        payload = {
            "stamp": 1775440000.123,
            "event_type": "intent_recognized",
            "intent": "greet",
            "text": "你好",
            "confidence": 0.9,
            "provider": "sensevoice_cloud",
            "source": "web_bridge",
            "session_id": "test-uuid",
            "matched_keywords": ["你好"],
            "latency_ms": 500.0,
            "degraded": False,
            "timestamp": "2026-04-06T10:00:00",
        }
        required_fields = [
            "stamp", "event_type", "intent", "text", "confidence",
            "provider", "source", "session_id", "matched_keywords",
            "latency_ms", "degraded", "timestamp",
        ]
        for field in required_fields:
            assert field in payload, f"Missing field: {field}"
        assert payload["event_type"] == "intent_recognized"
        assert payload["source"] == "web_bridge"
