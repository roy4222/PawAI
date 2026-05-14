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

        # ── Phase A capability gates (5/2) ──
        # SAFETY priority already returned above; CHAT / TTS / non-NAV-non-MOTION
        # steps fall through these gates unaffected.

        # /state/nav/paused (latched): global pause — block NAV and MOTION steps.
        if world.nav_paused:
            has_nav_or_motion = any(
                step.executor in (ExecutorKind.NAV, ExecutorKind.MOTION)
                for step in plan.steps
            )
            if has_nav_or_motion:
                return ValidationResult(False, "nav_paused")

        has_nav = any(step.executor == ExecutorKind.NAV for step in plan.steps)
        if has_nav:
            if not world.nav_ready:
                return ValidationResult(False, "nav_not_ready")
            if not world.depth_clear:
                return ValidationResult(False, "depth_not_clear")

        # High-risk MOTION (anything not already caught by motion whitelist):
        # require depth_clear=True so we don't move forward into a 0.3m obstacle.
        has_motion = any(step.executor == ExecutorKind.MOTION for step in plan.steps)
        if has_motion and not world.depth_clear:
            return ValidationResult(False, "depth_not_clear_for_motion")

        return ValidationResult(True)
