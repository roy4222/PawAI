"""Aggregate baseline JSONL records into a capability scoreboard snapshot.

The snapshot carries static capability metadata plus the derived Brain allow
decision. This module is intentionally pure Python and does not connect to
Brain runtime or ROS.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

from .grader import Criterion, GRADE_INSUFFICIENT, brain_allowed, grade_capability
from .scoreboard_schema import CAPABILITY_META


@dataclass
class CapabilityScore:
    capability_id: str
    grade: str
    sample_count: int
    success_rate: float
    false_trigger_rate: float
    latency_p50: Optional[float]
    latency_p90: Optional[float]
    confirmed: bool
    positive_count: int = 0
    idle_count: int = 0
    registered_recall: Optional[float] = None
    unknown_false_accept_rate: Optional[float] = None
    wrong_person_count: int = 0


def _pctl(values: list[Optional[float]], p: float) -> Optional[float]:
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    k = int(round((p / 100.0) * (len(xs) - 1)))
    k = max(0, min(len(xs) - 1, k))
    return xs[k]


def load_results(path: str) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _scenario_kind(record: dict) -> str:
    return record.get("scenario_kind", "positive")


def _passed(record: dict) -> bool:
    return record.get("pass_fail") == "pass"


def _false_triggered(record: dict) -> bool:
    return record.get("false_trigger") is True


def _rate(count: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return count / total


def _round_optional(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 3)


def aggregate(
    records: list[dict],
    criteria_by_capability: dict[str, list[Criterion]],
    confirm_min: int = 3,
) -> dict[str, CapabilityScore]:
    """Aggregate records by capability without mixing positive and idle scenarios."""
    by_capability: dict[str, list[dict]] = {}
    for record in records:
        by_capability.setdefault(record["capability_id"], []).append(record)

    scores: dict[str, CapabilityScore] = {}
    for capability_id, cap_records in by_capability.items():
        sample_count = len(cap_records)
        positives = [r for r in cap_records if _scenario_kind(r) == "positive"]
        idles = [r for r in cap_records if _scenario_kind(r) == "idle"]

        success_rate = _rate(sum(1 for r in cap_records if _passed(r)), sample_count)
        false_trigger_rate = _rate(
            sum(1 for r in cap_records if _false_triggered(r)),
            sample_count,
        )
        registered_recall = _rate(sum(1 for r in positives if _passed(r)), len(positives))
        unknown_false_accept_rate = _rate(
            sum(1 for r in idles if _false_triggered(r)),
            len(idles),
        )
        wrong_person_count = sum(1 for r in positives if _false_triggered(r))
        latencies = [r.get("latency_ms") for r in cap_records]

        metrics = {
            "success_rate": success_rate,
            "false_trigger_rate": false_trigger_rate,
            "latency_p50": _pctl(latencies, 50),
            "latency_p90": _pctl(latencies, 90),
            "registered_recall": registered_recall,
            "unknown_false_accept_rate": unknown_false_accept_rate,
            "wrong_person_count": wrong_person_count,
        }
        grade = grade_capability(
            metrics,
            criteria_by_capability.get(capability_id, []),
            sample_count,
            confirm_min,
        )
        scores[capability_id] = CapabilityScore(
            capability_id=capability_id,
            grade=grade,
            sample_count=sample_count,
            success_rate=round(success_rate, 3) if success_rate is not None else 0.0,
            false_trigger_rate=round(false_trigger_rate, 3)
            if false_trigger_rate is not None
            else 0.0,
            latency_p50=metrics["latency_p50"],
            latency_p90=metrics["latency_p90"],
            confirmed=sample_count >= confirm_min,
            positive_count=len(positives),
            idle_count=len(idles),
            registered_recall=_round_optional(registered_recall),
            unknown_false_accept_rate=_round_optional(unknown_false_accept_rate),
            wrong_person_count=wrong_person_count,
        )
    return scores


def _empty_score_dict(capability_id: str) -> dict:
    return {
        "capability_id": capability_id,
        "grade": GRADE_INSUFFICIENT,
        "sample_count": 0,
        "success_rate": None,
        "false_trigger_rate": None,
        "latency_p50": None,
        "latency_p90": None,
        "confirmed": False,
        "positive_count": 0,
        "idle_count": 0,
        "registered_recall": None,
        "unknown_false_accept_rate": None,
        "wrong_person_count": 0,
    }


def to_snapshot(scores: dict[str, CapabilityScore], run_meta: dict) -> dict:
    run_trusted = bool(run_meta.get("run_trusted", False))
    capabilities = {}

    for capability_id, meta in CAPABILITY_META.items():
        if capability_id in scores:
            capability = asdict(scores[capability_id])
        else:
            capability = _empty_score_dict(capability_id)

        if not run_trusted:
            capability["grade"] = GRADE_INSUFFICIENT
            capability["failure_reason"] = (
                f"layer0_preflight={run_meta.get('layer0_preflight_status', 'unknown')}"
            )

        capability["claim_level"] = meta["claim_level"]
        capability["risk_role"] = meta["risk_role"]
        capability["depth"] = meta["depth"]
        capability["dependency_role"] = meta["dependency_role"]
        capability["brain_allowed"] = brain_allowed(
            capability["grade"],
            meta["claim_level"],
        )
        capabilities[capability_id] = capability

    return {
        "schema_version": "scoreboard-0.1",
        **run_meta,
        "capabilities": capabilities,
    }


def write_snapshot(
    scores: dict[str, CapabilityScore],
    run_meta: dict,
    out_path: str,
) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(to_snapshot(scores, run_meta), f, ensure_ascii=False, indent=2)
