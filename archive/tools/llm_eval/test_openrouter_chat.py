#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for tools/llm_eval/openrouter_chat.py.

Mocks requests.post — no real API calls.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import openrouter_chat  # noqa: E402
from openrouter_chat import chat  # noqa: E402


def _good_response(skill: str = "wave_hello", reply: str = "[excited] 嗨！"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"reply": reply, "skill": skill, "args": {}}
                    )
                }
            }
        ]
    }
    return resp


class TestNoKey(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_no_key_returns_no_key_error(self):
        result = chat("你好")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "no_key")
        self.assertIn("not set", result["error"])


class TestSuccessPaths(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_eval_schema_to_bridge_legacy_skill_kept(self, mock_post):
        mock_post.return_value = _good_response(skill="hello", reply="嗨")
        result = chat("hi")
        self.assertTrue(result["ok"])
        self.assertEqual(result["reply_text"], "嗨")
        self.assertEqual(result["selected_skill"], "hello")  # in legacy P0 set
        self.assertEqual(result["raw_skill"], "hello")
        self.assertEqual(result["intent"], "greet")  # mapped from wave_hello variant

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_eval_schema_strips_unknown_skill(self, mock_post):
        mock_post.return_value = _good_response(skill="wave_hello", reply="嗨")
        result = chat("hi")
        self.assertTrue(result["ok"])
        self.assertIsNone(result["selected_skill"])  # not in P0
        self.assertEqual(result["raw_skill"], "wave_hello")

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_audio_tag_preserved(self, mock_post):
        mock_post.return_value = _good_response(
            skill="chat_reply", reply="[excited] 你好啊！"
        )
        result = chat("hi")
        self.assertTrue(result["ok"])
        self.assertIn("[excited]", result["reply_text"])

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-fallback"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_openrouter_api_key_env_also_works(self, mock_post):
        mock_post.return_value = _good_response()
        result = chat("hi")
        self.assertTrue(result["ok"])

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_explicit_api_key_arg_overrides_env(self, mock_post):
        mock_post.return_value = _good_response()
        # api_key kwarg used directly
        result = chat("hi", api_key="sk-explicit")
        self.assertTrue(result["ok"])
        # Verify request was made with explicit key
        call_kwargs = mock_post.call_args
        self.assertIn("Bearer sk-explicit", call_kwargs.kwargs["headers"]["Authorization"])

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_legacy_schema_bad_confidence_does_not_crash(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "intent": "chat",
                                "reply_text": "嗨",
                                "selected_skill": None,
                                "reasoning": "test",
                                "confidence": "high",
                            }
                        )
                    }
                }
            ]
        }
        mock_post.return_value = resp
        result = chat("hi")
        self.assertTrue(result["ok"])
        self.assertEqual(result["confidence"], 0.8)


class TestErrorPaths(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_timeout(self, mock_post):
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout()
        result = chat("hi", timeout_s=0.5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "timeout")

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_connection_refused(self, mock_post):
        from requests.exceptions import ConnectionError as ReqConnErr

        mock_post.side_effect = ReqConnErr("refused")
        result = chat("hi")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "connection")

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_http_401(self, mock_post):
        resp = MagicMock()
        resp.status_code = 401
        resp.text = '{"error":"unauthorized"}'
        mock_post.return_value = resp
        result = chat("hi")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "http")
        self.assertIn("401", result["error"])

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_malformed_json_parse_fail(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": '{"reply": "[curi'}}]
        }
        mock_post.return_value = resp
        result = chat("hi")
        # Regex salvage might rescue this — check both outcomes are reasonable.
        if result["ok"]:
            self.assertIn("curi", result["reply_text"])  # salvaged partial
        else:
            self.assertEqual(result["error_kind"], "parse")

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_empty_content_returns_parse_error(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": ""}}]}
        mock_post.return_value = resp
        result = chat("hi")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "parse")
        self.assertIn("empty", result["error"])

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_null_content_returns_parse_error(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": None}}]}
        mock_post.return_value = resp
        result = chat("hi")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_kind"], "parse")


class TestPersonaLoad(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_persona_default_path_loads(self, mock_post):
        # Default persona should load from tools/llm_eval/persona.txt
        mock_post.return_value = _good_response()
        chat("hi")
        body = mock_post.call_args.kwargs["json"]
        system_msg = body["messages"][0]["content"]
        # The shipped persona has skill list — should be > 100 bytes.
        self.assertGreater(len(system_msg), 100)

    @patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=True)
    @patch("openrouter_chat.requests.post")
    def test_missing_persona_file_uses_inline_fallback(self, mock_post):
        mock_post.return_value = _good_response()
        result = chat("hi", persona_path="/nonexistent/persona.txt")
        self.assertTrue(result["ok"])
        body = mock_post.call_args.kwargs["json"]
        system_msg = body["messages"][0]["content"]
        # Inline fallback contains "PawAI"
        self.assertIn("PawAI", system_msg)


if __name__ == "__main__":
    unittest.main()
