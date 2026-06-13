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
        assert env["data"]["origin"] == "tts"
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


class TestParseTtsPayload:
    """Test _parse_tts_payload helper from studio_gateway."""

    def test_tts_envelope_parse_extracts_text_and_origin(self):
        """JSON envelope: {text, input_origin, source} → broadcast with parsed fields."""
        sys.path.insert(0, str(Path(__file__).parent))
        from studio_gateway import _parse_tts_payload

        raw = '{"text":"我是 PawAI","input_origin":"studio_text","source":"chat_reply"}'
        parsed = _parse_tts_payload(raw)

        assert parsed["text"] == "我是 PawAI"
        assert parsed["origin"] == "studio_text"
        assert parsed["source"] == "chat_reply"

    def test_tts_plain_text_backward_compat(self):
        """Plain text (no JSON) → text only, origin/source default."""
        from studio_gateway import _parse_tts_payload

        raw = "嗨，今天好嗎？"
        parsed = _parse_tts_payload(raw)

        assert parsed["text"] == "嗨，今天好嗎？"
        assert parsed["origin"] == "tts"
        assert parsed.get("source") is None

    def test_tts_envelope_malformed_falls_back_to_text(self):
        """Malformed JSON → treat as plain text."""
        from studio_gateway import _parse_tts_payload

        raw = '{"text": "broken'  # truncated
        parsed = _parse_tts_payload(raw)

        assert parsed["text"] == raw  # original string preserved

    def test_tts_envelope_missing_text_field_falls_back(self):
        """JSON dict without 'text' field → treat as plain text."""
        from studio_gateway import _parse_tts_payload

        raw = '{"foo": "bar"}'
        parsed = _parse_tts_payload(raw)

        assert parsed["text"] == raw


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


class TestTextNormalizationGateway:
    """Integration tests for P1-3 s2twp in gateway text_normalization."""

    def test_basic_conversion(self):
        """「网络」→「網路」 when OpenCC is available."""
        sys.path.insert(0, str(Path(__file__).parent))
        try:
            from opencc import OpenCC  # noqa: F401
        except ImportError:
            pytest.skip("opencc not installed")
        # Reset module state
        import text_normalization as tn
        tn._converter = None
        result = tn.to_traditional_tw("网络")
        assert result == "網路", f"Expected 網路, got {result!r}"

    def test_empty_passthrough(self):
        """Empty string returns immediately."""
        sys.path.insert(0, str(Path(__file__).parent))
        import text_normalization as tn
        result = tn.to_traditional_tw("")
        assert result == ""

    def test_opencc_unavailable_fallback(self):
        """When OpenCC is absent, original text is returned."""
        sys.path.insert(0, str(Path(__file__).parent))
        import text_normalization as tn
        tn._converter = False
        result = tn.to_traditional_tw("网络")
        assert result == "网络"
        tn._converter = None  # restore for other tests

    def test_convert_error_fallback(self):
        """When converter.convert() raises, original text is returned."""
        sys.path.insert(0, str(Path(__file__).parent))
        from unittest.mock import MagicMock
        import text_normalization as tn
        bad = MagicMock()
        bad.convert.side_effect = RuntimeError("fail")
        tn._converter = bad
        result = tn.to_traditional_tw("网络")
        assert result == "网络"
        tn._converter = None  # restore


class TestQuatToYaw:
    """Tests for GatewayNode._quat_to_yaw (Task A nav panel — pure math, no ROS)."""

    def test_yaw_zero(self):
        sys.path.insert(0, str(Path(__file__).parent))
        from studio_gateway import GatewayNode
        # identity quaternion (qz=0, qw=1) → yaw ≈ 0
        assert abs(GatewayNode._quat_to_yaw(0.0, 1.0)) < 1e-6

    def test_yaw_90_deg(self):
        from studio_gateway import GatewayNode
        # 90° about z (qz=qw=0.70710678) → yaw ≈ π/2
        assert abs(GatewayNode._quat_to_yaw(0.70710678, 0.70710678) - 1.5707963) < 1e-4

    def test_yaw_180_deg(self):
        from studio_gateway import GatewayNode
        # 180° about z (qz=1, qw=0) → yaw ≈ ±π
        assert abs(abs(GatewayNode._quat_to_yaw(1.0, 0.0)) - 3.14159265) < 1e-4


