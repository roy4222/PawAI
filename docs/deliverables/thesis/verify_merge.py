#!/usr/bin/env python3
"""
驗證合併檔是否包含所有原始檔的每一行（非空白行）。
"""
import os
import sys

BASE = "/home/roy422/newLife/elder_and_dog/docs/deliverables/thesis/背景知識"
MERGED = "/home/roy422/newLife/elder_and_dog/docs/deliverables/thesis/Ch4-背景知識-合併版.md"

FILES = [
    "4-1-ROS2.md",
    "4-2-Unitree-Go2.md",
    "4-3-MediaPipe-Gesture.md",
    "4-4-MediaPipe-Pose.md",
    "4-5-YuNet-SFace.md",
    "4-6-Speech.md",
    "4-7-YOLO26.md",
    "4-8-Navigation.md",
    "4-9-Jetson.md",
    "4-10-D435.md",
]

# 讀取合併檔的所有行（strip 後），建成 multiset 用 list 計數
with open(MERGED, "r", encoding="utf-8") as f:
    merged_lines = [line.rstrip("\n") for line in f.readlines()]

# 建立合併檔行的查找集合（保留重複計數用 dict）
from collections import Counter
merged_counter = Counter(merged_lines)

total_missing = 0
print(f"{'檔案':<30} {'原始非空行數':>12} {'全部找到':>10} {'缺失行數':>10}")
print("-" * 70)

all_missing = []

for fname in FILES:
    fpath = os.path.join(BASE, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        raw_lines = [line.rstrip("\n") for line in f.readlines()]

    # 只檢查非空白行
    non_empty = [l for l in raw_lines if l.strip()]

    missing = []
    for line in non_empty:
        if line not in merged_counter or merged_counter[line] == 0:
            missing.append(line)
        # 不做計數扣減，允許相同行在多個原始檔中都存在於合併檔

    status = "OK" if not missing else "FAIL"
    print(f"{fname:<30} {len(non_empty):>12} {status:>10} {len(missing):>10}")

    if missing:
        total_missing += len(missing)
        for line in missing:
            all_missing.append((fname, line))

print("-" * 70)

if all_missing:
    print(f"\n[FAIL] 共 {total_missing} 行缺失：")
    for fname, line in all_missing:
        print(f"  [{fname}] {repr(line)}")
    sys.exit(1)
else:
    print(f"\n[PASS] 所有原始非空白行均存在於合併檔中，0 缺失。")
    sys.exit(0)
