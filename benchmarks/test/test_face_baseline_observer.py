from benchmarks.core.face_baseline_observer import (
    FaceRoundMeta,
    FaceStateSnapshot,
    enrich_record,
    evaluate_face_round,
    filter_face_window,
    load_face_round_meta,
    parse_face_state,
)


def test_parse_face_state_normal() -> None:
    payload = {
        "stamp": 123.4,
        "face_count": 1,
        "tracks": [
            {
                "track_id": 7,
                "stable_name": "alice",
                "sim": 0.91,
                "distance_m": 1.2,
                "bbox": [1, 2, 3, 4],
                "mode": "recognized",
            }
        ],
    }

    snapshot = parse_face_state(payload)

    assert snapshot == FaceStateSnapshot(ts=123.4, tracks=payload["tracks"])


def test_parse_face_state_missing_tracks_defaults_to_empty_list() -> None:
    snapshot = parse_face_state({"stamp": "5.5", "face_count": 0})

    assert snapshot == FaceStateSnapshot(ts=5.5, tracks=[])


def test_filter_face_window_includes_boundaries_sorts_and_supports_open_end() -> None:
    snapshots = [
        FaceStateSnapshot(ts=3.0, tracks=[]),
        FaceStateSnapshot(ts=1.0, tracks=[]),
        FaceStateSnapshot(ts=2.0, tracks=[]),
        FaceStateSnapshot(ts=4.0, tracks=[]),
    ]

    bounded = filter_face_window(snapshots, 2.0, 3.0)
    open_ended = filter_face_window(snapshots, 2.0, None)

    assert [snapshot.ts for snapshot in bounded] == [2.0, 3.0]
    assert [snapshot.ts for snapshot in open_ended] == [2.0, 3.0, 4.0]


def test_load_face_round_meta_reads_example_yaml() -> None:
    rounds = load_face_round_meta("benchmarks/core/round_meta.face.example.yaml")

    assert rounds == [
        FaceRoundMeta(
            capability_id="face.recognition",
            scenario_id="alice_1m_01",
            expected_label="alice",
            distance_m=1.0,
            scenario_kind="positive",
        ),
        FaceRoundMeta(
            capability_id="face.recognition",
            scenario_id="alice_2m_01",
            expected_label="alice",
            distance_m=2.0,
            scenario_kind="positive",
        ),
        FaceRoundMeta(
            capability_id="face.recognition",
            scenario_id="stranger_idle_01",
            expected_label="unknown",
            scenario_kind="idle",
        ),
    ]


def test_enrich_record_adds_common_fields_without_overwriting() -> None:
    record = {
        "pass_fail": "pass",
        "run_id": "existing-run",
        "timestamp": "2026-06-03T00:00:00+00:00",
        "git_commit": "existing-commit",
    }

    enriched = enrich_record(record, run_id="new-run", git_commit="new-commit")

    assert enriched["pass_fail"] == "pass"
    assert enriched["run_id"] == "existing-run"
    assert enriched["timestamp"] == "2026-06-03T00:00:00+00:00"
    assert enriched["git_commit"] == "existing-commit"
    assert enriched is not record


# --- 復原：原 #75 的 evaluate_face_round 核心測試（Codex 誤刪，review 補回）---
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
