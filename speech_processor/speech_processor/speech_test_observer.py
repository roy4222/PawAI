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
    created_ts: float = 0.0


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

    def __init__(self, tts_correlation_window_s: float = 5.0,
                 require_meta: bool = True):
        self.rounds: List[RoundRecord] = []
        self._pending_meta: Optional[Dict] = None
        self._prev_state: str = "LISTENING"
        self._auto_round_id: int = 0
        self._last_speech_start_ts: float = 0.0
        self.tts_correlation_window_s = tts_correlation_window_s
        self.require_meta = require_meta
        self.ignored_events: int = 0

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
        """Rule 1: round_meta → immediately create a pending RoundRecord."""
        # Force-close any leftover pending round to avoid cross-contamination
        prev = self._latest_pending()
        if prev:
            idx = self.rounds.index(prev)
            prev.intent = prev.intent or "timeout"
            prev.status = "timeout"
            prev.match = "miss"
        r = RoundRecord()
        r.round_id = round_id
        r.mode = mode
        r.expected_intent = expected_intent
        r.utterance_text = utterance_text
        r.created_ts = time.time()
        self.rounds.append(r)

    def _latest_pending(self) -> Optional[RoundRecord]:
        """Find the most recent pending round."""
        for r in reversed(self.rounds):
            if r.status == "pending":
                return r
        return None

    def on_state_change(self, old_state: str, new_state: str, ts: float) -> None:
        """Rule 2: state changes just fill in timestamps on the latest pending round."""
        r = self._latest_pending()
        if not r:
            return
        if old_state == "LISTENING" and new_state == "RECORDING":
            if r.speech_start_ts == 0.0:
                r.speech_start_ts = ts
        elif old_state == "RECORDING" and new_state == "TRANSCRIBING":
            if r.speech_end_ts == 0.0:
                r.speech_end_ts = ts
        self._prev_state = new_state

    def on_asr_result(self, session_id: str, text: str, provider: str,
                      latency_ms: float, ts: float) -> None:
        """Rule 2: ASR result fills in fields on the latest pending round."""
        r = self._latest_pending()
        if r and not r.asr_text:
            r.session_id = session_id
            r.asr_text = text
            r.asr_ts = ts
            r.asr_latency_ms = latency_ms

    def on_intent_event(self, session_id: str, intent: str,
                        confidence: float, latency_ms: float, ts: float,
                        text: str = "") -> bool:
        """Rule 3: real intent → finalize immediately.
        Rule 5: hallucination → record but stay pending (let real intent or timeout close it).
        Returns True if a round was finalized."""
        r = self._latest_pending()
        if not r:
            self.ignored_events += 1
            return False

        # Hallucination: record details but keep round pending for real intent
        if intent == "hallucination":
            r.notes = f"hallucination:{text}" if text else "hallucination"
            if not r.session_id:
                r.session_id = session_id
            if not r.asr_text and text:
                r.asr_text = text
            if r.intent_ts == 0.0:
                r.intent_ts = ts
            return False

        # Real intent: fill fields and finalize
        r.intent = intent
        r.intent_ts = ts
        r.intent_confidence = confidence
        r.intent_latency_ms = latency_ms
        r.session_id = session_id
        if text and not r.asr_text:
            r.asr_text = text

        idx = self.rounds.index(r)
        self.finalize_round(idx)
        return True

    def finalize_as_timeout(self, round_id: int) -> Optional[RoundRecord]:
        """Rule 4: meta timeout → finalize as timeout/hallucination. Never delete."""
        for r in self.rounds:
            if r.round_id == round_id and r.status == "pending":
                # If hallucination was recorded, keep that info
                r.intent = "hallucination" if "hallucination" in r.notes else "timeout"
                r.status = "timeout"
                r.match = "miss"
                return r
        return None

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
            if r.intent in ("hallucination", "timeout"):
                r.match = "miss"
            elif not r.asr_text:
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


# ---------------------------------------------------------------------------
# ROS2 node wrapper
# ---------------------------------------------------------------------------

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String as RosString
    _HAS_ROS2 = True
except ImportError:
    _HAS_ROS2 = False

try:
    from go2_interfaces.msg import WebRtcReq
    _HAS_GO2 = True
except ImportError:
    _HAS_GO2 = False


