# 語音主路徑 30 輪驗收 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable 30-round end-to-end validation framework for the speech pipeline (no-VAD → ASR → Intent → TTS → Go2 playback), including observer node, clean-start script, test YAML, and orchestration script.

**Architecture:** Observer node subscribes to ROS2 topics, aggregates per-round timing data by session_id and state transitions, outputs CSV + JSON summary. Shell scripts handle environment cleanup and test orchestration with operator prompts. Topic-based req/ack for control (no custom .srv).

**Tech Stack:** Python 3 / ROS2 Humble / std_msgs / go2_interfaces / PyYAML / Bash/Zsh

**Spec:** `docs/superpowers/specs/2026-03-14-speech-30round-validation-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `speech_processor/speech_processor/speech_test_observer.py` | Observer node: subscribe topics, aggregate RoundRecords, write CSV/JSON |
| Create | `speech_processor/test/test_speech_test_observer.py` | Unit tests for observer logic (no ROS2 runtime needed) |
| Create | `test_scripts/speech_30round.yaml` | 30-round test definition (15 fixed + 15 free) |
| Create | `scripts/clean_speech_env.sh` | Environment cleanup (kill sessions, pkill nodes, verify clean) |
| Create | `scripts/run_speech_test.sh` | Test orchestration (clean → build → launch → observe → report) |
| Modify | `speech_processor/setup.py:30-38` | Add `speech_test_observer` entry_point |
| Modify | `scripts/start_asr_tts_no_vad_tmux.sh:58-61` | Replace manual kill with `bash clean_speech_env.sh` |

---

## Chunk 1: Observer Node Core — RoundRecord + State Machine

### Task 1: RoundRecord dataclass + YAML loader

**Files:**
- Create: `speech_processor/speech_processor/speech_test_observer.py`
- Create: `speech_processor/test/test_speech_test_observer.py`

- [ ] **Step 0: Create test directory**

```bash
mkdir -p speech_processor/test
touch speech_processor/test/__init__.py
```

- [ ] **Step 1: Write test for RoundRecord defaults and status logic**

```python
# speech_processor/test/test_speech_test_observer.py
import pytest
from speech_processor.speech_test_observer import RoundRecord, compute_round_status


def test_round_record_defaults():
    r = RoundRecord()
    assert r.session_id == ""
    assert r.round_id == 0
    assert r.mode == ""
    assert r.expected_intent == ""
    assert r.status == "pending"
    assert r.audio_chunks_count == 0
    assert r.correlated_by_time is False


def test_status_complete():
    r = RoundRecord(
        speech_start_ts=1.0,
        speech_end_ts=2.0,
        asr_ts=2.5,
        intent_ts=2.6,
        tts_ts=3.0,
        webrtc_play_start_ts=3.5,
        webrtc_play_end_ts=5.0,
    )
    assert compute_round_status(r) == "complete"


def test_status_partial_no_tts():
    r = RoundRecord(
        speech_start_ts=1.0,
        speech_end_ts=2.0,
        asr_ts=2.5,
        intent_ts=2.6,
    )
    assert compute_round_status(r) == "partial"


def test_status_timeout():
    r = RoundRecord()  # nothing filled
    assert compute_round_status(r) == "timeout"


def test_status_orphan():
    """Orphan: got TTS/webrtc but no matching session context."""
    r = RoundRecord(
        tts_ts=3.0,
        webrtc_play_start_ts=3.5,
    )
    assert compute_round_status(r) == "orphan"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/roy422/newLife/elder_and_dog
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement RoundRecord + compute_round_status**

```python
# speech_processor/speech_processor/speech_test_observer.py
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
    mode: str = ""                    # "fixed" | "free"
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
    match: str = "n/a"               # "hit" | "miss" | "n/a"
    status: str = "pending"          # computed later
    correlated_by_time: bool = False
    notes: str = ""


def compute_round_status(r: RoundRecord) -> str:
    """Determine round status based on which fields are populated.

    - complete: speech_start through webrtc_play_end all present
    - partial: has speech/asr/intent but missing tts or play
    - orphan: has tts/webrtc but no speech_start or asr
    - timeout: nothing meaningful populated
    """
    has_speech = r.speech_start_ts > 0
    has_asr = r.asr_ts > 0
    has_intent = r.intent_ts > 0
    has_tts = r.tts_ts > 0
    has_play_start = r.webrtc_play_start_ts > 0

    # Orphan: got downstream events but no upstream context
    if (has_tts or has_play_start) and not has_speech and not has_asr:
        return "orphan"

    # Complete: full chain populated
    if has_speech and has_asr and has_intent and has_tts and has_play_start:
        return "complete"

    # Partial: at least speech or asr started but chain incomplete
    if has_speech or has_asr:
        return "partial"

    return "timeout"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/roy422/newLife/elder_and_dog
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add speech_processor/speech_processor/speech_test_observer.py speech_processor/test/test_speech_test_observer.py
git commit -m "feat(observer): add RoundRecord dataclass and status logic"
```

