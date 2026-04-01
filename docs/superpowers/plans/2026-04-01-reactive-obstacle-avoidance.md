# Reactive Obstacle Avoidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** D435 depth → 前方 ROI 障礙物偵測 → executive Damp 停車。反應式安全停車，不做導航。

**Architecture:** 純 Python/numpy `ObstacleDetector` 核心邏輯（無 ROS2 依賴，100% 可測試）+ `obstacle_avoidance_node` ROS2 包裝。放在 `vision_perception` package 內。Executive 已支援 OBSTACLE_STOP，不需修改。

**Tech Stack:** Python 3.10, numpy, rclpy, sensor_msgs, std_msgs, cv_bridge

**Spec:** `docs/superpowers/specs/2026-04-01-reactive-obstacle-avoidance-design.md`

---

## File Structure

### New Files
```
vision_perception/vision_perception/obstacle_detector.py    # 純邏輯 (~60 行)
vision_perception/vision_perception/obstacle_avoidance_node.py  # ROS2 node (~80 行)
vision_perception/test/test_obstacle_detector.py            # 7 unit tests
vision_perception/launch/obstacle_avoidance.launch.py       # Launch config
```

### Modified Files
```
vision_perception/setup.py   # 加 console_scripts entry
```

---

## Task 1: ObstacleDetector — TDD Tests (RED)

**Files:**
- Create: `vision_perception/test/test_obstacle_detector.py`

- [ ] **Step 1: Write all 7 test cases**

```python
"""Tests for ObstacleDetector — pure Python/numpy, no ROS2."""
import numpy as np
import pytest

from vision_perception.obstacle_detector import ObstacleDetector, ObstacleResult


class TestObstacleDetectorDefaults:
    """Tests with default parameters (threshold=0.8m, ratio_trigger=0.15)."""

    def setup_method(self):
        self.detector = ObstacleDetector()

    def test_no_obstacle_all_far(self):
        """All pixels at 2.0m → clear, no obstacle."""
        depth = np.full((240, 424), 2.0, dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.is_obstacle is False
        assert result.zone == "clear"
        assert result.distance_min > 1.0

    def test_close_obstacle_triggers(self):
        """Center ROI filled with 0.3m → danger, obstacle detected."""
        depth = np.full((240, 424), 2.0, dtype=np.float32)
        # Fill ROI region (40%-80% height, 20%-80% width) with close obstacle
        depth[96:192, 85:339] = 0.3
        result = self.detector.detect(depth)
        assert result.is_obstacle is True
        assert result.zone == "danger"
        assert result.distance_min < 0.5

    def test_partial_obstacle_below_trigger(self):
        """Only 5% of ROI close → below 15% trigger, no obstacle."""
        depth = np.full((240, 424), 2.0, dtype=np.float32)
        # Fill small portion of ROI
        depth[96:101, 85:100] = 0.3  # ~5 rows x 15 cols = tiny fraction
        result = self.detector.detect(depth)
        assert result.is_obstacle is False

    def test_warning_zone(self):
        """ROI at 1.0m with enough ratio → warning (between threshold and warning_m)."""
        depth = np.full((240, 424), 1.0, dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.zone == "warning"
        assert result.is_obstacle is False  # warning doesn't trigger obstacle

    def test_all_invalid_depth(self):
        """All zeros (invalid depth) → clear, no obstacle."""
        depth = np.zeros((240, 424), dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.is_obstacle is False
        assert result.zone == "clear"

    def test_mixed_valid_invalid(self):
        """50% zeros + 50% close → only valid pixels counted for ratio."""
        depth = np.zeros((240, 424), dtype=np.float32)
        # Fill right half of ROI with close obstacle
        depth[96:192, 212:339] = 0.3
        result = self.detector.detect(depth)
        # Should still detect because valid pixels have high obstacle ratio
        assert result.is_obstacle is True
        assert result.distance_min < 0.5


class TestObstacleDetectorCustomParams:
    """Tests with custom parameters."""

    def test_custom_threshold(self):
        """Custom threshold=1.0 → 0.9m triggers obstacle."""
        detector = ObstacleDetector(threshold_m=1.0)
        depth = np.full((240, 424), 0.9, dtype=np.float32)
        result = detector.detect(depth)
        assert result.is_obstacle is True
        assert result.zone == "danger"
```

