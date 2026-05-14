# Vision Perception Skeleton Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum runnable ROS2 package for gesture + pose recognition, testable without a camera.

**Architecture:** Two parallel workstreams — Subagent A builds classifiers (pure Python + unit tests), Subagent B builds package skeleton + ROS2 node + mock publisher. Both share frozen interfaces (classifier signatures + InferenceResult dataclass) defined in the spec.

**Tech Stack:** Python 3, ROS2 Humble, numpy, pytest, std_msgs, sensor_msgs, cv_bridge

**Spec:** `docs/superpowers/specs/2026-03-18-vision-perception-skeleton-design.md`

**Reference implementation:** `face_perception/` package (same structure pattern)

---

## Subagent Assignment

| Task | Subagent | Isolation |
|------|----------|-----------|
| Task 1-2 | **Subagent A** (classifiers) | worktree |
| Task 3-8 | **Subagent B** (package/node) | worktree |

Subagent A **must not** import event_builder or any ROS2 module.
Subagent B **must not** modify classifier function signatures.

---

## Task 1: Gesture Classifier + Tests (Subagent A)

**Files:**
- Create: `vision_perception/vision_perception/gesture_classifier.py`
- Create: `vision_perception/test/test_gesture_classifier.py`

**COCO-WholeBody Hand Keypoint Indices (21 per hand):**
```
0=wrist, 1-4=thumb(CMC→tip), 5-8=index(MCP→tip),
9-12=middle(MCP→tip), 13-16=ring(MCP→tip), 17-20=pinky(MCP→tip)
Fingertip indices: thumb=4, index=8, middle=12, ring=16, pinky=20
MCP indices: index=5, middle=9, ring=13, pinky=17
```

- [ ] **Step 1: Write failing tests**

```python
# vision_perception/test/test_gesture_classifier.py
"""Tests for gesture_classifier — pure Python, no ROS2."""
import numpy as np
import pytest


def _make_hand(positions: dict[int, tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
    """Helper: build (21,2) kps + (21,) scores from sparse dict."""
    kps = np.zeros((21, 2), dtype=np.float32)
    scores = np.ones(21, dtype=np.float32) * 0.9
    for idx, (x, y) in positions.items():
        kps[idx] = [x, y]
    return kps, scores


class TestClassifyGesture:
    """Each test builds keypoints that unambiguously match one gesture."""

    def test_stop_all_fingers_extended(self):
        from vision_perception.gesture_classifier import classify_gesture
        # Wrist at origin, all fingertips far away (spread hand)
        kps, scores = _make_hand({
            0: (0, 0),       # wrist
            4: (80, -60),    # thumb tip
            8: (40, -150),   # index tip
            12: (0, -160),   # middle tip
            16: (-40, -150), # ring tip
            20: (-80, -130), # pinky tip
            # MCP joints closer to wrist
            5: (30, -50), 9: (0, -50), 13: (-30, -50), 17: (-60, -50),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture == "stop"
        assert conf > 0.5

    def test_point_only_index_extended(self):
        from vision_perception.gesture_classifier import classify_gesture
        # Index extended, others curled into fist
        kps, scores = _make_hand({
            0: (0, 0),
            4: (20, -20),    # thumb curled
            8: (40, -150),   # index tip far = extended
            12: (0, -30),    # middle curled
            16: (-20, -30),  # ring curled
            20: (-40, -30),  # pinky curled
            5: (30, -50), 9: (0, -50), 13: (-30, -50), 17: (-60, -50),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture == "point"
        assert conf > 0.5

    def test_fist_all_fingers_curled(self):
        from vision_perception.gesture_classifier import classify_gesture
        # All fingertips close to palm center
        kps, scores = _make_hand({
            0: (0, 0),
            4: (15, -25),    # all tips near palm center ~(0, -40)
            8: (10, -35),
            12: (0, -35),
            16: (-10, -35),
            20: (-20, -30),
            5: (20, -40), 9: (0, -40), 13: (-20, -40), 17: (-40, -35),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture == "fist"
        assert conf > 0.5

    def test_ambiguous_returns_none(self):
        from vision_perception.gesture_classifier import classify_gesture
        # Random mid-range positions — no clear gesture
        kps, scores = _make_hand({
            0: (0, 0),
            4: (30, -40), 8: (20, -80), 12: (0, -60),
            16: (-20, -70), 20: (-30, -50),
            5: (20, -40), 9: (0, -40), 13: (-20, -40), 17: (-40, -35),
        })
        gesture, conf = classify_gesture(kps, scores)
        assert gesture is None
        assert conf == 0.0

    def test_zero_keypoints_returns_none(self):
        from vision_perception.gesture_classifier import classify_gesture
        kps = np.zeros((21, 2), dtype=np.float32)
        scores = np.zeros(21, dtype=np.float32)
        gesture, conf = classify_gesture(kps, scores)
        assert gesture is None

    def test_low_scores_returns_none(self):
        from vision_perception.gesture_classifier import classify_gesture
        kps, _ = _make_hand({
            0: (0, 0), 4: (80, -60), 8: (40, -150),
            12: (0, -160), 16: (-40, -150), 20: (-80, -130),
            5: (30, -50), 9: (0, -50), 13: (-30, -50), 17: (-60, -50),
        })
        scores = np.ones(21, dtype=np.float32) * 0.05  # very low
        gesture, conf = classify_gesture(kps, scores)
        assert gesture is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/roy422/newLife/elder_and_dog && python -m pytest vision_perception/test/test_gesture_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vision_perception'`

- [ ] **Step 3: Write gesture_classifier.py**

