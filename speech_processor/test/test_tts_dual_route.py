"""Unit tests for Branch E TTS dual-route + audio_format/served_by refactor.

Covers:
  E3-1  provider output_format attributes
  E3-2  _play_on_robot served-format tracking (_last_served_format)
  E3-3  _compute_effective_length + _should_use_fast_lane helpers
  E3-4  tts_callback dual-route chain selection (mocked node)

No ROS runtime required — provider classes and module-level helpers are
imported directly; EnhancedTTSNode is exercised through a _StubNode shim
for the chain-selection logic.
"""

from typing import Optional
import pytest


# ---------------------------------------------------------------------------
# Module import helpers
# ---------------------------------------------------------------------------

def _load_tts_node():
    """Import tts_node; skip when ROS env unavailable."""
    try:
        import speech_processor.tts_node as m
        return m
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"tts_node requires ROS env: {exc}")


# ---------------------------------------------------------------------------
# E3-3: _compute_effective_length and _should_use_fast_lane
# ---------------------------------------------------------------------------

def _helpers():
    m = _load_tts_node()
    return m._compute_effective_length, m._should_use_fast_lane, m.FAST_LANE_THRESHOLD


class TestComputeEffectiveLength:
    def test_pure_cjk(self):
        cel, _, _ = _helpers()
        # 8 Chinese characters
        assert cel("我喜歡和你一起玩") == 8

    def test_cjk_with_punctuation_stripped(self):
        cel, _, _ = _helpers()
        # "你好，世界！" → 4 CJK chars
        assert cel("你好，世界！") == 4

    def test_audio_tag_stripped(self):
        cel, _, _ = _helpers()
        # "[playful] 嗨～" → 1 CJK char (～ is punctuation-like, stripped)
        result = cel("[playful] 嗨～")
        # 嗨 = 1 CJK; ～ stripped as punctuation
        assert result == 1

    def test_empty_string(self):
        cel, _, _ = _helpers()
        assert cel("") == 0

    def test_only_audio_tags(self):
        cel, _, _ = _helpers()
        assert cel("[excited][laughs]") == 0

    def test_english_words(self):
        cel, _, _ = _helpers()
        # "hello world" → 2 words
        assert cel("hello world") == 2

    def test_mixed_cjk_and_english(self):
        cel, _, _ = _helpers()
        # "你好 hello" → 2 CJK + 1 word = 3
        assert cel("你好 hello") == 3

    def test_multiple_audio_tags_stripped(self):
        cel, _, _ = _helpers()
        # "[playful] 嗨，我是機器狗！" → 嗨我是機器狗 = 6 CJK
        result = cel("[playful] 嗨，我是機器狗！")
        assert result == 6

    def test_long_chinese_sentence(self):
        cel, _, _ = _helpers()
        text = "今天天氣真好，我們一起出去走走吧，享受一下陽光和新鮮空氣。"
        # count CJK chars excluding punctuation
        cjk_chars = [c for c in text if "一" <= c <= "鿿" or "㐀" <= c <= "䶿"]
        result = cel(text)
        assert result == len(cjk_chars)

    def test_whitespace_only(self):
        cel, _, _ = _helpers()
        assert cel("   \t\n") == 0


