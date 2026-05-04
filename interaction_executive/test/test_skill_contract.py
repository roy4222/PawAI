"""Tests for skill_contract.py (Phase B v1, spec §4.1)."""
import pytest

from interaction_executive.skill_contract import (
    BANNED_API_IDS,
    META_SKILLS,
    MOTION_NAME_MAP,
    SKILL_REGISTRY,
    ExecutorKind,
    PriorityClass,
    SkillContract,
    build_plan,
    skills_by_bucket,
)


# ---------------------------------------------------------------------------
# Inventory shape (spec §4.1)
# ---------------------------------------------------------------------------

EXPECTED_ACTIVE = {
    "stop_move",
    "system_pause",
    "show_status",
    "chat_reply",
    "say_canned",
    "self_introduce",
    "wave_hello",
    "wiggle",
    "stretch",
    "sit_along",
    "careful_remind",
    "greet_known_person",
    "stranger_alert",
    "object_remark",
    "nav_demo_point",
    "approach_person",
    "fallen_alert",
}
EXPECTED_HIDDEN = {
    "enter_mute_mode",
    "enter_listen_mode",
    "akimbo_react",
    "knee_kneel_react",
    "patrol_route",
}
EXPECTED_DISABLED = {"follow_me", "follow_person", "dance", "go_to_named_place"}
EXPECTED_RETIRED = {"acknowledge_gesture"}


def test_registry_total_count():
    # spec §4.1 表格寫 26 為 typo；實際列出 17+5+4+1 = 27
    assert len(SKILL_REGISTRY) == 27


def test_active_bucket_matches_inventory():
    assert {c.name for c in skills_by_bucket("active")} == EXPECTED_ACTIVE


def test_hidden_bucket_matches_inventory():
    assert {c.name for c in skills_by_bucket("hidden")} == EXPECTED_HIDDEN


def test_disabled_bucket_matches_inventory():
    assert {c.name for c in skills_by_bucket("disabled")} == EXPECTED_DISABLED


def test_retired_bucket_matches_inventory():
    assert {c.name for c in skills_by_bucket("retired")} == EXPECTED_RETIRED


def test_no_skill_unbucketed():
    # All skills must declare a bucket explicitly through enum
    for c in SKILL_REGISTRY.values():
        assert c.bucket in {"active", "hidden", "disabled", "retired"}


# ---------------------------------------------------------------------------
# Field semantics (bucket vs static_enabled vs enabled_when)
# ---------------------------------------------------------------------------


def test_retired_skill_static_disabled():
    assert SKILL_REGISTRY["acknowledge_gesture"].bucket == "retired"
    assert SKILL_REGISTRY["acknowledge_gesture"].static_enabled is False


def test_disabled_bucket_static_flags():
    # follow_me / follow_person / dance: static_enabled=False
    # go_to_named_place: static_enabled=True but enabled_when blocked
    assert SKILL_REGISTRY["follow_me"].static_enabled is False
    assert SKILL_REGISTRY["follow_person"].static_enabled is False
    assert SKILL_REGISTRY["dance"].static_enabled is False
    assert SKILL_REGISTRY["go_to_named_place"].static_enabled is True
    assert SKILL_REGISTRY["go_to_named_place"].enabled_when


def test_high_risk_skills_require_confirmation():
    for name in ("wiggle", "stretch", "approach_person", "nav_demo_point"):
        c = SKILL_REGISTRY[name]
        assert c.requires_confirmation is True, name
        assert c.risk_level == "high", name


def test_low_risk_social_does_not_require_confirmation():
    for name in ("wave_hello", "sit_along", "careful_remind"):
        assert SKILL_REGISTRY[name].requires_confirmation is False, name


def test_safety_skills_have_safety_priority():
    assert SKILL_REGISTRY["stop_move"].priority_class == PriorityClass.SAFETY
    assert SKILL_REGISTRY["system_pause"].priority_class == PriorityClass.SAFETY


# ---------------------------------------------------------------------------
# build_plan behavior preserved
# ---------------------------------------------------------------------------


