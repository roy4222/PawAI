from benchmarks.core.perception_baseline_observer import (
    RoundMeta, evaluate_round, count_false_triggers,
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
