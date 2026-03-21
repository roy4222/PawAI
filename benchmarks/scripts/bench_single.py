#!/usr/bin/env python3
"""CLI entry point: benchmark a single model from a candidates config.

Usage:
    python benchmarks/scripts/bench_single.py \
        --config benchmarks/configs/face_candidates.yaml \
        --model yunet_legacy \
        --level 1
"""
import argparse
import importlib
import logging
import sys

import yaml

# Add repo root to path so 'benchmarks' package is importable
sys.path.insert(0, ".")

from benchmarks.core.runner import BenchmarkRunner

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_single")

# Adapter registry: adapter name -> module.Class
ADAPTER_REGISTRY = {
    "face_yunet": "benchmarks.adapters.face_yunet:FaceYuNetAdapter",
    "pose_rtmpose": "benchmarks.adapters.pose_rtmpose:PoseRTMPoseAdapter",
    "gesture_mediapipe": "benchmarks.adapters.gesture_mediapipe:GestureMediaPipeAdapter",
    "pose_mediapipe": "benchmarks.adapters.pose_mediapipe:PoseMediaPipeAdapter",
    "face_scrfd": "benchmarks.adapters.face_scrfd:FaceSCRFDAdapter",
}


def load_adapter(adapter_name: str):
    """Dynamically load an adapter class by name."""
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter: {adapter_name}. "
                         f"Known: {list(ADAPTER_REGISTRY.keys())}")
    module_path, class_name = ADAPTER_REGISTRY[adapter_name].rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def main():
    parser = argparse.ArgumentParser(description="Run benchmark for a single model")
    parser.add_argument("--config", required=True, help="Path to candidates YAML")
    parser.add_argument("--model", required=True, help="Model name from config")
    parser.add_argument("--level", type=int, default=1, help="Benchmark level (1-4)")
    parser.add_argument("--mode", default="headless", choices=["headless", "ros_debug"])
    parser.add_argument("--results-dir", default="benchmarks/results/raw")
    parser.add_argument("--input", default=None, help="Test input file (overrides config)")
    args = parser.parse_args()

    with open(args.config) as f:
        candidates = yaml.safe_load(f)

    task = candidates["task"]
    model_config = None
    for m in candidates["models"]:
        if m["name"] == args.model:
            model_config = m
            break

    if model_config is None:
        logger.error(f"Model '{args.model}' not found in {args.config}")
        sys.exit(1)

    adapter = load_adapter(model_config["adapter"])
    runner = BenchmarkRunner(results_dir=args.results_dir)
    result = runner.run(
        adapter=adapter,
        config=model_config,
        task=task,
        level=args.level,
        mode=args.mode,
        test_input_ref=args.input,
    )

    gate = "PASS" if result["feasibility"].get("gate_pass") else "FAIL"
    fps = result["feasibility"].get("fps_mean", "?")
    logger.info(f"\n{'='*50}")
    logger.info(f"Model: {args.model}")
    logger.info(f"FPS: {fps}")
    logger.info(f"Gate: {gate}")
    logger.info(f"Hint: {result.get('decision_hint', '?')}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
