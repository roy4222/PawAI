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
    plan = build_plan("fallen_alert")
    result = safety.validate(plan, WorldStateSnapshot(obstacle=True))
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
    plan = build_plan("acknowledge_gesture", args={"gesture": "wave"})
    result = safety.validate(plan, WorldStateSnapshot())
    assert result.ok
