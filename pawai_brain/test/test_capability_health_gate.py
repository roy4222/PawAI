"""Truth-table for the capability health gate (issue #85, v0.2)."""
from dataclasses import dataclass

from pawai_brain.capability.effective_status import (
    CapabilityHealth,
    WorldFlags,
    _GATE_OFF,
    _grade_gate,
    compute_effective_status,
)


@dataclass
class FakeSkill:
    name: str = "x"
    baseline: str = "available"
    static_enabled: bool = True
    enabled_when: list = None
    cooldown_remaining_s: float = 0.0
    has_say_step: bool = False
    has_motion_step: bool = False
    has_nav_step: bool = False
    kind: str = "reactive"

    def __post_init__(self):
        if self.enabled_when is None:
            self.enabled_when = []


def _motion():
    return FakeSkill(has_motion_step=True)


def _say():
    return FakeSkill(has_say_step=True)


def H(**kw):
    return CapabilityHealth(**kw)


# -- _grade_gate unit truth table --

def test_pass_mainline_abstains():
    assert _grade_gate(_motion(), H(grade="pass", dependency_role="trigger", claim_level="mainline", brain_allowed=True)) == (None, "")


def test_pass_safety_guard_mainline_abstains():
    assert _grade_gate(_motion(), H(grade="pass", dependency_role="safety_guard", claim_level="mainline", brain_allowed=True)) == (None, "")


def test_pass_not_mainline_blocks_motion_class():
    s, r = _grade_gate(_motion(), H(grade="pass", dependency_role="trigger", claim_level="studio_only", brain_allowed=False))
    assert s == "disabled" and "not_mainline" in r


def test_pass_future_actuation_disabled():
    s, _ = _grade_gate(_motion(), H(grade="pass", dependency_role="actuation", claim_level="future", brain_allowed=False))
    assert s == "disabled"


def test_fail_trigger_disabled():
    assert _grade_gate(_motion(), H(grade="fail", dependency_role="trigger")) == ("disabled", "capability_grade_fail:trigger")


def test_fail_safety_guard_blocked():
    assert _grade_gate(_motion(), H(grade="fail", dependency_role="safety_guard")) == ("blocked", "capability_grade_fail:safety_guard")


def test_fail_actuation_blocked():
    assert _grade_gate(_motion(), H(grade="fail", dependency_role="actuation")) == ("blocked", "capability_grade_fail:actuation")


def test_fail_content_passthrough():
    assert _grade_gate(_say(), H(grade="fail", dependency_role="content")) == (None, "")


def test_fail_evidence_passthrough():
    assert _grade_gate(_say(), H(grade="fail", dependency_role="evidence")) == (None, "")


def test_fail_unknown_dep_motion_failclosed():
    s, r = _grade_gate(_motion(), H(grade="fail", dependency_role=None))
    assert s == "blocked" and "unknown_dep" in r


def test_degraded_trigger_blocked():
    assert _grade_gate(_motion(), H(grade="degraded", dependency_role="trigger")) == ("blocked", "capability_degraded:trigger")


def test_degraded_safety_guard_blocked():
    s, _ = _grade_gate(_motion(), H(grade="degraded", dependency_role="safety_guard"))
    assert s == "blocked"


def test_insufficient_trigger_blocked():
    assert _grade_gate(_motion(), H(grade="insufficient_data", dependency_role="trigger")) == ("blocked", "capability_insufficient_data:trigger")


def test_insufficient_safety_critical_corner_blocked():
    # corner case: insufficient_data + motion + safety_critical (non-motion dep) => fail-closed block
    s, r = _grade_gate(_motion(), H(grade="insufficient_data", dependency_role=None, risk_role="safety_critical"))
    assert s == "blocked" and "safety_critical" in r


def test_insufficient_content_passthrough():
    assert _grade_gate(_say(), H(grade="insufficient_data", dependency_role="content")) == (None, "")


def test_unknown_grade_is_failclosed_insufficient():
    # bogus grade => treated as insufficient_data => motion-class blocked
    s, _ = _grade_gate(_motion(), H(grade="bogus", dependency_role="safety_guard"))
    assert s == "blocked"


# -- default-OFF + integration with compute_effective_status --

def test_default_off_gate_is_inert():
    # No health wired => identical to today (2-arg call path).
    world = WorldFlags()
    assert compute_effective_status(_motion(), world) == ("available", "")
    assert compute_effective_status(_motion(), world, _GATE_OFF) == ("available", "")


def test_default_off_grade_none_brain_none_abstains():
    assert _grade_gate(_motion(), H()) == (None, "")


def test_hard_disable_wins_over_healthy_grade():
    # baseline disabled must NOT be resurrected by a passing grade.
    s = FakeSkill(baseline="disabled", has_motion_step=True)
    status, _ = compute_effective_status(s, WorldFlags(), H(grade="pass", dependency_role="trigger", claim_level="mainline", brain_allowed=True))
    assert status == "disabled"


def test_gate_blocks_through_compute_effective_status():
    # available skill + fail trigger grade => gate disables it.
    status, reason = compute_effective_status(_motion(), WorldFlags(), H(grade="fail", dependency_role="trigger"))
    assert status == "disabled" and "grade_fail" in reason
