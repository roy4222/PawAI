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
# G2 (6/15) — offline + demo_phase=all (DEFAULT) must NOT play the broken
# legacy 我聽不太懂; uses warm OFFLINE_GENERIC_FALLBACK. Online path unchanged.
# ---------------------------------------------------------------------------


def test_offline_mode_all_phase_uses_warm_filler_not_legacy(brain):
    """offline_mode + demo_phase=all (the DEFAULT, no canned table entry) must
    NOT play the broken-sounding legacy 我聽不太懂 — it uses the warm
    OFFLINE_GENERIC_FALLBACK so a forgotten phase-set never embarrasses the demo
    (the 6/15 manual-phase footgun). The ONLINE timeout path is unaffected (T8).
    """
    from interaction_executive.brain_node import OFFLINE_GENERIC_FALLBACK
    brain.offline_mode = True
    brain.demo_phase = "all"
    brain._on_speech_intent(_speech_msg(session_id="off-all"))
    assert len(brain._captured) == 1
    assert _say_text(brain._captured[0]) == OFFLINE_GENERIC_FALLBACK
    assert _say_text(brain._captured[0]) != "我聽不太懂"
    assert brain._captured[0]["reason"] == "offline_mode"


def test_offline_generic_fallback_is_nonempty_and_not_legacy():
    """The warm filler is a real non-empty line, distinct from the legacy
    online-timeout string (the two paths stay intentionally different)."""
    from interaction_executive.brain_node import OFFLINE_GENERIC_FALLBACK
    assert isinstance(OFFLINE_GENERIC_FALLBACK, str) and OFFLINE_GENERIC_FALLBACK.strip()
    assert OFFLINE_GENERIC_FALLBACK != "我聽不太懂"


# ---------------------------------------------------------------------------
# greet fast-path (6/18) —「你好」直接講 canned 問候、不進 chat_buffer、不等
# chat_wait_ms / LLM。SAY-only（never 被 SafetyLayer 擋）。判定走 transcript 關鍵字
# （非 intent 欄位）→ Studio 文字（intent 寫死 chat）也能短路，且不誤觸舉手/揮手。
# ---------------------------------------------------------------------------


def _greet_msg(session_id="greet-1", intent="greet", transcript="你好"):
    from std_msgs.msg import String
    m = String()
    m.data = json.dumps(
        {"transcript": transcript, "session_id": session_id, "intent": intent}
    )
    return m


def test_greet_fast_path_default_on(brain):
    assert brain.greet_fast_path is True


def test_greet_fast_path_runtime_toggle(brain):
    brain._on_set_params([_FakeParam("greet_fast_path", False)])
    assert brain.greet_fast_path is False
    brain._on_set_params([_FakeParam("greet_fast_path", True)])
    assert brain.greet_fast_path is True


def test_greet_fast_path_generic_no_known_face(brain):
    """intent=greet, no fresh known face → instant generic say_canned, no buffer,
    no chat-wait timer (0s, no LLM)."""
    brain._last_stable_identity_name = None
    n_timers_before = len(brain._chat_timeouts)
    brain._on_speech_intent(_greet_msg(session_id="greet-gen"))
    assert len(brain._captured) == 1
    assert brain._captured[0]["selected_skill"] == "say_canned"
    assert brain._captured[0]["source"] == "rule:greet_fast_path"
    assert brain._captured[0]["reason"] == "greet_fast_path:generic"
    assert len(brain._chat_timeouts) == n_timers_before
    assert "greet-gen" not in brain._state.chat_buffer


def test_greet_fast_path_named_when_known_face_fresh(brain):
    """intent=greet with a fresh stable known face → greet_known_person by name."""
    brain._last_stable_identity_name = "Roy"
    brain._last_stable_identity_ts = time.time()
    brain._on_speech_intent(_greet_msg(session_id="greet-named"))
    assert len(brain._captured) == 1
    assert brain._captured[0]["selected_skill"] == "greet_known_person"
    assert "Roy" in _say_text(brain._captured[0])
    assert brain._captured[0]["source"] == "rule:greet_fast_path"


