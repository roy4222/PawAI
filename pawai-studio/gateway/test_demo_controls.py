"""Tests for plan4 operator manual FLOOR controls (demo_phase + offline_mode).

studio_gateway imports rclpy / std_msgs / geometry_msgs at module level. On WSL
dev boxes (and the CI fast gate) those ROS2 modules are absent, so this file
installs lightweight stubs into sys.modules BEFORE importing studio_gateway.
This keeps the cases runnable locally without a ROS2 runtime. The CI gate stays
test_auth.py + test_trace_store.py (which need no stubs); these cases are run
locally / on Jetson where ROS2 is present (the stubs are then unused harmless
duplicates only if rclpy is already importable — see _install_ros_stubs guard).
"""
import sys
import types
from pathlib import Path

import pytest

# Allow importing studio_gateway + same-dir helpers (auth/trace_store/...).
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "speech_processor" / "speech_processor"))


def _install_ros_stubs() -> None:
    """Install minimal rclpy/std_msgs/geometry_msgs stubs if ROS2 is absent.

    No-op when real rclpy is importable (Jetson) so the real classes win.
    """
    try:
        import rclpy  # noqa: F401
        return  # real ROS2 present — do not shadow it
    except ImportError:
        pass

    rclpy = types.ModuleType("rclpy")
    rclpy.init = lambda *a, **k: None
    rclpy.spin = lambda *a, **k: None

    node_mod = types.ModuleType("rclpy.node")

    class _Node:
        def __init__(self, *a, **k):
            pass

    node_mod.Node = _Node

    qos_mod = types.ModuleType("rclpy.qos")

    class _QoSProfile:
        def __init__(self, *a, **k):
            pass

    class _QoSEnum:
        RELIABLE = 1
        VOLATILE = 1
        TRANSIENT_LOCAL = 2
        BEST_EFFORT = 2

    qos_mod.QoSProfile = _QoSProfile
    qos_mod.ReliabilityPolicy = _QoSEnum
    qos_mod.DurabilityPolicy = _QoSEnum
    rclpy.node = node_mod
    rclpy.qos = qos_mod

    std = types.ModuleType("std_msgs")
    stdm = types.ModuleType("std_msgs.msg")

    class _Bool:
        def __init__(self):
            self.data = False

    class _Empty:
        def __init__(self):
            pass

    class _String:
        def __init__(self):
            self.data = ""

    stdm.Bool = _Bool
    stdm.Empty = _Empty
    stdm.String = _String
    std.msg = stdm

    geo = types.ModuleType("geometry_msgs")
    geom = types.ModuleType("geometry_msgs.msg")

    class _PoseWithCovarianceStamped:
        pass

    geom.PoseWithCovarianceStamped = _PoseWithCovarianceStamped
    geo.msg = geom

    for name, mod in {
        "rclpy": rclpy,
        "rclpy.node": node_mod,
        "rclpy.qos": qos_mod,
        "std_msgs": std,
        "std_msgs.msg": stdm,
        "geometry_msgs": geo,
        "geometry_msgs.msg": geom,
    }.items():
        sys.modules.setdefault(name, mod)


_install_ros_stubs()

import studio_gateway as sg  # noqa: E402 — must follow stub install


class _RecordingNode:
    """Stand-in for GatewayNode that records publish call order.

    Mirrors the real publish_demo_phase contract: reset_context BEFORE phase.
    """

    def __init__(self):
        self.calls: list[tuple] = []
        self._demo_phase_last: str | None = None
        self._offline_mode_last: bool | None = None

    # demo_phase
    def publish_demo_phase(self, phase: str) -> None:
        # real method publishes reset then phase — record both in order
        self.calls.append(("reset_context",))
        self.calls.append(("demo_phase", phase))
        self._demo_phase_last = phase

    def demo_phase_snapshot(self) -> str | None:
        return self._demo_phase_last

    # offline_mode
    def publish_offline_mode(self, enabled: bool) -> None:
        self.calls.append(("offline_mode", bool(enabled)))
        self._offline_mode_last = bool(enabled)

    def offline_mode_snapshot(self) -> bool | None:
        return self._offline_mode_last

    # farewell (學校 demo 道別鈕)
    def publish_farewell(self) -> dict:
        self.calls.append(("farewell",))
        return {"ok": True, "heart_sent": True, "text": "口號"}


class _FakeWsManager:
    def __init__(self):
        self.broadcasts: list[dict] = []

    async def broadcast(self, envelope: dict) -> None:
        self.broadcasts.append(envelope)


@pytest.fixture
def wired(monkeypatch):
    """Wire a recording node + fake ws_manager onto the module under test."""
    node = _RecordingNode()
    ws = _FakeWsManager()
    monkeypatch.setattr(sg, "node", node)
    monkeypatch.setattr(sg, "ws_manager", ws)
    return node, ws