---

### Task 2: State machine tracking + session aggregation

**Files:**
- Modify: `speech_processor/speech_processor/speech_test_observer.py`
- Modify: `speech_processor/test/test_speech_test_observer.py`

- [ ] **Step 1: Write tests for SessionAggregator**

```python
# Append to test_speech_test_observer.py
from speech_processor.speech_test_observer import SessionAggregator


def test_state_transition_creates_round():
    agg = SessionAggregator()
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    assert len(agg.rounds) == 1
    assert agg.rounds[0].speech_start_ts == 100.0


def test_state_recording_to_transcribing():
    agg = SessionAggregator()
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_state_change("RECORDING", "TRANSCRIBING", ts=102.0)
    assert agg.rounds[0].speech_end_ts == 102.0


def test_asr_result_binds_session_id():
    agg = SessionAggregator()
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="whisper_local",
                      latency_ms=600.0, ts=102.5)
    r = agg.rounds[0]
    assert r.session_id == "sp-001"
    assert r.asr_text == "你好"
    assert r.asr_ts == 102.5


def test_intent_event_fills_record():
    agg = SessionAggregator()
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    r = agg.rounds[0]
    assert r.intent == "greet"
    assert r.intent_confidence == 0.95


def test_tts_correlation_by_time():
    agg = SessionAggregator(tts_correlation_window_s=3.0)
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    agg.on_tts(text="哈囉，我在這裡。", ts=103.0)
    r = agg.rounds[0]
    assert r.tts_ts == 103.0
    assert r.tts_text == "哈囉，我在這裡。"
    assert r.correlated_by_time is True


def test_tts_outside_window_not_correlated():
    agg = SessionAggregator(tts_correlation_window_s=1.0)
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    agg.on_tts(text="哈囉", ts=106.0)  # 3.4s after intent, > 1.0 window
    r = agg.rounds[0]
    assert r.tts_ts == 0.0  # not correlated


def test_webrtc_events():
    agg = SessionAggregator(tts_correlation_window_s=3.0)
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    agg.on_webrtc_req(api_id=4001, ts=103.5)
    agg.on_webrtc_req(api_id=4003, ts=103.6)
    agg.on_webrtc_req(api_id=4003, ts=103.7)
    agg.on_webrtc_req(api_id=4002, ts=104.0)
    r = agg.rounds[0]
    assert r.webrtc_play_start_ts == 103.5
    assert r.webrtc_play_end_ts == 104.0
    assert r.audio_chunks_count == 2
    assert r.last_audio_chunk_ts == 103.7


def test_e2e_latency_computed():
    agg = SessionAggregator(tts_correlation_window_s=3.0)
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    agg.on_webrtc_req(api_id=4001, ts=103.5)
    agg.on_webrtc_req(api_id=4002, ts=104.0)
    r = agg.finalize_round(0)
    assert r.e2e_latency_ms == 3500.0  # (103.5 - 100.0) * 1000
    assert r.status == "partial"  # no tts


def test_pending_meta_binds_to_next_round():
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    r = agg.rounds[0]
    assert r.round_id == 1
    assert r.mode == "fixed"
    assert r.expected_intent == "greet"
    # pending_meta consumed
    assert agg._pending_meta is None


def test_match_logic():
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    r = agg.finalize_round(0)
    assert r.match == "hit"


def test_match_miss():
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="過來", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="come_here",
                        confidence=0.8, latency_ms=5.0, ts=102.6)
    r = agg.finalize_round(0)
    assert r.match == "miss"


def test_match_empty():
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="unknown",
                        confidence=0.0, latency_ms=5.0, ts=102.6)
    r = agg.finalize_round(0)
    assert r.match == "empty"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v -k "test_state or test_asr or test_intent or test_tts or test_webrtc or test_e2e or test_pending or test_match"
```

Expected: `ImportError: cannot import name 'SessionAggregator'`

- [ ] **Step 3: Implement SessionAggregator**

Add to `speech_test_observer.py` after `compute_round_status`:

