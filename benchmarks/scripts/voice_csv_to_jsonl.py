#!/usr/bin/env python3
"""將 speech_test CSV 離線轉成 baseline_result JSONL。"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def _positive_float_or_none(value: object) -> float | None:
    """只接受可轉成 float 且大於 0 的延遲值。"""
    try:
        latency_ms = float(value)
    except (TypeError, ValueError):
        return None
    return latency_ms if latency_ms > 0 else None


def csv_row_to_record(
    row: dict,
    stop_intents: set[str],
    run_id: str,
    git_commit: str | None,
) -> dict | None:
    """把單列 speech_test CSV 轉成 baseline result record。"""
    expected_intent = row.get("expected_intent")
    if row.get("status") == "orphan" or not expected_intent:
        return None

    capability_id = "voice.stop" if expected_intent in stop_intents else "voice.command"
    record = {
        "capability_id": capability_id,
        "scenario_id": f'voice_{row.get("round_id", "")}',
        "scenario_kind": "positive",
        "expected_label": expected_intent,
        "predicted_label": row.get("intent", ""),
        "pass_fail": "pass" if row.get("match") == "match" else "fail",
        "false_trigger": False,
        "latency_ms": _positive_float_or_none(row.get("e2e_latency_ms")),
    }

    # 用 setdefault 補 metadata，保留未來呼叫端預先放進 record 的可能性。
    record.setdefault("run_id", run_id)
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    record.setdefault("git_commit", git_commit)
    return record


def convert(
    csv_path: str,
    out_path: str,
    stop_intents: set[str],
    run_id: str,
    git_commit: str | None,
) -> int:
    """讀取 CSV，過濾非資料列後 append 成 JSONL，回傳寫入筆數。"""
    out = Path(out_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as csv_file, open(
        out,
        "a",
        encoding="utf-8",
    ) as out_file:
        for row in csv.DictReader(csv_file):
            record = csv_row_to_record(row, stop_intents, run_id, git_commit)
            if record is None:
                continue
            out_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def _git_commit() -> str | None:
    """從目前 repo 讀 HEAD commit；離線或非 git 目錄時回 None。"""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert speech_test CSV to baseline JSONL.")
    parser.add_argument("--csv", required=True, help="speech_test_observer CSV path")
    parser.add_argument(
        "--out",
        default="artifacts/baseline/baseline_result.jsonl",
        help="output JSONL path",
    )
    parser.add_argument(
        "--stop-intent",
        action="append",
        help="intent label treated as voice.stop; may be repeated",
    )
    parser.add_argument("--run-id", default="voice-baseline", help="baseline run id")
    args = parser.parse_args(argv)

    stop_intents = set(args.stop_intent or ["stop"])
    count = convert(args.csv, args.out, stop_intents, args.run_id, _git_commit())
    print(f"wrote {count} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
