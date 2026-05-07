"""Tests for effective_status — Plan §4.5 priority order."""
from dataclasses import dataclass

from pawai_brain.capability.effective_status import (
    WorldFlags,
    compute_effective_status,
)


@dataclass
class FakeSkill:
    name: str
    baseline: str = "available_execute"
    static_enabled: bool = True
    enabled_when: list = None
    cooldown_remaining_s: float = 0.0
    has_say_step: bool = False
    has_motion_step: bool = False
    has_nav_step: bool = False
    kind: str = "skill"

    def __post_init__(self):
        if self.enabled_when is None:
            self.enabled_when = []


def _world(**kw):
    return WorldFlags(
        tts_playing=kw.get("tts_playing", False),
        obstacle=kw.get("obstacle", False),
        nav_safe=kw.get("nav_safe", True),
    )


def test_disabled_baseline_wins_over_everything():
    skill = FakeSkill(name="dance", baseline="disabled")
    s, _ = compute_effective_status(skill, _world(tts_playing=True, obstacle=True))
    assert s == "disabled"


def test_studio_only_baseline():
    skill = FakeSkill(name="fallen_alert", baseline="studio_only")
    s, _ = compute_effective_status(skill, _world())
    assert s == "studio_only"


def test_demo_guide_kind_always_explain_only():
    skill = FakeSkill(name="gesture_demo", kind="demo_guide", baseline="explain_only")
    s, _ = compute_effective_status(skill, _world())
    assert s == "explain_only"


def test_explain_only_baseline():
    skill = FakeSkill(name="object_remark", baseline="explain_only")
    s, _ = compute_effective_status(skill, _world())
    assert s == "explain_only"


def test_static_enabled_false_yields_disabled():
    skill = FakeSkill(name="follow_me", static_enabled=False)
    s, reason = compute_effective_status(skill, _world())
    assert s == "disabled"
    assert "靜態未啟用" in reason


def test_cooldown_blocks_available():
    skill = FakeSkill(name="wave_hello", cooldown_remaining_s=4.2)
    s, reason = compute_effective_status(skill, _world())
    assert s == "cooldown"
    assert "4" in reason  # contains the seconds


def test_tts_playing_defers_say_skill():
    skill = FakeSkill(name="show_status", has_say_step=True)
    s, _ = compute_effective_status(skill, _world(tts_playing=True))
    assert s == "defer"


def test_obstacle_blocks_motion_skill():
    skill = FakeSkill(name="wave_hello", has_motion_step=True)
    s, _ = compute_effective_status(skill, _world(obstacle=True))
    assert s == "blocked"


def test_nav_unsafe_blocks_nav_skill():
    skill = FakeSkill(name="nav_demo_point", has_nav_step=True)
    s, _ = compute_effective_status(skill, _world(nav_safe=False))
    assert s == "blocked"


def test_physical_block_runs_BEFORE_needs_confirm():
    """Plan §4.5 ordering fix: wiggle/stretch must NOT prompt OK if obstacle."""
    skill = FakeSkill(name="wiggle", baseline="available_confirm", has_motion_step=True)
    s, _ = compute_effective_status(skill, _world(obstacle=True))
    assert s == "blocked"  # NOT needs_confirm


def test_available_confirm_yields_needs_confirm_when_clear():
    skill = FakeSkill(name="wiggle", baseline="available_confirm", has_motion_step=True)
    s, _ = compute_effective_status(skill, _world())
    assert s == "needs_confirm"


def test_available_when_all_clear():
    skill = FakeSkill(name="show_status", has_say_step=True)
    s, _ = compute_effective_status(skill, _world())
    assert s == "available"