```python
class SessionAggregator:
    """Aggregates topic events into RoundRecords.

    State machine tracking:
    - LISTENING → RECORDING = speech_start (new round)
    - RECORDING → TRANSCRIBING = speech_end

    Session binding:
    - State transition creates the RoundRecord
    - /asr_result binds session_id to the current round

    TTS/webrtc correlation:
    - No session_id, uses time window after intent_ts
    """

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
        """Find the most recent round whose intent_ts is within correlation window."""
        for r in reversed(self.rounds):
            if r.intent_ts > 0 and (ts - r.intent_ts) <= self.tts_correlation_window_s:
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

    def _find_round_with_play_start(self) -> Optional[RoundRecord]:
        """Find most recent round that has webrtc_play_start but no play_end."""
        for r in reversed(self.rounds):
            if r.webrtc_play_start_ts > 0 and r.webrtc_play_end_ts == 0.0:
                return r
        return None

    def on_webrtc_req(self, api_id: int, ts: float) -> None:
        if api_id == 4001:
            # START_AUDIO: correlate by time window (same as TTS)
            r = self._find_round_for_correlation(ts)
            if not r:
                r = self._current_round()
            if r and r.webrtc_play_start_ts == 0.0:
                r.webrtc_play_start_ts = ts
                r.correlated_by_time = True
        elif api_id in (4002, 4003):
            # SEND_AUDIO_BLOCK / STOP_AUDIO: attach to round that already has play_start
            r = self._find_round_with_play_start()
            if not r:
                return
            if api_id == 4003:
                r.audio_chunks_count += 1
                r.last_audio_chunk_ts = ts
            else:  # 4002
                r.webrtc_play_end_ts = ts

    def finalize_round(self, index: int) -> RoundRecord:
        r = self.rounds[index]
        # Compute e2e latency
        if r.speech_start_ts > 0 and r.webrtc_play_start_ts > 0:
            r.e2e_latency_ms = round(
                (r.webrtc_play_start_ts - r.speech_start_ts) * 1000, 1
            )
        # Compute match
        if r.expected_intent:
            if not r.asr_text:
                r.match = "empty"
            elif r.intent == r.expected_intent:
                r.match = "hit"
            else:
                r.match = "miss"
        r.status = compute_round_status(r)
        return r
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add speech_processor/speech_processor/speech_test_observer.py speech_processor/test/test_speech_test_observer.py
git commit -m "feat(observer): add SessionAggregator with state machine + correlation"
```

---

### Task 3: CSV + Summary JSON report generation

**Files:**
- Modify: `speech_processor/speech_processor/speech_test_observer.py`
- Modify: `speech_processor/test/test_speech_test_observer.py`

- [ ] **Step 1: Write tests for report generation**

```python
# Append to test_speech_test_observer.py
import tempfile
import os
from speech_processor.speech_test_observer import ReportGenerator


def _make_complete_round(round_id, mode, expected, intent, e2e_ms):
    return RoundRecord(
        session_id=f"sp-{round_id:03d}",
        round_id=round_id,
        mode=mode,
        expected_intent=expected,
        intent=intent,
        speech_start_ts=100.0,
        speech_end_ts=102.0,
        asr_ts=102.5,
        asr_text="test",
        intent_ts=102.6,
        intent_confidence=0.9,
        tts_ts=103.0,
        webrtc_play_start_ts=100.0 + e2e_ms / 1000,
        webrtc_play_end_ts=105.0,
        e2e_latency_ms=e2e_ms,
        match="hit" if intent == expected else ("miss" if expected else "n/a"),
        status="complete",
        correlated_by_time=True,
    )


def test_csv_output():
    rounds = [
        _make_complete_round(1, "fixed", "greet", "greet", 2000),
        _make_complete_round(2, "fixed", "stop", "unknown", 2500),
    ]
    with tempfile.TemporaryDirectory() as d:
        gen = ReportGenerator(output_dir=d, test_name="test", yaml_file="test.yaml")
        csv_path = gen.write_csv(rounds)
        assert os.path.exists(csv_path)
        with open(csv_path) as f:
            lines = f.readlines()
        assert len(lines) == 3  # header + 2 rows


def test_summary_json_grade_pass():
    rounds = [_make_complete_round(i, "fixed", "greet", "greet", 2000) for i in range(1, 16)]
    with tempfile.TemporaryDirectory() as d:
        gen = ReportGenerator(output_dir=d, test_name="test", yaml_file="test.yaml")
        summary = gen.compute_summary(rounds)
        assert summary["grade"] == "PASS"
        assert summary["fixed_rounds"]["accuracy"] == 1.0


def test_summary_json_grade_fail():
    rounds = []
    for i in range(1, 16):
        intent = "greet" if i <= 5 else "unknown"  # 5/15 = 33%
        rounds.append(_make_complete_round(i, "fixed", "greet", intent, 2000))
    with tempfile.TemporaryDirectory() as d:
        gen = ReportGenerator(output_dir=d, test_name="test", yaml_file="test.yaml")
        summary = gen.compute_summary(rounds)
        assert summary["grade"] == "FAIL"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v -k "test_csv or test_summary"
```