```python
# vision_perception/vision_perception/gesture_classifier.py
"""Single-frame static gesture classifier.

Pure Python — no ROS2, no camera, no GPU.
Input: COCO-WholeBody hand keypoints (21, 2) + scores (21,).
Output: (gesture_name, confidence) or (None, 0.0).

Does NOT return "wave" — wave requires temporal analysis done by the Node layer.
"""
from __future__ import annotations

import numpy as np

STATIC_GESTURES = ("stop", "point", "fist")

# COCO-WholeBody hand keypoint indices
_WRIST = 0
_FINGERTIPS = (4, 8, 12, 16, 20)  # thumb, index, middle, ring, pinky
_INDEX_TIP = 8
_MCPS = (5, 9, 13, 17)  # index, middle, ring, pinky MCP

# Thresholds (pixel-space, tuned for ~640x480 input)
_MIN_SCORE = 0.2          # minimum average keypoint confidence
_EXTEND_RATIO = 1.8       # fingertip-to-wrist / MCP-to-wrist ratio for "extended"
_CURL_RATIO = 0.8         # fingertip-to-wrist / MCP-to-wrist ratio for "curled"


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _finger_extended(kps: np.ndarray, tip_idx: int, mcp_idx: int, wrist: np.ndarray) -> bool:
    """True if fingertip is significantly farther from wrist than its MCP joint."""
    tip_dist = _dist(kps[tip_idx], wrist)
    mcp_dist = _dist(kps[mcp_idx], wrist)
    if mcp_dist < 1e-6:
        return tip_dist > 10.0  # fallback: absolute distance
    return tip_dist / mcp_dist > _EXTEND_RATIO


def _finger_curled(kps: np.ndarray, tip_idx: int, mcp_idx: int, wrist: np.ndarray) -> bool:
    """True if fingertip is close to or behind its MCP joint relative to wrist."""
    tip_dist = _dist(kps[tip_idx], wrist)
    mcp_dist = _dist(kps[mcp_idx], wrist)
    if mcp_dist < 1e-6:
        return tip_dist < 10.0
    return tip_dist / mcp_dist < _CURL_RATIO


def classify_gesture(
    hand_kps: np.ndarray,
    hand_scores: np.ndarray,
) -> tuple[str | None, float]:
    """Single-frame static gesture classification.

    Returns:
        ("stop" | "point" | "fist", confidence) or (None, 0.0).
    """
    if hand_kps.shape != (21, 2) or hand_scores.shape != (21,):
        return None, 0.0

    avg_score = float(np.mean(hand_scores))
    if avg_score < _MIN_SCORE:
        return None, 0.0

    wrist = hand_kps[_WRIST]

    # Check finger extension state (index through pinky; thumb uses tip only)
    # MCP pairs: (tip, mcp) — thumb has no MCP in our check, use simple distance
    finger_pairs = list(zip(_FINGERTIPS[1:], _MCPS))  # index, middle, ring, pinky
    extended = [_finger_extended(hand_kps, t, m, wrist) for t, m in finger_pairs]
    curled = [_finger_curled(hand_kps, t, m, wrist) for t, m in finger_pairs]

    # Thumb: extended if tip is far from wrist
    thumb_dist = _dist(hand_kps[4], wrist)
    avg_mcp_dist = np.mean([_dist(hand_kps[m], wrist) for m in _MCPS])
    thumb_extended = thumb_dist > avg_mcp_dist * 1.2 if avg_mcp_dist > 1e-6 else thumb_dist > 10.0

    n_extended = sum(extended) + (1 if thumb_extended else 0)
    n_curled = sum(curled)

    # stop: all 5 fingers extended (or at least 4 + thumb)
    if n_extended >= 4 and thumb_extended:
        return "stop", avg_score

    # point: only index extended, rest curled
    if extended[0] and sum(curled[1:]) >= 2 and not extended[1] and not extended[2]:
        return "point", avg_score

    # fist: all 4 non-thumb fingers curled
    if n_curled >= 3 and not any(extended):
        return "fist", avg_score

    return None, 0.0
```

- [ ] **Step 4: Create `__init__.py`**

```python
# vision_perception/vision_perception/__init__.py
```