class TestScoreboardEndpoint:
    """Tests for _read_scoreboard helper (issue #76 GET /api/scoreboard)."""

    def test_missing_file_returns_missing_provenance(self, tmp_path):
        from studio_gateway import _read_scoreboard
        out = _read_scoreboard(tmp_path / "nope.json")
        assert out["provenance"] == "missing"
        assert out["capabilities"] == []

    def test_frozen_snapshot_maps_fields(self, tmp_path):
        from studio_gateway import _read_scoreboard
        snap = {
            "schema_version": "scoreboard-0.1",
            "timestamp": "2026-06-03T06:49:40.049762+00:00",
            "wsl_commit": "2e00914",
            "run_trusted": True,
            "version_mismatch": False,
            "capabilities": {
                "face.recognition": {
                    "capability_id": "face.recognition",
                    "grade": "fail",
                    "brain_allowed": False,
                },
            },
        }
        p = tmp_path / "baseline_snapshot.json"
        p.write_text(json.dumps(snap), encoding="utf-8")
        out = _read_scoreboard(p)
        assert out["provenance"] == "frozen"
        assert out["run_trusted"] is True
        assert out["version_mismatch"] is False
        assert out["git_commit"] == "2e00914"
        cap = out["capabilities"][0]
        assert cap["capability_id"] == "face.recognition"
        assert cap["grade"] == "fail"
        assert cap["failure_reason"] == ""
        assert cap["last_tested_at"] == snap["timestamp"]

    def test_env_override_respected(self, tmp_path, monkeypatch):
        from studio_gateway import _scoreboard_path
        target = tmp_path / "custom.json"
        monkeypatch.setenv("PAWAI_SCOREBOARD_PATH", str(target))
        assert _scoreboard_path() == target


class TestTraceSessionsEndpoint:
    """Lane 2 T2-1: read-only trace session list endpoint."""

    def test_trace_sessions_lists_redaction_free_stats(self, tmp_path, monkeypatch):
        import asyncio
        from studio_gateway import get_trace_sessions

        p = tmp_path / "20260613-010000.jsonl"
        p.write_text(
            json.dumps({
                "v": 1,
                "ts": 100.0,
                "decision_id": "d1",
                "node": "brain_node",
                "kind": "policy_decision",
                "verdict": "suppressed",
                "gate": "greet_cooldown",
                "reason": "cooldown:greet:Roy",
                "detail": {"source_summary": "identity=Roy conf=0.9"},
            }) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))

        class _Req:
            headers = {}

        resp = asyncio.run(get_trace_sessions(_Req()))

        assert resp == {
            "ok": True,
            "sessions": [{
                "session_id": "20260613-010000",
                "started_ts": 100.0,
                "line_count": 1,
                "file_size": p.stat().st_size,
                "parts": ["20260613-010000.jsonl"],
            }],
        }

    def test_trace_sessions_uses_export_auth_posture(self, tmp_path, monkeypatch):
        import asyncio
        from auth import AuthConfig
        import studio_gateway

        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))
        monkeypatch.setattr(
            studio_gateway,
            "AUTH",
            AuthConfig(host="0.0.0.0", token="secret", allowed_origins=()),
        )

        class _Missing:
            headers = {}

        class _Authed:
            headers = {"authorization": "Bearer secret"}

        missing = asyncio.run(studio_gateway.get_trace_sessions(_Missing()))
        authed = asyncio.run(studio_gateway.get_trace_sessions(_Authed()))

        assert missing.status_code == 401
        assert authed["ok"] is True


def _trace_event(ts: float, decision_id: str) -> dict:
    return {
        "v": 1,
        "ts": ts,
        "decision_id": decision_id,
        "node": "brain_node",
        "kind": "policy_decision",
        "verdict": "suppressed",
        "gate": "greet_cooldown",
        "reason": "cooldown:greet:Roy",
        "detail": {"source_summary": "identity=Roy conf=0.9"},
    }


class _CaptureStreamingResponse:
    def __init__(self, content, media_type=None, **_kwargs):
        self.lines = list(content)
        self.media_type = media_type


def _captured_json_lines(resp):
    return [json.loads(line) for line in resp.lines]


