"""Demo Conductor / Auto-Advance / Manual-Floor tests (plan2, 2026-06-13).

interaction_state.py is rclpy-free → its T2-1 assertions are tested directly.
brain_node.py node-level tests (T2-2..T2-5) need rclpy; they mirror the
construction pattern in test_brain_rules.py and skip cleanly when ROS env is
unavailable (so the CI-safe subset still passes).
"""
from __future__ import annotations

import pytest

from interaction_executive import interaction_state
from interaction_executive.interaction_state import (
    canonicalize_phase,
    phase_allows,
)


# ---------------------------------------------------------------------------
# T2-1 — PHASE_ALLOWED_KINDS five-phase + canonicalize_phase alias (rclpy-free)
# ---------------------------------------------------------------------------


def test_alias_s2_face_equals_canonical_s2_greet():
    assert phase_allows("s2_face", "greet") == phase_allows("s2_greet", "greet") is True


def test_alias_s3_object_equals_canonical_s3_pose_object():
    assert phase_allows("s3_object", "object") == phase_allows("s3_pose_object", "object") is True


@pytest.mark.parametrize("kind", ["greet", "object", "gesture"])
def test_s1_nav_allows_nothing(kind):
    assert phase_allows("s1_nav", kind) is False


@pytest.mark.parametrize("kind", ["greet", "object", "gesture"])
def test_s5_safety_allows_nothing(kind):
    assert phase_allows("s5_safety", kind) is False


def test_s4_gesture_allows_only_gesture():
    assert phase_allows("s4_gesture", "gesture") is True
    assert phase_allows("s4_gesture", "greet") is False
    assert phase_allows("s4_gesture", "object") is False


def test_s2_greet_allows_only_greet():
    assert phase_allows("s2_greet", "greet") is True
    assert phase_allows("s2_greet", "object") is False


def test_s3_pose_object_allows_only_object():
    assert phase_allows("s3_pose_object", "object") is True
    assert phase_allows("s3_pose_object", "greet") is False


def test_unknown_phase_resolves_to_all_not_quiet():
    # unknown phase must NOT be tightened to quiet — stays permissive (True).
    assert phase_allows("typo_xyz", "greet") is True
    assert phase_allows("typo_xyz", "object") is True
    assert phase_allows("typo_xyz", "gesture") is True


def test_all_phase_allows_three_social_kinds():
    assert phase_allows("all", "greet") is True
    assert phase_allows("all", "object") is True
    assert phase_allows("all", "gesture") is True


def test_quiet_phase_allows_nothing():
    assert phase_allows("quiet", "greet") is False
    assert phase_allows("quiet", "object") is False


def test_canonicalize_phase_aliases():
    assert canonicalize_phase("s2_face") == "s2_greet"
    assert canonicalize_phase("s3_object") == "s3_pose_object"


def test_canonicalize_phase_passthrough():
    assert canonicalize_phase("all") == "all"
    assert canonicalize_phase("s4_gesture") == "s4_gesture"
    assert canonicalize_phase("s1_nav") == "s1_nav"
    assert canonicalize_phase("s5_safety") == "s5_safety"
    assert canonicalize_phase("quiet") == "quiet"
    assert canonicalize_phase("typo_xyz") == "typo_xyz"


def test_phase_allowed_kinds_has_canonical_five_plus_aliases():
    keys = set(interaction_state.PHASE_ALLOWED_KINDS)
    for k in ("s1_nav", "s2_greet", "s3_pose_object", "s4_gesture", "s5_safety"):
        assert k in keys, f"missing canonical phase {k}"
    # aliases + legacy keys preserved (byte-identical)
    for k in ("all", "quiet", "s2_face", "s3_object"):
        assert k in keys, f"missing legacy/alias phase {k}"