# ── P4-1: demo_phase ───────────────────────────────────────────────


class TestDemoPhaseRoute:
    def test_demo_phase_post_resets_before_switch(self, wired):
        """POST a valid phase → publish records reset_context BEFORE demo_phase."""
        import asyncio
        node, _ = wired
        out = asyncio.run(sg.post_demo_phase(sg.DemoPhasePayload(phase="s2_greet")))
        assert out == {"ok": True, "phase": "s2_greet"}
        assert node.calls == [("reset_context",), ("demo_phase", "s2_greet")]
        # reset strictly precedes the phase publish
        assert node.calls.index(("reset_context",)) < node.calls.index(
            ("demo_phase", "s2_greet")
        )

    def test_demo_phase_post_rejects_invalid(self, wired):
        """Unknown phase → invalid_phase, nothing published (no silent all)."""
        import asyncio
        node, ws = wired
        out = asyncio.run(sg.post_demo_phase(sg.DemoPhasePayload(phase="s9_bogus")))
        assert out == {"ok": False, "error": "invalid_phase"}
        assert node.calls == []  # nothing published
        assert ws.broadcasts == []  # no WS broadcast on reject

    def test_demo_phase_accepts_aliases(self, wired):
        """s2_face / s3_object aliases are accepted (brain validates authoritatively)."""
        import asyncio
        node, _ = wired
        out = asyncio.run(sg.post_demo_phase(sg.DemoPhasePayload(phase="s2_face")))
        assert out == {"ok": True, "phase": "s2_face"}
        assert ("demo_phase", "s2_face") in node.calls

    def test_demo_phase_get_returns_cache(self, wired):
        """GET None before any switch; the cached phase after a switch."""
        import asyncio
        node, _ = wired
        before = asyncio.run(sg.get_demo_phase())
        assert before == {"ok": True, "phase": None}
        asyncio.run(sg.post_demo_phase(sg.DemoPhasePayload(phase="s3_pose_object")))
        after = asyncio.run(sg.get_demo_phase())
        assert after == {"ok": True, "phase": "s3_pose_object"}

    def test_demo_phase_ws_broadcast(self, wired):
        """POST → WS envelope event_type=demo_phase, data.phase set."""
        import asyncio
        _, ws = wired
        asyncio.run(sg.post_demo_phase(sg.DemoPhasePayload(phase="s4_gesture")))
        assert len(ws.broadcasts) == 1
        env = ws.broadcasts[0]
        assert env["source"] == "brain"
        assert env["event_type"] == "demo_phase"
        assert env["data"] == {"phase": "s4_gesture"}
        assert "id" in env and "timestamp" in env

    def test_demo_phase_node_none(self, monkeypatch):
        import asyncio
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.post_demo_phase(sg.DemoPhasePayload(phase="s1_nav")))
        assert out == {"ok": False, "error": "ros_node_not_ready"}

    def test_demo_phase_get_node_none(self, monkeypatch):
        import asyncio
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.get_demo_phase())
        assert out["ok"] is False
        assert out["phase"] is None


# ── P4-2: offline_mode ─────────────────────────────────────────────


class TestOfflineModeRoute:
    def test_offline_mode_post_publishes(self, wired):
        import asyncio
        node, _ = wired
        out = asyncio.run(sg.post_offline_mode(sg.OfflineModePayload(enabled=True)))
        assert out == {"ok": True, "enabled": True}
        assert node.calls == [("offline_mode", True)]

    def test_offline_mode_get_returns_cache(self, wired):
        import asyncio
        before = asyncio.run(sg.get_offline_mode())
        assert before == {"ok": True, "enabled": None}  # default OFF / untouched
        asyncio.run(sg.post_offline_mode(sg.OfflineModePayload(enabled=True)))
        after = asyncio.run(sg.get_offline_mode())
        assert after == {"ok": True, "enabled": True}

    def test_offline_mode_ws_broadcast(self, wired):
        import asyncio
        _, ws = wired
        asyncio.run(sg.post_offline_mode(sg.OfflineModePayload(enabled=False)))
        assert len(ws.broadcasts) == 1
        env = ws.broadcasts[0]
        assert env["source"] == "brain"
        assert env["event_type"] == "offline_mode"
        assert env["data"] == {"enabled": False}

    def test_offline_mode_node_none(self, monkeypatch):
        import asyncio
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.post_offline_mode(sg.OfflineModePayload(enabled=True)))
        assert out == {"ok": False, "error": "ros_node_not_ready"}


# ── 學校 demo: farewell (道別鈕) ────────────────────────────────────