- [ ] **Step 2: Run tests to verify they FAIL**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'vision_perception.obstacle_detector'`

- [ ] **Step 3: Commit RED tests**

```bash
git add vision_perception/test/test_obstacle_detector.py
git commit -m "test(vision): add obstacle detector tests — RED (TDD)"
```

---

## Task 2: ObstacleDetector — Implementation (GREEN)

**Files:**
- Create: `vision_perception/vision_perception/obstacle_detector.py`

- [ ] **Step 1: Implement ObstacleDetector**

```python
"""Reactive obstacle detector — pure Python/numpy, no ROS2 dependency.

Extracts a center-band ROI from D435 depth frame, counts pixels
closer than threshold, and returns an ObstacleResult.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class ObstacleResult:
    """Result of a single obstacle detection frame."""

    is_obstacle: bool
    distance_min: float       # meters (inf if no valid pixels)
    obstacle_ratio: float     # 0.0~1.0
    zone: str                 # "clear" / "warning" / "danger"


class ObstacleDetector:
    """Stateless depth-ROI obstacle detector.

    Parameters are constructor args so the class stays pure and testable.
    """

    def __init__(
        self,
        threshold_m: float = 0.8,
        warning_m: float = 1.2,
        max_range_m: float = 3.0,
        roi_top_ratio: float = 0.4,
        roi_bottom_ratio: float = 0.8,
        roi_left_ratio: float = 0.2,
        roi_right_ratio: float = 0.8,
        obstacle_ratio_trigger: float = 0.15,
    ):
        self.threshold_m = threshold_m
        self.warning_m = warning_m
        self.max_range_m = max_range_m
        self.roi_top = roi_top_ratio
        self.roi_bottom = roi_bottom_ratio
        self.roi_left = roi_left_ratio
        self.roi_right = roi_right_ratio
        self.ratio_trigger = obstacle_ratio_trigger

    def detect(self, depth: np.ndarray) -> ObstacleResult:
        """Analyze a depth frame and return obstacle status.

        Args:
            depth: (H, W) float32 array, depth in meters.
                   0.0 = invalid / no reading.
        """
        h, w = depth.shape[:2]
        roi = depth[
            int(h * self.roi_top): int(h * self.roi_bottom),
            int(w * self.roi_left): int(w * self.roi_right),
        ]

        # Filter valid pixels (non-zero and within max range)
        valid_mask = (roi > 0) & (roi <= self.max_range_m)
        valid = roi[valid_mask]

        if valid.size == 0:
            return ObstacleResult(
                is_obstacle=False, distance_min=float("inf"),
                obstacle_ratio=0.0, zone="clear",
            )

        distance_min = float(np.min(valid))
        close_count = int(np.sum(valid < self.threshold_m))
        obstacle_ratio = close_count / valid.size

        if obstacle_ratio >= self.ratio_trigger and distance_min < self.threshold_m:
            zone = "danger"
        elif obstacle_ratio >= self.ratio_trigger and distance_min < self.warning_m:
            zone = "warning"
        else:
            zone = "clear"

        is_obstacle = zone == "danger"

        return ObstacleResult(
            is_obstacle=is_obstacle,
            distance_min=distance_min,
            obstacle_ratio=obstacle_ratio,
            zone=zone,
        )
```

- [ ] **Step 2: Run tests to verify they PASS**

```bash
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

Expected: 7 passed

- [ ] **Step 3: Commit GREEN**

```bash
git add vision_perception/vision_perception/obstacle_detector.py
git commit -m "feat(vision): implement obstacle detector — all tests GREEN"
```

---

## Task 3: obstacle_avoidance_node — ROS2 Wrapper

**Files:**
- Create: `vision_perception/vision_perception/obstacle_avoidance_node.py`
- Modify: `vision_perception/setup.py`

- [ ] **Step 1: Implement ROS2 node**

```python
"""ROS2 obstacle avoidance node — subscribes to D435 depth, publishes obstacle events.

