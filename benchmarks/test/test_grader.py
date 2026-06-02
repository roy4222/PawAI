from benchmarks.core.grader import (
    Criterion,
    grade_capability,
    brain_allowed,
    GRADE_PASS,
    GRADE_DEGRADED,
    GRADE_FAIL,
    GRADE_INSUFFICIENT,
)

HIGHER = Criterion(
    metric="success_rate",
    pass_min=0.90,
    degraded_min=0.80,
    higher_is_better=True,
)
LOWER = Criterion(
    metric="false_trigger_rate",
    pass_min=0.10,
    degraded_min=0.30,
    higher_is_better=False,
)


def test_zero_samples_is_insufficient():
    assert (
        grade_capability({"success_rate": 0.99}, [HIGHER], sample_count=0)
        == GRADE_INSUFFICIENT
    )


def test_empty_criteria_is_not_pass():
    # 缺 criteria 無從判斷 -> fail-closed，絕不可 pass
    assert (
        grade_capability({"success_rate": 0.99}, [], sample_count=5)
        == GRADE_INSUFFICIENT
    )


def test_all_pass_but_unconfirmed_is_degraded():
    assert grade_capability({"success_rate": 0.95}, [HIGHER], sample_count=1) == GRADE_DEGRADED


def test_all_pass_and_confirmed_is_pass():
    assert grade_capability({"success_rate": 0.95}, [HIGHER], sample_count=3) == GRADE_PASS


def test_any_metric_fail_is_fail():
    metrics = {"success_rate": 0.95, "false_trigger_rate": 0.40}
    assert grade_capability(metrics, [HIGHER, LOWER], sample_count=5) == GRADE_FAIL


def test_lower_is_better_band():
    assert grade_capability({"false_trigger_rate": 0.05}, [LOWER], sample_count=5) == GRADE_PASS
    assert (
        grade_capability({"false_trigger_rate": 0.20}, [LOWER], sample_count=5)
        == GRADE_DEGRADED
    )


def test_degraded_band_dominates_over_unconfirmed():
    assert grade_capability({"success_rate": 0.85}, [HIGHER], sample_count=5) == GRADE_DEGRADED


def test_brain_allowed_only_pass_and_mainline():
    # claim_level 只能更嚴：pass 但 future -> 不放行
    assert brain_allowed(GRADE_PASS, "mainline") is True
    assert brain_allowed(GRADE_PASS, "future") is False
    assert brain_allowed(GRADE_PASS, "studio_only") is False
    assert brain_allowed(GRADE_DEGRADED, "mainline") is False
    assert brain_allowed(GRADE_FAIL, "mainline") is False
    assert brain_allowed(GRADE_INSUFFICIENT, "mainline") is False
