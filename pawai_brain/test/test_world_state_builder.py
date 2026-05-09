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
