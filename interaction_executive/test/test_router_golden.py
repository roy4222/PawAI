"""Golden fixtures (Plan D3): same payloads through router-ON vs router-OFF
must produce IDENTICAL /brain/proposal sequences (normalized on plan_id /
created_at / session_id uuids). This suite is the Phase 0 behavior-frozen
authority. rclpy required → local tier (NOT in the CI fast gate); run before
every Plan-D-touching PR.

The driver deliberately reaches PAST the accumulate/attention gates (timer
backdating, forced ENGAGED, face→fallen name-injection chain) so that pose /
object / face parsing differences actually surface in emitted proposals —
single-shot fixtures would be silently swallowed by the 1-2s accumulate
timers and the golden comparison would be blind to those parsers (verified:
a de-lowered parse_pose canary passes a naive single-shot suite).

Canary-verified sensitivity (mutating the parser makes this suite fail):
pose lowering, face stable_name chain, object array label fallback, object
color, gesture lowering (the WAVE fixture lives on the speech-free node —
conversation-gated gestures are swallowed within 30s of chat input).
Known structural blind spot: speech transcript .strip() — padding
never alters any emitted /brain/proposal (hard rules substring-match and the
stop/safety plans don't echo the transcript), so no proposal-level referee
can see it; the parser unit tests cover it instead."""
import json

import pytest

rclpy = pytest.importorskip("rclpy")
from std_msgs.msg import String  # noqa: E402

from interaction_executive.attention_machine import AttentionState  # noqa: E402
from interaction_executive.brain_node import BrainNode  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def rclpy_ctx():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


def _cb(node: BrainNode, name: str, payload: dict) -> None:
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    getattr(node, name)(msg)


def _capture(node: BrainNode) -> list[str]:
    published: list[str] = []
    node._pub_proposal.publish = (  # type: ignore[method-assign]
        lambda m: published.append(m.data)
    )
    return published


def _scenario_speech_gesture(router_on: bool) -> list[str]:
    """Speech hard rules + gestures (immediate-emit paths)."""
    node = BrainNode()
    try:
        node.perception_router_enabled = router_on
        published = _capture(node)
        _cb(node, "_on_speech_intent", {"transcript": "你好", "session_id": "g1"})
        _cb(node, "_on_speech_intent", {"text": " 停 ", "request_id": "g2"})
        _cb(node, "_on_speech_intent", {"transcript": "請你翻跟斗", "session_id": "g3"})
        _cb(node, "_on_gesture", {"gesture": "palm", "confidence": 0.9, "hand": "right"})
        _cb(node, "_on_gesture", {"gesture": "thumbs_up", "confidence": 0.95})
        return published
    finally:
        node.destroy_node()


def _scenario_face_pose(router_on: bool) -> list[str]:
    """Face formats + pose accumulate paths on an interference-free node
    (gesture/speech plans on the same node would trip PendingConfirm /
    active-plan gates and silently swallow the pose emissions)."""
    node = BrainNode()
    try:
        node.perception_router_enabled = router_on
        published = _capture(node)

        # face: the LAST stable identity before the fallen events must arrive
        # via the stable_name/event_type wire format — _last_stable_identity_name
        # feeds the fallen_alert name injection below, so a parse regression on
        # that format surfaces in the proposal text. (Ordering matters: an
        # identity-keyed event after Roy would overwrite the cache through a
        # code path the canary mutations don't touch, masking the difference.)
        # gesture wave first (mixed-case → lowering is golden-visible here:
        # this node has no speech, so the 30s conversation gate that silently
        # swallowed wave on the speech node does not apply).
        _cb(node, "_on_gesture", {"type": "WAVE"})

        _cb(node, "_on_face", {"identity": "alice", "identity_stable": True})
        _cb(node, "_on_face", {"event_type": "track_lost"})
        _cb(node, "_on_face", {"identity": "   "})
        _cb(node, "_on_face", {"stable_name": "Roy", "event_type": "identity_stable",
                               "distance_m": "1.5"})

        # pose sitting → sit_along (1.0s accumulate; backdate the timer)
        _cb(node, "_on_pose", {"pose": "sitting"})
        if node._state.sitting_first_seen is not None:
            node._state.sitting_first_seen -= 1.1
        _cb(node, "_on_pose", {"posture": " Sitting "})

        # pose bending → careful_remind (1.0s accumulate)
        _cb(node, "_on_pose", {"posture": " Bending "})
        if node._state.bending_first_seen is not None:
            node._state.bending_first_seen -= 1.1
        _cb(node, "_on_pose", {"pose": "bending"})

        # pose fallen → fallen_alert (2.0s accumulate); name comes from the
        # cached stable face identity → face parsing flows into this proposal.
        _cb(node, "_on_pose", {"pose": "fallen"})
        if node._state.fallen_first_seen is not None:
            node._state.fallen_first_seen -= 2.1
        _cb(node, "_on_pose", {"posture": "FALLEN"})

        return published
    finally:
        node.destroy_node()


