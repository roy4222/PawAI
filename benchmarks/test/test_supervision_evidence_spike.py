import json

from benchmarks.scripts import supervision_evidence_spike as sut


def test_parse_object_jsonl_into_detection_events():
    lines = [
        json.dumps({
            "frame": 10,
            "timestamp": 1.25,
            "bbox": [1, 2, 30, 40],
            "class": "cup",
            "conf": 0.42,
            "decision_id": "dec-001",
        }),
        "",
        json.dumps({
            "frame": 11,
            "bbox": [2, 3, 31, 41],
            "class_name": "chair",
            "confidence": 0.37,
        }),
    ]

    events = sut.parse_detection_jsonl_lines(lines)

    assert len(events) == 2
    assert events[0].frame == 10
    assert events[0].bbox == (1.0, 2.0, 30.0, 40.0)
    assert events[0].class_name == "cup"
    assert events[0].confidence == 0.42
    assert events[0].decision_id == "dec-001"
    assert events[1].class_name == "chair"


def test_confidence_filter_supports_035_baseline_and_030_track_buffer():
    events = [
        sut.DetectionEvent(1, None, (0, 0, 10, 10), "cup", 0.32, "d-low"),
        sut.DetectionEvent(2, None, (0, 0, 10, 10), "cup", 0.33, "d-low"),
        sut.DetectionEvent(3, None, (0, 0, 10, 10), "cup", 0.34, "d-low"),
        sut.DetectionEvent(4, None, (20, 20, 30, 30), "chair", 0.36, "d-high"),
    ]

    baseline = sut.filter_detection_events(events, conf=0.35, track_buffer=1)
    low_conf_tracked = sut.filter_detection_events(events, conf=0.30, track_buffer=3)

    assert [event.decision_id for event in baseline] == ["d-high"]
    assert [event.frame for event in low_conf_tracked] == [3]


def test_decision_id_is_carried_in_custom_data_join_field():
    event = sut.DetectionEvent(7, 0.7, (1, 2, 3, 4), "person", 0.9, "join-777")

    custom_data = sut.build_custom_data(event)

    assert custom_data["decision_id"] == "join-777"
    assert custom_data["join_field"] == "decision_id"
    assert custom_data["frame"] == 7
