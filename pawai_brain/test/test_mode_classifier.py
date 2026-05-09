"""Unit tests for mode_classifier — 5-mode rule-based classifier.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1C
"""
from __future__ import annotations
import pytest

from pawai_brain.nodes.mode_classifier import classify_mode


@pytest.mark.parametrize("text,expected", [
    # Safety
    ("停！", "safety"),
    ("小心一點", "safety"),
    ("stop", "safety"),
    ("不要動", "safety"),
    ("危險！", "safety"),
    # Identity
    ("你是誰？", "identity"),
    ("介紹一下你自己", "identity"),
    ("你叫什麼", "identity"),
    # Capability question
    ("你會什麼？", "capability_question"),
    ("有什麼功能", "capability_question"),
    ("能做什麼", "capability_question"),
    ("你有哪些能力", "capability_question"),
    # Action request
    ("扭一下", "action_request"),
    ("伸個懶腰", "action_request"),
    ("揮個手", "action_request"),
    # Chat (default)
    ("天氣好嗎", "chat"),
    ("我今天累了", "chat"),
    ("講個故事", "chat"),
])
def test_classify_mode(text, expected):
    assert classify_mode(text) == expected


def test_classify_mode_empty():
    assert classify_mode("") == "chat"
    assert classify_mode("   ") == "chat"


def test_classify_mode_safety_takes_priority():
    """Safety keywords override other patterns."""
    assert classify_mode("停，你是誰") == "safety"


def test_classify_mode_returns_string():
    result = classify_mode("嗨")
    assert isinstance(result, str)
    assert result in ("safety", "identity", "capability_question", "action_request", "chat")
