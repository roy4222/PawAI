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
