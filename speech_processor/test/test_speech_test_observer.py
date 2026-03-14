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
