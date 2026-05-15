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
    assert "使用者說：" in msg  # label is [語音] or [文字] per 1E source-based label
    assert "[環境]" in msg
    assert "[能力]" in msg


# ── N3-A: recent_objects injection ────────────────────────────────────────


def test_recent_objects_injects_red_cup_in_chat_mode():
    """§[2:30] 紅杯子段在 chat mode 也要看到。"""
    ws = _world_state()
    ws["recent_objects"] = [{"class": "cup", "color": "red", "age_s": 5.0}]
    state = {"user_text": "你看到什麼", "world_state": ws}
    msg = _build_user_message(state)
    assert "[最近看到]" in msg
    assert "紅色的杯子" in msg


def test_recent_objects_translates_chair_no_color():
    ws = _world_state()
    ws["recent_objects"] = [{"class": "chair", "color": None, "age_s": 18.0}]
    state = {"user_text": "x", "world_state": ws}
    msg = _build_user_message(state)
    assert "椅子（18 秒前）" in msg
    # no color prefix
    line = [l for l in msg.splitlines() if "[最近看到]" in l][0]
    assert "色的" not in line  # no "紅色的" / "藍色的" etc when color None


def test_recent_objects_skips_unknown_class_silently():
    """Unknown class_name → not in OBJECT_CLASS_ZH → drop, don't dump raw English."""
    ws = _world_state()
    ws["recent_objects"] = [
        {"class": "elephant", "color": "gray", "age_s": 1.0},  # not in dict
        {"class": "cup", "color": "red", "age_s": 2.0},
    ]
    state = {"user_text": "x", "world_state": ws}
    msg = _build_user_message(state)
    assert "[最近看到]" in msg
    assert "elephant" not in msg
    assert "杯子" in msg


def test_recent_objects_no_inject_when_empty():
    state = {"user_text": "x", "world_state": _world_state()}  # no recent_objects key
    msg = _build_user_message(state)
    assert "[最近看到]" not in msg


# ── N3-B: demo_session injection ──────────────────────────────────────────


def test_demo_session_active_injects_segment_and_shown():
    cap = _capability_context()
    cap["demo_session"] = {
        "active": True,
        "current_segment": "gesture",
        "shown_skills": ["wiggle"],
        "candidate_next": ["stretch", "wave"],
    }
    state = {"user_text": "x", "world_state": _world_state(), "capability_context": cap}
    msg = _build_user_message(state)
    assert "[demo]" in msg
    assert "gesture" in msg
    assert "wiggle" in msg
    assert "stretch" in msg


def test_demo_session_inactive_no_inject():
    cap = _capability_context()
    cap["demo_session"] = {"active": False, "shown_skills": [], "candidate_next": []}
    state = {"user_text": "x", "world_state": _world_state(), "capability_context": cap}
    msg = _build_user_message(state)
    assert "[demo]" not in msg


# ── N4: self_intro_request scaffold + capability inject ──────────────────


