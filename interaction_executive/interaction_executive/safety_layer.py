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

# 2026-05-23: 5/27 demo § 5 — 危險動作關鍵字偵測
# 對齊 ADR-0001 非接觸式定位 + 5/27 spec § 5 設計：
# 使用者語音請求危險動作 → SafetyLayer 主動拒絕 → TTS + Studio BLOCKED_BY_SAFETY 紅色
# LLM whitelist 完全不動 / BANNED_API_IDS 不動 / 危險動作不可能被執行
UNSAFE_KEYWORDS_REJECT = (
    "翻跟斗", "翻跟头", "後空翻", "后空翻", "前空翻", "倒立",
    "backflip", "front flip", "frontflip", "handstand",
)
UNSAFE_REJECT_TEXT = "這個動作不安全，我不能執行。"


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

    def unsafe_request(self, transcript: str | None) -> tuple[SkillPlan, SkillPlan] | None:
        """偵測危險動作關鍵字 → 返回 (TTS 拒絕 plan, 視覺化 BLOCKED plan).

        兩個 plan 分開的設計理由:
        - SafetyLayer.validate() 對 banned MOTION step 整個 plan 原子拒絕
        - 如果 SAY + MOTION 包同一 plan,SAY 不會播 (整個 plan 被 reject)
        - 所以拆兩個:
          1. say_canned → TTS 真的播出「這個動作不安全」(對應 ADR-0001)
          2. request_backflip (只含 MOTION step) → validate 必然 reject banned_api:1301
             → SkillResult emit BLOCKED_BY_SAFETY → Studio chat-panel.tsx:543 紅色 highlight

        對齊 5/27 spec § 5 設計原則:
        - LLM whitelist 完全不動 (LLM 不會獨立生成 backflip plan)
        - BANNED_API_IDS 不動 (execution 攔截層仍 100% 阻擋)
        - request_backflip skill 只能由本 method 觸發,不會被 LLM 路徑產生
        """
        if not transcript:
            return None
        text = transcript.strip().lower()
        for keyword in UNSAFE_KEYWORDS_REJECT:
            if keyword in text:
                say_plan = build_plan(
                    "say_canned",
                    args={"text": UNSAFE_REJECT_TEXT},
                    source="rule:safety_unsafe_action",
                    reason=f"unsafe_keyword:{keyword}",
                )
                motion_plan = build_plan(
                    "request_backflip",
                    source="rule:safety_unsafe_action_visual",
                    reason=f"unsafe_keyword:{keyword}",
                )
                return (say_plan, motion_plan)
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
