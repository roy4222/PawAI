from benchmarks.core.face_baseline_observer import (
    FaceRoundMeta,
    FaceStateSnapshot,
    evaluate_face_round,
)


def _snap(ts, tracks):
    return FaceStateSnapshot(ts=ts, tracks=tracks)


def test_idle_round_with_known_person_is_false_trigger():
    meta = FaceRoundMeta(
        "face.recognition",
        "idle_unknown_1.5m",
        expected_label="unknown",
        distance_m=1.5,
        window_start_ts=100.0,
    )
    snaps = [
        _snap(
            101.0,
            [
                {
                    "track_id": 1,
                    "stable_name": "roy",
                    "sim": 0.9,
                    "distance_m": 1.5,
                    "mode": "stable",
                }
            ],
        )
    ]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is True
    assert rec["predicted_label"] == "roy"


def test_idle_round_only_unknown_tracks_is_pass():
    meta = FaceRoundMeta(
        "face.recognition",
        "idle_unknown_1.5m",
        expected_label="unknown",
        window_start_ts=100.0,
    )
    snaps = [
        _snap(
            101.0,
            [
                {
                    "track_id": 1,
                    "stable_name": "unknown",
                    "sim": 0.2,
                    "distance_m": 1.5,
                    "mode": "hold",
                }
            ],
        )
    ]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False


def test_positive_round_correct_match_is_pass_with_distance():
    meta = FaceRoundMeta(
        "face.recognition",
        "known_roy_1.5m",
        expected_label="roy",
        distance_m=1.5,
        window_start_ts=100.0,
    )
    snaps = [
        _snap(
            100.5,
            [
                {
                    "track_id": 1,
                    "stable_name": "roy",
                    "sim": 0.92,
                    "distance_m": 1.48,
                    "mode": "stable",
                }
            ],
        )
    ]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["confidence"] == 0.92
    assert rec["distance_m"] == 1.48
    assert rec["distance_source"] == "d435_depth"


def test_positive_round_miss_is_fail_not_false_trigger():
    meta = FaceRoundMeta(
        "face.recognition",
        "known_roy_3m",
        expected_label="roy",
        distance_m=3.0,
        window_start_ts=100.0,
    )
    snaps = [
        _snap(
            101.0,
            [
                {
                    "track_id": 1,
                    "stable_name": "unknown",
                    "sim": 0.3,
                    "distance_m": 3.0,
                    "mode": "hold",
                }
            ],
        )
    ]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is False


def test_positive_round_wrong_person_is_false_accept():
    meta = FaceRoundMeta(
        "face.recognition",
        "known_roy_1.5m",
        expected_label="roy",
        distance_m=1.5,
        window_start_ts=100.0,
    )
    snaps = [
        _snap(
            101.0,
            [
                {
                    "track_id": 1,
                    "stable_name": "alice",
                    "sim": 0.88,
                    "distance_m": 1.5,
                    "mode": "stable",
                }
            ],
        )
    ]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is True
    assert rec["predicted_label"] == "alice"
