#!/usr/bin/env python3
"""L3: Full stack coexistence test — face + pose + whisper simultaneously."""
import json
import logging
import os
import sys
import threading
import time

sys.path.insert(0, ".")

import cv2
import numpy as np

from benchmarks.adapters.face_yunet import FaceYuNetAdapter
from benchmarks.adapters.pose_rtmpose import PoseRTMPoseAdapter
from benchmarks.core.monitor import JetsonMonitor

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_l3")

TEST_IMG = "benchmarks/test_inputs/images/synthetic_640x480.jpg"
DURATION_SEC = 30


def run_l3():
    test_img = cv2.imread(TEST_IMG)
    if test_img is None:
        test_img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)

    # --- Load all models ---
    logger.info("Loading face (YuNet)...")
    face = FaceYuNetAdapter()
    face.load({"model_path": "/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
               "score_threshold": 0.35, "input_size": [320, 320]})

    logger.info("Loading pose (RTMPose lightweight)...")
    pose = PoseRTMPoseAdapter()
    pose.load({"mode": "lightweight", "device": "cuda", "backend": "onnxruntime"})

    # Whisper: load via faster-whisper directly
    whisper_model = None
    try:
        from faster_whisper import WhisperModel
        logger.info("Loading whisper (small)...")
        whisper_model = WhisperModel("small", device="cuda", compute_type="float16")
        audio_input = np.random.randn(3 * 16000).astype(np.float32) * 0.01
    except Exception as e:
        logger.warning(f"Whisper not available: {e}")

    # --- Warmup all ---
    logger.info("Warming up...")
    for _ in range(5):
        face.infer(test_img)
    for _ in range(5):
        pose.infer(test_img)
    if whisper_model:
        for _ in range(2):
            list(whisper_model.transcribe(audio_input, language="zh", beam_size=1)[0])

    # --- Start monitor ---
    monitor = JetsonMonitor(interval=1.0)
    monitor.start()

    # --- Run all models concurrently for DURATION_SEC ---
    stop = threading.Event()
    counts = {"face": 0, "pose": 0, "whisper": 0}
    errors = {"face": 0, "pose": 0, "whisper": 0}

    def face_loop():
        while not stop.is_set():
            try:
                face.infer(test_img)
                counts["face"] += 1
            except Exception as e:
                errors["face"] += 1
                if errors["face"] <= 3:
                    logger.warning(f"face error: {e}")
            time.sleep(1 / 8.0)  # ~8Hz

    def pose_loop():
        while not stop.is_set():
            try:
                pose.infer(test_img)
                counts["pose"] += 1
            except Exception as e:
                errors["pose"] += 1
                if errors["pose"] <= 3:
                    logger.warning(f"pose error: {e}")

    def whisper_loop():
        if not whisper_model:
            return
        while not stop.is_set():
            try:
                list(whisper_model.transcribe(audio_input, language="zh", beam_size=1)[0])
                counts["whisper"] += 1
            except Exception as e:
                errors["whisper"] += 1
                if errors["whisper"] <= 3:
                    logger.warning(f"whisper error: {e}")
            time.sleep(5.0)  # on-demand every 5s

    threads = [
        threading.Thread(target=face_loop, daemon=True),
        threading.Thread(target=pose_loop, daemon=True),
        threading.Thread(target=whisper_loop, daemon=True),
    ]

    logger.info(f"=== L3 FULL STACK: {DURATION_SEC}s ===")
    logger.info("Running: face@8Hz(CPU) + pose(CUDA) + whisper@0.2Hz(CUDA)")

    for t in threads:
        t.start()

    time.sleep(DURATION_SEC)
    stop.set()
    for t in threads:
        t.join(timeout=10)

    hw_records = monitor.stop()
    hw_stats = JetsonMonitor.aggregate(hw_records)

    # --- Cleanup ---
    face.cleanup()
    pose.cleanup()

    # --- Results ---
    pose_fps = counts["pose"] / DURATION_SEC
    face_fps = counts["face"] / DURATION_SEC
    whisper_rate = counts["whisper"] / DURATION_SEC

    result = {
        "_type": "exploratory/stress-only",  # NOT comparable to L1/L2 schema
        "duration_sec": DURATION_SEC,
        "face_count": counts["face"],
        "face_fps": round(face_fps, 1),
        "face_errors": errors["face"],
        "pose_count": counts["pose"],
        "pose_fps": round(pose_fps, 1),
        "pose_errors": errors["pose"],
        "whisper_count": counts["whisper"],
        "whisper_rate_hz": round(whisper_rate, 2),
        "whisper_errors": errors["whisper"],
        "hw_stats": hw_stats,
        "crashed": any(v > 0 for v in errors.values()),
    }

    print(f"\n{'='*60}")
    print(f"L3 FULL STACK RESULTS ({DURATION_SEC}s)")
    print(f"{'='*60}")
    print(f"  Face (YuNet, CPU@8Hz):     {counts['face']} frames, {face_fps:.1f} FPS, {errors['face']} errors")
    print(f"  Pose (RTMPose lw, CUDA):   {counts['pose']} frames, {pose_fps:.1f} FPS, {errors['pose']} errors")
    print(f"  Whisper (small, CUDA@5s):  {counts['whisper']} infers, {whisper_rate:.2f} Hz, {errors['whisper']} errors")
    if hw_stats:
        print(f"  GPU: {hw_stats.get('gpu_util_pct_mean', '?')}%  "
              f"RAM: {hw_stats.get('ram_mb_peak', '?')}MB  "
              f"Temp: {hw_stats.get('temp_c_max', '?')}°C  "
              f"Power: {hw_stats.get('power_w_mean', '?')}W")
    print(f"  Crashed: {result['crashed']}")
    print(f"{'='*60}")

    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    out_dir = "benchmarks/results/raw"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"l3_full_stack_{date_str}.jsonl")
    with open(out_path, "a") as f:
        f.write(json.dumps(result, default=str) + "\n")
    print(f"  Saved: {out_path}")


if __name__ == "__main__":
    run_l3()
