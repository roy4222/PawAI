#!/usr/bin/env python3
"""LiDAR 前方扇區 debug 工具 — 一鍵看 reactive_stop 為什麼擋。

訂閱 /scan_rplidar，印出 Go2 物理前方 ±15° / ±20° / ±30° 三段扇區的最近距離，
以及全 ±30° 內最近點的角度（相對前方，度）。現場用來快速分辨：

  「正前方真的有障礙」 vs 「側前方家具被掃進 safety cone」

對齊 reactive_stop_node 的同款幾何（go2_robot_sdk.lidar_geometry.compute_front_min_distance
+ front_offset_rad）。v8 mount 是 LiDAR 反裝 yaw=π，所以 --front-offset-rad 預設 π；
改 mount 角度時要一起改（與 reactive_stop_node 的 front_offset_rad 保持一致）。

用法：
    python3 scripts/lidar_front_sector.py            # 2 Hz 連續
    python3 scripts/lidar_front_sector.py --once     # 收到第一筆 scan 印一次就退出
    python3 scripts/lidar_front_sector.py --front-offset-rad 0   # 傳統 mount（laser 0°=前方）
"""
import argparse
import math
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan

from go2_robot_sdk.lidar_geometry import compute_front_min_distance

QOS_SCAN = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
SECTORS_DEG = (15.0, 20.0, 30.0)


def nearest_point(ranges, angle_min, angle_increment, half_rad,
                  range_min, range_max, front_offset_rad):
    """±half_rad（front_offset 補正後）內最近有效點 → (min_dist, rel_angle_rad)。

    無有效點回 (inf, nan)。rel_angle 為相對 Go2 前方的角度（+ 左 / - 右取決於 frame）。
    """
    best_d = float("inf")
    best_a = float("nan")
    for i, r in enumerate(ranges):
        if not math.isfinite(r) or r < range_min or r > range_max:
            continue
        angle = angle_min + i * angle_increment
        rel = math.atan2(math.sin(angle - front_offset_rad),
                         math.cos(angle - front_offset_rad))
        if abs(rel) > half_rad:
            continue
        if r < best_d:
            best_d = r
            best_a = rel
    return best_d, best_a


def _fmt(d):
    return f"{d:5.2f}m" if math.isfinite(d) else "  inf "


class FrontSectorNode(Node):
    def __init__(self, args):
        super().__init__("lidar_front_sector")
        self._args = args
        self._latest = None
        self.create_subscription(LaserScan, args.scan_topic, self._on_scan, QOS_SCAN)
        if not args.once:
            self.create_timer(1.0 / args.rate, self._tick)

    def _on_scan(self, msg):
        self._latest = msg

    def _tick(self):
        if self._latest is not None:
            self.report()

    def report(self):
        msg = self._latest
        if msg is None:
            return
        ranges = list(msg.ranges)
        a = self._args
        parts = []
        for deg in SECTORS_DEG:
            half = math.radians(deg)
            d = compute_front_min_distance(
                ranges, msg.angle_min, msg.angle_increment, half,
                a.range_min, a.range_max, a.front_offset_rad,
            )
            parts.append(f"±{deg:>4.0f}°={_fmt(d)}")
        nd, na = nearest_point(
            ranges, msg.angle_min, msg.angle_increment,
            math.radians(max(SECTORS_DEG)),
            a.range_min, a.range_max, a.front_offset_rad,
        )
        na_str = f"{math.degrees(na):+6.1f}°" if math.isfinite(na) else "   n/a"
        print(f"front  {'  '.join(parts)}   nearest(±30°)={_fmt(nd)} @ {na_str}", flush=True)


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scan-topic", default="/scan_rplidar")
    p.add_argument("--front-offset-rad", type=float, default=math.pi,
                   help="laser frame → Go2 前方 offset；v8 反裝 mount=π（預設），傳統 mount=0")
    p.add_argument("--range-min", type=float, default=0.10)
    p.add_argument("--range-max", type=float, default=8.0)
    p.add_argument("--rate", type=float, default=2.0, help="連續模式列印頻率 (Hz)")
    p.add_argument("--once", action="store_true", help="收到第一筆 scan 印一次就退出")
    p.add_argument("--timeout", type=float, default=10.0, help="--once 模式等 scan 的上限 (秒)")
    args = p.parse_args()

    rclpy.init()
    node = FrontSectorNode(args)
    print(f"# lidar_front_sector: topic={args.scan_topic} "
          f"front_offset={math.degrees(args.front_offset_rad):+.0f}° "
          f"range=[{args.range_min},{args.range_max}]m — waiting for scan...",
          file=sys.stderr, flush=True)
    try:
        if args.once:
            deadline = time.monotonic() + args.timeout
            while rclpy.ok() and node._latest is None and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.2)
            if node._latest is not None:
                node.report()
            else:
                print("no scan received within timeout", file=sys.stderr)
        else:
            rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