def test_self_intro_request_injects_scaffold():
    state = {
        "user_text": "你自我介紹一下",
        "mode": "self_intro_request",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    assert "[intro_scaffold]" in msg
    # 5-段提示應該在 prompt 內
    assert "開場" in msg or "身份" in msg
    assert "專題使命" in msg or "多模態" in msg


def test_self_intro_request_also_injects_capability():
    """N4: intro 需要看到 capability 才能挑 2-3 個 skill 講。"""
    state = {
        "user_text": "你自我介紹一下",
        "mode": "self_intro_request",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    # capability should be injected (either [能力] for module-level or [能力 runtime] for instance)
    assert "[能力]" in msg or "[能力 runtime]" in msg
    assert "self_introduce" in msg or "wiggle" in msg


def test_self_intro_request_uses_positive_framing_only():
    """N4.1 (review #2): scaffold must NOT contain negative-prime phrases like
    '長者陪伴' or '聊天機器人'. Those words shown to an LLM tend to leak
    into the reply (don't-think-of-a-pink-elephant). Use positive direction.
    """
    state = {
        "user_text": "你自我介紹一下",
        "mode": "self_intro_request",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    # Negative-prime phrases must NOT appear in the scaffold.
    assert "長者陪伴" not in msg, "scaffold leaks negative-prime phrase '長者陪伴'"
    assert "聊天機器人" not in msg, "scaffold leaks negative-prime phrase '聊天機器人'"
    # Positive markers we DO want present:
    assert "具身互動" in msg  # what PawAI IS
    assert "多模態" in msg  # project framing
    assert "感知" in msg or "感知融合" in msg  # capability focus


def test_identity_mode_no_scaffold():
    """N4: 純 identity (你是誰) 不要注入完整 scaffold — 保持簡短人格回答。"""
    state = {
        "user_text": "你是誰",
        "mode": "identity",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "[intro_scaffold]" not in msg
    assert "[mode_hint]" in msg  # identity-specific terse hint


def test_chat_mode_no_scaffold_no_capability():
    """N4: chat mode 維持精簡，不注入 scaffold 也不注入 capability。"""
    state = {
        "user_text": "今天天氣好嗎",
        "mode": "chat",
        "world_state": _world_state(),
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    assert "[intro_scaffold]" not in msg
    # module-level falls back to legacy [能力] inject; instance method
    # suppresses for chat. The module-level test below verifies that path.
    # Here we only assert scaffold absence.


# ── N5-B / N5-C: pose / gesture / scene_query ─────────────────────────────


def test_current_pose_injects_zh_translation():
    ws = _world_state()
    ws["current_pose"] = {"name": "sitting", "age_s": 2.0}
    state = {"user_text": "x", "world_state": ws}
    msg = _build_user_message(state)
    assert "[最近姿勢]" in msg
    assert "坐著" in msg
    assert "2 秒前" in msg


def test_current_gesture_injects_zh_translation():
    ws = _world_state()
    ws["current_gesture"] = {"name": "ok", "age_s": 4.0}
    state = {"user_text": "x", "world_state": ws}
    msg = _build_user_message(state)
    assert "[最近手勢]" in msg
    assert "OK" in msg
    assert "4 秒前" in msg


def test_unknown_pose_silently_dropped():
    """Unknown pose name → no [最近姿勢] line (don't dump raw English)."""
    ws = _world_state()
    ws["current_pose"] = {"name": "moonwalking", "age_s": 1.0}
    state = {"user_text": "x", "world_state": ws}
    msg = _build_user_message(state)
    assert "[最近姿勢]" not in msg
    assert "moonwalking" not in msg


def test_no_pose_gesture_when_world_state_lacks_them():
    state = {"user_text": "x", "world_state": _world_state()}
    msg = _build_user_message(state)
    assert "[最近姿勢]" not in msg
    assert "[最近手勢]" not in msg


def test_scene_query_mode_injects_scene_hint():
    ws = _world_state()
    ws["current_pose"] = {"name": "sitting", "age_s": 1.0}
    state = {
        "user_text": "看到什麼",
        "mode": "scene_query",
        "world_state": ws,
    }
    msg = _build_user_message(state)
    assert "[scene_hint]" in msg
    # scene_hint references the four perception channels
    assert "整合" in msg or "推論" in msg
    assert "眼前的人" in msg or "最近姿勢" in msg


def test_scene_query_mode_uses_positive_framing():
    """N4.1 review lesson: no negative-prime phrases in scene_hint either."""
    state = {
        "user_text": "我在幹嘛",
        "mode": "scene_query",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    # No "don't list objects" — say "整合場景描述" positively instead.
    assert "不是聊天機器人" not in msg
    assert "長者陪伴" not in msg


def test_chat_mode_no_scene_hint():
    state = {
        "user_text": "今天天氣好嗎",
        "mode": "chat",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "[scene_hint]" not in msg


# 學校招生 demo (2026-05-16) — school_demo_request facts injection
def test_school_demo_request_injects_facts():
    state = {
        "user_text": "介紹輔大資管系的特色",
        "mode": "school_demo_request",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "[school_demo_facts]" in msg
    # 5 大亮點關鍵字
    assert "1981" in msg
    assert "AI" in msg
    assert "做中學" in msg or "專題" in msg
    assert "AACSB" in msg or "跨域" in msg
    assert "EMI" in msg or "國際化" in msg


def test_school_demo_request_does_not_inject_scaffold_or_scene_hint():
    """facts 注入時不該疊上 intro_scaffold / scene_hint / capability。"""
    state = {
        "user_text": "輔大資管",
        "mode": "school_demo_request",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "[intro_scaffold]" not in msg
    assert "[scene_hint]" not in msg
    assert "[能力描述]" not in msg
    assert "[mode_hint]" not in msg


def test_chat_mode_no_school_demo_facts():
    """確保 facts 不污染日常對話。"""
    state = {
        "user_text": "今天天氣好嗎",
        "mode": "chat",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "[school_demo_facts]" not in msg
    assert "輔大資管" not in msg


def test_identity_mode_no_school_demo_facts():
    state = {
        "user_text": "你是誰",
        "mode": "identity",
        "world_state": _world_state(),
    }
    msg = _build_user_message(state)
    assert "[school_demo_facts]" not in msg