(Empty file — required for Python package import.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/roy422/newLife/elder_and_dog && PYTHONPATH=vision_perception python -m pytest vision_perception/test/test_gesture_classifier.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add vision_perception/vision_perception/__init__.py \
       vision_perception/vision_perception/gesture_classifier.py \
       vision_perception/test/test_gesture_classifier.py
git commit -m "feat(vision): add gesture_classifier with rule-based single-frame classification

Classifies stop/point/fist from COCO-WholeBody hand keypoints.
Wave is not returned — handled by Node layer temporal analysis.
6 unit tests covering all gestures + edge cases."
```

---

## Task 2: Pose Classifier + Tests (Subagent A)

**Files:**
- Create: `vision_perception/vision_perception/pose_classifier.py`
- Create: `vision_perception/test/test_pose_classifier.py`

**COCO Body Keypoint Indices (17):**
```
0=nose, 1=left_eye, 2=right_eye, 3=left_ear, 4=right_ear,
5=left_shoulder, 6=right_shoulder, 7=left_elbow, 8=right_elbow,
9=left_wrist, 10=right_wrist, 11=left_hip, 12=right_hip,
13=left_knee, 14=right_knee, 15=left_ankle, 16=right_ankle
```

- [ ] **Step 1: Write failing tests**

```python
# vision_perception/test/test_pose_classifier.py
"""Tests for pose_classifier — pure Python, no ROS2."""
import math
import numpy as np
import pytest


def _body_from_angles(hip_angle_deg: float, knee_angle_deg: float,
                      trunk_angle_deg: float) -> np.ndarray:
    """Generate (17, 2) body keypoints that produce the given angles.
    Uses a simplified stick figure: shoulder at top, hip at middle, knee/ankle below.
    """
    kps = np.zeros((17, 2), dtype=np.float32)

    # Fixed reference: hip at (200, 300)
    hip = np.array([200.0, 300.0])
    kps[11] = hip  # left_hip
    kps[12] = hip + [20, 0]  # right_hip

    # Shoulder: trunk_angle from vertical
    trunk_rad = math.radians(trunk_angle_deg)
    shoulder_offset = np.array([math.sin(trunk_rad) * 100, -math.cos(trunk_rad) * 100])
    kps[5] = hip + shoulder_offset  # left_shoulder
    kps[6] = hip + shoulder_offset + [20, 0]  # right_shoulder

    # Knee: hip_angle from shoulder-hip line
    hip_rad = math.radians(180 - hip_angle_deg)  # angle at hip joint
    knee_offset = np.array([math.sin(hip_rad + trunk_rad) * 80,
                            math.cos(hip_rad + trunk_rad) * 80])
    kps[13] = hip + knee_offset  # left_knee
    kps[14] = hip + knee_offset + [20, 0]  # right_knee

    # Ankle: knee_angle from hip-knee line
    knee_rad = math.radians(180 - knee_angle_deg)
    knee_to_hip_angle = math.atan2(knee_offset[1], knee_offset[0])
    ankle_offset = knee_offset + np.array([
        math.cos(knee_to_hip_angle + knee_rad) * 70,
        math.sin(knee_to_hip_angle + knee_rad) * 70,
    ])
    kps[15] = hip + ankle_offset  # left_ankle
    kps[16] = hip + ankle_offset + [20, 0]  # right_ankle

    # Nose above shoulder
    kps[0] = kps[5] + [10, -30]

    return kps


class TestClassifyPose:
    def test_standing(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=175, knee_angle_deg=175, trunk_angle_deg=5)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.4)
        assert pose == "standing"
        assert conf > 0.5

    def test_sitting(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=90, knee_angle_deg=90, trunk_angle_deg=15)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.6)
        assert pose == "sitting"
        assert conf > 0.5

    def test_crouching(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=60, knee_angle_deg=60, trunk_angle_deg=40)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose == "crouching"
        assert conf > 0.5

    def test_fallen_horizontal(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=170, knee_angle_deg=170, trunk_angle_deg=80)
        scores = np.ones(17, dtype=np.float32) * 0.9
        # bbox wider than tall = horizontal body
        pose, conf = classify_pose(kps, scores, bbox_ratio=1.5)
        assert pose == "fallen"
        assert conf > 0.5

    def test_fallen_priority_over_standing(self):
        """fallen check runs before standing — even if angles look upright,
        bbox_ratio > 1.0 + trunk > 60° = fallen."""
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=170, knee_angle_deg=170, trunk_angle_deg=70)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=1.3)
        assert pose == "fallen"

    def test_ambiguous_returns_none(self):
        from vision_perception.pose_classifier import classify_pose
        # hip=140, knee=140, trunk=40 — doesn't match any rule cleanly
        kps = _body_from_angles(hip_angle_deg=140, knee_angle_deg=140, trunk_angle_deg=40)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=0.7)
        assert pose is None
        assert conf == 0.0

    def test_zero_keypoints_returns_none(self):
        from vision_perception.pose_classifier import classify_pose
        kps = np.zeros((17, 2), dtype=np.float32)
        scores = np.zeros(17, dtype=np.float32)
        pose, conf = classify_pose(kps, scores, bbox_ratio=None)
        assert pose is None

    def test_no_bbox_ratio_still_classifies(self):
        from vision_perception.pose_classifier import classify_pose
        kps = _body_from_angles(hip_angle_deg=175, knee_angle_deg=175, trunk_angle_deg=5)
        scores = np.ones(17, dtype=np.float32) * 0.9
        pose, conf = classify_pose(kps, scores, bbox_ratio=None)
        assert pose == "standing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/roy422/newLife/elder_and_dog && PYTHONPATH=vision_perception python -m pytest vision_perception/test/test_pose_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vision_perception.pose_classifier'`

- [ ] **Step 3: Write pose_classifier.py**