class TestTraceExportEndpoint:
    """Lane 2 T2-2: session-scoped trace export."""

    def test_trace_export_session_returns_only_that_session(self, tmp_path, monkeypatch):
        import asyncio
        import studio_gateway as sg

        (tmp_path / "20260612-101500.jsonl").write_text(
            json.dumps(_trace_event(10.0, "target-1")) + "\n",
            encoding="utf-8",
        )
        (tmp_path / "20260612-101500.2.jsonl").write_text(
            json.dumps(_trace_event(20.0, "target-2")) + "\n",
            encoding="utf-8",
        )
        (tmp_path / "20260612-102000.jsonl").write_text(
            json.dumps(_trace_event(99.0, "other")) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))
        monkeypatch.setattr(sg, "StreamingResponse", _CaptureStreamingResponse)

        class _Req:
            headers = {}

        resp = asyncio.run(sg.get_trace_export(_Req(), session="20260612-101500"))
        lines = _captured_json_lines(resp)

        assert resp.media_type == "application/x-ndjson"
        assert [ev["decision_id"] for ev in lines] == ["target-1", "target-2"]
        assert all(ev["detail"]["source_summary"] == "[private]" for ev in lines)

    def test_trace_export_malicious_session_id_returns_400(self, tmp_path, monkeypatch):
        import asyncio
        import studio_gateway as sg

        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))

        class _Req:
            headers = {}

        resp = asyncio.run(sg.get_trace_export(_Req(), session="../x"))

        assert resp.status_code == 400
        assert json.loads(resp.body.decode("utf-8")) == {"error": "invalid_session"}

    def test_trace_export_redact_zero_with_session_still_403_when_auth_off(
        self, tmp_path, monkeypatch
    ):
        import asyncio
        from auth import AuthConfig
        import studio_gateway as sg

        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))
        monkeypatch.setattr(sg, "AUTH", AuthConfig(host="0.0.0.0", token="", allowed_origins=()))

        class _Req:
            headers = {}

        resp = asyncio.run(
            sg.get_trace_export(_Req(), redact=0, session="20260612-101500")
        )

        assert resp.status_code == 403
        assert json.loads(resp.body.decode("utf-8")) == {"error": "full_export_requires_auth"}

    def test_trace_export_session_composes_with_since(self, tmp_path, monkeypatch):
        import asyncio
        import studio_gateway as sg

        (tmp_path / "20260612-101500.jsonl").write_text(
            json.dumps(_trace_event(10.0, "before")) + "\n"
            + json.dumps(_trace_event(20.0, "after")) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))
        monkeypatch.setattr(sg, "StreamingResponse", _CaptureStreamingResponse)

        class _Req:
            headers = {}

        resp = asyncio.run(
            sg.get_trace_export(_Req(), since=15.0, session="20260612-101500")
        )
        lines = _captured_json_lines(resp)

        assert [ev["decision_id"] for ev in lines] == ["after"]


