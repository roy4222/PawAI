#!/usr/bin/env python3
"""Object 辨識矩陣量測 harness — 逐 cell × N trials 收 /event/object_detected → CSV。

一個 cell = (object, distance, light, angle)。每 trial = 固定窗（--window 秒）內看 target
class 有沒有被偵測到。跑完 N trials 聚合成一筆 row：成功率 / 平均 confidence / bbox /
誤認 / PASS|DEGRADED|FAIL，append 到 CSV（檔不存在自動寫 header）。

只訂 /event/object_detected（不碰 gesture，避免 6/4 footgun 的 gesture/object 跨流污染）。
判定 gate 與純邏輯見 benchmarks/core/object_matrix.py（有 unit test）。

用法（互動：每 trial 擺好場景按 Enter）：
    python3 scripts/obj_matrix_cap.py --object chair --distance 1.0 --light normal --angle front
    python3 scripts/obj_matrix_cap.py --object cup --distance 1.5 --light backlit --angle side \\
        --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv

自動模式（不等 Enter，trial 間固定間隔）：
    python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light normal --auto

需先啟 object_perception（/event/object_detected 活著）。
"""
import argparse
import csv
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.core.object_matrix import (  # noqa: E402
    CSV_HEADER, csv_row, other_labels, summarize_cell, summarize_trial,
)

OBJECT_EVENT_COOLDOWN_S = 5.0


def validate_timing(window: float, gap: float, auto: bool,
                    allow_short_window: bool = False) -> list[str]:
    """Validate capture windows against object_perception's per-class cooldown."""
    warnings: list[str] = []
    if window < OBJECT_EVENT_COOLDOWN_S:
        msg = f"window {window}s is below object cooldown {OBJECT_EVENT_COOLDOWN_S}s"
        if allow_short_window:
            warnings.append(msg)
        else:
            raise ValueError(msg)
    if auto and gap < OBJECT_EVENT_COOLDOWN_S:
        msg = f"gap {gap}s is below object cooldown {OBJECT_EVENT_COOLDOWN_S}s"
        if allow_short_window:
            warnings.append(msg)
        else:
            raise ValueError(msg)
    return warnings


def _capture_trials(args, events, lock):
    """跑 args.trials 個 trial 窗，回傳 list[TrialResult]。每窗清空 → sleep → snapshot。

    Ctrl-C 中斷時回傳已收的部分 trials（讓操作員提早結束仍能聚合）。
    """
    trials = []
    try:
        for i in range(1, args.trials + 1):
            if args.auto:
                print(f"  trial {i}/{args.trials}: capturing {args.window}s ...", flush=True)
            else:
                input(f"  trial {i}/{args.trials}: 擺好場景，按 Enter 開始收 {args.window}s 窗")
            with lock:
                events.clear()
            time.sleep(args.window)
            with lock:
                captured = list(events)
            tr = summarize_trial(captured, args.object, args.conf_min)
            trials.append(tr)
            print(f"    -> detected={tr.detected} conf={tr.confidence} bbox={tr.bbox} "
                  f"(events_in_window={len(captured)})", flush=True)
            if args.auto and i < args.trials:
                time.sleep(args.gap)
    except KeyboardInterrupt:
        print("\n中斷；用已收的 trials 聚合。")
    return trials


def _write_csv(out_path, row):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    with out.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(CSV_HEADER)
        writer.writerow(csv_row(row))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--object", required=True, help="target COCO class_name, e.g. chair/laptop/cup")
    p.add_argument("--distance", type=float, required=True, help="declared distance (m)")
    p.add_argument("--light", required=True, help="light condition, e.g. normal/backlit/side/dim")
    p.add_argument("--angle", default="front", help="viewing angle, e.g. front/side/45")
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--window", type=float, default=6.0, help="每 trial 收集窗 (秒)")
    p.add_argument("--conf-min", type=float, default=0.0,
                   help="harness 端額外信心門檻（node 預設已 0.5 過濾，預設 0=不再過濾）")
    p.add_argument("--object-topic", default="/event/object_detected")
    p.add_argument("--auto", action="store_true", help="不等 Enter，trial 間固定間隔自動跑")
    p.add_argument("--gap", type=float, default=6.0, help="--auto 模式 trial 間隔 (秒)")
    p.add_argument("--out", default="artifacts/object_matrix/object_matrix.csv")
    p.add_argument("--notes", default="")
    p.add_argument("--allow-short-window", action="store_true",
                   help="allow window/gap below object cooldown for debugging")
    args = p.parse_args(argv)

    try:
        for warning in validate_timing(
            args.window, args.gap, args.auto, args.allow_short_window
        ):
            print(f"warning: {warning}", file=sys.stderr)
    except ValueError as exc:
        print(f"timing error: {exc}", file=sys.stderr)
        return 2

    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    events: list = []
    all_events: list = []
    lock = threading.Lock()

    rclpy.init()
    node = Node("obj_matrix_cap")

    def cb(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        with lock:
            events.append(data)
            all_events.append(data)

    node.create_subscription(String, args.object_topic, cb, 10)
    spin = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin.start()

    print(f"== object matrix: {args.object} @ {args.distance}m / {args.light} / {args.angle} "
          f"— {args.trials} trials × {args.window}s ==")
    try:
        trials = _capture_trials(args, events, lock)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        spin.join(timeout=2.0)

    if not trials:
        print("no trials captured", file=sys.stderr)
        return 1

    cell = summarize_cell(trials)
    with lock:
        misclass = other_labels(all_events, args.object)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "object": args.object,
        "distance_m": args.distance,
        "light": args.light,
        "angle": args.angle,
        "misclass": misclass,
        "notes": args.notes,
        **cell,
    }
    out = _write_csv(args.out, row)

    print(f"\nCELL: {cell['verdict']}{' / low_conf' if cell['low_conf'] else ''} "
          f"success={cell['success']}/{cell['trials']} rate={cell['success_rate']} "
          f"avg_conf={cell['avg_confidence']} misclass={misclass}")
    print(f"appended -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