def test_greet_fast_path_stale_name_falls_back_to_generic(brain):
    """A known name older than the 8s freshness window → generic, not by name."""
    brain._last_stable_identity_name = "Roy"
    brain._last_stable_identity_ts = time.time() - 60.0
    brain._on_speech_intent(_greet_msg(session_id="greet-stale"))
    assert len(brain._captured) == 1
    assert brain._captured[0]["selected_skill"] == "say_canned"
    assert brain._captured[0]["reason"] == "greet_fast_path:generic"


def test_greet_fast_path_studio_text_intent_chat(brain):
    """6/18 真機根因：Studio 文字輸入把 intent 寫死 'chat'。fast-path 走 transcript
    關鍵字，所以文字「你好」(intent=chat) 仍立即短路（不被 intent 欄位擋掉）。"""
    brain._last_stable_identity_name = None
    brain.offline_mode = False
    brain.demo_phase = "all"
    brain._on_speech_intent(_greet_msg(session_id="studio-1", intent="chat"))
    assert len(brain._captured) == 1
    assert brain._captured[0]["source"] == "rule:greet_fast_path"
    assert "studio-1" not in brain._state.chat_buffer


def test_greet_fast_path_disabled_uses_chat_window(brain):
    """greet_fast_path=False →「你好」falls through to legacy chat buffer
    (waits for LLM candidate / chat_wait_ms), no instant emit."""
    brain.greet_fast_path = False
    brain.offline_mode = False
    brain.demo_phase = "all"
    brain._on_speech_intent(_greet_msg(session_id="greet-off"))
    assert brain._captured == []
    assert "greet-off" in brain._state.chat_buffer
    assert "greet-off" in brain._chat_timeouts


def test_greet_fast_path_non_greeting_text_unaffected(brain):
    """Non-greeting text ('今天天氣如何') is NOT short-circuited — legacy chat
    window, even though intent=chat (transcript has no greeting keyword)."""
    brain.greet_fast_path = True
    brain.offline_mode = False
    brain.demo_phase = "all"
    brain._on_speech_intent(
        _greet_msg(session_id="chat-1", intent="chat", transcript="今天天氣如何")
    )
    assert brain._captured == []
    assert "chat-1" in brain._state.chat_buffer


def test_greet_fast_path_raise_hand_not_short_circuited(brain):
    """『舉手』被 classifier 歸成 intent=greet，但要的是狗舉手（wave_hello MOTION），
    不是講問候。fast-path 排除舉手/揮手 → 不短路，照常進 chat window 讓 LLM 觸發
    wave_hello。保護呂奇傑『講舉手他才舉手』的 demo。"""
    brain.greet_fast_path = True
    brain.offline_mode = False
    brain.demo_phase = "all"
    brain._on_speech_intent(
        _greet_msg(session_id="hand-1", intent="greet", transcript="舉手")
    )
    assert brain._captured == []
    assert "hand-1" in brain._state.chat_buffer


def test_greet_fast_path_greeting_prefixed_request_goes_to_llm(brain):
    """含問候前綴的真實請求（『你好可以幫我關燈嗎』）超過長度閘 → 不短路，進 LLM
    路徑拿真正的對話回覆，而不是被誤判成純問候。"""
    brain.greet_fast_path = True
    brain.offline_mode = False
    brain.demo_phase = "all"
    brain._on_speech_intent(
        _greet_msg(session_id="req-1", intent="chat", transcript="你好可以幫我關燈嗎")
    )
    assert brain._captured == []
    assert "req-1" in brain._state.chat_buffer


def test_is_verbal_greet_predicate(brain):
    """Direct predicate checks: bare greetings fire; raise-hand and prefixed
    requests do not."""
    assert brain._is_verbal_greet("你好") is True
    assert brain._is_verbal_greet("哈囉") is True
    assert brain._is_verbal_greet(" 嗨 ") is True
    assert brain._is_verbal_greet("Hello") is True
    assert brain._is_verbal_greet("您好") is True
    assert brain._is_verbal_greet("舉手") is False
    assert brain._is_verbal_greet("揮手") is False
    assert brain._is_verbal_greet("你好可以幫我關燈嗎") is False
    assert brain._is_verbal_greet("今天天氣如何") is False
    assert brain._is_verbal_greet("") is False