Expected: `ImportError: cannot import name 'ReportGenerator'`

- [ ] **Step 3: Implement ReportGenerator**

Add to `speech_test_observer.py`:

```python
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

        # Status breakdown
        status_counts = {"complete": 0, "partial": 0, "timeout": 0, "orphan": 0, "pending": 0}
        for r in rounds:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        # Fixed rounds stats
        fixed_hit = sum(1 for r in fixed if r.match == "hit")
        fixed_miss = sum(1 for r in fixed if r.match == "miss")
        fixed_empty = sum(1 for r in fixed if not r.asr_text and r.expected_intent)
        fixed_total = len(fixed)
        fixed_accuracy = fixed_hit / fixed_total if fixed_total > 0 else 0.0

        # Free rounds stats
        free_with_expected = [r for r in free if r.expected_intent]
        free_hit = sum(1 for r in free_with_expected if r.match == "hit")
        free_miss = sum(1 for r in free_with_expected if r.match == "miss")
        free_unknown = sum(1 for r in free if r.intent == "unknown")

        # Latency stats
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

        # Pass criteria evaluation
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add speech_processor/speech_processor/speech_test_observer.py speech_processor/test/test_speech_test_observer.py
git commit -m "feat(observer): add ReportGenerator with CSV, summary JSON, grade logic"
```

---

### Task 4: ROS2 node wrapper

**Files:**
- Modify: `speech_processor/speech_processor/speech_test_observer.py`
- Modify: `speech_processor/setup.py:30-38`

- [ ] **Step 1: Add ROS2 node class to speech_test_observer.py**

Append to `speech_test_observer.py`:

