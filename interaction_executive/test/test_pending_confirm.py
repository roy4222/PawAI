"""Tests for PendingConfirm state machine.

Spec: docs/pawai-brain/specs/2026-05-04-phase-b-implementation-notes.md §2
"""
import pytest

from interaction_executive.pending_confirm import (
    ConfirmOutcomeKind,
    ConfirmState,
    PendingConfirm,
)


@pytest.fixture
def pc():
    # default timeout 5s, stable 0.5s, ok gesture "ok"
    return PendingConfirm()


# ---- request_confirm ------------------------------------------------------


def test_initial_state_is_idle(pc):
    assert pc.state == ConfirmState.IDLE
    assert pc.pending_skill is None


def test_request_confirm_enters_pending(pc):
    out = pc.request_confirm("wiggle", {"intensity": 1}, now=100.0)
    assert out.kind == ConfirmOutcomeKind.PENDING
    assert pc.state == ConfirmState.PENDING
    assert pc.pending_skill == "wiggle"
    assert pc.pending_args == {"intensity": 1}


def test_request_confirm_replaces_prior(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    pc.request_confirm("stretch", {"name": "Roy"}, now=101.0)
    assert pc.pending_skill == "stretch"
    assert pc.pending_args == {"name": "Roy"}


# ---- timeout --------------------------------------------------------------


def test_tick_within_timeout_stays_pending(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    out = pc.tick(now=104.9, current_gesture=None)
    assert out.kind == ConfirmOutcomeKind.PENDING
    assert pc.state == ConfirmState.PENDING


def test_timeout_just_at_boundary_still_pending(pc):
    # boundary: now - started_at == timeout_s should NOT cancel (strict >)
    pc.request_confirm("wiggle", {}, now=100.0)
    out = pc.tick(now=105.0, current_gesture=None)
    assert out.kind == ConfirmOutcomeKind.PENDING


def test_timeout_past_boundary_cancels(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    out = pc.tick(now=105.01, current_gesture=None)
    assert out.kind == ConfirmOutcomeKind.CANCELLED
    assert out.reason == "timeout"
    assert pc.state == ConfirmState.IDLE


# ---- OK stability ---------------------------------------------------------


def test_single_ok_tick_below_stable_window_stays_pending(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    out = pc.tick(now=100.1, current_gesture="ok")
    assert out.kind == ConfirmOutcomeKind.PENDING
    assert pc.state == ConfirmState.PENDING


def test_ok_stable_05s_confirms(pc):
    pc.request_confirm("wiggle", {"a": 1}, now=100.0)
    pc.tick(now=100.0, current_gesture="ok")           # ok_stable_since = 100.0
    out = pc.tick(now=100.5, current_gesture="ok")     # exactly 0.5s
    assert out.kind == ConfirmOutcomeKind.CONFIRMED
    assert out.skill == "wiggle"
    assert out.args == {"a": 1}
    assert pc.state == ConfirmState.IDLE


def test_ok_then_blank_resets_stability(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    pc.tick(now=100.0, current_gesture="ok")
    pc.tick(now=100.3, current_gesture=None)           # break streak
    pc.tick(now=100.4, current_gesture="ok")           # restart at 100.4
    out = pc.tick(now=100.6, current_gesture="ok")     # only 0.2s, not enough
    assert out.kind == ConfirmOutcomeKind.PENDING


def test_ok_case_and_whitespace_normalized(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    pc.tick(now=100.0, current_gesture="  OK  ")
    out = pc.tick(now=100.5, current_gesture="Ok")
    assert out.kind == ConfirmOutcomeKind.CONFIRMED


# ---- wrong gesture --------------------------------------------------------


def test_different_gesture_cancels(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    out = pc.tick(now=100.2, current_gesture="palm")
    assert out.kind == ConfirmOutcomeKind.CANCELLED
    assert out.reason == "different_gesture"
    assert pc.state == ConfirmState.IDLE


def test_wrong_gesture_after_partial_ok_cancels(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    pc.tick(now=100.0, current_gesture="ok")
    out = pc.tick(now=100.2, current_gesture="thumbs_up")
    assert out.kind == ConfirmOutcomeKind.CANCELLED
    assert out.reason == "different_gesture"


# ---- idle no-op -----------------------------------------------------------


def test_tick_in_idle_is_noop_pending(pc):
    out = pc.tick(now=999.0, current_gesture="ok")
    assert out.kind == ConfirmOutcomeKind.PENDING
    assert pc.state == ConfirmState.IDLE


# ---- manual cancel --------------------------------------------------------


def test_manual_cancel_when_pending(pc):
    pc.request_confirm("wiggle", {}, now=100.0)
    out = pc.cancel("user_aborted")
    assert out.kind == ConfirmOutcomeKind.CANCELLED
    assert out.reason == "user_aborted"
    assert pc.state == ConfirmState.IDLE


def test_manual_cancel_when_idle(pc):
    out = pc.cancel()
    assert out.kind == ConfirmOutcomeKind.CANCELLED
    assert out.reason == "not_pending"


# ---- ctor validation ------------------------------------------------------


def test_invalid_timeout_rejected():
    with pytest.raises(ValueError):
        PendingConfirm(timeout_s=0)
    with pytest.raises(ValueError):
        PendingConfirm(timeout_s=-1)


def test_invalid_stable_rejected():
    with pytest.raises(ValueError):
        PendingConfirm(stable_s=-0.1)


def test_custom_ok_gesture_works():
    pc = PendingConfirm(ok_gesture="thumbs_up")
    pc.request_confirm("wiggle", {}, now=100.0)
    pc.tick(now=100.0, current_gesture="thumbs_up")
    out = pc.tick(now=100.5, current_gesture="thumbs_up")
    assert out.kind == ConfirmOutcomeKind.CONFIRMED
