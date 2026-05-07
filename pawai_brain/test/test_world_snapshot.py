import json

from pawai_brain.capability.world_snapshot import WorldStateSnapshot


def test_defaults_are_safe():
    s = WorldStateSnapshot()
    assert s.tts_playing is False
    assert s.obstacle is False
    assert s.nav_safe is True
    assert s.active_skill is None


def test_apply_tts_playing_bool():
    s = WorldStateSnapshot()
    s.apply_tts_playing(True)
    assert s.tts_playing is True


def test_apply_reactive_stop_status_obstacle_true():
    s = WorldStateSnapshot()
    s.apply_reactive_stop_status_json(json.dumps({"obstacle": True}))
    assert s.obstacle is True


def test_apply_reactive_stop_status_malformed_keeps_default():
    s = WorldStateSnapshot()
    s.apply_reactive_stop_status_json("not json")
    assert s.obstacle is False


def test_apply_nav_safety_false():
    s = WorldStateSnapshot()
    s.apply_nav_safety_json(json.dumps({"nav_safe": False}))
    assert s.nav_safe is False


def test_apply_pawai_brain_state_active_plan():
    s = WorldStateSnapshot()
    payload = {"active_plan": {"selected_skill": "self_introduce", "step_index": 3}}
    s.apply_pawai_brain_state_json(json.dumps(payload))
    assert s.active_skill == "self_introduce"
    assert s.active_skill_step == 3


def test_to_world_flags_rounds_trip():
    s = WorldStateSnapshot()
    s.apply_tts_playing(True)
    s.apply_reactive_stop_status_json(json.dumps({"obstacle": True}))
    flags = s.to_world_flags()
    assert flags.tts_playing is True
    assert flags.obstacle is True
    assert flags.nav_safe is True
