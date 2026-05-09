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
MODE_PATTERNS: Final[list[tuple[str, str]]] = [
    (
        "safety",
        r"停|停止|不要動|別動|先不要動|小心|警告|危險|stop",
    ),
    (
        "identity",
        r"你是誰|你叫什麼|介紹.*自己|你誰啊|你是\s*AI",
    ),
    (
        "capability_question",
        r"你會什麼|你會啥|有什麼功能|能做什麼|會做啥|有哪些能力|功能有哪些",
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