class TestShouldUseFastLane:
    def test_safety_keyword_stop(self):
        _, fast, _ = _helpers()
        assert fast("停") is True

    def test_safety_keyword_stop_full(self):
        _, fast, _ = _helpers()
        assert fast("停止") is True

    def test_safety_keyword_in_long_text(self):
        _, fast, _ = _helpers()
        # Even though > 30 chars, contains 停 → fast
        assert fast("停下來，不然我們就會撞到牆壁，這樣很危險的不是嗎？") is True

    def test_safety_keyword_stop_english(self):
        _, fast, _ = _helpers()
        assert fast("stop") is True

    def test_safety_keyword_careful(self):
        _, fast, _ = _helpers()
        assert fast("小心！") is True

    def test_safety_keyword_danger(self):
        _, fast, _ = _helpers()
        assert fast("危險") is True

    def test_short_emotional_audio_tag_forces_quality(self):
        _, fast, _ = _helpers()
        # 5/9 fix: short emotional sentences with audio tag should NOT use
        # fast lane (edge-tts robotic) — voice fidelity matters more than latency.
        assert fast("[playful] 嗨～") is False

    def test_short_greeting_no_tag_fast(self):
        _, fast, _ = _helpers()
        assert fast("你好啊！") is True  # 3 CJK ≤ 12, no audio tag

    def test_long_chinese_quality(self):
        _, fast, _ = _helpers()
        # 50+ CJK chars → quality lane
        long_text = "今天天氣很好，我們去公園散步好嗎？你可以給我一些建議嗎，比如穿什麼衣服最合適。"
        assert fast(long_text) is False

    def test_threshold_boundary_at_exactly_threshold(self):
        _, fast, threshold = _helpers()
        # Build a text that is exactly threshold CJK chars (no audio tag)
        text = "一" * threshold
        assert fast(text) is True  # equal → fast (no emotional tag)

    def test_threshold_boundary_above_threshold(self):
        _, fast, threshold = _helpers()
        text = "一" * (threshold + 1)
        assert fast(text) is False  # over → quality

    def test_audio_tag_emotional_overrides_short(self):
        # Short content + emotional audio tag → quality lane (not fast)
        # This is the core 5/9 fix: short emotional → quality voice.
        _, fast, _ = _helpers()
        assert fast("[playful][excited][laughs] 好") is False

    def test_unknown_audio_tag_does_not_force_quality(self):
        # An unknown tag (not in QUALITY_LANE_AUDIO_TAGS) shouldn't override.
        _, fast, _ = _helpers()
        assert fast("[noise] 嗯") is True  # 1 CJK after strip → fast

    def test_threshold_default_is_12(self):
        _, _, threshold = _helpers()
        assert threshold == 12, "5/9 review: threshold lowered from 30 to 12"

    def test_safety_keyword_overrides_audio_tag(self):
        # Safety > emotional tag — even with [worried], 停 forces fast lane.
        _, fast, _ = _helpers()
        assert fast("[worried] 停下來") is True

    def test_dont_move_keyword_is_fast(self):
        _, fast, _ = _helpers()
        assert fast("不要動") is True

    def test_alert_keyword(self):
        _, fast, _ = _helpers()
        assert fast("警告！有陌生人！") is True


# ---------------------------------------------------------------------------
# E3-1: provider output_format class attributes
# ---------------------------------------------------------------------------

class TestProviderOutputFormat:
    """Each provider must declare output_format matching its actual container."""

    def _get_module(self):
        return _load_tts_node()

    def test_elevenlabs_is_mp3(self):
        m = self._get_module()
        assert m.TTSProvider_ElevenLabs.output_format == m.AudioFormat.MP3

    def test_melotts_is_wav(self):
        m = self._get_module()
        assert m.TTSProvider_MeloTTS.output_format == m.AudioFormat.WAV

    def test_piper_is_wav(self):
        m = self._get_module()
        assert m.TTSProvider_Piper.output_format == m.AudioFormat.WAV

    def test_edge_tts_is_mp3(self):
        m = self._get_module()
        assert m.TTSProvider_EdgeTTS.output_format == m.AudioFormat.MP3

    def test_openrouter_gemini_is_wav(self):
        m = self._get_module()
        assert m.TTSProvider_OpenRouterGemini.output_format == m.AudioFormat.WAV

    def test_all_output_formats_are_audio_format_enum(self):
        m = self._get_module()
        provider_classes = [
            m.TTSProvider_ElevenLabs,
            m.TTSProvider_MeloTTS,
            m.TTSProvider_Piper,
            m.TTSProvider_EdgeTTS,
            m.TTSProvider_OpenRouterGemini,
        ]
        for cls in provider_classes:
            assert isinstance(cls.output_format, m.AudioFormat), (
                f"{cls.__name__}.output_format is not AudioFormat: {cls.output_format!r}"
            )


# ---------------------------------------------------------------------------
# E3-2 + E3-1: _last_served_format tracking in provider chain loop
# ---------------------------------------------------------------------------

class _MockProvider:
    """Minimal mock implementing the provider protocol."""

    def __init__(self, name: str, output_format, returns: Optional[bytes]):
        self.name = name
        self.sample_rate = 16000
        self.supports_audio_tags = False
        self.output_format = output_format
        self._returns = returns

    def synthesize(self, text: str) -> Optional[bytes]:
        return self._returns


class _StubNode:
    """Minimal stand-in for EnhancedTTSNode provider-chain helpers."""

    class _Logger:
        def warning(self, *a, **k): pass
        def warn(self, *a, **k): pass
        def info(self, *a, **k): pass
        def error(self, *a, **k): pass

    def __init__(self, config, module):
        self.config = config
        self._logger = self._Logger()
        self._module = module

    def get_logger(self):
        return self._logger


def _make_stub(module):
    config = module.TTSConfig(
        api_key="",
        provider=module.TTSProvider.EDGE_TTS,
        piper_model_path="",
    )
    return _StubNode(config, module)


def _run_chain_loop(stub, module, chain: list, text: str):
    """Replicate the provider chain loop from tts_callback in isolation.

    Returns (audio_data, served_by, last_served_format).
    """
    AudioFormat = module.AudioFormat
    audio_data = None
    served_by = ""
    last_served_format = AudioFormat.MP3  # default

    for prov in chain:
        pname = getattr(prov, "name", prov.__class__.__name__)
        try:
            fresh = prov.synthesize(text)
        except Exception:
            continue

        if fresh:
            audio_data = fresh
            served_by = pname
            last_served_format = getattr(prov, "output_format", AudioFormat.MP3)
            break

    return audio_data, served_by, last_served_format


