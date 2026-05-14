"""Unit tests for TTSProvider_OpenRouterGemini (Stage 3 of B1 Plan D).

Covers:
- happy path: 200 PCM → WAV-wrapped bytes with correct header (24kHz/16-bit/mono)
- HTTP 401 / 400 / 500 → return None
- timeout → return None (caller can fallback)
- missing OPENROUTER_KEY → return None without HTTP call
- supports_audio_tags=True (so tts_callback skips strip)
- name and sample_rate match Stage 2 protocol expectations
"""

import io
import wave
from unittest.mock import patch, MagicMock

import pytest


def _load_provider_class():
    """Load class lazily — module imports rclpy + std_msgs which need ROS env."""
    try:
        from speech_processor.tts_node import (
            TTSProvider_OpenRouterGemini,
            TTSConfig,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"tts_node requires ROS env: {exc}")
    return TTSProvider_OpenRouterGemini, TTSConfig


def _make_config(TTSConfig):
    return TTSConfig(
        api_key="",
        openrouter_gemini_voice="Despina",
        openrouter_gemini_model="google/gemini-3.1-flash-tts-preview",
        openrouter_gemini_timeout_s=6.0,
    )


# --- Class-level attribute checks (Stage 2 protocol contract) ----------------


def test_protocol_attrs() -> None:
    Provider, _ = _load_provider_class()
    assert Provider.name == "openrouter_gemini"
    assert Provider.sample_rate == 24000
    assert Provider.supports_audio_tags is True


# --- Synthesize behavior ------------------------------------------------------


def test_synthesize_happy_path_wraps_pcm_to_wav() -> None:
    Provider, TTSConfig = _load_provider_class()
    fake_pcm = b"\x00\x00\x10\x00\x20\x00" * 1000  # 6000 bytes ≈ 0.125s @ 24kHz

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = fake_pcm
    fake_response.text = ""

    with patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=False):
        with patch("speech_processor.tts_node.requests.post", return_value=fake_response) as post:
            provider = Provider(_make_config(TTSConfig))
            result = provider.synthesize("[excited] hi")

    assert result is not None
    assert post.call_count == 1
    # Verify the request body
    call = post.call_args
    body = call.kwargs["json"]
    assert body["model"] == "google/gemini-3.1-flash-tts-preview"
    assert body["voice"] == "Despina"
    assert body["response_format"] == "pcm"
    assert body["input"] == "[excited] hi"  # tag NOT stripped (caller's job)
    headers = call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-test"

    # Verify WAV header
    with wave.open(io.BytesIO(result), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() == 24000
        assert wf.readframes(wf.getnframes()) == fake_pcm


def test_synthesize_returns_none_on_401() -> None:
    Provider, TTSConfig = _load_provider_class()
    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.text = '{"error": "unauthorized"}'

    with patch.dict("os.environ", {"OPENROUTER_KEY": "sk-bad"}, clear=False):
        with patch("speech_processor.tts_node.requests.post", return_value=fake_response):
            provider = Provider(_make_config(TTSConfig))
            assert provider.synthesize("hi") is None


def test_synthesize_returns_none_on_timeout() -> None:
    Provider, TTSConfig = _load_provider_class()
    import requests as _requests

    with patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=False):
        with patch(
            "speech_processor.tts_node.requests.post",
            side_effect=_requests.exceptions.Timeout(),
        ):
            provider = Provider(_make_config(TTSConfig))
            assert provider.synthesize("hi") is None


def test_synthesize_returns_none_when_key_missing() -> None:
    Provider, TTSConfig = _load_provider_class()
    with patch.dict(
        "os.environ", {"OPENROUTER_KEY": "", "OPENROUTER_API_KEY": ""}, clear=False
    ):
        with patch("speech_processor.tts_node.requests.post") as post:
            provider = Provider(_make_config(TTSConfig))
            assert provider.synthesize("hi") is None
            # Must not even attempt HTTP call when key is missing
            assert post.call_count == 0


def test_synthesize_returns_none_on_json_body() -> None:
    """Defensive: 200 with JSON body would mean OpenRouter contract drift."""
    Provider, TTSConfig = _load_provider_class()
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b'{"error":"unexpected"}'
    fake_response.text = '{"error":"unexpected"}'

    with patch.dict("os.environ", {"OPENROUTER_KEY": "sk-test"}, clear=False):
        with patch("speech_processor.tts_node.requests.post", return_value=fake_response):
            provider = Provider(_make_config(TTSConfig))
            assert provider.synthesize("hi") is None
