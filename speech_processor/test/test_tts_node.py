#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Unit tests for tts_node TTSConfig (plan3 online/offline speech).

T1 — openrouter_gemini_timeout_s dataclass dead-default 60->6 consistency fix.
T8 — byte-identical regression: the rest of TTSConfig defaults unchanged.

tts_node imports rclpy + std_msgs (needs ROS env); load lazily and skip cleanly
when ROS is unavailable so the CI-safe subset still passes.
"""
from __future__ import annotations

import pytest


def _load_tts_config():
    try:
        from speech_processor.tts_node import TTSConfig
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"tts_node requires ROS env: {exc}")
    return TTSConfig


# ---------------------------------------------------------------------------
# T1 — dataclass dead-default consistency (60.0 -> 6.0)
# ---------------------------------------------------------------------------


def test_openrouter_gemini_timeout_dataclass_default_is_6():
    TTSConfig = _load_tts_config()
    assert TTSConfig(api_key="dummy").openrouter_gemini_timeout_s == 6.0


# ---------------------------------------------------------------------------
# T8 — byte-identical regression: T1 must not perturb other TTSConfig defaults
# ---------------------------------------------------------------------------


def test_tts_config_other_defaults_unchanged():
    TTSConfig = _load_tts_config()
    c = TTSConfig(api_key="dummy")
    # Spot-check a representative set of unrelated defaults (T1 only touched the
    # one timeout field). If any of these drift, T1's "consistency only" claim
    # is broken.
    assert c.openrouter_gemini_voice == "Despina"
    assert c.openrouter_gemini_model == "google/gemini-3.1-flash-tts-preview"
    assert c.piper_length_scale == 1.0
    assert c.edge_tts_voice == "zh-CN-XiaoxiaoNeural"
