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


# ── N3-A: recent_objects cache ────────────────────────────────────────────


def test_apply_object_detected_single_cup_red():
    s = WorldStateSnapshot()
    payload = {
        "stamp": 12345.0,
        "event_type": "object_detected",
        "objects": [{"class_name": "cup", "color": "red", "color_confidence": 0.8,
                     "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
    }
    s.apply_object_detected_json(json.dumps(payload))
    objs = s.get_recent_objects()
    assert len(objs) == 1
    assert objs[0]["class"] == "cup"
    assert objs[0]["color"] == "red"
    assert "age_s" in objs[0]


def test_apply_object_detected_dedups_by_class():
    """5 chair detections in a row should leave only ONE chair entry (latest)."""
    s = WorldStateSnapshot()
    for _ in range(5):
        s.apply_object_detected_json(json.dumps({
            "stamp": 0.0, "event_type": "object_detected",
            "objects": [{"class_name": "chair", "color": "black", "color_confidence": 0.8,
                          "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
        }))
    objs = s.get_recent_objects()
    assert len(objs) == 1
    assert objs[0]["class"] == "chair"


def test_apply_object_detected_multiple_classes_kept():
    """cup + chair in same payload → both stored."""
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [
            {"class_name": "cup", "color": "red", "color_confidence": 0.8,
             "confidence": 0.9, "bbox": [0, 0, 1, 1]},
            {"class_name": "chair", "color": "black", "color_confidence": 0.8,
             "confidence": 0.9, "bbox": [0, 0, 1, 1]},
        ],
    }))
    objs = s.get_recent_objects()
    classes = {o["class"] for o in objs}
    assert classes == {"cup", "chair"}


def test_apply_object_detected_drops_unknown_color():
    """color='Unknown' from HSV failure → stored as None (don't pollute prompt)."""
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [{"class_name": "cup", "color": "Unknown", "confidence": 0.5, "bbox": []}],
    }))
    objs = s.get_recent_objects()
    assert len(objs) == 1
    assert objs[0]["color"] is None


def test_apply_object_detected_malformed_json_safe():
    s = WorldStateSnapshot()
    s.apply_object_detected_json("not json")
    assert s.get_recent_objects() == []


def test_get_recent_objects_window_filters_out_stale():
    """Manually inject an old timestamp; window should drop it."""
    import time as _t
    s = WorldStateSnapshot()
    s._recent_objects.append({"class": "cup", "color": "red", "ts": _t.time() - 100.0})
    s._recent_objects.append({"class": "chair", "color": None, "ts": _t.time() - 1.0})
    fresh = s.get_recent_objects(window_s=30.0)
    classes = [o["class"] for o in fresh]
    assert "chair" in classes
    assert "cup" not in classes


def test_to_dict_includes_recent_objects():
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [{"class_name": "cup", "color": "red", "color_confidence": 0.8,
                      "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
    }))
    d = s.to_dict()
    assert "recent_objects" in d
    assert d["recent_objects"][0]["class"] == "cup"


# ── N5-A: object filters (person exclude + color confidence gate) ─────────


def test_person_class_filtered_from_recent_objects():
    """N5-A: face_identity owns people — object person path must not duplicate."""
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [
            {"class_name": "person", "color": "black", "color_confidence": 0.9,
             "confidence": 0.9, "bbox": [0, 0, 1, 1]},
            {"class_name": "cup", "color": "red", "color_confidence": 0.8,
             "confidence": 0.9, "bbox": [0, 0, 1, 1]},
        ],
    }))
    objs = s.get_recent_objects()
    classes = [o["class"] for o in objs]
    assert "person" not in classes
    assert "cup" in classes


def test_low_color_confidence_drops_color():
    """N5-A: color_confidence < 0.6 → color None, mention class only."""
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [{"class_name": "tv", "color": "blue", "color_confidence": 0.3,
                      "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
    }))
    objs = s.get_recent_objects()
    assert len(objs) == 1
    assert objs[0]["class"] == "tv"
    assert objs[0]["color"] is None


def test_high_color_confidence_keeps_color():
    """N5-A: color_confidence ≥ 0.6 → color preserved."""
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [{"class_name": "tv", "color": "blue", "color_confidence": 0.85,
                      "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
    }))
    objs = s.get_recent_objects()
    assert objs[0]["color"] == "blue"


def test_missing_color_confidence_treated_as_zero():
    """Defensive: missing color_confidence defaults to 0 → drop color."""
    s = WorldStateSnapshot()
    s.apply_object_detected_json(json.dumps({
        "stamp": 0.0, "event_type": "object_detected",
        "objects": [{"class_name": "tv", "color": "blue",
                      "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
    }))
    objs = s.get_recent_objects()
    assert objs[0]["color"] is None
