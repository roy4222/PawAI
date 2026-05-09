"""Unit tests for speech_processor.text_normalization."""
import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _reload_module():
    """Reload text_normalization so _converter is reset between tests."""
    mod_name = "speech_processor.text_normalization"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    # Also reset any cached state on the module if it was imported before
    import speech_processor.text_normalization as m
    m._converter = None
    return m


class TestToTraditionalTw:
    def test_basic_conversion(self):
        """「网络」→「網路」 (simplified → traditional TW)."""
        m = _reload_module()
        try:
            from opencc import OpenCC  # noqa: F401
        except ImportError:
            pytest.skip("opencc not installed")
        result = m.to_traditional_tw("网络")
        assert result == "網路", f"Expected 網路, got {result!r}"

    def test_mixed_en_zh(self):
        """Mixed English + Chinese: English passthrough, Chinese converted."""
        m = _reload_module()
        try:
            from opencc import OpenCC  # noqa: F401
        except ImportError:
            pytest.skip("opencc not installed")
        result = m.to_traditional_tw("Hello 网络")
        assert "網路" in result
        assert "Hello" in result

    def test_empty_string(self):
        """Empty string is returned as-is without calling OpenCC."""
        m = _reload_module()
        result = m.to_traditional_tw("")
        assert result == ""

    def test_none_like_empty(self):
        """Empty string (falsy) returns immediately."""
        m = _reload_module()
        result = m.to_traditional_tw("")
        assert result == ""

    def test_opencc_import_error_fallback(self):
        """When OpenCC import fails, return original text unchanged."""
        m = _reload_module()
        m._converter = None  # force lazy init

        # Patch builtins.__import__ to simulate ImportError for opencc
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def mock_import(name, *args, **kwargs):
            if name == "opencc":
                raise ImportError("mocked: opencc not available")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            m._converter = None  # ensure fresh lazy init
            result = m.to_traditional_tw("网络")

        # Fallback: original text returned
        assert result == "网络"

    def test_converter_false_fallback(self):
        """When _converter is False (import failed), return text unchanged."""
        m = _reload_module()
        m._converter = False
        result = m.to_traditional_tw("网络")
        assert result == "网络"

    def test_convert_raises_fallback(self):
        """When converter.convert() raises, return text unchanged."""
        m = _reload_module()
        bad_converter = MagicMock()
        bad_converter.convert.side_effect = RuntimeError("conversion error")
        m._converter = bad_converter
        result = m.to_traditional_tw("网络")
        assert result == "网络"

    def test_already_traditional(self):
        """Traditional Chinese passes through without change."""
        m = _reload_module()
        try:
            from opencc import OpenCC  # noqa: F401
        except ImportError:
            pytest.skip("opencc not installed")
        result = m.to_traditional_tw("網路")
        assert result == "網路"
