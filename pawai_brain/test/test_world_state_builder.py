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
