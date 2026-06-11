"""Pure machine tests for the Interaction State Machine (Plan ISM Phase 0).

CI-safe: imports only interaction_state (no rclpy). These assertions ENCODE the
master-plan §7 design rules so a later phase can't silently regress them:
priority iron law, confirm-is-not-a-black-hole, perception-never-executes-directly,
watchdog. `now` is always injected — the machine is deterministic.
"""
from interaction_executive.interaction_state import (
    Candidate,
    Decision,
    InteractionPolicy,
    InteractionState,
    InteractionState as S,
    InteractionStateMachine,
    Priority as P,
    TransitionSignal,
    TriggerKind as T,
    Verdict as V,
)


def _cand(kind, prio, **kw):
    return Candidate(kind=kind, priority=prio, source=kw.pop("source", "test"), **kw)


# ── InteractionPolicy: priority iron law + non-black-hole (§3.4 / §3.5) ──────
def test_social_suppressed_while_executing():
    d = InteractionPolicy.evaluate(S.EXECUTING, _cand("object_remark", P.SOCIAL))
    assert d.verdict == V.SUPPRESS and d.reason == "gate:executing"


def test_safety_preempts_executing():
    d = InteractionPolicy.evaluate(S.EXECUTING, _cand("stop", P.SAFETY))
    assert d.verdict == V.PREEMPT and d.next_state == S.SAFETY_HOLD


def test_alert_preempts_executing():
    d = InteractionPolicy.evaluate(S.EXECUTING, _cand("fallen_alert", P.ALERT, skill="fallen_alert"))
    assert d.verdict == V.PREEMPT and d.next_state == S.ALERT_ACTIVE


def test_safety_preempts_alert_but_alert_does_not_preempt_safety():
    # SAFETY_HOLD only yields to SAFETY (§3.4): an alert during a safety hold is suppressed.
    d = InteractionPolicy.evaluate(S.SAFETY_HOLD, _cand("fallen_alert", P.ALERT))
    assert d.verdict == V.SUPPRESS and d.reason == "gate:safety_hold"
    # but ALERT_ACTIVE yields to SAFETY.
    d2 = InteractionPolicy.evaluate(S.ALERT_ACTIVE, _cand("stop", P.SAFETY))
    assert d2.verdict == V.PREEMPT and d2.next_state == S.SAFETY_HOLD


def test_confirm_pending_social_suppressed_not_blackhole():
    # §7.4: a social candidate during confirm gets an explicit suppress-with-reason,
    # never a silent drop.
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("greet", P.SOCIAL))
    assert d.verdict == V.SUPPRESS and d.reason == "gate:confirm_pending"


def test_confirm_pending_ok_confirms():
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("confirm_ok", P.CONFIRM, skill="wiggle"))
    assert d.verdict == V.ACCEPT and d.next_state == S.EXECUTING and d.emit_skill == "wiggle"


def test_confirm_pending_cancel_returns_idle():
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("confirm_cancel", P.CONFIRM))
    assert d.verdict == V.ACCEPT and d.next_state == S.IDLE


def test_explicit_command_supersedes_confirm():
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("chat", P.EXPLICIT, explicit=True))
    assert d.verdict == V.PREEMPT and d.reason == "confirm_superseded"


def test_requires_confirmation_routes_to_confirm_pending():
    d = InteractionPolicy.evaluate(S.IDLE, _cand("gesture_cmd", P.SOCIAL,
                                                 skill="wiggle", requires_confirmation=True))
    assert d.verdict == V.ACCEPT and d.next_state == S.CONFIRM_PENDING


def test_idle_accepts_social():
    d = InteractionPolicy.evaluate(S.IDLE, _cand("greet", P.SOCIAL, skill="greet_known_person"))
    assert d.verdict == V.ACCEPT and d.next_state == S.SPEAKING


def test_speaking_queues_social():
    d = InteractionPolicy.evaluate(S.SPEAKING, _cand("object_remark", P.SOCIAL))
    assert d.verdict == V.QUEUE and "speaking" in d.reason


def test_speaking_suppresses_confirm_priority():
    # confirm-priority candidate while merely speaking (not confirm_pending) → suppressed.
    d = InteractionPolicy.evaluate(S.SPEAKING, _cand("confirm_ok", P.CONFIRM))
    assert d.verdict == V.SUPPRESS and d.reason == "gate:speaking"


def test_perception_social_never_enters_executing_directly():
    # §3.3 source trust: a social perception candidate can never reach EXECUTING.
    d = InteractionPolicy.evaluate(S.IDLE, _cand("object_remark", P.SOCIAL))
    assert d.next_state != S.EXECUTING


def test_explicit_with_skill_executes():
    d = InteractionPolicy.evaluate(S.IDLE, _cand("gesture_cmd", P.EXPLICIT,
                                                 explicit=True, skill="stretch"))
    assert d.verdict == V.ACCEPT and d.next_state == S.EXECUTING and d.emit_skill == "stretch"


