"""Speech test observer node — pure observation + recording for 30-round validation."""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
import time
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class RoundRecord:
    session_id: str = ""
    round_id: int = 0
    mode: str = ""
    expected_intent: str = ""
    utterance_text: str = ""
    speech_start_ts: float = 0.0
    speech_end_ts: float = 0.0
    asr_ts: float = 0.0
    asr_text: str = ""
    asr_latency_ms: float = 0.0
    intent_ts: float = 0.0
    intent: str = ""
    intent_confidence: float = 0.0
    intent_latency_ms: float = 0.0
    tts_ts: float = 0.0
    tts_text: str = ""
    webrtc_play_start_ts: float = 0.0
    webrtc_play_end_ts: float = 0.0
    last_audio_chunk_ts: float = 0.0
    audio_chunks_count: int = 0
    e2e_latency_ms: float = 0.0
    match: str = "n/a"
    status: str = "pending"
    correlated_by_time: bool = False
    notes: str = ""


def compute_round_status(r: RoundRecord) -> str:
    has_speech = r.speech_start_ts > 0
    has_asr = r.asr_ts > 0
    has_intent = r.intent_ts > 0
    has_tts = r.tts_ts > 0
    has_play_start = r.webrtc_play_start_ts > 0

    if (has_tts or has_play_start) and not has_speech and not has_asr:
        return "orphan"
    if has_speech and has_asr and has_intent and has_tts and has_play_start:
        return "complete"
    if has_speech or has_asr:
        return "partial"
    return "timeout"