```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Import conditionally to allow unit tests without ROS2
try:
    from go2_interfaces.msg import WebRtcReq
    _HAS_GO2 = True
except ImportError:
    _HAS_GO2 = False


class SpeechTestObserverNode(Node):
    def __init__(self):
        super().__init__("speech_test_observer")

        # Parameters
        self.declare_parameter("output_dir", "test_results")
        self.declare_parameter("tts_correlation_window_s", 3.0)
        self.declare_parameter("round_meta_timeout_s", 30.0)
        self.declare_parameter("round_complete_timeout_s", 10.0)

        output_dir = str(self.get_parameter("output_dir").value)
        tts_window = float(self.get_parameter("tts_correlation_window_s").value)
        self._meta_timeout = float(self.get_parameter("round_meta_timeout_s").value)

        self._aggregator = SessionAggregator(tts_correlation_window_s=tts_window)
        self._report_gen = ReportGenerator(
            output_dir=output_dir, test_name="", yaml_file=""
        )
        self._prev_state = "LISTENING"
        self._meta_set_time: float = 0.0
        self._round_complete_timeout = float(
            self.get_parameter("round_complete_timeout_s").value
        )

        # Subscribers — observation topics
        self.create_subscription(
            String, "/state/interaction/speech", self._on_speech_state, 10
        )
        self.create_subscription(
            String, "/asr_result", self._on_asr_result, 10
        )
        self.create_subscription(
            String, "/event/speech_intent_recognized", self._on_intent_event, 10
        )
        self.create_subscription(String, "/tts", self._on_tts, 10)
        if _HAS_GO2:
            self.create_subscription(
                WebRtcReq, "/webrtc_req", self._on_webrtc_req, 10
            )

        # Control topics — req/ack
        self.create_subscription(
            String, "/speech_test_observer/round_meta_req", self._on_round_meta_req, 10
        )
        self._meta_ack_pub = self.create_publisher(
            String, "/speech_test_observer/round_meta_ack", 10
        )
        self.create_subscription(
            String, "/speech_test_observer/generate_report_req",
            self._on_generate_report_req, 10
        )
        self._report_ack_pub = self.create_publisher(
            String, "/speech_test_observer/generate_report_ack", 10
        )

        # Timers
        self.create_timer(1.0, self._check_meta_timeout)
        self.create_timer(1.0, self._check_round_timeout)

        self.get_logger().info("speech_test_observer ready")

    def _on_speech_state(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        new_state = data.get("state", "")
        if new_state and new_state != self._prev_state:
            ts = time.time()
            self._aggregator.on_state_change(self._prev_state, new_state, ts)
            if self._prev_state == "LISTENING" and new_state == "RECORDING":
                self.get_logger().info(
                    f"[Round {len(self._aggregator.rounds)}] speech_start detected"
                )
            self._prev_state = new_state

    def _on_asr_result(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        self._aggregator.on_asr_result(
            session_id=data.get("session_id", ""),
            text=data.get("text", ""),
            provider=data.get("provider", ""),
            latency_ms=float(data.get("latency_ms", 0)),
            ts=time.time(),
        )

    def _on_intent_event(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        self._aggregator.on_intent_event(
            session_id=data.get("session_id", ""),
            intent=data.get("intent", "unknown"),
            confidence=float(data.get("confidence", 0)),
            latency_ms=float(data.get("latency_ms", 0)),
            ts=time.time(),
        )
        # Log per-round result
        r = self._aggregator._current_round()
        if r:
            self.get_logger().info(
                f"[Round {r.round_id}] intent={r.intent} "
                f"asr_text={r.asr_text!r}"
            )

    def _on_tts(self, msg: String) -> None:
        self._aggregator.on_tts(text=msg.data, ts=time.time())

    def _on_webrtc_req(self, msg) -> None:
        self._aggregator.on_webrtc_req(api_id=int(msg.api_id), ts=time.time())

    def _on_round_meta_req(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self._publish_ack(self._meta_ack_pub, {"ok": False})
            return
        self._aggregator.set_pending_meta(
            round_id=int(data.get("round_id", 0)),
            mode=str(data.get("mode", "")),
            expected_intent=str(data.get("expected_intent", "")),
            utterance_text=str(data.get("utterance_text", "")),
        )
        self._meta_set_time = time.time()
        self._publish_ack(
            self._meta_ack_pub,
            {"ok": True, "round_id": data.get("round_id", 0)},
        )
        self.get_logger().info(f"Round meta set: {data}")

    def _on_generate_report_req(self, msg: String) -> None:
        # Finalize all rounds
        for i in range(len(self._aggregator.rounds)):
            self._aggregator.finalize_round(i)
        rounds = self._aggregator.rounds
        suffix = self._report_gen._timestamp_suffix()
        csv_path = self._report_gen.write_csv(rounds, suffix=suffix)
        summary = self._report_gen.compute_summary(rounds)
        summary_path = self._report_gen.write_summary(summary, suffix=suffix)
        self._publish_ack(
            self._report_ack_pub,
            {"ok": True, "csv_path": csv_path, "summary_path": summary_path},
        )
        self.get_logger().info(
            f"Report generated: grade={summary['grade']} "
            f"csv={csv_path} summary={summary_path}"
        )

    def _publish_ack(self, pub, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=True)
        pub.publish(msg)

    def _check_round_timeout(self) -> None:
        """Auto-finalize rounds that have been pending too long."""
        now = time.time()
        for i, r in enumerate(self._aggregator.rounds):
            if r.status == "pending" and r.speech_start_ts > 0:
                if (now - r.speech_start_ts) > self._round_complete_timeout:
                    self._aggregator.finalize_round(i)
                    self.get_logger().warning(
                        f"[Round {r.round_id}] timed out after "
                        f"{self._round_complete_timeout}s, status={r.status}"
                    )

    def _check_meta_timeout(self) -> None:
        if (
            self._aggregator._pending_meta
            and self._meta_set_time > 0
            and (time.time() - self._meta_set_time) > self._meta_timeout
        ):
            self.get_logger().warning("Pending round meta expired, clearing")
            self._aggregator._pending_meta = None
            self._meta_set_time = 0.0


def main(args=None):
    rclpy.init(args=args)
    node = SpeechTestObserverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add entry_point to setup.py**

In `speech_processor/setup.py`, add to the `console_scripts` list:

```python
"speech_test_observer = speech_processor.speech_test_observer:main",
```

- [ ] **Step 3: Verify build**

```bash
cd /home/roy422/newLife/elder_and_dog
source /opt/ros/humble/setup.bash
colcon build --packages-select speech_processor
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add speech_processor/speech_processor/speech_test_observer.py speech_processor/setup.py
git commit -m "feat(observer): add ROS2 node wrapper with topic subscriptions and req/ack"
```

---

## Chunk 2: Shell Scripts + YAML + Integration

### Task 5: YAML test definition

**Files:**
- Create: `test_scripts/speech_30round.yaml`

- [ ] **Step 1: Create test_scripts directory and YAML**

Write the YAML file exactly as specified in the design spec (15 fixed rounds with 3x each of `greet`, `come_here`, `stop`, `take_photo`, `status` + 15 free rounds).

Full content: see spec `docs/superpowers/specs/2026-03-14-speech-30round-validation-design.md` §3.2.

- [ ] **Step 2: Validate YAML parses correctly**

```bash
python3 -c "
import yaml
with open('test_scripts/speech_30round.yaml') as f:
    data = yaml.safe_load(f)
