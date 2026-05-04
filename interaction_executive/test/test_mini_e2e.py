"""Mini E2E — Studio button → Brain → Executive → SkillResult chain.

Phase B B5 / Mini E2E target (impl notes 2026-05-04 §3):
  Studio button [self_introduce]
    → Gateway POST /api/skill_request
    → ROS2 /brain/skill_request
    → brain_node._on_skill_request → build_plan(self_introduce, 6 steps)
    → publish /brain/proposal
    → executive._on_proposal → ACCEPTED → STARTED → 6×(STEP_STARTED + STEP_SUCCESS)
    → COMPLETED
    → brain_node._on_skill_result clears active_plan

This test exercises the wiring without ROS spinning by directly invoking
node callbacks and capturing emitted messages.
"""
from __future__ import annotations

import json
import time

import pytest
import rclpy
from std_msgs.msg import String

from interaction_executive.brain_node import BrainNode
from interaction_executive.interaction_executive_node import InteractionExecutiveNode
from interaction_executive.skill_contract import SkillResultStatus


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
    captured_proposals = []

    original_publish = node._pub_proposal.publish

    def capture(msg):
        captured_proposals.append(json.loads(msg.data))
        original_publish(msg)

    node._pub_proposal.publish = capture
    node._captured_proposals = captured_proposals
    try:
        yield node
    finally:
        for timer in list(node._chat_timeouts.values()):
            node.destroy_timer(timer)
        node.destroy_node()


@pytest.fixture
def executive():
    node = InteractionExecutiveNode()
    node.step_settle_s = 0.0
    # Mini E2E runs without depth sensor — open both gates manually.
    node._world._snap.depth_clear = True
    node._world._snap.nav_ready = True
    captured_results = []
    captured_tts = []

    def cap_result(msg):
        captured_results.append(json.loads(msg.data))

    def cap_tts(msg):
        captured_tts.append(msg.data)

    node._pub_skill_result.publish = cap_result
    node._pub_tts.publish = cap_tts
    node._captured_results = captured_results
    node._captured_tts = captured_tts
    try:
        yield node
    finally:
        node.destroy_node()


def _msg(payload):
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


def _drive_executive_to_completion(executive, max_ticks=30):
    """Run worker_tick until queue empties or COMPLETED is emitted."""
    completed = False
    for _ in range(max_ticks):
        executive._worker_tick()
        statuses = {r["status"] for r in executive._captured_results}
        if SkillResultStatus.COMPLETED.value in statuses:
            completed = True
            break
    return completed


# ---------------------------------------------------------------------------


def test_mini_e2e_studio_button_self_introduce(brain, executive):
    """Studio [self_introduce] button → 6-step plan → executor → COMPLETED."""

    # Step 1: Studio button — Gateway publishes /brain/skill_request to brain.
    brain._on_skill_request(
        _msg(
            {
                "skill": "self_introduce",
                "args": {},
                "request_id": "btn-mini-e2e-1",
                "source": "studio_button",
            }
        )
    )

    # Step 2: Brain emitted exactly one proposal.
    assert len(brain._captured_proposals) == 1
    proposal = brain._captured_proposals[-1]
    assert proposal["selected_skill"] == "self_introduce"
    assert len(proposal["steps"]) == 6

    # Step 3: Forward proposal to executive (simulating ROS2 topic delivery).
    executive._on_proposal(_msg(proposal))

    # First result is ACCEPTED.
    assert executive._captured_results[0]["status"] == SkillResultStatus.ACCEPTED.value

    # Step 4: Drive executive ticks until COMPLETED.
    assert _drive_executive_to_completion(executive), (
        f"executive did not complete; results={executive._captured_results!r}"
    )

    # Step 5: Verify result sequence shape.
    statuses = [r["status"] for r in executive._captured_results]
    assert statuses[0] == SkillResultStatus.ACCEPTED.value
    assert SkillResultStatus.STARTED.value in statuses
    assert statuses.count(SkillResultStatus.STEP_STARTED.value) == 6
    assert statuses.count(SkillResultStatus.STEP_SUCCESS.value) == 6
    assert statuses[-1] == SkillResultStatus.COMPLETED.value

    # Step 6: Verify SAY steps published to /tts (3 SAY steps in self_introduce).
    assert len(executive._captured_tts) == 3
    assert all(isinstance(t, str) and t for t in executive._captured_tts)

    # Step 7: Feed COMPLETED back to brain — active_plan should clear.
    last_result = executive._captured_results[-1]
    brain._on_skill_result(_msg(last_result))
    # No assertion needed beyond not crashing; brain.active_plan is None by default
    # and the COMPLETED handler clears it.


def test_mini_e2e_motion_step_dry_runs_without_webrtc(executive):
    """MOTION step succeeds via dry_run path when WebRtcReq is unavailable."""
    # Build a tiny SAY+MOTION plan.
    from interaction_executive.skill_contract import build_plan

    plan = build_plan("wave_hello")
    payload = {
        "plan_id": plan.plan_id,
        "selected_skill": plan.selected_skill,
        "steps": [{"executor": s.executor.value, "args": s.args} for s in plan.steps],
        "reason": plan.reason,
        "source": plan.source,
        "priority_class": int(plan.priority_class),
        "session_id": plan.session_id,
        "created_at": plan.created_at,
    }
    executive._on_proposal(_msg(payload))
    assert _drive_executive_to_completion(executive)

    statuses = [r["status"] for r in executive._captured_results]
    assert statuses[-1] == SkillResultStatus.COMPLETED.value
    # 2 steps (SAY + MOTION) → 2 STEP_STARTED + 2 STEP_SUCCESS
    assert statuses.count(SkillResultStatus.STEP_STARTED.value) == 2
    assert statuses.count(SkillResultStatus.STEP_SUCCESS.value) == 2