class TestTraceReportEndpoint:
    """Lane 2 T2-5: per-session trace report endpoint."""

    def test_trace_report_session_returns_summary_json(self, tmp_path, monkeypatch):
        import asyncio
        import studio_gateway as sg

        session_id = "20260613-123456"
        (tmp_path / f"{session_id}.jsonl").write_text(
            json.dumps(_trace_event(10.0, "target-1")) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))

        class _Req:
            headers = {}

        summary = asyncio.run(sg.get_trace_report(_Req(), session=session_id))

        assert summary["session_id"] == session_id
        assert summary["event_count"] == 1
        assert {"time_range", "verdict_distribution", "top_suppressed_gates",
                "shadow_divergence"} <= set(summary)

    def test_trace_report_markdown_format_returns_text_markdown(self, tmp_path, monkeypatch):
        import asyncio
        import studio_gateway as sg

        session_id = "20260613-123456"
        (tmp_path / f"{session_id}.jsonl").write_text(
            json.dumps(_trace_event(10.0, "target-1")) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))

        class _Req:
            headers = {}

        resp = asyncio.run(sg.get_trace_report(_Req(), session=session_id, format="md"))

        assert resp.media_type == "text/markdown"
        assert session_id in resp.body.decode("utf-8")

    def test_trace_report_missing_or_invalid_session_returns_400(self, tmp_path, monkeypatch):
        import asyncio
        import studio_gateway as sg

        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))

        class _Req:
            headers = {}

        missing = asyncio.run(sg.get_trace_report(_Req()))
        invalid = asyncio.run(sg.get_trace_report(_Req(), session="../x"))

        assert missing.status_code == 400
        assert invalid.status_code == 400
        assert json.loads(missing.body.decode("utf-8")) == {"error": "invalid_session"}
        assert json.loads(invalid.body.decode("utf-8")) == {"error": "invalid_session"}

    def test_trace_report_uses_export_auth_posture(self, tmp_path, monkeypatch):
        import asyncio
        from auth import AuthConfig
        import studio_gateway as sg

        session_id = "20260613-123456"
        (tmp_path / f"{session_id}.jsonl").write_text(
            json.dumps(_trace_event(10.0, "target-1")) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PAWAI_TRACE_DIR", str(tmp_path))
        monkeypatch.setattr(sg, "AUTH", AuthConfig(host="0.0.0.0", token="secret",
                                                   allowed_origins=()))

        class _Req:
            headers = {}

        resp = asyncio.run(sg.get_trace_report(_Req(), session=session_id))

        assert resp.status_code == 401
        assert json.loads(resp.body.decode("utf-8")) == {"error": "unauthorized"}


# ── Operator-controlled nav driving (S1 "move to scene") ────────


class _FakeGoalHandle:
    """Stand-in for rclpy ClientGoalHandle. Records cancel calls."""

    def __init__(self, accepted: bool = True):
        self.accepted = accepted
        self.cancel_calls = 0

    def cancel_goal_async(self):
        self.cancel_calls += 1
        return object()

    def get_result_async(self):
        # Return a future-like object that never fires in these tests; we drive
        # _on_nav_result manually instead.
        class _Fut:
            def add_done_callback(self, cb):
                pass
        return _Fut()


class _FakeActionClient:
    """Stand-in for rclpy ActionClient. server_ready toggles fail-closed path."""

    def __init__(self, server_ready: bool = True):
        self._server_ready = server_ready
        self.sent_goals = []

    def wait_for_server(self, timeout_sec=2.0):
        return self._server_ready

    def server_is_ready(self):
        return self._server_ready

    def send_goal_async(self, goal, feedback_callback=None):
        self.sent_goals.append(goal)

        class _Fut:
            def add_done_callback(self, cb):
                pass
        return _Fut()


def _make_nav_node(server_ready: bool = True):
    """Build a GatewayNode shell that exercises the REAL nav state machine
    without an rclpy runtime. Bypasses Node.__init__; wires only the attrs the
    nav methods touch. _broadcast_nav is stubbed to record envelopes.
    """
    import threading as _threading
    from studio_gateway import GatewayNode, GotoRelative

    node = GatewayNode.__new__(GatewayNode)
    node._nav_lock = _threading.Lock()
    node._nav_ctrl = {
        "state": "idle", "goal_handle": None, "goal_token": None,
        "remaining_m": 0.0, "target_m": 0.0, "danger_cancel": False,
    }
    node._nav_client = _FakeActionClient(server_ready=server_ready)
    node._broadcasts = []
    node._broadcast_nav = lambda et, data: node._broadcasts.append((et, data))

    class _Logger:
        def info(self, *a, **k):
            pass

        def warn(self, *a, **k):
            pass
    node.get_logger = lambda: _Logger()
    # GotoRelative is None on WSL — give nav_start a goal-builder stub so the
    # real dispatch path runs without go2_interfaces.
    if GotoRelative is None:
        import studio_gateway as sg

        class _Goal:
            distance = 0.0
            yaw_offset = 0.0
            max_speed = 0.0

        class _GotoStub:
            Goal = _Goal
        sg.GotoRelative = _GotoStub
        node._patched_goto = True
    else:
        node._patched_goto = False
    return node


def _unpatch_goto(node):
    if getattr(node, "_patched_goto", False):
        import studio_gateway as sg
        sg.GotoRelative = None


class TestNavStateMachine:
    """Exercise the REAL nav danger-cancel → paused_confirm → resume FSM."""

    def test_start_running(self):
        node = _make_nav_node()
        try:
            out = node.nav_start(distance=1.2)
            assert out["ok"] is True
            assert out["state"] == "running"
            assert node._nav_ctrl["state"] == "running"
            assert node._nav_ctrl["target_m"] == 1.2
            assert node._nav_ctrl["remaining_m"] == 1.2
            assert len(node._nav_client.sent_goals) == 1
        finally:
            _unpatch_goto(node)

    def test_start_clamps_distance(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=99.0)
            assert node._nav_ctrl["target_m"] == 2.0  # NAV_DISTANCE_MAX_M
            node._nav_ctrl["state"] = "idle"
            node.nav_start(distance=0.01)
            assert node._nav_ctrl["target_m"] == 0.2  # NAV_DISTANCE_MIN_M
        finally:
            _unpatch_goto(node)

    def test_start_fail_closed_when_no_server(self):
        node = _make_nav_node(server_ready=False)
        try:
            out = node.nav_start(distance=1.0)
            assert out["ok"] is False
            assert out["error"] == "nav_server_unavailable"
            assert node._nav_ctrl["state"] == "idle"
        finally:
            _unpatch_goto(node)

    def test_danger_cancels_and_paused_confirm(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.2)
            handle = _FakeGoalHandle()
            node._nav_ctrl["goal_handle"] = handle  # simulate accepted goal
            node._nav_danger_cancel()
            assert node._nav_ctrl["state"] == "paused_confirm"
            assert node._nav_ctrl["danger_cancel"] is True
            assert node._nav_ctrl["goal_token"] is None
            assert handle.cancel_calls == 1  # goal cancelled — NO auto-resume
        finally:
            _unpatch_goto(node)

    def test_danger_noop_when_not_running(self):
        node = _make_nav_node()
        try:
            # idle → danger is a no-op (nothing to cancel)
            node._nav_danger_cancel()
            assert node._nav_ctrl["state"] == "idle"
            assert node._nav_ctrl["danger_cancel"] is False
        finally:
            _unpatch_goto(node)

    def test_resume_only_from_paused_confirm(self):
        node = _make_nav_node()
        try:
            # running → resume rejected
            node.nav_start(distance=1.0)
            out = node.nav_resume()
            assert out["ok"] is False
            assert out["error"] == "not_paused"
        finally:
            _unpatch_goto(node)

    def test_resume_resends_remaining(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.2)
            node._nav_ctrl["remaining_m"] = 0.8  # simulate feedback progress
            handle = _FakeGoalHandle()
            node._nav_ctrl["goal_handle"] = handle
            node._nav_danger_cancel()
            assert node._nav_ctrl["state"] == "paused_confirm"
            before = len(node._nav_client.sent_goals)
            out = node.nav_resume()
            assert out["ok"] is True
            assert out["state"] == "running"
            assert out["remaining_m"] == 0.8
            assert len(node._nav_client.sent_goals) == before + 1
            assert node._nav_client.sent_goals[-1].distance == 0.8
        finally:
            _unpatch_goto(node)

    def test_resume_below_min_marks_done(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.2)
            node._nav_ctrl["remaining_m"] = 0.05  # below NAV_DISTANCE_MIN_M
            node._nav_danger_cancel()  # no handle → just transitions
            node._nav_ctrl["state"] = "paused_confirm"
            out = node.nav_resume()
            assert out["ok"] is True
            assert out["state"] == "done"  # no sub-deadband micro-goal
        finally:
            _unpatch_goto(node)

    def test_stop_cancels_to_idle(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.0)
            handle = _FakeGoalHandle()
            node._nav_ctrl["goal_handle"] = handle
            out = node.nav_stop()
            assert out["ok"] is True
            assert out["state"] == "idle"
            assert handle.cancel_calls == 1
        finally:
            _unpatch_goto(node)

    def test_feedback_tracks_remaining(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.2)
            token = node._nav_ctrl["goal_token"]

            class _FB:
                class feedback:
                    distance_to_goal = 0.45
            node._on_nav_feedback(token, _FB())
            assert node._nav_ctrl["remaining_m"] == 0.45
        finally:
            _unpatch_goto(node)

    def test_stale_result_does_not_flip_paused_confirm(self):
        """A late CANCELED result after danger-cancel must NOT resume the dog."""
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.0)
            stale_token = node._nav_ctrl["goal_token"]
            handle = _FakeGoalHandle()
            node._nav_ctrl["goal_handle"] = handle
            node._nav_danger_cancel()  # token cleared, state=paused_confirm

            class _Inner:
                class result:
                    success = False

            class _Fut:
                def result(self):
                    return _Inner()
            # stale result for the cancelled goal arrives late
            node._on_nav_result(stale_token, _Fut())
            assert node._nav_ctrl["state"] == "paused_confirm"
        finally:
            _unpatch_goto(node)

    def test_result_success_marks_done(self):
        node = _make_nav_node()
        try:
            node.nav_start(distance=1.0)
            token = node._nav_ctrl["goal_token"]

            class _Inner:
                class result:
                    success = True

            class _Fut:
                def result(self):
                    return _Inner()
            node._on_nav_result(token, _Fut())
            assert node._nav_ctrl["state"] == "done"
            assert node._nav_ctrl["remaining_m"] == 0.0
        finally:
            _unpatch_goto(node)


