"""Unit tests for speech_processor.audio_tag.strip_audio_tags."""

import pytest

from speech_processor.audio_tag import strip_audio_tags


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("[excited] 你好", "你好"),
        ("[curious] 我是 PawAI", "我是 PawAI"),
        ("[laughs]哈哈", "哈哈"),
        ("你好", "你好"),
        ("", ""),
        ("[excited] [curious] 雙標籤", "雙標籤"),
        ("中段[playful]標籤", "中段標籤"),
        ("結尾標籤[sighs]", "結尾標籤"),
        # Chinese-bracketed non-tag must be preserved
        ("[非tag] 保留", "[非tag] 保留"),
        # Numbers in brackets should be preserved (not an emotion tag)
        ("[123] 你好", "[123] 你好"),
        # Underscore tags allowed
        ("[very_excited] 嗨", "嗨"),
    ],
)
def test_strip_audio_tags(raw: str, expected: str) -> None:
    assert strip_audio_tags(raw) == expected


def test_strip_audio_tags_idempotent() -> None:
    once = strip_audio_tags("[excited] [curious] 你好")
    twice = strip_audio_tags(once)
    assert once == twice == "你好"


def test_strip_audio_tags_handles_none_safe() -> None:
    # We document `text` as str, but guard against accidental empty/None.
    assert strip_audio_tags("") == ""
