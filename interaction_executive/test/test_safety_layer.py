"""Tests for safety_layer.py."""
import pytest

from interaction_executive.safety_layer import SAFETY_KEYWORDS_STOP, SafetyLayer
from interaction_executive.skill_contract import (
    ExecutorKind,
    PriorityClass,
    SkillPlan,
    SkillStep,
    build_plan,
)
from interaction_executive.world_state import WorldStateSnapshot


@pytest.fixture
def safety():
    return SafetyLayer()


@pytest.mark.parametrize("keyword", list(SAFETY_KEYWORDS_STOP))
def test_hard_rule_hits_each_keyword(safety, keyword):
    plan = safety.hard_rule(f"請{keyword}一下")
    assert plan is not None
    assert plan.selected_skill == "stop_move"
    assert plan.priority_class == PriorityClass.SAFETY


def test_hard_rule_misses_normal_text(safety):
    assert safety.hard_rule("你好嗎") is None
    assert safety.hard_rule("") is None
    assert safety.hard_rule(None) is None


def test_validate_safety_bypasses_world(safety):
    plan = build_plan("stop_move")
    result = safety.validate(plan, WorldStateSnapshot(obstacle=True, emergency=True))
    assert result.ok


def test_validate_blocks_emergency(safety):
    plan = build_plan("self_introduce")
    result = safety.validate(plan, WorldStateSnapshot(emergency=True))
    assert not result.ok
    assert "emergency" in result.reason


def test_validate_blocks_obstacle_for_motion_skill(safety):
    plan = build_plan("greet_known_person", args={"name": "alice"})
    result = safety.validate(plan, WorldStateSnapshot(obstacle=True))
    assert not result.ok
    assert "obstacle" in result.reason


def test_validate_alert_bypasses_obstacle(safety):
    # Phase A: WorldStateSnapshot defaults are fail-closed
    # (nav_ready/depth_clear=False). ALERT bypasses the obstacle gate, but the
    # MOTION step in fallen_alert still goes through the new depth_clear gate,
    # so we explicitly set depth_clear=True to keep this test about
    # alert-bypasses-obstacle, not alert-bypasses-everything.
    plan = build_plan("fallen_alert")
    result = safety.validate(plan, WorldStateSnapshot(obstacle=True, depth_clear=True))
    assert result.ok


def test_validate_blocks_banned_api(safety, monkeypatch):
    from interaction_executive import skill_contract as sc

    monkeypatch.setitem(sc.MOTION_NAME_MAP, "front_flip", 1030)
    plan = SkillPlan(
        plan_id="t-banned",
        selected_skill="custom",
        steps=[SkillStep(ExecutorKind.MOTION, {"name": "front_flip"})],
        reason="test",
        source="test",
        priority_class=PriorityClass.SKILL,
    )
    result = safety.validate(plan, WorldStateSnapshot())
    assert not result.ok
    assert "banned_api" in result.reason


def test_validate_pass_when_clean(safety):
    # Phase A: a "clean" world for a MOTION skill must explicitly set
    # depth_clear=True (and nav_ready=True if NAV is involved). Defaults are
    # fail-closed by design.
    plan = build_plan("wave_hello")  # post-Phase-B retire of acknowledge_gesture
    result = safety.validate(plan, WorldStateSnapshot(depth_clear=True))
    assert result.ok


# ── Phase A 5/2 capability gates ────────────────────────────────────────────
# /capability/nav_ready, /capability/depth_clear, /state/nav/paused
# All defaults are fail-closed (False) for nav_ready/depth_clear and
# safe-default (False) for nav_paused.


def _nav_plan():
    """Hand-built NAV-step plan.

    We can't call build_plan('go_to_named_place') because that contract is
    statically gated to Phase B (`enabled_when=[("phase_b_pending", ...)]`).
    Construct the SkillPlan directly so these tests stay focused on
    SafetyLayer.validate() behaviour, not on contract registration policy.
    """
    return SkillPlan(
        plan_id="t-nav",
        selected_skill="t_nav",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "goto_named", "args": {}})],
        reason="test",
        source="test",
        priority_class=PriorityClass.SKILL,
    )


def _motion_plan():
    """Build a SAY+MOTION plan via wave_hello (spec §4.1 Active)."""
    return build_plan("wave_hello")


def _chat_plan():
    """Build a SAY-only CHAT plan."""
    return build_plan("chat_reply", args={"text": "hi"})


def test_nav_blocked_when_nav_not_ready(safety):
    plan = _nav_plan()
    # depth_clear=True so it's only nav_ready that fails the gate
    result = safety.validate(plan, WorldStateSnapshot(nav_ready=False, depth_clear=True))
    assert not result.ok
    assert "nav_not_ready" in result.reason


def test_nav_blocked_when_depth_not_clear(safety):
    plan = _nav_plan()
    result = safety.validate(plan, WorldStateSnapshot(nav_ready=True, depth_clear=False))
    assert not result.ok
    assert "depth_not_clear" in result.reason


def test_nav_blocked_when_nav_paused(safety):
    plan = _nav_plan()
    # Capabilities healthy, but global pause is on
    result = safety.validate(
        plan,
        WorldStateSnapshot(nav_ready=True, depth_clear=True, nav_paused=True),
    )
    assert not result.ok
    assert "nav_paused" in result.reason


def test_motion_blocked_when_nav_paused(safety):
    plan = _motion_plan()
    result = safety.validate(
        plan,
        WorldStateSnapshot(depth_clear=True, nav_paused=True),
    )
    assert not result.ok
    assert "nav_paused" in result.reason


def test_safety_priority_passes_even_when_nav_paused(safety):
    """SAFETY skills (e.g. stop_move) are first-class; nav_paused must not block them."""
    plan = build_plan("stop_move")
    result = safety.validate(plan, WorldStateSnapshot(nav_paused=True))
    assert result.ok


def test_chat_passes_when_nav_paused(safety):
    """CHAT plans have only SAY steps — capability gates must not touch them."""
    plan = _chat_plan()
    result = safety.validate(plan, WorldStateSnapshot(nav_paused=True))
    assert result.ok


def test_motion_blocked_when_depth_not_clear(safety):
    plan = _motion_plan()
    # depth_clear default False blocks; everything else clean
    result = safety.validate(plan, WorldStateSnapshot())
    assert not result.ok
    assert "depth_not_clear_for_motion" in result.reason


def test_chat_passes_when_depth_not_clear(safety):
    """Depth gate must not gate CHAT/SAY paths."""
    plan = _chat_plan()
    result = safety.validate(plan, WorldStateSnapshot(depth_clear=False))
    assert result.ok


def test_nav_passes_when_all_capabilities_healthy(safety):
    plan = _nav_plan()
    result = safety.validate(
        plan,
        WorldStateSnapshot(nav_ready=True, depth_clear=True, nav_paused=False),
    )
    assert result.ok


def test_obstacle_gate_still_runs_first_regression(safety):
    """Existing obstacle gate (pre-Phase-A) still fires for SKILL-priority MOTION
    even when capability fields look healthy."""
    plan = _motion_plan()
    result = safety.validate(
        plan,
        WorldStateSnapshot(obstacle=True, depth_clear=True, nav_ready=True),
    )
    assert not result.ok
    assert "obstacle" in result.reason
