#!/usr/bin/env python3
"""Standalone test: MediaPipe Gesture Recognizer Task API on Jetson.

No ROS2 dependency. Uses D435 via OpenCV.
Downloads model automatically if not present.

Exit codes:
    0 = all tests passed
    1 = import or model load failed
    2 = live stream quality gate failed (FPS < 10)

Usage:
    python3 scripts/test_gesture_recognizer.py [--duration 30] [--device 0]
    python3 scripts/test_gesture_recognizer.py --model-path /path/to/model.task
"""
import argparse
import os
import sys
import time
from collections import defaultdict

_DEFAULT_MODEL_DIR = os.path.expanduser("~/face_models")
_DEFAULT_MODEL_PATH = os.path.join(_DEFAULT_MODEL_DIR, "gesture_recognizer.task")
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
)


def ensure_model(model_path: str) -> str:
    """Ensure gesture_recognizer.task exists. Download if missing and online."""
    if os.path.exists(model_path):
        size_mb = os.path.getsize(model_path) / 1e6
        print(f"[OK] Model exists: {model_path} ({size_mb:.1f} MB)")
        return model_path

    model_dir = os.path.dirname(model_path)
    os.makedirs(model_dir, exist_ok=True)
    print(f"Model not found at {model_path}, attempting download...")
    try:
        import urllib.request
        urllib.request.urlretrieve(_MODEL_URL, model_path)
        size_mb = os.path.getsize(model_path) / 1e6
        print(f"[OK] Downloaded ({size_mb:.1f} MB)")
        return model_path
    except Exception as e:
        print(f"[FAIL] Download failed: {e}")
        print(f"  Please manually download the model and place it at:")
        print(f"    {model_path}")
        print(f"  Or specify --model-path to an existing file.")
        print(f"  URL: {_MODEL_URL}")
        sys.exit(1)


def test_import():
    """Test 1: Can we import the Task API?"""
    print("\n=== Test 1: Import ===")
    try:
        import mediapipe as mp  # noqa: F401
        from mediapipe.tasks.python import vision  # noqa: F401
        print(f"[OK] mediapipe {mp.__version__}")
        print("[OK] mediapipe.tasks.python.vision imported")
        return True
    except ImportError as e:
        print(f"[FAIL] {e}")
        return False


def test_model_load(model_path: str):
    """Test 2: Can we load the model?"""
    print("\n=== Test 2: Model Load ===")
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    t0 = time.time()
    try:
        options = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(
                model_asset_path=model_path
            ),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=2,
        )
        recognizer = vision.GestureRecognizer.create_from_options(options)
        load_time = time.time() - t0
        print(f"[OK] Model loaded in {load_time:.1f}s")
        recognizer.close()
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_live_stream(duration: int, device: int, model_path: str,
                     min_fps: float = 10.0) -> bool:
    """Test 3: Live stream recognition with D435 / webcam.

    Returns True if quality gate passed (FPS >= min_fps).
    """
    print(f"\n=== Test 3: Live Stream ({duration}s, device={device}) ===")
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"[FAIL] Cannot open camera device {device}")
        return False

    # Stats
    gesture_counts = defaultdict(int)
    frame_count = 0
    latencies = []

    # Use VIDEO mode (synchronous, simpler for benchmarking)
    options = vision.GestureRecognizerOptions(
        base_options=python.BaseOptions(
            model_asset_path=model_path
        ),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    t_load = time.time()
    recognizer = vision.GestureRecognizer.create_from_options(options)
    print(f"  Model loaded in {time.time() - t_load:.1f}s")

    print(f"  Running for {duration}s ...")
    t_start = time.time()

    while time.time() - t_start < duration:
        ret, frame = cap.read()
        if not ret:
            continue

        t_infer = time.time()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int((time.time() - t_start) * 1000)

        try:
            result = recognizer.recognize_for_video(mp_image, timestamp_ms)
        except Exception as e:
            print(f"  [WARN] recognize failed: {e}")
            continue

        latency_ms = (time.time() - t_infer) * 1000
        latencies.append(latency_ms)
        frame_count += 1

        if result.gestures:
            for hand_gestures in result.gestures:
                top = hand_gestures[0]
                gesture_counts[top.category_name] += 1
                if top.category_name != "Unknown":
                    print(f"  [{timestamp_ms:>6d}ms] {top.category_name:15s} "
                          f"conf={top.score:.3f}  latency={latency_ms:.1f}ms")

    elapsed = time.time() - t_start
    cap.release()
    recognizer.close()

    # Summary
    fps = frame_count / elapsed if elapsed > 0 else 0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    p50_lat = sorted(latencies)[len(latencies) // 2] if latencies else 0

    print(f"\n  --- Results ---")
    print(f"  Frames: {frame_count}")
    print(f"  FPS: {fps:.1f}")
    print(f"  Latency avg: {avg_lat:.1f}ms  P50: {p50_lat:.1f}ms")
    print(f"  Gesture counts:")
    for g, c in sorted(gesture_counts.items(), key=lambda x: -x[1]):
        print(f"    {g:20s}: {c}")

    non_unknown = sum(c for g, c in gesture_counts.items() if g != "Unknown")
    print(f"  Non-Unknown detections: {non_unknown}")

    # Quality gate
    passed = fps >= min_fps
    print(f"  [{'PASS' if passed else 'FAIL'}] FPS {fps:.1f} "
          f"(gate: >= {min_fps})")
    return passed


def test_single_image(model_path: str) -> bool:
    """Test 2b: Recognize gesture from a synthetic test image."""
    print("\n=== Test 2b: Single Image Recognition ===")
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    import numpy as np

    try:
        options = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
        )
        recognizer = vision.GestureRecognizer.create_from_options(options)

        # Create a blank image (no hand = should return no gestures or Unknown)
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=blank)

        t0 = time.time()
        result = recognizer.recognize(mp_image)
        latency = (time.time() - t0) * 1000

        n_gestures = len(result.gestures) if result.gestures else 0
        print(f"  Blank image: {n_gestures} hands detected, latency={latency:.1f}ms")
        print(f"  [OK] recognize() works on this platform")

        recognizer.close()
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test MediaPipe Gesture Recognizer on Jetson")
    parser.add_argument("--duration", type=int, default=30, help="Live stream duration (seconds)")
    parser.add_argument("--device", type=int, default=-1,
                        help="Camera device index (-1 = skip live stream test)")
    parser.add_argument("--model-path", default=_DEFAULT_MODEL_PATH,
                        help=f"Path to gesture_recognizer.task (default: {_DEFAULT_MODEL_PATH})")
    parser.add_argument("--min-fps", type=float, default=10.0, help="Minimum FPS to pass (default: 10)")
    args = parser.parse_args()

    model_path = ensure_model(args.model_path)

    if not test_import():
        print("\n[ABORT] Import failed. Task API not available on this platform.")
        sys.exit(1)

    if not test_model_load(model_path):
        print("\n[ABORT] Model load failed.")
        sys.exit(1)

    if not test_single_image(model_path):
        print("\n[ABORT] Single image recognition failed.")
        sys.exit(1)

    if args.device >= 0:
        if not test_live_stream(args.duration, args.device, model_path, args.min_fps):
            print("\n[FAIL] Quality gate not met.")
            sys.exit(2)
    else:
        print("\n=== Skipping live stream test (no --device specified) ===")
        print("  To test with camera: --device 0")
        print("  D435 requires ROS2 realsense2_camera node (not direct OpenCV)")

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    main()