def test_self_introduce_meta_six_steps():
    plan = build_plan("self_introduce")
    assert len(plan.steps) == 6
    assert plan.priority_class == PriorityClass.SEQUENCE
    # Alternating SAY / MOTION / SAY / MOTION / SAY / MOTION
    expected = [
        ExecutorKind.SAY,
        ExecutorKind.MOTION,
        ExecutorKind.SAY,
        ExecutorKind.MOTION,
        ExecutorKind.SAY,
        ExecutorKind.MOTION,
    ]
    assert [s.executor for s in plan.steps] == expected


def test_meta_skills_dict_exposes_self_introduce():
    assert "self_introduce" in META_SKILLS
    assert len(META_SKILLS["self_introduce"]) == 6


def test_greet_known_person_template_resolves():
    plan = build_plan("greet_known_person", args={"name": "alice"})
    assert plan.steps[0].args["text"] == "歡迎回來，alice"
    assert plan.steps[1].args["name"] == "hello"


def test_chat_reply_and_say_canned_text_injection():
    chat = build_plan("chat_reply", args={"text": "你好啊"}, source="llm_bridge")
    canned = build_plan("say_canned", args={"text": "我聽不太懂"})
    assert chat.steps[0].args["text"] == "你好啊"
    assert canned.steps[0].args["text"] == "我聽不太懂"


def test_stranger_alert_no_motion():
    plan = build_plan("stranger_alert")
    assert all(step.executor == ExecutorKind.SAY for step in plan.steps)
    assert plan.priority_class == PriorityClass.ALERT


def test_fallen_alert_template_with_name():
    plan = build_plan("fallen_alert", args={"name": "Roy"})
    motion_steps = [step for step in plan.steps if step.executor == ExecutorKind.MOTION]
    say_steps = [step for step in plan.steps if step.executor == ExecutorKind.SAY]
    assert len(motion_steps) == 1
    assert motion_steps[0].args["name"] == "stop_move"
    assert "Roy" in say_steps[0].args["text"]


def test_go_to_named_place_known_but_blocked_until_phase_b():
    contract = SKILL_REGISTRY["go_to_named_place"]
    assert contract.static_enabled is True
    assert contract.enabled_when
    with pytest.raises(ValueError, match="Phase B"):
        build_plan("go_to_named_place")


def test_static_disabled_skill_rejected():
    with pytest.raises(ValueError, match="statically disabled"):
        build_plan("follow_me")
    with pytest.raises(ValueError, match="statically disabled"):
        build_plan("acknowledge_gesture")


def test_motion_name_map_covers_registry_and_avoids_banned_ids():
    referenced = set()
    for contract in SKILL_REGISTRY.values():
        for step in contract.steps:
            if step.executor == ExecutorKind.MOTION:
                name = step.args.get("name")
                if name:
                    referenced.add(name)
    assert referenced <= set(MOTION_NAME_MAP), referenced - set(MOTION_NAME_MAP)
    assert not (set(MOTION_NAME_MAP.values()) & BANNED_API_IDS)


def test_stop_move_priority_is_safety():
    plan = build_plan("stop_move")
    assert plan.priority_class == PriorityClass.SAFETY


# ---------------------------------------------------------------------------
# Audio tag preembedding (spec §4.3): 5 LLM-dynamic skills must NOT preembed
# ---------------------------------------------------------------------------

LLM_DYNAMIC_SKILLS = {
    "chat_reply",
    "greet_known_person",
    "object_remark",
    "stranger_alert",
    "fallen_alert",
}


def _say_texts(contract: SkillContract) -> list[str]:
    out: list[str] = []
    for step in contract.steps:
        if step.executor != ExecutorKind.SAY:
            continue
        for key in ("text", "text_template"):
            if key in step.args and isinstance(step.args[key], str):
                out.append(step.args[key])
    return out


def test_llm_dynamic_skills_have_no_audio_tag():
    for name in LLM_DYNAMIC_SKILLS:
        for text in _say_texts(SKILL_REGISTRY[name]):
            assert "[" not in text, f"{name} say_template should not preembed audio tag: {text!r}"


def test_active_static_say_skills_have_audio_tag():
    # Active bucket, has non-empty SAY text, and not in LLM_DYNAMIC_SKILLS
    # → must contain at least one audio tag like [excited]
    for c in skills_by_bucket("active"):
        if c.name in LLM_DYNAMIC_SKILLS:
            continue
        for text in _say_texts(c):
            if not text.strip():
                continue
            assert "[" in text and "]" in text, (
                f"{c.name} say_template missing audio tag: {text!r}"
            )