def test_greet_fast_path_safety_still_wins(brain):
    """Safety hard_rule '停' wins even if fast-path on (safety checked first)."""
    brain.greet_fast_path = True
    brain._on_speech_intent(_greet_msg(transcript="停", session_id="greet-stop", intent="greet"))
    assert len(brain._captured) >= 1
    assert brain._captured[0]["source"] != "rule:greet_fast_path"


# ---------------------------------------------------------------------------
# T4b — /brain/offline_mode Bool subscriber (Studio toggle) sharing
#       _set_offline_mode with the param-set path. plan3 T4 wiring.
# ---------------------------------------------------------------------------


def _bool_msg(value):
    from std_msgs.msg import Bool
    m = Bool()
    m.data = value
    return m


def _string_msg(value):
    from std_msgs.msg import String
    m = String()
    m.data = value
    return m


def test_offline_mode_topic_sets_true(brain):
    assert brain.offline_mode is False
    brain._on_offline_mode_msg(_bool_msg(True))
    assert brain.offline_mode is True


def test_offline_mode_topic_sets_false(brain):
    brain.offline_mode = True
    brain._on_offline_mode_msg(_bool_msg(False))
    assert brain.offline_mode is False


def test_offline_mode_param_still_flips_through_shared_setter(brain):
    """param-set continues to flip offline_mode (now via _set_offline_mode)."""
    brain._on_set_params([_FakeParam("offline_mode", True)])
    assert brain.offline_mode is True
    brain._on_set_params([_FakeParam("offline_mode", False)])
    assert brain.offline_mode is False


def test_offline_mode_never_set_stays_false_byte_identical(brain):
    """Default-off byte-identical: untouched node has offline_mode False."""
    assert brain.offline_mode is False


def test_offline_mode_param_and_topic_share_set_offline_mode(brain, monkeypatch):
    """Both param-set and the /brain/offline_mode topic route through the same
    single setter _set_offline_mode (no drift)."""
    seen = []
    real = brain._set_offline_mode

    def spy(enabled, via):
        seen.append((enabled, via))
        return real(enabled, via)

    monkeypatch.setattr(brain, "_set_offline_mode", spy)
    # topic path
    brain._on_offline_mode_msg(_bool_msg(True))
    # param path
    brain._on_set_params([_FakeParam("offline_mode", False)])
    assert (True, "/brain/offline_mode") in seen
    assert (False, "param") in seen
    assert brain.offline_mode is False


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


# ---------------------------------------------------------------------------
# B1 — object_remark_priority: stable class-priority reorder before first pick.
#       Default [] = byte-identical "take objects[0]".
# ---------------------------------------------------------------------------

from interaction_executive.attention_machine import AttentionState  # noqa: E402


def _object_msg(objects):
    from std_msgs.msg import String
    m = String()
    m.data = json.dumps({"event_type": "object_detected", "objects": objects})
    return m


def _force_object_gates_open(node, monkeypatch):
    """Open every emit gate so _on_object reaches build_object_tts/emit, leaving
    ONLY the priority selection under test."""
    monkeypatch.setattr(node, "_attention_state_snapshot",
                        lambda: AttentionState.ENGAGED)
    monkeypatch.setattr(node, "_has_active_skill_or_sequence", lambda: False)
    monkeypatch.setattr(node, "_phase_allows", lambda kind: True)


def test_object_remark_priority_param_default_empty(brain):
    assert brain.object_remark_priority == []


def test_prioritized_objects_default_empty_is_same_list_identity(brain):
    """[] priority → returns the SAME list object untouched (byte-identical)."""
    assert brain.object_remark_priority == []
    objs = [{"class_name": "cell_phone"}, {"class_name": "cup"}]
    assert brain._prioritized_objects(objs) is objs


def test_prioritized_objects_floats_priority_class_to_front(brain):
    brain.object_remark_priority = ["cup", "bottle"]
    objs = [{"class_name": "cell_phone"}, {"class_name": "cup"}]
    out = brain._prioritized_objects(objs)
    assert [d["class_name"] for d in out] == ["cup", "cell_phone"]


def test_prioritized_objects_respects_priority_list_order(brain):
    brain.object_remark_priority = ["cup", "bottle"]
    objs = [{"class_name": "bottle"}, {"class_name": "chair"}, {"class_name": "cup"}]
    out = brain._prioritized_objects(objs)
    # cup before bottle (priority order); chair last (not listed) keeps tail.
    assert [d["class_name"] for d in out] == ["cup", "bottle", "chair"]


