"""Deterministic safety guards for PawAI Brain MVS."""
from __future__ import annotations

from dataclasses import dataclass

from .skill_contract import (
    BANNED_API_IDS,
    MOTION_NAME_MAP,
    ExecutorKind,
    PriorityClass,
    SkillPlan,
    build_plan,
)
from .world_state import WorldStateSnapshot


SAFETY_KEYWORDS_STOP = ("停", "stop", "煞車", "暫停", "緊急")


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


class SafetyLayer:
    """Pure-Python safety layer; ROS2-independent."""

    def hard_rule(self, transcript: str | None) -> SkillPlan | None:
        if not transcript:
            return None
        text = transcript.strip().lower()
        for keyword in SAFETY_KEYWORDS_STOP:
            if keyword in text:
                return build_plan(
                    "stop_move",
                    source="rule:safety_keyword",
                    reason=f"keyword:{keyword}",
                )
        return None

    def validate(self, plan: SkillPlan, world: WorldStateSnapshot) -> ValidationResult:
        if plan.priority_class == PriorityClass.SAFETY:
            return ValidationResult(True)

        for step in plan.steps:
            if step.executor == ExecutorKind.MOTION:
                name = step.args.get("name")
                api_id = MOTION_NAME_MAP.get(name)
                if api_id is None:
                    return ValidationResult(False, f"unknown_motion:{name!r}")
                if api_id in BANNED_API_IDS:
                    return ValidationResult(False, f"banned_api:{api_id}")

        if world.emergency:
            return ValidationResult(False, "emergency_active")

        if plan.priority_class != PriorityClass.ALERT and world.obstacle:
            has_motion_or_nav = any(
                step.executor in (ExecutorKind.MOTION, ExecutorKind.NAV)
                for step in plan.steps
            )
            if has_motion_or_nav:
                return ValidationResult(False, "obstacle_active")

        if not world.nav_safe:
            has_nav = any(step.executor == ExecutorKind.NAV for step in plan.steps)
            if has_nav:
                return ValidationResult(False, "nav_unsafe")

        return ValidationResult(True)