# ---------------------------------------------------------------------------
# Node-level fixtures (T2-2..T2-5) — rclpy required, skip cleanly otherwise.
# ---------------------------------------------------------------------------

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
    from interaction_executive.brain_node import BrainNode

    node = BrainNode()
    captured = []

    def capture(plan):
        captured.append(node._plan_to_dict(plan))

    node._emit = capture
    node._captured = captured

    try:
        yield node
    finally:
        for timer in list(node._chat_timeouts.values()):
            node.destroy_timer(timer)
        if getattr(node, "_phase_wait_timer", None) is not None:
            try:
                node.destroy_timer(node._phase_wait_timer)
            except Exception:  # noqa: BLE001
                pass
        node.destroy_node()


def _set_pending(node, skill="wiggle"):
    """Drive PendingConfirm into PENDING via the real API."""
    import time as _t
    from interaction_executive.pending_confirm import ConfirmState
    node._pending_confirm.request_confirm(skill, {}, _t.time())
    assert node._pending_confirm.state == ConfirmState.PENDING


# ---------------------------------------------------------------------------
# T2-2 — _apply_phase_transition cleanup helper + trace
# ---------------------------------------------------------------------------


def test_phase_transition_clears_pending_confirm(brain):
    from interaction_executive.pending_confirm import ConfirmState
    _set_pending(brain, "wiggle")
    brain._apply_phase_transition("s5_safety", "s4_gesture")
    assert brain._pending_confirm.state != ConfirmState.PENDING


def test_phase_transition_clears_active_plan(brain):
    brain._state.active_plan = {"selected_skill": "wiggle"}
    brain._apply_phase_transition("s5_safety", "s4_gesture")
    assert brain._state.active_plan is None


def test_phase_transition_clears_gesture_cooldown(brain):
    import time as _t
    # gesture-driven skill cooldowns + gesture-source dedup + live tracker
    brain._state.last_alert_ts["wiggle"] = _t.time()
    brain._state.last_alert_ts["stretch"] = _t.time()
    brain._state.dedup_cache[("gesture", "thumbs_up", 1)] = _t.time()
    brain._state.current_gesture = "thumbs_up"
    brain._state.current_gesture_ts = _t.time()
    brain._apply_phase_transition("s5_safety", "s4_gesture")
    assert "wiggle" not in brain._state.last_alert_ts
    assert "stretch" not in brain._state.last_alert_ts
    assert ("gesture", "thumbs_up", 1) not in brain._state.dedup_cache
    assert brain._state.current_gesture is None


def test_phase_transition_preserves_attention(brain):
    # attention object identity must be preserved (not reset on phase switch)
    attn_before = brain._attention
    state_before = brain._attention.state
    brain._apply_phase_transition("s5_safety", "s4_gesture")
    assert brain._attention is attn_before
    assert brain._attention.state == state_before


def test_phase_transition_clear_object_false_keeps_dedup(brain):
    brain._object_remark_seen[("cup",)] = 123.0
    import time as _t
    brain._state.last_alert_ts["object_remark"] = _t.time()
    brain._apply_phase_transition("s4_gesture", "s3_pose_object", clear_object=False)
    assert ("cup",) in brain._object_remark_seen
    assert "object_remark" in brain._state.last_alert_ts


def test_phase_transition_clear_object_true_clears_dedup(brain):
    brain._object_remark_seen[("cup",)] = 123.0
    import time as _t
    brain._state.last_alert_ts["object_remark"] = _t.time()
    brain._apply_phase_transition("s3_pose_object", "s4_gesture", clear_object=True)
    assert ("cup",) not in brain._object_remark_seen
    assert "object_remark" not in brain._state.last_alert_ts


def test_phase_transition_clear_greet_true_clears_person_keys(brain):
    import time as _t
    brain._state.last_alert_ts["greet_known_person:Roy"] = _t.time()
    brain._state.last_alert_ts["stranger_alert"] = _t.time()  # other alert preserved
    brain._apply_phase_transition("s2_greet", "all", clear_greet=True)
    assert "greet_known_person:Roy" not in brain._state.last_alert_ts
    assert "stranger_alert" in brain._state.last_alert_ts


