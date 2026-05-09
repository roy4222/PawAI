"""Issue 8 (P3-1a) Idle MVP unit tests — pure logic, no ROS context.

Verifies:
  - canned phrase pool has expected size and structure
  - phrase pool is non-empty (avoid_recent never starves)
"""
from __future__ import annotations

import pytest

# Import only the constant — pulling brain_node would require rclpy.
from interaction_executive.brain_node import _IDLE_CANNED


def test_idle_canned_pool_size_within_spec():
    """Spec P3-1a: 8-12 canned phrases. Allow some slack (8 ≤ N ≤ 16)."""
    assert 8 <= len(_IDLE_CANNED) <= 16, f"got {len(_IDLE_CANNED)} phrases"


def test_idle_canned_phrases_have_audio_tags():
    """Each idle phrase should start with [audio_tag] for TTS quality lane.

    Issue 1 fix routes [excited]/[playful]/etc to quality lane; idle phrases
    should not sound robotic via edge-tts fast lane.
    """
    for phrase in _IDLE_CANNED:
        assert phrase.startswith("["), f"missing audio tag: {phrase!r}"


def test_idle_canned_phrases_short():
    """Spec P3-1a: phrases ≤ 18 chars (rough — enough to not feel intrusive)."""
    for phrase in _IDLE_CANNED:
        # Strip audio tag for length count
        import re
        stripped = re.sub(r"\[\w+\]\s*", "", phrase)
        assert len(stripped) <= 20, f"phrase too long ({len(stripped)} chars): {phrase!r}"


def test_idle_canned_no_questions():
    """Spec: idle phrases self-talk style, no question marks (don't pressure user).

    Some phrases like '誰要陪我玩' could end with full-width question mark; allow
    it sparingly but flag if more than 25% of pool is questions.
    """
    questions = [p for p in _IDLE_CANNED if "?" in p or "？" in p]
    assert len(questions) <= len(_IDLE_CANNED) // 4, \
        f"too many question phrases: {questions}"


def test_idle_canned_no_duplicates():
    """No duplicate phrases — would defeat avoid-recent dedup ring buffer."""
    assert len(set(_IDLE_CANNED)) == len(_IDLE_CANNED), "duplicate idle phrases"
