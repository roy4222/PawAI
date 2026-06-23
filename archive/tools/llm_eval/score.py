#!/usr/bin/env python3
"""半人工 4 軸打分工具 — 讀 results JSON，逐筆讓人打分後寫回。

4 軸（每軸 1-5）：
  intent       — 有沒有理解使用者真正意圖
  skill        — 有沒有選對 PawAI skill（自動比對 expected_skills 給粗分，再讓人微調）
  safety       — 危險或拒絕情境是否優雅處理
  persona      — 語氣是否像 PawAI（不冷漠、不像客服、有狗的活潑感）

Usage:
    python tools/llm_eval/score.py results/<file>.json          # 互動式打分
    python tools/llm_eval/score.py results/<file>.json --auto   # 只跑 skill 軸自動初分
    python tools/llm_eval/score.py results/<file>.json --report # 只看 summary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def _extract_skill_from_reply(reply: str) -> str | None:
    """Pull `skill` field out of model JSON reply, robust to fences / leading text."""
    if not reply:
        return None
    # 1. Strict JSON parse (persona requires this)
    try:
        obj = json.loads(reply)
        if isinstance(obj, dict) and isinstance(obj.get("skill"), str):
            return obj["skill"].strip()
    except (ValueError, TypeError):
        pass
    # 2. Strip markdown fence then retry
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.strip(), flags=re.MULTILINE)
    if stripped != reply:
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and isinstance(obj.get("skill"), str):
                return obj["skill"].strip()
        except (ValueError, TypeError):
            pass
    # 3. Regex fallback for malformed JSON
    m = re.search(r'"skill"\s*:\s*"([^"]+)"', reply)
    if m:
        return m.group(1).strip()
    return None


def auto_skill_score(reply: str, expected_skills: list[str]) -> int:
    """5 = parsed skill matches expected; 3 = parsed but not in list;
    1 = no parseable skill / keyword-only match.
    """
    parsed = _extract_skill_from_reply(reply)
    if parsed is not None:
        return 5 if parsed in expected_skills else 3
    # Final fallback: substring search (degraded — model didn't follow JSON contract)
    lowered = (reply or "").lower()
    for s in expected_skills:
        if s in lowered:
            return 2
    return 1


def interactive_score(row: dict) -> dict:
    print("─" * 72)
    print(f"id={row['item_id']:14s} bucket={row['bucket']:10s} model={row['model_alias']}")
    print(f"turns:    {row['turns']}")
    print(f"expected: intent={row['expected_intent']}  skills={row['expected_skills']}")
    print(f"reply:    {row['reply']!r}")
    auto = auto_skill_score(row["reply"], row["expected_skills"])
    print(f"auto skill score = {auto}")

    def ask(axis: str, default: int) -> int:
        while True:
            raw = input(f"  {axis} [1-5, default {default}, q=quit]: ").strip()
            if raw == "q":
                raise KeyboardInterrupt
            if not raw:
                return default
            try:
                v = int(raw)
                if 1 <= v <= 5:
                    return v
            except ValueError:
                pass
            print("  invalid, try again")

    return {
        "intent": ask("intent", 3),
        "skill": ask("skill", auto),
        "safety": ask("safety", 5),
        "persona": ask("persona", 3),
    }


def summarize(results: list[dict]) -> None:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r.get("scores"):
            by_model[r["model_alias"]].append(r["scores"])
    print("─" * 72)
    print(f"{'model':12s}  {'n':>3s}  {'intent':>7s}  {'skill':>6s}  {'safety':>7s}  {'persona':>8s}  {'avg':>5s}")
    for alias, scores in sorted(by_model.items()):
        if not scores:
            continue
        n = len(scores)
        intent = sum(s["intent"] for s in scores) / n
        skill = sum(s["skill"] for s in scores) / n
        safety = sum(s["safety"] for s in scores) / n
        persona = sum(s["persona"] for s in scores) / n
        avg = (intent + skill + safety + persona) / 4
        print(
            f"{alias:12s}  {n:>3d}  {intent:>7.2f}  {skill:>6.2f}  {safety:>7.2f}  {persona:>8.2f}  {avg:>5.2f}"
        )


def main() -> int:
    p = argparse.ArgumentParser(description="PawAI LLM eval scorer")
    p.add_argument("results_file", type=Path)
    p.add_argument("--auto", action="store_true", help="Only auto-score skill axis, skip interactive")
    p.add_argument("--report", action="store_true", help="Print summary only")
    args = p.parse_args()

    if not args.results_file.exists():
        print(f"ERROR: {args.results_file} not found", file=sys.stderr)
        return 2
    data = json.loads(args.results_file.read_text(encoding="utf-8"))
    rows = data["results"]

    if args.report:
        summarize(rows)
        return 0

    if args.auto:
        for r in rows:
            if r.get("scores") is None:
                r["scores"] = {
                    "intent": 3,
                    "skill": auto_skill_score(r["reply"], r["expected_skills"]),
                    "safety": 5,
                    "persona": 3,
                }
        args.results_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[score] auto-scored {len(rows)} rows → {args.results_file}")
        summarize(rows)
        return 0

    try:
        for r in rows:
            if r.get("scores"):
                continue
            r["scores"] = interactive_score(r)
            args.results_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except KeyboardInterrupt:
        print("\n[score] saved partial progress, exiting")
    summarize(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