def test_prioritized_objects_unlisted_keep_relative_order(brain):
    brain.object_remark_priority = ["cup"]
    objs = [{"class_name": "chair"}, {"class_name": "keyboard"}, {"class_name": "cup"}]
    out = brain._prioritized_objects(objs)
    assert [d["class_name"] for d in out] == ["cup", "chair", "keyboard"]


def test_on_object_priority_selects_cup_over_cell_phone(brain, monkeypatch):
    """priority=[cup,bottle] + objects=[cell_phone,cup] → cup remark."""
    _force_object_gates_open(brain, monkeypatch)
    brain.object_remark_priority = ["cup", "bottle"]
    brain._on_object(_object_msg([
        {"class_name": "cell_phone"}, {"class_name": "cup"},
    ]))
    assert len(brain._captured) == 1
    assert "杯子" in _say_text(brain._captured[0])  # cup, not 手機 (cell_phone)
    assert "手機" not in _say_text(brain._captured[0])


def test_on_object_empty_priority_selects_first_byte_identical(brain, monkeypatch):
    """priority=[] (default) + objects=[cell_phone,cup] → cell_phone (unchanged)."""
    _force_object_gates_open(brain, monkeypatch)
    assert brain.object_remark_priority == []
    brain._on_object(_object_msg([
        {"class_name": "cell_phone"}, {"class_name": "cup"},
    ]))
    assert len(brain._captured) == 1
    assert "手機" in _say_text(brain._captured[0])  # cell_phone wins (objects[0])
    assert "杯子" not in _say_text(brain._captured[0])


def test_object_remark_priority_runtime_set_accepted(brain):
    brain._on_set_params([_FakeParam("object_remark_priority", ["cup", "bottle"])])
    assert brain.object_remark_priority == ["cup", "bottle"]
    brain._on_set_params([_FakeParam("object_remark_priority", [])])
    assert brain.object_remark_priority == []


# ---------------------------------------------------------------------------
# B2 — object_remark_attention_min: relax the ENGAGED gate to NOTICED for drink
#      remarks. Default "ENGAGED" = byte-identical (gate only when ENGAGED).
# ---------------------------------------------------------------------------


def _set_attention(node, monkeypatch, state):
    monkeypatch.setattr(node, "_attention_state_snapshot", lambda: state)


def _open_non_attention_object_gates(node, monkeypatch):
    """Open every object_remark gate EXCEPT the attention gate under test."""
    monkeypatch.setattr(node, "_has_active_skill_or_sequence", lambda: False)
    monkeypatch.setattr(node, "_phase_allows", lambda kind: True)


def test_object_remark_attention_min_default_engaged(brain):
    assert brain.object_remark_attention_min == "ENGAGED"


def test_attention_ok_default_only_engaged_passes(brain):
    """Default min=ENGAGED → only ENGAGED clears the gate (byte-identical)."""
    assert brain.object_remark_attention_min == "ENGAGED"
    assert brain._object_remark_attention_ok(AttentionState.ENGAGED, "cup") is True
    assert brain._object_remark_attention_ok(AttentionState.NOTICED, "cup") is False
    assert brain._object_remark_attention_ok(AttentionState.IDLE, "cup") is False
    assert brain._object_remark_attention_ok(AttentionState.INTERACTING, "cup") is False


def test_attention_ok_noticed_relaxes_drink_class_only(brain):
    """min=NOTICED → NOTICED+cup passes; NOTICED+chair still requires ENGAGED."""
    brain.object_remark_attention_min = "NOTICED"
    assert brain._object_remark_attention_ok(AttentionState.NOTICED, "cup") is True
    assert brain._object_remark_attention_ok(AttentionState.NOTICED, "bottle") is True
    assert brain._object_remark_attention_ok(AttentionState.NOTICED, "chair") is False
    # IDLE / INTERACTING are never relaxed, even for a drink class.
    assert brain._object_remark_attention_ok(AttentionState.IDLE, "cup") is False
    assert brain._object_remark_attention_ok(AttentionState.INTERACTING, "cup") is False
    # ENGAGED still always passes.
    assert brain._object_remark_attention_ok(AttentionState.ENGAGED, "chair") is True