class TestNavEndpoints:
    """FastAPI endpoint wiring: node-None fail-closed + delegation to node.

    Route coroutines are driven via asyncio.run with the module-level `node`
    monkeypatched — this avoids the lifespan (which would call rclpy.init).
    The existing tests follow the same monkeypatch-`node` pattern.
    """

    def test_initialpose_node_none(self, monkeypatch):
        import asyncio
        import studio_gateway as sg
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.post_nav_initialpose(
            sg.NavInitialPosePayload(x=1.0, y=2.0, yaw=0.0)))
        assert out["ok"] is False
        assert out["error"] == "ros_node_not_ready"

    def test_initialpose_calls_publish(self, monkeypatch):
        import asyncio
        import studio_gateway as sg

        class _FakeNode:
            def __init__(self):
                self.calls = []

            def publish_initialpose(self, x, y, yaw):
                self.calls.append((x, y, yaw))
                return {"ok": True, "x": x, "y": y, "yaw": yaw}
        fn = _FakeNode()
        monkeypatch.setattr(sg, "node", fn)
        out = asyncio.run(sg.post_nav_initialpose(
            sg.NavInitialPosePayload(x=1.5, y=-0.5, yaw=0.3)))
        assert out["ok"] is True
        assert fn.calls == [(1.5, -0.5, 0.3)]

    def test_start_node_none_returns_not_ready(self, monkeypatch):
        import asyncio
        import studio_gateway as sg
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.post_nav_start(sg.NavStartPayload(distance=1.2)))
        assert out["ok"] is False
        assert out["error"] == "ros_node_not_ready"

    def test_start_delegates(self, monkeypatch):
        import asyncio
        import studio_gateway as sg

        class _FakeNode:
            def nav_start(self, distance, yaw_offset):
                return {"ok": True, "state": "running",
                        "target_m": distance, "remaining_m": distance}
        monkeypatch.setattr(sg, "node", _FakeNode())
        out = asyncio.run(sg.post_nav_start(
            sg.NavStartPayload(distance=0.9, yaw_offset=0.2)))
        assert out["ok"] is True
        assert out["state"] == "running"
        assert out["target_m"] == 0.9

    def test_control_get_returns_state(self, monkeypatch):
        import asyncio
        import studio_gateway as sg

        class _FakeNode:
            def nav_control_snapshot(self):
                return {"state": "paused_confirm", "target_m": 1.2,
                        "remaining_m": 0.6, "danger_cancel": True}
        monkeypatch.setattr(sg, "node", _FakeNode())
        out = asyncio.run(sg.get_nav_control())
        assert out["ok"] is True
        assert out["state"] == "paused_confirm"
        assert out["remaining_m"] == 0.6

    def test_control_get_node_none(self, monkeypatch):
        import asyncio
        import studio_gateway as sg
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.get_nav_control())
        assert out["ok"] is False
        assert out["error"] == "ros_node_not_ready"

    def test_resume_only_works_in_paused_confirm(self, monkeypatch):
        """Endpoint delegates; node returns not_paused outside paused_confirm."""
        import asyncio
        import studio_gateway as sg

        class _FakeNode:
            def __init__(self):
                self.state = "running"

            def nav_resume(self):
                if self.state != "paused_confirm":
                    return {"ok": False, "error": "not_paused",
                            "state": self.state}
                return {"ok": True, "state": "running"}
        fn = _FakeNode()
        monkeypatch.setattr(sg, "node", fn)
        out = asyncio.run(sg.post_nav_resume())
        assert out["ok"] is False
        assert out["error"] == "not_paused"
        fn.state = "paused_confirm"
        out2 = asyncio.run(sg.post_nav_resume())
        assert out2["ok"] is True
        assert out2["state"] == "running"

    def test_stop_delegates(self, monkeypatch):
        import asyncio
        import studio_gateway as sg

        class _FakeNode:
            def nav_stop(self):
                return {"ok": True, "state": "idle"}
        monkeypatch.setattr(sg, "node", _FakeNode())
        out = asyncio.run(sg.post_nav_stop())
        assert out["ok"] is True
        assert out["state"] == "idle"