```python
# vision_perception/vision_perception/pose_classifier.py
"""Single-frame pose classifier.

Pure Python — no ROS2, no camera, no GPU.
Input: COCO body keypoints (17, 2) + scores (17,) + optional bbox_ratio.
Output: (pose_name, confidence) or (None, 0.0).

Classification order (first match wins):
1. fallen (safety priority)
2. standing
3. crouching
4. sitting
5. None (ambiguous)
"""
from __future__ import annotations

import math

import numpy as np

POSES = ("standing", "sitting", "crouching", "fallen")

# COCO body keypoint indices
_L_SHOULDER, _R_SHOULDER = 5, 6
_L_HIP, _R_HIP = 11, 12
_L_KNEE, _R_KNEE = 13, 14
_L_ANKLE, _R_ANKLE = 15, 16

_MIN_SCORE = 0.2


def _angle_deg(a: np.ndarray, vertex: np.ndarray, b: np.ndarray) -> float:
    """Angle at vertex in degrees, formed by vectors vertex→a and vertex→b."""
    va = a - vertex
    vb = b - vertex
    cos_val = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-8)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    return float(math.degrees(math.acos(cos_val)))


def _trunk_angle_deg(shoulder: np.ndarray, hip: np.ndarray) -> float:
    """Angle between shoulder-hip line and vertical (downward Y direction)."""
    vec = shoulder - hip  # points upward from hip to shoulder
    # Vertical reference: straight up = (0, -1) in image coords
    vertical = np.array([0.0, -1.0])
    cos_val = np.dot(vec, vertical) / (np.linalg.norm(vec) + 1e-8)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    return float(math.degrees(math.acos(cos_val)))


def _mid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2.0


def classify_pose(
    body_kps: np.ndarray,
    body_scores: np.ndarray,
    bbox_ratio: float | None = None,
) -> tuple[str | None, float]:
    """Single-frame pose classification.

    Args:
        body_kps: (17, 2) COCO body keypoints.
        body_scores: (17,) confidence per keypoint.
        bbox_ratio: width/height of person bounding box (from Node layer).

    Returns:
        (pose_name, confidence) or (None, 0.0).
    """
    if body_kps.shape != (17, 2) or body_scores.shape != (17,):
        return None, 0.0

    avg_score = float(np.mean(body_scores))
    if avg_score < _MIN_SCORE:
        return None, 0.0

    # Compute midpoints for left/right averaging
    shoulder = _mid(body_kps[_L_SHOULDER], body_kps[_R_SHOULDER])
    hip = _mid(body_kps[_L_HIP], body_kps[_R_HIP])
    knee = _mid(body_kps[_L_KNEE], body_kps[_R_KNEE])
    ankle = _mid(body_kps[_L_ANKLE], body_kps[_R_ANKLE])

    # Guard: if key joints are at origin (all zeros), bail out
    if np.linalg.norm(hip) < 1e-6 and np.linalg.norm(shoulder) < 1e-6:
        return None, 0.0

    hip_angle = _angle_deg(shoulder, hip, knee)
    knee_angle = _angle_deg(hip, knee, ankle)
    trunk_angle = _trunk_angle_deg(shoulder, hip)

    # 1. fallen (safety priority)
    if bbox_ratio is not None and bbox_ratio > 1.0 and trunk_angle > 60:
        return "fallen", avg_score

    # 2. standing
    if hip_angle > 160 and knee_angle > 160:
        return "standing", avg_score

    # 3. crouching
    if hip_angle < 80 and knee_angle < 80:
        return "crouching", avg_score

    # 4. sitting
    if 70 < hip_angle < 130 and trunk_angle < 30:
        return "sitting", avg_score

    # 5. ambiguous
    return None, 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/roy422/newLife/elder_and_dog && PYTHONPATH=vision_perception python -m pytest vision_perception/test/test_pose_classifier.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add vision_perception/vision_perception/pose_classifier.py \
       vision_perception/test/test_pose_classifier.py
git commit -m "feat(vision): add pose_classifier with angle + bbox rule-based classification

Classifies standing/sitting/crouching/fallen from COCO body keypoints.
fallen has priority (safety function). Ambiguous poses return None.
8 unit tests covering all poses + edge cases."
```

---

## Task 3: Package Skeleton (Subagent B)

**Files:**
- Create: `vision_perception/setup.py`
- Create: `vision_perception/package.xml`
- Create: `vision_perception/resource/vision_perception` (empty marker)
- Create: `vision_perception/vision_perception/__init__.py` (if not already by Task 1)

- [ ] **Step 1: Create setup.py**

```python
# vision_perception/setup.py
from glob import glob

from setuptools import setup

package_name = "vision_perception"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=[
        "setuptools",
        "numpy",
    ],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS2 vision perception: gesture + pose classification",
    license="BSD-3-Clause",
    entry_points={
        "console_scripts": [
            "vision_perception_node = vision_perception.vision_perception_node:main",
            "mock_event_publisher = vision_perception.mock_event_publisher:main",
        ],
    },
)
```

- [ ] **Step 2: Create package.xml**

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>vision_perception</name>
  <version>0.1.0</version>
  <description>ROS2 vision perception: gesture + pose classification</description>
  <maintainer email="roy@pawai.dev">Roy</maintainer>
  <license>BSD-3-Clause</license>

  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <depend>sensor_msgs</depend>
  <depend>cv_bridge</depend>

  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

- [ ] **Step 3: Create resource marker**

```bash
mkdir -p vision_perception/resource
touch vision_perception/resource/vision_perception
```

- [ ] **Step 4: Create __init__.py** (if not exists)

```python
# vision_perception/vision_perception/__init__.py
```

- [ ] **Step 5: Verify package structure**

```bash
ls -la vision_perception/
# Expected: setup.py, package.xml, resource/, vision_perception/, test/, launch/, config/
```

- [ ] **Step 6: Commit**

```bash
git add vision_perception/setup.py vision_perception/package.xml \
       vision_perception/resource/vision_perception \
       vision_perception/vision_perception/__init__.py
git commit -m "feat(vision): create vision_perception ROS2 package skeleton"
```

---

## Task 4: Inference Adapter + Mock Inference (Subagent B)

**Files:**
- Create: `vision_perception/vision_perception/inference_adapter.py`
- Create: `vision_perception/vision_perception/mock_inference.py`

- [ ] **Step 1: Write inference_adapter.py**

```python
# vision_perception/vision_perception/inference_adapter.py
"""Abstract inference adapter interface.

Defines InferenceResult dataclass and InferenceAdapter ABC.
Phase 1: MockInference. Phase 2: RTMPoseInference.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class InferenceResult:
    """Standardized keypoint output from any inference backend."""
    body_kps: np.ndarray           # (17, 2) COCO body
    body_scores: np.ndarray        # (17,)
    left_hand_kps: np.ndarray      # (21, 2) COCO-WholeBody hand
    left_hand_scores: np.ndarray   # (21,)
    right_hand_kps: np.ndarray     # (21, 2)
    right_hand_scores: np.ndarray  # (21,)


class InferenceAdapter(ABC):
    @abstractmethod
    def infer(self, image_bgr: np.ndarray | None) -> InferenceResult:
        """Run inference on an image.

        Args:
            image_bgr: BGR image, or None in use_camera=false mode.
                Mock implementations accept None and return scenario keypoints.
                Real implementations must raise ValueError if image_bgr is None.
        """
```