class TestFarewellRoute:
    def test_farewell_post_publishes_and_returns(self, wired):
        import asyncio
        node, _ = wired
        out = asyncio.run(sg.post_farewell_action())
        assert out["ok"] is True
        assert ("farewell",) in node.calls

    def test_farewell_ws_broadcast(self, wired):
        import asyncio
        _, ws = wired
        asyncio.run(sg.post_farewell_action())
        assert len(ws.broadcasts) == 1
        env = ws.broadcasts[0]
        assert env["source"] == "brain"
        assert env["event_type"] == "farewell_action"
        assert "text" in env["data"] and "heart_sent" in env["data"]

    def test_farewell_node_none(self, monkeypatch):
        import asyncio
        monkeypatch.setattr(sg, "node", None)
        out = asyncio.run(sg.post_farewell_action())
        assert out == {"ok": False, "error": "ros_node_not_ready"}


class _RecPub:
    """Records every published message onto a shared ordered log."""

    def __init__(self, log, label):
        self._log = log
        self._label = label

    def publish(self, msg):
        # String carries .data; Empty has none — record label + payload if any
        self._log.append((self._label, getattr(msg, "data", None)))


def _make_floor_node():
    """GatewayNode shell exercising the REAL publish_demo_phase / publish_offline_mode
    without an rclpy runtime (mirrors test_gateway.py::_make_nav_node)."""
    node = sg.GatewayNode.__new__(sg.GatewayNode)
    log: list[tuple] = []
    node._reset_pub = _RecPub(log, "reset_context")
    node._demo_phase_pub = _RecPub(log, "demo_phase")
    node._offline_mode_pub = _RecPub(log, "offline_mode")
    node._demo_phase_last = None
    node._offline_mode_last = None

    class _Logger:
        def info(self, *a, **k):
            pass

        def warn(self, *a, **k):
            pass

    node.get_logger = lambda: _Logger()
    node._floor_log = log
    return node


class TestRealPublishCallOrder:
    """Exercise the REAL node methods (not the recording stub) for true call order."""

    def test_real_publish_demo_phase_resets_before_phase(self):
        node = _make_floor_node()
        node.publish_demo_phase("s5_safety")
        assert node._floor_log == [
            ("reset_context", None),
            ("demo_phase", "s5_safety"),
        ]
        assert node.demo_phase_snapshot() == "s5_safety"

    def test_real_publish_offline_mode_caches(self):
        node = _make_floor_node()
        node.publish_offline_mode(True)
        assert node._floor_log == [("offline_mode", True)]
        assert node.offline_mode_snapshot() is True

    def test_real_publish_farewell_heart_then_tts(self, monkeypatch):
        """比愛心(WebRtcReq) + 口號(/tts String) 都發出；口號文字 = 管院版。"""
        class _WebRtcReq:
            def __init__(self):
                self.id = 0
                self.topic = ""
                self.api_id = 0
                self.parameter = ""
                self.priority = 0

        monkeypatch.setattr(sg, "WebRtcReq", _WebRtcReq)
        node = _make_floor_node()
        log: list[tuple] = []
        node._webrtc_pub = _RecPub(log, "webrtc")
        node._tts_pub = _RecPub(log, "tts")
        out = node.publish_farewell()
        assert out["ok"] is True and out["heart_sent"] is True
        labels = [c[0] for c in log]
        assert "webrtc" in labels and "tts" in labels
        # 口號原文（管院版）出現在 /tts payload
        tts_payload = next(p for lbl, p in log if lbl == "tts")
        assert "輔大管院" in tts_payload and "第一志願" in tts_payload

    def test_real_publish_farewell_no_webrtc_still_speaks(self, monkeypatch):
        """WebRtcReq 不可用時略過比愛心但口號照播（heart_sent=False）。"""
        monkeypatch.setattr(sg, "WebRtcReq", None)
        node = _make_floor_node()
        log: list[tuple] = []
        node._webrtc_pub = None
        node._tts_pub = _RecPub(log, "tts")
        out = node.publish_farewell()
        assert out["ok"] is True and out["heart_sent"] is False
        assert [lbl for lbl, _ in log] == ["tts"]


class TestDemoPhaseWhitelist:
    def test_canonical_five_phases_present(self):
        for p in ("s1_nav", "s2_greet", "s3_pose_object", "s4_gesture", "s5_safety"):
            assert p in sg.DEMO_PHASE_WHITELIST

    def test_aliases_and_fallbacks_present(self):
        for p in ("all", "quiet", "s2_face", "s3_object"):
            assert p in sg.DEMO_PHASE_WHITELIST

    def test_bogus_phase_absent(self):
        assert "s9_bogus" not in sg.DEMO_PHASE_WHITELIST