Wraps ObstacleDetector with frame-level debounce and rate limiting.
"""
import json
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String

from .obstacle_detector import ObstacleDetector

QOS_EVENT = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_SENSOR = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)


class ObstacleAvoidanceNode(Node):
    def __init__(self):
        super().__init__("obstacle_avoidance_node")

        # Parameters
        self.declare_parameter("threshold_m", 0.8)
        self.declare_parameter("warning_m", 1.2)
        self.declare_parameter("max_range_m", 3.0)
        self.declare_parameter("roi_top_ratio", 0.4)
        self.declare_parameter("roi_bottom_ratio", 0.8)
        self.declare_parameter("roi_left_ratio", 0.2)
        self.declare_parameter("roi_right_ratio", 0.8)
        self.declare_parameter("obstacle_ratio_trigger", 0.15)
        self.declare_parameter("publish_rate_hz", 5.0)
        self.declare_parameter("debounce_frames", 3)
        self.declare_parameter(
            "depth_topic",
            "/camera/camera/aligned_depth_to_color/image_raw",
        )

        self._detector = ObstacleDetector(
            threshold_m=self.get_parameter("threshold_m").value,
            warning_m=self.get_parameter("warning_m").value,
            max_range_m=self.get_parameter("max_range_m").value,
            roi_top_ratio=self.get_parameter("roi_top_ratio").value,
            roi_bottom_ratio=self.get_parameter("roi_bottom_ratio").value,
            roi_left_ratio=self.get_parameter("roi_left_ratio").value,
            roi_right_ratio=self.get_parameter("roi_right_ratio").value,
            obstacle_ratio_trigger=self.get_parameter("obstacle_ratio_trigger").value,
        )

        depth_topic = self.get_parameter("depth_topic").value
        self._pub = self.create_publisher(
            String, "/event/obstacle_detected", QOS_EVENT,
        )
        self.create_subscription(Image, depth_topic, self._on_depth, QOS_SENSOR)

        self._publish_interval = 1.0 / self.get_parameter("publish_rate_hz").value
        self._debounce_needed = int(self.get_parameter("debounce_frames").value)
        self._danger_streak = 0
        self._last_publish_time = 0.0

        self.get_logger().info(
            f"ObstacleAvoidanceNode started — threshold={self._detector.threshold_m}m, "
            f"debounce={self._debounce_needed} frames"
        )

    def _on_depth(self, msg: Image):
        # Convert uint16 mm → float32 meters
        depth_mm = np.frombuffer(msg.data, dtype=np.uint16).reshape(
            msg.height, msg.width,
        )
        depth_m = depth_mm.astype(np.float32) / 1000.0

        result = self._detector.detect(depth_m)

        # Frame-level debounce
        if result.zone == "danger":
            self._danger_streak += 1
        else:
            self._danger_streak = 0

        # Log zone at debug level
        self.get_logger().debug(
            f"zone={result.zone} min={result.distance_min:.2f}m "
            f"ratio={result.obstacle_ratio:.2f} streak={self._danger_streak}"
        )

        # Publish only when debounce threshold met + rate limited
        now = time.monotonic()
        if (
            self._danger_streak >= self._debounce_needed
            and (now - self._last_publish_time) >= self._publish_interval
        ):
            event = {
                "stamp": time.time(),
                "event_type": "obstacle_detected",
                "distance_min": round(result.distance_min, 3),
                "obstacle_ratio": round(result.obstacle_ratio, 3),
                "zone": result.zone,
            }
            out = String()
            out.data = json.dumps(event)
            self._pub.publish(out)
            self._last_publish_time = now
            self.get_logger().info(
                f"OBSTACLE: min={result.distance_min:.2f}m "
                f"ratio={result.obstacle_ratio:.0%}"
            )


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleAvoidanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add console_scripts entry to setup.py**

Add to `vision_perception/setup.py` `entry_points.console_scripts`:

```python
"obstacle_avoidance_node = vision_perception.obstacle_avoidance_node:main",
```

- [ ] **Step 3: Verify build**

```bash
colcon build --packages-select vision_perception
source install/setup.bash
```

Expected: build success

- [ ] **Step 4: Commit**

```bash
git add vision_perception/vision_perception/obstacle_avoidance_node.py \
    vision_perception/setup.py
git commit -m "feat(vision): add obstacle avoidance ROS2 node with debounce"
```

---

## Task 4: Launch File

**Files:**
- Create: `vision_perception/launch/obstacle_avoidance.launch.py`

- [ ] **Step 1: Create launch file**

```python
"""Launch obstacle avoidance node with configurable parameters."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("threshold_m", default_value="0.8"),
            DeclareLaunchArgument("warning_m", default_value="1.2"),
            DeclareLaunchArgument("max_range_m", default_value="3.0"),
            DeclareLaunchArgument("roi_top_ratio", default_value="0.4"),
            DeclareLaunchArgument("roi_bottom_ratio", default_value="0.8"),
            DeclareLaunchArgument("roi_left_ratio", default_value="0.2"),
            DeclareLaunchArgument("roi_right_ratio", default_value="0.8"),
            DeclareLaunchArgument("obstacle_ratio_trigger", default_value="0.15"),
            DeclareLaunchArgument("publish_rate_hz", default_value="5.0"),
            DeclareLaunchArgument("debounce_frames", default_value="3"),
            DeclareLaunchArgument(
                "depth_topic",
                default_value="/camera/camera/aligned_depth_to_color/image_raw",
            ),
            Node(
                package="vision_perception",
                executable="obstacle_avoidance_node",
                name="obstacle_avoidance_node",
                parameters=[
                    {
                        "threshold_m": LaunchConfiguration("threshold_m"),
                        "warning_m": LaunchConfiguration("warning_m"),
                        "max_range_m": LaunchConfiguration("max_range_m"),
                        "roi_top_ratio": LaunchConfiguration("roi_top_ratio"),
                        "roi_bottom_ratio": LaunchConfiguration("roi_bottom_ratio"),
                        "roi_left_ratio": LaunchConfiguration("roi_left_ratio"),
                        "roi_right_ratio": LaunchConfiguration("roi_right_ratio"),
                        "obstacle_ratio_trigger": LaunchConfiguration(
                            "obstacle_ratio_trigger"
                        ),
                        "publish_rate_hz": LaunchConfiguration("publish_rate_hz"),
                        "debounce_frames": LaunchConfiguration("debounce_frames"),
                        "depth_topic": LaunchConfiguration("depth_topic"),
                    }
                ],
                output="screen",
            ),
        ]
    )
