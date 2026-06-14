#!/usr/bin/env python3
"""Offline object-detection confusion-matrix harness for Lane 4 (n@640 baseline).

This is a **WSL / benchmark-venv only** spike. It NEVER runs on the Jetson
runtime path. It replays recorded clips or image folders through the SAME
runtime model (``yolo26n.onnx`` @ input_size 640, conf 0.35) using ONNX Runtime
CPU, and reports, per ``(object, distance)`` cell:

  * detection count for the labelled object (how many frames hit it)
  * confidence min / avg / max for that object
  * a **class confusion matrix** — when the ground-truth object is X, which
    COCO class label did the model actually emit (cup mislabelled phone/bottle…)
  * inference FPS (offline ORT CPU throughput, not a Jetson number)

Input layout (Roy records cup/bottle/phone/chair @ 0.7/1.0/1.5m tonight). Each
leaf is an image folder OR a single video file; the ground-truth object and
distance are encoded in the path::

    clips/cup/0.7m/*.jpg          # image folder
    clips/cup/1.0m.mp4            # single clip
    clips/bottle__1.5m/*.png      # flat "object__distanceM" naming

Use ``--dry-run`` to list what would be processed without loading a model.

Dependency policy: stdlib + numpy always; ``cv2`` (opencv-headless) and
``onnxruntime`` are imported lazily only when actually decoding frames. If they
are missing in the dev venv, the harness gates gracefully and prints the
install line below. NONE of these touch the Jetson runtime.

    uv venv .tmp/obj_bench_venv
    .tmp/obj_bench_venv/bin/uv pip install onnxruntime opencv-python-headless numpy
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np

# COCO 80 contiguous IDs (0-79), underscored names. Mirrored (NOT imported)
# from object_perception/object_perception/coco_classes.py to keep this harness
# free of any ROS-package import. Keep in sync if the runtime table changes.
COCO_CLASSES: dict[int, str] = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic_light",
    10: "fire_hydrant", 11: "stop_sign", 12: "parking_meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports_ball", 33: "kite",
    34: "baseball_bat", 35: "baseball_glove", 36: "skateboard",
    37: "surfboard", 38: "tennis_racket", 39: "bottle", 40: "wine_glass",
    41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl", 46: "banana",
    47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli", 51: "carrot",
    52: "hot_dog", 53: "pizza", 54: "donut", 55: "cake", 56: "chair",
    57: "couch", 58: "potted_plant", 59: "bed", 60: "dining_table",
    61: "toilet", 62: "tv", 63: "laptop", 64: "mouse", 65: "remote",
    66: "keyboard", 67: "cell_phone", 68: "microwave", 69: "oven",
    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock",
    75: "vase", 76: "scissors", 77: "teddy_bear", 78: "hair_drier",
    79: "toothbrush",
}

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
VIDEO_SUFFIXES = (".mp4", ".mov", ".avi", ".mkv")

# Default gate thresholds inherited from the lane4 / synthesis / 5-20 protocol.
DEFAULT_CONF = 0.35
DEFAULT_IMGSZ = 640
RECALL_PASS = 0.80          # cup@1.5m recall >= 80% (synthesis T2 gate)
RECALL_DEGRADED = 0.60      # protocol §5.1 hard floor for P0 objects


@dataclass(frozen=True)
class Detection:
    """One decoded detection in original-image pixel coordinates."""
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ClipSpec:
    """A labelled measurement unit: ground-truth object + distance + source."""
    object_name: str
    distance_m: float
    path: Path
    is_video: bool

    @property
    def cell_key(self) -> tuple[str, float]:
        return (self.object_name, self.distance_m)


@dataclass
class CellMetrics:
    """Aggregated per-(object, distance) detection metrics."""
    object_name: str
    distance_m: float
    frames: int = 0
    detected_frames: int = 0          # frames where the GT object was detected
    confidences: list[float] = field(default_factory=list)

    @property
    def detection_count(self) -> int:
        return self.detected_frames

    @property
    def recall(self) -> float:
        return (self.detected_frames / self.frames) if self.frames else 0.0

    @property
    def conf_min(self) -> float | None:
        return min(self.confidences) if self.confidences else None

    @property
    def conf_max(self) -> float | None:
        return max(self.confidences) if self.confidences else None

    @property
    def conf_avg(self) -> float | None:
        if not self.confidences:
            return None
        return sum(self.confidences) / len(self.confidences)


# --------------------------------------------------------------------------- #
# Pure logic: detection decode (numpy only, no cv2/ort) — unit-tested.         #
# --------------------------------------------------------------------------- #
def rescale_bbox(
    x1: float, y1: float, x2: float, y2: float,
    scale: float, pad_left: int, pad_top: int, orig_w: int, orig_h: int,
) -> tuple[float, float, float, float]:
    """Map letterboxed-canvas coords back to original image pixel coords.

    Mirrors object_perception_node.rescale_bbox so offline numbers match the
    runtime decode path.
    """
    rx1 = (x1 - pad_left) / scale
    ry1 = (y1 - pad_top) / scale
    rx2 = (x2 - pad_left) / scale
    ry2 = (y2 - pad_top) / scale
    rx1 = float(min(max(rx1, 0.0), orig_w))
    ry1 = float(min(max(ry1, 0.0), orig_h))
    rx2 = float(min(max(rx2, 0.0), orig_w))
    ry2 = float(min(max(ry2, 0.0), orig_h))
    return rx1, ry1, rx2, ry2


def decode_detections(
    raw: np.ndarray,
    *,
    conf: float,
    scale: float = 1.0,
    pad_left: int = 0,
    pad_top: int = 0,
    orig_w: int = DEFAULT_IMGSZ,
    orig_h: int = DEFAULT_IMGSZ,
    allowed: set[int] | None = None,
) -> list[Detection]:
    """Decode a YOLO26 ``(N, 6)`` tensor (x1,y1,x2,y2,conf,class_id).

    Replicates the runtime postprocess: confidence gate, class whitelist,
    COCO-id validity, degenerate-bbox drop, rescale to original coords.
    """
    arr = np.asarray(raw)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2 or arr.shape[-1] != 6:
        raise ValueError(f"expected (N,6) detection tensor, got shape {arr.shape}")

    out: list[Detection] = []
    for det in arr:
        confidence = float(det[4])
        if confidence < conf:
            continue
        class_id = int(det[5])
        if allowed is not None and class_id not in allowed:
            continue
        if class_id not in COCO_CLASSES:
            continue
        bx1, by1, bx2, by2 = rescale_bbox(
            float(det[0]), float(det[1]), float(det[2]), float(det[3]),
            scale, pad_left, pad_top, orig_w, orig_h,
        )
        if bx2 <= bx1 or by2 <= by1:
            continue
        out.append(Detection(
            class_id=class_id,
            class_name=COCO_CLASSES[class_id],
            confidence=round(confidence, 3),
            bbox=(bx1, by1, bx2, by2),
        ))
    return out


# --------------------------------------------------------------------------- #
# Pure logic: clip discovery from path conventions — unit-tested.             #
# --------------------------------------------------------------------------- #
_DIST_RE = re.compile(r"(\d+(?:\.\d+)?)\s*m$", re.IGNORECASE)
_FLAT_RE = re.compile(r"^(?P<obj>.+?)__(?P<dist>\d+(?:\.\d+)?)\s*m$", re.IGNORECASE)


def parse_distance_token(token: str) -> float | None:
    """Parse a distance token like '0.7m' / '1.5 M' → 0.7 / 1.5; else None."""
    match = _DIST_RE.search(token.strip())
    return float(match.group(1)) if match else None


def clip_spec_from_path(path: Path, root: Path) -> ClipSpec | None:
    """Infer (object, distance) from a leaf path relative to ``root``.

    Supported layouts (object names are normalized to underscores):
      * <root>/<object>/<distance>m/             (image folder)
      * <root>/<object>/<distance>m.<ext>        (single video clip)
      * <root>/<object>__<distance>m/ or .<ext>  (flat naming)
    """
    rel = path.relative_to(root)
    parts = rel.parts
    is_video = path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES

    # Flat "object__distanceM" on the leaf (folder or file stem).
    leaf = path.stem if path.is_file() else path.name
    flat = _FLAT_RE.match(leaf)
    if flat:
        return ClipSpec(
            object_name=_normalize_object(flat.group("obj")),
            distance_m=float(flat.group("dist")),
            path=path,
            is_video=is_video,
        )

    # Nested "<object>/<distance>m" — distance is the leaf, object its parent.
    dist_token = path.stem if path.is_file() else path.name
    distance = parse_distance_token(dist_token)
    if distance is not None and len(parts) >= 2:
        return ClipSpec(
            object_name=_normalize_object(parts[-2]),
            distance_m=distance,
            path=path,
            is_video=is_video,
        )
    return None


def _normalize_object(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def discover_clips(root: Path) -> list[ClipSpec]:
    """Walk ``root`` and return all labelled clip specs (sorted, deduped).

    A directory containing image files is one clip; a standalone video file is
    one clip. Image folders take precedence over their individual images.
    """
    if not root.exists():
        raise FileNotFoundError(f"clip root not found: {root}")

    specs: dict[Path, ClipSpec] = {}

    # Image folders: any dir that directly holds >=1 image file.
    for directory in sorted(p for p in root.rglob("*") if p.is_dir()):
        has_image = any(
            child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
            for child in directory.iterdir()
        )
        if not has_image:
            continue
        spec = clip_spec_from_path(directory, root)
        if spec is not None:
            specs[directory] = spec

    # Standalone video files.
    for file in sorted(root.rglob("*")):
        if not (file.is_file() and file.suffix.lower() in VIDEO_SUFFIXES):
            continue
        spec = clip_spec_from_path(file, root)
        if spec is not None:
            specs[file] = spec

    return sorted(specs.values(), key=lambda s: (s.object_name, s.distance_m, str(s.path)))


def frame_paths_for_clip(spec: ClipSpec) -> list[Path]:
    """Return image-file paths for an image-folder clip (empty for videos)."""
    if spec.is_video:
        return []
    return sorted(
        child for child in spec.path.iterdir()
        if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
    )


# --------------------------------------------------------------------------- #
# Pure logic: metric / confusion-matrix aggregation — unit-tested.            #
# --------------------------------------------------------------------------- #
class ConfusionMatrix:
    """Ground-truth object → emitted COCO label counts (frame-level)."""

    def __init__(self) -> None:
        # gt_object -> emitted_label -> frame count
        self._counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._gt_frames: dict[str, int] = defaultdict(int)

    def record_frame(self, gt_object: str, detections: Sequence[Detection]) -> None:
        """Record one frame: count each distinct emitted label once per frame."""
        self._gt_frames[gt_object] += 1
        labels = {det.class_name for det in detections}
        if not labels:
            self._counts[gt_object]["__none__"] += 1
            return
        for label in labels:
            self._counts[gt_object][label] += 1

    def gt_objects(self) -> list[str]:
        return sorted(self._gt_frames)

    def emitted_labels(self) -> list[str]:
        labels: set[str] = set()
        for row in self._counts.values():
            labels.update(row)
        return sorted(labels)

    def frame_count(self, gt_object: str) -> int:
        return self._gt_frames.get(gt_object, 0)

    def count(self, gt_object: str, emitted_label: str) -> int:
        return self._counts.get(gt_object, {}).get(emitted_label, 0)

    def confusions(self, gt_object: str) -> dict[str, int]:
        """Emitted labels for ``gt_object`` excluding self and the no-detect bucket."""
        row = self._counts.get(gt_object, {})
        return {
            label: n for label, n in sorted(row.items())
            if label not in (gt_object, "__none__")
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "gt_objects": self.gt_objects(),
            "emitted_labels": self.emitted_labels(),
            "gt_frames": dict(self._gt_frames),
            "matrix": {gt: dict(row) for gt, row in self._counts.items()},
        }


def evaluate_recall_gate(recall: float) -> str:
    """PASS / DEGRADED / FAIL per protocol §5.1 + synthesis T2 gate."""
    if recall >= RECALL_PASS:
        return "PASS"
    if recall >= RECALL_DEGRADED:
        return "DEGRADED"
    return "FAIL"


# --------------------------------------------------------------------------- #
# I/O: frame reading + ONNX inference (lazy cv2 / ort imports).               #
# --------------------------------------------------------------------------- #
def lazy_import_cv2():
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - depends on optional venv.
        raise RuntimeError(
            "cv2 (opencv-python-headless) required to read frames; "
            "uv pip install opencv-python-headless"
        ) from exc
    return cv2


def lazy_import_ort():
    try:
        import onnxruntime as ort
    except ImportError as exc:  # pragma: no cover - depends on optional venv.
        raise RuntimeError(
            "onnxruntime required for inference; uv pip install onnxruntime"
        ) from exc
    return ort


def letterbox(cv2, image_bgr: np.ndarray, imgsz: int):
    """Square letterbox; returns (canvas, scale, pad_left, pad_top)."""
    height, width = image_bgr.shape[:2]
    scale = min(imgsz / float(width), imgsz / float(height))
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    pad_left = (imgsz - new_w) // 2
    pad_top = (imgsz - new_h) // 2
    canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
    return canvas, scale, pad_left, pad_top


def iter_clip_frames(spec: ClipSpec, *, frame_stride: int = 1) -> Iterator[np.ndarray]:
    """Yield BGR frames from an image folder or video clip."""
    cv2 = lazy_import_cv2()
    if spec.is_video:
        cap = cv2.VideoCapture(str(spec.path))
        if not cap.isOpened():
            raise RuntimeError(f"video not readable: {spec.path}")
        idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if idx % frame_stride == 0:
                    yield frame
                idx += 1
        finally:
            cap.release()
    else:
        for i, image_path in enumerate(frame_paths_for_clip(spec)):
            if i % frame_stride != 0:
                continue
            frame = cv2.imread(str(image_path))
            if frame is None:
                continue
            yield frame


def make_session(model_path: Path):
    """Open ONNX Runtime CPU session (offline harness — no GPU/TRT)."""
    ort = lazy_import_ort()
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    return session


def infer_frame(cv2, session, frame_bgr: np.ndarray, imgsz: int) -> np.ndarray:
    """Run one BGR frame → raw ``(N, 6)`` detection tensor (letterbox coords)."""
    canvas, scale, pad_left, pad_top = letterbox(cv2, frame_bgr, imgsz)
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    blob = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: blob})
    return outputs[0], scale, pad_left, pad_top


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #
@dataclass
class HarnessResult:
    cells: list[CellMetrics]
    confusion: ConfusionMatrix
    total_frames: int
    elapsed_s: float

    @property
    def fps(self) -> float:
        return (self.total_frames / self.elapsed_s) if self.elapsed_s > 0 else 0.0


def run_harness(
    clips: Sequence[ClipSpec],
    model_path: Path,
    *,
    conf: float = DEFAULT_CONF,
    imgsz: int = DEFAULT_IMGSZ,
    allowed: set[int] | None = None,
    frame_stride: int = 1,
) -> HarnessResult:
    """Replay clips through the model and aggregate metrics + confusion matrix."""
    cv2 = lazy_import_cv2()
    session = make_session(model_path)

    cells: dict[tuple[str, float], CellMetrics] = {}
    confusion = ConfusionMatrix()
    total_frames = 0
    start = time.monotonic()

    for spec in clips:
        cell = cells.setdefault(
            spec.cell_key,
            CellMetrics(object_name=spec.object_name, distance_m=spec.distance_m),
        )
        for frame in iter_clip_frames(spec, frame_stride=frame_stride):
            total_frames += 1
            cell.frames += 1
            h, w = frame.shape[:2]
            raw, scale, pad_left, pad_top = infer_frame(cv2, session, frame, imgsz)
            detections = decode_detections(
                raw, conf=conf, scale=scale, pad_left=pad_left, pad_top=pad_top,
                orig_w=w, orig_h=h, allowed=allowed,
            )
            confusion.record_frame(spec.object_name, detections)
            target_confs = [
                d.confidence for d in detections if d.class_name == spec.object_name
            ]
            if target_confs:
                cell.detected_frames += 1
                cell.confidences.append(max(target_confs))

    elapsed = time.monotonic() - start
    ordered = sorted(cells.values(), key=lambda c: (c.object_name, c.distance_m))
    return HarnessResult(
        cells=ordered, confusion=confusion,
        total_frames=total_frames, elapsed_s=elapsed,
    )


def result_to_report(result: HarnessResult, *, conf: float, imgsz: int,
                     model_path: str) -> dict[str, Any]:
    """Serialize a HarnessResult into a machine-readable report dict."""
    cells = []
    for cell in result.cells:
        cells.append({
            "object": cell.object_name,
            "distance_m": cell.distance_m,
            "frames": cell.frames,
            "detection_count": cell.detection_count,
            "recall": round(cell.recall, 3),
            "conf_min": round(cell.conf_min, 3) if cell.conf_min is not None else None,
            "conf_avg": round(cell.conf_avg, 3) if cell.conf_avg is not None else None,
            "conf_max": round(cell.conf_max, 3) if cell.conf_max is not None else None,
            "verdict": evaluate_recall_gate(cell.recall),
            "confusions": result.confusion.confusions(cell.object_name),
        })
    return {
        "model_path": model_path,
        "conf": conf,
        "imgsz": imgsz,
        "total_frames": result.total_frames,
        "elapsed_s": round(result.elapsed_s, 3),
        "fps": round(result.fps, 2),
        "cells": cells,
        "confusion_matrix": result.confusion.to_dict(),
    }


def render_dry_run(clips: Sequence[ClipSpec]) -> str:
    """Human-readable listing of clips that WOULD be processed (no model load)."""
    lines = [f"DRY RUN: {len(clips)} clip(s) discovered"]
    by_object: dict[str, list[ClipSpec]] = defaultdict(list)
    for spec in clips:
        by_object[spec.object_name].append(spec)
    for obj in sorted(by_object):
        for spec in sorted(by_object[obj], key=lambda s: s.distance_m):
            kind = "video" if spec.is_video else "image-folder"
            count = "" if spec.is_video else f" ({len(frame_paths_for_clip(spec))} imgs)"
            lines.append(
                f"  {spec.object_name:>10s} @ {spec.distance_m:>4.2f}m  "
                f"[{kind}]{count}  {spec.path}"
            )
    if not clips:
        lines.append("  (no labelled clips found — check path layout in --help)")
    return "\n".join(lines)


def parse_whitelist(raw: str | None) -> set[int] | None:
    if not raw:
        return None
    ids: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if token:
            ids.add(int(token))
    return ids or None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clips_root", help="root dir of recorded clips/image folders")
    parser.add_argument("--model", help="ONNX model path (yolo26n.onnx @ 640)")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    parser.add_argument("--whitelist", help="comma class-id whitelist, e.g. 39,41,56,67")
    parser.add_argument("--frame-stride", type=int, default=1,
                        help="process every Nth frame (default 1)")
    parser.add_argument("--out", help="write JSON report to this path")
    parser.add_argument("--dry-run", action="store_true",
                        help="list clips that would be processed, then exit")
    return parser.parse_args(argv)


def _print_cell_table(report: dict[str, Any]) -> None:
    header = (f"{'object':>10s} {'dist':>5s} {'frames':>6s} {'det':>4s} "
              f"{'recall':>6s} {'cmin':>5s} {'cavg':>5s} {'cmax':>5s} "
              f"{'verdict':>8s}  confusions")
    print(header)
    for cell in report["cells"]:
        def fmt(value: Any) -> str:
            return f"{value:.2f}" if isinstance(value, float) else "  -  "
        conf_str = ", ".join(f"{k}:{v}" for k, v in cell["confusions"].items()) or "-"
        print(f"{cell['object']:>10s} {cell['distance_m']:>5.2f} "
              f"{cell['frames']:>6d} {cell['detection_count']:>4d} "
              f"{cell['recall']:>6.2f} {fmt(cell['conf_min']):>5s} "
              f"{fmt(cell['conf_avg']):>5s} {fmt(cell['conf_max']):>5s} "
              f"{cell['verdict']:>8s}  {conf_str}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.clips_root).expanduser()

    try:
        clips = discover_clips(root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(render_dry_run(clips))
        return 0

    if not clips:
        print(render_dry_run(clips), file=sys.stderr)
        return 1
    if not args.model:
        print("ERROR: --model is required unless --dry-run", file=sys.stderr)
        return 1

    model_path = Path(args.model).expanduser()
    if not model_path.exists():
        print(f"ERROR: model not found: {model_path}", file=sys.stderr)
        return 1

    try:
        result = run_harness(
            clips, model_path, conf=args.conf, imgsz=args.imgsz,
            allowed=parse_whitelist(args.whitelist), frame_stride=args.frame_stride,
        )
    except RuntimeError as exc:  # missing cv2/ort or unreadable media.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = result_to_report(
        result, conf=args.conf, imgsz=args.imgsz, model_path=str(model_path))
    _print_cell_table(report)
    print(f"\noffline FPS (ORT CPU): {report['fps']}  "
          f"(total {report['total_frames']} frames in {report['elapsed_s']}s)")

    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"wrote_report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