assert len(data['fixed_rounds']) == 15
assert len(data['free_rounds']) == 15
assert all(r['expected_intent'] in ('greet','come_here','stop','take_photo','status') for r in data['fixed_rounds'])
print('YAML validation OK')
"
```

Expected: `YAML validation OK`

- [ ] **Step 3: Commit**

```bash
git add test_scripts/speech_30round.yaml
git commit -m "feat: add 30-round speech test YAML definition"
```

---

### Task 6: clean_speech_env.sh

**Files:**
- Create: `scripts/clean_speech_env.sh`
- Modify: `scripts/start_asr_tts_no_vad_tmux.sh:58-61`

- [ ] **Step 1: Write clean_speech_env.sh**

```bash
#!/usr/bin/env bash
# Clean speech test environment — kill sessions, nodes, verify clean.
# Usage: bash scripts/clean_speech_env.sh [--with-go2-driver]

set -euo pipefail

WITH_GO2_DRIVER=0
for arg in "$@"; do
  case "$arg" in
    --with-go2-driver) WITH_GO2_DRIVER=1 ;;
  esac
done

SPEECH_SESSIONS=("asr-tts-no-vad" "speech-e2e" "speech-test")
SPEECH_PROCS=("stt_intent_node" "intent_tts_bridge_node" "tts_node" "speech_test_observer")

if [ "$WITH_GO2_DRIVER" = "1" ]; then
  SPEECH_PROCS+=("go2_driver_node")
fi

KILLED_SESSIONS=0
KILLED_PROCS=0

# Step 1: Kill tmux sessions
for sess in "${SPEECH_SESSIONS[@]}"; do
  if tmux has-session -t "$sess" 2>/dev/null; then
    tmux kill-session -t "$sess" 2>/dev/null || true
    ((KILLED_SESSIONS++))
  fi
done

# Step 2: pkill speech nodes
for proc in "${SPEECH_PROCS[@]}"; do
  if pkill -f "$proc" 2>/dev/null; then
    ((KILLED_PROCS++))
  fi
done

# Step 3: Wait for processes to exit (max 5s)
WAITED=0
while [ $WAITED -lt 50 ]; do
  STILL_ALIVE=0
  for proc in "${SPEECH_PROCS[@]}"; do
    if pgrep -f "$proc" >/dev/null 2>&1; then
      STILL_ALIVE=1
      break
    fi
  done
  if [ "$STILL_ALIVE" = "0" ]; then
    break
  fi
  sleep 0.1
  ((WAITED++))
done

# Step 4: Check for residual processes
RESIDUAL=0
for proc in "${SPEECH_PROCS[@]}"; do
  PIDS=$(pgrep -f "$proc" 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "[WARN] Residual process: $proc (PIDs: $PIDS)"
    RESIDUAL=1
  fi
done

# Step 5: Output status
echo "[clean_speech_env] Killed $KILLED_SESSIONS sessions, $KILLED_PROCS process groups"

if [ "$RESIDUAL" = "1" ]; then
  echo "[WARN] Some processes could not be killed. Check manually."
  exit 1
fi

echo "[OK] Speech environment clean"
exit 0
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x scripts/clean_speech_env.sh
bash scripts/clean_speech_env.sh
```

Expected: `[OK] Speech environment clean` (nothing to kill on dev machine).

- [ ] **Step 3: Update start_asr_tts_no_vad_tmux.sh**

Replace lines 58-61:

```bash
# Old:
# tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
# pkill -f "/speech_processor/stt_intent_node" || true
# pkill -f "/speech_processor/intent_tts_bridge_node" || true
# pkill -f "/speech_processor/tts_node" || true

# New:
bash "$(dirname "$0")/clean_speech_env.sh" || { echo "[ERROR] clean_speech_env failed"; exit 1; }
```

- [ ] **Step 4: Commit**

```bash
git add scripts/clean_speech_env.sh scripts/start_asr_tts_no_vad_tmux.sh
git commit -m "feat: add clean_speech_env.sh and integrate into no-VAD launcher"
```

---

### Task 7: run_speech_test.sh

**Files:**
- Create: `scripts/run_speech_test.sh`

- [ ] **Step 1: Write run_speech_test.sh**

```bash
#!/usr/bin/env bash
# Orchestrate 30-round speech validation test.
# Usage: scripts/run_speech_test.sh [--yaml path] [--skip-build] [--skip-driver]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKDIR="/home/jetson/elder_and_dog"
CT2_LIB_PATH="$HOME/.local/ctranslate2-cuda/lib"
YAML_FILE="${SCRIPT_DIR}/../test_scripts/speech_30round.yaml"
SKIP_BUILD=0
SKIP_DRIVER=0

# Parse args
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
    --skip-driver) SKIP_DRIVER=1 ;;
    --yaml=*) YAML_FILE="${arg#*=}" ;;
    --yaml) shift; YAML_FILE="$1" ;;
  esac
done

if [ ! -f "$YAML_FILE" ]; then
  echo "[ERROR] YAML file not found: $YAML_FILE"
  exit 1
