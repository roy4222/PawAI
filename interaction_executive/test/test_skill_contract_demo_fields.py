"""Verify the 4 demo metadata fields are populated for all 27 SKILL_REGISTRY entries."""
from interaction_executive.skill_contract import SKILL_REGISTRY, SkillContract


VALID_BASELINES = {
    "available_execute", "available_confirm",
    "explain_only", "studio_only", "disabled",
}
VALID_DEMO_VALUES = {"high", "medium", "low"}


def test_skill_contract_dataclass_has_4_demo_fields():
    fields = {f.name for f in SkillContract.__dataclass_fields__.values()}
    assert "display_name" in fields
    assert "demo_status_baseline" in fields
    assert "demo_value" in fields
    assert "demo_reason" in fields


def test_all_27_skills_have_valid_baseline():
    for name, contract in SKILL_REGISTRY.items():
        assert contract.demo_status_baseline in VALID_BASELINES, \
            f"{name}: invalid baseline {contract.demo_status_baseline!r}"


def test_all_27_skills_have_valid_demo_value():
    for name, contract in SKILL_REGISTRY.items():
        assert contract.demo_value in VALID_DEMO_VALUES, \
            f"{name}: invalid demo_value {contract.demo_value!r}"


def test_all_skills_have_display_name():
    for name, contract in SKILL_REGISTRY.items():
        assert contract.display_name, f"{name}: empty display_name"


def test_baseline_distribution_matches_spec_section_11():
    """5/18 baseline classification per spec §11.
    5/9 evening: +stand (available_execute).
    5/23 evening: +request_backflip (explain_only) for 5/27 demo § 5 safety reject viz.
    """
    counts = {}
    for contract in SKILL_REGISTRY.values():
        counts[contract.demo_status_baseline] = counts.get(contract.demo_status_baseline, 0) + 1

    # available_execute: original 9 (incl. stop_move) + stand = 10
    assert counts.get("available_execute") == 10
    assert counts.get("available_confirm") == 2
    # explain_only: 5/18 baseline 5 + request_backflip (5/23) = 6
    assert counts.get("explain_only") == 6
    assert counts.get("studio_only") == 1
    assert counts.get("disabled") == 10


def test_specific_skill_baselines():
    assert SKILL_REGISTRY["self_introduce"].demo_status_baseline == "available_execute"
    assert SKILL_REGISTRY["wiggle"].demo_status_baseline == "available_confirm"
    assert SKILL_REGISTRY["fallen_alert"].demo_status_baseline == "explain_only"
    assert SKILL_REGISTRY["system_pause"].demo_status_baseline == "studio_only"
    assert SKILL_REGISTRY["dance"].demo_status_baseline == "disabled"
