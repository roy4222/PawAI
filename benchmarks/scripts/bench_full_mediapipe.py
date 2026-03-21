#!/usr/bin/env python3
"""Test: Can MediaPipe Pose + Hands + YuNet ALL run on CPU simultaneously?
Measures FPS, CPU%, RAM, temperature over 30 seconds.
"""
import sys
import time
import threading
import logging
import json
import os

sys.path.insert(0, ".")

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_full_mp")

DURATION = 30
IMG_PATH = "benchmarks/test_inputs/images/synthetic_640x480.jpg"


def get_ram_mb():
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                p = line.split()
                if len(p) >= 2:
                    info[p[0].rstrip(":")] = int(p[1])
        return (info.get("MemTotal", 0) - info.get("MemAvailable", 0)) / 1024
    except:
        return 0


def get_gpu_load():
    try:
        return int(open("/sys/devices/gpu.0/load").read()) / 10.0
    except:
        return 0.0


def get_temp():
    try:
        return int(open("/sys/devices/virtual/thermal/thermal_zone1/temp").read()) / 1000.0
    except:
        return 0.0


def main():
    img = cv2.imread(IMG_PATH)
    if img is None:
        img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # --- Load all models ---
    logger.info("Loading YuNet...")
    face_det = cv2.FaceDetectorYN.create(
        "/home/jetson/face_models/face_detection_yunet_2023mar.onnx", "", (320, 320))

    logger.info("Loading MediaPipe Pose...")
    import mediapipe as mp
    mp_pose = mp.solutions.pose.Pose(
        static_image_mode=False, model_complexity=1, min_detection_confidence=0.5)

    logger.info("Loading MediaPipe Hands...")
    mp_hands = mp.solutions.hands.Hands(
        static_image_mode=False, max_num_hands=2, min_detection_confidence=0.5)

    # --- Warmup ---
    logger.info("Warming up...")
    for _ in range(5):
        face_det.setInputSize((640, 480))
        face_det.detect(img)
    for _ in range(3):
        mp_pose.process(img_rgb)
    for _ in range(3):
        mp_hands.process(img_rgb)

    # --- Concurrent test ---
    stop = threading.Event()
    counts = {"face": 0, "pose": 0, "hands": 0}
    errors = {"face": 0, "pose": 0, "hands": 0}
    hw_samples = []

    def face_loop():
        while not stop.is_set():
            try:
                face_det.setInputSize((640, 480))
                face_det.detect(img)
                counts["face"] += 1
            except Exception as e:
                errors["face"] += 1
                if errors["face"] <= 3:
                    logger.warning(f"face: {e}")
            time.sleep(1 / 8.0)

    def pose_loop():
        while not stop.is_set():
            try:
                mp_pose.process(img_rgb)
                counts["pose"] += 1
            except Exception as e:
                errors["pose"] += 1
                if errors["pose"] <= 3:
                    logger.warning(f"pose: {e}")

    def hands_loop():
        while not stop.is_set():
            try:
                mp_hands.process(img_rgb)
                counts["hands"] += 1
            except Exception as e:
                errors["hands"] += 1
                if errors["hands"] <= 3:
                    logger.warning(f"hands: {e}")

    def monitor_loop():
        while not stop.is_set():
            hw_samples.append({
                "ts": time.time(),
                "ram_mb": round(get_ram_mb(), 0),
                "gpu_pct": round(get_gpu_load(), 1),
                "temp_c": round(get_temp(), 1),
            })
            time.sleep(2)

    threads = [
        threading.Thread(target=face_loop, daemon=True),
        threading.Thread(target=pose_loop, daemon=True),
        threading.Thread(target=hands_loop, daemon=True),
        threading.Thread(target=monitor_loop, daemon=True),
    ]

    ram_before = get_ram_mb()
    logger.info(f"=== FULL MEDIAPIPE TEST: {DURATION}s ===")
    logger.info("Running: YuNet(CPU) + MP Pose(CPU) + MP Hands(CPU)")

    for t in threads:
        t.start()
    time.sleep(DURATION)
    stop.set()
    for t in threads:
        t.join(timeout=5)

    # --- Results ---
    face_fps = counts["face"] / DURATION
    pose_fps = counts["pose"] / DURATION
    hands_fps = counts["hands"] / DURATION

    ram_samples = [s["ram_mb"] for s in hw_samples]
    gpu_samples = [s["gpu_pct"] for s in hw_samples]
    temp_samples = [s["temp_c"] for s in hw_samples]

    result = {
        "_type": "mediapipe_feasibility_test",
        "duration_sec": DURATION,
        "face_fps": round(face_fps, 1),
        "pose_fps": round(pose_fps, 1),
        "hands_fps": round(hands_fps, 1),
        "face_errors": errors["face"],
        "pose_errors": errors["pose"],
        "hands_errors": errors["hands"],
        "ram_before_mb": round(ram_before, 0),
        "ram_peak_mb": round(max(ram_samples), 0) if ram_samples else 0,
        "ram_mean_mb": round(sum(ram_samples) / len(ram_samples), 0) if ram_samples else 0,
        "gpu_mean_pct": round(sum(gpu_samples) / len(gpu_samples), 1) if gpu_samples else 0,
        "temp_mean_c": round(sum(temp_samples) / len(temp_samples), 1) if temp_samples else 0,
        "temp_max_c": round(max(temp_samples), 1) if temp_samples else 0,
        "crashed": any(v > 0 for v in errors.values()),
    }

    print(f"\n{'='*60}")
    print(f"FULL MEDIAPIPE FEASIBILITY ({DURATION}s)")
    print(f"{'='*60}")
    print(f"  YuNet (CPU@8Hz):      {counts['face']} frames, {face_fps:.1f} FPS, {errors['face']} errors")
    print(f"  MP Pose (CPU):        {counts['pose']} frames, {pose_fps:.1f} FPS, {errors['pose']} errors")
    print(f"  MP Hands (CPU):       {counts['hands']} frames, {hands_fps:.1f} FPS, {errors['hands']} errors")
    print(f"  GPU:  {result['gpu_mean_pct']:.1f}% (should be ~0%)")
    print(f"  RAM:  {result['ram_mean_mb']:.0f} MB mean, {result['ram_peak_mb']:.0f} MB peak")
    print(f"  Temp: {result['temp_mean_c']:.1f}°C mean, {result['temp_max_c']:.1f}°C max")
    print(f"  Crashed: {result['crashed']}")
    print(f"{'='*60}")
    print()
    print("COMPARISON:")
    print(f"  {'':25s} {'Mixed (now)':>12s} {'Full MP':>12s}")
    print(f"  {'Pose FPS':25s} {'17.6':>12s} {pose_fps:>12.1f}")
    print(f"  {'Gesture FPS':25s} {'16.8':>12s} {hands_fps:>12.1f}")
    print(f"  {'GPU%':25s} {'~90%':>12s} {result['gpu_mean_pct']:>11.1f}%")
    print(f"  {'RAM peak':25s} {'~3.5GB':>12s} {result['ram_peak_mb']:>10.0f}MB")

    out_path = "benchmarks/results/raw/full_mediapipe_test.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "a") as f:
        f.write(json.dumps(result, default=str) + "\n")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