- [ ] **Step 2: Write mock_inference.py**

```python
# vision_perception/vision_perception/mock_inference.py
"""Mock inference adapter — returns scenario-based fake keypoints.

No GPU, no model, no camera required. Used for Phase 1 development.
"""
from __future__ import annotations

import numpy as np

from .inference_adapter import InferenceAdapter, InferenceResult

# Pre-built keypoint scenarios
_SCENARIOS: dict[str, dict] = {}


def _register(name: str, body: np.ndarray, left_hand: np.ndarray, right_hand: np.ndarray):
    _SCENARIOS[name] = {"body": body, "left_hand": left_hand, "right_hand": right_hand}


def _standing_body() -> np.ndarray:
    """Upright standing pose — hip/knee angles ~175°, trunk ~5°."""
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[0] = [320, 50]    # nose
    kps[5] = [290, 120]   # l_shoulder
    kps[6] = [350, 120]   # r_shoulder
    kps[11] = [300, 280]  # l_hip
    kps[12] = [340, 280]  # r_hip
    kps[13] = [300, 380]  # l_knee
    kps[14] = [340, 380]  # r_knee
    kps[15] = [300, 460]  # l_ankle
    kps[16] = [340, 460]  # r_ankle
    return kps


def _sitting_body() -> np.ndarray:
    """Seated pose — hip ~90°, trunk ~15°."""
    kps = _standing_body().copy()
    kps[13] = [380, 280]  # knees forward
    kps[14] = [420, 280]
    kps[15] = [380, 380]  # ankles down
    kps[16] = [420, 380]
    return kps


def _fallen_body() -> np.ndarray:
    """Horizontal body — trunk > 60°, bbox_ratio > 1."""
    kps = np.zeros((17, 2), dtype=np.float32)
    kps[0] = [100, 400]
    kps[5] = [150, 380]
    kps[6] = [150, 420]
    kps[11] = [300, 380]
    kps[12] = [300, 420]
    kps[13] = [400, 380]
    kps[14] = [400, 420]
    kps[15] = [480, 380]
    kps[16] = [480, 420]
    return kps


def _stop_hand() -> np.ndarray:
    """Open palm — all fingers extended."""
    kps = np.zeros((21, 2), dtype=np.float32)
    kps[0] = [0, 0]       # wrist
    kps[4] = [80, -60]    # thumb tip
    kps[8] = [40, -150]   # index tip
    kps[12] = [0, -160]   # middle tip
    kps[16] = [-40, -150] # ring tip
    kps[20] = [-80, -130] # pinky tip
    kps[5] = [30, -50]    # index MCP
    kps[9] = [0, -50]     # middle MCP
    kps[13] = [-30, -50]  # ring MCP
    kps[17] = [-60, -50]  # pinky MCP
    return kps


def _fist_hand() -> np.ndarray:
    """Closed fist — all fingers curled."""
    kps = np.zeros((21, 2), dtype=np.float32)
    kps[0] = [0, 0]
    kps[4] = [15, -25]
    kps[8] = [10, -35]
    kps[12] = [0, -35]
    kps[16] = [-10, -35]
    kps[20] = [-20, -30]
    kps[5] = [20, -40]
    kps[9] = [0, -40]
    kps[13] = [-20, -40]
    kps[17] = [-40, -35]
    return kps


def _point_hand() -> np.ndarray:
    """Point — only index extended."""
    kps = _fist_hand().copy()
    kps[8] = [40, -150]  # index tip far
    return kps


def _idle_hand() -> np.ndarray:
    return np.zeros((21, 2), dtype=np.float32)


# Register scenarios
_register("standing_idle", _standing_body(), _idle_hand(), _idle_hand())
_register("sitting", _sitting_body(), _idle_hand(), _idle_hand())
_register("fallen", _fallen_body(), _idle_hand(), _idle_hand())
_register("stop", _standing_body(), _stop_hand(), _idle_hand())
_register("fist", _standing_body(), _fist_hand(), _idle_hand())
_register("point", _standing_body(), _point_hand(), _idle_hand())


class MockInference(InferenceAdapter):
    """Returns pre-configured keypoints for a given scenario.

    Args:
        scenario: Key from _SCENARIOS dict. Default "standing_idle".
    """

    def __init__(self, scenario: str = "standing_idle"):
        if scenario not in _SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario}'. Available: {sorted(_SCENARIOS)}"
            )
        self._scenario = _SCENARIOS[scenario]

    def infer(self, image_bgr: np.ndarray | None) -> InferenceResult:
        """Return scenario keypoints. image_bgr is ignored (can be None)."""
        high = np.ones(17, dtype=np.float32) * 0.9
        hand_high = np.ones(21, dtype=np.float32) * 0.9
        hand_zero = np.zeros(21, dtype=np.float32)

        left = self._scenario["left_hand"]
        right = self._scenario["right_hand"]

        return InferenceResult(
            body_kps=self._scenario["body"].copy(),
            body_scores=high.copy(),
            left_hand_kps=left.copy(),
            left_hand_scores=hand_high.copy() if np.any(left) else hand_zero.copy(),
            right_hand_kps=right.copy(),
            right_hand_scores=hand_high.copy() if np.any(right) else hand_zero.copy(),
        )
```

- [ ] **Step 3: Commit**

```bash
git add vision_perception/vision_perception/inference_adapter.py \
       vision_perception/vision_perception/mock_inference.py
git commit -m "feat(vision): add InferenceAdapter ABC + MockInference with scenarios"
```

---

## Task 5: Event Builder + Tests (Subagent B)

**Files:**
- Create: `vision_perception/vision_perception/event_builder.py`
- Create: `vision_perception/test/test_event_builder.py`

- [ ] **Step 1: Write event_builder.py**

