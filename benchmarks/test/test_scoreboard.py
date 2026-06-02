from benchmarks.core.scoreboard import aggregate, to_snapshot
from benchmarks.core.grader import Criterion, GRADE_PASS, GRADE_FAIL

CRIT = {
    "gesture.wave": [
        Criterion("success_rate", 0.90, 0.80, higher_is_better=True),
        Criterion("false_trigger_rate", 0.10, 0.30, higher_is_better=False),
    ],
}


def _rec(cap, ok, ft=False, lat=100.0, kind="positive"):
    return {
        "capability_id": cap,
        "pass_fail": "pass" if ok else "fail",
        "false_trigger": ft,
        "latency_ms": lat,
        "scenario_kind": kind,
    }


def test_aggregate_success_rate_and_grade():
    recs = [_rec("gesture.wave", True) for _ in range(4)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    s = scores["gesture.wave"]
    assert s.sample_count == 4
    assert s.success_rate == 1.0
    assert s.false_trigger_rate == 0.0
    assert s.confirmed is True
    assert s.grade == GRADE_PASS


def test_aggregate_false_trigger_forces_fail():
    recs = [_rec("gesture.wave", True, ft=True) for _ in range(4)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    assert scores["gesture.wave"].grade == GRADE_FAIL


def test_aggregate_separates_recall_from_false_accept():
    # F2: known/unknown are not mixed. 3 positive hits + 2 idle with 1 false accept.
    recs = [
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", False, ft=True, kind="idle"),
        _rec("face.recognition", True, kind="idle"),
    ]
    s = aggregate(recs, {}, confirm_min=3)["face.recognition"]
    assert s.positive_count == 3 and s.idle_count == 2
    assert s.registered_recall == 1.0
    assert s.unknown_false_accept_rate == 0.5
    assert s.wrong_person_count == 0


def test_aggregate_wrong_person_counted_on_positive_round():
    recs = [
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", False, ft=True, kind="positive"),
    ]
    s = aggregate(recs, {}, confirm_min=3)["face.recognition"]
    assert s.wrong_person_count == 1
    assert s.registered_recall == 0.5


def test_snapshot_carries_claim_level_and_brain_allowed():
    recs = [_rec("gesture.wave", True, lat=v) for v in (50, 100, 150, 200)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    snap = to_snapshot(
        scores,
        {
            "git_commit": "abc",
            "timestamp": "2026-05-31T00:00:00Z",
            "run_trusted": True,
        },
    )
    assert snap["git_commit"] == "abc"
    cap = snap["capabilities"]["gesture.wave"]
    assert cap["latency_p50"] is not None and cap["latency_p90"] is not None
    assert cap["claim_level"] == "mainline"
    assert cap["risk_role"] == "convenience"
    assert cap["dependency_role"] == "trigger"
    assert cap["brain_allowed"] is True


def test_future_capability_not_brain_allowed_even_if_pass():
    recs = [_rec("nav.dynamic_avoidance", True) for _ in range(4)]
    crit = {"nav.dynamic_avoidance": [Criterion("success_rate", 0.9, 0.8)]}
    scores = aggregate(recs, crit, confirm_min=3)
    snap = to_snapshot(scores, {"git_commit": "abc", "run_trusted": True})
    cap = snap["capabilities"]["nav.dynamic_avoidance"]
    assert cap["brain_allowed"] is False


def test_snapshot_always_lists_all_15_capabilities():
    recs = [_rec("gesture.wave", True) for _ in range(4)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    snap = to_snapshot(scores, {"git_commit": "abc", "run_trusted": True})
    assert len(snap["capabilities"]) == 15
    untested = snap["capabilities"]["face.recognition"]
    assert untested["grade"] == "insufficient_data"
    assert untested["sample_count"] == 0
    assert untested["success_rate"] is None
    assert untested["brain_allowed"] is False
    assert untested["dependency_role"] == "content"
    assert snap["capabilities"]["gesture.wave"]["grade"] == "pass"


def test_missing_run_trusted_defaults_failclosed():
    recs = [_rec("gesture.wave", True) for _ in range(5)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    snap = to_snapshot(scores, {"git_commit": "abc"})
    assert snap["capabilities"]["gesture.wave"]["grade"] == "insufficient_data"
    assert all(c["grade"] == "insufficient_data" for c in snap["capabilities"].values())


def test_layer0_preflight_fail_forces_all_insufficient():
    recs = [_rec("gesture.wave", True) for _ in range(5)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    assert scores["gesture.wave"].grade == "pass"
    snap = to_snapshot(
        scores,
        {
            "git_commit": "abc",
            "run_trusted": False,
            "layer0_preflight_status": "fail",
        },
    )
    cap = snap["capabilities"]["gesture.wave"]
    assert cap["grade"] == "insufficient_data"
    assert cap["brain_allowed"] is False
    assert cap["failure_reason"] == "layer0_preflight=fail"
    assert cap["success_rate"] is not None
    assert all(c["grade"] == "insufficient_data" for c in snap["capabilities"].values())
