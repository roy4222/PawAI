#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for /api/text_input — both default offline mock and
MOCK_OPENROUTER=1 opt-in path. Uses FastAPI TestClient (no real network).
"""
from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _good_openrouter_response(skill: str = "wave_hello", reply: str = "[excited] 嗨"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {"message": {"content": json.dumps({"reply": reply, "skill": skill, "args": {}})}}
        ]
    }
    return resp


def _reload_mock_server():
    """Reload mock_server with current env vars (MOCK_OPENROUTER read at import)."""
    if "mock_server" in sys.modules:
        del sys.modules["mock_server"]
    import mock_server  # noqa: F401

    return sys.modules["mock_server"]


class TestDefaultOffline(unittest.TestCase):
    """No MOCK_OPENROUTER env → default canned reply with (mock) marker."""

    @patch.dict("os.environ", {}, clear=True)
    def test_text_input_returns_mock_canned(self):
        from fastapi.testclient import TestClient

        ms = _reload_mock_server()
        client = TestClient(ms.app)
        resp = client.post(
            "/api/text_input",
            json={"text": "你好", "request_id": "t1"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["mock"])
        self.assertFalse(body["openrouter"])

    @patch.dict("os.environ", {}, clear=True)
    def test_module_flag_disabled_when_env_unset(self):
        ms = _reload_mock_server()
        self.assertFalse(ms._MOCK_OPENROUTER_ENABLED)


class TestOptInWithKey(unittest.TestCase):
    """MOCK_OPENROUTER=1 + key → call OpenRouter (mocked)."""

    @patch.dict(
        "os.environ",
        {"MOCK_OPENROUTER": "1", "OPENROUTER_KEY": "sk-test"},
        clear=True,
    )
    def test_text_input_calls_openrouter_real_path(self):
        from fastapi.testclient import TestClient

        ms = _reload_mock_server()
        self.assertTrue(ms._MOCK_OPENROUTER_ENABLED)

        with patch("openrouter_chat.requests.post") as mock_post:
            mock_post.return_value = _good_openrouter_response(
                skill="wave_hello", reply="[excited] 嗨！"
            )
            client = TestClient(ms.app)
            resp = client.post(
                "/api/text_input",
                json={"text": "你好啊", "request_id": "t-or"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["openrouter"])
        self.assertIn("intent", body)
        self.assertEqual(body["raw_skill"], "wave_hello")

    @patch.dict(
        "os.environ",
        {"MOCK_OPENROUTER": "1", "OPENROUTER_KEY": "sk-test"},
        clear=True,
    )
    def test_text_input_falls_back_when_openrouter_fails(self):
        from fastapi.testclient import TestClient
        from requests.exceptions import Timeout

        ms = _reload_mock_server()
        with patch("openrouter_chat.requests.post") as mock_post:
            mock_post.side_effect = Timeout()
            client = TestClient(ms.app)
            resp = client.post(
                "/api/text_input",
                json={"text": "你好", "request_id": "t-fail"},
            )
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["openrouter"])
        self.assertEqual(body["openrouter_error"], "timeout")

    @patch.dict(
        "os.environ",
        {"MOCK_OPENROUTER": "1", "OPENROUTER_KEY": "sk-test"},
        clear=True,
    )
    def test_text_input_falls_back_when_helper_raises(self):
        from fastapi.testclient import TestClient

        ms = _reload_mock_server()
        with patch("mock_server._openrouter_chat") as mock_chat:
            mock_chat.side_effect = RuntimeError("boom")
            client = TestClient(ms.app)
            resp = client.post(
                "/api/text_input",
                json={"text": "你好", "request_id": "t-exc"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["openrouter"])
        self.assertEqual(body["openrouter_error"], "exception")


class TestOptInNoKey(unittest.TestCase):
    """MOCK_OPENROUTER=1 but no key → log warn, fall back to canned."""

    @patch.dict("os.environ", {"MOCK_OPENROUTER": "1"}, clear=True)
    def test_module_flag_still_set_but_canned_used(self):
        from fastapi.testclient import TestClient

        ms = _reload_mock_server()
        self.assertTrue(ms._MOCK_OPENROUTER_ENABLED)

        client = TestClient(ms.app)
        resp = client.post(
            "/api/text_input",
            json={"text": "你好", "request_id": "t-nokey"},
        )
        body = resp.json()
        self.assertTrue(body["ok"])
        # openrouter call attempted but failed at no_key gate
        # → falls into the failure branch → openrouter=False with error
        self.assertFalse(body["openrouter"])
        self.assertEqual(body["openrouter_error"], "no_key")


if __name__ == "__main__":
    unittest.main()