```python
# vision_perception/vision_perception/event_builder.py
"""Shared JSON event builders for gesture and pose events.

Used by both vision_perception_node and mock_event_publisher.
Output format aligns with interaction_contract.md v2.0 §4.3 / §4.4.
"""
from __future__ import annotations

import time

# v2.0 contract uses "ok" but implementation uses "fist".
# Transition via compat map until 3/25 benchmark confirms switch.
GESTURE_COMPAT_MAP = {"fist": "ok"}


def build_gesture_event(gesture: str, confidence: float, hand: str) -> dict:
    """Build /event/gesture_detected JSON payload.

    stamp and event_type are auto-generated.
    Applies GESTURE_COMPAT_MAP (impl uses "fist", contract sends "ok").
    """
    return {
        "stamp": time.time(),
        "event_type": "gesture_detected",
        "gesture": GESTURE_COMPAT_MAP.get(gesture, gesture),
        "confidence": round(confidence, 4),
        "hand": hand,
    }


def build_pose_event(pose: str, confidence: float, track_id: int = 0) -> dict:
    """Build /event/pose_detected JSON payload.

    track_id: Phase 1 always 0 (no face association).
    ⚠️ track_id=0 is a Phase 1 internal convention, NOT a contract sentinel.
    Downstream must not use this value for face association logic.
    """
    return {
        "stamp": time.time(),
        "event_type": "pose_detected",
        "pose": pose,
        "confidence": round(confidence, 4),
        "track_id": track_id,
    }
```

- [ ] **Step 2: Write test_event_builder.py**

```python
# vision_perception/test/test_event_builder.py
"""Tests for event_builder — validates contract v2.0 alignment."""
import pytest


class TestBuildGestureEvent:
    def test_contains_all_contract_fields(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("stop", 0.87, "right")
        assert set(evt.keys()) == {"stamp", "event_type", "gesture", "confidence", "hand"}

    def test_event_type_is_gesture_detected(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("stop", 0.87, "right")
        assert evt["event_type"] == "gesture_detected"

    def test_fist_compat_map(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("fist", 0.9, "left")
        assert evt["gesture"] == "ok"  # v2.0 contract

    def test_stop_passes_through(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("stop", 0.85, "right")
        assert evt["gesture"] == "stop"

    def test_confidence_rounded(self):
        from vision_perception.event_builder import build_gesture_event
        evt = build_gesture_event("point", 0.87654321, "right")
        assert evt["confidence"] == 0.8765


class TestBuildPoseEvent:
    def test_contains_all_contract_fields(self):
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("standing", 0.92)
        assert set(evt.keys()) == {"stamp", "event_type", "pose", "confidence", "track_id"}

    def test_event_type_is_pose_detected(self):
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("fallen", 0.95)
        assert evt["event_type"] == "pose_detected"

    def test_phase1_internal_track_id_is_zero(self):
        """Phase 1 internal convention — NOT a contract guarantee."""
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("standing", 0.9)
        assert evt["track_id"] == 0

    def test_stamp_is_float(self):
        from vision_perception.event_builder import build_pose_event
        evt = build_pose_event("sitting", 0.8)
        assert isinstance(evt["stamp"], float)
```

- [ ] **Step 3: Run tests**

Run: `cd /home/roy422/newLife/elder_and_dog && PYTHONPATH=vision_perception python -m pytest vision_perception/test/test_event_builder.py -v`
Expected: 9 passed

- [ ] **Step 4: Commit**

```bash
git add vision_perception/vision_perception/event_builder.py \
       vision_perception/test/test_event_builder.py
git commit -m "feat(vision): add event_builder with contract v2.0 alignment + compat map

Shared JSON builders for gesture/pose events.
fist→ok compat map for v2.0 contract transition.
9 unit tests verifying all contract fields."
```

---

## Task 6: Vision Perception Node (Subagent B)

**Files:**
- Create: `vision_perception/vision_perception/vision_perception_node.py`

- [ ] **Step 1: Write vision_perception_node.py**