def test_phase_transition_never_raises_on_substep_failure(brain, monkeypatch):
    # Force the pending_confirm cancel substep to raise; helper must swallow it.
    from interaction_executive.pending_confirm import ConfirmState
    _set_pending(brain, "wiggle")

    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(brain._pending_confirm, "cancel", _boom)
    # Must not raise; later substeps (active_plan) still run.
    brain._state.active_plan = {"selected_skill": "x"}
    brain._apply_phase_transition("s5_safety", "s4_gesture")
    assert brain._state.active_plan is None


# ---------------------------------------------------------------------------
# T2-3 — _set_demo_phase shared helper + /brain/demo_phase String subscriber
# ---------------------------------------------------------------------------


def test_set_demo_phase_same_value_does_not_call_helper(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_apply_phase_transition",
                        lambda *a, **k: calls.append((a, k)))
    brain.demo_phase = "all"
    brain._set_demo_phase("all")
    assert calls == []  # no-op transition (same value) → byte-identical
    assert brain.demo_phase == "all"


def test_set_demo_phase_real_change_calls_helper(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_apply_phase_transition",
                        lambda *a, **k: calls.append((a, k)))
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_greet")
    assert len(calls) == 1
    assert brain.demo_phase == "s2_greet"


def test_set_demo_phase_canonicalizes_alias(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_apply_phase_transition",
                        lambda *a, **k: calls.append((a, k)))
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_face")
    assert brain.demo_phase == "s2_greet"  # alias canonicalized
    assert len(calls) == 1


def test_set_demo_phase_invalid_keeps_old(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_apply_phase_transition",
                        lambda *a, **k: calls.append((a, k)))
    brain.demo_phase = "s3_pose_object"
    brain._set_demo_phase("bogus")
    assert brain.demo_phase == "s3_pose_object"  # unchanged
    assert calls == []  # helper not called for invalid


def _make_str_msg(data):
    from std_msgs.msg import String
    m = String()
    m.data = data
    return m


def test_demo_phase_topic_canonicalizes_alias(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_apply_phase_transition",
                        lambda *a, **k: calls.append((a, k)))
    brain.demo_phase = "all"
    brain._on_demo_phase_msg(_make_str_msg("s2_face"))
    assert brain.demo_phase == "s2_greet"
    assert len(calls) == 1


def test_demo_phase_topic_handles_case_and_whitespace(brain, monkeypatch):
    monkeypatch.setattr(brain, "_apply_phase_transition", lambda *a, **k: None)
    brain.demo_phase = "all"
    brain._on_demo_phase_msg(_make_str_msg("  S5_SAFETY "))
    assert brain.demo_phase == "s5_safety"


def test_demo_phase_topic_invalid_keeps_old(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_apply_phase_transition",
                        lambda *a, **k: calls.append((a, k)))
    brain.demo_phase = "s4_gesture"
    brain._on_demo_phase_msg(_make_str_msg("nonsense"))
    assert brain.demo_phase == "s4_gesture"
    assert calls == []


def test_param_and_topic_share_set_demo_phase(brain, monkeypatch):
    """Both param-set and topic route through the same _set_demo_phase."""
    seen = []
    real = brain._set_demo_phase

    def spy(value):
        seen.append(value)
        return real(value)

    monkeypatch.setattr(brain, "_set_demo_phase", spy)
    monkeypatch.setattr(brain, "_apply_phase_transition", lambda *a, **k: None)
    # topic path
    brain.demo_phase = "all"
    brain._on_demo_phase_msg(_make_str_msg("s2_greet"))
    # param path
    from rcl_interfaces.msg import Parameter as _PMsg  # noqa: F401
    brain._on_set_params([_FakeParam("demo_phase", "s3_pose_object")])
    assert "s2_greet" in seen and "s3_pose_object" in seen


