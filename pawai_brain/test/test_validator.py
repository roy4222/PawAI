"""Unit tests for pawai_brain.validator — pure-function coverage."""
from pawai_brain.validator import (
    cap_length,
    looks_truncated,
    parse_persona_json,
    strip_emoji,
    strip_markdown_fences,
)


# ── strip_markdown_fences ───────────────────────────────────────────────

def test_strip_fences_with_json_label():
    raw = '```json\n{"reply": "hi"}\n```'
    assert strip_markdown_fences(raw) == '{"reply": "hi"}'


def test_strip_fences_no_fences():
    assert strip_markdown_fences('  {"a":1}  ') == '{"a":1}'


def test_strip_fences_only_trailing():
    raw = '{"x":1}\n```'
    assert strip_markdown_fences(raw) == '{"x":1}'


# ── parse_persona_json ──────────────────────────────────────────────────

def test_parse_valid_persona():
    result = parse_persona_json('{"reply": "嗨", "skill": "self_introduce"}')
    assert result == {"reply": "嗨", "skill": "self_introduce"}


def test_parse_with_fences():
    result = parse_persona_json('```\n{"reply":"嗨"}\n```')
    assert result == {"reply": "嗨"}


def test_parse_truncated_json_returns_none():
    assert parse_persona_json('{"reply": "嗨", "skill":') is None


def test_parse_non_dict_returns_none():
    assert parse_persona_json('"just a string"') is None
    assert parse_persona_json("[1,2,3]") is None


def test_parse_empty_returns_none():
    assert parse_persona_json("") is None
    assert parse_persona_json("   ") is None


# ── strip_emoji ─────────────────────────────────────────────────────────

def test_strip_emoji_keeps_audio_tags():
    text = "[excited] 嗨 🎉 你好 🐶"
    assert strip_emoji(text) == "[excited] 嗨  你好"


def test_strip_emoji_no_emoji():
    assert strip_emoji("正常文字") == "正常文字"


def test_strip_emoji_empty():
    assert strip_emoji("") == ""
    assert strip_emoji(None) == ""  # type: ignore


# ── cap_length ──────────────────────────────────────────────────────────

def test_cap_length_under_limit():
    assert cap_length("短文", 10) == "短文"


def test_cap_length_over_limit():
    assert cap_length("一二三四五六七八", 4) == "一二三四"


def test_cap_length_zero_means_uncapped():
    long = "一" * 100
    assert cap_length(long, 0) == long


def test_cap_length_negative_means_uncapped():
    long = "一" * 100
    assert cap_length(long, -1) == long


# ── looks_truncated ─────────────────────────────────────────────────────

def test_truncated_mid_clause():
    assert looks_truncated("今天天氣很好，我們可以一起去散步，") == "mid-clause"


def test_truncated_no_terminator():
    assert looks_truncated("今天天氣很好我們可以一起去散步") == "no-terminator"


def test_proper_terminator_ok():
    assert looks_truncated("今天天氣很好。") is None
    assert looks_truncated("好啊！") is None


def test_short_reply_not_flagged():
    # length <= 8 → skip check (legitimate short replies like "好喔" must pass)
    assert looks_truncated("好喔") is None
    assert looks_truncated("我去了") is None