```

- [ ] **Step 2: Build and verify launch**

```bash
colcon build --packages-select vision_perception
```

- [ ] **Step 3: Commit**

```bash
git add vision_perception/launch/obstacle_avoidance.launch.py
git commit -m "feat(vision): add obstacle avoidance launch file"
```

---

## Task 5: Integration Verification

- [ ] **Step 1: Run all vision_perception tests**

```bash
python3 -m pytest vision_perception/test/ -v
```

Expected: all existing tests (gesture/pose/event_builder) + 7 new obstacle tests pass

- [ ] **Step 2: Run full CI test suite**

```bash
python3 -m pytest speech_processor/test/ interaction_executive/test/ vision_perception/test/ -v
```

Expected: all pass

- [ ] **Step 3: Final commit with test verification**

```bash
git add -A
git commit -m "test(vision): obstacle detector 7/7 + full CI pass

TDD complete: ObstacleDetector + ObstacleAvoidanceNode + launch file
Ready for Jetson deployment and 10x collision test"
```

---

## Post-Implementation: Jetson Deployment & Testing

These steps require Jetson hardware access (not part of code plan):

1. `rsync` to Jetson + `colcon build --packages-select vision_perception`
2. Start D435 camera + obstacle_avoidance_node
3. 手動拿物體接近 D435，觀察 Foxglove `/event/obstacle_detected`
4. 確認 executive 收到 event → OBSTACLE_STOP → ACTION_DAMP
5. 10x 防撞測試（Go2 行走 → 放障礙物 → 停下）
