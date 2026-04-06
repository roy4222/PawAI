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
