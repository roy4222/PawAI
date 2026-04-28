"""BrainNode rule tests for Phase A MVS scenarios."""
import json

import pytest
import rclpy
from std_msgs.msg import String

from interaction_executive.brain_node import BrainNode
from interaction_executive.skill_contract import PriorityClass, SkillResultStatus


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

    def capture(plan):
        captured.append(node._plan_to_dict(plan))

    node._emit = capture
    node._captured_proposals = captured
    try:
        yield node
    finally:
        for timer in list(node._chat_timeouts.values()):
            node.destroy_timer(timer)
        node.destroy_node()


def _msg(payload):
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


def _latest(brain):
    assert brain._captured_proposals
    return brain._captured_proposals[-1]


def test_speech_stop_hard_rule(brain):
    brain._on_speech_intent(_msg({"transcript": "請停一下", "session_id": "s-stop"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "stop_move"
    assert plan["priority_class"] == int(PriorityClass.SAFETY)


def test_speech_self_introduce(brain):
    brain._on_speech_intent(_msg({"transcript": "介紹你自己", "session_id": "s-intro"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "self_introduce"
    assert len(plan["steps"]) == 10


def test_chat_candidate_matches_buffered_speech(brain):
    brain._on_speech_intent(_msg({"transcript": "你好", "session_id": "s-chat"}))
    brain._on_chat_candidate(_msg({"session_id": "s-chat", "reply_text": "你好啊"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "chat_reply"
    assert plan["steps"][0]["args"]["text"] == "你好啊"


def test_chat_candidate_timeout_falls_back_to_say_canned(brain):
    brain._on_speech_intent(_msg({"transcript": "未知句子", "session_id": "s-timeout"}))
    brain._on_chat_timeout("s-timeout")
    plan = _latest(brain)
    assert plan["selected_skill"] == "say_canned"
    assert plan["steps"][0]["args"]["text"] == "我聽不太懂"


def test_gesture_wave_acknowledges(brain):
    brain._on_gesture(_msg({"gesture": "wave"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "acknowledge_gesture"


def test_known_face_greets_stable_identity(brain):
    brain._on_face(_msg({"identity": "alice", "identity_stable": True}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "greet_known_person"
    assert plan["steps"][0]["args"]["text"] == "歡迎回來，alice"


def test_unknown_face_stable_triggers_stranger_alert(brain):
    brain._on_face(_msg({"identity": "unknown"}))
    brain._state.unknown_face_first_seen -= 0.06
    brain._on_face(_msg({"identity": "unknown"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "stranger_alert"
    assert all(step["executor"] == "say" for step in plan["steps"])


def test_pose_fallen_stable_triggers_fallen_alert(brain):
    brain._on_pose(_msg({"pose": "fallen"}))
    brain._state.fallen_first_seen -= 0.06
    brain._on_pose(_msg({"pose": "fallen"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "fallen_alert"
    motions = [step for step in plan["steps"] if step["executor"] == "motion"]
    assert motions[0]["args"]["name"] == "stop_move"


def test_studio_skill_request_self_introduce(brain):
    brain._on_skill_request(_msg({"skill": "self_introduce", "args": {}, "request_id": "btn-1"}))
    assert _latest(brain)["selected_skill"] == "self_introduce"


def test_studio_skill_request_nav_blocked_until_phase_b(brain):
    brain._on_skill_request(
        _msg({"skill": "go_to_named_place", "args": {"place_id": "kitchen"}, "request_id": "btn-2"})
    )
    assert not brain._captured_proposals


def test_text_input_uses_main_pipeline(brain):
    brain._on_text_input(_msg({"text": "停", "request_id": "txt-1"}))
    assert _latest(brain)["selected_skill"] == "stop_move"


def test_active_sequence_blocks_general_skill_but_not_safety(brain):
    brain._on_skill_result(
        _msg(
            {
                "plan_id": "p-seq",
                "selected_skill": "self_introduce",
                "status": SkillResultStatus.STARTED.value,
                "priority_class": int(PriorityClass.SEQUENCE),
                "step_total": 10,
            }
        )
    )
    brain._on_gesture(_msg({"gesture": "wave"}))
    assert not brain._captured_proposals
    brain._on_speech_intent(_msg({"transcript": "停", "session_id": "s-safety"}))
    assert _latest(brain)["selected_skill"] == "stop_move"

    brain._on_skill_result(
        _msg(
            {
                "plan_id": "p-seq",
                "status": SkillResultStatus.COMPLETED.value,
            }
        )
    )
    brain._on_gesture(_msg({"gesture": "wave"}))
    assert _latest(brain)["selected_skill"] == "acknowledge_gesture"
