"""Skill-first PawAI Brain core types.

Spec:
  - docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md §3
  - docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md §4 (Skill Inventory v1)
  - docs/pawai-brain/specs/2026-05-04-phase-b-implementation-notes.md (bucket semantics)

Bucket vs static_enabled vs enabled_when:
  - bucket: 產品/展示分類，Studio 讀（active=enabled、hidden=grayed、disabled=hidden-or-灰、retired=不顯示）
  - static_enabled: 全局開關，Brain 讀（False → build_plan 直接拒）
  - enabled_when: runtime 條件 sentinel，Brain 讀（如 Nav Gate / Depth Gate / robot_stable）
  三者不互相覆蓋。
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


SkillBucket = Literal["active", "hidden", "disabled", "retired"]


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
    bucket: SkillBucket = "active"

    # Phase A.6 demo metadata
    display_name: str = ""
    demo_status_baseline: Literal[
        "available_execute", "available_confirm",
        "explain_only", "studio_only", "disabled",
    ] = "disabled"
    demo_value: Literal["high", "medium", "low"] = "low"
    demo_reason: str = ""


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
    "stretch": 1017,
    "wiggle_hip": 1029,
    "scrape": 1029,
}

BANNED_API_IDS: set[int] = {1030, 1031, 1301}


# ---------------------------------------------------------------------------
# SKILL_REGISTRY — Phase B v1（spec §4.1）
#
# Active   (17): stop_move, system_pause, show_status, chat_reply, say_canned,
#                self_introduce, wave_hello, wiggle, stretch, sit_along,
#                careful_remind, greet_known_person, stranger_alert,
#                object_remark, nav_demo_point, approach_person, fallen_alert
# Hidden   (5):  enter_mute_mode, enter_listen_mode, akimbo_react,
#                knee_kneel_react, patrol_route
# Disabled (4):  follow_me, follow_person, dance, go_to_named_place
# Retired  (1):  acknowledge_gesture
# Total: 27 entries (spec §4.1 表格寫 26 為 typo，採實際列出的 27)
#
# audio tag 預埋（spec §4.3）：21 條非動態 say_template 預埋
# 不預埋（5 LLM-動態）：chat_reply, greet_known_person, object_remark,
#                       stranger_alert, fallen_alert
# ---------------------------------------------------------------------------

SKILL_REGISTRY: dict[str, SkillContract] = {
    # ---- Safety ----
    "stop_move": SkillContract(
        name="stop_move",
        steps=[SkillStep(ExecutorKind.MOTION, {"name": "stop_move"})],
        priority_class=PriorityClass.SAFETY,
        description="Emergency stop. Safety hard-rule path.",
        ui_style="safety",
        bucket="active",
        display_name="緊急停止",
        demo_status_baseline="available_execute",
        demo_value="high",
        demo_reason="安全短路，不會被 LLM 提案",
    ),
    "system_pause": SkillContract(
        name="system_pause",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "stop_move"}),
            SkillStep(ExecutorKind.SAY, {"text": "[whispers] 我先安靜一下"}),
        ],
        priority_class=PriorityClass.SAFETY,
        description="System pause: stop motion first, then silence + ignore non-safety triggers.",
        ui_style="safety",
        bucket="active",
        display_name="系統暫停",
        demo_status_baseline="studio_only",
        demo_value="low",
        demo_reason="系統級開關只給 Studio",
    ),
    "show_status": SkillContract(
        name="show_status",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "[playful] 系統狀態正常喔"})],
        priority_class=PriorityClass.CHAT,
        cooldown_s=2.0,
        description="Status read-out (Studio button).",
        bucket="active",
        display_name="狀態回報",
        demo_status_baseline="available_execute",
        demo_value="medium",
        demo_reason="低風險語音回報",
    ),

    # ---- Chat (LLM-driven, dynamic text) ----
    "chat_reply": SkillContract(
        name="chat_reply",
        steps=[SkillStep(ExecutorKind.SAY, {"text": ""})],
        priority_class=PriorityClass.CHAT,
        description="LLM-sourced free-form chat reply.",
        args_schema={"text": "string"},
        bucket="active",
        display_name="自然對話",
        demo_status_baseline="available_execute",
        demo_value="high",
        demo_reason="Demo 主軸功能",
    ),
    "say_canned": SkillContract(
        name="say_canned",
        steps=[SkillStep(ExecutorKind.SAY, {"text": ""})],
        priority_class=PriorityClass.CHAT,
        description="Brain rule fallback canned line.",
        args_schema={"text": "string"},
        bucket="active",
        display_name="規則回覆",
        demo_status_baseline="available_execute",
        demo_value="medium",
        demo_reason="LLM 失敗時的 fallback",
    ),

    # ---- Sequence (meta) ----
    "self_introduce": SkillContract(
        name="self_introduce",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[excited] 大家好，我是 PawAI！"}),
            SkillStep(ExecutorKind.MOTION, {"name": "hello"}),
            SkillStep(ExecutorKind.SAY, {"text": "[curious] 我會看臉、聽聲音、認手勢"}),
            SkillStep(ExecutorKind.MOTION, {"name": "sit"}),
            SkillStep(ExecutorKind.SAY, {"text": "[playful] 隨時跟我互動！"}),
            SkillStep(ExecutorKind.MOTION, {"name": "balance_stand"}),
        ],
        priority_class=PriorityClass.SEQUENCE,
        cooldown_s=60.0,
        timeout_s=60.0,
        description="Self-introduction 6-step meta sequence.",
        bucket="active",
        display_name="自我介紹",
        demo_status_baseline="available_execute",
        demo_value="high",
        demo_reason="Demo 主軸功能",
    ),

    # ---- Social motion (low-risk) ----
    "wave_hello": SkillContract(
        name="wave_hello",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[excited] 嗨！"}),
            SkillStep(ExecutorKind.MOTION, {"name": "hello"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=5.0,
        description="Wave back when user waves.",
        bucket="active",
        display_name="揮手打招呼",
        demo_status_baseline="available_execute",
        demo_value="high",
        demo_reason="低風險社交動作",
    ),
    "sit_along": SkillContract(
        name="sit_along",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[playful] 我也坐下陪你"}),
            SkillStep(ExecutorKind.MOTION, {"name": "sit"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=15.0,
        description="Sit when user sits.",
        bucket="active",
        display_name="跟坐",
        demo_status_baseline="available_execute",
        demo_value="medium",
        demo_reason="低風險陪伴動作",
    ),
    "careful_remind": SkillContract(
        name="careful_remind",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "[worried] 小心一點喔"})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=10.0,
        description="Remind user to be careful (bending detected).",
        bucket="active",
        display_name="小心提醒",
        demo_status_baseline="available_execute",
        demo_value="medium",
        demo_reason="貼心語音提示",
    ),

    # ---- Social motion (high-risk, requires OK confirm) ----
    "wiggle": SkillContract(
        name="wiggle",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[playful] 看我扭一下！"}),
            SkillStep(ExecutorKind.MOTION, {"name": "wiggle_hip"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=10.0,
        safety_requirements=["depth_clear", "robot_stable"],
        requires_confirmation=True,
        risk_level="high",
        fallback_skill="say_canned",
        description="Hip wiggle. High-risk motion, requires OK confirm.",
        bucket="active",
        display_name="搖擺",
        demo_status_baseline="available_confirm",
        demo_value="medium",
        demo_reason="低風險表演動作但需 OK 確認",
    ),
    "stretch": SkillContract(
        name="stretch",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[sighs] 伸個懶腰～"}),
            SkillStep(ExecutorKind.MOTION, {"name": "stretch"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=15.0,
        safety_requirements=["depth_clear", "robot_stable"],
        requires_confirmation=True,
        risk_level="high",
        fallback_skill="say_canned",
        description="Body stretch. High-risk motion, requires OK confirm.",
        bucket="active",
        display_name="伸展",
        demo_status_baseline="available_confirm",
        demo_value="medium",
        demo_reason="低風險表演動作但需 OK 確認",
    ),

    # ---- Face-driven ----
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
        bucket="active",
        display_name="熟人問候",
        demo_status_baseline="available_execute",
        demo_value="high",
        demo_reason="人臉識別 + 個人化招呼",
    ),
    "stranger_alert": SkillContract(
        name="stranger_alert",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "偵測到不認識的人，請注意"})],
        priority_class=PriorityClass.ALERT,
        cooldown_s=30.0,
        description="Unknown face stable for 3 seconds.",
        ui_style="alert",
        bucket="active",
        display_name="陌生人警告",
        demo_status_baseline="explain_only",
        demo_value="medium",
        demo_reason="關閉誤觸打斷對話；只在 Studio 顯示警示",
    ),
    "fallen_alert": SkillContract(
        name="fallen_alert",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "stop_move"}),
            SkillStep(
                ExecutorKind.SAY,
                {"text_template": "偵測到 {name} 跌倒，請確認是否需要協助"},
            ),
        ],
        priority_class=PriorityClass.ALERT,
        cooldown_s=15.0,
        description="Human fallen detected. Stop dog, then alert with name.",
        ui_style="alert",
        args_schema={"name": "string"},
        bucket="active",
        display_name="跌倒提醒",
        demo_status_baseline="explain_only",
        demo_value="medium",
        demo_reason="關閉誤觸打斷對話；只在 Studio 顯示警示",
    ),

    # ---- Object ----
    "object_remark": SkillContract(
        name="object_remark",
        # 5/6: brain_node now pre-builds the localized text via build_object_tts
        # (colour preamble + class zh + optional personality suffix). Template
        # just renders {text}; legacy {color}/{label} args are kept for trace.
        steps=[SkillStep(ExecutorKind.SAY, {"text_template": "{text}"})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=5.0,
        description="Comment on a salient detected object (text pre-built in brain).",
        args_schema={"text": "string", "label": "string", "color": "string"},
        bucket="active",
        display_name="物體解說",
        demo_status_baseline="explain_only",
        demo_value="medium",
        demo_reason="Demo 不主動展示，由 demo_guide 引導",
    ),

    # ---- Navigation (high-risk) ----
    "nav_demo_point": SkillContract(
        name="nav_demo_point",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "goto_relative", "distance": 1.2})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=8.0,
        timeout_s=20.0,
        safety_requirements=["nav_ready", "depth_clear"],
        requires_confirmation=True,  # Studio button trigger 由 brain bypass
        risk_level="high",
        fallback_skill="say_canned",
        description="Short relative goto (Scene 2 保底). Studio button bypass confirm.",
        bucket="active",
        display_name="短距離移動",
        demo_status_baseline="explain_only",
        demo_value="medium",
        demo_reason="動態避障非主展示，需場地較大",
    ),
    "approach_person": SkillContract(
        name="approach_person",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "goto_face", "stop_distance": 1.0})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=15.0,
        timeout_s=25.0,
        safety_requirements=["nav_ready", "depth_clear", "robot_stable"],
        requires_confirmation=True,
        risk_level="high",
        fallback_skill="wave_hello",
        description="Approach person to 1m (Scene 7 Wow C).",
        args_schema={"name": "string"},
        bucket="active",
        display_name="走近人",
        demo_status_baseline="explain_only",
        demo_value="medium",
        demo_reason="動態導航非主展示",
    ),

    # ---- Hidden (registry 內、Studio grayed-out) ----
    "enter_mute_mode": SkillContract(
        name="enter_mute_mode",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "[whispers] 進入靜音模式"})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=5.0,
        requires_confirmation=True,
        risk_level="medium",
        description="Mute TTS until next un-mute. Hidden in Phase B Demo.",
        bucket="hidden",
        display_name="靜音模式",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Phase B Demo 隱藏",
    ),
    "enter_listen_mode": SkillContract(
        name="enter_listen_mode",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "[curious] 我在聽"})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=3.0,
        description="Force-open ASR window. Hidden in Phase B Demo.",
        bucket="hidden",
        display_name="聆聽模式",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Phase B Demo 隱藏",
    ),
    "akimbo_react": SkillContract(
        name="akimbo_react",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[playful] 喔～你叉腰啦！"}),
            SkillStep(ExecutorKind.MOTION, {"name": "balance_stand"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=10.0,
        description="React to akimbo pose. Hidden in Phase B Demo.",
        bucket="hidden",
        display_name="叉腰回應",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Phase B Demo 隱藏",
    ),
    "knee_kneel_react": SkillContract(
        name="knee_kneel_react",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text": "[curious] 你跪下做什麼？"}),
            SkillStep(ExecutorKind.MOTION, {"name": "sit"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=10.0,
        description="React to single-knee kneel. Hidden in Phase B Demo.",
        bucket="hidden",
        display_name="跪地回應",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Phase B Demo 隱藏",
    ),
    "patrol_route": SkillContract(
        name="patrol_route",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "patrol", "route_id": ""})],
        priority_class=PriorityClass.SKILL,
        cooldown_s=30.0,
        timeout_s=60.0,
        safety_requirements=["nav_ready", "depth_clear"],
        requires_confirmation=True,
        risk_level="high",
        description="Run a saved route. Hidden in Phase B Demo (optional surface).",
        args_schema={"route_id": "string"},
        bucket="hidden",
        display_name="巡邏路線",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Phase B Demo 隱藏",
    ),

    # ---- Disabled / Future ----
    "follow_me": SkillContract(
        name="follow_me",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "follow_user"})],
        priority_class=PriorityClass.SKILL,
        static_enabled=False,
        risk_level="high",
        description="Follow the user. Disabled in 5/12 Demo (Future Work).",
        bucket="disabled",
        display_name="跟隨我",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Future Work",
    ),
    "follow_person": SkillContract(
        name="follow_person",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "follow_face"})],
        priority_class=PriorityClass.SKILL,
        static_enabled=False,
        risk_level="high",
        description="Follow a specific named person. Disabled (Future).",
        args_schema={"name": "string"},
        bucket="disabled",
        display_name="跟隨人",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Future Work",
    ),
    "dance": SkillContract(
        name="dance",
        steps=[SkillStep(ExecutorKind.MOTION, {"name": "wiggle_hip"})],
        priority_class=PriorityClass.SKILL,
        static_enabled=False,
        risk_level="high",
        description="Choreographed dance. Disabled (Future).",
        bucket="disabled",
        display_name="跳舞",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="動作不穩定",
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
        bucket="disabled",
        display_name="前往指定地點",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="Phase B 才整合 nav_capability",
    ),

    # ---- Retired (registry 保留、Studio 不顯示、brain 不選) ----
    "acknowledge_gesture": SkillContract(
        name="acknowledge_gesture",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "content"}),
            SkillStep(ExecutorKind.SAY, {"text": "收到"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=3.0,
        static_enabled=False,
        description="Generic gesture ack. Retired — split into wave_hello / wiggle / stretch.",
        args_schema={"gesture": "string"},
        bucket="retired",
        display_name="手勢確認 (retired)",
        demo_status_baseline="disabled",
        demo_value="low",
        demo_reason="已退役，拆成 wave_hello / wiggle / stretch",
    ),
}


# Convenience views for Brain / Studio consumers.
META_SKILLS: dict[str, list[SkillStep]] = {
    "self_introduce": SKILL_REGISTRY["self_introduce"].steps,
}


def skills_by_bucket(bucket: SkillBucket) -> list[SkillContract]:
    """Return all contracts in a given bucket (deterministic order)."""
    return [c for c in SKILL_REGISTRY.values() if c.bucket == bucket]


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
