"""Unit tests for the TTS provider fallback chain (Stage 4 of B1 Plan D).

Validates two responsibilities of EnhancedTTSNode:

1. _build_fallback_chain() returns the right list per main provider.
2. _cache_voice_for() resolves the correct voice attribute per provider.

The chain iteration logic in tts_callback is exercised end-to-end on
Jetson (live smoke); pure-unit testing it would require mocking ROS
publishers, the cache, and the playback subprocess — out of scope for
this stage. Stage 5 spec doc captures the live result.
"""

from typing import Optional

import pytest


def _load_node():
    """Load tts_node module — skip cleanly when ROS env absent."""
    try:
        from speech_processor import tts_node as m
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"tts_node requires ROS env: {exc}")
    return m


class _StubNode:
    """Minimal stand-in for EnhancedTTSNode methods we want to test in
    isolation. The real Node base class needs rclpy + a running context;
    we only need `config` + `get_logger()` for the helpers under test.
    """

    class _Logger:
        def warning(self, *a, **k): pass
        def warn(self, *a, **k): pass
        def info(self, *a, **k): pass
        def error(self, *a, **k): pass

    def __init__(self, config):
        self.config = config
        self._logger = self._Logger()

    def get_logger(self):
        return self._logger


def _make_node(provider_value: str):
    m = _load_node()
    config = m.TTSConfig(
        api_key="",
        provider=m.TTSProvider(provider_value),
        edge_tts_voice="zh-CN-XiaoxiaoNeural",
        openrouter_gemini_voice="Despina",
        voice_name="default-voice-id",
        piper_model_path="",  # Piper will fail to instantiate; the chain
                              # builder warns and skips — that's the test
    )
    stub = _StubNode(config)
    # Bind the unbound methods from EnhancedTTSNode onto the stub
    stub._build_fallback_chain = m.EnhancedTTSNode._build_fallback_chain.__get__(stub)
    stub._cache_voice_for = m.EnhancedTTSNode._cache_voice_for.__get__(stub)
    return stub, m


def test_cache_voice_for_each_provider() -> None:
    stub, _m = _make_node("openrouter_gemini")
    assert stub._cache_voice_for("edge_tts") == "zh-CN-XiaoxiaoNeural"
    assert stub._cache_voice_for("openrouter_gemini") == "Despina"
    assert stub._cache_voice_for("piper") == "default-voice-id"
    assert stub._cache_voice_for("elevenlabs") == "default-voice-id"


def test_chain_for_openrouter_gemini_includes_edge_tts() -> None:
    """Main = Gemini → fallback chain should at least contain edge_tts.
    Piper may fail to init when model path empty — that's allowed."""
    stub, _m = _make_node("openrouter_gemini")
    chain = stub._build_fallback_chain()
    names = [getattr(p, "name", p.__class__.__name__) for p in chain]
    assert "edge_tts" in names, f"expected edge_tts fallback, got: {names}"


def test_chain_for_edge_tts_main_is_piper_only_or_empty() -> None:
    """Main = edge_tts → fallback should be Piper if it can init,
    otherwise empty (warned but not fatal)."""
    stub, _m = _make_node("edge_tts")
    chain = stub._build_fallback_chain()
    names = [getattr(p, "name", p.__class__.__name__) for p in chain]
    # No Gemini fallback when main is edge_tts
    assert "openrouter_gemini" not in names
    assert "edge_tts" not in names  # never includes self


def test_chain_for_piper_is_empty() -> None:
    """Piper main → no fallback (already terminal offline option)."""
    stub, _m = _make_node("piper")
    chain = stub._build_fallback_chain()
    assert chain == []


def test_provider_name_attrs_populated_on_chain_members() -> None:
    """Every chain member must declare TTSProviderBase attrs (Stage 2)
    so tts_callback's strip-gate / cache-key helpers don't crash."""
    stub, _m = _make_node("openrouter_gemini")
    chain = stub._build_fallback_chain()
    for prov in chain:
        assert isinstance(prov.name, str) and prov.name
        assert isinstance(prov.sample_rate, int) and prov.sample_rate >= 0
        assert isinstance(prov.supports_audio_tags, bool)
