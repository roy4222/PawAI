"""Trace emission tests (Plan E4) — rclpy local tier (NOT in the CI fast gate).
Pattern: capture /brain/trace publishes, fire one suppression scenario, assert
gate/reason/decision-chain fields. Behavior itself is asserted unchanged by the
untouched pre-Plan-E test suite."""
import json

import pytest

rclpy = pytest.importorskip("rclpy")
from std_msgs.msg import String  # noqa: E402

from interaction_executive.brain_node import BrainNode  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def rclpy_ctx():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


@pytest.fixture
def node():
    n = BrainNode()
    n.traces = []
    n._pub_trace.publish = (  # type: ignore[method-assign]
        lambda m: n.traces.append(json.loads(m.data))
    )
    yield n
    n.destroy_node()


def _msg(payload: dict) -> String:
    m = String()
    m.data = json.dumps(payload, ensure_ascii=False)
    return m


def test_gesture_disabled_emits_suppressed(node):
    node.gesture_enabled = False
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    hits = [t for t in node.traces if t["gate"] == "gesture_enabled"]
    assert hits and hits[0]["verdict"] == "suppressed"
    assert hits[0]["detail"]["demo_phase"] == node.demo_phase
    assert hits[0]["decision_id"].startswith("gesture-")


def test_phase_gate_emits_suppressed_with_phase(node):
    node.demo_phase = "s3_object"
    node.gesture_enabled = True
    node._on_gesture(_msg({"gesture": "wave", "confidence": 0.9}))
    hits = [t for t in node.traces if t["gate"] == "demo_phase"]
    assert hits and "s3_object" in hits[0]["reason"]
    assert "gesture" in hits[0]["reason"]


def test_plan_emitted_and_skill_result_share_decision_id(node):
    node._on_speech_intent(_msg({"transcript": "停", "session_id": "t1"}))
    emitted = [t for t in node.traces if t["kind"] == "plan_emitted"]
    assert emitted, "stop keyword should emit a plan"
    plan_id, decision_id = emitted[0]["plan_id"], emitted[0]["decision_id"]
    assert decision_id.startswith("speech-")
    node._on_skill_result(_msg({"plan_id": plan_id, "status": "completed"}))
    results = [t for t in node.traces if t["kind"] == "skill_result"]
    assert results and results[0]["decision_id"] == decision_id
    assert results[0]["verdict"] == "accepted"


def test_blocked_by_safety_result_verdict(node):
    node._on_speech_intent(_msg({"transcript": "停", "session_id": "t2"}))
    emitted = [t for t in node.traces if t["kind"] == "plan_emitted"]
    plan_id = emitted[0]["plan_id"]
    node._on_skill_result(_msg({"plan_id": plan_id, "status": "blocked_by_safety",
                                "reason": "banned_api:1301"}))
    blocked = [t for t in node.traces
               if t["kind"] == "skill_result" and t["verdict"] == "blocked"]
    assert blocked and blocked[0]["gate"] == "safety"
    assert blocked[0]["reason"] == "banned_api:1301"


def test_object_dedup_emits_suppressed_with_remaining(node):
    from interaction_executive.attention_machine import AttentionState
    node._attention._state = AttentionState.ENGAGED
    payload = {"objects": [{"class_name": "cup", "confidence": 0.6, "color": "red"}]}
    node._on_object(_msg(payload))          # first: emits remark, sets dedup
    node._on_object(_msg(payload))          # second: 60s remark dedup hit
    hits = [t for t in node.traces if t["gate"] == "object_remark_dedup"]
    assert hits, [t["gate"] for t in node.traces]
    assert hits[0]["detail"]["cooldown_remaining_s"] > 0
    assert "cup" in hits[0]["detail"]["source_summary"]


def test_trace_never_breaks_callback(node):
    node._pub_trace.publish = lambda m: (_ for _ in ()).throw(RuntimeError("boom"))
    node.gesture_enabled = False
    # Must not raise even though every trace publish explodes.
    node._on_gesture(_msg({"gesture": "thumbs_up"}))
