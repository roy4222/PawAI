#!/usr/bin/env python3
"""Compare current HSV12 color naming with Lab-LUT zh color naming.

Offline Lane 4 W3 spike. It reads an image plus one or more bounding boxes and
prints/writes a per-bbox table:

    HSV12 full bbox, HSV12 center 50%, Lab-LUT full bbox, Lab-LUT center 50%

The HSV12 path prefers object_perception's ``analyze_bbox_color``. If importing
that module pulls in unavailable ROS2 dependencies, this script falls back to a
pure OpenCV copy of the same HSV12 masks. The Lab-LUT path is independent and
uses a fixed Traditional Chinese 19+1 color-name v0 list.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

BBox = tuple[int, int, int, int]
HsvAnalyzer = Callable[[np.ndarray, int, int, int, int], tuple[str, float]]

LAB_COLOR_BGR_V0: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("紅色", (0, 0, 255)),
    ("橙色", (0, 128, 255)),
    ("黃色", (0, 255, 255)),
    ("黃綠色", (0, 255, 128)),
    ("綠色", (0, 255, 0)),
    ("青色", (255, 255, 0)),
    ("天藍色", (255, 200, 0)),
    ("藍色", (255, 0, 0)),
    ("紫色", (255, 0, 128)),
    ("粉紅色", (203, 192, 255)),
    ("棕色", (42, 42, 165)),
    ("米色", (220, 245, 245)),
    ("黑色", (0, 0, 0)),
    ("白色", (255, 255, 255)),
    ("灰色", (128, 128, 128)),
    ("深灰色", (64, 64, 64)),
    ("淺灰色", (192, 192, 192)),
    ("金色", (0, 215, 255)),
    ("深藍色", (128, 0, 0)),
)
LAB_COLOR_NAMES_V0 = tuple(name for name, _ in LAB_COLOR_BGR_V0) + ("unknown",)


@dataclass(frozen=True)
class ColorName:
    name: str
    confidence: float
    distance: float


@dataclass(frozen=True)
class ColorComparison:
    bbox: str
    hsv12_full: str
    hsv12_full_conf: float
    hsv12_center: str
    hsv12_center_conf: float
    lab_full: str
    lab_full_conf: float
    lab_center: str
    lab_center_conf: float


def center_half_bbox(bbox: BBox) -> BBox:
    """Return center crop with width and height reduced to 50%."""
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    return (
        int(round(x1 + width * 0.25)),
        int(round(y1 + height * 0.25)),
        int(round(x1 + width * 0.75)),
        int(round(y1 + height * 0.75)),
    )


def _clip_bbox(image_bgr: np.ndarray, bbox: BBox) -> BBox | None:
    height, width = image_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(int(x1), width - 1))
    x2 = max(0, min(int(x2), width))
    y1 = max(0, min(int(y1), height - 1))
    y2 = max(0, min(int(y2), height))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _crop(image_bgr: np.ndarray, bbox: BBox) -> np.ndarray:
    clipped = _clip_bbox(image_bgr, bbox)
    if clipped is None:
        return np.empty((0, 0, 3), dtype=np.uint8)
    x1, y1, x2, y2 = clipped
    return image_bgr[y1:y2, x1:x2]


def _bgr_to_lab_vector(bgr: tuple[int, int, int]) -> np.ndarray:
    pixel = np.array([[bgr]], dtype=np.uint8)
    return cv2.cvtColor(pixel, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)


def _lab_lut() -> tuple[tuple[str, np.ndarray], ...]:
    return tuple((name, _bgr_to_lab_vector(bgr)) for name, bgr in LAB_COLOR_BGR_V0)


def name_lab_color(image_bgr: np.ndarray, bbox: BBox) -> ColorName:
    """Name mean bbox color by nearest neighbor in Lab space."""
    crop = _crop(image_bgr, bbox)
    if crop.size == 0:
        return ColorName(name="unknown", confidence=0.0, distance=float("inf"))
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)
    mean_lab = np.mean(lab.reshape(-1, 3), axis=0)
    distances = [
        (name, float(np.linalg.norm(mean_lab - lab_value)))
        for name, lab_value in _lab_lut()
    ]
    name, distance = min(distances, key=lambda item: item[1])
    confidence = max(0.0, 1.0 - min(distance / 255.0, 1.0))
    return ColorName(name=name, confidence=round(confidence, 3), distance=round(distance, 3))


def analyze_bbox_color_hsv12(image_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int):
    """Pure fallback copy of object_perception HSV12 bbox color analysis."""
    crop = _crop(image_bgr, (x1, y1, x2, y2))
    if crop.size == 0:
        return "Unknown", 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h_channel = hsv[..., 0]
    s_channel = hsv[..., 1]
    v_channel = hsv[..., 2]

    black = v_channel < 50
    white = (s_channel < 40) & (v_channel >= 200) & ~black
    gray = (s_channel < 40) & ~black & ~white
    chromatic = ~(black | white | gray)
    brown = chromatic & (h_channel >= 5) & (h_channel <= 25) & (v_channel < 130)
    rest = chromatic & ~brown
    pink = (
        rest
        & (((h_channel >= 160) | (h_channel <= 5)) & (s_channel < 150))
        & (v_channel >= 180)
    ) | (rest & (h_channel > 150) & (h_channel < 165))
    rest = rest & ~pink
    masks = {
        "black": black,
        "white": white,
        "gray": gray,
        "brown": brown,
        "pink": pink,
        "red": rest & ((h_channel <= 8) | (h_channel >= 165)),
        "orange": rest & (h_channel > 8) & (h_channel <= 22),
        "yellow": rest & (h_channel > 22) & (h_channel <= 35),
        "green": rest & (h_channel > 35) & (h_channel <= 85),
        "cyan": rest & (h_channel > 85) & (h_channel <= 100),
        "blue": rest & (h_channel > 100) & (h_channel <= 130),
        "purple": rest & (h_channel > 130) & (h_channel <= 150),
    }
    counts = {name: int(mask.sum()) for name, mask in masks.items()}
    total = float(sum(counts.values()))
    if total <= 0:
        return "Unknown", 0.0
    peak = max(counts, key=counts.get)
    ratio = counts[peak] / total
    if ratio < 0.25:
        return "Unknown", 0.0
    return peak, round(float(ratio), 3)


def load_hsv12_analyzer() -> HsvAnalyzer:
    """Prefer current runtime HSV12 function, falling back if ROS imports fail."""
    try:
        from object_perception.object_perception.object_perception_node import (
            analyze_bbox_color,
        )

        return analyze_bbox_color
    except Exception:
        return analyze_bbox_color_hsv12


def compare_bbox_colors(
    image_bgr: np.ndarray,
    bbox: BBox,
    hsv_analyzer: HsvAnalyzer | None = None,
) -> ColorComparison:
    analyzer = hsv_analyzer or load_hsv12_analyzer()
    center = center_half_bbox(bbox)
    hsv_full, hsv_full_conf = analyzer(image_bgr, *bbox)
    hsv_center, hsv_center_conf = analyzer(image_bgr, *center)
    lab_full = name_lab_color(image_bgr, bbox)
    lab_center = name_lab_color(image_bgr, center)
    return ColorComparison(
        bbox=",".join(str(value) for value in bbox),
        hsv12_full=str(hsv_full),
        hsv12_full_conf=float(hsv_full_conf),
        hsv12_center=str(hsv_center),
        hsv12_center_conf=float(hsv_center_conf),
        lab_full=lab_full.name,
        lab_full_conf=lab_full.confidence,
        lab_center=lab_center.name,
        lab_center_conf=lab_center.confidence,
    )


def parse_bbox(raw: str) -> BBox:
    parts = [int(part.strip()) for part in raw.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be x1,y1,x2,y2")
    x1, y1, x2, y2 = parts
    if x2 <= x1 or y2 <= y1:
        raise argparse.ArgumentTypeError("bbox must have x2>x1 and y2>y1")
    return x1, y1, x2, y2


def write_csv(rows: list[ColorComparison], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def print_table(rows: list[ColorComparison]) -> None:
    for row in rows:
        print(
            "bbox={bbox} hsv_full={hsv12_full}:{hsv12_full_conf:.3f} "
            "hsv_center={hsv12_center}:{hsv12_center_conf:.3f} "
            "lab_full={lab_full}:{lab_full_conf:.3f} "
            "lab_center={lab_center}:{lab_center_conf:.3f}".format(**asdict(row))
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="input image path")
    parser.add_argument("--bbox", action="append", type=parse_bbox, required=True)
    parser.add_argument(
        "--out-csv",
        default="benchmarks/results/raw/color_naming_spike.csv",
        help="CSV output path under a gitignored results directory",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    image_path = Path(args.image).expanduser()
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        print(f"ERROR: image not readable: {image_path}", file=sys.stderr)
        return 1

    rows = [compare_bbox_colors(image, bbox) for bbox in args.bbox]
    print_table(rows)
    write_csv(rows, Path(args.out_csv))
    print(f"wrote_csv: {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
