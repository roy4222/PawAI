"""BrainNode rule tests for Phase A MVS scenarios."""
import json

import pytest
import rclpy
from std_msgs.msg import String

from interaction_executive.attention_machine import AttentionState
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
    captured_traces = []

    def capture(plan):
        captured.append(node._plan_to_dict(plan))

    node._emit = capture
    node._captured_proposals = captured

    # Intercept conversation_trace_pub.publish to capture traces in tests.
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
# Helpers for Task 4 tests (LLM proposal allowlist + trace publisher)
# ---------------------------------------------------------------------------

def _feed_speech(node, transcript, session_id):
    """Buffer a speech intent without relying on ROS2 timer firing."""
    node._on_speech_intent(_msg({"transcript": transcript, "session_id": session_id}))


def _feed_chat_candidate(node, payload):
    node._on_chat_candidate(_msg(payload))


def _drain_proposals(node):
    """Return and clear captured proposals."""
    result = list(node._captured_proposals)
    node._captured_proposals.clear()
    return result


def _drain_traces(node):
    """Return and clear captured conversation traces."""
    result = list(node._captured_traces)
    node._captured_traces.clear()
    return result


def _msg(payload):
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


def _latest(brain):
    assert brain._captured_proposals
    return brain._captured_proposals[-1]


def _prime_attention_engaged(brain) -> None:
    """Drive AttentionMachine to ENGAGED state using fake-clock ticks.

    D-2/D-3: greet_known_person and object_remark now require ENGAGED attention.
    Tests that need to trigger these skills must call this first.

    Timeline (default thresholds: face_stable_s=0.5, dwell_s=1.5):
      t=0.0 → IDLE, face appears, dwell starts
      t=0.6 → NOTICED (face stable 0.6s >= 0.5s), dwell continues
      t=2.5 → ENGAGED (dwell 1.9s >= 1.5s)
    """
    am = brain._attention
    am.tick(now=0.0, face_visible=True, distance_m=1.0, active_plan=False)
    am.tick(now=0.6, face_visible=True, distance_m=1.0, active_plan=False)   # → NOTICED
    am.tick(now=2.5, face_visible=True, distance_m=1.0, active_plan=False)   # → ENGAGED
    assert am.state == AttentionState.ENGAGED, f"Expected ENGAGED, got {am.state}"


def _prime_attention_noticed(brain) -> None:
    """Drive AttentionMachine to NOTICED state (face stable, not yet close/dwelling)."""
    am = brain._attention
    am.tick(now=0.0, face_visible=True, distance_m=2.5, active_plan=False)
    am.tick(now=0.6, face_visible=True, distance_m=2.5, active_plan=False)   # → NOTICED
    assert am.state == AttentionState.NOTICED, f"Expected NOTICED, got {am.state}"


