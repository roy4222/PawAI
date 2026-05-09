"""Integration tests for Attention Policy (Branch D) — mock timeline scenarios.

Tests cover 4 scenarios from the spec/plan:
  1. Roy 路過比 OK — NOTICED allows gesture, IDLE/NOTICED silences object_remark
  2. Roy stops to interact — dwell ≥ 1.5s + dist ≤ 1.6m → ENGAGED → greet emits
  3. Color jitter dedup — same class/different color → 60s dedup holds (class_name key)
  4. Active skill guard — wave_hello SKILL active → object_remark blocked

All tests use fake-clock AttentionMachine ticks — no ROS2 timer dependency.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P2-1
Plan: docs/pawai-brain/plans/2026-05-12-attention-policy.md Task D-5
"""
from __future__ import annotations

import json
import time

import pytest
import rclpy
from std_msgs.msg import String

from interaction_executive.attention_machine import AttentionState
from interaction_executive.brain_node import BrainNode
from interaction_executive.skill_contract import PriorityClass, SkillResultStatus
from interaction_executive.pending_confirm import ConfirmState


@pytest.fixture(scope="module", autouse=True)
def rclpy_context():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


@pytest.fixture
def brain():
    node = BrainNode()
    node.unknown_face_accumulate_s = 0.05
    node.fallen_accumulate_s = 0.05
    node.chat_wait_ms = 50
    captured = []
    captured_traces = []

    def capture(plan):
        captured.append(node._plan_to_dict(plan))

    node._emit = capture
    node._captured_proposals = captured

    class _TraceCap:
        def publish(self_inner, msg):
            captured_traces.append(json.loads(msg.data))

    node.conversation_trace_pub = _TraceCap()
    node._captured_traces = captured_traces

    try:
        yield node
    finally:
        for timer in list(node._chat_timeouts.values()):
            node.destroy_timer(timer)
        node.destroy_node()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(payload):
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


def _latest(brain):
    assert brain._captured_proposals
    return brain._captured_proposals[-1]


def _drain(brain):
    result = list(brain._captured_proposals)
    brain._captured_proposals.clear()
    return result


def _tick_am(brain, now: float, face: bool = True, dist: float | None = None,
             plan: bool = False, speech: bool = False) -> AttentionState:
    """Drive AttentionMachine directly with fake clock."""
    return brain._attention.tick(
        now=now, face_visible=face, distance_m=dist,
        active_plan=plan, speech_intent=speech,
    )


def _simulate_active_skill(brain, skill: str, priority: int = int(PriorityClass.SKILL)):
    """Inject a STARTED skill result so brain._state.active_plan is set."""
    brain._on_skill_result(_msg({
        "plan_id": f"p-{skill}",
        "selected_skill": skill,
        "status": SkillResultStatus.STARTED.value,
        "priority_class": priority,
        "step_total": 3,
    }))


def _simulate_skill_done(brain, skill: str):
    """Inject a COMPLETED skill result to clear active_plan."""
    brain._on_skill_result(_msg({
        "plan_id": f"p-{skill}",
        "selected_skill": skill,
        "status": SkillResultStatus.COMPLETED.value,
        "priority_class": int(PriorityClass.SKILL),
    }))


# ---------------------------------------------------------------------------
# Scenario 1: Roy 路過比 OK
# Timeline:
#   t=0   face stable → NOTICED (no greet — not ENGAGED)
#   t=0.5 thumbs_up → PendingConfirm (NOTICED allows gesture confirm)
#   t=1.0 OK gesture → wiggle INTERACTING
#   t=1.5 chair detected → state=INTERACTING ≠ ENGAGED → silenced
# ---------------------------------------------------------------------------