```python
# vision_perception/vision_perception/vision_perception_node.py
"""ROS2 node: gesture + pose classification from shared inference.

Two modes:
- use_camera=false (Phase 1): timer-driven, MockInference, no camera needed.
- use_camera=true (Phase 2+): subscribes to D435 camera topics.

Reference: face_perception/face_identity_node.py for error handling patterns.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .event_builder import build_gesture_event, build_pose_event
from .gesture_classifier import classify_gesture
from .inference_adapter import InferenceResult
from .mock_inference import MockInference
from .pose_classifier import classify_pose


def _majority(buffer: deque) -> str | None:
    """Return most common non-None element, or None if empty."""
    items = [x for x in buffer if x is not None]
    if not items:
        return None
    return max(set(items), key=items.count)


def _bbox_ratio_from_kps(body_kps: np.ndarray) -> float | None:
    """Compute width/height ratio from body keypoints bounding box."""
    valid = body_kps[body_kps.sum(axis=1) != 0]
    if len(valid) < 2:
        return None
    mins = valid.min(axis=0)
    maxs = valid.max(axis=0)
    w = maxs[0] - mins[0]
    h = maxs[1] - mins[1]
    if h < 1e-6:
        return None
    return float(w / h)


class VisionPerceptionNode(Node):
    def __init__(self):
        super().__init__("vision_perception_node")

        # --- Parameters ---
        self.declare_parameter("inference_backend", "mock")
        self.declare_parameter("use_camera", False)
        self.declare_parameter("publish_fps", 8.0)
        self.declare_parameter("tick_period", 0.05)
        self.declare_parameter("color_topic", "/camera/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/camera/aligned_depth_to_color/image_raw")
        self.declare_parameter("gesture_vote_frames", 5)
        self.declare_parameter("pose_vote_frames", 20)
        self.declare_parameter("mock_scenario", "standing_idle")

        backend = self.get_parameter("inference_backend").value
        self.use_camera = self.get_parameter("use_camera").value
        publish_fps = self.get_parameter("publish_fps").value
        tick_period = self.get_parameter("tick_period").value
        gesture_frames = self.get_parameter("gesture_vote_frames").value
        pose_frames = self.get_parameter("pose_vote_frames").value
        mock_scenario = self.get_parameter("mock_scenario").value

        # --- State ---
        self.shutting_down = False
        self.lock = threading.Lock()
        self.color = None
        self.publish_period = 1.0 / max(0.1, float(publish_fps))
        self.last_publish_ts = 0.0

        # Temporal buffers (node-managed, not in classifiers)
        self.gesture_buffer: deque[str | None] = deque(maxlen=gesture_frames)
        self.pose_buffer: deque[str | None] = deque(maxlen=pose_frames)
        self.last_gesture: str | None = None
        self.last_pose: str | None = None
        self.last_hand: str = "right"

        # --- Inference adapter ---
        if backend == "mock":
            self.adapter = MockInference(scenario=mock_scenario)
        else:
            raise ValueError(f"Unknown inference_backend: {backend}. Phase 2 will add 'rtmpose'.")

        # --- Camera subscription (only if use_camera=true) ---
        if self.use_camera:
            from cv_bridge import CvBridge
            from sensor_msgs.msg import Image
            self.bridge = CvBridge()
            color_topic = self.get_parameter("color_topic").value
            self.create_subscription(Image, color_topic, self._cb_color, 10)

        # --- Publishers (QoS: Reliable, Volatile, depth=10) ---
        self.gesture_pub = self.create_publisher(String, "/event/gesture_detected", 10)
        self.pose_pub = self.create_publisher(String, "/event/pose_detected", 10)

        if self.use_camera:
            from sensor_msgs.msg import Image as ImageMsg
            self.debug_pub = self.create_publisher(ImageMsg, "/vision_perception/debug_image", 1)
        else:
            self.debug_pub = None

        # --- Timer ---
        self.timer = self.create_timer(tick_period, self._tick)

        self.get_logger().info(
            f"VisionPerceptionNode ready: backend={backend}, use_camera={self.use_camera}, "
            f"scenario={mock_scenario}"
        )

    def _cb_color(self, msg):
        with self.lock:
            self.color = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def _tick(self):
        if self.shutting_down or not rclpy.ok():
            return

        # Get image (None in no-camera mode)
        image = None
        if self.use_camera:
            with self.lock:
                image = self.color.copy() if self.color is not None else None
            if image is None:
                return  # no frame yet

        # --- Inference ---
        try:
            result: InferenceResult = self.adapter.infer(image)
        except Exception as exc:
            self.get_logger().warning(f"Inference failed: {exc}", throttle_duration_sec=1.0)
            return

        # --- Pose classification ---
        bbox_ratio = _bbox_ratio_from_kps(result.body_kps)
        pose_raw, pose_conf = classify_pose(result.body_kps, result.body_scores, bbox_ratio)
        if pose_raw is not None:
            self.pose_buffer.append(pose_raw)
        pose_vote = _majority(self.pose_buffer)

        if pose_vote is not None and pose_vote != self.last_pose:
            self.last_pose = pose_vote
            msg = String()
            msg.data = json.dumps(build_pose_event(pose_vote, pose_conf))
            self.pose_pub.publish(msg)

        # --- Gesture classification (dual hand, pick higher confidence) ---
        g_left, c_left = classify_gesture(result.left_hand_kps, result.left_hand_scores)
        g_right, c_right = classify_gesture(result.right_hand_kps, result.right_hand_scores)

        if c_left > c_right and g_left is not None:
            gesture_raw, gesture_conf, hand = g_left, c_left, "left"
        elif g_right is not None:
            gesture_raw, gesture_conf, hand = g_right, c_right, "right"
        else:
            gesture_raw, gesture_conf, hand = None, 0.0, self.last_hand

        if gesture_raw is not None:
            self.gesture_buffer.append(gesture_raw)
            self.last_hand = hand
        gesture_vote = _majority(self.gesture_buffer)

        if gesture_vote is not None and gesture_vote != self.last_gesture:
            self.last_gesture = gesture_vote
            msg = String()
            msg.data = json.dumps(build_gesture_event(gesture_vote, gesture_conf, self.last_hand))
            self.gesture_pub.publish(msg)

    def close(self):
        self.shutting_down = True
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()


def main():
    rclpy.init()
    node = VisionPerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
```

- [ ] **Step 2: Commit**

```bash
git add vision_perception/vision_perception/vision_perception_node.py
git commit -m "feat(vision): add vision_perception_node with dual-mode (camera/no-camera)

Timer-driven tick, temporal vote buffers, dual-hand gesture strategy.
use_camera=false for Phase 1 (no D435 needed).
Publishes /event/gesture_detected + /event/pose_detected on state change."
```

---

## Task 7: Mock Event Publisher (Subagent B)

**Files:**
- Create: `vision_perception/vision_perception/mock_event_publisher.py`

- [ ] **Step 1: Write mock_event_publisher.py**

