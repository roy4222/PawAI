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


def compute_effective_status(skill: _SkillLike, world: WorldFlags) -> tuple[str, str]:
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
