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


CSV_FIELDS = [
    "round_id", "mode", "utterance_text", "expected_intent", "session_id",
    "speech_start_ts", "speech_end_ts",
    "asr_ts", "asr_text", "asr_latency_ms",
    "intent_ts", "intent", "intent_confidence", "intent_latency_ms",
    "tts_ts", "tts_text",
    "webrtc_play_start_ts", "webrtc_play_end_ts", "last_audio_chunk_ts",
    "audio_chunks_count", "e2e_latency_ms", "match", "status",
    "correlated_by_time", "notes",
]

PASS_CRITERIA = {
    "fixed_accuracy_ge_80pct": {"threshold": 0.80, "higher_is_better": True},
    "e2e_median_le_3500ms": {"threshold": 3500, "higher_is_better": False},
    "e2e_max_le_6000ms": {"threshold": 6000, "higher_is_better": False},
    "play_ok_rate_ge_80pct": {"threshold": 0.80, "higher_is_better": True},
}


class ReportGenerator:
    def __init__(self, output_dir: str, test_name: str, yaml_file: str):
        self.output_dir = output_dir
        self.test_name = test_name
        self.yaml_file = yaml_file
        os.makedirs(output_dir, exist_ok=True)

    def _timestamp_suffix(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def write_csv(self, rounds: List[RoundRecord], suffix: str = "") -> str:
        suffix = suffix or self._timestamp_suffix()
        path = os.path.join(self.output_dir, f"speech_test_{suffix}.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for r in rounds:
                row = {k: getattr(r, k, "") for k in CSV_FIELDS}
                writer.writerow(row)
        return path

    def compute_summary(self, rounds: List[RoundRecord]) -> dict:
        completed = [r for r in rounds if r.status != "timeout"]
        fixed = [r for r in rounds if r.mode == "fixed"]
        free = [r for r in rounds if r.mode == "free"]

        status_counts = {"complete": 0, "partial": 0, "timeout": 0, "orphan": 0, "pending": 0}
        for r in rounds:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        fixed_hit = sum(1 for r in fixed if r.match == "hit")
        fixed_miss = sum(1 for r in fixed if r.match == "miss")
        fixed_empty = sum(1 for r in fixed if not r.asr_text and r.expected_intent)
        fixed_total = len(fixed)
        fixed_accuracy = fixed_hit / fixed_total if fixed_total > 0 else 0.0

        free_with_expected = [r for r in free if r.expected_intent]
        free_hit = sum(1 for r in free_with_expected if r.match == "hit")
        free_miss = sum(1 for r in free_with_expected if r.match == "miss")
        free_unknown = sum(1 for r in free if r.intent == "unknown")

        e2e_values = [r.e2e_latency_ms for r in completed if r.e2e_latency_ms > 0]
        asr_values = [r.asr_latency_ms for r in completed if r.asr_latency_ms > 0]

        def safe_median(vals):
            return round(statistics.median(vals), 1) if vals else 0

        def safe_quantile(vals, q):
            if not vals:
                return 0
            sorted_v = sorted(vals)
            idx = int(math.ceil(q * len(sorted_v))) - 1
            return round(sorted_v[max(0, idx)], 1)

        num_completed = len(completed) or 1
        tts_ok_rate = round(sum(1 for r in completed if r.tts_ts > 0) / num_completed, 3)
        play_ok_rate = round(
            sum(1 for r in completed if r.webrtc_play_start_ts > 0) / num_completed, 3
        )

        actuals = {
            "fixed_accuracy_ge_80pct": fixed_accuracy,
            "e2e_median_le_3500ms": safe_median(e2e_values),
            "e2e_max_le_6000ms": max(e2e_values) if e2e_values else 0,
            "play_ok_rate_ge_80pct": play_ok_rate,
        }
        criteria_results = {}
        for key, spec in PASS_CRITERIA.items():
            actual = actuals[key]
            threshold = spec["threshold"]
            if spec["higher_is_better"]:
                passed = actual >= threshold
            else:
                passed = actual <= threshold
            criteria_results[key] = {
                "threshold": threshold,
                "actual": round(actual, 3),
                "pass": passed,
            }

        grade = self._compute_grade(criteria_results, PASS_CRITERIA)

        return {
            "test_name": self.test_name,
            "yaml_file": self.yaml_file,
            "date": datetime.now().isoformat(timespec="seconds"),
            "total_rounds": len(rounds),
            "completed": len(completed),
            "status_breakdown": status_counts,
            "fixed_rounds": {
                "total": fixed_total,
                "hit": fixed_hit,
                "miss": fixed_miss,
                "empty": fixed_empty,
                "accuracy": round(fixed_accuracy, 3),
            },
            "free_rounds": {
                "total": len(free),
                "with_expected": len(free_with_expected),
                "hit": free_hit,
                "miss": free_miss,
                "unknown": free_unknown,
                "no_expected": len(free) - len(free_with_expected),
            },
            "latency": {
                "e2e_median_ms": safe_median(e2e_values),
                "e2e_p90_ms": safe_quantile(e2e_values, 0.9),
                "e2e_max_ms": round(max(e2e_values), 1) if e2e_values else 0,
                "asr_median_ms": safe_median(asr_values),
                "asr_max_ms": round(max(asr_values), 1) if asr_values else 0,
                "tts_ok_rate": tts_ok_rate,
                "play_ok_rate": play_ok_rate,
            },
            "pass_criteria": criteria_results,
            "grade": grade,
        }

    def _compute_grade(self, results: dict, specs: dict) -> str:
        failures = []
        for key, result in results.items():
            if not result["pass"]:
                spec = specs[key]
                threshold = spec["threshold"]
                actual = result["actual"]
                if spec["higher_is_better"]:
                    deviation = (threshold - actual) / threshold if threshold else 0
                else:
                    deviation = (actual - threshold) / threshold if threshold else 0
                failures.append(deviation)
        if not failures:
            return "PASS"
        if len(failures) == 1 and failures[0] <= 0.10:
            return "MARGINAL"
        return "FAIL"

    def write_summary(self, summary: dict, suffix: str = "") -> str:
        suffix = suffix or self._timestamp_suffix()
        path = os.path.join(self.output_dir, f"speech_test_{suffix}_summary.json")
        with open(path, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        return path