```python
# vision_perception/vision_perception/mock_event_publisher.py
"""Standalone mock event publisher — bypasses inference + classifier entirely.

Cycles through gesture and pose scenarios, publishing events via event_builder.
Used for frontend development (PawAI Studio GesturePanel / PosePanel).
Does NOT use vision_perception_node — completely independent path.
"""
from __future__ import annotations

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .event_builder import build_gesture_event, build_pose_event

# (event_type, name, duration_sec)
_SEQUENCE = [
    ("gesture", "wave", 2.0),
    ("gesture", "stop", 2.0),
    ("gesture", "point", 2.0),
    ("gesture", "fist", 2.0),
    ("pose", "standing", 3.0),
    ("pose", "sitting", 2.0),
    ("pose", "crouching", 2.0),
    ("pose", "fallen", 2.0),
]


class MockEventPublisher(Node):
    def __init__(self):
        super().__init__("mock_event_publisher")

        self.declare_parameter("interval", 0.5)  # publish interval within each scenario
        self.interval = self.get_parameter("interval").value

        self.gesture_pub = self.create_publisher(String, "/event/gesture_detected", 10)
        self.pose_pub = self.create_publisher(String, "/event/pose_detected", 10)

        self._seq_idx = 0
        self._phase_start = time.time()
        self.timer = self.create_timer(self.interval, self._tick)

        self.get_logger().info("MockEventPublisher started — cycling through scenarios")

    def _tick(self):
        now = time.time()
        kind, name, duration = _SEQUENCE[self._seq_idx]

        if now - self._phase_start > duration:
            self._seq_idx = (self._seq_idx + 1) % len(_SEQUENCE)
            self._phase_start = now
            kind, name, duration = _SEQUENCE[self._seq_idx]
            self.get_logger().info(f"Scenario: {kind}/{name}")

        msg = String()
        if kind == "gesture":
            msg.data = json.dumps(build_gesture_event(name, 0.85, "right"))
            self.gesture_pub.publish(msg)
        else:
            msg.data = json.dumps(build_pose_event(name, 0.90))
            self.pose_pub.publish(msg)


def main():
    rclpy.init()
    node = MockEventPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
```

- [ ] **Step 2: Commit**

```bash
git add vision_perception/vision_perception/mock_event_publisher.py
git commit -m "feat(vision): add mock_event_publisher for frontend development

Cycles through gesture+pose scenarios, publishes events via shared event_builder.
Independent from vision_perception_node — no camera, no inference."
```

---

## Task 8: Launch + Config + Integration Test (Subagent B)

**Files:**
- Create: `vision_perception/launch/vision_perception.launch.py`
- Create: `vision_perception/launch/mock_publisher.launch.py`
- Create: `vision_perception/config/vision_perception.yaml`
- Create: `vision_perception/test/` directory marker

- [ ] **Step 1: Write vision_perception.launch.py**

```python
# vision_perception/launch/vision_perception.launch.py
"""Launch vision_perception_node with config."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("vision_perception")
    default_config = os.path.join(pkg_dir, "config", "vision_perception.yaml")

    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value=default_config),
        DeclareLaunchArgument("inference_backend", default_value="mock"),
        DeclareLaunchArgument("use_camera", default_value="false"),
        DeclareLaunchArgument("mock_scenario", default_value="standing_idle"),
        Node(
            package="vision_perception",
            executable="vision_perception_node",
            name="vision_perception_node",
            parameters=[
                LaunchConfiguration("config_file"),
                {"inference_backend": LaunchConfiguration("inference_backend")},
                {"use_camera": LaunchConfiguration("use_camera")},
                {"mock_scenario": LaunchConfiguration("mock_scenario")},
            ],
            output="screen",
        ),
    ])
```

- [ ] **Step 2: Write mock_publisher.launch.py**

```python
# vision_perception/launch/mock_publisher.launch.py
"""Launch mock_event_publisher for frontend development."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="vision_perception",
            executable="mock_event_publisher",
            name="mock_event_publisher",
            output="screen",
        ),
    ])
```

- [ ] **Step 3: Write vision_perception.yaml**

```yaml
# vision_perception/config/vision_perception.yaml
# Phase 1 defaults — no camera, mock inference
vision_perception_node:
  ros__parameters:
    inference_backend: "mock"
    use_camera: false
    publish_fps: 8.0
    tick_period: 0.05
    color_topic: "/camera/camera/color/image_raw"
    depth_topic: "/camera/camera/aligned_depth_to_color/image_raw"
    gesture_vote_frames: 5
    pose_vote_frames: 20
    mock_scenario: "standing_idle"
```

- [ ] **Step 4: Ensure test/ directory exists**

```bash
mkdir -p vision_perception/test
mkdir -p vision_perception/launch
mkdir -p vision_perception/config
```

- [ ] **Step 5: Commit**

```bash
git add vision_perception/launch/ vision_perception/config/
git commit -m "feat(vision): add launch files + config for Phase 1 mock mode"
```

- [ ] **Step 6: Build and verify**

```bash
cd /home/roy422/newLife/elder_and_dog
source /opt/ros/humble/setup.bash   # or .zsh on Jetson
colcon build --packages-select vision_perception
source install/setup.bash

# Unit tests
PYTHONPATH=vision_perception python -m pytest vision_perception/test/ -v
# Expected: all tests pass

# Launch no-camera mock node
ros2 launch vision_perception vision_perception.launch.py &
sleep 3

# Verify topics exist
ros2 topic list | grep -E "gesture|pose"
# Expected:
#   /event/gesture_detected
#   /event/pose_detected

# Verify event JSON
ros2 topic echo /event/pose_detected --once
# Expected: JSON with stamp, event_type, pose, confidence, track_id

# Kill node
pkill -f vision_perception_node

# Launch mock publisher
ros2 launch vision_perception mock_publisher.launch.py &
sleep 5

ros2 topic echo /event/gesture_detected --once
# Expected: JSON with gesture events cycling

pkill -f mock_event_publisher
```

- [ ] **Step 7: Final commit**

```bash
git add -A vision_perception/
git commit -m "feat(vision): vision_perception Phase 1 complete — build + smoke verified

Package skeleton, classifiers, mock inference, node, mock publisher,
launch files, config. All testable without camera (use_camera=false)."
```