if _HAS_ROS2:

    class SpeechTestObserverNode(Node):
        def __init__(self):
            super().__init__("speech_test_observer")

            self.declare_parameter("output_dir", "test_results")
            self.declare_parameter("tts_correlation_window_s", 5.0)
            self.declare_parameter("round_meta_timeout_s", 30.0)
            self.declare_parameter("round_complete_timeout_s", 10.0)

            output_dir = str(self.get_parameter("output_dir").value)
            tts_window = float(self.get_parameter("tts_correlation_window_s").value)
            self._meta_timeout = float(self.get_parameter("round_meta_timeout_s").value)
            self._round_complete_timeout = float(
                self.get_parameter("round_complete_timeout_s").value
            )

            self._aggregator = SessionAggregator(tts_correlation_window_s=tts_window)
            self._report_gen = ReportGenerator(
                output_dir=output_dir, test_name="", yaml_file=""
            )
            self._prev_state = "LISTENING"
            self._meta_set_time: float = 0.0

            self.create_subscription(
                RosString, "/state/interaction/speech", self._on_speech_state, 10
            )
            self.create_subscription(
                RosString, "/asr_result", self._on_asr_result, 10
            )
            self.create_subscription(
                RosString, "/event/speech_intent_recognized", self._on_intent_event, 10
            )
            self.create_subscription(RosString, "/tts", self._on_tts, 10)
            if _HAS_GO2:
                self.create_subscription(
                    WebRtcReq, "/webrtc_req", self._on_webrtc_req, 10
                )

            self.create_subscription(
                RosString, "/speech_test_observer/round_meta_req",
                self._on_round_meta_req, 10
            )
            self._meta_ack_pub = self.create_publisher(
                RosString, "/speech_test_observer/round_meta_ack", 10
            )
            self.create_subscription(
                RosString, "/speech_test_observer/generate_report_req",
                self._on_generate_report_req, 10
            )
            self._report_ack_pub = self.create_publisher(
                RosString, "/speech_test_observer/generate_report_ack", 10
            )
            self._round_done_pub = self.create_publisher(
                RosString, "/speech_test_observer/round_done_ack", 10
            )

            self.create_timer(1.0, self._check_meta_timeout)
            self.create_timer(1.0, self._check_round_timeout)

            self.get_logger().info("speech_test_observer ready")

        def _on_speech_state(self, msg) -> None:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                return
            new_state = data.get("state", "")
            if new_state and new_state != self._prev_state:
                ts = time.time()
                self._aggregator.on_state_change(self._prev_state, new_state, ts)
                if self._prev_state == "LISTENING" and new_state == "RECORDING":
                    if self._aggregator.rounds:
                        self.get_logger().info(
                            f"[Round {len(self._aggregator.rounds)}] speech_start detected"
                        )
                    else:
                        self.get_logger().debug(
                            "speech_start ignored (no pending round_meta)"
                        )
                self._prev_state = new_state

        def _on_asr_result(self, msg) -> None:
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

        def _on_intent_event(self, msg) -> None:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                return
            finalized = self._aggregator.on_intent_event(
                session_id=data.get("session_id", ""),
                intent=data.get("intent", "unknown"),
                confidence=float(data.get("confidence", 0)),
                latency_ms=float(data.get("latency_ms", 0)),
                ts=time.time(),
                text=data.get("text", ""),
            )
            if finalized:
                r = self._aggregator._current_round()
                if r:
                    self.get_logger().info(
                        f"[Round {r.round_id}] DONE intent={r.intent} "
                        f"match={r.match} asr_text={r.asr_text!r}"
                    )
                    self._publish_ack(
                        self._round_done_pub,
                        {"round_id": r.round_id, "intent": r.intent,
                         "asr_text": r.asr_text, "match": r.match},
                    )

        def _on_tts(self, msg) -> None:
            self._aggregator.on_tts(text=msg.data, ts=time.time())

        def _on_webrtc_req(self, msg) -> None:
            self._aggregator.on_webrtc_req(api_id=int(msg.api_id), ts=time.time())

        def _on_round_meta_req(self, msg) -> None:
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
            self.get_logger().info(f"Round {data.get('round_id')} created (pending)")

        def _on_generate_report_req(self, msg) -> None:
            for i in range(len(self._aggregator.rounds)):
                self._aggregator.finalize_round(i)
            rounds = self._aggregator.rounds
            suffix = self._report_gen._timestamp_suffix()
            csv_path = self._report_gen.write_csv(rounds, suffix=suffix)
            summary = self._report_gen.compute_summary(rounds)
            summary["ignored_events"] = self._aggregator.ignored_events
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
            msg = RosString()
            msg.data = json.dumps(payload, ensure_ascii=True)
            pub.publish(msg)

        def _check_round_timeout(self) -> None:
            """Removed — _check_meta_timeout handles all pending rounds via created_ts."""
            pass

        def _check_meta_timeout(self) -> None:
            """Rule 4: any pending round older than meta_timeout → finalize as timeout."""
            now = time.time()
            for r in self._aggregator.rounds:
                if r.status != "pending":
                    continue
                if r.created_ts > 0 and (now - r.created_ts) > self._meta_timeout:
                    result = self._aggregator.finalize_as_timeout(r.round_id)
                    self.get_logger().warning(
                        f"[Round {r.round_id}] timeout → intent={r.intent} "
                        f"({self._meta_timeout}s since creation)"
                    )
                    self._publish_ack(
                        self._round_done_pub,
                        {"round_id": r.round_id, "intent": r.intent,
                         "asr_text": r.asr_text, "match": r.match},
                    )


def main(args=None):
    if not _HAS_ROS2:
        raise RuntimeError("rclpy is not available — cannot run SpeechTestObserverNode")
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
