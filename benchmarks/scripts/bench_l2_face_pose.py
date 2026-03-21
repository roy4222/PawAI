#!/usr/bin/env python3
"""L2 benchmark: pose (balanced + lightweight) with face companion at 8Hz."""
import sys
import time
import threading
import logging

sys.path.insert(0, ".")

import cv2
import numpy as np

from benchmarks.adapters.face_yunet import FaceYuNetAdapter
from benchmarks.adapters.pose_rtmpose import PoseRTMPoseAdapter
from benchmarks.core.runner import BenchmarkRunner

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_l2")

TEST_IMG = "benchmarks/test_inputs/images/synthetic_640x480.jpg"
RESULTS_DIR = "benchmarks/results/raw"
COMPANION_META = [{"name": "yunet_2023mar", "rate_hz": 8.0, "mode": "headless"}]


def run_l2():
    # Load face companion
    face = FaceYuNetAdapter()
    face.load({
        "model_path": "/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
        "score_threshold": 0.35,
        "input_size": [320, 320],
    })
    test_img = cv2.imread(TEST_IMG)
    if test_img is None:
        test_img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)

    # Warmup face
    for _ in range(10):
        face.infer(test_img)

    # Background face thread at ~8Hz
    stop_face = threading.Event()

    def face_loop():
        while not stop_face.is_set():
            face.infer(test_img)
            time.sleep(1 / 8.0)

    face_thread = threading.Thread(target=face_loop, daemon=True)
    face_thread.start()
    logger.info("Face companion running at ~8Hz")

    runner = BenchmarkRunner(results_dir=RESULTS_DIR)

    # --- Balanced ---
    logger.info("=== L2: rtmpose_balanced + face ===")
    config_bal = {
        "name": "rtmpose_balanced",
        "params": {"mode": "balanced", "device": "cuda", "backend": "onnxruntime"},
        "benchmark": {"n_warmup": 10, "n_measure": 50,
                       "input_source": "benchmarks/test_inputs/images/"},
        "feasibility_gate": {"min_fps": 2.0, "must_not_crash": True},
    }
    r_bal = runner.run(
        adapter=PoseRTMPoseAdapter(),
        config=config_bal,
        task="pose_estimation",
        level=2,
        mode="headless",
        concurrent_models=COMPANION_META,
        test_input_ref=TEST_IMG,
    )
    fps_bal = r_bal["feasibility"]["fps_mean"]
    gate_bal = r_bal["feasibility"]["gate_pass"]
    logger.info(f"balanced L2: FPS={fps_bal}, gate={gate_bal}")

    # Cooldown
    time.sleep(10)

    # --- Lightweight ---
    logger.info("=== L2: rtmpose_lightweight + face ===")
    config_lw = {
        "name": "rtmpose_lightweight",
        "params": {"mode": "lightweight", "device": "cuda", "backend": "onnxruntime"},
        "benchmark": {"n_warmup": 10, "n_measure": 50,
                       "input_source": "benchmarks/test_inputs/images/"},
        "feasibility_gate": {"min_fps": 2.0, "must_not_crash": True},
    }
    r_lw = runner.run(
        adapter=PoseRTMPoseAdapter(),
        config=config_lw,
        task="pose_estimation",
        level=2,
        mode="headless",
        concurrent_models=COMPANION_META,
        test_input_ref=TEST_IMG,
    )
    fps_lw = r_lw["feasibility"]["fps_mean"]
    gate_lw = r_lw["feasibility"]["gate_pass"]
    logger.info(f"lightweight L2: FPS={fps_lw}, gate={gate_lw}")

    # Cleanup
    stop_face.set()
    face_thread.join(timeout=3)
    face.cleanup()

    print("\n" + "=" * 60)
    print(f"L2 Results (pose + face@8Hz companion):")
    print(f"  balanced:    FPS={fps_bal:6.1f}  gate={'PASS' if gate_bal else 'FAIL'}")
    print(f"  lightweight: FPS={fps_lw:6.1f}  gate={'PASS' if gate_lw else 'FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    run_l2()