class _FakeParam:
    def __init__(self, name, value):
        self.name = name
        self.value = value


# ---------------------------------------------------------------------------
# T2-4 — auto_advance_phases + gotcha #1 (phase-entry known-face greet)
# ---------------------------------------------------------------------------


def _set_fresh_known_face(node, name="Roy", age_s=0.5):
    import time as _t
    node._last_stable_identity_name = name
    node._last_stable_identity_ts = _t.time() - age_s


def test_auto_advance_phases_default_empty(brain):
    assert list(brain.auto_advance_phases) == []


def test_auto_advance_on_canonicalizes(brain):
    brain.auto_advance_phases = ["s2_greet"]
    assert brain._auto_advance_on("s2_greet") is True
    assert brain._auto_advance_on("s2_face") is True  # alias
    assert brain._auto_advance_on("s3_pose_object") is False


def test_auto_off_does_not_fire_entry_greet(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet",
                        lambda: calls.append(1))
    monkeypatch.setattr(brain, "_apply_phase_transition", lambda *a, **k: None)
    brain.auto_advance_phases = []
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_greet")
    assert calls == []  # byte-identical: entry-greet not invoked when auto OFF


def test_auto_on_s2_calls_entry_greet(brain, monkeypatch):
    calls = []
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet",
                        lambda: calls.append(1))
    monkeypatch.setattr(brain, "_apply_phase_transition", lambda *a, **k: None)
    brain.auto_advance_phases = ["s2_greet"]
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_greet")
    assert calls == [1]


def test_entry_greet_emits_when_fresh_known_face(brain):
    brain.greet_cooldown_s = 20.0
    brain.greet_sitting_window_s = 3.0
    _set_fresh_known_face(brain, "Roy", age_s=0.5)
    brain.demo_phase = "s2_greet"
    brain._maybe_fire_phase_entry_greet()
    assert len(brain._captured) == 1
    assert brain._captured[0]["selected_skill"] == "greet_known_person"


def test_entry_greet_respects_cooldown(brain):
    import time as _t
    brain.greet_cooldown_s = 20.0
    _set_fresh_known_face(brain, "Roy", age_s=0.5)
    brain._state.last_alert_ts["greet_known_person:Roy"] = _t.time()  # in cooldown
    brain.demo_phase = "s2_greet"
    brain._maybe_fire_phase_entry_greet()
    assert brain._captured == []  # cooldown blocks re-greet


def test_entry_greet_no_known_face_no_fire(brain):
    brain._last_stable_identity_name = None
    brain._last_stable_identity_ts = 0.0
    brain.demo_phase = "s2_greet"
    brain._maybe_fire_phase_entry_greet()
    assert brain._captured == []


def test_entry_greet_stale_face_no_fire(brain):
    # churn / expired snapshot: known name but timestamp far outside freshness.
    brain.greet_sitting_window_s = 3.0
    _set_fresh_known_face(brain, "Roy", age_s=999.0)
    brain.demo_phase = "s2_greet"
    brain._maybe_fire_phase_entry_greet()
    assert brain._captured == []


# ---------------------------------------------------------------------------
# T2-5 — gotcha #2 sitting save/restore + max_wait timer + timeout canned-rescue
# ---------------------------------------------------------------------------


def test_greet_sitting_state_machine_auto(brain, monkeypatch):
    """3-stage state machine (precise vars), auto-advance path."""
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet", lambda: None)
    brain.auto_advance_phases = ["s2_greet"]
    brain.greet_require_sitting = True
    assert brain._greet_sitting_pre_s2 is True  # init = default
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_greet")
    assert brain._greet_sitting_pre_s2 is True       # remembered pre-s2 value
    assert brain.greet_require_sitting is False       # face-only inside s2
    brain._set_demo_phase("s3_pose_object")
    assert brain.greet_require_sitting is True         # restored == pre value


