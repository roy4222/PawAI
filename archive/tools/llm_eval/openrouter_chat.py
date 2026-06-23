#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Lightweight OpenRouter chat helper — used by mock_server and smoke tests.

Why not import from llm_bridge_node? That module imports rclpy / std_msgs
which only resolve inside a ROS workspace. mock_server runs in a plain
Python venv (no ROS), so we keep this helper standalone.

Schema contract: returns the same bridge-shape dict as
llm_bridge_node._call_openrouter (intent / reply_text / selected_skill /
reasoning / confidence) so downstream consumers can re-use existing
parsing.

Usage:
    from openrouter_chat import chat

    # Sync — for mock_server thread / scripts
    result = chat("你好啊")
    if result["ok"]:
        print(result["reply_text"])
    else:
        print(f"failed: {result['error_kind']}")

Cost guard: this module is single-shot only. Callers (e.g. mock_server)
must rate-limit themselves. Default timeout 5s; default model is
gemini-3-flash-preview.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


_DEFAULT_MODEL = "google/gemini-3-flash-preview"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default persona lives next to this file. Caller can override.
_DEFAULT_PERSONA = Path(__file__).resolve().parent / "persona.txt"

# Skills that the legacy bridge can map to a Go2 motion command.
# Mirrors speech_processor/llm_contract.SKILL_TO_CMD; duplicated here so
# this module stays self-contained.
_LEGACY_P0_SKILLS = frozenset({"hello", "stop_move", "sit", "stand", "content"})

# Skill → intent inference (for mock_server which doesn't run brain rules).
_SKILL_TO_INTENT = {
    # Legacy P0 skills (in SKILL_TO_CMD)
    "hello": "greet",
    "stop_move": "stop",
    "sit": "sit",
    "stand": "stand",
    "content": "chat",
    # Phase B Active skills (eval persona vocabulary)
    "sit_along": "sit",
    "wave_hello": "greet",
    "greet_known_person": "greet",
    "show_status": "status",
    "self_introduce": "greet",
    "stranger_alert": "stranger",
    "fallen_alert": "fallen",
}


def _load_persona(persona_path: Path | str | None) -> str:
    """Load persona text. None / missing file → minimal fallback."""
    if persona_path is None:
        persona_path = _DEFAULT_PERSONA
    p = Path(persona_path)
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return (
            "你是 PawAI，居家互動機器狗。回覆嚴格 JSON："
            '{"reply": "<繁體中文 ≤25 字>", "skill": "chat_reply", "args": {}}'
        )


def _strip_markdown_fences(raw: str) -> str:
    content = raw.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1] if "\n" in content else content
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    return content.strip()


