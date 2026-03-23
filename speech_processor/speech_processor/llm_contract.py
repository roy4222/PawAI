#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""LLM response contract — pure Python constants and parsing, no ROS2 dependency.

Extracted from llm_bridge_node.py to allow standalone testing in CI.
"""

import json


# ── Skill → Go2 Command mapping (spec §3) ──────────────────────────────
# api_id 權威來源：go2_robot_sdk/domain/constants/robot_commands.py (ROBOT_CMD)
_HELLO = 1016
_STOP_MOVE = 1003
_SIT = 1009
_STAND_UP = 1004
_CONTENT = 1020

SKILL_TO_CMD = {
    "hello":     {"api_id": _HELLO, "parameter": str(_HELLO)},
    "stop_move": {"api_id": _STOP_MOVE, "parameter": str(_STOP_MOVE)},
    "sit":       {"api_id": _SIT, "parameter": str(_SIT)},
    "stand":     {"api_id": _STAND_UP, "parameter": str(_STAND_UP)},
    "content":   {"api_id": _CONTENT, "parameter": str(_CONTENT)},
}

BANNED_API_IDS = {1030, 1031, 1301}  # FrontFlip, FrontJump, Handstand

# P0 today: only these skills are validated
P0_SKILLS = {"hello", "stop_move", "sit", "stand"}

# Required fields in every LLM JSON response
LLM_REQUIRED_FIELDS = {"intent", "reply_text", "selected_skill", "reasoning", "confidence"}


def strip_markdown_fences(raw: str) -> str:
    """Strip markdown code fences that LLMs sometimes wrap around JSON."""
    content = raw.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]  # remove ```json line
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    return content.strip()


def parse_llm_response(raw: str):
    """Parse and validate an LLM response string.

    Returns the parsed dict on success, or None on failure.
    """
    try:
        content = strip_markdown_fences(raw)
        result = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(result, dict):
        return None
    if not LLM_REQUIRED_FIELDS.issubset(result.keys()):
        return None
    return result
