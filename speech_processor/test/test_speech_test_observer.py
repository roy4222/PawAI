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
    assert r.tts_ts == 0.0


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
    assert r.e2e_latency_ms == 3500.0
    assert r.status == "partial"


def test_pending_meta_binds_to_next_round():
    agg = SessionAggregator()
    agg.set_pending_meta(round_id=1, mode="fixed",
                         expected_intent="greet", utterance_text="你好")
    agg.on_state_change("LISTENING", "RECORDING", ts=100.0)
    r = agg.rounds[0]
    assert r.round_id == 1
    assert r.mode == "fixed"
    assert r.expected_intent == "greet"
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