def test_greet_sitting_state_machine_manual_not_gated_by_auto(brain, monkeypatch):
    """Manual entry (auto OFF) must ALSO toggle — solves hardlock-on-sitting."""
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet", lambda: None)
    brain.auto_advance_phases = []   # auto OFF
    brain.greet_require_sitting = True
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_greet")   # simulate manual Studio button / param set
    assert brain.greet_require_sitting is False  # s2 not hardlocked on sitting
    brain._set_demo_phase("s3_pose_object")
    assert brain.greet_require_sitting is True


def test_greet_sitting_untouched_when_never_leaves_all(brain):
    """demo_phase never leaves all → greet_require_sitting stays default True."""
    brain.greet_require_sitting = True
    brain.demo_phase = "all"
    brain._set_demo_phase("all")  # no-op
    assert brain.greet_require_sitting is True


def test_phase_max_wait_table_has_five_phases(brain):
    from interaction_executive.brain_node import BrainNode
    for k in ("s1_nav", "s2_greet", "s3_pose_object", "s4_gesture", "s5_safety"):
        assert k in BrainNode._PHASE_MAX_WAIT_S


def test_auto_on_arms_max_wait_timer(brain, monkeypatch):
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet", lambda: None)
    brain.auto_advance_phases = ["s3_pose_object"]
    brain.demo_phase = "all"
    brain._set_demo_phase("s3_pose_object")
    assert brain._phase_wait_timer is not None  # armed


def test_auto_off_does_not_arm_timer(brain, monkeypatch):
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet", lambda: None)
    brain.auto_advance_phases = []  # OFF → no timer (byte-identical)
    brain.demo_phase = "all"
    brain._set_demo_phase("s3_pose_object")
    assert brain._phase_wait_timer is None


def test_phase_switch_cancels_previous_timer(brain, monkeypatch):
    monkeypatch.setattr(brain, "_maybe_fire_phase_entry_greet", lambda: None)
    brain.auto_advance_phases = ["s2_greet", "s3_pose_object"]
    brain.demo_phase = "all"
    brain._set_demo_phase("s2_greet")
    t1 = brain._phase_wait_timer
    assert t1 is not None
    cancelled = {"v": False}
    orig_cancel = t1.cancel
    monkeypatch.setattr(t1, "cancel", lambda: (cancelled.__setitem__("v", True),
                                               orig_cancel())[1])
    brain._set_demo_phase("s3_pose_object")
    # old timer must be cancelled (not crossing phases) and replaced
    assert cancelled["v"] is True
    assert brain._phase_wait_timer is not t1


def test_max_wait_timeout_emits_canned_rescue(brain):
    brain.demo_phase = "s3_pose_object"
    brain._on_phase_max_wait("s3_pose_object")
    assert len(brain._captured) == 1
    assert _say_text_pc(brain._captured[0]) == "記得多喝水、休息一下。"
    assert brain._captured[0]["reason"] == "timeout_canned_rescue"


def test_max_wait_timeout_stale_phase_no_emit(brain):
    """Timer for an old phase must not fire canned after we already switched."""
    brain.demo_phase = "s4_gesture"
    brain._on_phase_max_wait("s3_pose_object")  # stale callback
    assert brain._captured == []


def test_s5_rescue_does_not_call_llm(brain, monkeypatch):
    """s5 rescue is rule-first; must not open chat window / call LLM."""
    # any chat-window creation would land in _chat_timeouts; assert none.
    n_before = len(brain._chat_timeouts)
    brain.demo_phase = "s5_safety"
    brain._on_phase_max_wait("s5_safety")
    assert len(brain._chat_timeouts) == n_before
    assert _say_text_pc(brain._captured[0]) == "為了安全，我不能執行這個動作。"


def _say_text_pc(plan_dict):
    for step in plan_dict.get("steps", []):
        if "text" in step.get("args", {}):
            return step["args"]["text"]
    return None