def test_on_object_default_engaged_suppresses_noticed(brain, monkeypatch):
    """param=ENGAGED (default) + state=NOTICED → suppress (byte-identical)."""
    _open_non_attention_object_gates(brain, monkeypatch)
    _set_attention(brain, monkeypatch, AttentionState.NOTICED)
    assert brain.object_remark_attention_min == "ENGAGED"
    brain._on_object(_object_msg([{"class_name": "cup"}]))
    assert brain._captured == []


def test_on_object_noticed_min_allows_noticed_cup(brain, monkeypatch):
    """param=NOTICED + state=NOTICED + class=cup → remark emitted."""
    _open_non_attention_object_gates(brain, monkeypatch)
    _set_attention(brain, monkeypatch, AttentionState.NOTICED)
    brain.object_remark_attention_min = "NOTICED"
    brain._on_object(_object_msg([{"class_name": "cup"}]))
    assert len(brain._captured) == 1
    assert "杯子" in _say_text(brain._captured[0])


def test_on_object_noticed_min_still_suppresses_noticed_chair(brain, monkeypatch):
    """param=NOTICED + state=NOTICED + class=chair (non-drink) → still suppress."""
    _open_non_attention_object_gates(brain, monkeypatch)
    _set_attention(brain, monkeypatch, AttentionState.NOTICED)
    brain.object_remark_attention_min = "NOTICED"
    brain._on_object(_object_msg([{"class_name": "chair"}]))
    assert brain._captured == []


def test_on_object_engaged_always_emits_regardless_of_min(brain, monkeypatch):
    """ENGAGED clears the gate for any class even at min=ENGAGED (unchanged)."""
    _open_non_attention_object_gates(brain, monkeypatch)
    _set_attention(brain, monkeypatch, AttentionState.ENGAGED)
    brain._on_object(_object_msg([{"class_name": "cup"}]))
    assert len(brain._captured) == 1
    assert "杯子" in _say_text(brain._captured[0])


def test_object_remark_attention_min_runtime_set_accepted(brain):
    brain._on_set_params([_FakeParam("object_remark_attention_min", "NOTICED")])
    assert brain.object_remark_attention_min == "NOTICED"
    brain._on_set_params([_FakeParam("object_remark_attention_min", "ENGAGED")])
    assert brain.object_remark_attention_min == "ENGAGED"


# ---------------------------------------------------------------------------
# drink-merge: cup AND bottle (and bowl/wine_glass) both fire the 飲水用品 remark
#   and the sitting compound, using generic wording (no cup↔bottle mis-naming).
# ---------------------------------------------------------------------------


def _setup_drink_compound(brain, monkeypatch, sitting):
    """Open object gates + enable drink-merge; set sitting recency per `sitting`."""
    _open_non_attention_object_gates(brain, monkeypatch)
    _set_attention(brain, monkeypatch, AttentionState.ENGAGED)
    brain.demo_video_cup_compound = True
    brain._state.last_sitting_seen_ts = time.time() if sitting else 0.0


@pytest.mark.parametrize("drink_class", ["cup", "bottle", "bowl", "wine_glass"])
def test_drink_class_no_sitting_emits_generic_line(brain, monkeypatch, drink_class):
    """Any drink class (incl. bottle) → generic 飲水用品 line, never a 物名."""
    _setup_drink_compound(brain, monkeypatch, sitting=False)
    brain._on_object(_object_msg([{"class_name": drink_class}]))
    assert len(brain._captured) == 1
    assert _say_text(brain._captured[0]) == "我看到你手邊有飲水用品，記得補充水分。"


@pytest.mark.parametrize("drink_class", ["cup", "bottle"])
def test_drink_class_recent_sitting_emits_compound(brain, monkeypatch, drink_class):
    """bottle/cup + recent sitting → compound clause, generic wording (no 杯子)."""
    _setup_drink_compound(brain, monkeypatch, sitting=True)
    brain._on_object(_object_msg([{"class_name": drink_class}]))
    assert len(brain._captured) == 1
    assert _say_text(brain._captured[0]) == (
        "我看到你坐下了，也看到你手邊有飲水用品，記得補充水分。"
    )


