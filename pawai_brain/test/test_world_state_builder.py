from datetime import datetime
from unittest.mock import patch

from pawai_brain.capability.world_snapshot import WorldStateSnapshot
from pawai_brain.nodes import world_state_builder as ws_node


def _wire_world(snap: WorldStateSnapshot):
    ws_node.set_world_provider(lambda: snap)


def test_writes_period_and_time():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    ws = out["world_state"]
    assert "period" in ws and "time" in ws
    assert ws["source"] == "speech"


def test_writes_runtime_flags():
    snap = WorldStateSnapshot()
    snap.apply_tts_playing(True)
    _wire_world(snap)
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["tts_playing"] is True


def test_emits_trace_entry():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert any(t["stage"] == "world_state" for t in out["trace"])


# ── 1H: current_speaker injection ────────────────────────────────────────

def test_current_speaker_known_within_3s():
    """Known identity within 3s → current_speaker = identity."""
    snap = WorldStateSnapshot()
    _wire_world(snap)
    ws_node.set_speaker_provider(lambda: ("Roy", __import__('time').time()))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["current_speaker"] == "Roy"


def test_current_speaker_unknown_when_stale():
    """Identity older than 3s → current_speaker = 'unknown'."""
    snap = WorldStateSnapshot()
    _wire_world(snap)
    ws_node.set_speaker_provider(lambda: ("Roy", __import__('time').time() - 5.0))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["current_speaker"] == "unknown"


def test_current_speaker_default_unknown():
    """Default provider → current_speaker = 'unknown'."""
    snap = WorldStateSnapshot()
    _wire_world(snap)
    ws_node.set_speaker_provider(lambda: ("unknown", 0.0))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["current_speaker"] == "unknown"


# ── N5-B: pose / gesture providers ────────────────────────────────────────
import time as _time


def test_pose_provider_writes_current_pose():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    ws_node.set_pose_provider(lambda: ("sitting", _time.time()))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    pose = out["world_state"]["current_pose"]
    assert pose is not None
    assert pose["name"] == "sitting"


def test_gesture_provider_writes_current_gesture():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    ws_node.set_gesture_provider(lambda: ("ok", _time.time()))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    gst = out["world_state"]["current_gesture"]
    assert gst is not None
    assert gst["name"] == "ok"


def test_stale_pose_filtered_out():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    # 100s old → way past _POSE_STALE_S=10s
    ws_node.set_pose_provider(lambda: ("sitting", _time.time() - 100.0))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["current_pose"] is None


def test_stale_gesture_filtered_out():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    # 10s old → past _GESTURE_STALE_S=5s
    ws_node.set_gesture_provider(lambda: ("ok", _time.time() - 10.0))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["current_gesture"] is None


def test_trace_detail_includes_pose_gesture_tags():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    ws_node.set_pose_provider(lambda: ("sitting", _time.time()))
    ws_node.set_gesture_provider(lambda: ("ok", _time.time()))
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    ws_trace = [t for t in out["trace"] if t["stage"] == "world_state"][0]
    assert "pose=sitting" in ws_trace["detail"]
    assert "gst=ok" in ws_trace["detail"]
