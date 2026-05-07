"""RuleBrain say_canned templates — wrapper-level emergency fallback.

Used when:
  - graph fatal exception (wrapper catch-all)
  - llm_decision exhausted retries and repair_failed
  - skill_policy_gate normalised away to None but reply_text was empty

Templates copied verbatim from llm_bridge_node REPLY_TEMPLATES /
RULE_SKILL_MAP so legacy and pawai_brain emit the same tone.
"""
from __future__ import annotations


REPLY_TEMPLATES: dict[str, str] = {
    "greet": "[excited] 嗨！我在這裡，今天過得怎麼樣？",
    "come_here": "[playful] 收到，我馬上過去找你！",
    "stop": "好的，我停下來。",
    "sit": "[playful] 好喔，我坐下囉。",
    "stand": "[excited] 好，我站起來！",
    "take_photo": "[curious] 收到，我來拍張照。",
    "status": "我現在狀態還不錯，感官都正常喔。",
    "unknown": "[curious] 欸我沒聽清楚，可以再講一次嗎？",
}

RULE_SKILL_MAP: dict[str, str | None] = {
    "greet": "hello",
    "stop": "stop_move",
    "sit": "sit",
    "stand": "stand",
}


# Keyword → intent (cheap classifier for wrapper fallback path).
# Order matters: scan left-to-right, first match wins.
_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("停", "stop", "暫停", "煞車", "緊急"), "stop"),
    (("坐下", "坐"), "sit"),
    (("站起來", "起來", "站好", "stand"), "stand"),
    (("你好", "嗨", "hi", "hello"), "greet"),
    (("狀態", "怎麼樣", "在做什麼"), "status"),
]


def classify_intent(text: str) -> str:
    """Cheap keyword-based intent classifier for emergency fallback path."""
    if not text:
        return "unknown"
    lower = text.lower()
    for kws, intent in _KEYWORDS:
        if any(kw in text or kw in lower for kw in kws):
            return intent
    return "unknown"


def fallback_reply(text: str) -> tuple[str, str, str | None]:
    """Pick a canned reply for the given user_text.

    Returns:
        (reply_text, intent, selected_skill)
    """
    intent = classify_intent(text)
    reply = REPLY_TEMPLATES.get(intent, REPLY_TEMPLATES["unknown"])
    skill = RULE_SKILL_MAP.get(intent)
    return reply, intent, skill
