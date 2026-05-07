"""Offline tests for OpenRouterClient — mock requests, verify fallback chain.

Tests the conditional fallback rules from Plan §3:
  Gemini timeout → return None (do NOT try DeepSeek)
  Gemini HTTP / connection / parse fail → try DeepSeek
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock

import requests as real_requests

from pawai_brain.llm_client import (
    OpenRouterClient,
    OpenRouterConfig,
    resolve_openrouter_key,
)


def _client(api_key: str = "test-key") -> OpenRouterClient:
    return OpenRouterClient(
        config=OpenRouterConfig(
            request_timeout_s=2.0,
            overall_budget_s=4.0,
        ),
        api_key=api_key,
        logger=lambda _: None,
    )


def _mock_response(status: int, payload):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.text = "mock"
    return resp


def test_inactive_when_no_key():
    client = OpenRouterClient(api_key="", logger=lambda _: None)
    assert client.active is False
    assert client.chat("sys", [], "hi") is None


def test_gemini_success_no_deepseek_call():
    client = _client()
    ok_payload = {"choices": [{"message": {"content": '{"reply":"ok"}'}}]}
    with patch("pawai_brain.llm_client.requests.post") as post:
        post.return_value = _mock_response(200, ok_payload)
        result = client.chat("sys", [], "hi")
    assert result is not None
    assert result["raw"] == '{"reply":"ok"}'
    assert result["model"] == client.config.gemini_model
    assert post.call_count == 1


def test_gemini_timeout_does_not_try_deepseek():
    client = _client()
    with patch("pawai_brain.llm_client.requests.post") as post:
        post.side_effect = real_requests.exceptions.Timeout()
        result = client.chat("sys", [], "hi")
    assert result is None
    assert post.call_count == 1  # never tried DeepSeek on timeout


def test_gemini_connection_error_falls_to_deepseek():
    client = _client()
    ok_payload = {"choices": [{"message": {"content": '{"reply":"ds"}'}}]}
    call_count = {"n": 0}

    def side_effect(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise real_requests.exceptions.ConnectionError()
        return _mock_response(200, ok_payload)

    with patch("pawai_brain.llm_client.requests.post", side_effect=side_effect):
        result = client.chat("sys", [], "hi")
    assert result is not None
    assert result["model"] == client.config.deepseek_model
    assert call_count["n"] == 2


def test_gemini_http_5xx_falls_to_deepseek():
    client = _client()
    ok_payload = {"choices": [{"message": {"content": '{"reply":"ds"}'}}]}
    responses = [_mock_response(503, {}), _mock_response(200, ok_payload)]

    with patch("pawai_brain.llm_client.requests.post", side_effect=responses):
        result = client.chat("sys", [], "hi")
    assert result is not None
    assert result["model"] == client.config.deepseek_model


def test_both_fail_returns_none():
    client = _client()
    with patch(
        "pawai_brain.llm_client.requests.post",
        side_effect=real_requests.exceptions.ConnectionError(),
    ) as post:
        result = client.chat("sys", [], "hi")
    assert result is None
    assert post.call_count == 2


# ── resolve_openrouter_key (gate by ROS param) ──────────────────────────

def test_resolve_key_disabled_returns_empty_even_if_env_set():
    """enable_openrouter=False must short-circuit; demo can force offline mode."""
    env = {"OPENROUTER_KEY": "real-key-abc"}
    assert resolve_openrouter_key(enable_openrouter=False, env=env) == ""


def test_resolve_key_disabled_with_no_env():
    assert resolve_openrouter_key(enable_openrouter=False, env={}) == ""


def test_resolve_key_enabled_picks_primary_env():
    env = {"OPENROUTER_KEY": "primary", "OPENROUTER_API_KEY": "secondary"}
    assert resolve_openrouter_key(enable_openrouter=True, env=env) == "primary"


def test_resolve_key_enabled_falls_back_to_alt_env():
    env = {"OPENROUTER_API_KEY": "alt-key"}
    assert resolve_openrouter_key(enable_openrouter=True, env=env) == "alt-key"


def test_resolve_key_enabled_no_env_returns_empty():
    assert resolve_openrouter_key(enable_openrouter=True, env={}) == ""


def test_resolve_key_strips_whitespace():
    env = {"OPENROUTER_KEY": "  spaced-key  "}
    assert resolve_openrouter_key(enable_openrouter=True, env=env) == "spaced-key"


def test_disabled_client_does_not_call_network():
    """End-to-end: disabled flag → empty key → client.active False → no requests."""
    key = resolve_openrouter_key(enable_openrouter=False, env={"OPENROUTER_KEY": "x"})
    client = OpenRouterClient(api_key=key, logger=lambda _: None)
    assert client.active is False
    # chat() returns None without raising or hitting network
    assert client.chat("sys", [], "hi") is None


def test_parse_failure_falls_to_deepseek():
    client = _client()
    ok_payload = {"choices": [{"message": {"content": '{"reply":"ds"}'}}]}
    bad_payload = {"choices": [{"message": {"content": ""}}]}  # empty content
    responses = [_mock_response(200, bad_payload), _mock_response(200, ok_payload)]

    with patch("pawai_brain.llm_client.requests.post", side_effect=responses):
        result = client.chat("sys", [], "hi")
    assert result is not None
    assert result["model"] == client.config.deepseek_model