fi

echo "=== Speech 30-Round Validation ==="
echo "YAML: $YAML_FILE"

# Step 1: Clean environment
echo "[1/7] Cleaning environment..."
bash "$SCRIPT_DIR/clean_speech_env.sh" || { echo "[ERROR] Clean failed"; exit 1; }

# Step 2: Build (optional)
if [ "$SKIP_BUILD" = "0" ]; then
  echo "[2/7] Building..."
  cd "$WORKDIR"
  zsh -lc "source /opt/ros/humble/setup.zsh && colcon build --packages-select speech_processor go2_robot_sdk"
else
  echo "[2/7] Build skipped"
fi

cd "$WORKDIR"

# Step 3: Launch main nodes in tmux
echo "[3/7] Starting main nodes..."
SESSION_NAME="speech-test"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
CONN_TYPE="${CONN_TYPE:-webrtc}"

tmux new-session -d -s "$SESSION_NAME" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   export ROBOT_IP=$ROBOT_IP CONN_TYPE=$CONN_TYPE && \
   ros2 launch go2_robot_sdk robot.launch.py enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false'"

tmux split-window -h -t "$SESSION_NAME" \
  "zsh -lc 'setopt nonomatch; cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   export LD_LIBRARY_PATH=$CT2_LIB_PATH:\${LD_LIBRARY_PATH:-} && \
   ros2 run speech_processor stt_intent_node --ros-args \
   -p provider_order:=\"[\\\"whisper_local\\\"]\" \
   -p whisper_local.model_name:=small \
   -p whisper_local.device:=cuda \
   -p whisper_local.compute_type:=float16 \
   -p input_device:=0 \
   -p sample_rate:=16000 \
   -p capture_sample_rate:=44100'"

tmux split-window -v -t "$SESSION_NAME" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   ros2 run speech_processor intent_tts_bridge_node'"

PIPER_MODEL="/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
PIPER_CONFIG="/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json"
tmux split-window -v -t "$SESSION_NAME" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   export PATH=\"\$HOME/.local/bin:\$PATH\" && \
   ros2 run speech_processor tts_node --ros-args \
   -p provider:=piper \
   -p piper_model_path:=$PIPER_MODEL \
   -p piper_config_path:=$PIPER_CONFIG'"

# Step 4: Launch observer
echo "[4/7] Starting observer..."
tmux split-window -v -t "$SESSION_NAME" \
  "zsh -lc 'cd $WORKDIR && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   ros2 run speech_processor speech_test_observer --ros-args \
   -p output_dir:=$WORKDIR/test_results'"

# Health checks
echo "[4/7] Health checks..."

wait_for_topic() {
  local TOPIC="$1"
  local TIMEOUT="$2"
  local ELAPSED=0
  while [ $ELAPSED -lt "$TIMEOUT" ]; do
    if ros2 topic info "$TOPIC" 2>/dev/null | grep -q "Publisher count: [1-9]"; then
      return 0
    fi
    sleep 1
    ((ELAPSED++))
  done
  return 1
}

source /opt/ros/humble/setup.zsh 2>/dev/null || source /opt/ros/humble/setup.bash
source "$WORKDIR/install/setup.zsh" 2>/dev/null || source "$WORKDIR/install/setup.bash"

for CHECK in \
  "/speech_test_observer/round_meta_ack:15" \
  "/tts:15" \
  "/webrtc_req:15" \
  "/event/speech_intent_recognized:45"; do
  TOPIC="${CHECK%:*}"
  TIMEOUT="${CHECK#*:}"
  echo "  Waiting for $TOPIC (${TIMEOUT}s)..."
  if ! wait_for_topic "$TOPIC" "$TIMEOUT"; then
    echo "[ERROR] $TOPIC not ready after ${TIMEOUT}s"
    tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
    exit 1
  fi
  echo "  ✓ $TOPIC ready"
done

# Step 5: Warmup round
echo ""
echo "=== WARMUP (不計分) ==="
echo "請說任意一句話做暖機..."
read -rp "（完成後按 Enter）"
echo ""

# Step 5: Read YAML and run test loop
echo "[5/7] Running test rounds..."

