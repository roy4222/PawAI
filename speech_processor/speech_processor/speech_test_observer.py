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


class SessionAggregator:
    """Aggregates topic events into RoundRecords."""

    def __init__(self, tts_correlation_window_s: float = 3.0):
        self.rounds: List[RoundRecord] = []
        self._pending_meta: Optional[Dict] = None
        self._prev_state: str = "LISTENING"
        self._auto_round_id: int = 0
        self.tts_correlation_window_s = tts_correlation_window_s

    def _current_round(self) -> Optional[RoundRecord]:
        return self.rounds[-1] if self.rounds else None

    def _find_round_by_session(self, session_id: str) -> Optional[RoundRecord]:
        for r in reversed(self.rounds):
            if r.session_id == session_id:
                return r
        return None

    def _find_round_for_correlation(self, ts: float) -> Optional[RoundRecord]:
        for r in reversed(self.rounds):
            if r.intent_ts > 0 and (ts - r.intent_ts) <= self.tts_correlation_window_s:
                return r
        return None

    def _find_round_with_play_start(self) -> Optional[RoundRecord]:
        for r in reversed(self.rounds):
            if r.webrtc_play_start_ts > 0 and r.webrtc_play_end_ts == 0.0:
                return r
        return None

    def set_pending_meta(self, round_id: int, mode: str,
                         expected_intent: str, utterance_text: str) -> None:
        self._pending_meta = {
            "round_id": round_id,
            "mode": mode,
            "expected_intent": expected_intent,
            "utterance_text": utterance_text,
        }

    def on_state_change(self, old_state: str, new_state: str, ts: float) -> None:
        if old_state == "LISTENING" and new_state == "RECORDING":
            self._auto_round_id += 1
            r = RoundRecord(speech_start_ts=ts)
            if self._pending_meta:
                r.round_id = self._pending_meta["round_id"]
                r.mode = self._pending_meta["mode"]
                r.expected_intent = self._pending_meta["expected_intent"]
                r.utterance_text = self._pending_meta["utterance_text"]
                self._pending_meta = None
            else:
                r.round_id = self._auto_round_id
            self.rounds.append(r)
        elif old_state == "RECORDING" and new_state == "TRANSCRIBING":
            r = self._current_round()
            if r and r.speech_end_ts == 0.0:
                r.speech_end_ts = ts
        self._prev_state = new_state

    def on_asr_result(self, session_id: str, text: str, provider: str,
                      latency_ms: float, ts: float) -> None:
        r = self._current_round()
        if r and not r.session_id:
            r.session_id = session_id
            r.asr_text = text
            r.asr_ts = ts
            r.asr_latency_ms = latency_ms

    def on_intent_event(self, session_id: str, intent: str,
                        confidence: float, latency_ms: float, ts: float) -> None:
        r = self._find_round_by_session(session_id)
        if not r:
            r = self._current_round()
        if r:
            r.intent = intent
            r.intent_ts = ts
            r.intent_confidence = confidence
            r.intent_latency_ms = latency_ms

    def on_tts(self, text: str, ts: float) -> None:
        r = self._find_round_for_correlation(ts)
        if r and r.tts_ts == 0.0:
            r.tts_ts = ts
            r.tts_text = text
            r.correlated_by_time = True

    def on_webrtc_req(self, api_id: int, ts: float) -> None:
        if api_id == 4001:
            r = self._find_round_for_correlation(ts)
            if not r:
                r = self._current_round()
            if r and r.webrtc_play_start_ts == 0.0:
                r.webrtc_play_start_ts = ts
                r.correlated_by_time = True
        elif api_id in (4002, 4003):
            r = self._find_round_with_play_start()
            if not r:
                return
            if api_id == 4003:
                r.audio_chunks_count += 1
                r.last_audio_chunk_ts = ts
            else:
                r.webrtc_play_end_ts = ts

    def finalize_round(self, index: int) -> RoundRecord:
        r = self.rounds[index]
        if r.speech_start_ts > 0 and r.webrtc_play_start_ts > 0:
            r.e2e_latency_ms = round(
                (r.webrtc_play_start_ts - r.speech_start_ts) * 1000, 1
            )
        if r.expected_intent:
            if not r.asr_text:
                r.match = "empty"
            elif r.intent == r.expected_intent:
                r.match = "hit"
            else:
                r.match = "miss"
        r.status = compute_round_status(r)
        return r
