#!/usr/bin/env python3
"""Check whether an object ONNX model matches object_perception's output contract.

Current object_perception postprocess expects a YOLO26 detection tensor shaped
like ``(1, 300, 6)``: x1, y1, x2, y2, confidence, class_id. Segmentation,
open-vocabulary, or NMS-bearing exports need a new adapter and should fail this
check before a HITL run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _shape_to_list(shape: Any) -> list[Any]:
    return [int(x) if isinstance(x, int) else str(x) for x in list(shape or [])]


def is_compatible_output_shape(shape: list[Any]) -> bool:
    """Return True for rank-3 detection output whose last dimension is 6."""
    if len(shape) != 3:
        return False
    return shape[-1] == 6


def _sha256_short(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def inspect_model(path: Path, providers: list[str] | None = None) -> dict[str, Any]:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=providers or ["CPUExecutionProvider"])
    inputs = [{"name": i.name, "shape": _shape_to_list(i.shape), "type": i.type}
              for i in sess.get_inputs()]
    outputs = [{"name": o.name, "shape": _shape_to_list(o.shape), "type": o.type}
               for o in sess.get_outputs()]
    compatible = any(is_compatible_output_shape(o["shape"]) for o in outputs)
    return {
        "model_path": str(path),
        "sha256": _sha256_short(path),
        "providers": sess.get_providers(),
        "inputs": inputs,
        "outputs": outputs,
        "compatible_object_perception": compatible,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("model_path")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.add_argument("--allow-incompatible", action="store_true",
                   help="return 0 even when output shape does not match")
    args = p.parse_args(argv)

    path = Path(args.model_path).expanduser()
    if not path.exists():
        raise SystemExit(f"model not found: {path}")

    report = inspect_model(path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"model: {report['model_path']}")
        print(f"sha256: {report['sha256']}")
        print(f"providers: {', '.join(report['providers'])}")
        print(f"inputs: {report['inputs']}")
        print(f"outputs: {report['outputs']}")
        print(f"compatible_object_perception: {report['compatible_object_perception']}")

    if report["compatible_object_perception"] or args.allow_incompatible:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
