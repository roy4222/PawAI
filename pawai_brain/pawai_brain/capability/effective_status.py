"""Pure effective_status calculation — Plan §4.5 rule table."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorldFlags:
    tts_playing: bool = False
    obstacle: bool = False
    nav_safe: bool = True


class _SkillLike(Protocol):
    name: str
    baseline: str
    static_enabled: bool
    enabled_when: list
    cooldown_remaining_s: float
    has_say_step: bool
    has_motion_step: bool
    has_nav_step: bool
    kind: str


# -- Capability health gate (issue #85, v0.2 -- default-OFF, fail-closed) --
@dataclass(frozen=True)
class CapabilityHealth:
    """Per-capability baseline health. All-None => gate inert (default-OFF)."""
    grade: str | None = None            # pass | degraded | fail | insufficient_data | None
    claim_level: str | None = None      # mainline | future | studio_only | not_claimed
    dependency_role: str | None = None  # trigger | content | safety_guard | actuation | evidence
    risk_role: str | None = None        # evidence_only | convenience | safety_critical | actuation | safety_support
    brain_allowed: bool | None = None   # precomputed by grader; None = not wired


_GATE_OFF = CapabilityHealth()
# dependency_role values that gate motion/nav-class actions.
_MOTION_KINDS = ("trigger", "safety_guard", "actuation")


def _grade_gate(skill: _SkillLike, h: CapabilityHealth) -> tuple[str | None, str]:
    """Fail-closed capability-health gate.

    Returns (status, reason). status is None when the gate ABSTAINS -- either
    default-OFF (no health wired) or a non-motion content/evidence passthrough --
    letting the normal rule table continue. Never returns a less-restrictive
    status. Unknown/missing grade is treated as insufficient_data (fail-closed).
    """
    # Default-OFF: no grade wired => abstain entirely (current behaviour preserved).
    if h.grade is None and h.brain_allowed is None:
        return None, ""

    grade = h.grade if h.grade in ("pass", "degraded", "fail", "insufficient_data") else "insufficient_data"
    dep = h.dependency_role
    motion = bool(skill.has_motion_step or skill.has_nav_step)

    if grade == "pass":
        if h.brain_allowed is True:
            return None, ""                      # healthy mainline => normal flow
        # pass but not mainline-claimed (studio_only / future): block motion-class.
        if dep in _MOTION_KINDS:
            return "disabled", f"capability_not_mainline:{h.claim_level}"
        return None, ""

    if grade == "fail":
        if dep == "trigger":
            return "disabled", "capability_grade_fail:trigger"
        if dep in ("safety_guard", "actuation"):
            return "blocked", f"capability_grade_fail:{dep}"
        if dep in ("content", "evidence"):
            return None, ""                      # non-motion content/evidence => passthrough
        return ("blocked", "capability_grade_fail:unknown_dep") if motion else (None, "")

    # grade in {degraded, insufficient_data}: motion/nav class all blocked.
    if dep in _MOTION_KINDS:
        return "blocked", f"capability_{grade}:{dep}"
    if motion and h.risk_role == "safety_critical":
        return "blocked", f"capability_{grade}:safety_critical"
    return None, ""


def compute_effective_status(skill: _SkillLike, world: WorldFlags, health: CapabilityHealth = _GATE_OFF) -> tuple[str, str]:
    """Return (effective_status, reason). First match wins.

    Priority (matches Plan §4.5):
      disabled / studio_only / demo_guide / explain_only baselines
      → static_enabled / enabled_when
      → cooldown
      → physical block (TTS / obstacle / nav)
      → available_confirm → needs_confirm
      → available
    """
    baseline = skill.baseline
    if baseline == "disabled":
        return "disabled", ""
    if baseline == "studio_only":
        return "studio_only", ""
    if skill.kind == "demo_guide":
        return "explain_only", ""
    if baseline == "explain_only":
        return "explain_only", ""

    # Capability health gate (issue #85, default-OFF). Runs after hard-disable
    # baselines so a healthy grade can never resurrect a disabled skill.
    gated, gate_reason = _grade_gate(skill, health)
    if gated is not None:
        return gated, gate_reason

    if not skill.static_enabled:
        return "disabled", "靜態未啟用"

    if skill.enabled_when:
        # enabled_when is list of (key, reason) tuples; presence == not yet enabled
        flag, reason = skill.enabled_when[0]
        return "disabled", reason or flag

    if skill.cooldown_remaining_s > 0:
        return "cooldown", f"cooldown 剩 {skill.cooldown_remaining_s:.1f} 秒"

    if world.tts_playing and skill.has_say_step:
        return "defer", "TTS 播放中"

    if world.obstacle and skill.has_motion_step:
        return "blocked", "前方有障礙"

    if not world.nav_safe and skill.has_nav_step:
        return "blocked", "導航未 ready"

    if baseline == "available_confirm":
        return "needs_confirm", "需 OK 確認"

    return "available", ""