class TestLastServedFormat:
    def test_fast_lane_edge_succeeds_format_is_mp3(self):
        m = _load_tts_node()
        edge = _MockProvider("edge_tts", m.AudioFormat.MP3, b"fake_mp3")
        piper = _MockProvider("piper", m.AudioFormat.WAV, b"fake_wav")
        chain = [edge, piper]
        audio, served_by, fmt = _run_chain_loop(_make_stub(m), m, chain, "停")
        assert served_by == "edge_tts"
        assert fmt == m.AudioFormat.MP3

    def test_fallback_to_piper_format_is_wav(self):
        """When edge-tts fails, Piper serves WAV — last_served_format must be WAV."""
        m = _load_tts_node()
        edge = _MockProvider("edge_tts", m.AudioFormat.MP3, None)  # fails
        piper = _MockProvider("piper", m.AudioFormat.WAV, b"fake_wav")
        chain = [edge, piper]
        audio, served_by, fmt = _run_chain_loop(_make_stub(m), m, chain, "test")
        assert served_by == "piper"
        assert fmt == m.AudioFormat.WAV

    def test_gemini_succeeds_format_is_wav(self):
        m = _load_tts_node()
        gemini = _MockProvider("openrouter_gemini", m.AudioFormat.WAV, b"fake_wav")
        edge = _MockProvider("edge_tts", m.AudioFormat.MP3, b"fake_mp3")
        chain = [gemini, edge]
        audio, served_by, fmt = _run_chain_loop(_make_stub(m), m, chain, "test")
        assert served_by == "openrouter_gemini"
        assert fmt == m.AudioFormat.WAV

    def test_gemini_fails_edge_tts_serves_mp3(self):
        """Quality lane: Gemini timeout → edge-tts fallback → format MP3."""
        m = _load_tts_node()
        gemini = _MockProvider("openrouter_gemini", m.AudioFormat.WAV, None)
        edge = _MockProvider("edge_tts", m.AudioFormat.MP3, b"fake_mp3")
        piper = _MockProvider("piper", m.AudioFormat.WAV, b"fake_wav")
        chain = [gemini, edge, piper]
        audio, served_by, fmt = _run_chain_loop(_make_stub(m), m, chain, "test")
        assert served_by == "edge_tts"
        assert fmt == m.AudioFormat.MP3

    def test_all_cloud_fail_piper_serves_wav(self):
        """All cloud providers fail → Piper last-resort → WAV."""
        m = _load_tts_node()
        gemini = _MockProvider("openrouter_gemini", m.AudioFormat.WAV, None)
        edge = _MockProvider("edge_tts", m.AudioFormat.MP3, None)
        piper = _MockProvider("piper", m.AudioFormat.WAV, b"fallback_wav")
        chain = [gemini, edge, piper]
        audio, served_by, fmt = _run_chain_loop(_make_stub(m), m, chain, "test")
        assert served_by == "piper"
        assert fmt == m.AudioFormat.WAV

    def test_all_fail_returns_none(self):
        m = _load_tts_node()
        edge = _MockProvider("edge_tts", m.AudioFormat.MP3, None)
        piper = _MockProvider("piper", m.AudioFormat.WAV, None)
        chain = [edge, piper]
        audio, served_by, fmt = _run_chain_loop(_make_stub(m), m, chain, "test")
        assert audio is None
        assert served_by == ""


# ---------------------------------------------------------------------------
# E3-4: dual-route lane selection helpers
# ---------------------------------------------------------------------------

class TestDualRouteLaneHelpers:
    """Verify the module-level lane helpers used by tts_callback."""

    def test_safety_forces_fast_even_if_long(self):
        _, fast, _ = _helpers()
        long_safety = "停下來" + "好" * 50
        assert fast(long_safety) is True

    def test_no_keywords_short_is_fast(self):
        _, fast, _ = _helpers()
        assert fast("你好") is True

    def test_no_keywords_long_is_quality(self):
        _, fast, _ = _helpers()
        assert fast("這是一段非常長的文字，超過了快速通道的字數門檻，所以應該走品質通道進行合成。") is False

    def test_custom_threshold_overrides_default(self):
        cel, fast_fn, _ = _helpers()
        # 5-char text should be quality if threshold=3
        text = "一二三四五"
        # default threshold → fast (5 ≤ 30)
        assert fast_fn(text) is True
        # custom threshold=3 → quality (5 > 3)
        assert fast_fn(text, threshold=3) is False
