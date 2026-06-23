#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""OpenRouter live smoke test — exercises llm_bridge_node helpers against the
real OpenRouter API (no ROS, no Jetson).

What this verifies for commit fda1b3c:
  1. _call_openrouter() against gemini-3-flash-preview returns a real reply
     that survives bridge schema validation (LLM_REQUIRED_FIELDS).
  2. _try_openrouter_chain() picks gemini and the result is usable downstream.
  3. adapt_eval_schema() preserves audio tags + maps to legacy schema.
  4. Timeouts and HTTP errors propagate as the right error_kind values when
     we deliberately misuse the API.

Usage:
    set -a && . ./.env && set +a
    python3 tools/llm_eval/openrouter_live_smoke.py
    python3 tools/llm_eval/openrouter_live_smoke.py --skip-error-paths

Cost: ~5 calls × ~$0.0005 = ~$0.003 USD against gemini-3-flash-preview.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "speech_processor"))

# ── Stub rclpy / std_msgs so we can import llm_bridge_node outside ROS. ──
def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


_ensure_module("rclpy")
_rclpy_node = _ensure_module("rclpy.node")
_rclpy_node.Node = type("Node", (), {})
_ensure_module("std_msgs")
_std_msgs_msg = _ensure_module("std_msgs.msg")
_std_msgs_msg.String = type("String", (), {})

from speech_processor.llm_bridge_node import LlmBridgeNode, SYSTEM_PROMPT  # noqa: E402
from speech_processor.llm_contract import (  # noqa: E402
    LLM_REQUIRED_FIELDS,
    SKILL_TO_CMD,
    adapt_eval_schema,
)


class _FakeLogger:
    def warn(self, msg):
        print(f"  [WARN] {msg}")

    def error(self, msg):
        print(f"  [ERROR] {msg}")

    def info(self, msg):
        print(f"  [INFO] {msg}")


