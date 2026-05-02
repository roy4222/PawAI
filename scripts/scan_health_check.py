#!/usr/bin/env python3
"""scan_health_check.py — RPLIDAR /scan_rplidar 健康度驗證

依據 docs/navigation/research/lidar-dev/2026-04-27-lidar-dev-roadmap.md Phase 2.2 規格：

PHANTOM ALERT (fail gate) — 必須四項全中才 FAIL:
  a. 連續 ≥ 10° 範圍角度
  b. 該範圍內 range 幾乎固定 (max-min < 50mm)
  c. 該範圍內 jitter < 5mm
  d. N 樣本中 ≥ 67% 出現同一角度段 phantom = stable
  intensity 只當輔助欄位列印，不作為必要條件

SYMMETRY WARN (warning only):
  左右 ±θ range 差異 > 50% 列印 WARN（不 fail）

Usage:
  python3 scripts/scan_health_check.py [--duration 5] [--csv /tmp/scan_health.csv]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from collections import defaultdict
from typing import List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan


PHANTOM_ARC_MIN_DEG = 10.0
PHANTOM_RANGE_FIXED_MM = 50.0
PHANTOM_JITTER_MAX_MM = 5.0
PHANTOM_STABLE_RATIO = 0.67
SYMMETRY_DIFF_RATIO = 0.50
ANGLE_BIN_DEG = 5.0


class ScanCollector(Node):
    def __init__(self, target_samples: int):
        super().__init__("scan_health_check")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.sub = self.create_subscription(
            LaserScan, "/scan_rplidar", self._cb, qos
        )
        self.scans: List[LaserScan] = []
        self.target = target_samples

    def _cb(self, msg: LaserScan) -> None:
        if len(self.scans) < self.target:
            self.scans.append(msg)


def collect_scans(duration_sec: float, target_samples: int) -> List[LaserScan]:
    rclpy.init()
    node = ScanCollector(target_samples)
    deadline = time.time() + duration_sec + 5.0
    try:
        while rclpy.ok() and len(node.scans) < target_samples and time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        scans = list(node.scans)
        node.destroy_node()
        rclpy.shutdown()
    return scans


def bin_per_scan(scan: LaserScan, bin_deg: float = ANGLE_BIN_DEG) -> dict:
    """Return dict[deg_bin] = (range_m, intensity)."""
    out = {}
    n = len(scan.ranges)
    for i in range(n):
        ang = scan.angle_min + i * scan.angle_increment
        deg = math.degrees(ang) % 360.0
        bin_key = int((deg // bin_deg) * bin_deg)
        r = scan.ranges[i]
        if not math.isfinite(r) or r <= 0.0:
            continue
        if r < scan.range_min or r > scan.range_max:
            continue
        intensity = scan.intensities[i] if i < len(scan.intensities) else 0.0
        if bin_key not in out or r < out[bin_key][0]:
            out[bin_key] = (r, intensity)
    return out


def aggregate(scans: List[LaserScan]) -> dict:
    """Return dict[deg_bin] = {ranges:[m..], intensities:[..], count:int}."""
    agg = defaultdict(lambda: {"ranges": [], "intensities": []})
    for scan in scans:
        binned = bin_per_scan(scan)
        for deg, (r, it) in binned.items():
            agg[deg]["ranges"].append(r)
            agg[deg]["intensities"].append(it)
    return agg


def detect_phantom_arcs(scans: List[LaserScan]) -> List[Tuple[float, float, dict]]:
    """掃過 30 樣本，找出每樣本內符合 a+b+c 的弧段，再篩 d (stable across samples)。

    回傳: [(start_deg, end_deg, stats), ...] 通過全部四條件的弧段
    """
    n_total = len(scans)
    if n_total == 0:
        return []
    threshold = max(1, int(n_total * PHANTOM_STABLE_RATIO))

    per_sample_arcs: List[set] = []
    for scan in scans:
        binned = bin_per_scan(scan)
        sorted_degs = sorted(binned.keys())
        arcs_in_sample = set()

        i = 0
        while i < len(sorted_degs):
            j = i
            while (
                j + 1 < len(sorted_degs)
                and abs(sorted_degs[j + 1] - sorted_degs[j]) <= ANGLE_BIN_DEG + 0.1
            ):
                j += 1
            seg = sorted_degs[i : j + 1]
            arc_deg = (seg[-1] - seg[0]) + ANGLE_BIN_DEG
            if arc_deg >= PHANTOM_ARC_MIN_DEG:
                ranges_seg = [binned[d][0] for d in seg]
                rng_span_mm = (max(ranges_seg) - min(ranges_seg)) * 1000.0
                if rng_span_mm < PHANTOM_RANGE_FIXED_MM:
                    arcs_in_sample.add((seg[0], seg[-1]))
            i = j + 1

        per_sample_arcs.append(arcs_in_sample)

    arc_counts: dict = defaultdict(int)
    for arcs in per_sample_arcs:
        for arc in arcs:
            arc_counts[arc] += 1

    stable_arcs = [(s, e) for (s, e), c in arc_counts.items() if c >= threshold]

    agg = aggregate(scans)
    results = []
    for (s, e) in stable_arcs:
        deg_bins = [d for d in agg if s <= d <= e]
        all_ranges = []
        for d in deg_bins:
            all_ranges.extend(agg[d]["ranges"])
        if not all_ranges:
            continue
        per_bin_jitter_mm = []
        for d in deg_bins:
            rs = agg[d]["ranges"]
            if len(rs) >= 2:
                per_bin_jitter_mm.append((max(rs) - min(rs)) * 1000.0)
        if not per_bin_jitter_mm:
            continue
        max_jitter = max(per_bin_jitter_mm)
        if max_jitter >= PHANTOM_JITTER_MAX_MM:
            continue
        stats = {
            "stable_count": arc_counts[(s, e)],
            "n_samples": n_total,
            "range_min_m": min(all_ranges),
            "range_max_m": max(all_ranges),
            "max_jitter_mm": max_jitter,
        }
        results.append((s, e, stats))
    return results


def detect_symmetry_warn(agg: dict) -> List[Tuple[float, float, float]]:
    """左右 ±θ range 差異 > 50% 列印 WARN."""
    warns = []
    for deg in range(int(ANGLE_BIN_DEG), 180, int(ANGLE_BIN_DEG)):
        left = agg.get(float(deg))
        right = agg.get(float((360 - deg) % 360))
        if not left or not right or not left["ranges"] or not right["ranges"]:
            continue
        l_avg = sum(left["ranges"]) / len(left["ranges"])
        r_avg = sum(right["ranges"]) / len(right["ranges"])
        if l_avg <= 0 or r_avg <= 0:
            continue
        diff = abs(l_avg - r_avg) / max(l_avg, r_avg)
        if diff > SYMMETRY_DIFF_RATIO:
            warns.append((float(deg), l_avg, r_avg))
    return warns


def write_csv(path: str, agg: dict) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "deg",
                "n_samples",
                "range_avg_m",
                "range_min_m",
                "range_max_m",
                "jitter_mm",
                "intensity_avg",
            ]
        )
        for deg in sorted(agg.keys()):
            rs = agg[deg]["ranges"]
            its = agg[deg]["intensities"]
            if not rs:
                continue
            w.writerow(
                [
                    f"{deg:.1f}",
                    len(rs),
                    f"{sum(rs)/len(rs):.4f}",
                    f"{min(rs):.4f}",
                    f"{max(rs):.4f}",
                    f"{(max(rs)-min(rs))*1000:.2f}",
                    f"{(sum(its)/len(its)) if its else 0.0:.1f}",
                ]
            )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=5.0, help="收集秒數")
    p.add_argument("--samples", type=int, default=30, help="目標樣本數")
    p.add_argument("--csv", default="/tmp/scan_health.csv", help="輸出 CSV 路徑")
    args = p.parse_args()

    print(f"[scan_health] 收集 ≥ {args.samples} 個 /scan_rplidar 訊息（最多 {args.duration + 5:.0f}s）...")
    scans = collect_scans(args.duration, args.samples)
    if not scans:
        print("[ERROR] 沒收到任何 scan — 確認 sllidar 已啟動且 /scan_rplidar 有資料")
        return 2
    print(f"[scan_health] 收到 {len(scans)} 樣本")

    agg = aggregate(scans)
    write_csv(args.csv, agg)
    print(f"[scan_health] CSV 已寫入 {args.csv}")

    print("\n=== 360° 摘要（每 5° 一筆）===")
    print(f"{'deg':>5} {'n':>3} {'r_avg(m)':>9} {'jit(mm)':>8} {'int_avg':>7}")
    for deg in sorted(agg.keys()):
        rs = agg[deg]["ranges"]
        its = agg[deg]["intensities"]
        if not rs:
            continue
        r_avg = sum(rs) / len(rs)
        jit = (max(rs) - min(rs)) * 1000.0
        it_avg = (sum(its) / len(its)) if its else 0.0
        print(f"{deg:5.1f} {len(rs):3d} {r_avg:9.4f} {jit:8.2f} {it_avg:7.1f}")

    print("\n=== PHANTOM 檢查（必須四項全中才 FAIL）===")
    phantoms = detect_phantom_arcs(scans)
    if phantoms:
        print(f"[FAIL] 偵測到 {len(phantoms)} 個 phantom 弧段：")
        for (s, e, stats) in phantoms:
            print(
                f"  {s:.0f}°-{e + ANGLE_BIN_DEG:.0f}° "
                f"range={stats['range_min_m']:.3f}-{stats['range_max_m']:.3f}m "
                f"jitter={stats['max_jitter_mm']:.2f}mm "
                f"stable={stats['stable_count']}/{stats['n_samples']}"
            )
        phantom_fail = True
    else:
        print("[PASS] 無 phantom 弧段")
        phantom_fail = False

    print("\n=== SYMMETRY 檢查（warning only）===")
    warns = detect_symmetry_warn(agg)
    if warns:
        print(f"[WARN] {len(warns)} 個角度對稱差異 > {SYMMETRY_DIFF_RATIO*100:.0f}%（房間不對稱很正常）：")
        for (deg, l_avg, r_avg) in warns[:8]:
            print(f"  ±{deg:.0f}°  L={l_avg:.3f}m R={r_avg:.3f}m")
    else:
        print("[OK] 無顯著對稱差異")

    print("\n=== 結論 ===")
    if phantom_fail:
        print("FAIL — 拆 mount 修：檢查線材是否纏繞、雷達是否被自身遮擋")
        return 1
    print("PASS — Phase 2 通過，可進 Phase 3 SLAM 重建圖")
    return 0


if __name__ == "__main__":
    sys.exit(main())
