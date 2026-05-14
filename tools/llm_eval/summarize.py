#!/usr/bin/env python3
"""Auto-summarize an eval results JSON — produces markdown tables ready to
paste into docs/pawai-brain/specs/2026-05-04-llm-eval-result.md.

Usage:
    python tools/llm_eval/summarize.py results/stage3-full-2026-05-04.json
    python tools/llm_eval/summarize.py results/stage3-full-2026-05-04.json --md > section.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Per-token USD prices (verified 2026-05-04)
PRICE = {
    "google/gemini-3-flash-preview": (5e-7, 3e-6),
    "deepseek/deepseek-v4-flash":    (1.4e-7, 2.8e-7),
    "qwen/qwen3.6-flash":            (2.5e-7, 1.5e-6),
    "qwen/qwen3.6-plus":             (3.25e-7, 1.95e-6),
}


def call_cost(slug: str, prompt_tok: int, completion_tok: int) -> float:
    pin, pout = PRICE.get(slug, (0.0, 0.0))
    return prompt_tok * pin + completion_tok * pout


def safe_score_axis(rows: list[dict], axis: str) -> float | None:
    vals = [r["scores"][axis] for r in rows if r.get("scores") and axis in r["scores"]]
    return sum(vals) / len(vals) if vals else None


def summarize(results: list[dict]) -> dict:
    by_model: dict[str, dict] = defaultdict(
        lambda: {
            "n": 0, "ok": 0, "empty": 0, "in": 0, "out": 0, "lat": [],
            "cost": 0.0, "by_bucket": defaultdict(list), "rows": [],
        }
    )
    for r in results:
        m = by_model[r["model_alias"]]
        m["n"] += 1
        m["rows"].append(r)
        m["by_bucket"][r["bucket"]].append(r)
        raw = r.get("raw") or {}
        if raw.get("ok"):
            m["ok"] += 1
            resp = raw.get("response") or {}
            usage = resp.get("usage") or {}
            m["in"] += usage.get("prompt_tokens", 0)
            m["out"] += usage.get("completion_tokens", 0)
            m["lat"].append(raw.get("latency_s", 0))
            m["cost"] += call_cost(
                r["model_slug"],
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
        if not r.get("reply"):
            m["empty"] += 1
    return by_model


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interp percentile on a sorted list. pct in 0..1."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = pct * (len(sorted_vals) - 1)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def fmt_overall(by_model: dict) -> str:
    lines = [
        "| Model | n | ok | empty | in_tot | out_tot | lat avg | lat p90 | lat max | cost (USD) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    grand = 0.0
    for alias in ("gemini", "deepseek", "qwen", "qwen-plus"):
        if alias not in by_model:
            continue
        m = by_model[alias]
        lats = sorted(m["lat"])
        lat_avg = sum(lats) / len(lats) if lats else 0.0
        lat_p90 = _percentile(lats, 0.9) if lats else 0.0
        lat_max = lats[-1] if lats else 0.0
        grand += m["cost"]
        lines.append(
            f"| {alias} | {m['n']} | {m['ok']} | {m['empty']} | {m['in']} | "
            f"{m['out']} | {lat_avg:.2f}s | {lat_p90:.2f}s | {lat_max:.2f}s | "
            f"${m['cost']:.4f} |"
        )
    lines.append(f"\n**Total cost**: ${grand:.4f} USD")
    return "\n".join(lines)


def fmt_axis(by_model: dict) -> str:
    lines = [
        "| Model | intent | skill | safety | persona | avg |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for alias in ("gemini", "deepseek", "qwen", "qwen-plus"):
        if alias not in by_model:
            continue
        m = by_model[alias]
        intent = safe_score_axis(m["rows"], "intent")
        skill = safe_score_axis(m["rows"], "skill")
        safety = safe_score_axis(m["rows"], "safety")
        persona = safe_score_axis(m["rows"], "persona")
        avg_parts = [v for v in (intent, skill, safety, persona) if v is not None]
        avg = sum(avg_parts) / len(avg_parts) if avg_parts else None

        def f(v):
            return f"{v:.2f}" if v is not None else "—"

        lines.append(
            f"| {alias} | {f(intent)} | {f(skill)} | {f(safety)} | {f(persona)} | {f(avg)} |"
        )
    return "\n".join(lines)


def fmt_per_bucket_skill(by_model: dict) -> str:
    buckets = ["chat", "action-in", "action-out", "alert", "multi-turn"]
    aliases = [a for a in ("gemini", "deepseek", "qwen", "qwen-plus") if a in by_model]

    header = "| Bucket | " + " | ".join(aliases) + " |"
    sep = "|---" + "|---:" * len(aliases) + "|"
    lines = [header, sep]
    for b in buckets:
        cells = []
        for a in aliases:
            rows = by_model[a]["by_bucket"].get(b, [])
            if not rows:
                cells.append("—")
                continue
            scores = [r["scores"]["skill"] for r in rows if r.get("scores") and "skill" in r["scores"]]
            if not scores:
                cells.append("—")
            else:
                cells.append(f"{sum(scores)/len(scores):.2f} (n={len(scores)})")
        lines.append(f"| {b} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def fmt_anomalies(results: list[dict]) -> str:
    """Items where ALL models scored skill <= 2."""
    by_item: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_item[r["item_id"]].append(r)

    bad = []
    for iid, rows in by_item.items():
        scores = [r["scores"]["skill"] for r in rows if r.get("scores") and "skill" in r["scores"]]
        if scores and max(scores) <= 2:
            sample = rows[0]
            bad.append((iid, sample["bucket"], sample["turns"], sample["expected_skills"]))

    if not bad:
        return "（無：所有 prompt 至少有一個模型 skill ≥ 3）"
    lines = ["| item | bucket | turns | expected |", "|---|---|---|---|"]
    for iid, bucket, turns, exp in bad:
        lines.append(f"| {iid} | {bucket} | {turns} | {exp} |")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Summarize eval results")
    p.add_argument("results_file", type=Path)
    p.add_argument("--md", action="store_true", help="Output markdown only (for piping)")
    args = p.parse_args()

    if not args.results_file.exists():
        print(f"ERROR: {args.results_file} not found", file=sys.stderr)
        return 2
    data = json.loads(args.results_file.read_text(encoding="utf-8"))
    by_model = summarize(data["results"])

    out = []
    out.append(f"### 整體執行成績 / 成本\n\n{fmt_overall(by_model)}\n")
    out.append(f"### 4 軸平均（人工 score 後）\n\n{fmt_axis(by_model)}\n")
    out.append(f"### Per-bucket skill 軸\n\n{fmt_per_bucket_skill(by_model)}\n")
    out.append(f"### 三模型都打掛的 prompt（skill ≤ 2）\n\n{fmt_anomalies(data['results'])}\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
