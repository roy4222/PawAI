"""Unit tests for AttentionMachine — fake-clock, no ROS2 dependency.

All tests inject `now` explicitly so no real-time sleep is needed.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P2-1
Plan: docs/pawai-brain/plans/2026-05-12-attention-policy.md Task D-1
"""
from __future__ import annotations

import pytest

from interaction_executive.attention_machine import AttentionMachine, AttentionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_am(**kwargs) -> AttentionMachine:
    """Create AttentionMachine with default thresholds (overridable)."""
    defaults = dict(
        dwell_s=1.5,
        face_lost_s=3.0,
        quiet_s=8.0,
        engaged_distance_m=1.6,
        face_stable_s=0.5,
    )
    defaults.update(kwargs)
    return AttentionMachine(**defaults)


def tick(am: AttentionMachine, now: float, face=True, dist=None, plan=False, speech=False):
    """Shorthand tick call."""
    return am.tick(now=now, face_visible=face, distance_m=dist, active_plan=plan, speech_intent=speech)


# ---------------------------------------------------------------------------
# T1: IDLE → NOTICED on face stable ≥ face_stable_s
# ---------------------------------------------------------------------------

def test_idle_to_noticed_on_stable_face():
    """Face must be visible for face_stable_s before leaving IDLE."""
    am = make_am(face_stable_s=0.5)

    # t=0: face appears — still IDLE (not stable yet)
    state = tick(am, now=0.0, face=True)
    assert state == AttentionState.IDLE, "Should stay IDLE before face_stable_s"

    # t=0.4: still not long enough
    state = tick(am, now=0.4, face=True)
    assert state == AttentionState.IDLE

    # t=0.5: exactly at threshold → NOTICED
    state = tick(am, now=0.5, face=True)
    assert state == AttentionState.NOTICED


# ---------------------------------------------------------------------------
# T2: NOTICED → IDLE on face lost ≥ face_lost_s
# ---------------------------------------------------------------------------

def test_noticed_to_idle_on_face_lost():
    """Person walks away → NOTICED → IDLE after face_lost_s."""
    am = make_am(face_stable_s=0.5, face_lost_s=3.0)

    # Reach NOTICED
    tick(am, now=0.0, face=True)
    tick(am, now=0.5, face=True)
    assert am.state == AttentionState.NOTICED

    # Face disappears at t=1.0 (last seen t=0.5)
    tick(am, now=1.0, face=False)
    assert am.state == AttentionState.NOTICED  # only 0.5s lost — not enough

    # At t=3.4, it's been exactly 2.9s since last seen (t=0.5) — not yet 3.0s
    tick(am, now=3.4, face=False)
    assert am.state == AttentionState.NOTICED  # 2.9s lost, threshold is 3.0s

    # At t=3.6, it's been 3.1s since last seen → IDLE
    tick(am, now=3.6, face=False)
    assert am.state == AttentionState.IDLE, "3s+ face lost should → IDLE"


# ---------------------------------------------------------------------------
# T3: NOTICED → ENGAGED on dwell ≥ dwell_s at distance ≤ engaged_distance_m
# ---------------------------------------------------------------------------

def test_noticed_to_engaged_on_dwell():
    """Person moves close and stays → NOTICED → ENGAGED."""
    am = make_am(face_stable_s=0.5, dwell_s=1.5, engaged_distance_m=1.6)

    # Reach NOTICED
    tick(am, now=0.0, face=True)
    tick(am, now=0.5, face=True)
    assert am.state == AttentionState.NOTICED

    # Person enters distance threshold — dwell clock starts at t=0.5
    tick(am, now=0.5, face=True, dist=1.4)   # starts dwell at t=0.5
    tick(am, now=1.5, face=True, dist=1.4)   # 1.0s dwell — not yet
    assert am.state == AttentionState.NOTICED

    tick(am, now=2.0, face=True, dist=1.4)   # 1.5s dwell → ENGAGED
    assert am.state == AttentionState.ENGAGED


def test_noticed_no_engage_if_too_far():
    """Person visible but beyond engaged_distance_m → stays NOTICED."""
    am = make_am(face_stable_s=0.5, dwell_s=1.5, engaged_distance_m=1.6)

    tick(am, now=0.0, face=True)
    tick(am, now=0.5, face=True)
    assert am.state == AttentionState.NOTICED

    # Person far away — no dwell
    for t in [1.0, 2.0, 3.0, 4.0]:
        tick(am, now=t, face=True, dist=2.0)
    assert am.state == AttentionState.NOTICED


# ---------------------------------------------------------------------------
# T4: ENGAGED → INTERACTING on active_plan or speech_intent
# ---------------------------------------------------------------------------

def test_engaged_to_interacting_on_plan():
    """Active plan while ENGAGED → INTERACTING."""
    am = make_am(face_stable_s=0.1, dwell_s=0.5, engaged_distance_m=1.6)

    tick(am, now=0.0, face=True, dist=1.0)
    tick(am, now=0.1, face=True, dist=1.0)
    tick(am, now=0.6, face=True, dist=1.0)
    assert am.state == AttentionState.ENGAGED

    tick(am, now=0.7, face=True, dist=1.0, plan=True)
    assert am.state == AttentionState.INTERACTING


