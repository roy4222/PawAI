#!/usr/bin/env python3
"""Offline Lane 4 W5 pose three-way harness.

Primary path is dependency-light: feed pre-extracted COCO17 keypoints JSONL to
the existing ``classify_pose`` and ``to_two_class`` functions, then compare the
same classifier output across three backend labels:

    mediapipe, yolo26n_pose, 478_sc

Video extraction backends are intentionally lazy. MediaPipe, YOLO ONNX, and
478_SC model code should live in throwaway benchmark environments, not runtime.
If the 478_SC model path is absent, the route prints a download/prep hint and
is skipped without killing the harness.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from vision_perception.vision_perception.pose_classifier import classify_pose, to_two_class

DEFAULT_BACKENDS = ("mediapipe", "yolo26n_pose", "478_sc")


@dataclass(frozen=True)
class KeypointFrame:
    frame: int
    timestamp: float | None
    keypoints: np.ndarray
    scores: np.ndarray
    bbox_ratio: float | None = None


@dataclass(frozen=True)
class PoseBackendResult:
    backend: str
    pose_name: str | None
    confidence: float
    two_class: str | None
    skipped: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class FramePoseComparison:
    frame: int
    timestamp: float | None
    results: dict[str, PoseBackendResult]


def classify_keypoint_pose(
    keypoints: np.ndarray,
    scores: np.ndarray,
    min_score: float,
    bbox_ratio: float | None = None,
    backend: str = "keypoints",
) -> PoseBackendResult:
    """Feed COCO17 keypoints into the existing pose classifier."""
    keypoints = np.asarray(keypoints, dtype=np.float32)
    scores = np.asarray(scores, dtype=np.float32)
    pose_name, confidence = classify_pose(
        keypoints,
        scores,
        bbox_ratio=bbox_ratio,
        min_score=min_score,
    )
    return PoseBackendResult(
        backend=backend,
        pose_name=pose_name,
        confidence=round(float(confidence), 4),
        two_class=to_two_class(pose_name),
    )


def compare_keypoint_backends(
    frames: Iterable[KeypointFrame],
    min_score: float,
    backends: Iterable[str] = DEFAULT_BACKENDS,
) -> list[FramePoseComparison]:
    comparisons: list[FramePoseComparison] = []
    backend_names = tuple(backends)
    for frame in frames:
        results = {
            backend: classify_keypoint_pose(
                frame.keypoints,
                frame.scores,
                min_score=min_score,
                bbox_ratio=frame.bbox_ratio,
                backend=backend,
            )
            for backend in backend_names
        }
        comparisons.append(
            FramePoseComparison(frame=frame.frame, timestamp=frame.timestamp, results=results)
        )
    return comparisons


def _array_from_record(record: dict[str, Any], key: str, shape: tuple[int, ...]) -> np.ndarray:
    array = np.asarray(record[key], dtype=np.float32)
    if array.shape != shape:
        raise ValueError(f"{key} must have shape {shape}, got {array.shape}")
    return array


def parse_keypoint_record(record: dict[str, Any]) -> KeypointFrame:
    timestamp = record.get("timestamp")
    bbox_ratio = record.get("bbox_ratio")
    return KeypointFrame(
        frame=int(record["frame"]),
        timestamp=None if timestamp is None else float(timestamp),
        keypoints=_array_from_record(record, "keypoints", (17, 2)),
        scores=_array_from_record(record, "scores", (17,)),
        bbox_ratio=None if bbox_ratio is None else float(bbox_ratio),
    )


def parse_keypoints_jsonl_lines(lines: Iterable[str]) -> list[KeypointFrame]:
    frames: list[KeypointFrame] = []
    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            frames.append(parse_keypoint_record(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"invalid keypoints JSONL line {line_number}: {exc}") from exc
    return frames


def load_keypoints_jsonl(path: Path) -> list[KeypointFrame]:
    with path.open("r", encoding="utf-8") as f:
        return parse_keypoints_jsonl_lines(f)


def parse_min_score_sweep(raw: str) -> list[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("min-score-sweep must contain at least one value")
    return values


def comparison_rows(
    comparisons: Iterable[FramePoseComparison],
    min_score: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for comparison in comparisons:
        for backend, result in comparison.results.items():
            rows.append({
                "frame": comparison.frame,
                "timestamp": comparison.timestamp,
                "min_score": min_score,
                "backend": backend,
                "pose_name": result.pose_name,
                "confidence": result.confidence,
                "two_class": result.two_class,
                "skipped": result.skipped,
                "reason": result.reason,
            })
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        print(
            "frame={frame} backend={backend} min_score={min_score:.2f} "
            "pose={pose_name} two_class={two_class} conf={confidence}".format(**row)
        )


def _try_import(name: str):
    try:
        return __import__(name)
    except ImportError:
        return None


def available_video_backends(
    yolo_pose_model: Path | None,
    model_478_sc: Path | None,
) -> list[str]:
    """Return video backends whose heavy dependencies and model files exist."""
    available: list[str] = []
    if _try_import("mediapipe") is not None:
        available.append("mediapipe")
    else:
        print("SKIP mediapipe: install mediapipe in a benchmark venv", file=sys.stderr)

    if yolo_pose_model is not None and yolo_pose_model.exists():
        if _try_import("onnxruntime") is not None:
            available.append("yolo26n_pose")
        else:
            print("SKIP yolo26n_pose: onnxruntime unavailable", file=sys.stderr)
    else:
        print("SKIP yolo26n_pose: pass --yolo-pose-model pointing at ONNX", file=sys.stderr)

    if model_478_sc is not None and model_478_sc.exists():
        available.append("478_sc")
    else:
        print(
            "SKIP 478_sc: model missing; prepare PINTO 478_SC under .tmp/models/",
            file=sys.stderr,
        )
    return available


def run_keypoints_jsonl(
    path: Path,
    out_dir: Path,
    min_scores: Iterable[float],
) -> int:
    frames = load_keypoints_jsonl(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    for min_score in min_scores:
        comparisons = compare_keypoint_backends(frames, min_score=min_score)
        rows = comparison_rows(comparisons, min_score=min_score)
        total_rows += len(rows)
        output = out_dir / f"pose_3way_min_score_{min_score:.2f}.csv"
        write_csv(rows, output)
        print_rows(rows)
        print(f"wrote_csv: {output}")
    print(f"total_rows: {total_rows}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--keypoints-jsonl", help="pre-extracted COCO17 keypoints JSONL")
    source.add_argument("--video", help="video path for heavy backend extraction")
    parser.add_argument("--out-dir", default="benchmarks/results/raw/pose_3way")
    parser.add_argument("--min-score-sweep", type=parse_min_score_sweep, default=[0.2])
    parser.add_argument("--yolo-pose-model", help="YOLO26n-pose ONNX path")
    parser.add_argument("--model-478-sc", help="478_SC model path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir).expanduser()
    if args.keypoints_jsonl:
        return run_keypoints_jsonl(
            Path(args.keypoints_jsonl).expanduser(),
            out_dir,
            args.min_score_sweep,
        )

    available = available_video_backends(
        Path(args.yolo_pose_model).expanduser() if args.yolo_pose_model else None,
        Path(args.model_478_sc).expanduser() if args.model_478_sc else None,
    )
    print(f"available_video_backends: {available}")
    print("video extraction is intentionally not used by base-env unit tests", file=sys.stderr)
    return 0 if available else 2


if __name__ == "__main__":
    raise SystemExit(main())
