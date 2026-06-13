#!/usr/bin/env python3
"""Offline ONNX sanity check for Lane 4 object-model candidates.

This script is a WSL-only spike. It validates that an ONNX model can be opened
by ONNX Runtime CPU, has an object_perception-compatible output tensor
(``(1, 300, 6)``-style detections), and can run one synthetic BGR frame.

Before running with real models, check whether fixed-shape e2e exports already
exist:

    ls .tmp/yolo_export/out/

Expected stems are ``yolo26s_640``, ``yolo26n_960``, and ``yolo26s_960``. If
they are missing, use the existing export workspace, for example:

    .tmp/yolo_export/venv/bin/python .tmp/yolo_export/export_models.py \
        --models yolo26s:640 yolo26n:960 yolo26s:960 --e2e --fixed-shape

Models are not committed. After review, copy them to Jetson additively, without
``--delete``:

    rsync -av .tmp/yolo_export/out/*.onnx jetson-nano:/home/jetson/models/
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts import object_model_contract


@dataclass(frozen=True)
class LetterboxMeta:
    output_shape: tuple[int, int, int]
    resized_shape: tuple[int, int]
    pad_top: int
    pad_left: int
    scale: float


@dataclass(frozen=True)
class SanityReport:
    model_path: str
    providers: list[str]
    input_name: str
    output_shapes: list[list[Any]]
    actual_output_shapes: list[list[int]]
    compatible_object_perception: bool


def generate_synthetic_bgr(width: int, height: int, seed: int = 0) -> np.ndarray:
    """Return a deterministic random BGR uint8 frame."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def letterbox_resize_bgr(image_bgr: np.ndarray, imgsz: int) -> tuple[np.ndarray, LetterboxMeta]:
    """Resize BGR image into square letterbox canvas."""
    if imgsz <= 0:
        raise ValueError("imgsz must be positive")
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("image_bgr must have shape (H, W, 3)")

    height, width = image_bgr.shape[:2]
    scale = min(imgsz / float(width), imgsz / float(height))
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    resized = cv2.resize(image_bgr, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    pad_left = (imgsz - new_width) // 2
    pad_top = (imgsz - new_height) // 2
    canvas[pad_top:pad_top + new_height, pad_left:pad_left + new_width] = resized
    meta = LetterboxMeta(
        output_shape=canvas.shape,
        resized_shape=(new_height, new_width),
        pad_top=pad_top,
        pad_left=pad_left,
        scale=scale,
    )
    return canvas, meta


def preprocess_bgr_for_onnx(image_bgr: np.ndarray, imgsz: int) -> tuple[np.ndarray, LetterboxMeta]:
    """Return RGB NCHW float32 input blob and letterbox metadata."""
    canvas, meta = letterbox_resize_bgr(image_bgr, imgsz)
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[None, ...]
    return blob, meta


def is_object_output_shape_compatible(shape: list[Any]) -> bool:
    """Delegate compatibility to the runtime contract helper."""
    return object_model_contract.is_compatible_output_shape(shape)


def _shape_to_list(shape: Any) -> list[Any]:
    return [int(x) if isinstance(x, int) else str(x) for x in list(shape or [])]


def _actual_shape_to_list(array: np.ndarray) -> list[int]:
    return [int(x) for x in array.shape]


def _blob_for_input(input_shape: list[Any], nchw_blob: np.ndarray) -> np.ndarray:
    if len(input_shape) == 4 and str(input_shape[-1]) == "3":
        return np.transpose(nchw_blob, (0, 2, 3, 1))
    return nchw_blob


def run_sanity(model_path: Path, imgsz: int) -> SanityReport:
    """Open the model with ORT CPU and run one synthetic frame."""
    try:
        import onnxruntime as ort
    except ImportError as exc:  # pragma: no cover - depends on local env.
        raise RuntimeError("onnxruntime is required for end-to-end sanity") from exc

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_meta = session.get_inputs()[0]
    input_shape = _shape_to_list(input_meta.shape)
    image = generate_synthetic_bgr(width=imgsz, height=imgsz, seed=13)
    nchw_blob, _ = preprocess_bgr_for_onnx(image, imgsz=imgsz)
    input_blob = _blob_for_input(input_shape, nchw_blob)

    outputs = session.run(None, {input_meta.name: input_blob})
    output_shapes = [_shape_to_list(meta.shape) for meta in session.get_outputs()]
    actual_shapes = [_actual_shape_to_list(output) for output in outputs]
    compatible = any(is_object_output_shape_compatible(shape) for shape in actual_shapes)
    if not compatible:
        compatible = any(is_object_output_shape_compatible(shape) for shape in output_shapes)

    return SanityReport(
        model_path=str(model_path),
        providers=list(session.get_providers()),
        input_name=str(input_meta.name),
        output_shapes=output_shapes,
        actual_output_shapes=actual_shapes,
        compatible_object_perception=compatible,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="ONNX model path")
    parser.add_argument("--imgsz", type=int, default=640, help="synthetic square input size")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    model_path = Path(args.model).expanduser()
    if not model_path.exists():
        print(f"ERROR: model not found: {model_path}", file=sys.stderr)
        return 1

    try:
        report = run_sanity(model_path=model_path, imgsz=int(args.imgsz))
    except Exception as exc:
        print(f"ERROR: ONNX sanity failed: {exc}", file=sys.stderr)
        return 1

    payload = asdict(report)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"model: {report.model_path}")
        print(f"providers: {', '.join(report.providers)}")
        print(f"input: {report.input_name}")
        print(f"declared_outputs: {report.output_shapes}")
        print(f"actual_outputs: {report.actual_output_shapes}")
        print(f"compatible_object_perception: {report.compatible_object_perception}")

    return 0 if report.compatible_object_perception else 2


if __name__ == "__main__":
    raise SystemExit(main())
