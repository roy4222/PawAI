"""Regression tests for `_build_user_message` — Phase A.6 capability injection.

Two bugs caught by user review:
1. `capability_context` was built but never surfaced to LLM (whole point of A.6).
2. Builder still read legacy `env_context` (replaced by `world_state` after the
   env_builder/context_builder removal).
"""
from __future__ import annotations
import json

from pawai_brain.conversation_graph_node import _build_user_message


def _capability_context() -> dict:
    return {
        "capabilities": [
            {
                "name": "self_introduce",
                "kind": "skill",
                "display_name": "自我介紹",
                "effective_status": "available",
                "demo_value": "high",
                "can_execute": True,
                "requires_confirmation": False,
                "reason": "",
            },
            {
                "name": "wiggle",
                "kind": "skill",
                "display_name": "搖擺",
                "effective_status": "needs_confirm",
                "demo_value": "medium",
                "can_execute": False,
                "requires_confirmation": True,
                "reason": "需 OK 確認",
            },
            {
                "name": "gesture_demo",
                "kind": "demo_guide",
                "display_name": "手勢辨識",
                "effective_status": "explain_only",
                "demo_value": "high",
                "can_execute": False,
                "requires_confirmation": False,
                "reason": "",
                "intro": "請對著鏡頭比 OK、讚、或握拳",
                "related_skills": ["wave_hello"],
            },
        ],
        "limits": ["陌生人警告已關閉避免誤觸", "一次最多執行一個動作"],
        "demo_session": {"active": False, "shown_skills": [], "candidate_next": []},
        "recent_skill_results": [
            {"name": "self_introduce", "status": "completed", "ts": 1.0, "detail": "6 steps"}
        ],
    }


def _world_state() -> dict:
    return {
        "period": "下午",
        "time": "14:30",
        "weather": "晴 24°C",
        "source": "speech",
        "tts_playing": False,
        "obstacle": False,
        "nav_safe": True,
    }


# ── Bug #1 regression: capability_context must reach the prompt ──────────


def test_message_includes_user_text():
    msg = _build_user_message({"user_text": "你好"})
    assert "你好" in msg


def test_message_surfaces_capability_section():
    """If capability_context is on state, the prompt MUST include it."""
    state = {
        "user_text": "你會做什麼",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    assert "[能力]" in msg, "capability section missing from prompt"
    assert "self_introduce" in msg
    assert "gesture_demo" in msg


def test_message_capability_payload_is_valid_json():
    state = {
        "user_text": "你會做什麼",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    # Extract the JSON after "[能力] "
    cap_line = next(line for line in msg.splitlines() if line.startswith("[能力]"))
    payload = json.loads(cap_line.removeprefix("[能力] "))
    assert "capabilities" in payload
    assert "limits" in payload
    assert "recent_skill_results" in payload


def test_message_capability_keeps_essential_fields():
    state = {
        "user_text": "你好",
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    cap_line = next(line for line in msg.splitlines() if line.startswith("[能力]"))
    payload = json.loads(cap_line.removeprefix("[能力] "))
    # Find self_introduce entry — must have core fields the persona prompt uses
    by_name = {c["name"]: c for c in payload["capabilities"]}
    si = by_name["self_introduce"]
    for required in ("kind", "display_name", "effective_status",
                     "can_execute", "demo_value"):
        assert required in si, f"missing {required} on self_introduce capability"


def test_message_demo_guide_includes_intro_and_related_skills():
    state = {
        "user_text": "x",
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    cap_line = next(line for line in msg.splitlines() if line.startswith("[能力]"))
    payload = json.loads(cap_line.removeprefix("[能力] "))
    by_name = {c["name"]: c for c in payload["capabilities"]}
    guide = by_name["gesture_demo"]
    assert "intro" in guide and guide["intro"]
    assert "related_skills" in guide


def test_message_includes_recent_skill_results_for_chaining():
    state = {
        "user_text": "x",
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    cap_line = next(line for line in msg.splitlines() if line.startswith("[能力]"))
    payload = json.loads(cap_line.removeprefix("[能力] "))
    assert payload["recent_skill_results"]
    assert payload["recent_skill_results"][0]["name"] == "self_introduce"


# ── Bug #2 regression: world_state, not env_context ─────────────────────


def test_message_reads_world_state_for_env_line():
    """Phase A.6 dropped env_builder; world_state_builder owns time/weather."""
    state = {"user_text": "你好", "world_state": _world_state()}
    msg = _build_user_message(state)
    assert "下午 14:30" in msg
    assert "晴" in msg


def test_message_no_env_line_when_world_state_missing():
    """Defensive: missing world_state should not crash and not emit env line."""
    msg = _build_user_message({"user_text": "你好"})
    assert "[環境]" not in msg
    assert "你好" in msg


def test_message_legacy_env_context_field_is_ignored():
    """Surface bug: previously read state['env_context']. After A.6 it must
    use state['world_state'] only — env_context (if any) must be ignored to
    avoid leaking stale state into the prompt."""
    state = {
        "user_text": "x",
        "env_context": {"period": "STALE", "time": "00:00", "weather": "STALE"},
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "STALE" not in msg
    assert "下午" in msg


# ── Combined sanity ─────────────────────────────────────────────────────


def test_message_full_payload_has_three_sections():
    state = {
        "user_text": "你會做什麼",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    assert "[語音輸入]" in msg
    assert "[環境]" in msg
    assert "[能力]" in msg
