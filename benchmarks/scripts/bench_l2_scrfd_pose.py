#!/usr/bin/env python3
"""L2 benchmark: pose lightweight with SCRFD companion.
Tests if SCRFD (GPU) + RTMPose (GPU) can coexist.
"""
import sys
import time
import threading
import logging

sys.path.insert(0, ".")

import cv2
import numpy as np

from benchmarks.adapters.face_scrfd import FaceSCRFDAdapter
from benchmarks.adapters.pose_rtmpose import PoseRTMPoseAdapter
from benchmarks.core.runner import BenchmarkRunner

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_l2_scrfd")

TEST_IMG = "benchmarks/test_inputs/images/synthetic_640x480.jpg"
COMPANION_META = [{"name": "scrfd_500m", "rate_hz": 8.0, "mode": "headless"}]


def run_l2():
    # Load SCRFD companion
    scrfd = FaceSCRFDAdapter()
    scrfd.load({
        "model_path": "/home/jetson/face_models/det_500m.onnx",
        "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"],
        "input_size": [640, 640],
    })
    test_img = cv2.imread(TEST_IMG)
    if test_img is None:
        test_img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)

    # Warmup SCRFD
    for _ in range(10):
        scrfd.infer(test_img)

    # Background SCRFD thread at ~8Hz
    stop = threading.Event()
    def scrfd_loop():
        while not stop.is_set():
            scrfd.infer(test_img)
            time.sleep(1 / 8.0)

    t = threading.Thread(target=scrfd_loop, daemon=True)
    t.start()
    logger.info("SCRFD companion running at ~8Hz (GPU)")

    # Benchmark pose lightweight with SCRFD companion (both on GPU!)
    runner = BenchmarkRunner(results_dir="benchmarks/results/raw")
    config = {
        "name": "rtmpose_lightweight",
        "params": {"mode": "lightweight", "device": "cuda", "backend": "onnxruntime"},
        "benchmark": {"n_warmup": 10, "n_measure": 50,
                       "input_source": "benchmarks/test_inputs/images/"},
        "feasibility_gate": {"min_fps": 2.0, "must_not_crash": True},
    }
    result = runner.run(
        adapter=PoseRTMPoseAdapter(),
        config=config,
        task="pose_estimation",
        level=2,
        mode="headless",
        concurrent_models=COMPANION_META,
        test_input_ref=TEST_IMG,
    )
    fps = result["feasibility"]["fps_mean"]
    gate = result["feasibility"]["gate_pass"]

    stop.set()
    t.join(timeout=3)
    scrfd.cleanup()

    print(f"\n{'='*60}")
    print(f"L2: pose_lightweight + SCRFD@8Hz (BOTH GPU)")
    print(f"  FPS: {fps:.1f}  gate={'PASS' if gate else 'FAIL'}")
    print(f"  Compare: L1 standalone = 17.6, L2 with YuNet(CPU) = 16.5")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_l2()
