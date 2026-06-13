#!/usr/bin/env python3
"""Build offline annotated evidence clips with supervision.

Lane 4 W4 is offline-only. Install supervision in an isolated throwaway venv,
never in Jetson runtime:

    uv venv .tmp/sv_venv
    .tmp/sv_venv/bin/uv pip install supervision

Input object JSONL schema accepts one detection per line:

    {"frame": 10, "timestamp": 1.25, "bbox": [x1, y1, x2, y2],
     "class": "cup", "conf": 0.42, "decision_id": "abc"}

Output JSONL writes the filtered detection plus:

    "custom_data": {"decision_id": "...", "join_field": "decision_id", ...}

Lane 2 should join annotated clips back to decisions through
``custom_data.decision_id``. The script compares current conf 0.35 behavior
with lower-conf temporal evidence such as conf 0.30 plus ``track_buffer=3``.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class DetectionEvent:
    frame: int
    timestamp: float | None
    bbox: BBox
    class_name: str
    confidence: float
    decision_id: str | None
    class_id: int = -1


def _parse_bbox(raw: Any) -> BBox:
    if isinstance(raw, dict):
        values = [raw.get(key) for key in ("x1", "y1", "x2", "y2")]
    else:
        values = list(raw or [])
    if len(values) != 4:
        raise ValueError("bbox must contain x1,y1,x2,y2")
    x1, y1, x2, y2 = (float(value) for value in values)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("bbox must have x2>x1 and y2>y1")
    return x1, y1, x2, y2


def parse_detection_record(record: dict[str, Any]) -> DetectionEvent:
    class_name = record.get("class", record.get("class_name", "unknown"))
    confidence = record.get("conf", record.get("confidence", 0.0))
    timestamp = record.get("timestamp")
    return DetectionEvent(
        frame=int(record["frame"]),
        timestamp=None if timestamp is None else float(timestamp),
        bbox=_parse_bbox(record.get("bbox")),
        class_name=str(class_name),
        confidence=float(confidence),
        decision_id=record.get("decision_id"),
        class_id=int(record.get("class_id", -1)),
    )


def parse_detection_jsonl_lines(lines: Iterable[str]) -> list[DetectionEvent]:
    events: list[DetectionEvent] = []
    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(parse_detection_record(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"invalid detection JSONL line {line_number}: {exc}") from exc
    return events


def load_detection_jsonl(path: Path) -> list[DetectionEvent]:
    with path.open("r", encoding="utf-8") as f:
        return parse_detection_jsonl_lines(f)


def _track_key(event: DetectionEvent) -> str:
    if event.decision_id:
        return event.decision_id
    rounded = ",".join(str(int(round(value))) for value in event.bbox)
    return f"{event.class_name}:{rounded}"


def filter_detection_events(
    events: Iterable[DetectionEvent],
    conf: float = 0.35,
    track_buffer: int = 1,
) -> list[DetectionEvent]:
    """Filter by confidence, optionally requiring N consecutive frame votes."""
    min_votes = max(1, int(track_buffer))
    if min_votes == 1:
        return [event for event in events if event.confidence >= conf]

    kept: list[DetectionEvent] = []
    streaks: dict[str, tuple[int, int]] = {}
    for event in sorted(events, key=lambda item: item.frame):
        key = _track_key(event)
        if event.confidence < conf:
            streaks.pop(key, None)
            continue
        previous_frame, previous_count = streaks.get(key, (-10**9, 0))
        count = previous_count + 1 if event.frame == previous_frame + 1 else 1
        streaks[key] = (event.frame, count)
        if count >= min_votes:
            kept.append(event)
    return kept


def build_custom_data(event: DetectionEvent) -> dict[str, Any]:
    """Return supervision custom_data payload used for Lane 2 joins."""
    return {
        "decision_id": event.decision_id,
        "join_field": "decision_id",
        "frame": event.frame,
        "timestamp": event.timestamp,
        "class_name": event.class_name,
        "confidence": event.confidence,
    }


def event_to_output_record(event: DetectionEvent) -> dict[str, Any]:
    payload = asdict(event)
    payload["bbox"] = list(event.bbox)
    payload["custom_data"] = build_custom_data(event)
    return payload


def write_detection_jsonl(events: Iterable[DetectionEvent], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event_to_output_record(event), ensure_ascii=False) + "\n")


def lazy_import_supervision():
    try:
        import supervision as sv
    except ImportError as exc:  # pragma: no cover - depends on optional venv.
        raise RuntimeError(
            "supervision is required for MP4 annotation; install it in .tmp/sv_venv"
        ) from exc
    return sv


def _class_id_map(events: Iterable[DetectionEvent]) -> dict[str, int]:
    names = sorted({event.class_name for event in events})
    return {name: index for index, name in enumerate(names)}


def _detections_for_frame(sv, events: list[DetectionEvent], class_ids: dict[str, int]):
    if not events:
        return sv.Detections.empty()
    xyxy = np.array([event.bbox for event in events], dtype=np.float32)
    confidence = np.array([event.confidence for event in events], dtype=np.float32)
    class_id = np.array([class_ids[event.class_name] for event in events], dtype=int)
    data = {
        "decision_id": np.array([event.decision_id for event in events], dtype=object),
        "custom_data": np.array([build_custom_data(event) for event in events], dtype=object),
    }
    try:
        return sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id, data=data)
    except TypeError:
        detections = sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)
        detections.data = data
        return detections


def annotate_video(
    video_path: Path,
    events: list[DetectionEvent],
    out_dir: Path,
    track_buffer: int,
) -> Path:
    """Annotate MP4 with supervision when optional dependency is installed."""
    sv = lazy_import_supervision()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{video_path.stem}.supervision_annotated.mp4"
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"video not readable: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 10.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    by_frame: dict[int, list[DetectionEvent]] = defaultdict(list)
    for event in events:
        by_frame[event.frame].append(event)

    class_ids = _class_id_map(events)
    tracker = sv.ByteTrack(track_buffer=track_buffer)
    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frame_events = by_frame.get(frame_index, [])
        detections = _detections_for_frame(sv, frame_events, class_ids)
        detections = tracker.update_with_detections(detections)
        labels = [
            f"{event.class_name} {event.confidence:.2f} {event.decision_id or ''}"
            for event in frame_events
        ]
        annotated = box_annotator.annotate(scene=frame.copy(), detections=detections)
        annotated = label_annotator.annotate(
            scene=annotated,
            detections=detections,
            labels=labels,
        )
        writer.write(annotated)
        frame_index += 1

    capture.release()
    writer.release()
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="input MP4 path")
    parser.add_argument("jsonl", help="object detection JSONL path")
    parser.add_argument("--out-dir", default="benchmarks/results/raw/supervision_evidence")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--track-buffer", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    video_path = Path(args.video).expanduser()
    jsonl_path = Path(args.jsonl).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    events = load_detection_jsonl(jsonl_path)
    filtered = filter_detection_events(events, conf=args.conf, track_buffer=args.track_buffer)

    output_jsonl = out_dir / "supervision_evidence.filtered.jsonl"
    write_detection_jsonl(filtered, output_jsonl)
    try:
        output_video = annotate_video(video_path, filtered, out_dir, args.track_buffer)
    except Exception as exc:
        print(f"ERROR: annotation failed after JSONL write: {exc}", file=sys.stderr)
        print(f"wrote_jsonl: {output_jsonl}", file=sys.stderr)
        return 2

    print(f"kept_detections: {len(filtered)}")
    print(f"wrote_jsonl: {output_jsonl}")
    print(f"wrote_video: {output_video}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
