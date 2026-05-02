"""Skill-first PawAI Brain core types.

Spec: docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md section 3
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Literal


class ExecutorKind(str, Enum):
    SAY = "say"
    MOTION = "motion"
    NAV = "nav"


class PriorityClass(IntEnum):
    SAFETY = 0
    ALERT = 1
    SEQUENCE = 2
    SKILL = 3
    CHAT = 4


class SkillResultStatus(str, Enum):
    ACCEPTED = "accepted"
    STARTED = "started"
    STEP_STARTED = "step_started"
    STEP_SUCCESS = "step_success"
    STEP_FAILED = "step_failed"
    COMPLETED = "completed"
    ABORTED = "aborted"
    BLOCKED_BY_SAFETY = "blocked_by_safety"


@dataclass
class SkillStep:
    executor: ExecutorKind
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillContract:
    name: str
    steps: list[SkillStep]
    priority_class: PriorityClass
    safety_requirements: list[str] = field(default_factory=list)
    cooldown_s: float = 0.0
    timeout_s: float = 8.0
    fallback_skill: str | None = None
    description: str = ""
    args_schema: dict[str, Any] = field(default_factory=dict)
    ui_style: Literal["normal", "alert", "safety"] = "normal"
    static_enabled: bool = True
    enabled_when: list = field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"


@dataclass
class SkillPlan:
    plan_id: str
    selected_skill: str
    steps: list[SkillStep]
    reason: str
    source: str
    priority_class: PriorityClass
    session_id: str | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class SkillResult:
    plan_id: str
    step_index: int | None
    status: SkillResultStatus
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


def new_plan_id(prefix: str = "p") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


MOTION_NAME_MAP: dict[str, int] = {
    "hello": 1016,
    "stop_move": 1003,
    "sit": 1009,
    "stand": 1004,
    "content": 1020,
    "balance_stand": 1002,
}

BANNED_API_IDS: set[int] = {1030, 1031, 1301}


SKILL_REGISTRY: dict[str, SkillContract] = {
    "chat_reply": SkillContract(
        name="chat_reply",
        steps=[SkillStep(ExecutorKind.SAY, {"text": ""})],
        priority_class=PriorityClass.CHAT,
        description="LLM-sourced free-form chat reply.",
        args_schema={"text": "string"},
    ),
    "say_canned": SkillContract(
        name="say_canned",
        steps=[SkillStep(ExecutorKind.SAY, {"text": ""})],
        priority_class=PriorityClass.CHAT,
        description="Brain rule fallback canned line.",
        args_schema={"text": "string"},
    ),
    "stop_move": SkillContract(
        name="stop_move",
        steps=[SkillStep(ExecutorKind.MOTION, {"name": "stop_move"})],
        priority_class=PriorityClass.SAFETY,
        description="Emergency stop. Safety hard-rule path.",
        ui_style="safety",
    ),
    "acknowledge_gesture": SkillContract(
        name="acknowledge_gesture",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "content"}),
            SkillStep(ExecutorKind.SAY, {"text": "收到"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=3.0,
        description="Generic gesture acknowledgement.",
        args_schema={"gesture": "string"},
    ),
    "greet_known_person": SkillContract(
        name="greet_known_person",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text_template": "歡迎回來，{name}"}),
            SkillStep(ExecutorKind.MOTION, {"name": "hello"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=20.0,
        description="Personalised greeting for a registered face.",
        args_schema={"name": "string"},
    ),
    "self_introduce": SkillContract(
        name="self_introduce",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "我是 PawAI，你的居家互動機器狗"}),
            SkillStep(ExecutorKind.MOTION, {"name": "hello"}),
            SkillStep(ExecutorKind.SAY, {"text": "平常我會待在你身邊，等你叫我"}),
            SkillStep(ExecutorKind.MOTION, {"name": "sit"}),
            SkillStep(ExecutorKind.SAY, {"text": "你可以用聲音、手勢，或直接跟我互動"}),
            SkillStep(ExecutorKind.MOTION, {"name": "content"}),
            SkillStep(ExecutorKind.SAY, {"text": "我也會注意周圍發生的事情"}),
            SkillStep(ExecutorKind.MOTION, {"name": "stand"}),
            SkillStep(ExecutorKind.SAY, {"text": "如果看到陌生人，我會提醒你提高注意"}),
            SkillStep(ExecutorKind.MOTION, {"name": "balance_stand"}),
        ],
        priority_class=PriorityClass.SEQUENCE,
        cooldown_s=60.0,
        timeout_s=60.0,
        description="Self-introduction sequence.",
    ),
    "stranger_alert": SkillContract(
        name="stranger_alert",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "偵測到不認識的人，請注意"})],
        priority_class=PriorityClass.ALERT,
        cooldown_s=30.0,
        description="Unknown face stable for 3 seconds. MVS: say only.",
        ui_style="alert",
    ),
    "fallen_alert": SkillContract(
        name="fallen_alert",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "stop_move"}),
            SkillStep(ExecutorKind.SAY, {"text": "偵測到有人跌倒，請確認是否需要協助"}),
        ],
        priority_class=PriorityClass.ALERT,
        cooldown_s=15.0,
        description="Human fallen detected. Stop the dog itself, then say alert.",
        ui_style="alert",
    ),
    "go_to_named_place": SkillContract(
        name="go_to_named_place",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "goto_named", "args": {}})],
        priority_class=PriorityClass.SKILL,
        description="Navigate to a named place. Phase B integration pending.",
        static_enabled=True,
        enabled_when=[("phase_b_pending", "Phase B 才整合 nav_capability")],
        risk_level="medium",
        args_schema={"place_id": "string"},
    ),
}


def _phase_a_enabled_when_blocks(contract: SkillContract) -> list[str]:
    """Return Phase A sentinel block reasons.

    Phase B will replace tuple sentinels with real predicates. In A1, tuple
    sentinels intentionally block plan construction for known-but-unavailable
    capabilities such as navigation.
    """
    reasons: list[str] = []
    for item in contract.enabled_when:
        if isinstance(item, tuple) and len(item) == 2:
            reasons.append(str(item[1]))
    return reasons


def build_plan(
    skill_name: str,
    args: dict[str, Any] | None = None,
    source: str = "rule",
    reason: str = "",
    session_id: str | None = None,
) -> SkillPlan:
    args = args or {}
    contract = SKILL_REGISTRY[skill_name]
    if not contract.static_enabled:
        raise ValueError(f"Skill {skill_name!r} is statically disabled")
    block_reasons = _phase_a_enabled_when_blocks(contract)
    if block_reasons:
        raise ValueError(f"Skill {skill_name!r} blocked: {'; '.join(block_reasons)}")

    resolved_steps: list[SkillStep] = []
    for step in contract.steps:
        step_args = dict(step.args)
        for key in list(step_args.keys()):
            if key.endswith("_template") and isinstance(step_args[key], str):
                target_key = key[: -len("_template")]
                template = step_args.pop(key)
                try:
                    step_args[target_key] = template.format(**args)
                except KeyError:
                    step_args[target_key] = template
        if contract.name in ("chat_reply", "say_canned") and "text" in args:
            step_args["text"] = args["text"]
        resolved_steps.append(SkillStep(step.executor, step_args))

    return SkillPlan(
        plan_id=new_plan_id(),
        selected_skill=skill_name,
        steps=resolved_steps,
        reason=reason or f"build_plan:{skill_name}",
        source=source,
        priority_class=contract.priority_class,
        session_id=session_id,
    )
