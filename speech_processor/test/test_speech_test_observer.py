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
    r = RoundRecord(
        tts_ts=3.0,
        webrtc_play_start_ts=3.5,
    )
    assert compute_round_status(r) == "orphan"


from speech_processor.speech_test_observer import SessionAggregator


def test_state_transition_records_speech_start():
    """on_state_change(LISTENING→RECORDING) fills speech_start_ts on the latest
    pending round created by set_pending_meta."""
    agg = SessionAggregator(require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    assert len(agg.rounds) == 1
    assert agg.rounds[0].speech_start_ts == 100.0


def test_state_transition_no_ignored_events():
    """on_state_change without a pending round does nothing and does not
    increment ignored_events."""
    agg = SessionAggregator(require_meta=True)
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    assert len(agg.rounds) == 0
    assert agg.ignored_events == 0


def test_intent_event_ignored_without_meta():
    agg = SessionAggregator(require_meta=True)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    assert len(agg.rounds) == 0
    assert agg.ignored_events == 1


def test_state_recording_to_transcribing():
    """speech_end_ts is set on RECORDING→TRANSCRIBING on the latest pending round.
    After on_intent_event finalizes, the round is no longer pending so a second
    pending round is needed to receive the TRANSCRIBING timestamp."""
    agg = SessionAggregator(require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_state_change("RECORDING", "TRANSCRIBING", ts=102.0)
    assert agg.rounds[0].speech_end_ts == 102.0


def test_asr_result_binds_session_id():
    """set_pending_meta creates the round; on_state_change fills speech_start_ts;
    on_intent_event fills session_id and finalizes."""
    agg = SessionAggregator(require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.9, latency_ms=5.0, ts=102.5)
    r = agg.rounds[0]
    assert r.session_id == "sp-001"
    assert r.speech_start_ts == 100.0


def test_intent_event_fills_record():
    agg = SessionAggregator(require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    r = agg.rounds[0]
    assert r.intent == "greet"
    assert r.intent_confidence == 0.95


def test_tts_correlation_by_time():
    agg = SessionAggregator(tts_correlation_window_s=3.0, require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
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
    agg = SessionAggregator(tts_correlation_window_s=1.0, require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_asr_result(session_id="sp-001", text="你好", provider="w",
                      latency_ms=600.0, ts=102.5)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    agg.on_tts(text="哈囉", ts=106.0)  # 3.4s after intent, > 1.0 window
    r = agg.rounds[0]
    assert r.tts_ts == 0.0


def test_webrtc_events():
    agg = SessionAggregator(tts_correlation_window_s=3.0, require_meta=False)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
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
    """With pending_meta, speech_start_ts comes from _last_speech_start_ts (100.0).
    e2e = (webrtc_play_start 103.5 - speech_start 100.0) * 1000 = 3500ms."""
    agg = SessionAggregator(tts_correlation_window_s=3.0)
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    agg.on_webrtc_req(api_id=4001, ts=103.5)
    agg.on_webrtc_req(api_id=4002, ts=104.0)
    r = agg.finalize_round(0)
    assert r.e2e_latency_ms == 3500.0
    assert r.status == "partial"


def test_pending_meta_binds_to_next_round():
    """set_pending_meta immediately creates a pending RoundRecord.
    on_state_change fills speech_start_ts. on_intent_event finalizes."""
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    # Round is created immediately by set_pending_meta
    assert len(agg.rounds) == 1
    assert agg.rounds[0].status == "pending"
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    assert agg.rounds[0].speech_start_ts == 100.0
    # Intent event finalizes the round
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6)
    r = agg.rounds[0]
    assert r.round_id == 1
    assert r.mode == "fixed"
    assert r.expected_intent == "greet"
    assert r.speech_start_ts == 100.0
    assert r.status != "pending"  # finalized


def test_match_logic():
    """Round is created by on_intent_event with pending_meta.
    asr_text is filled via the text param of on_intent_event."""
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_intent_event(session_id="sp-001", intent="greet",
                        confidence=0.95, latency_ms=5.0, ts=102.6,
                        text="你好")
    r = agg.rounds[0]
    assert r.match == "hit"


def test_match_miss():
    """Round created by on_intent_event; asr_text via text param."""
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    agg.on_intent_event(session_id="sp-001", intent="come_here",
                        confidence=0.8, latency_ms=5.0, ts=102.6,
                        text="過來")
    r = agg.rounds[0]
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
