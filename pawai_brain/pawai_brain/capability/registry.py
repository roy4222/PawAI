"""CapabilityRegistry — merge SkillContract + DemoGuide → CapabilityEntry list."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any

from .demo_guides_loader import DemoGuide
from .effective_status import WorldFlags, compute_effective_status


_AVAILABLE_STATUSES = frozenset({"available", "needs_confirm"})


@dataclass(frozen=True)
class CapabilityEntry:
    name: str
    kind: str  # "skill" | "demo_guide"
    display_name: str
    effective_status: str
    demo_value: str
    can_execute: bool
    requires_confirmation: bool
    reason: str
    intro: str = ""  # demo_guide only
    related_skills: tuple = ()  # demo_guide only

    def to_llm_dict(self) -> dict:
        d = {
            "name": self.name,
            "kind": self.kind,
            "display_name": self.display_name,
            "effective_status": self.effective_status,
            "demo_value": self.demo_value,
            "can_execute": self.can_execute,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
        }
        if self.kind == "demo_guide":
            d["intro"] = self.intro
            d["related_skills"] = list(self.related_skills)
        return d


class CapabilityRegistry:
    def __init__(self, skills: dict, guides: list) -> None:
        skill_names = set(skills.keys())
        guide_names = {g.name for g in guides}
        overlap = skill_names & guide_names
        if overlap:
            raise ValueError(f"SkillContract / DemoGuide names not disjoint: {overlap}")
        self._skills = skills
        self._guides = list(guides)

    def build_entries(
        self, world: WorldFlags, recent_results: list
    ) -> list:
        entries: list = []
        for name, contract in self._skills.items():
            entries.append(self._skill_entry(name, contract, world, recent_results))
        for guide in self._guides:
            entries.append(self._guide_entry(guide))
        return entries

    # ── internals ──

    def _skill_entry(
        self, name: str, contract, world: WorldFlags, recent_results: list
    ) -> CapabilityEntry:
        # Adapter for compute_effective_status
        adapter = _SkillAdapter(
            name=name,
            baseline=contract.demo_status_baseline,
            static_enabled=contract.static_enabled,
            enabled_when=list(contract.enabled_when or []),
            cooldown_remaining_s=_cooldown_remaining(name, contract.cooldown_s, recent_results),
            has_say_step=any(_is_say(s) for s in (contract.steps or [])),
            has_motion_step=any(_is_motion(s) for s in (contract.steps or [])),
            has_nav_step=any(_is_nav(s) for s in (contract.steps or [])),
            kind="skill",
        )
        status, reason = compute_effective_status(adapter, world)
        return CapabilityEntry(
            name=name,
            kind="skill",
            display_name=contract.display_name or name,
            effective_status=status,
            demo_value=contract.demo_value,
            can_execute=(status == "available"),
            requires_confirmation=bool(contract.requires_confirmation),
            reason=reason,
        )

    def _guide_entry(self, guide: DemoGuide) -> CapabilityEntry:
        adapter = _SkillAdapter(
            name=guide.name,
            baseline=guide.baseline_status,
            static_enabled=True,
            enabled_when=[],
            cooldown_remaining_s=0.0,
            has_say_step=False,
            has_motion_step=False,
            has_nav_step=False,
            kind="demo_guide",
        )
        status, reason = compute_effective_status(adapter, WorldFlags())
        return CapabilityEntry(
            name=guide.name,
            kind="demo_guide",
            display_name=guide.display_name,
            effective_status=status,
            demo_value=guide.demo_value,
            can_execute=False,
            requires_confirmation=False,
            reason=reason,
            intro=guide.intro,
            related_skills=tuple(guide.related_skills),
        )


# ── helpers ──


@dataclass
class _SkillAdapter:
    name: str
    baseline: str
    static_enabled: bool
    enabled_when: list
    cooldown_remaining_s: float
    has_say_step: bool
    has_motion_step: bool
    has_nav_step: bool
    kind: str


def _is_say(step) -> bool:
    return getattr(step.executor, "name", "") == "SAY"


def _is_motion(step) -> bool:
    return getattr(step.executor, "name", "") == "MOTION"


def _is_nav(step) -> bool:
    return getattr(step.executor, "name", "") == "NAV"


def _cooldown_remaining(name: str, cooldown_s: float, recent: list) -> float:
    if cooldown_s <= 0:
        return 0.0
    last_ts = None
    for r in recent:
        if r.get("name") == name and r.get("status") == "completed":
            ts = r.get("ts", 0)
            if last_ts is None or ts > last_ts:
                last_ts = ts
    if last_ts is None:
        return 0.0
    return max(0.0, last_ts + cooldown_s - time.time())


def build_capability_entries(*args, **kwargs):
    """Convenience function for older tests / call sites."""
    return CapabilityRegistry(*args, **kwargs).build_entries(WorldFlags(), [])
