"""Evidence Center zh table coverage locks."""

import re

from pawai_contracts.zh_tables import (
    ISM_STATE_ZH,
    ISM_TRIGGER_ZH,
    ISM_VERDICT_ZH,
    TRACE_GATE_ZH,
    TRACE_REASON_PREFIX_ZH,
)


EXPECTED_TRACE_GATES = frozenset(
    {
        "active_plan",
        "alert_active",
        "attention_engaged",
        "capability_health",
        "confirm_pending",
        "conversation_gate",
        "dedup",
        "demo_phase",
        "depth_clear",
        "emergency",
        "executing",
        "gesture_enabled",
        "greet_cooldown",
        "greet_gate",
        "greet_sitting_window",
        "ism_shadow",
        "llm_allowlist",
        "nav_paused",
        "nav_ready",
        "object_remark_dedup",
        "pending_confirm",
        "safety",
        "safety_hold",
        "skill_cooldown",
        "speaking",
        "stranger_alert_enabled",
        "tts_playing",
    }
)

EXPECTED_REASON_PREFIXES = frozenset(
    {"cooldown", "phase", "watchdog_timeout", "banned_api", "gate", "identity"}
)

CJK = re.compile(r"[\u4e00-\u9fff]")


def test_trace_gate_zh_has_exact_brain_gate_coverage():
    assert set(TRACE_GATE_ZH) == EXPECTED_TRACE_GATES


def test_ism_zh_tables_cover_all_interaction_state_machine_codes():
    assert set(ISM_VERDICT_ZH) == {"accept", "suppress", "queue", "preempt"}
    assert set(ISM_TRIGGER_ZH) == {
        "skill_result",
        "confirm_result",
        "tts_ack",
        "operator",
        "safety",
    }
    assert set(ISM_STATE_ZH) == {
        "idle",
        "listening",
        "speaking",
        "confirm_pending",
        "executing",
        "alert_active",
        "safety_hold",
        "error_recovery",
    }


def test_reason_prefix_zh_contains_required_trace_reason_prefixes():
    assert set(TRACE_REASON_PREFIX_ZH) >= EXPECTED_REASON_PREFIXES


def test_evidence_center_zh_values_are_non_empty_chinese_strings():
    tables = [
        TRACE_GATE_ZH,
        TRACE_REASON_PREFIX_ZH,
        ISM_VERDICT_ZH,
        ISM_TRIGGER_ZH,
        ISM_STATE_ZH,
    ]
    placeholders = [
        f"{key}={value!r}"
        for table in tables
        for key, value in table.items()
        if not isinstance(value, str) or not value.strip() or not CJK.search(value)
    ]
    assert not placeholders
