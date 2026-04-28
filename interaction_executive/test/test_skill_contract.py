"""Tests for skill_contract.py."""
import pytest

from interaction_executive.skill_contract import (
    BANNED_API_IDS,
    MOTION_NAME_MAP,
    SKILL_REGISTRY,
    ExecutorKind,
    PriorityClass,
    build_plan,
)


def test_registry_has_nine_entries():
    assert set(SKILL_REGISTRY) == {
        "chat_reply",
        "say_canned",
        "stop_move",
        "acknowledge_gesture",
        "greet_known_person",
        "self_introduce",
        "stranger_alert",
        "fallen_alert",
        "go_to_named_place",
    }


def test_skill_contract_forward_compat_fields_present():
    contract = SKILL_REGISTRY["chat_reply"]
    assert contract.static_enabled is True
    assert contract.enabled_when == []
    assert contract.requires_confirmation is False
    assert contract.risk_level == "low"


def test_self_introduce_has_ten_steps():
    plan = build_plan("self_introduce")
    assert len(plan.steps) == 10
    assert plan.priority_class == PriorityClass.SEQUENCE


def test_greet_known_person_template_resolves():
    plan = build_plan("greet_known_person", args={"name": "alice"})
    assert plan.steps[0].executor == ExecutorKind.SAY
    assert plan.steps[0].args["text"] == "歡迎回來，alice"
    assert plan.steps[1].executor == ExecutorKind.MOTION
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


def test_fallen_alert_uses_stop_move_not_balance_stand():
    plan = build_plan("fallen_alert")
    motion_steps = [step for step in plan.steps if step.executor == ExecutorKind.MOTION]
    assert len(motion_steps) == 1
    assert motion_steps[0].args["name"] == "stop_move"
    assert all(step.args.get("name") != "balance_stand" for step in motion_steps)


def test_go_to_named_place_known_but_blocked_until_phase_b():
    contract = SKILL_REGISTRY["go_to_named_place"]
    assert contract.static_enabled is True
    assert contract.enabled_when
    with pytest.raises(ValueError, match="Phase B"):
        build_plan("go_to_named_place")


def test_motion_name_map_covers_registry_and_avoids_banned_ids():
    referenced = set()
    for contract in SKILL_REGISTRY.values():
        for step in contract.steps:
            if step.executor == ExecutorKind.MOTION:
                referenced.add(step.args["name"])
    assert referenced <= set(MOTION_NAME_MAP)
    assert not (set(MOTION_NAME_MAP.values()) & BANNED_API_IDS)


def test_stop_move_priority_is_safety():
    plan = build_plan("stop_move")
    assert plan.priority_class == PriorityClass.SAFETY