def test_scenario_passerby_no_greet_but_gesture_works(brain):
    """路過比 OK：NOTICED does not trigger greet, but does allow gesture confirm path."""
    # t=0: face appears, becomes NOTICED
    _tick_am(brain, now=0.0, face=True, dist=2.0)
    _tick_am(brain, now=0.6, face=True, dist=2.0)
    assert brain._attention.state == AttentionState.NOTICED

    # Known face stable event — should NOT greet (not ENGAGED)
    brain._on_face(_msg({"identity": "alice", "identity_stable": True}))
    proposals = _drain(brain)
    greet_plans = [p for p in proposals if p["selected_skill"] == "greet_known_person"]
    assert not greet_plans, "Should not greet when only NOTICED (person passing by)"

    # Thumbs_up gesture → should enter PendingConfirm (NOTICED allows gesture flow)
    brain._on_gesture(_msg({"gesture": "thumbs_up"}))
    proposals_after_gesture = _drain(brain)
    # PendingConfirm machinery should have been invoked (say_canned hint or pending state)
    assert brain._pending_confirm.state == ConfirmState.PENDING, \
        "thumbs_up in NOTICED should still start PendingConfirm (D-3: gesture allowed at NOTICED+)"

    # Chair detected while NOTICED → object_remark should be silenced
    brain._on_object(_msg({
        "event_type": "object_detected",
        "objects": [{"class_name": "chair", "color": "brown"}],
    }))
    proposals_obj = _drain(brain)
    obj_plans = [p for p in proposals_obj if p["selected_skill"] == "object_remark"]
    assert not obj_plans, "object_remark should be silenced when not ENGAGED"


# ---------------------------------------------------------------------------
# Scenario 2: Roy stops to interact — dwell triggers ENGAGED → greet emits
# ---------------------------------------------------------------------------

def test_scenario_person_stops_near_dog_gets_greet(brain):
    """Person dwells close → ENGAGED → greet_known_person emits."""
    # Reset attention
    brain._attention.reset(now=0.0)

    # Face appears (far away → NOTICED)
    _tick_am(brain, now=0.0, face=True, dist=2.5)
    _tick_am(brain, now=0.6, face=True, dist=2.5)
    assert brain._attention.state == AttentionState.NOTICED

    # Person moves close — dwell starts
    _tick_am(brain, now=0.7, face=True, dist=1.2)

    # Not long enough for ENGAGED
    _tick_am(brain, now=1.5, face=True, dist=1.2)
    assert brain._attention.state == AttentionState.NOTICED, \
        "Should still be NOTICED (dwell 0.8s < 1.5s threshold)"

    # Now dwell >= 1.5s → ENGAGED
    _tick_am(brain, now=2.3, face=True, dist=1.2)
    assert brain._attention.state == AttentionState.ENGAGED

    # Send stable face event — now ENGAGED so greet should fire
    brain._on_face(_msg({"identity": "alice", "identity_stable": True}))
    proposals = _drain(brain)
    greet_plans = [p for p in proposals if p["selected_skill"] == "greet_known_person"]
    assert greet_plans, "Should greet when ENGAGED (person stopped near dog)"
    # greet_known_person uses text_template "歡迎回來，{name}" — plan carries the name arg
    assert greet_plans[0]["source"] == "rule:known_face"


# ---------------------------------------------------------------------------
# Scenario 3: Color jitter dedup — class_name key prevents bypass
# ---------------------------------------------------------------------------

def test_scenario_color_jitter_dedup(brain):
    """Same object with drifting color → class_name-only dedup blocks repeat emit."""
    brain._attention.reset(now=0.0)
    _tick_am(brain, now=0.0, face=True, dist=1.0)
    _tick_am(brain, now=0.6, face=True, dist=1.0)
    _tick_am(brain, now=2.5, face=True, dist=1.0)
    assert brain._attention.state == AttentionState.ENGAGED

    # First detection: brown chair
    brain._on_object(_msg({
        "event_type": "object_detected",
        "objects": [{"class_name": "chair", "color": "brown"}],
    }))
    proposals = _drain(brain)
    first_emits = [p for p in proposals if p["selected_skill"] == "object_remark"]
    assert first_emits, "First brown_chair should emit"

    # 1s later: same chair, color drifted to "coffee" (YOLO jitter)
    brain._on_object(_msg({
        "event_type": "object_detected",
        "objects": [{"class_name": "chair", "color": "coffee"}],
    }))
    proposals2 = _drain(brain)
    second_emits = [p for p in proposals2 if p["selected_skill"] == "object_remark"]
    assert not second_emits, \
        "coffee_chair within 60s dedup window should be blocked (class_name key)"

    # Verify dedup dict uses class-only key: ("chair",) present, ("cup",) absent
    # (cup was never emitted, so not in dedup).  The class-name-only key design
    # is what prevents color-jitter bypass — different color same class hits same key.
    assert ("chair",) in brain._object_remark_seen, \
        "chair should be in _object_remark_seen with class-only tuple key"
    assert ("cup",) not in brain._object_remark_seen, \
        "cup should NOT be in _object_remark_seen (different class, never emitted)"


