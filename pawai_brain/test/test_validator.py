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


# ── N6: normalize_audio_tags ──────────────────────────────────────────────

from pawai_brain.validator import normalize_audio_tags


def test_normalize_audio_tags_whispers_passes_through():
    """5/11 night: [whispers] restored — user wants whisper voice for storytelling."""
    out = normalize_audio_tags("[whispers] 好喔。從前有一隻小狗。")
    assert "[whispers]" in out
    assert "[curious]" not in out


def test_normalize_audio_tags_sighs_to_curious():
    out = normalize_audio_tags("[sighs] 那個我還在學")
    assert "[sighs]" not in out
    assert "[curious] 那個我還在學" == out


def test_normalize_audio_tags_case_insensitive():
    assert "[curious]" in normalize_audio_tags("[Sighs] hi")
    assert "[curious]" in normalize_audio_tags("[SIGHS] hi")


def test_normalize_audio_tags_singular_form():
    """[sigh] (no s) also normalized; [whisper] passes through."""
    assert "[curious]" in normalize_audio_tags("[sigh] hi")
    assert "[whisper]" in normalize_audio_tags("[whisper] hi")


def test_normalize_audio_tags_keeps_stable_tags():
    """[excited] / [curious] / [playful] / [whispers] etc must pass through unchanged."""
    cases = [
        "[excited] 大家好！",
        "[curious] 哦？",
        "[playful] 我搖一下！",
        "[worried] 你還好嗎？",
        "[thinking] 嗯～",
        "[whispers] 故事開始了。",
    ]
    for c in cases:
        assert normalize_audio_tags(c) == c, f"stable tag mutated: {c}"


def test_normalize_audio_tags_mixed_only_sighs_normalized():
    """[whispers] kept, [sighs] still normalized."""
    out = normalize_audio_tags("[whispers] 我說 [sighs] 慢慢的")
    assert "[whispers]" in out
    assert "[sighs]" not in out
    assert out.count("[curious]") == 1


def test_normalize_audio_tags_empty_safe():
    assert normalize_audio_tags("") == ""
    assert normalize_audio_tags(None) is None  # passthrough for None
