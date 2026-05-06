#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for OpenRouter provider chain in llm_bridge_node (Phase B B1, 2026-05-04).

Covers:
- adapt_eval_schema() in llm_contract.py
- _call_openrouter() single-shot behaviour (mocked requests.post)
- _try_openrouter_chain() — Gemini primary + conditional DeepSeek fallback
- llm_persona_file ROS param load + fallback to inline SYSTEM_PROMPT

These tests do NOT call the real OpenRouter API. requests.post is fully mocked.
"""
from __future__ import annotations

import json
import os
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch


# ── Stub rclpy / std_msgs so we can import llm_bridge_node outside ROS ──
# These tests only exercise pure-Python helpers; we never spin a node.
def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


_rclpy = _ensure_module("rclpy")
_rclpy_node = _ensure_module("rclpy.node")
_rclpy_node.Node = type("Node", (), {})
_std_msgs = _ensure_module("std_msgs")
_std_msgs_msg = _ensure_module("std_msgs.msg")
_std_msgs_msg.String = type("String", (), {})

from speech_processor.llm_contract import (  # noqa: E402
    LLM_REQUIRED_FIELDS,
    SKILL_TO_CMD,
    adapt_eval_schema,
)


# ---------------------------------------------------------------------------
# adapt_eval_schema (no Node, pure function)
# ---------------------------------------------------------------------------


class TestAdaptEvalSchema(unittest.TestCase):
    def test_eval_schema_to_bridge_schema_basic(self):
        out = adapt_eval_schema({"reply": "嗨！", "skill": "wave_hello", "args": {}})
        self.assertEqual(set(out.keys()), LLM_REQUIRED_FIELDS)
        self.assertEqual(out["reply_text"], "嗨！")
        # wave_hello not in legacy SKILL_TO_CMD → stripped to None
        self.assertIsNone(out["selected_skill"])
        # but intent should still derive from raw skill
        self.assertEqual(out["intent"], "greet")

    def test_legacy_skill_kept(self):
        # 'hello' IS in SKILL_TO_CMD → kept
        out = adapt_eval_schema({"reply": "嗨", "skill": "hello"})
        self.assertEqual(out["selected_skill"], "hello")

    def test_unknown_skill_stripped(self):
        out = adapt_eval_schema({"reply": "看", "skill": "object_remark"})
        self.assertIsNone(out["selected_skill"])

    def test_stop_move_kept_and_intent_stop(self):
        out = adapt_eval_schema({"reply": "", "skill": "stop_move"})
        self.assertEqual(out["selected_skill"], "stop_move")
        self.assertEqual(out["intent"], "stop")

    def test_empty_input_safe(self):
        out = adapt_eval_schema({})
        self.assertEqual(set(out.keys()), LLM_REQUIRED_FIELDS)
        self.assertEqual(out["reply_text"], "")
        self.assertIsNone(out["selected_skill"])
        self.assertEqual(out["intent"], "chat")  # default fallback

    def test_explicit_intent_wins(self):
        out = adapt_eval_schema(
            {"reply": "嗨", "skill": "wave_hello", "intent": "smalltalk"}
        )
        self.assertEqual(out["intent"], "smalltalk")

    def test_confidence_clamped(self):
        out = adapt_eval_schema({"reply": "x", "confidence": 1.7})
        self.assertEqual(out["confidence"], 1.0)
        out = adapt_eval_schema({"reply": "x", "confidence": -0.5})
        self.assertEqual(out["confidence"], 0.0)
        out = adapt_eval_schema({"reply": "x", "confidence": "garbage"})
        self.assertEqual(out["confidence"], 0.8)  # default


# ---------------------------------------------------------------------------
# _call_openrouter / _try_openrouter_chain via a minimal node-like stub.
# We don't init rclpy / ROS — we instantiate a thin object that has only the
# attributes the methods touch, and bind the methods onto it.
# ---------------------------------------------------------------------------


class _FakeLogger:
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []

    def warn(self, msg):
        self.warnings.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def info(self, msg):
        self.infos.append(msg)


class _StubNode:
    """Minimal node with the attributes the OpenRouter helpers use."""

    def __init__(self, **overrides):
        import threading
        from collections import deque
        self._logger = _FakeLogger()
        self.last_error = ""
        self.llm_temperature = 0.6
        self.llm_max_tokens = 500
        self._openrouter_key = "sk-or-test"
        self._openrouter_active = True
        self.openrouter_base_url = "https://openrouter.test/v1/chat/completions"
        self.openrouter_gemini_model = "google/gemini-3-flash-preview"
        self.openrouter_deepseek_model = "deepseek/deepseek-v4-flash"
        self.openrouter_request_timeout_s = 2.0
        self.openrouter_overall_budget_s = 2.2
        self._system_prompt = "TEST PERSONA"
        # 5/5 night: conversation memory deque + lock; openrouter call reads them
        self._convo_history: deque = deque(maxlen=10)
        self._convo_lock = threading.Lock()
        for k, v in overrides.items():
            setattr(self, k, v)

    def get_logger(self):
        return self._logger

    # Bind real methods from the node.
    def _post_process_reply(self, result):
        # Mimic the simplest passthrough; real node truncates reply_text.
        return result


def _bind_methods(stub):
    """Attach the real methods from llm_bridge_node onto the stub."""
    from speech_processor.llm_bridge_node import LlmBridgeNode

    stub._call_openrouter = LlmBridgeNode._call_openrouter.__get__(stub)
    stub._try_openrouter_chain = LlmBridgeNode._try_openrouter_chain.__get__(stub)
    stub._load_system_prompt = LlmBridgeNode._load_system_prompt.__get__(stub)
    return stub


def _good_response(skill="wave_hello", reply="嗨！"):
    """Build a fake requests.Response with eval-schema content."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"reply": reply, "skill": skill, "args": {}})
                }
            }
        ]
    }
    return resp