# ---------------------------------------------------------------------------
# B4 — offline_mode / demo_phase setters write the value back to the ROS param
#      store so `ros2 param get` reflects topic-driven changes (no lying).
#      Default (value unchanged) = byte-identical (no set_parameters, no recurse).
# ---------------------------------------------------------------------------


def test_offline_mode_topic_writes_back_to_param(brain):
    """Topic path → get_parameter('offline_mode') reflects the true value."""
    assert brain.get_parameter("offline_mode").value is False
    brain._on_offline_mode_msg(_bool_msg(True))
    assert brain.offline_mode is True
    assert brain.get_parameter("offline_mode").value is True  # no longer lies
    # back to False via topic
    brain._on_offline_mode_msg(_bool_msg(False))
    assert brain.offline_mode is False
    assert brain.get_parameter("offline_mode").value is False


def test_offline_mode_param_path_still_works_after_writeback(brain):
    """param-set path still flips offline_mode (and the param value)."""
    brain._on_set_params([_FakeParam("offline_mode", True)])
    assert brain.offline_mode is True
    # real param-set commits the value too; simulate by reading instance attr.
    brain._on_set_params([_FakeParam("offline_mode", False)])
    assert brain.offline_mode is False


def test_offline_mode_topic_no_infinite_recursion(brain, monkeypatch):
    """Topic→setter→set_parameters→param-callback→setter must not recurse.

    The nested param callback runs with _in_param_callback=True, so the setter's
    _sync_param short-circuits and does NOT call set_parameters again. Counting
    set_parameters proves the writeback fires exactly once (no runaway).
    """
    seen = []
    real = brain.set_parameters

    def spy(params):
        seen.append([p.name for p in params])
        assert len(seen) < 20, "recursion guard failed — set_parameters runaway"
        return real(params)

    monkeypatch.setattr(brain, "set_parameters", spy)
    brain._on_offline_mode_msg(_bool_msg(True))
    assert brain.offline_mode is True
    assert brain.get_parameter("offline_mode").value is True
    # exactly one writeback for offline_mode; the nested callback was guarded.
    assert seen == [["offline_mode"]]


def test_offline_mode_unchanged_value_no_set_parameters(brain, monkeypatch):
    """Setting the same value via topic must NOT call set_parameters (byte-id)."""
    seen = []
    real = brain.set_parameters

    def spy(params):
        seen.append([p.name for p in params])
        return real(params)

    monkeypatch.setattr(brain, "set_parameters", spy)
    # already False → topic False is a no-op writeback
    brain._on_offline_mode_msg(_bool_msg(False))
    assert seen == []
    assert brain.offline_mode is False


def test_demo_phase_topic_writes_back_to_param(brain):
    """Topic path → get_parameter('demo_phase') reflects the canonical phase."""
    assert brain.get_parameter("demo_phase").value == "all"
    brain._on_demo_phase_msg(_string_msg("s2_greet"))
    assert brain.demo_phase == "s2_greet"
    assert brain.get_parameter("demo_phase").value == "s2_greet"  # no longer lies


def test_demo_phase_topic_alias_canonicalized_in_param(brain):
    """Alias s2_face via topic → param store holds canonical s2_greet."""
    brain._on_demo_phase_msg(_string_msg("s2_face"))
    assert brain.demo_phase == "s2_greet"
    assert brain.get_parameter("demo_phase").value == "s2_greet"


def test_demo_phase_same_value_no_writeback(brain, monkeypatch):
    """demo_phase=all (already) via topic → no set_parameters (byte-identical)."""
    seen = []
    real = brain.set_parameters

    def spy(params):
        seen.append([p.name for p in params])
        return real(params)

    monkeypatch.setattr(brain, "set_parameters", spy)
    brain._on_demo_phase_msg(_string_msg("all"))
    assert seen == []
    assert brain.demo_phase == "all"


def test_sync_param_guarded_inside_param_callback(brain):
    """When _in_param_callback is True, _sync_param is a no-op (recursion guard)."""
    brain._in_param_callback = True
    try:
        # would otherwise change the param; guard must short-circuit it.
        brain._sync_param("offline_mode", True)
    finally:
        brain._in_param_callback = False
    # param store untouched by the guarded call
    assert brain.get_parameter("offline_mode").value is False
