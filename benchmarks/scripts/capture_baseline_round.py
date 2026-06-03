#!/usr/bin/env python3
"""非互動 baseline round capture（HITL 遠端驅動 / 操作員都可用）。

複用 benchmarks 既有、已測的純邏輯（`evaluate_round` / `evaluate_face_round` /
`normalize_*` / `filter_*` / `enrich_record`），以**固定時間窗**收集 perception topic，
產一筆正規 `baseline_result.jsonl` record。

與互動式 observer（`perception_baseline_observer` / `face_baseline_observer`）的差異：
observer 用 operator 按 Enter 切窗（在 Jetson 終端機前操作最順）；本工具用固定 `--window`
秒數切窗，適合**遠端 SSH 驅動**或腳本化（不需 stdin 互動）。兩者產出同款 record schema。

rclpy 只在 run_*() 內 lazy import（module 載入維持 CI-safe，無 top-level rclpy）。

用法：
  # 人臉（吃 /state/perception/face 連續流）
  python3 benchmarks/scripts/capture_baseline_round.py face \\
      --capability face.recognition --scenario-id roy_1m_01 \\
      --expected roy --kind positive --distance 1.0 --window 8 \\
      --out artifacts/baseline/baseline_result.jsonl

  # 手勢/物體（吃 /event/gesture_detected + /event/object_detected）
  python3 benchmarks/scripts/capture_baseline_round.py percep \\
      --capability gesture.wave --scenario-id wave_1m_01 \\
      --expected wave --kind positive --window 12 \\
      --out artifacts/baseline/baseline_result.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.core import face_baseline_observer as F  # noqa: E402
from benchmarks.core import perception_baseline_observer as P  # noqa: E402


def git_commit() -> str | None:
    """回傳 repo HEAD 完整 SHA；取不到（如 rsync 後 Jetson git 壞）回 None。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def append_record(out_path: str, record: dict) -> None:
    out = Path(out_path)
    if out.parent != Path("."):
        os.makedirs(out.parent, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _spin_collect(node, window_s: float):
    """背景 spin node，主 thread 等固定窗，回傳 (window_start, window_end)。"""
    import rclpy

    t = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    t.start()
    window_start = time.time()
    time.sleep(window_s)
    window_end = time.time()
    return window_start, window_end


def run_face(args) -> dict:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    snaps: list = []
    lock = threading.Lock()

    rclpy.init()
    node = Node("capture_baseline_face")

    def cb(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        with lock:
            snaps.append(F.parse_face_state(data))

    node.create_subscription(String, args.topic, cb, 10)
    window_start, window_end = _spin_collect(node, args.window)
    with lock:
        captured = list(snaps)
    node.destroy_node()
    rclpy.shutdown()

    in_window = F.filter_face_window(captured, window_start, window_end)
    meta = F.FaceRoundMeta(
        capability_id=args.capability, scenario_id=args.scenario_id,
        expected_label=args.expected, distance_m=args.distance,
        window_start_ts=window_start, scenario_kind=args.kind,
    )
    record = F.enrich_record(F.evaluate_face_round(meta, in_window), args.run_id, git_commit())
    print("snapshots_in_window =", len(in_window))
    return record


def run_percep(args) -> dict:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    obs: list = []
    lock = threading.Lock()

    rclpy.init()
    node = Node("capture_baseline_percep")

    def cb_gesture(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        with lock:
            obs.extend(P.normalize_gesture_event(data))

    def cb_object(msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        with lock:
            obs.extend(P.normalize_object_event(data))

    node.create_subscription(String, args.gesture_topic, cb_gesture, 10)
    node.create_subscription(String, args.object_topic, cb_object, 10)
    window_start, window_end = _spin_collect(node, args.window)
    with lock:
        captured = list(obs)
    node.destroy_node()
    rclpy.shutdown()

    in_window = P.filter_window(captured, window_start, window_end)
    meta = P.RoundMeta(
        capability_id=args.capability, scenario_id=args.scenario_id,
        expected_label=args.expected, distance_m=args.distance,
        window_start_ts=window_start, scenario_kind=args.kind,
    )
    record = P.enrich_record(P.evaluate_round(meta, in_window), args.run_id, git_commit())
    print("observations_in_window =", len(in_window), "labels =", [o[0] for o in in_window][:20])
    return record


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["face", "percep"])
    ap.add_argument("--capability", required=True)
    ap.add_argument("--scenario-id", required=True)
    ap.add_argument("--expected", required=True, help="positive 用真名/標籤；idle 用 unknown/none")
    ap.add_argument("--kind", default="positive", choices=["positive", "idle"])
    ap.add_argument("--distance", type=float, default=None)
    ap.add_argument("--window", type=float, default=8.0, help="固定收集窗（秒）")
    ap.add_argument("--out", default="artifacts/baseline/baseline_result.jsonl")
    ap.add_argument("--run-id", default="hitl")
    ap.add_argument("--topic", default="/state/perception/face", help="face mode 的 state topic")
    ap.add_argument("--gesture-topic", default="/event/gesture_detected")
    ap.add_argument("--object-topic", default="/event/object_detected")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    record = run_face(args) if args.mode == "face" else run_percep(args)
    append_record(args.out, record)
    print("RECORD:", json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
