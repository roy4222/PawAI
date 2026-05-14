#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for _emit_chat_candidate in llm_bridge_node (Phase 0.5, 2026-05-06).

Covers:
- proposed_skill / proposed_args / proposal_reason / engine fields in payload
- defaults when optional kwargs are omitted
"""
from __future__ import annotations

import json
import sys
import threading
import types
from collections import deque


# ── Stub rclpy / std_msgs so we can import llm_bridge_node outside ROS ──
def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


_rclpy = _ensure_module("rclpy")
_rclpy_node = _ensure_module("rclpy.node")
_rclpy_node.Node = type("Node", (), {})
_std_msgs = _ensure_module("std_msgs")
_std_msgs_msg = _ensure_module("std_msgs.msg")


class _FakeStringMsg:
    data = ""


_std_msgs_msg.String = _FakeStringMsg


class _FakeLogger:
    def warn(self, msg):
        pass

    def error(self, msg):
        pass

    def info(self, msg):
        pass


class _FakePub:
    def __init__(self):
        self.last_msg = None

    def publish(self, msg):
        self.last_msg = msg


class _StubNode:
    """Minimal stub that exposes only what _emit_chat_candidate touches."""

    def __init__(self):
        self._logger = _FakeLogger()
        self.chat_candidate_pub = _FakePub()
        self.output_mode = "brain"
        # convo state used by other methods — not exercised here but avoids
        # AttributeError if the method ever reads them.
        self._convo_history: deque = deque(maxlen=10)
        self._convo_lock = threading.Lock()

    def get_logger(self):
        return self._logger


def _make_node_for_test():
    """Return a stub with _emit_chat_candidate bound from the real node."""
    from speech_processor.llm_bridge_node import LlmBridgeNode

    stub = _StubNode()
    stub._emit_chat_candidate = LlmBridgeNode._emit_chat_candidate.__get__(stub)
    return stub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_chat_candidate_includes_proposal_fields_when_persona_returns_skill():
    """Persona returns {reply, skill: 'show_status', args: {}} →
    chat_candidate should carry proposed_skill='show_status'."""
    node = _make_node_for_test()

    node._emit_chat_candidate(
        session_id="test-1",
        reply_text="目前一切正常",
        intent="status",
        selected_skill=None,
        confidence=0.85,
        proposed_skill="show_status",
        proposed_args={},
        proposal_reason="openrouter:eval_schema",
    )

    msg = node.chat_candidate_pub.last_msg
    assert msg is not None, "publish was not called"
    p = json.loads(msg.data)

    assert p["reply_text"] == "目前一切正常"
    assert p["selected_skill"] is None
    assert p["proposed_skill"] == "show_status"
    assert p["proposed_args"] == {}
    assert p["proposal_reason"] == "openrouter:eval_schema"
    assert p["engine"] == "legacy"


def test_chat_candidate_proposal_fields_default_to_none_when_omitted():
    """When optional proposal kwargs are omitted, payload still has the keys
    with sensible defaults."""
    node = _make_node_for_test()

    node._emit_chat_candidate(
        session_id="test-2",
        reply_text="你好",
        intent="chat",
        selected_skill=None,
        confidence=0.8,
    )

    msg = node.chat_candidate_pub.last_msg
    assert msg is not None, "publish was not called"
    p = json.loads(msg.data)

    assert p["proposed_skill"] is None
    assert p["proposed_args"] == {}
    assert p["proposal_reason"] == ""
    assert p["engine"] == "legacy"
