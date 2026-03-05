#!/usr/bin/env python3
"""Quick Intel RealSense D435 sanity test.

What it checks:
1) RGB + Depth can stream at 640x480@30
2) Average FPS over test duration
3) Depth holes ratio in center ROI
4) Center-point flicker (peak-to-peak, mm)

Usage:
  python scripts/d435_quick_test.py

Optional args:
  --seconds 120 --width 640 --height 480 --fps 30
  --min-avg-fps 29 --max-hole-ratio 0.05 --max-flicker-mm 20
"""

from __future__ import annotations

import argparse
import importlib
import statistics
import time
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D435 quick test")
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)

    parser.add_argument("--min-avg-fps", type=float, default=29.0)
    parser.add_argument("--max-hole-ratio", type=float, default=0.05)
    parser.add_argument("--max-flicker-mm", type=float, default=20.0)
    parser.add_argument("--max-hole-ratio-filtered", type=float, default=0.10)
    parser.add_argument("--disable-filters", action="store_true")
    return parser.parse_args()


def print_device_info(device: Any, rs_module: Any) -> None:
    print("=== Device Info ===")
    rs = rs_module
    keys = [
        rs.camera_info.name,
        rs.camera_info.serial_number,
        rs.camera_info.firmware_version,
        rs.camera_info.usb_type_descriptor,
        rs.camera_info.product_line,
    ]
    for key in keys:
        if device.supports(key):
            print(f"{key.name}: {device.get_info(key)}")


def center_median_mm(depth_image: np.ndarray) -> float | None:
    h, w = depth_image.shape
    cy, cx = h // 2, w // 2
    patch = depth_image[max(0, cy - 2) : cy + 3, max(0, cx - 2) : cx + 3]
    valid = patch[patch > 0]
    if valid.size == 0:
        return None
    return float(np.median(valid))


def hole_ratio_center_roi(depth_image: np.ndarray) -> float:
    h, w = depth_image.shape
    y1, y2 = int(h * 0.1), int(h * 0.9)
    x1, x2 = int(w * 0.1), int(w * 0.9)
    roi = depth_image[y1:y2, x1:x2]
    return float(np.count_nonzero(roi == 0)) / float(roi.size)


def main() -> int:
    args = parse_args()

    print("[d435_quick_test] starting...", flush=True)
    rs = importlib.import_module("pyrealsense2")
    print("[d435_quick_test] pyrealsense2 imported", flush=True)

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(
        rs.stream.depth, args.width, args.height, rs.format.z16, args.fps
    )
    config.enable_stream(
        rs.stream.color, args.width, args.height, rs.format.bgr8, args.fps
    )

    print("[d435_quick_test] Starting D435 stream...", flush=True)
    profile = pipeline.start(config)
    print_device_info(profile.get_device(), rs)
    try:
        depth_sensor = profile.get_device().first_depth_sensor()
        if depth_sensor.supports(rs.option.emitter_enabled):
            depth_sensor.set_option(rs.option.emitter_enabled, 1)
            print("[d435_quick_test] emitter_enabled=1", flush=True)
        if depth_sensor.supports(rs.option.enable_auto_exposure):
            depth_sensor.set_option(rs.option.enable_auto_exposure, 1)
            print("[d435_quick_test] depth_auto_exposure=1", flush=True)
    except Exception as exc:
        print(f"[d435_quick_test] sensor option setup skipped: {exc}", flush=True)

    dec_filter = rs.decimation_filter()
    spat_filter = rs.spatial_filter()
    temp_filter = rs.temporal_filter()
    hole_filter = rs.hole_filling_filter()
    print("[d435_quick_test] Stream started", flush=True)

    for _ in range(30):
        pipeline.wait_for_frames(timeout_ms=5000)
    print("[d435_quick_test] Warm-up done", flush=True)

    t0 = time.time()
    frame_count = 0
    hole_ratios: list[float] = []
    hole_ratios_filtered: list[float] = []
    center_mm_values: list[float] = []

    try:
        while (time.time() - t0) < args.seconds:
            frames = pipeline.wait_for_frames(timeout_ms=5000)
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            if not depth_frame or not color_frame:
                continue

            filtered_depth_frame = depth_frame
            if not args.disable_filters:
                filtered_depth_frame = dec_filter.process(filtered_depth_frame)
                filtered_depth_frame = spat_filter.process(filtered_depth_frame)
                filtered_depth_frame = temp_filter.process(filtered_depth_frame)
                filtered_depth_frame = hole_filter.process(filtered_depth_frame)

            frame_count += 1
            depth_image = np.asanyarray(depth_frame.get_data())
            filtered_depth_image = np.asanyarray(filtered_depth_frame.get_data())

            hole_ratios.append(hole_ratio_center_roi(depth_image))
            hole_ratios_filtered.append(hole_ratio_center_roi(filtered_depth_image))
            center_mm = center_median_mm(depth_image)
            if center_mm is not None:
                center_mm_values.append(center_mm)
    finally:
        pipeline.stop()

    elapsed = time.time() - t0
    avg_fps = frame_count / elapsed if elapsed > 0 else 0.0
    avg_hole_ratio = statistics.fmean(hole_ratios) if hole_ratios else 1.0
    avg_hole_ratio_filtered = (
        statistics.fmean(hole_ratios_filtered) if hole_ratios_filtered else 1.0
    )

    if len(center_mm_values) >= 2:
        flicker_p2p_mm = max(center_mm_values) - min(center_mm_values)
    else:
        flicker_p2p_mm = float("inf")

    pass_fps = avg_fps >= args.min_avg_fps
    pass_hole = avg_hole_ratio <= args.max_hole_ratio
    pass_hole_filtered = avg_hole_ratio_filtered <= args.max_hole_ratio_filtered
    pass_flicker = flicker_p2p_mm <= args.max_flicker_mm
    overall = pass_fps and pass_hole_filtered and pass_flicker

    print("\n=== Result ===")
    print(f"Duration: {args.seconds}s")
    print(f"Frames: {frame_count}")
    print(f"Avg FPS: {avg_fps:.2f}")
    print(f"Avg hole ratio RAW (center 80%): {avg_hole_ratio * 100:.2f}%")
    print(f"Avg hole ratio FILTERED (center 80%): {avg_hole_ratio_filtered * 100:.2f}%")
    if np.isfinite(flicker_p2p_mm):
        print(f"Center flicker p2p: {flicker_p2p_mm:.2f} mm")
    else:
        print("Center flicker p2p: N/A (insufficient valid depth)")

    print("\n=== PASS/FAIL ===")
    print(f"FPS >= {args.min_avg_fps:.2f}: {'PASS' if pass_fps else 'FAIL'}")
    print(
        f"Hole RAW <= {args.max_hole_ratio * 100:.2f}%: {'PASS' if pass_hole else 'FAIL'}"
    )
    print(
        "Hole FILTERED <= "
        f"{args.max_hole_ratio_filtered * 100:.2f}%: "
        f"{'PASS' if pass_hole_filtered else 'FAIL'}"
    )
    print(
        f"Flicker <= {args.max_flicker_mm:.2f} mm: {'PASS' if pass_flicker else 'FAIL'}"
    )
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")

    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