# ---------------------------------------------------------------------------
# Scenario 4: Active wave_hello + chair detected → object_remark blocked
# ---------------------------------------------------------------------------

def test_scenario_active_skill_blocks_object_remark(brain):
    """wave_hello (SKILL priority) running → object_remark must not interrupt."""
    brain._attention.reset(now=0.0)
    _tick_am(brain, now=0.0, face=True, dist=1.0)
    _tick_am(brain, now=0.6, face=True, dist=1.0)
    _tick_am(brain, now=2.5, face=True, dist=1.0)
    assert brain._attention.state == AttentionState.ENGAGED

    # Simulate wave_hello skill is actively running (SKILL priority)
    _simulate_active_skill(brain, "wave_hello", priority=int(PriorityClass.SKILL))
    assert brain._state.active_plan is not None

    # Chair detected — should be blocked by _has_active_skill_or_sequence()
    brain._on_object(_msg({
        "event_type": "object_detected",
        "objects": [{"class_name": "chair", "color": "gray"}],
    }))
    proposals = _drain(brain)
    obj_plans = [p for p in proposals if p["selected_skill"] == "object_remark"]
    assert not obj_plans, \
        "object_remark must not emit while wave_hello (SKILL) is active"

    # Skill completes
    _simulate_skill_done(brain, "wave_hello")
    assert brain._state.active_plan is None


# ---------------------------------------------------------------------------
# Scenario 5: stranger_alert fires with NOTICED+ (Option B validation)
# ---------------------------------------------------------------------------

def test_scenario_stranger_alert_requires_noticed_plus(brain):
    """stranger_alert: IDLE state blocks it; NOTICED+ allows it (Option B)."""
    brain._attention.reset(now=0.0)

    # In IDLE: unknown face 3s accumulation — should NOT fire (IDLE blocks)
    brain._on_face(_msg({"identity": "unknown", "event_type": "track_started"}))
    brain._state.unknown_face_first_seen -= 0.06  # simulate 3s elapsed
    brain._on_face(_msg({"identity": "unknown"}))
    proposals = _drain(brain)
    stranger_plans = [p for p in proposals if p["selected_skill"] == "stranger_alert"]
    assert not stranger_plans, \
        "stranger_alert should NOT fire in IDLE state (Option B: NOTICED+ required)"

    # Now enter NOTICED
    brain._attention.reset(now=100.0)  # use far-future to avoid timestamp pollution
    _tick_am(brain, now=100.0, face=True, dist=2.0)
    _tick_am(brain, now=100.6, face=True, dist=2.0)
    assert brain._attention.state == AttentionState.NOTICED

    # Reset the accumulation timer + cooldown
    brain._state.unknown_face_first_seen = None
    brain._state.last_alert_ts.pop("stranger_alert", None)

    # NOTICED: unknown face 3s accumulation — should fire
    brain._on_face(_msg({"identity": "unknown", "event_type": "track_started"}))
    brain._state.unknown_face_first_seen -= 0.06  # simulate 3s elapsed
    brain._on_face(_msg({"identity": "unknown"}))
    proposals2 = _drain(brain)
    stranger_plans2 = [p for p in proposals2 if p["selected_skill"] == "stranger_alert"]
    assert stranger_plans2, \
        "stranger_alert SHOULD fire in NOTICED+ state (Option B: threshold met)"
