"""Four-tier capability grader (v0.1).

Pure functions with no ROS dependencies. The grader combines threshold bands
with sample sufficiency, then derives a conservative Brain allow decision from
grade and claim level.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

GRADE_PASS = "pass"
GRADE_DEGRADED = "degraded"
GRADE_FAIL = "fail"
GRADE_INSUFFICIENT = "insufficient_data"


@dataclass
class Criterion:
    metric: str
    pass_min: float
    degraded_min: float
    higher_is_better: bool = True


def grade_one(value: Optional[float], crit: Criterion) -> str:
    """Grade a single metric. Missing values fail closed."""
    if value is None:
        return GRADE_FAIL
    if crit.higher_is_better:
        if value >= crit.pass_min:
            return GRADE_PASS
        if value >= crit.degraded_min:
            return GRADE_DEGRADED
        return GRADE_FAIL

    if value <= crit.pass_min:
        return GRADE_PASS
    if value <= crit.degraded_min:
        return GRADE_DEGRADED
    return GRADE_FAIL


def grade_capability(
    metrics: dict,
    criteria: list[Criterion],
    sample_count: int,
    confirm_min: int = 3,
) -> str:
    """Combine threshold bands and sample sufficiency into a four-tier grade."""
    if sample_count <= 0:
        return GRADE_INSUFFICIENT
    if not criteria:
        return GRADE_INSUFFICIENT

    grades = [grade_one(metrics.get(crit.metric), crit) for crit in criteria]
    if GRADE_FAIL in grades:
        return GRADE_FAIL
    if GRADE_DEGRADED in grades:
        return GRADE_DEGRADED
    if sample_count < confirm_min:
        return GRADE_DEGRADED
    return GRADE_PASS


def brain_allowed(grade: str, claim_level: str) -> bool:
    """Allow Brain mainline only when grade passes and claim level is mainline."""
    return grade == GRADE_PASS and claim_level == "mainline"
