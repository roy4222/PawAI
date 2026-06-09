"""Unit tests for benchmarks.core.object_matrix (object 矩陣量測純邏輯)。"""
from benchmarks.core.object_matrix import (
    CSV_HEADER,
    csv_row,
    detections_for,
    other_labels,
    summarize_cell,
    summarize_trial,
    verdict_for,
)


def _ev(*objs):
    return {"event_type": "object_detected", "objects": list(objs)}


def _obj(name, conf, bbox=None):
    return {"class_name": name, "confidence": conf, "bbox": bbox or [0, 0, 10, 10]}


def test_detections_for_filters_target():
    ev = _ev(_obj("chair", 0.8, [1, 2, 3, 4]), _obj("cup", 0.6))
    assert detections_for(ev, "chair") == [(0.8, [1, 2, 3, 4])]


def test_detections_for_handles_missing_objects_key():
    assert detections_for({"event_type": "object_detected"}, "chair") == []


def test_summarize_trial_picks_max_conf():
    events = [_ev(_obj("chair", 0.6)), _ev(_obj("chair", 0.82, [5, 6, 7, 8]))]
    tr = summarize_trial(events, "chair", conf_min=0.0)
    assert tr.detected is True
    assert tr.confidence == 0.82
    assert tr.bbox == [5, 6, 7, 8]


def test_summarize_trial_miss_when_below_conf_min():
    tr = summarize_trial([_ev(_obj("chair", 0.3))], "chair", conf_min=0.5)
    assert tr.detected is False
    assert tr.confidence is None


def test_summarize_trial_miss_when_absent():
    tr = summarize_trial([_ev(_obj("cup", 0.9))], "chair", conf_min=0.0)
    assert tr.detected is False


def test_summarize_cell_rate_and_verdict_pass():
    trials = [summarize_trial([_ev(_obj("chair", 0.7))], "chair", 0.0) for _ in range(4)]
    trials.append(summarize_trial([_ev(_obj("cup", 0.7))], "chair", 0.0))  # 1 miss
    cell = summarize_cell(trials)
    assert cell["success"] == 4
    assert cell["trials"] == 5
    assert cell["success_rate"] == 0.8
    assert cell["avg_confidence"] == 0.7
    assert cell["verdict"] == "PASS"
    assert cell["low_conf"] is False


def test_summarize_cell_degraded():
    trials = [summarize_trial([_ev(_obj("cup", 0.7))], "cup", 0.0) for _ in range(3)]
    trials += [summarize_trial([], "cup", 0.0) for _ in range(2)]
    cell = summarize_cell(trials)
    assert cell["success_rate"] == 0.6
    assert cell["verdict"] == "DEGRADED"


def test_summarize_cell_empty_is_fail():
    cell = summarize_cell([])
    assert cell["success_rate"] == 0.0
    assert cell["verdict"] == "FAIL"
    assert cell["avg_confidence"] is None
    assert cell["bbox"] is None


def test_verdict_low_conf_flag():
    v, low = verdict_for(1.0, 0.40)
    assert (v, low) == ("PASS", True)
    v2, low2 = verdict_for(0.4, 0.9)
    assert (v2, low2) == ("FAIL", False)


def test_other_labels_dedup_sorted():
    events = [_ev(_obj("chair", 0.8), _obj("cup", 0.6)),
              _ev(_obj("bottle", 0.5), _obj("cup", 0.7))]
    assert other_labels(events, "chair") == ["bottle", "cup"]


def test_csv_row_matches_header_length_and_bbox_format():
    cell = summarize_cell([summarize_trial([_ev(_obj("chair", 0.7))], "chair", 0.0)])
    row = {"timestamp": "t", "object": "chair", "distance_m": 1.0, "light": "normal",
           "angle": "front", "misclass": ["cup", "bottle"], "notes": "", **cell}
    out = csv_row(row)
    assert len(out) == len(CSV_HEADER)
    assert out[CSV_HEADER.index("bbox")] == "0|0|10|10"
    assert out[CSV_HEADER.index("misclass")] == "cup|bottle"
    assert out[CSV_HEADER.index("verdict")] == "PASS"