_OBJECT_PAYLOADS: list[dict] = [
    {"objects": [{"class_name": "cup", "confidence": 0.6, "color": "red"}]},
    {"objects": [{"class_name": "chair", "confidence": 0.9},
                 {"class_name": "cup", "confidence": 0.5}]},
    {"class_name": "laptop", "confidence": 0.7},          # flat legacy
    {"label": "bottle", "color": "blue"},                 # flat + label key
    {"objects": [{"label": "keyboard"}]},                 # array + label key
    {"objects": [{"class": "vase"}]},                     # array + class key
    {"objects": []},
]


def _scenario_object(router_on: bool) -> list[str]:
    """Object remark path. ONE FRESH NODE PER PAYLOAD: object_remark goes
    through a skill-level cooldown (_emit_with_cooldown), so on a shared node
    only the first event ever emits and every later payload's parsing would be
    invisible to the golden comparison. Attention forced to ENGAGED so the
    remark gate passes; all classes chosen from OBJECT_CLASS_ZH (classes
    outside the table return None from build_object_tts and stay silent)."""
    published: list[str] = []
    for payload in _OBJECT_PAYLOADS:
        node = BrainNode()
        try:
            node.perception_router_enabled = router_on
            node_pub = _capture(node)
            node._attention._state = AttentionState.ENGAGED
            _cb(node, "_on_object", payload)
            published.extend(node_pub)
        finally:
            node.destroy_node()
    return published


def _normalize(published: list[str]) -> list[dict]:
    out = []
    for raw in published:
        d = json.loads(raw)
        for vol in ("plan_id", "created_at", "session_id"):
            d.pop(vol, None)
        for step in d.get("steps", []):
            step.pop("step_id", None)
        out.append(d)
    return out


def _run_path(router_on: bool) -> list[dict]:
    return _normalize(
        _scenario_speech_gesture(router_on)
        + _scenario_face_pose(router_on)
        + _scenario_object(router_on)
    )


def test_router_on_off_identical_proposals():
    on = _run_path(True)
    off = _run_path(False)
    assert on == off, (
        f"router-ON produced {len(on)} proposals, OFF {len(off)};\n"
        f"ON: {json.dumps(on, ensure_ascii=False, indent=1)}\n"
        f"OFF: {json.dumps(off, ensure_ascii=False, indent=1)}"
    )
    # Teeth check: every perception kind must contribute at least one proposal,
    # otherwise the equivalence comparison is blind for that parser.
    sources = " ".join(json.dumps(d, ensure_ascii=False) for d in on)
    assert len(on) >= 5, f"only {len(on)} proposals — fixtures too weak\n{sources}"
    for marker in ("pose_fallen", "pose_sitting", "pose_bending"):
        assert marker in sources, f"pose path '{marker}' never emitted:\n{sources}"
    # Each emit-capable object payload must surface its class in some proposal —
    # otherwise that payload's parsing is invisible to the equivalence check.
    for zh_marker in ("杯子", "椅子", "筆電", "瓶子", "鍵盤", "花瓶"):
        assert zh_marker in sources, f"object '{zh_marker}' never emitted:\n{sources}"