# ── InteractionStateMachine: transition drivers + watchdog (§3.2 / §3.6) ─────
def test_skill_started_enters_executing():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "priority_class": 4,
                                                     "plan_id": "p1", "timeout_s": 10.0}))
    assert m.state == InteractionState.EXECUTING


def test_alert_priority_skill_enters_alert_active():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED",
                                                     "priority_class": int(P.ALERT),
                                                     "plan_id": "a1", "timeout_s": 8.0}))
    assert m.state == InteractionState.ALERT_ACTIVE


def test_skill_terminal_returns_idle():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1",
                                                     "timeout_s": 10.0}))
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "COMPLETED", "plan_id": "p1"}))
    assert m.state == InteractionState.IDLE


def test_terminal_for_wrong_plan_id_ignored():
    # A stale terminal for a different plan must not clear the active one.
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1",
                                                     "timeout_s": 10.0}))
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "COMPLETED", "plan_id": "OTHER"}))
    assert m.state == InteractionState.EXECUTING


def test_watchdog_timeout_to_recovery():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1",
                                                     "timeout_s": 5.0}))
    d = m.tick(now=6.0)
    assert m.state == InteractionState.IDLE
    assert d is not None and "watchdog_timeout:executing" in d.reason


def test_watchdog_no_premature_fire():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1",
                                                     "timeout_s": 5.0}))
    assert m.tick(now=4.9) is None and m.state == InteractionState.EXECUTING


def test_timeout_zero_means_no_deadline():
    # Regression: timeout_s=0 must mean "no watchdog", not "deadline == now".
    m = InteractionStateMachine(now=5.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1",
                                                     "timeout_s": 0}), now=5.0)
    assert m.deadline is None
    assert m.tick(now=99.0) is None


def test_confirm_timeout_30s():
    m = InteractionStateMachine(now=0.0)
    m.propose(Candidate(kind="gesture_cmd", priority=P.SOCIAL, source="gesture",
                        skill="wiggle", requires_confirmation=True), now=0.0)
    assert m.state == InteractionState.CONFIRM_PENDING and m.deadline == 30.0
    m.tick(now=31.0)
    assert m.state == InteractionState.IDLE


def test_propose_confirm_ok_transitions_executing():
    m = InteractionStateMachine(now=0.0, state=InteractionState.CONFIRM_PENDING, deadline=30.0)
    d = m.propose(Candidate(kind="confirm_ok", priority=P.CONFIRM, source="gesture",
                            skill="wiggle"), now=1.0)
    assert d.verdict == V.ACCEPT and m.state == InteractionState.EXECUTING


def test_tts_ack_speaking_then_idle():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.TTS_ACK, {"event": "start"}))
    assert m.state == InteractionState.SPEAKING
    m.apply_signal(TransitionSignal(T.TTS_ACK, {"event": "end"}))
    assert m.state == InteractionState.IDLE


def test_operator_reset_returns_idle_and_clears_plan():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1",
                                                     "timeout_s": 10.0}))
    m.apply_signal(TransitionSignal(T.OPERATOR, {"op": "reset"}))
    assert m.state == InteractionState.IDLE
    # a stale terminal afterward must not re-affect state (plan id was cleared)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "COMPLETED", "plan_id": "p1"}))
    assert m.state == InteractionState.IDLE


def test_history_records_transitions_and_is_bounded():
    m = InteractionStateMachine(now=0.0)
    for i in range(80):
        ev = "start" if i % 2 == 0 else "end"
        m.apply_signal(TransitionSignal(T.TTS_ACK, {"event": ev}), now=float(i))
    assert len(m.history) <= 64
    ts, frm, to, trig = m.history[-1]
    assert frm in {s.value for s in InteractionState} and to in {s.value for s in InteractionState}


def test_6_9_replay_alert_stuck_then_social_suppressed_not_blackhole():
    """6/9 regression net (§7.8): an ALERT plan that never returns terminal must
    NOT black-hole subsequent social candidates — they get suppress-with-reason,
    and the watchdog eventually frees the machine."""
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED",
                                                     "priority_class": int(P.ALERT),
                                                     "plan_id": "stranger1", "timeout_s": 10.0}))
    assert m.state == InteractionState.ALERT_ACTIVE
    # cup + greet arrive while alert is stuck → each gets an explicit suppress.
    for kind in ("object_remark", "greet"):
        d = m.propose(_cand(kind, P.SOCIAL), now=2.0)
        assert d.verdict == V.SUPPRESS and d.reason == "gate:alert_active"
    # watchdog frees it (no terminal ever arrived).
    m.tick(now=11.0)
    assert m.state == InteractionState.IDLE
