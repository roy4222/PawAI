"""Brain-node speech/offline/canned tests (plan3 online/offline hybrid speech).

T8 — byte-identical regression skeleton (added FIRST, before T3/T4/T5 land):
pins the CURRENT chat-timeout behavior so every later change is checked. With
offline_mode=False + demo_phase=all the chat-timeout fallback MUST still emit
"我聽不太懂" verbatim.

T3/T4/T5 assertions are appended in their own commits.

brain_node imports rclpy → these tests require ROS env and skip cleanly when it
is unavailable (CI-safe subset still passes).
"""
from __future__ import annotations

import time

import pytest

rclpy = pytest.importorskip("rclpy", reason="brain_node tests require ROS env")


@pytest.fixture(scope="module", autouse=True)
def rclpy_context():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


@pytest.fixture
def brain():
    from interaction_executive.brain_node import BrainNode, BufferedSpeech

    node = BrainNode()
    node.chat_wait_ms = 50
    captured = []

    def capture(plan):
        captured.append(node._plan_to_dict(plan))

    node._emit = capture
    node._captured = captured
    node._BufferedSpeech = BufferedSpeech

    try:
        yield node
    finally:
        for timer in list(node._chat_timeouts.values()):
            node.destroy_timer(timer)
        node.destroy_node()


def _buffer_speech(node, session_id="sess-1", transcript="嗯嗯"):
    node._state.chat_buffer[session_id] = node._BufferedSpeech(
        session_id=session_id, transcript=transcript, enqueued_at=time.time()
    )


def _say_text(plan_dict):
    """Extract the say step text from an emitted plan dict."""
    for step in plan_dict.get("steps", []):
        if "text" in step.get("args", {}):
            return step["args"]["text"]
    return None


# ---------------------------------------------------------------------------
# T8 — byte-identical regression (offline_mode=False + demo_phase=all)
# ---------------------------------------------------------------------------


def test_chat_timeout_all_phase_emits_legacy_string(brain):
    """demo_phase=all → chat timeout emits the verbatim legacy fallback."""
    brain.demo_phase = "all"
    _buffer_speech(brain, "sess-1")
    brain._on_chat_timeout("sess-1")
    assert len(brain._captured) == 1
    assert _say_text(brain._captured[0]) == "我聽不太懂"
    assert brain._captured[0]["selected_skill"] == "say_canned"
    assert brain._captured[0]["reason"] == "chat_candidate_timeout"


def test_chat_timeout_no_buffer_emits_nothing(brain):
    """No buffered session → no plan (byte-identical early return)."""
    brain.demo_phase = "all"
    brain._on_chat_timeout("never-buffered")
    assert brain._captured == []
