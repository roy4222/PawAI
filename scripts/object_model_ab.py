#!/usr/bin/env python3
"""Generate object model A/B capture commands.

This intentionally does not restart ROS nodes or move hardware. The operator
starts object_perception with the selected model, then runs the generated
``obj_matrix_cap.py`` command for each cell. Metadata is carried in ``--notes``
so CSV rows remain traceable.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    path: str


def parse_model_specs(items: list[str]) -> list[ModelSpec]:
    specs: list[ModelSpec] = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"model spec must be name=/path/model.onnx: {item!r}")
        name, path = item.split("=", 1)
        name = name.strip()
        path = path.strip()
        if not name or not path:
            raise ValueError(f"invalid model spec: {item!r}")
        specs.append(ModelSpec(name=name, path=path))
    return specs


def build_capture_command(
    *,
    model_name: str,
    model_path: str,
    threshold: float,
    input_size: int,
    git_commit: str,
    target_object: str,
    distance: float,
    light: str,
    angle: str,
    trials: int,
    window: float,
    gap: float,
    output_csv: str,
) -> list[str]:
    notes = (
        f"model_name={model_name};model_path={model_path};conf={threshold};"
        f"input_size={input_size};git_commit={git_commit}"
    )
    return [
        "python3", "scripts/obj_matrix_cap.py",
        "--object", target_object,
        "--distance", str(distance),
        "--light", light,
        "--angle", angle,
        "--trials", str(trials),
        "--window", str(window),
        "--gap", str(gap),
        "--auto",
        "--out", output_csv,
        "--notes", notes,
    ]


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", action="append", required=True,
                   help="model profile as name=/path/model.onnx; repeatable")
    p.add_argument("--threshold", type=float, default=0.35)
    p.add_argument("--input-size", type=int, default=640)
    p.add_argument("--object", default="cup")
    p.add_argument("--distance", type=float, default=1.0)
    p.add_argument("--light", default="normal")
    p.add_argument("--angle", default="front")
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--window", type=float, default=6.0)
    p.add_argument("--gap", type=float, default=6.0)
    p.add_argument("--out-dir", default="artifacts/object_matrix")
    args = p.parse_args(argv)

    specs = parse_model_specs(args.model)
    commit = _git_commit()
    for spec in specs:
        out = f"{args.out_dir}/{spec.name}_{args.object}_{args.distance:g}m.csv"
        cmd = build_capture_command(
            model_name=spec.name,
            model_path=spec.path,
            threshold=args.threshold,
            input_size=args.input_size,
            git_commit=commit,
            target_object=args.object,
            distance=args.distance,
            light=args.light,
            angle=args.angle,
            trials=args.trials,
            window=args.window,
            gap=args.gap,
            output_csv=out,
        )
        print(shlex.join(cmd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
