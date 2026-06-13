#!/usr/bin/env python3
"""Offline Lane 4 W7 gesture false-trigger sweep.

Use non-gesture demo segments to quantify false triggers for:

    min_conf {0.5, 0.7, 0.8} x min_votes {1, 3, 5}

The default current runtime point is 0.7 x 3. The dependency-light path reads
pre-extracted per-frame JSONL events:

    {"frame": 1, "timestamp": 0.1, "gesture_label": "ok", "score": 0.73}

The video path intentionally lazy-imports MediaPipe recognizer dependencies and
prints a clear skip/error in base envs. It does not install models or touch
runtime code.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from vision_perception.vision_perception import voting

DEFAULT_MIN_CONFS = (0.5, 0.7, 0.8)
DEFAULT_MIN_VOTES = (1, 3, 5)
CURRENT_MIN_CONF = 0.7
CURRENT_MIN_VOTES = 3


@dataclass(frozen=True)
class GestureEvent:
    label: str | None
    score: float
    frame: int | None = None
    timestamp: float | None = None


def count_false_triggers(
    events: Iterable[GestureEvent],
    min_conf: float,
    min_votes: int,
    window: int,
) -> int:
    """Count windows where majority_vote emits any gesture in a non-gesture segment."""
    if window <= 0:
        raise ValueError("window must be positive")
    buffer: list[str | None] = []
    false_triggers = 0
    for event in events:
        candidate = event.label if event.label and event.score >= min_conf else None
        buffer.append(candidate)
        buffer = buffer[-window:]
        winner = voting.majority_vote(buffer, min_votes=min_votes)
        if winner is not None:
            false_triggers += 1
    return false_triggers


def sweep_false_triggers(
    events: Iterable[GestureEvent],
    window: int,
    min_confs: Iterable[float] = DEFAULT_MIN_CONFS,
    min_votes_values: Iterable[int] = DEFAULT_MIN_VOTES,
) -> list[dict[str, Any]]:
    event_list = list(events)
    rows: list[dict[str, Any]] = []
    for min_conf in min_confs:
        for min_votes in min_votes_values:
            rows.append({
                "min_conf": min_conf,
                "min_votes": min_votes,
                "window": window,
                "false_triggers": count_false_triggers(
                    event_list,
                    min_conf=min_conf,
                    min_votes=min_votes,
                    window=window,
                ),
                "is_current_runtime": (
                    min_conf == CURRENT_MIN_CONF and min_votes == CURRENT_MIN_VOTES
                ),
            })
    return rows


def parse_gesture_record(record: dict[str, Any]) -> GestureEvent:
    label = record.get("gesture_label", record.get("gesture", record.get("label")))
    timestamp = record.get("timestamp")
    frame = record.get("frame")
    return GestureEvent(
        label=None if label in ("", "None", None) else str(label),
        score=float(record.get("score", record.get("confidence", 0.0))),
        frame=None if frame is None else int(frame),
        timestamp=None if timestamp is None else float(timestamp),
    )


def parse_events_jsonl_lines(lines: Iterable[str]) -> list[GestureEvent]:
    events: list[GestureEvent] = []
    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(parse_gesture_record(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"invalid gesture JSONL line {line_number}: {exc}") from exc
    return events


def load_events_jsonl(path: Path) -> list[GestureEvent]:
    with path.open("r", encoding="utf-8") as f:
        return parse_events_jsonl_lines(f)


def extract_events_from_video(video_path: Path) -> list[GestureEvent]:
    """Lazy recognizer placeholder for real offline video extraction."""
    try:
        import mediapipe  # noqa: F401
    except ImportError as exc:  # pragma: no cover - optional dependency.
        raise RuntimeError(
            "MediaPipe is required for --video extraction; use --events-jsonl in base env"
        ) from exc
    raise RuntimeError(
        f"video recognizer extraction is not wired in this pure spike: {video_path}"
    )


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_matrix(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        marker = " current" if row["is_current_runtime"] else ""
        print(
            "min_conf={min_conf:.1f} min_votes={min_votes} window={window} "
            "false_triggers={false_triggers}{marker}".format(marker=marker, **row)
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--events-jsonl", help="pre-extracted frame gesture+score JSONL")
    source.add_argument("--video", help="non-gesture segment video path")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument(
        "--out-csv",
        default="benchmarks/results/raw/gesture_false_trigger_sweep.csv",
        help="CSV output path under a gitignored results directory",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.events_jsonl:
            events = load_events_jsonl(Path(args.events_jsonl).expanduser())
        else:
            events = extract_events_from_video(Path(args.video).expanduser())
    except Exception as exc:
        print(f"ERROR: gesture event extraction failed: {exc}", file=sys.stderr)
        return 2

    rows = sweep_false_triggers(events, window=args.window)
    print_matrix(rows)
    write_csv(rows, Path(args.out_csv).expanduser())
    print(f"wrote_csv: {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
