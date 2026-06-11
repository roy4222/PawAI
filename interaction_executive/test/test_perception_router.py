"""Pure parser tests — CI-safe (no rclpy). Payload shapes mirror the real wire
formats documented in docs/contracts/interaction_contract.md plus the dual
formats brain_node historically accepts (face identity vs stable_name +
event_type; object objects[] vs flat). Assertions encode the VERBATIM legacy
semantics (e.g. empty-string — not None — for absent gesture/class_name,
because the callbacks' `if not x` guards rely on it)."""
from interaction_executive.perception_router import (
    PerceptionEvent,
    parse_face,
    parse_gesture,
    parse_object,
    parse_pose,
    parse_speech,
)


def test_parse_speech_or_chain_and_session_fallback():
    ev = parse_speech({"transcript": " 你好 ", "session_id": "s1"})
    assert (ev.kind, ev.transcript, ev.session_id) == ("speech", "你好", "s1")
    ev2 = parse_speech({"text": "hi", "request_id": "r9"})
    assert ev2.transcript == "hi" and ev2.session_id == "r9"
    ev3 = parse_speech({})
    assert ev3.transcript == "" and ev3.session_id.startswith("speech-")


def test_parse_face_both_wire_formats():
    new = parse_face({"stable_name": "Roy", "event_type": "identity_stable",
                      "distance_m": 1.2})
    assert (new.identity, new.stable, new.distance_m) == ("Roy", True, 1.2)
    old = parse_face({"identity": "alice", "identity_stable": True})
    assert (old.identity, old.stable) == ("alice", True)
    third = parse_face({"name": "bob", "stable": True})
    assert (third.identity, third.stable) == ("bob", True)
    unk = parse_face({"event_type": "track_started"})
    assert unk.identity == "unknown" and unk.stable is False
    assert unk.event_type == "track_started"


def test_parse_face_whitespace_identity_stays_empty():
    # Legacy: .strip() does NOT re-default to "unknown" — the callback's
    # `if not identity` branch depends on the empty string surviving.
    ev = parse_face({"identity": "   "})
    assert ev.identity == ""


def test_parse_face_distance_fallbacks_and_string_coercion():
    assert parse_face({"depth_m": 0.8}).distance_m == 0.8
    # try/except float() accepts numeric strings (legacy behavior)
    assert parse_face({"distance_m": "1.5"}).distance_m == 1.5
    assert parse_face({"distance_m": "not-a-number"}).distance_m is None
    assert parse_face({}).distance_m is None


def test_parse_object_array_and_flat_formats():
    arr = parse_object({"objects": [
        {"class_name": "cup", "confidence": 0.62, "color": "red"},
        {"class_name": "chair", "confidence": 0.9},
    ]})
    assert arr.class_name == "cup" and arr.color == "red" and len(arr.objects) == 2
    flat = parse_object({"class_name": "laptop", "confidence": 0.8})
    assert flat.class_name == "laptop" and flat.objects[0]["class_name"] == "laptop"
    legacy = parse_object({"label": "cup", "color": "red"})
    assert legacy.class_name == "cup" and legacy.color == "red"
    empty = parse_object({"objects": []})
    # Legacy: empty array falls through to the flat branch → "" (not None);
    # the callback's `if not class_name: return` guard handles both.
    assert empty.class_name == "" and empty.objects == []


def test_parse_object_label_class_fallbacks_in_array():
    ev = parse_object({"objects": [{"label": "bottle"}]})
    assert ev.class_name == "bottle"
    ev2 = parse_object({"objects": [{"class": "chair"}]})
    assert ev2.class_name == "chair"


def test_parse_gesture_or_chain_and_lowering():
    ev = parse_gesture({"gesture": " Thumbs_Up "})
    assert ev.gesture == "thumbs_up"
    assert parse_gesture({"type": "PALM"}).gesture == "palm"
    assert parse_gesture({"label": "ok"}).gesture == "ok"
    # Legacy: empty string (not None) when absent — `if not gesture` guard.
    assert parse_gesture({}).gesture == ""


def test_parse_pose_or_chain_and_lowering():
    assert parse_pose({"pose": "sitting", "confidence": 0.7}).pose == "sitting"
    assert parse_pose({"posture": " Fallen "}).pose == "fallen"
    assert parse_pose({}).pose == ""


def test_or_chain_order_first_key_wins():
    # Both-keys-present fixtures freeze the or-chain ORDER, not just coverage —
    # single-key fixtures cannot detect a reordered chain.
    assert parse_speech({"transcript": "a", "text": "b"}).transcript == "a"
    assert parse_speech({"session_id": "s", "request_id": "r"}).session_id == "s"
    assert parse_face({"identity": "i", "stable_name": "s", "name": "n"}).identity == "i"
    assert parse_face({"stable_name": "s", "name": "n"}).identity == "s"
    assert parse_face({"distance_m": 1.0, "depth_m": 2.0}).distance_m == 1.0
    assert parse_gesture({"gesture": "a", "type": "b", "label": "c"}).gesture == "a"
    assert parse_gesture({"type": "b", "label": "c"}).gesture == "b"
    assert parse_pose({"pose": "a", "posture": "b"}).pose == "a"
    ev = parse_object({"objects": [{"class_name": "a", "label": "b", "class": "c"}]})
    assert ev.class_name == "a"
    assert parse_object({"objects": [{"label": "b", "class": "c"}]}).class_name == "b"
    assert parse_object({"class_name": "a", "label": "b"}).class_name == "a"


def test_raw_payload_always_kept():
    payload = {"gesture": "wave", "extra": 1}
    assert parse_gesture(payload).raw is payload


def test_event_basics():
    ev = parse_speech({"transcript": "x"})
    assert isinstance(ev, PerceptionEvent)
    assert ev.kind == "speech" and len(ev.event_id) == 12 and ev.ts > 0