def _parse_eval_or_legacy(raw: str) -> dict | None:
    """Try to parse model reply as eval schema {reply, skill, args}.
    Falls back to legacy bridge schema if persona was the legacy one.
    Returns dict on success, None on parse failure.
    """
    try:
        obj = json.loads(_strip_markdown_fences(raw))
    except (ValueError, TypeError):
        # Salvage: regex-extract a "reply" string for graceful degradation.
        m = re.search(r'"reply"\s*:\s*"([^"]+)"', raw)
        if m:
            return {"reply": m.group(1), "skill": None, "args": {}}
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _adapt_to_bridge_schema(parsed: dict) -> dict:
    """Convert eval schema {reply, skill, args} OR legacy schema directly
    into the bridge schema {intent, reply_text, selected_skill, reasoning,
    confidence}. Audio tags are preserved verbatim — caller decides whether
    to strip for downstream renderers.
    """
    # Already legacy schema?
    if "reply_text" in parsed and "selected_skill" in parsed:
        try:
            confidence = float(parsed.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        return {
            "intent": str(parsed.get("intent") or "chat"),
            "reply_text": str(parsed.get("reply_text") or "").strip(),
            "selected_skill": parsed.get("selected_skill"),
            "reasoning": str(parsed.get("reasoning") or "openrouter"),
            "confidence": confidence,
        }

    # Eval schema → bridge schema.
    raw_skill = parsed.get("skill")
    selected_skill = None
    if isinstance(raw_skill, str):
        s = raw_skill.strip()
        if s in _LEGACY_P0_SKILLS:
            selected_skill = s

    intent = "chat"
    if isinstance(raw_skill, str) and raw_skill.strip() in _SKILL_TO_INTENT:
        intent = _SKILL_TO_INTENT[raw_skill.strip()]

    return {
        "intent": intent,
        "reply_text": str(parsed.get("reply") or "").strip(),
        "selected_skill": selected_skill,
        "reasoning": "openrouter:eval_schema",
        "confidence": 0.8,
    }


def chat(
    user_text: str,
    *,
    persona_path: Path | str | None = None,
    model_slug: str = _DEFAULT_MODEL,
    timeout_s: float = 5.0,
    api_key: str | None = None,
    base_url: str = _DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """Call OpenRouter chat completions with PawAI persona.

    Returns:
        {
          "ok": True,
          "reply_text": "...",
          "selected_skill": "..."|None,
          "intent": "...",
          "raw_skill": "..." (the model's original skill name even if not P0),
          "latency_s": float,
          "raw_response": <openrouter dict>
        }
        OR
        {
          "ok": False,
          "error_kind": "no_key" | "no_requests" | "timeout" | "connection"
                        | "http" | "parse",
          "error": "<human-readable>",
          "latency_s": float,
        }
    """
    t0 = time.monotonic()

    if requests is None:
        return {
            "ok": False,
            "error_kind": "no_requests",
            "error": "requests library not installed",
            "latency_s": 0.0,
        }

    key = (
        api_key
        or os.environ.get("OPENROUTER_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or ""
    ).strip()
    if not key:
        return {
            "ok": False,
            "error_kind": "no_key",
            "error": "OPENROUTER_KEY / OPENROUTER_API_KEY not set",
            "latency_s": 0.0,
        }

    persona = _load_persona(persona_path)
    body = {
        "model": model_slug,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.6,
        "max_tokens": 500,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/roy422/elder_and_dog",
        "X-Title": "PawAI Studio Mock Chat",
    }

    try:
        resp = requests.post(base_url, json=body, headers=headers, timeout=timeout_s)
    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "error_kind": "timeout",
            "error": f"openrouter call exceeded {timeout_s}s",
            "latency_s": time.monotonic() - t0,
        }
    except requests.exceptions.ConnectionError as exc:
        return {
            "ok": False,
            "error_kind": "connection",
            "error": f"connection refused: {exc}",
            "latency_s": time.monotonic() - t0,
        }
    except requests.exceptions.RequestException as exc:
        return {
            "ok": False,
            "error_kind": "http",
            "error": f"request error: {exc}",
            "latency_s": time.monotonic() - t0,
        }

    latency = time.monotonic() - t0

    if resp.status_code != 200:
        return {
            "ok": False,
            "error_kind": "http",
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            "latency_s": latency,
        }

    try:
        data = resp.json()
        raw_content = data["choices"][0]["message"].get("content")
    except (KeyError, IndexError, ValueError) as exc:
        return {
            "ok": False,
            "error_kind": "parse",
            "error": f"response structure: {exc}",
            "latency_s": latency,
        }

    if not isinstance(raw_content, str) or not raw_content.strip():
        return {
            "ok": False,
            "error_kind": "parse",
            "error": "empty content (model returned reasoning only?)",
            "latency_s": latency,
        }

    parsed = _parse_eval_or_legacy(raw_content)
    if parsed is None:
        return {
            "ok": False,
            "error_kind": "parse",
            "error": f"JSON parse failed: {raw_content[:200]}",
            "latency_s": latency,
        }

    bridge = _adapt_to_bridge_schema(parsed)
    raw_skill = parsed.get("skill") if "reply_text" not in parsed else parsed.get("selected_skill")

    return {
        "ok": True,
        "reply_text": bridge["reply_text"],
        "selected_skill": bridge["selected_skill"],
        "intent": bridge["intent"],
        "raw_skill": raw_skill,  # may be wave_hello/sit_along etc; not in P0 set
        "confidence": bridge["confidence"],
        "latency_s": latency,
        "raw_response": data,
    }


# Convenience CLI for ad-hoc smoke without the test harness.
if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or "你好啊"
    result = chat(text)
    if result["ok"]:
        print(f"[{result['latency_s']:.2f}s] reply: {result['reply_text']!r}")
        print(f"        skill: {result['selected_skill']}  raw_skill: {result['raw_skill']}")
        print(f"        intent: {result['intent']}")
    else:
        print(f"FAIL ({result['error_kind']}): {result['error']}", file=sys.stderr)
        sys.exit(1)