class TestCallOpenRouter(unittest.TestCase):
    def setUp(self):
        self.stub = _bind_methods(_StubNode())

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_success_returns_bridge_schema(self, mock_post):
        mock_post.return_value = _good_response(skill="hello", reply="嗨")
        out = self.stub._call_openrouter("google/gemini-3-flash-preview", "hi", 2.0)
        self.assertTrue(out["ok"])
        # Result must include all required legacy fields plus Phase 0.5 proposal fields
        self.assertTrue(LLM_REQUIRED_FIELDS.issubset(set(out["result"].keys())))
        self.assertEqual(out["result"]["selected_skill"], "hello")

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_timeout_returns_error_kind_timeout(self, mock_post):
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout()
        out = self.stub._call_openrouter("g", "hi", 0.5)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error_kind"], "timeout")

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_connection_refused_returns_error_kind_connection(self, mock_post):
        from requests.exceptions import ConnectionError as ReqConnErr

        mock_post.side_effect = ReqConnErr()
        out = self.stub._call_openrouter("g", "hi", 1.0)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error_kind"], "connection")

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_http_401_returns_error_kind_http(self, mock_post):
        resp = MagicMock()
        resp.status_code = 401
        resp.text = "unauthorized"
        mock_post.return_value = resp
        out = self.stub._call_openrouter("g", "hi", 1.0)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error_kind"], "http")

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_malformed_json_returns_error_kind_parse(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": '{"reply": "[curi'}}]
        }
        mock_post.return_value = resp
        out = self.stub._call_openrouter("g", "hi", 1.0)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error_kind"], "parse")


class TestTryOpenrouterChain(unittest.TestCase):
    def setUp(self):
        self.stub = _bind_methods(_StubNode())

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_gemini_success_skips_deepseek(self, mock_post):
        mock_post.return_value = _good_response(skill="hello")
        out = self.stub._try_openrouter_chain("hi")
        self.assertIsNotNone(out)
        self.assertEqual(out["selected_skill"], "hello")
        # only 1 HTTP call
        self.assertEqual(mock_post.call_count, 1)

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_gemini_timeout_does_not_try_deepseek(self, mock_post):
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout()
        out = self.stub._try_openrouter_chain("hi")
        self.assertIsNone(out)
        # 1 call (gemini), then short-circuit — no deepseek attempt
        self.assertEqual(mock_post.call_count, 1)

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_gemini_401_falls_through_to_deepseek_within_budget(self, mock_post):
        # First call: gemini → 401 (fast fail)
        # Second call: deepseek → success
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = "unauth"
        mock_post.side_effect = [resp_401, _good_response(skill="hello")]
        out = self.stub._try_openrouter_chain("hi")
        self.assertIsNotNone(out)
        self.assertEqual(mock_post.call_count, 2)

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_gemini_connection_refused_tries_deepseek(self, mock_post):
        from requests.exceptions import ConnectionError as ReqConnErr

        mock_post.side_effect = [ReqConnErr(), _good_response(skill="sit")]
        out = self.stub._try_openrouter_chain("hi")
        self.assertIsNotNone(out)
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(out["selected_skill"], "sit")

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_overall_budget_caps_deepseek_attempt(self, mock_post):
        # If less than 300ms left in budget, DeepSeek not attempted.
        from requests.exceptions import ConnectionError as ReqConnErr

        # Tighten budget so even fast gemini fail leaves <300ms.
        self.stub.openrouter_overall_budget_s = 0.05  # 50ms
        # Simulate connection error that takes effectively 0ms but budget already
        # < 300ms remaining → DeepSeek skipped.
        mock_post.side_effect = ReqConnErr()
        out = self.stub._try_openrouter_chain("hi")
        self.assertIsNone(out)
        # only gemini attempted
        self.assertEqual(mock_post.call_count, 1)

    @patch("speech_processor.llm_bridge_node.requests.post")
    def test_disabled_when_no_key(self, mock_post):
        self.stub._openrouter_key = ""
        self.stub._openrouter_active = False
        out = self.stub._try_openrouter_chain("hi")
        self.assertIsNone(out)
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# llm_persona_file load
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt(unittest.TestCase):
    def test_empty_path_uses_inline(self):
        from speech_processor.llm_bridge_node import SYSTEM_PROMPT

        stub = _bind_methods(_StubNode(llm_persona_file=""))
        prompt = stub._load_system_prompt()
        self.assertEqual(prompt, SYSTEM_PROMPT)

    def test_file_load_succeeds(self):
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".txt", delete=False
        ) as f:
            f.write("CUSTOM PERSONA — eval schema {reply, skill, args}.\n")
            path = f.name
        try:
            stub = _bind_methods(_StubNode(llm_persona_file=path))
            prompt = stub._load_system_prompt()
            self.assertIn("CUSTOM PERSONA", prompt)
        finally:
            os.unlink(path)

    def test_missing_file_falls_back_to_inline(self):
        from speech_processor.llm_bridge_node import SYSTEM_PROMPT

        stub = _bind_methods(_StubNode(llm_persona_file="/nonexistent/persona.txt"))
        prompt = stub._load_system_prompt()
        self.assertEqual(prompt, SYSTEM_PROMPT)
        # And a warning was logged
        self.assertTrue(
            any("load failed" in w for w in stub._logger.warnings),
            stub._logger.warnings,
        )


if __name__ == "__main__":
    unittest.main()