def test_speech_stop_hard_rule(brain):
    brain._on_speech_intent(_msg({"transcript": "請停一下", "session_id": "s-stop"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "stop_move"
    assert plan["priority_class"] == int(PriorityClass.SAFETY)


def test_speech_self_introduce_keyword_removed(brain):
    """5/5 night: self_introduce / show_status keyword bypasses removed.
    Voice 「介紹你自己」/「現在狀態」now flow through chat_buffer → LLM chat
    path → chat_reply (純 SAY，不含 motion，避開 SafetyLayer depth gate).
    Studio button path for full motion self_introduce still works
    (covered by test_studio_skill_request_self_introduce below)."""
    brain._on_speech_intent(_msg({"transcript": "介紹你自己", "session_id": "s-intro"}))
    # No immediate plan — buffered for LLM chat candidate, not direct emit
    assert not brain._captured_proposals

    brain._on_speech_intent(
        _msg({"transcript": "現在狀態如何", "session_id": "s-status"})
    )
    assert not brain._captured_proposals


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
    assert plan["selected_skill"] == "wave_hello"


def test_known_face_greets_stable_identity(brain):
    # D-3: greet_known_person now requires ENGAGED attention state.
    _prime_attention_engaged(brain)
    brain._on_face(_msg({"identity": "alice", "identity_stable": True}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "greet_known_person"
    assert plan["steps"][0]["args"]["text"] == "歡迎回來，alice"


def test_unknown_face_stable_triggers_stranger_alert(brain):
    # D-3: stranger_alert requires NOTICED+ attention state (Option B).
    _prime_attention_noticed(brain)
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
    assert _latest(brain)["selected_skill"] == "wave_hello"


# ---------------------------------------------------------------------------
# B3b — Phase B v1 new rules (impl notes 2026-05-04 §2)
# ---------------------------------------------------------------------------


def test_gesture_palm_triggers_system_pause(brain):
    brain._on_gesture(_msg({"gesture": "palm"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "system_pause"


def test_gesture_fist_triggers_enter_mute_mode(brain):
    """5/12 (測試功能清單 較急 2): fist gesture enters mute mode.

    Direct fire path (no OK confirm) — mode switch is low-risk.
    """
    brain._on_gesture(_msg({"gesture": "fist"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "enter_mute_mode"


def test_gesture_index_triggers_enter_listen_mode(brain):
    """5/12 (測試功能清單 較急 2): index (Pointing_Up) enters listen mode.

    MediaPipe maps Pointing_Up → index (gesture_recognizer_backend.py:52).
    """
    brain._on_gesture(_msg({"gesture": "index"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "enter_listen_mode"


def test_gesture_thumbs_up_requests_confirm_not_immediate_wiggle(brain):
    brain._on_gesture(_msg({"gesture": "thumbs_up"}))
    # Should emit a "say_canned" hint asking for OK, NOT wiggle directly.
    plan = _latest(brain)
    assert plan["selected_skill"] == "say_canned"
    assert "OK" in plan["steps"][0]["args"]["text"]
    assert brain._pending_confirm.pending_skill == "wiggle"


def test_gesture_peace_requests_confirm_for_stretch(brain):
    brain._on_gesture(_msg({"gesture": "peace"}))
    assert brain._pending_confirm.pending_skill == "stretch"


def test_gesture_ok_alone_does_not_fire_skill(brain):
    # No prior confirm request — OK gesture is just consumed by the tick.
    brain._on_gesture(_msg({"gesture": "ok"}))
    assert not brain._captured_proposals


def test_pose_sitting_stable_triggers_sit_along(brain):
    brain._on_pose(_msg({"pose": "sitting"}))
    brain._state.sitting_first_seen -= 1.1  # simulate 1.1s elapsed
    brain._on_pose(_msg({"pose": "sitting"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "sit_along"


def test_pose_bending_stable_triggers_careful_remind(brain):
    brain._on_pose(_msg({"pose": "bending"}))
    brain._state.bending_first_seen -= 1.1
    brain._on_pose(_msg({"pose": "bending"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "careful_remind"


# 5/8 [#F-confirm]: PENDING 期間 face/pose auto-rule 不應發 plan，避免蓋掉 confirm 流


def test_face_during_pending_does_not_emit(brain):
    """PENDING 期間人臉穩定不應觸發 greet_known_person。"""
    brain._on_gesture(_msg({"gesture": "thumbs_up"}))  # enter PENDING(wiggle)
    brain._captured_proposals.clear()
    # known face stable → 平常會發 greet_known_person，但 PENDING 應 suppress
    brain._on_face(_msg({"identity": "alice", "stable": True}))
    assert not any(
        p["selected_skill"] == "greet_known_person" for p in brain._captured_proposals
    )


def test_pose_sitting_during_pending_does_not_emit(brain):
    """PENDING 期間 sitting 穩定不應觸發 sit_along。"""
    brain._on_gesture(_msg({"gesture": "thumbs_up"}))  # enter PENDING(wiggle)
    brain._captured_proposals.clear()
    brain._on_pose(_msg({"pose": "sitting"}))
    brain._state.sitting_first_seen -= 1.1
    brain._on_pose(_msg({"pose": "sitting"}))
    assert not any(
        p["selected_skill"] == "sit_along" for p in brain._captured_proposals
    )


def test_pose_bending_during_pending_does_not_emit(brain):
    """PENDING 期間 bending 穩定不應觸發 careful_remind。"""
    brain._on_gesture(_msg({"gesture": "peace"}))  # enter PENDING(stretch)
    brain._captured_proposals.clear()
    brain._on_pose(_msg({"pose": "bending"}))
    brain._state.bending_first_seen -= 1.1
    brain._on_pose(_msg({"pose": "bending"}))
    assert not any(
        p["selected_skill"] == "careful_remind" for p in brain._captured_proposals
    )


def test_new_speech_intent_cancels_pending_confirm(brain):
    """5/8 [#F-confirm-timeout]: user 換新話題（語音）→ pending confirm 主動 cancel。"""
    from interaction_executive.pending_confirm import ConfirmState

    brain._on_gesture(_msg({"gesture": "thumbs_up"}))  # enter PENDING(wiggle)
    assert brain._pending_confirm.state == ConfirmState.PENDING
    brain._on_speech_intent(_msg({"transcript": "你好啊", "session_id": "s-newchat"}))
    # speech intent 經 buffer 等 chat_candidate；pending 應已 reset
    assert brain._pending_confirm.state == ConfirmState.IDLE


def test_pose_fallen_uses_name_when_available(brain):
    brain._on_pose(_msg({"pose": "fallen", "name": "Roy"}))
    brain._state.fallen_first_seen -= 0.06
    brain._on_pose(_msg({"pose": "fallen", "name": "Roy"}))
    plan = _latest(brain)
    say_steps = [s for s in plan["steps"] if s["executor"] == "say"]
    assert "Roy" in say_steps[0]["args"]["text"]


def test_pose_fallen_uses_cached_face_identity_when_pose_lacks_name(brain):
    """5/12: raw pose payload has no name → fall back to last stable face.

    Brain caches stable identity from /event/face_identity (_on_face) and
    injects into fallen_alert when pose payload lacks name. Audible fall TTS
    runs ONLY through Brain skill (bridge audible disabled 5/12) — name
    injection is the only way demo gets "偵測到 Roy 跌倒" instead of "有人".
    """
    # Prime cache with stable face
    brain._on_face(_msg({"identity": "Roy", "identity_stable": True}))
    # Fallen 2s, no name in pose payload
    brain._on_pose(_msg({"pose": "fallen"}))
    brain._state.fallen_first_seen -= 0.06
    brain._on_pose(_msg({"pose": "fallen"}))
    plan = _latest(brain)
    say_steps = [s for s in plan["steps"] if s["executor"] == "say"]
    assert "Roy" in say_steps[0]["args"]["text"], (
        f"Expected cached identity 'Roy' in fallen TTS, got: {say_steps[0]['args']['text']!r}"
    )


def test_pose_fallen_falls_back_to_youren_when_no_face_cached(brain):
    """5/12: no name in pose, no stable face cached → 'have人' fallback."""
    brain._on_pose(_msg({"pose": "fallen"}))
    brain._state.fallen_first_seen -= 0.06
    brain._on_pose(_msg({"pose": "fallen"}))
    plan = _latest(brain)
    say_steps = [s for s in plan["steps"] if s["executor"] == "say"]
    assert "有人" in say_steps[0]["args"]["text"]


def test_object_detected_triggers_object_remark(brain):
    """Production payload format (objects[] array) with colour preamble + special suffix.

    D-3: object_remark now requires ENGAGED attention state.
    """
    _prime_attention_engaged(brain)
    brain._on_object(_msg({
        "stamp": 1.0,
        "event_type": "object_detected",
        "objects": [{"class_name": "cup", "confidence": 0.9, "bbox": [0, 0, 10, 10], "color": "red"}],
    }))
    plan = _latest(brain)
    assert plan["selected_skill"] == "object_remark"
    assert plan["steps"][0]["args"]["text"] == "看到紅色的杯子了，你要喝水嗎？"


def test_object_legacy_flat_payload_still_works(brain):
    """Legacy/test format (flat dict) — backwards-compat with existing call sites.

    D-3: object_remark now requires ENGAGED attention state.
    """
    _prime_attention_engaged(brain)
    brain._on_object(_msg({"label": "laptop", "color": "blue"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "object_remark"
    assert plan["steps"][0]["args"]["text"] == "看到藍色的筆電了"


def test_object_unknown_color_drops_color_preamble(brain):
    # D-3: need ENGAGED for object_remark to emit
    _prime_attention_engaged(brain)
    brain._on_object(_msg({"label": "cup", "color": "Unknown"}))
    plan = _latest(brain)
    assert plan["steps"][0]["args"]["text"] == "看到杯子了，你要喝水嗎？"


def test_object_without_label_ignored(brain):
    brain._on_object(_msg({"color": "red"}))
    assert not brain._captured_proposals


def test_object_off_whitelist_class_silent(brain):
    """frisbee not in OBJECT_CLASS_ZH whitelist — UI shows it but PawAI stays quiet."""
    brain._on_object(_msg({
        "objects": [{"class_name": "frisbee", "confidence": 0.9, "bbox": [0, 0, 10, 10], "color": "red"}],
    }))
    assert not brain._captured_proposals


# ---------------------------------------------------------------------------
# Bug fixes from 2026-05-04 review
# ---------------------------------------------------------------------------


def test_studio_button_high_risk_skill_must_go_through_confirm(brain):
    """Bug 2: wiggle/stretch/approach_person must NOT bypass OK confirm even via Studio button."""
    brain._on_skill_request(
        _msg({"skill": "wiggle", "args": {}, "request_id": "btn-x", "source": "studio_button"})
    )
    # Should emit a "say_canned" hint asking for OK, NOT wiggle directly.
    assert brain._captured_proposals
    plan = _latest(brain)
    assert plan["selected_skill"] == "say_canned"
    assert "OK" in plan["steps"][0]["args"]["text"]
    assert brain._pending_confirm.pending_skill == "wiggle"


def test_studio_button_nav_demo_point_bypasses_confirm(brain):
    """Bug 2: nav_demo_point is the explicit allowlist for Studio button bypass."""
    brain._on_skill_request(
        _msg(
            {
                "skill": "nav_demo_point",
                "args": {},
                "request_id": "btn-nav",
                "source": "studio_button",
            }
        )
    )
    plan = _latest(brain)
    assert plan["selected_skill"] == "nav_demo_point"
    # PendingConfirm should remain idle for the bypass case.
    assert brain._pending_confirm.pending_skill is None


def test_studio_button_low_risk_skill_runs_directly(brain):
    """Studio button: low-risk skills (no requires_confirmation) still run immediately."""
    brain._on_skill_request(
        _msg({"skill": "wave_hello", "args": {}, "request_id": "btn-lr", "source": "studio_button"})
    )
    assert _latest(brain)["selected_skill"] == "wave_hello"


def test_system_pause_stops_motion_before_speaking(brain):
    """Bug 3: system_pause must include MOTION stop_move step."""
    brain._on_gesture(_msg({"gesture": "palm"}))
    plan = _latest(brain)
    assert plan["selected_skill"] == "system_pause"
    executors = [s["executor"] for s in plan["steps"]]
    assert "motion" in executors, f"system_pause missing motion step: {executors}"
    # MOTION must come BEFORE SAY (stop first, then speak).
    assert executors.index("motion") < executors.index("say"), (
        f"MOTION must precede SAY in system_pause: {executors}"
    )
    motion_step = next(s for s in plan["steps"] if s["executor"] == "motion")
    assert motion_step["args"]["name"] == "stop_move"


# ---------------------------------------------------------------------------
# Task 4 — LLM proposal allowlist + conversation_trace publisher
# ---------------------------------------------------------------------------


def test_chat_candidate_with_show_status_proposal_emits_chat_reply_then_show_status(brain):
    """show_status is in EXECUTE allowlist → both chat_reply and show_status enqueued."""
    _feed_speech(brain, "你還好嗎", "s1")
    _feed_chat_candidate(brain, {
        "session_id": "s1",
        "reply_text": "我很好",
        "proposed_skill": "show_status",
        "proposed_args": {},
        "proposal_reason": "openrouter:eval_schema",
        "engine": "legacy",
    })
    plans = _drain_proposals(brain)
    skills = [p["selected_skill"] for p in plans]
    assert skills == ["chat_reply", "show_status"]
    traces = _drain_traces(brain)
    assert any(t["stage"] == "skill_gate" and t["status"] == "accepted" for t in traces)


def test_chat_candidate_with_self_introduce_proposal_emits_chat_reply_only_trace_only(brain):
    """self_introduce is TRACE_ONLY → only chat_reply enqueued; trace records accepted_trace_only."""
    _feed_speech(brain, "你是誰", "s2")
    _feed_chat_candidate(brain, {
        "session_id": "s2",
        "reply_text": "汪，我是 PawAI",
        "proposed_skill": "self_introduce",
        "proposed_args": {},
        "engine": "legacy",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply"]
    traces = _drain_traces(brain)
    assert any(
        t["stage"] == "skill_gate" and t["status"] == "accepted_trace_only" and t["detail"] == "self_introduce"
        for t in traces
    )


def test_chat_candidate_with_disallowed_proposal_rejected(brain):
    """dance is not in the allowlist → only chat_reply enqueued; trace records rejected_not_allowed."""
    _feed_speech(brain, "跳舞", "s3")
    _feed_chat_candidate(brain, {
        "session_id": "s3",
        "reply_text": "好啊",
        "proposed_skill": "dance",
        "proposed_args": {},
        "engine": "legacy",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply"]
    traces = _drain_traces(brain)
    assert any(
        t["stage"] == "skill_gate" and t["status"] == "rejected_not_allowed"
        for t in traces
    )


def test_chat_candidate_with_no_proposal_only_chat_reply(brain):
    """No proposed_skill → only chat_reply enqueued; no skill_gate trace emitted."""
    _feed_speech(brain, "天氣如何", "s4")
    _feed_chat_candidate(brain, {
        "session_id": "s4",
        "reply_text": "今天很適合散步",
        "proposed_skill": None,
        "engine": "legacy",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply"]
    traces = _drain_traces(brain)
    assert not any(t["stage"] == "skill_gate" for t in traces)


def test_chat_candidate_for_orphan_session_drops_proposal_and_reply(brain):
    """Late LLM response after timeout: no chat_reply, no skill, no trace."""
    # Do NOT call feed_speech first — session is unknown / orphan.
    _feed_chat_candidate(brain, {
        "session_id": "orphan-session",
        "reply_text": "我是 PawAI",
        "proposed_skill": "show_status",
        "proposed_args": {},
        "engine": "legacy",
    })
    plans = _drain_proposals(brain)
    assert plans == []  # no chat_reply, no show_status
    traces = _drain_traces(brain)
    assert not any(t["stage"] == "skill_gate" for t in traces)


def test_chat_candidate_with_wiggle_proposal_requests_pending_confirm(brain):
    """wiggle is CONFIRM mode → no skill plan, PendingConfirm becomes PENDING,
    trace=needs_confirm. Brain_node delegates to existing _pending_confirm
    machinery (shared with gesture-confirm path)."""
    from interaction_executive.pending_confirm import ConfirmState
    _feed_speech(brain, "搖一下", "s-wig")
    _feed_chat_candidate(brain, {
        "session_id": "s-wig",
        "reply_text": "[playful] 好啊，請比 OK 我就搖",
        "proposed_skill": "wiggle",
        "proposed_args": {},
        "engine": "langgraph",
    })
    plans = _drain_proposals(brain)
    # chat_reply emitted, but no wiggle motion plan (waiting for OK)
    assert [p["selected_skill"] for p in plans] == ["chat_reply"]
    # PendingConfirm primed
    assert brain._pending_confirm.state == ConfirmState.PENDING
    assert brain._pending_confirm.pending_skill == "wiggle"   # ← property name
    # Trace evidence
    traces = _drain_traces(brain)
    assert any(
        t["stage"] == "skill_gate" and t["status"] == "needs_confirm"
        and t["detail"] == "wiggle"
        for t in traces
    )


def test_chat_candidate_with_wave_hello_proposal_executes(brain):
    _feed_speech(brain, "跟我打招呼", "s-wave")
    _feed_chat_candidate(brain, {
        "session_id": "s-wave",
        "reply_text": "[excited] 嗨！",
        "proposed_skill": "wave_hello",
        "proposed_args": {},
        "engine": "langgraph",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply", "wave_hello"]
    traces = _drain_traces(brain)
    assert any(t["stage"] == "skill_gate" and t["status"] == "accepted"
               and t["detail"] == "wave_hello" for t in traces)


def test_chat_candidate_with_sit_along_proposal_executes(brain):
    _feed_speech(brain, "我坐下來", "s-sit")
    _feed_chat_candidate(brain, {
        "session_id": "s-sit",
        "reply_text": "[playful] 我也坐下陪你",
        "proposed_skill": "sit_along",
        "proposed_args": {},
        "engine": "langgraph",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply", "sit_along"]


def test_chat_candidate_with_greet_known_person_proposal_now_trace_only(brain):
    """1G: LLM proposing greet_known_person → trace_only, not direct execute.

    Face stable detection already handles greet_known_person. Letting LLM also
    propose execute caused interruptions during 'walk over to gesture OK' flow.
    """
    _feed_speech(brain, "向 Roy 打招呼", "s-greet")
    _feed_chat_candidate(brain, {
        "session_id": "s-greet",
        "reply_text": "歡迎回來，Roy",
        "proposed_skill": "greet_known_person",
        "proposed_args": {"name": "Roy"},
        "engine": "langgraph",
    })
    plans = _drain_proposals(brain)
    # Only chat_reply plan is emitted (greet goes to trace_only, not plan)
    assert [p["selected_skill"] for p in plans] == ["chat_reply"]
    # Verify trace emitted with accepted_trace_only (stage=skill_gate)
    traces = _drain_traces(brain)
    assert any(
        t.get("status") == "accepted_trace_only"
        for t in traces
    )


def test_chat_candidate_with_careful_remind_proposal_executes(brain):
    _feed_speech(brain, "提醒一下小心", "s-care")
    _feed_chat_candidate(brain, {
        "session_id": "s-care",
        "reply_text": "[worried] 小心一點喔",
        "proposed_skill": "careful_remind",
        "proposed_args": {},
        "engine": "langgraph",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply", "careful_remind"]


def test_chat_candidate_with_stretch_proposal_requests_pending_confirm(brain):
    """stretch shares wiggle's confirm wiring — same expectation."""
    from interaction_executive.pending_confirm import ConfirmState
    _feed_speech(brain, "伸個懶腰", "s-str")
    _feed_chat_candidate(brain, {
        "session_id": "s-str",
        "reply_text": "[sighs] 好啊，請比 OK",
        "proposed_skill": "stretch",
        "proposed_args": {},
        "engine": "langgraph",
    })
    plans = _drain_proposals(brain)
    assert [p["selected_skill"] for p in plans] == ["chat_reply"]
    assert brain._pending_confirm.state == ConfirmState.PENDING
    assert brain._pending_confirm.pending_skill == "stretch"
    traces = _drain_traces(brain)
    assert any(t["stage"] == "skill_gate" and t["status"] == "needs_confirm"
               and t["detail"] == "stretch" for t in traces)