def test_engaged_to_interacting_on_speech():
    """Speech intent while ENGAGED → INTERACTING."""
    am = make_am(face_stable_s=0.1, dwell_s=0.5, engaged_distance_m=1.6)

    tick(am, now=0.0, face=True, dist=1.0)
    tick(am, now=0.1, face=True, dist=1.0)
    tick(am, now=0.6, face=True, dist=1.0)
    assert am.state == AttentionState.ENGAGED

    tick(am, now=0.7, face=True, speech=True)
    assert am.state == AttentionState.INTERACTING


# ---------------------------------------------------------------------------
# T5: INTERACTING → ENGAGED on plan done + quiet_s
# ---------------------------------------------------------------------------

def test_interacting_to_engaged_after_quiet():
    """Plan completes + quiet_s elapses → INTERACTING → ENGAGED."""
    am = make_am(face_stable_s=0.1, dwell_s=0.5, engaged_distance_m=1.6, quiet_s=8.0)

    # Reach INTERACTING
    tick(am, now=0.0, face=True, dist=1.0)
    tick(am, now=0.1, face=True, dist=1.0)
    tick(am, now=0.6, face=True, dist=1.0)
    tick(am, now=0.7, face=True, plan=True)
    assert am.state == AttentionState.INTERACTING

    # Plan ends at t=2.0
    tick(am, now=2.0, face=True, plan=False)
    tick(am, now=9.0, face=True, plan=False)  # 7s quiet — not yet
    assert am.state == AttentionState.INTERACTING

    tick(am, now=10.1, face=True, plan=False)  # 8.1s quiet → ENGAGED
    assert am.state == AttentionState.ENGAGED


# ---------------------------------------------------------------------------
# T6: INTERACTING → IDLE on face lost ≥ face_lost_s
# ---------------------------------------------------------------------------

def test_interacting_to_idle_on_face_lost():
    """Face disappears while INTERACTING → IDLE after face_lost_s."""
    am = make_am(face_stable_s=0.1, dwell_s=0.5, engaged_distance_m=1.6, face_lost_s=3.0)

    # Reach INTERACTING
    tick(am, now=0.0, face=True, dist=1.0)
    tick(am, now=0.1, face=True, dist=1.0)
    tick(am, now=0.6, face=True, dist=1.0)
    tick(am, now=0.7, face=True, plan=True)
    assert am.state == AttentionState.INTERACTING

    # Face disappears at t=1.0
    tick(am, now=1.0, face=False, plan=False)
    tick(am, now=3.5, face=False, plan=False)
    assert am.state == AttentionState.NOTICED or am.state == AttentionState.INTERACTING
    tick(am, now=4.0, face=False, plan=False)  # 3s since t=1.0 → IDLE
    assert am.state == AttentionState.IDLE


# ---------------------------------------------------------------------------
# T7: NOTICED → INTERACTING shortcut on plan/speech (walk-over-to-OK scenario)
# ---------------------------------------------------------------------------

def test_noticed_to_interacting_direct_on_speech():
    """Speech intent in NOTICED (user spoke while walking over) → INTERACTING directly."""
    am = make_am(face_stable_s=0.5, face_lost_s=3.0)

    tick(am, now=0.0, face=True)
    tick(am, now=0.5, face=True)
    assert am.state == AttentionState.NOTICED

    tick(am, now=0.6, face=True, speech=True)
    assert am.state == AttentionState.INTERACTING


# ---------------------------------------------------------------------------
# T8: state_since timestamp tracks transition time correctly
# ---------------------------------------------------------------------------

def test_state_since_tracks_transition():
    """state_since should reflect when each transition happened."""
    am = make_am(face_stable_s=0.5, dwell_s=1.5, engaged_distance_m=1.6)

    t_idle = 0.0
    am.reset(now=t_idle)
    assert am.state == AttentionState.IDLE
    assert am.state_since == t_idle

    tick(am, now=0.0, face=True)
    t_noticed = 0.5
    tick(am, now=t_noticed, face=True)
    assert am.state == AttentionState.NOTICED
    assert am.state_since == t_noticed

    tick(am, now=0.6, face=True, dist=1.0)  # start dwell
    t_engaged = 2.1  # 0.6 + 1.5s dwell
    tick(am, now=t_engaged, face=True, dist=1.0)
    assert am.state == AttentionState.ENGAGED
    assert am.state_since == t_engaged


# ---------------------------------------------------------------------------
# T9: IDLE face flicker — brief face blink doesn't cause NOTICED
# ---------------------------------------------------------------------------

def test_idle_face_flicker_does_not_trigger_noticed():
    """Very brief face (< face_stable_s) is ignored — no NOTICED."""
    am = make_am(face_stable_s=0.5)

    tick(am, now=0.0, face=True)
    # Face gone before 0.5s
    tick(am, now=0.3, face=False)
    tick(am, now=0.4, face=False)
    assert am.state == AttentionState.IDLE


# ---------------------------------------------------------------------------
# T10: reset() hard-resets to IDLE
# ---------------------------------------------------------------------------

def test_reset_returns_to_idle():
    """reset() should bring any state back to IDLE."""
    am = make_am(face_stable_s=0.1, dwell_s=0.5, engaged_distance_m=1.6)

    tick(am, now=0.0, face=True, dist=1.0)
    tick(am, now=0.1, face=True, dist=1.0)
    tick(am, now=0.6, face=True, dist=1.0, plan=True)
    assert am.state == AttentionState.INTERACTING

    am.reset(now=10.0)
    assert am.state == AttentionState.IDLE
    assert am.state_since == 10.0
