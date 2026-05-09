"""Tests for ConversationGraphNode — persona loader + _build_user_message + face state.

Test helper _build_test_node uses object.__new__ + monkeypatching to avoid
starting a real ROS2 node (Roy review #6).
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pawai_brain.conversation_graph_node import (
    ConversationGraphNode,
    _INLINE_PERSONA,
    _build_user_message,
)


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------

def _build_test_node(llm_persona_file: str = "", capabilities_md: str = ""):
    """Construct ConversationGraphNode without ROS2 init.

    Uses object.__new__ so __init__ is NOT called; we manually set only
    the attributes needed by the methods under test.
    """
    node = object.__new__(ConversationGraphNode)
    # Fake logger
    logger = MagicMock()
    object.__setattr__(node, "_logger_mock", logger)
    node.get_logger = lambda: logger

    # Attributes used by _load_persona
    node.llm_persona_file = llm_persona_file

    # Attributes set by _load_persona (initialise defaults)
    node._capabilities_md = capabilities_md

    # 1H: face identity tracking (default — same as __init__ sets)
    node._recent_face_identity = ("unknown", 0.0)

    # Call _load_persona to set _system_prompt + _capabilities_md
    if llm_persona_file:
        node._system_prompt = node._load_persona()
    else:
        node._system_prompt = _INLINE_PERSONA

    return node


# ---------------------------------------------------------------------------
# Task 1 (1A) — persona loader file/dir dual mode
# ---------------------------------------------------------------------------

def test_load_persona_inline_when_empty():
    """No llm_persona_file → returns _INLINE_PERSONA."""
    node = _build_test_node(llm_persona_file="")
    assert node._system_prompt == _INLINE_PERSONA


def test_load_persona_legacy_file_mode(tmp_path):
    """Legacy persona.txt single file mode — backward compat."""
    persona_file = tmp_path / "persona.txt"
    persona_file.write_text("legacy persona content", encoding="utf-8")

    node = _build_test_node(llm_persona_file=str(persona_file))
    assert node._system_prompt == "legacy persona content"
    assert node._capabilities_md == ""


def test_load_persona_directory_mode_5_files(tmp_path):
    """Directory mode: 5 files required, base concat 4, CAPABILITIES cached separately."""
    persona_dir = tmp_path / "personas" / "v1"
    persona_dir.mkdir(parents=True)
    for fname, content in [
        ("IDENTITY.md", "id_content"),
        ("STYLE.md", "style_content"),
        ("OUTPUT.md", "output_content"),
        ("EXAMPLES.md", "examples_content"),
        ("CAPABILITIES.md", "cap_content"),
    ]:
        (persona_dir / fname).write_text(content, encoding="utf-8")

    node = _build_test_node(llm_persona_file=str(persona_dir))
    assert "id_content" in node._system_prompt
    assert "style_content" in node._system_prompt
    assert "output_content" in node._system_prompt
    assert "examples_content" in node._system_prompt
    assert "cap_content" not in node._system_prompt  # CAPABILITIES not in base
    assert node._capabilities_md == "cap_content"


def test_load_persona_directory_mode_missing_file_raises(tmp_path):
    """Missing required file → FileNotFoundError raise (not silent fallback)."""
    persona_dir = tmp_path / "personas" / "v1"
    persona_dir.mkdir(parents=True)
    (persona_dir / "IDENTITY.md").write_text("id", encoding="utf-8")
    # Missing STYLE / OUTPUT / EXAMPLES / CAPABILITIES

    with pytest.raises(FileNotFoundError):
        _build_test_node(llm_persona_file=str(persona_dir))


def test_load_persona_fallback_on_bad_file(tmp_path):
    """Empty file → inline persona fallback (graceful degradation)."""
    persona_file = tmp_path / "persona.txt"
    persona_file.write_text("", encoding="utf-8")

    node = _build_test_node(llm_persona_file=str(persona_file))
    assert node._system_prompt == _INLINE_PERSONA


# ---------------------------------------------------------------------------
# Task 4 (1D) — _build_user_message lazy inject + mode_hint
# ---------------------------------------------------------------------------

def _capability_context():
    return {
        "capabilities": [
            {
                "name": "wiggle",
                "kind": "skill",
                "display_name": "搖擺",
                "effective_status": "needs_confirm",
                "demo_value": "medium",
                "can_execute": False,
                "requires_confirmation": True,
                "reason": "需 OK 確認",
            }
        ],
        "limits": ["一次最多執行一個動作"],
        "recent_skill_results": [],
    }


def test_build_user_message_chat_mode_no_capability():
    """chat mode: capability_context not injected."""
    state = {
        "user_text": "今天天氣好",
        "mode": "chat",
        "source": "speech",
        "world_state": {"period": "下午", "time": "14:30", "weather": "晴 25°C"},
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    assert "今天天氣好" in msg
    assert "[環境]" in msg and "下午" in msg
    assert "[能力描述]" not in msg
    assert "[mode_hint]" not in msg


def test_build_user_message_identity_mode_with_hint_no_capability():
    """identity mode: mode_hint injected, CAPABILITIES not injected."""
    state = {
        "user_text": "你是誰",
        "mode": "identity",
        "source": "speech",
        "world_state": {},
        "capability_context": _capability_context(),
    }
    msg = _build_user_message(state)
    assert "[mode_hint]" in msg
    assert "不要列功能清單" in msg
    assert "[能力描述]" not in msg


def test_build_user_message_capability_question_mode_injects_capabilities():
    """capability_question mode: CAPABILITIES.md + capability_context JSON injected."""
    node = _build_test_node()
    node._capabilities_md = "FAKE CAPABILITIES MD"
    state = {
        "user_text": "你會什麼",
        "mode": "capability_question",
        "source": "speech",
        "world_state": {},
        "capability_context": _capability_context(),
    }
    msg = node._build_user_message(state)
    assert "[能力描述]" in msg
    assert "FAKE CAPABILITIES MD" in msg
    assert "[能力 runtime]" in msg


def test_build_user_message_action_request_mode_injects_capabilities():
    """action_request mode: CAPABILITIES + capability_context both injected."""
    node = _build_test_node()
    node._capabilities_md = "CAP MD"
    state = {
        "user_text": "扭一下",
        "mode": "action_request",
        "source": "speech",
        "world_state": {},
        "capability_context": _capability_context(),
    }
    msg = node._build_user_message(state)
    assert "[能力描述]" in msg
    assert "CAP MD" in msg


def test_build_user_message_label_speech():
    """source='speech' → [語音] label."""
    state = {"user_text": "嗨", "mode": "chat", "source": "speech",
             "world_state": {}, "capability_context": {}}
    assert "[語音]" in _build_user_message(state)


def test_build_user_message_label_text():
    """source='text' → [文字] label."""
    state = {"user_text": "嗨", "mode": "chat", "source": "text",
             "world_state": {}, "capability_context": {}}
    assert "[文字]" in _build_user_message(state)


def test_build_user_message_includes_current_speaker():
    """world_state.current_speaker injected as [眼前的人]."""
    state = {
        "user_text": "嗨",
        "mode": "chat",
        "source": "speech",
        "world_state": {"current_speaker": "Roy"},
        "capability_context": {},
    }
    msg = _build_user_message(state)
    assert "[眼前的人] Roy" in msg


def test_build_user_message_omits_unknown_speaker():
    """current_speaker == 'unknown' or absent → no [眼前的人] line."""
    state = {
        "user_text": "嗨",
        "mode": "chat",
        "source": "speech",
        "world_state": {"current_speaker": "unknown"},
        "capability_context": {},
    }
    msg = _build_user_message(state)
    assert "[眼前的人]" not in msg


def test_build_user_message_omits_speaker_when_absent():
    """current_speaker absent → no [眼前的人] line."""
    state = {
        "user_text": "嗨",
        "mode": "chat",
        "source": "speech",
        "world_state": {},
        "capability_context": {},
    }
    msg = _build_user_message(state)
    assert "[眼前的人]" not in msg


# ---------------------------------------------------------------------------
# Task 8 (1H) — face state subscription + current_speaker tracking
# ---------------------------------------------------------------------------

class _FakeMsg:
    def __init__(self, data):
        self.data = data


def test_on_face_state_updates_recent_identity():
    """/state/perception/face msg with known name updates _recent_face_identity."""
    node = _build_test_node()
    # Simulate face state payload with a known person
    payload = {
        "stamp": time.time(),
        "face_count": 1,
        "tracks": [{"stable_name": "Roy", "mode": "stable", "sim": 0.8}],
    }
    node._on_face_state(_FakeMsg(json.dumps(payload)))
    name, ts = node._recent_face_identity
    assert name == "Roy"
    assert time.time() - ts < 1.0


def test_on_face_state_ignores_unknown():
    """/state/perception/face with all unknown tracks does not update _recent_face_identity."""
    node = _build_test_node()
    # Preset with a known person
    node._recent_face_identity = ("Roy", time.time() - 1.0)
    payload = {
        "stamp": time.time(),
        "face_count": 1,
        "tracks": [{"stable_name": "unknown", "mode": "hold"}],
    }
    node._on_face_state(_FakeMsg(json.dumps(payload)))
    # Should not overwrite Roy with unknown
    name, _ = node._recent_face_identity
    assert name == "Roy"


def test_on_face_state_handles_bad_json():
    """Bad JSON in face state → no crash."""
    node = _build_test_node()
    node._on_face_state(_FakeMsg("not-json"))
    assert node._recent_face_identity[0] == "unknown"  # default unchanged
