"""Rule-based conversation mode classifier — OpenClaw-lite L8 hook lite.

Used by _build_user_message and graph.py to decide whether to inject
CAPABILITIES.md and capability_context JSON.

Order matters: safety > identity > capability_question > action_request > chat (default).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1C
"""
from __future__ import annotations
import re
from typing import Final

# Patterns ordered by priority (safety checked first)
# 5/9 review: regex broadened — "介紹一下" / "介紹一下你自己" / "自我介紹"
# / "介紹一下 PawAI" all previously missed and fell to chat mode (then got
# capability JSON injected → feature-list answer).
MODE_PATTERNS: Final[list[tuple[str, str]]] = [
    (
        "safety",
        r"停|停止|不要動|別動|先不要動|小心|警告|危險|stop",
    ),
    (
        "identity",
        # Order: most specific first
        r"你是誰|你叫什麼|你叫啥|你誰啊|你是\s*AI"
        r"|自我介紹|介紹.{0,5}(自己|你|妳|PawAI|paw\s*ai)"
        r"|介紹一下"  # bare "介紹一下" — chat continuation, still identity-flavoured
        r"|你會做(自我介紹|介紹)",
    ),
    (
        "capability_question",
        r"你會(什麼|啥|哪些|做什麼|做啥)"
        r"|(有|你有)(什麼|哪些)(功能|能力|技能)"
        r"|能做(什麼|啥)"
        r"|功能有(哪些|什麼)",
    ),
    (
        "action_request",
        r"扭|搖|伸|懶腰|揮|過來|坐下|跳舞|走|看[你我].*OK|比.*OK",
    ),
]


def classify_mode(user_text: str) -> str:
    """Return conversation mode: safety / identity / capability_question / action_request / chat.

    Default: "chat" when no pattern matches.
    """
    text = (user_text or "").strip()
    if not text:
        return "chat"
    for mode, pattern in MODE_PATTERNS:
        if re.search(pattern, text):
            return mode
    return "chat"