ROUND_COUNT=$(python3 -c "
import yaml, json
with open('$YAML_FILE') as f:
    d = yaml.safe_load(f)
fixed = d.get('fixed_rounds', [])
free = d.get('free_rounds', [])
for r in fixed:
    print(json.dumps({'round_id': r['round_id'], 'mode': 'fixed',
          'expected_intent': r['expected_intent'], 'utterance': r.get('utterance',''),
          'notes': r.get('notes','')}))
for r in free:
    print(json.dumps({'round_id': r['round_id'], 'mode': 'free',
          'expected_intent': '', 'utterance': '',
          'notes': r.get('notes','')}))
")

echo "$ROUND_COUNT" | while IFS= read -r LINE; do
  ROUND_ID=$(echo "$LINE" | python3 -c "import sys,json; print(json.load(sys.stdin)['round_id'])")
  MODE=$(echo "$LINE" | python3 -c "import sys,json; print(json.load(sys.stdin)['mode'])")
  EXPECTED=$(echo "$LINE" | python3 -c "import sys,json; print(json.load(sys.stdin)['expected_intent'])")
  UTTERANCE=$(echo "$LINE" | python3 -c "import sys,json; print(json.load(sys.stdin)['utterance'])")
  NOTES=$(echo "$LINE" | python3 -c "import sys,json; print(json.load(sys.stdin)['notes'])")
  TOTAL=30

  echo ""
  if [ "$MODE" = "fixed" ]; then
    echo "[Round $ROUND_ID/$TOTAL] [FIXED] 請說：「$UTTERANCE」"
    echo "  expected_intent: $EXPECTED"
  else
    echo "[Round $ROUND_ID/$TOTAL] [FREE] 自由講"
    if [ -n "$NOTES" ]; then
      echo "  提示：$NOTES"
    fi
    read -rp "  expected_intent?（可留空）：" EXPECTED
  fi

  # Send round meta
  META_JSON="{\"round_id\":$ROUND_ID,\"mode\":\"$MODE\",\"expected_intent\":\"$EXPECTED\",\"utterance_text\":\"$UTTERANCE\"}"
  ros2 topic pub --once /speech_test_observer/round_meta_req std_msgs/msg/String "{data: '$META_JSON'}" >/dev/null 2>&1 &

  read -rp "  （準備好後按 Enter，輸入 q 結束）" INPUT
  if [ "$INPUT" = "q" ]; then
    echo "[INFO] 測試提前結束"
    break
  fi

  # Wait for round to complete (simple delay for observer to collect)
  sleep 3
done

# Step 6: Generate report
echo ""
echo "[6/7] Generating report..."
ros2 topic pub --once /speech_test_observer/generate_report_req std_msgs/msg/String "{data: '{}'}" >/dev/null 2>&1

# Wait for ack
sleep 2
ACK=$(timeout 5 ros2 topic echo --once /speech_test_observer/generate_report_ack std_msgs/msg/String 2>/dev/null || echo '{"ok":false}')
echo "$ACK"

# Step 7: Display summary
echo ""
echo "[7/7] Done!"
echo "Results in: test_results/"
ls -la test_results/ 2>/dev/null || echo "(no results yet)"

echo ""
echo "=== Test Complete ==="
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/run_speech_test.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run_speech_test.sh
git commit -m "feat: add run_speech_test.sh orchestration script"
```

---

### Task 8: Final integration — register entry_point, create test_results/.gitkeep

**Files:**
- Modify: `speech_processor/setup.py`
- Create: `test_results/.gitkeep`

- [ ] **Step 1: Verify setup.py entry_point was added in Task 4**

```bash
grep "speech_test_observer" speech_processor/setup.py
```

Expected: `"speech_test_observer = speech_processor.speech_test_observer:main",`

- [ ] **Step 2: Create test_results directory**

```bash
mkdir -p test_results
touch test_results/.gitkeep
echo "test_results/*.csv" >> .gitignore
echo "test_results/*.json" >> .gitignore
```

- [ ] **Step 3: Full build test**

```bash
source /opt/ros/humble/setup.bash
colcon build --packages-select speech_processor
source install/setup.bash
```

Expected: Build succeeds.

- [ ] **Step 4: Run all unit tests**

```bash
PYTHONPATH=speech_processor python -m pytest speech_processor/test/test_speech_test_observer.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add test_results/.gitkeep .gitignore speech_processor/setup.py
git commit -m "chore: add test_results dir, gitignore results, finalize setup.py"
```

---

## Implementation Notes

### Warmup round
- The orchestration script includes a warmup prompt before Round 1
- Warmup is **not counted** in the 30 rounds and not recorded by the observer
- Purpose: ensure Whisper model is loaded and audio pipeline is warm

### Observer `status=orphan` trigger conditions
- Received `/tts` or `/webrtc_req` events but no matching round has `speech_start_ts` or `asr_ts`
- This means downstream events arrived without an upstream speech session
- Most likely cause: residual TTS from a previous session, or observer started mid-conversation

### Testing on dev machine vs Jetson
- Unit tests (Tasks 1-3) run on dev machine — no ROS2 runtime needed
- ROS2 node (Task 4) and shell scripts (Tasks 5-7) require Jetson with full environment
- `go2_interfaces` import is conditional; unit tests work without it
