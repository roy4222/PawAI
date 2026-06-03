from benchmarks.core.perception_baseline_observer import (
    RoundMeta,
    count_false_triggers,
    enrich_record,
    evaluate_round,
    filter_window,
    normalize_gesture_event,
    normalize_object_event,
)


def test_idle_round_no_observation_is_pass_no_false_trigger():
    meta = RoundMeta("gesture.wave", "idle_hand_60s", expected_label="none", window_start_ts=100.0)
    rec = evaluate_round(meta, observations=[])
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["predicted_label"] == "none"


def test_idle_round_with_observation_is_false_trigger_fail():
    meta = RoundMeta("gesture.wave", "idle_hand_60s", expected_label="none", window_start_ts=100.0)
    rec = evaluate_round(meta, observations=[("wave", 1.0, 103.0)])
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is True
    assert rec["predicted_label"] == "wave"


def test_positive_round_matched_is_pass_with_latency():
    meta = RoundMeta("gesture.wave", "wave_1.5m", expected_label="wave",
                     distance_m=1.5, window_start_ts=100.0)
    rec = evaluate_round(meta, observations=[("wave", 1.0, 100.4)])
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["predicted_label"] == "wave"
    assert abs(rec["latency_ms"] - 400.0) < 1e-6
    assert rec["distance_m"] == 1.5


def test_positive_round_no_observation_is_miss_not_false_trigger():
    meta = RoundMeta("object.cup", "cup_1.5m", expected_label="cup", window_start_ts=0.0)
    rec = evaluate_round(meta, observations=[])
    assert rec["pass_fail"] == "fail"          # miss
    assert rec["false_trigger"] is False       # 漏報不是誤觸
    assert rec["predicted_label"] == "none"


def test_positive_round_wrong_label_is_miss_not_false_trigger():
    meta = RoundMeta("object.cup", "cup_1.5m", expected_label="cup", window_start_ts=0.0)
    rec = evaluate_round(meta, observations=[("bottle", 0.7, 1.0)])
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is False       # 認錯類別算 miss，誤觸只用於 idle round
    assert rec["predicted_label"] == "bottle"


def test_count_false_triggers_over_idle_rounds():
    rounds = [
        evaluate_round(RoundMeta("gesture.wave", "idle", "none", window_start_ts=0.0),
                       observations=[]),
        evaluate_round(RoundMeta("gesture.wave", "idle", "none", window_start_ts=0.0),
                       observations=[("point", 0.8, 1.0)]),
    ]
    assert count_false_triggers(rounds) == 1


def test_normalize_gesture_event_returns_observation_tuple():
    data = {
        "stamp": 100.5,
        "event_type": "gesture_detected",
        "gesture": "wave",
        "confidence": 0.9,
        "hand": "right",
    }

    assert normalize_gesture_event(data) == [("wave", 0.9, 100.5)]


def test_normalize_gesture_event_without_gesture_returns_empty():
    data = {
        "stamp": 100.5,
        "event_type": "gesture_detected",
        "confidence": 0.9,
        "hand": "right",
    }

    assert normalize_gesture_event(data) == []


def test_normalize_object_event_returns_multiple_observation_tuples():
    data = {
        "stamp": 200.0,
        "event_type": "object_detected",
        "objects": [
            {"class_name": "cup", "confidence": 0.8, "bbox": [1, 2, 3, 4], "color": "red"},
            {"class_name": "bottle", "confidence": 0.6, "bbox": [5, 6, 7, 8], "color": "blue"},
        ],
    }

    assert normalize_object_event(data) == [
        ("cup", 0.8, 200.0),
        ("bottle", 0.6, 200.0),
    ]


def test_normalize_object_event_without_objects_returns_empty():
    data = {"stamp": 200.0, "event_type": "object_detected"}

    assert normalize_object_event(data) == []


def test_filter_window_is_inclusive_sorts_and_supports_open_end():
    observations = [
        ("late", 0.7, 3.0),
        ("start", 0.8, 1.0),
        ("before", 0.5, 0.9),
        ("end", 0.9, 2.0),
        ("after", 0.4, 2.1),
    ]

    assert filter_window(observations, 1.0, 2.0) == [
        ("start", 0.8, 1.0),
        ("end", 0.9, 2.0),
    ]
    assert filter_window(observations, 2.0, None) == [
        ("end", 0.9, 2.0),
        ("after", 0.4, 2.1),
        ("late", 0.7, 3.0),
    ]


def test_enrich_record_adds_run_fields_without_mutating_input():
    record = {"pass_fail": "pass"}

    enriched = enrich_record(record, "gesture-object-run", "abc123")

    assert record == {"pass_fail": "pass"}
    assert enriched["pass_fail"] == "pass"
    assert enriched["run_id"] == "gesture-object-run"
    assert enriched["git_commit"] == "abc123"
    assert "timestamp" in enriched


def test_enrich_record_does_not_overwrite_existing_keys():
    record = {
        "run_id": "existing-run",
        "timestamp": "existing-ts",
        "git_commit": "existing-commit",
    }

    enriched = enrich_record(record, "new-run", "new-commit")

    assert enriched["run_id"] == "existing-run"
    assert enriched["timestamp"] == "existing-ts"
    assert enriched["git_commit"] == "existing-commit"