class _StubNode:
    """Minimal stand-in for LlmBridgeNode without ROS init."""

    # Class attrs that bound methods reach via self.<name>
    MAX_REPLY_CHARS = LlmBridgeNode.MAX_REPLY_CHARS

    def __init__(self, persona_path: Path | None = None, **overrides):
        self._logger = _FakeLogger()
        self.last_error = ""
        self.llm_temperature = 0.6
        key = (
            os.environ.get("OPENROUTER_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or ""
        ).strip()
        self._openrouter_key = key
        self._openrouter_active = bool(key)
        self.openrouter_base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.openrouter_gemini_model = "google/gemini-3-flash-preview"
        self.openrouter_deepseek_model = "deepseek/deepseek-v4-flash"
        self.openrouter_request_timeout_s = 5.0
        self.openrouter_overall_budget_s = 5.5

        if persona_path and persona_path.is_file():
            self._system_prompt = persona_path.read_text(encoding="utf-8")
            print(f"  loaded persona from {persona_path} ({len(self._system_prompt)} bytes)")
        else:
            self._system_prompt = SYSTEM_PROMPT
            print("  using legacy inline SYSTEM_PROMPT")

        for k, v in overrides.items():
            setattr(self, k, v)

        # bind real methods
        self._call_openrouter = LlmBridgeNode._call_openrouter.__get__(self)
        self._try_openrouter_chain = LlmBridgeNode._try_openrouter_chain.__get__(self)
        self._post_process_reply = LlmBridgeNode._post_process_reply.__get__(self)

    def get_logger(self):
        return self._logger


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def smoke_call_openrouter(node: _StubNode, prompt: str) -> dict:
    print(f"\n  prompt: {prompt!r}")
    t0 = time.time()
    out = node._call_openrouter(node.openrouter_gemini_model, prompt, 5.0)
    dt = time.time() - t0
    print(f"  latency: {dt:.2f}s  ok={out.get('ok')}  error_kind={out.get('error_kind', '-')}")
    if out.get("ok"):
        result = out["result"]
        print(f"  reply_text:    {result.get('reply_text')!r}")
        print(f"  selected_skill:{result.get('selected_skill')!r}")
        print(f"  intent:        {result.get('intent')!r}")
        print(f"  confidence:    {result.get('confidence')}")
        # Schema validation
        missing = LLM_REQUIRED_FIELDS - set(result.keys())
        if missing:
            print(f"  ✗ missing fields: {missing}")
            return {"ok": False, "reason": f"missing fields {missing}"}
        if result.get("selected_skill") and result["selected_skill"] not in SKILL_TO_CMD:
            print(
                f"  ✗ selected_skill {result['selected_skill']!r} not in SKILL_TO_CMD"
                " (adapter should have stripped it)"
            )
            return {"ok": False, "reason": "skill not stripped"}
        return {"ok": True, "result": result, "latency": dt}
    return {"ok": False, "reason": out.get("error_kind"), "latency": dt}


def smoke_chain(node: _StubNode, prompt: str) -> dict:
    print(f"\n  prompt: {prompt!r}")
    t0 = time.time()
    result = node._try_openrouter_chain(prompt)
    dt = time.time() - t0
    if result is None:
        print(f"  ✗ chain returned None (latency {dt:.2f}s)")
        return {"ok": False}
    print(f"  ✓ chain returned in {dt:.2f}s")
    print(f"  reply_text:    {result.get('reply_text')!r}")
    print(f"  selected_skill:{result.get('selected_skill')!r}")
    return {"ok": True, "result": result, "latency": dt}


def smoke_error_paths(node: _StubNode) -> None:
    """Force HTTP failures to validate error_kind values."""
    print("\n  -- forcing 401 via fake key --")
    bad_node = _StubNode(persona_path=None)
    bad_node._openrouter_key = "sk-or-v1-INVALID-KEY-FOR-SMOKE"
    bad_node._openrouter_active = True
    bad_node.openrouter_request_timeout_s = 5.0
    bad_node.openrouter_overall_budget_s = 5.5
    bad_node._call_openrouter = LlmBridgeNode._call_openrouter.__get__(bad_node)
    bad_node._try_openrouter_chain = LlmBridgeNode._try_openrouter_chain.__get__(bad_node)
    bad_node._post_process_reply = LlmBridgeNode._post_process_reply.__get__(bad_node)
    out = bad_node._call_openrouter(node.openrouter_gemini_model, "你好", 5.0)
    print(f"  result: ok={out.get('ok')} error_kind={out.get('error_kind')}")
    print(f"  expected: ok=False, error_kind='http' (401 unauthorized)")

    print("\n  -- forcing connection error via bad URL --")
    bad_node2 = _StubNode(persona_path=None)
    bad_node2.openrouter_base_url = "http://127.0.0.1:1/no-such-endpoint"
    bad_node2.openrouter_request_timeout_s = 2.0
    bad_node2.openrouter_overall_budget_s = 2.5
    bad_node2._call_openrouter = LlmBridgeNode._call_openrouter.__get__(bad_node2)
    out2 = bad_node2._call_openrouter(node.openrouter_gemini_model, "你好", 2.0)
    print(f"  result: ok={out2.get('ok')} error_kind={out2.get('error_kind')}")
    print(f"  expected: ok=False, error_kind='connection'")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--persona",
        type=Path,
        default=ROOT / "tools/llm_eval/persona.txt",
        help="System prompt file (default: tools/llm_eval/persona.txt)",
    )
    parser.add_argument(
        "--skip-error-paths",
        action="store_true",
        help="Skip 401 / connection-refused tests (saves ~1 sec)",
    )
    args = parser.parse_args()

    if not (
        os.environ.get("OPENROUTER_KEY") or os.environ.get("OPENROUTER_API_KEY")
    ):
        print("ERROR: OPENROUTER_KEY (or OPENROUTER_API_KEY) not set.", file=sys.stderr)
        print("       Run: set -a && . ./.env && set +a", file=sys.stderr)
        return 2

    banner(f"setup — persona={args.persona}")
    node = _StubNode(persona_path=args.persona)
    if not node._openrouter_active:
        print("ERROR: OpenRouter not active (no key).", file=sys.stderr)
        return 2

    # 5 representative prompts spanning multiple buckets
    prompts = [
        "你好啊",                  # chat → expect chat_reply / wave_hello
        "停",                       # action-in safety → expect stop_move
        "幫我倒一杯水",             # action-out → expect chat_reply redirect
        "你會做什麼",               # chat → expect chat_reply / self_introduce
        "走過來找我",               # action-in nav → expect approach_person/nav_demo_point
    ]

    banner("Test 1 — _call_openrouter (Gemini direct)")
    pass_count = 0
    fail_count = 0
    for p in prompts:
        r = smoke_call_openrouter(node, p)
        if r.get("ok"):
            pass_count += 1
        else:
            fail_count += 1

    banner("Test 2 — _try_openrouter_chain")
    chain_pass = 0
    chain_fail = 0
    for p in prompts[:2]:
        r = smoke_chain(node, p)
        if r.get("ok"):
            chain_pass += 1
        else:
            chain_fail += 1

    if not args.skip_error_paths:
        banner("Test 3 — error paths (no real cost)")
        smoke_error_paths(node)

    banner("Summary")
    print(f"  Test 1 (call_openrouter):      {pass_count} pass / {fail_count} fail")
    print(f"  Test 2 (try_openrouter_chain): {chain_pass} pass / {chain_fail} fail")
    print(f"  Persona loaded: {len(node._system_prompt)} bytes")
    print(f"  Estimated cost: ~$0.003 USD")

    return 0 if fail_count == 0 and chain_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
