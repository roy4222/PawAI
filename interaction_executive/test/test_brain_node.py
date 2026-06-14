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


# ---------------------------------------------------------------------------
# T3 — five-phase 3-tier DEMO_CANNED_TABLE + _phase_canned helper
# ---------------------------------------------------------------------------

_EXPECTED_CANNED = {
    "s1_nav": {
        "success": "我正在移動到巡檢位置。",
        "degraded": "我正在前往巡檢位置，請稍等。",
        "generic": "我先在這裡待命。",
    },
    "s2_greet": {
        "success": "Roy，歡迎回來，我看到你了。",
        "degraded": "嗨，歡迎回來。",
        "generic": "哈囉，很高興見到你。",
    },
    "s3_pose_object": {
        "success": "我看到杯子了，記得補充水分。",
        "degraded": "我看到桌上有東西，記得喝水喔。",
        "generic": "記得多喝水、休息一下。",
    },
    "s4_gesture": {
        "success": "你要我 WeGo 一下嗎？比 OK 我就開始。",
        "degraded": "我看到你的手勢了，比 OK 我就開始。",
        "generic": "你可以比個手勢跟我互動。",
    },
    "s5_safety": {
        "success": "這個動作不安全，我不能執行。",
        "degraded": "這個指令我不能做，太危險了。",
        "generic": "為了安全，我不能執行這個動作。",
    },
}


def test_demo_canned_table_has_five_phases_three_tiers_nonempty():
    from interaction_executive.brain_node import DEMO_CANNED_TABLE
    assert set(DEMO_CANNED_TABLE) == set(_EXPECTED_CANNED)
    for phase, tiers in DEMO_CANNED_TABLE.items():
        assert set(tiers) == {"success", "degraded", "generic"}, phase
        for tier, text in tiers.items():
            assert isinstance(text, str) and text.strip(), f"{phase}/{tier} empty"


def test_demo_canned_table_text_verbatim():
    from interaction_executive.brain_node import DEMO_CANNED_TABLE
    assert DEMO_CANNED_TABLE == _EXPECTED_CANNED


def test_phase_canned_helper_returns_tier_text(brain):
    assert brain._phase_canned("s3_pose_object", "success") == "我看到杯子了，記得補充水分。"
    assert brain._phase_canned("s2_greet", "generic") == "哈囉，很高興見到你。"
    assert brain._phase_canned("s5_safety", "degraded") == "這個指令我不能做，太危險了。"


def test_phase_canned_helper_canonicalizes_alias(brain):
    # legacy alias should resolve to canonical phase table entry
    assert brain._phase_canned("s2_face", "generic") == "哈囉，很高興見到你。"
    assert brain._phase_canned("s3_object", "success") == "我看到杯子了，記得補充水分。"


# ---------------------------------------------------------------------------
# T4 — offline_mode param: short-circuit chat/LLM path straight to canned
# ---------------------------------------------------------------------------

import json  # noqa: E402


def _speech_msg(transcript="今天天氣如何", session_id="off-1"):
    from std_msgs.msg import String
    m = String()
    m.data = json.dumps({"transcript": transcript, "session_id": session_id})
    return m


def test_offline_mode_param_default_false(brain):
    assert brain.offline_mode is False


class _FakeParam:
    def __init__(self, name, value):
        self.name = name
        self.value = value


def test_offline_mode_runtime_set_accepted(brain):
    brain._on_set_params([_FakeParam("offline_mode", True)])
    assert brain.offline_mode is True
    brain._on_set_params([_FakeParam("offline_mode", False)])
    assert brain.offline_mode is False


def test_offline_mode_true_emits_canned_no_timer(brain):
    """offline_mode=True → speech intent emits phase-aware canned, 0 LLM, no
    chat_wait_ms timer (0s window)."""
    brain.offline_mode = True
    brain.demo_phase = "s2_greet"
    n_timers_before = len(brain._chat_timeouts)
    brain._on_speech_intent(_speech_msg(session_id="off-1"))
    # canned emitted from s2 generic bucket
    assert len(brain._captured) == 1
    assert _say_text(brain._captured[0]) == "哈囉，很高興見到你。"
    # no chat-wait timer was created (no LLM window opened)
    assert len(brain._chat_timeouts) == n_timers_before
    assert "off-1" not in brain._state.chat_buffer


def test_offline_mode_false_uses_legacy_chat_window(brain):
    """offline_mode=False (default) → byte-identical: buffers speech + timer."""
    brain.offline_mode = False
    brain.demo_phase = "all"
    brain._on_speech_intent(_speech_msg(session_id="on-1"))
    # legacy path: buffered + timer created, no immediate emit
    assert brain._captured == []
    assert "on-1" in brain._state.chat_buffer
    assert "on-1" in brain._chat_timeouts


def test_offline_mode_does_not_short_circuit_safety(brain):
    """Safety (hard_rule '停') still wins even with offline_mode=True."""
    brain.offline_mode = True
    brain.demo_phase = "s2_greet"
    brain._on_speech_intent(_speech_msg(transcript="停", session_id="stop-1"))
    # safety plan emitted, NOT the s2 greet canned
    assert len(brain._captured) >= 1
    assert _say_text(brain._captured[0]) != "哈囉，很高興見到你。"
    assert brain._captured[0]["selected_skill"] != "say_canned" or \
        brain._captured[0]["source"] != "rule:chat_fallback"


# ---------------------------------------------------------------------------
# T5 — _on_chat_timeout phase-aware (generic tier); demo_phase=all byte-identical
# ---------------------------------------------------------------------------


def test_chat_timeout_phase_aware_generic_bucket(brain):
    """demo_phase=s2_greet + chat timeout → s2 generic canned."""
    brain.offline_mode = False
    brain.demo_phase = "s2_greet"
    _buffer_speech(brain, "ph-1")
    brain._on_chat_timeout("ph-1")
    assert len(brain._captured) == 1
    assert _say_text(brain._captured[0]) == "哈囉，很高興見到你。"


def test_chat_timeout_s3_generic_bucket(brain):
    brain.offline_mode = False
    brain.demo_phase = "s3_pose_object"
    _buffer_speech(brain, "ph-3")
    brain._on_chat_timeout("ph-3")
    assert _say_text(brain._captured[0]) == "記得多喝水、休息一下。"


def test_chat_timeout_all_phase_byte_identical(brain):
    """demo_phase=all → still verbatim 我聽不太懂 (byte-identical)."""
    brain.offline_mode = False
    brain.demo_phase = "all"
    _buffer_speech(brain, "ph-all")
    brain._on_chat_timeout("ph-all")
    assert _say_text(brain._captured[0]) == "我聽不太懂"


def test_chat_timeout_quiet_phase_byte_identical(brain):
    """demo_phase=quiet (no table entry) → legacy string too."""
    brain.offline_mode = False
    brain.demo_phase = "quiet"
    _buffer_speech(brain, "ph-q")
    brain._on_chat_timeout("ph-q")
    assert _say_text(brain._captured[0]) == "我聽不太懂"


def test_fallback_reason_enum_exists_with_low_confidence_hook():
    """T5: fallback-reason enum present; low_confidence is a declared hook."""
    from interaction_executive.brain_node import FallbackReason
    names = {m.name for m in FallbackReason}
    assert "CHAT_CANDIDATE_TIMEOUT" in names
    assert "LOW_CONFIDENCE" in names  # declared hook (unused for now)
    assert "OFFLINE_MODE" in names
