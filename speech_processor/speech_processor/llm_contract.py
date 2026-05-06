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


# ── Eval-schema adapter (Phase B B1, 2026-05-04) ────────────────────────
#
# tools/llm_eval/persona.txt drives Gemini/DeepSeek with a *different* JSON
# schema than the legacy llm_bridge contract:
#
#   eval persona output:  {"reply": "...", "skill": "...", "args": {...}}
#   bridge contract:      {"intent": "...", "reply_text": "...",
#                          "selected_skill": "...", "reasoning": "...",
#                          "confidence": ...}
#
# adapt_eval_schema() converts the former into the latter so existing
# llm_bridge code paths (parse_llm_response, _enforce_reply_text_limit,
# _emit_chat_candidate, etc.) keep working unchanged.
#
# selected_skill: only kept if it's in the legacy bridge SKILL_TO_CMD set.
# The eval persona has 17 active skills; legacy bridge maps only 4 P0 skills
# to Go2 commands. Brain MVS skill arbitration is handled by Brain rules
# (deterministic), not by LLM — so dropping unmapped skills is safe.

# Heuristic intent inference from skill: keep small + obvious only.
_SKILL_TO_INTENT = {
    "stop_move": "stop",
    "sit": "sit",
    "sit_along": "sit",
    "stand": "stand",
    "wave_hello": "greet",
    "greet_known_person": "greet",
    "show_status": "status",
    "self_introduce": "greet",
    "stranger_alert": "stranger",
    "fallen_alert": "fallen",
    # everything else falls to default fallback intent
}


def adapt_eval_schema(eval_obj: dict, fallback_intent: str = "chat") -> dict:
    """Convert eval persona output → legacy bridge schema.

    Args:
        eval_obj: dict with optional keys {reply, skill, args, intent, confidence}.
        fallback_intent: intent to use when not derivable from skill.

    Returns:
        dict with all keys in LLM_REQUIRED_FIELDS, ready for the existing
        llm_bridge pipeline (parse_llm_response will accept it as-is).
    """
    if not isinstance(eval_obj, dict):
        eval_obj = {}

    reply_text = str(eval_obj.get("reply") or eval_obj.get("reply_text") or "").strip()

    raw_skill = eval_obj.get("skill") or eval_obj.get("selected_skill")
    selected_skill = None
    if isinstance(raw_skill, str):
        s = raw_skill.strip()
        # legacy bridge only knows the 4 P0 skills — strip everything else.
        if s in SKILL_TO_CMD:
            selected_skill = s

    # intent: prefer explicit, else derive from raw skill name, else fallback.
    intent = eval_obj.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        if isinstance(raw_skill, str) and raw_skill.strip() in _SKILL_TO_INTENT:
            intent = _SKILL_TO_INTENT[raw_skill.strip()]
        else:
            intent = fallback_intent
    else:
        intent = intent.strip()

    # confidence: clamp to [0, 1]; default 0.8 (came from a real LLM).
    raw_conf = eval_obj.get("confidence", 0.8)
    try:
        confidence = float(raw_conf)
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = max(0.0, min(1.0, confidence))

    return {
        "intent": intent,
        "reply_text": reply_text,
        "selected_skill": selected_skill,
        "reasoning": "openrouter:eval_schema",
        "confidence": confidence,
    }


# Persona skills that are semantically equivalent to "no side-effect proposal":
# the reply_text already conveys the action. Don't surface them as a skill
# proposal — brain_node would reject them as "rejected_not_allowed" on every
# normal chat turn, flooding Studio trace with spurious rejections.
_PASSTHROUGH_SKILLS = frozenset({"chat_reply", "say_canned"})


def extract_proposal(eval_obj: dict) -> dict:
    """Pull skill proposal fields from persona JSON, bypassing legacy filtering.

    Unlike adapt_eval_schema (which only keeps the 4 P0 legacy commands in
    selected_skill), this preserves any skill name. brain_node enforces its
    own allowlist downstream -- this is just a faithful pass-through.

    Skills in _PASSTHROUGH_SKILLS (chat_reply, say_canned) are semantically
    equivalent to "no side effect beyond saying the reply" — they map to
    proposed_skill=None so brain_node never sees them as a proposal at all.
    This is a semantic filter, not a policy gate (policy gating still lives
    in brain_node).

    Returns:
        dict with keys {proposed_skill, proposed_args, proposal_reason}.
        proposed_skill is None if persona did not include one or if the skill
        is a passthrough (SAY-only, no side effect).
    """
    if not isinstance(eval_obj, dict):
        eval_obj = {}

    raw_skill = eval_obj.get("skill")
    proposed_skill = raw_skill.strip() if isinstance(raw_skill, str) and raw_skill.strip() else None
    if proposed_skill in _PASSTHROUGH_SKILLS:
        proposed_skill = None

    raw_args = eval_obj.get("args")
    proposed_args = raw_args if isinstance(raw_args, dict) else {}

    return {
        "proposed_skill": proposed_skill,
        "proposed_args": proposed_args,
        "proposal_reason": "openrouter:eval_schema",
    }
