"""Unit tests for mode_classifier — 5-mode rule-based classifier.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1C
"""
from __future__ import annotations
import pytest

from pawai_brain.nodes.mode_classifier import classify_mode


@pytest.mark.parametrize("text,expected", [
    # Safety
    ("停！", "safety"),
    ("小心一點", "safety"),
    ("stop", "safety"),
    ("不要動", "safety"),
    ("危險！", "safety"),
    # N4: self_intro_request — formal "please introduce yourself" for demo.
    # Stricter than identity; matched first.
    ("自我介紹", "self_intro_request"),
    ("介紹一下你自己", "self_intro_request"),
    ("介紹一下 PawAI", "self_intro_request"),
    ("我現在在跟教授 demo，你自我介紹一下自己", "self_intro_request"),
    ("跟教授介紹一下", "self_intro_request"),
    # N8 (2026-05-11): 「跟大家/教授打招呼」現在走 chat path（讓 LLM 自然
    # 問候 + wave_hello），不再強迫走 5 段 self_intro。
    ("跟大家打個招呼", "chat"),
    ("跟教授打個招呼", "chat"),
    ("詳細介紹一下你自己", "self_intro_request"),
    ("介紹一下你的功能", "self_intro_request"),
    ("完整介紹", "self_intro_request"),
    # N5: scene_query — integrate face+pose+gesture+objects to describe scene.
    ("你看到什麼？", "scene_query"),
    ("看到什麼", "scene_query"),
    ("看到啥", "scene_query"),
    ("我在幹嘛", "scene_query"),
    ("我在幹嘛？", "scene_query"),
    ("你覺得我在做什麼", "scene_query"),
    ("你猜我在做什麼", "scene_query"),
    ("我看起來像什麼", "scene_query"),
    ("我看起來怎樣", "scene_query"),
    ("現場有什麼", "scene_query"),
    ("這裡有什麼", "scene_query"),
    ("我現在是站著還是坐著", "scene_query"),
    # Identity (casual "who are you") — terse persona-only path
    ("你是誰？", "identity"),
    ("你叫什麼", "identity"),
    ("你叫啥", "identity"),
    ("介紹一下", "identity"),  # bare — chat continuation, still casual
    ("介紹一下你", "identity"),  # "你" without "自己" → still identity
    # Capability question
    ("你會什麼？", "capability_question"),
    ("有什麼功能", "capability_question"),
    ("能做什麼", "capability_question"),
    ("你有哪些能力", "capability_question"),
    # 5/9 review additions
    ("你會啥", "capability_question"),
    ("你會哪些", "capability_question"),
    ("功能有哪些", "capability_question"),
    # Action request
    ("扭一下", "action_request"),
    ("伸個懶腰", "action_request"),
    ("揮個手", "action_request"),
    # 學校招生 demo (2026-05-16) — school_demo_request 觸發輔大 facts 注入。
    # 每條都必須含「輔大 / 輔仁」校名錨點。
    ("輔大資管", "school_demo_request"),
    ("輔仁資管", "school_demo_request"),
    ("輔大資管系有什麼特色", "school_demo_request"),
    ("介紹輔大資管", "school_demo_request"),
    ("輔仁大學的資管系怎麼樣", "school_demo_request"),
    ("輔仁大學資訊管理系特色", "school_demo_request"),
    ("輔仁大學的資訊管理系", "school_demo_request"),
    ("為什麼要讀輔大資管", "school_demo_request"),
    ("為什麼選輔大資管系", "school_demo_request"),
    # 順序 regression：必須在 self_intro_request 之前判定，否則「跟大家介紹」
    # 會被 self_intro_request 的 「跟\s*(教授|大家|觀眾|評審).{0,5}介紹」吃掉。
    ("請跟大家介紹輔大資管系特色", "school_demo_request"),
    ("跟教授介紹輔大資管", "school_demo_request"),
    # 負面：其他學校的「資管系特色」絕對不能注入輔大 facts
    ("台大資管系特色", "chat"),
    ("政大資管系亮點", "chat"),
    ("資管系特色", "chat"),
    ("資管系亮點", "chat"),
    # 負面：一般「資訊管理」對話也不該誤觸
    ("我想念資訊管理", "chat"),
    ("資訊管理系都在學什麼", "chat"),
    # Chat (default)
    ("天氣好嗎", "chat"),
    ("我今天累了", "chat"),
    ("講個故事", "chat"),
])
def test_classify_mode(text, expected):
    assert classify_mode(text) == expected


def test_classify_mode_empty():
    assert classify_mode("") == "chat"
    assert classify_mode("   ") == "chat"


def test_classify_mode_safety_takes_priority():
    """Safety keywords override other patterns."""
    assert classify_mode("停，你是誰") == "safety"


def test_classify_mode_self_intro_beats_identity():
    """N4: self_intro_request must take priority over identity for explicit intro asks."""
    assert classify_mode("自我介紹一下") == "self_intro_request"
    assert classify_mode("你能完整介紹自己嗎") == "self_intro_request"


def test_classify_mode_scene_query_does_not_collide_with_capability():
    """N5: 'looking what' queries route to scene_query, NOT capability_question.
    Capability requires '你會' prefix, so '看到什麼' alone safely falls to scene."""
    assert classify_mode("看到什麼") == "scene_query"
    # But 'capability_question' still wins for '你會看到X' (你會 prefix).
    # (Currently no such ambiguous pattern in capability regex — safe.)


def test_classify_mode_scene_query_does_not_eat_planning_questions():
    """N5.1 review: '你覺得我...' must NOT auto-route to scene_query unless the
    phrasing is genuinely about the user's current scene/pose/action.
    Capability / planning / opinion questions should fall to chat (default)."""
    assert classify_mode("你覺得我該展示哪個功能") != "scene_query"
    assert classify_mode("你覺得我說得對嗎") != "scene_query"
    assert classify_mode("你覺得我這個想法怎樣") != "scene_query"
    # But scene-specific phrasings still route to scene_query:
    assert classify_mode("你覺得我在做什麼") == "scene_query"
    assert classify_mode("你覺得我看起來累不累") == "scene_query"
    assert classify_mode("你覺得我站著舒服嗎") == "scene_query"


def test_classify_mode_returns_string():
    result = classify_mode("嗨")
    assert isinstance(result, str)
    assert result in ("safety", "self_intro_request", "scene_query", "identity",
                       "capability_question", "action_request", "chat")
