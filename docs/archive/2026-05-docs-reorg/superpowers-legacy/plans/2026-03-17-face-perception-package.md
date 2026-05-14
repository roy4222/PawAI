# face_perception ROS2 Package (B-lite) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `scripts/face_identity_infer_cv.py` 包裝成正式 ROS2 package `face_perception`，可 `ros2 launch` 啟動，topic 對齊契約 v2.0，原 script 保留作為 fallback。

**Architecture:** 單一 ROS2 Python package，一個 node（`face_identity_node`）。核心邏輯從原 script 逐行搬入，argparse → `declare_parameter`。不做 Clean Architecture 分層，不拆 domain/application/presentation。原 `scripts/face_identity_infer_cv.py` 不動、不刪。

**Tech Stack:** ROS2 Humble / Python 3.10 / OpenCV (FaceDetectorYN + FaceRecognizerSF) / cv_bridge / std_msgs

**注意：Node 名稱變更**：原 script 的 node name 是 `face_identity_infer_cv`，新 package 改為 `face_identity_node`（對齊 interaction_contract v2.0 §7.1）。YAML config key `face_identity_node:` 依賴此名稱。

**分工邊界（Agent 1 限定）：**
- 只碰 `face_perception/`（新建）、`scripts/start_face_identity_tmux.sh`（新建）、`scripts/clean_face_env.sh`（新建）、`docs/人臉辨識/README.md`（更新）
- 不碰 `speech_processor/`、`go2_robot_sdk/`、`interaction_contract.md`
- topic 名稱和 schema 不改（契約 v2.0 凍結）

---

## Parameter Mapping Table

⚠️ **這是最容易出錯的地方。** 所有 argparse → declare_parameter 的對應必須逐一核對。

| # | argparse name | ROS2 param name | type | script default | ROS2 default | 備註 |
|---|---|---|---|---|---|---|
| 1 | `--db-dir` | `db_dir` | string | `/home/jetson/face_db` | 同左 | |
| 2 | `--model-path` | `model_path` | string | `/home/jetson/face_db/model_sface.pkl` | 同左 | |
| 3 | `--yunet-model` | `yunet_model` | string | `...yunet_2023mar.onnx` | `...yunet_legacy.onnx` | ⚠️ **修正**: 2023mar 在 Jetson OpenCV 4.5.4 不相容 |
| 4 | `--sface-model` | `sface_model` | string | `...sface_2021dec.onnx` | 同左 | |
| 5 | `--det-score-threshold` | `det_score_threshold` | float | 0.90 | 0.90 | 契約值；operational 用 yaml 覆蓋為 0.35 |
| 6 | `--det-nms-threshold` | `det_nms_threshold` | float | 0.30 | 0.30 | |
| 7 | `--det-top-k` | `det_top_k` | int | 5000 | 5000 | |
| 8 | `--sim-threshold-upper` | `sim_threshold_upper` | float | 0.35 | 0.35 | |
| 9 | `--sim-threshold-lower` | `sim_threshold_lower` | float | 0.25 | 0.25 | |
| 10 | `--stable-hits` | `stable_hits` | int | 3 | 3 | |
| 11 | `--unknown-grace-s` | `unknown_grace_s` | float | 1.2 | 1.2 | |
| 12 | `--min-face-area-ratio` | `min_face_area_ratio` | float | 0.02 | 0.02 | operational 用 yaml 覆蓋為 0.001 |
| 13 | `--max-faces` | `max_faces` | int | 5 | 5 | |
| 14 | `--track-iou-threshold` | `track_iou_threshold` | float | 0.3 | 0.3 | |
| 15 | `--track-max-misses` | `track_max_misses` | int | 10 | 10 | |
| 16 | `--publish-fps` | `publish_fps` | float | 8.0 | 8.0 | |
| 17 | `--tick-period` | `tick_period` | float | 0.05 | 0.05 | |
| 18 | `--no-publish-compare-image` | `publish_compare_image` | bool | *(flag, default=True after inversion)* | `True` | ⚠️ **反轉**: 正名化；operational yaml 設 false |
| 19 | `--save-debug-jpeg` | `save_debug_jpeg` | bool | False | `False` | |
| 20 | `--color-topic` | `color_topic` | string | `/camera/camera/color/image_raw` | 同左 | |
| 21 | `--depth-topic` | `depth_topic` | string | `/camera/camera/aligned_depth_to_color/image_raw` | 同左 | |
| 22 | `--headless` | `headless` | bool | False | `False` | 代碼內自動偵測 DISPLAY env |

**self.args.xxx → self.xxx 替換清單（tick/assign_tracks/decide_stable_name 內）：**

| 原 | 新 | 出現在 |
|---|---|---|
| `self.args.track_iou_threshold` | `self.track_iou_threshold` | `assign_tracks()` |
| `self.args.track_max_misses` | `self.track_max_misses` | `assign_tracks()` |
| `self.args.sim_threshold_upper` | `self.sim_threshold_upper` | `decide_stable_name()` |
| `self.args.sim_threshold_lower` | `self.sim_threshold_lower` | `decide_stable_name()` |
| `self.args.stable_hits` | `self.stable_hits` | `decide_stable_name()` |
| `self.args.unknown_grace_s` | `self.unknown_grace_s` | `decide_stable_name()` |
| `self.args.max_faces` | `self.max_faces` | `tick()` |
| `self.args.min_face_area_ratio` | `self.min_face_area_ratio` | `tick()` |
| `self.args.save_debug_jpeg` | `self.save_debug_jpeg` | `tick()` |

---

## File Map

| 檔案 | Task | 動作 |
|------|------|------|
| `face_perception/setup.py` | Task 1 | 新建 |
| `face_perception/setup.cfg` | Task 1 | 新建 |
| `face_perception/package.xml` | Task 1 | 新建 |
| `face_perception/resource/face_perception` | Task 1 | 新建（空檔） |
| `face_perception/face_perception/__init__.py` | Task 1 | 新建（空檔） |
| `face_perception/test/__init__.py` | Task 1 | 新建（空檔） |
| `face_perception/face_perception/face_identity_node.py` | Task 2 | 新建（核心） |
| `face_perception/test/test_utilities.py` | Task 3 | 新建 |
| `face_perception/launch/face_perception.launch.py` | Task 4 | 新建 |
| `face_perception/config/face_perception.yaml` | Task 4 | 新建 |
| `scripts/start_face_identity_tmux.sh` | Task 5 | 新建 |
| `scripts/clean_face_env.sh` | Task 5 | 新建 |
| `docs/人臉辨識/README.md` | Task 6 | 修改 |
| `scripts/face_identity_infer_cv.py` | — | **不動** |

---

## Task 1: Package Scaffold

**Files:**
- Create: `face_perception/setup.py`
- Create: `face_perception/setup.cfg`
- Create: `face_perception/package.xml`
- Create: `face_perception/resource/face_perception`
- Create: `face_perception/face_perception/__init__.py`

- [ ] **Step 1.1: 清除舊的 build artifacts**

```bash
cd /home/roy422/newLife/elder_and_dog
rm -rf build/face_perception install/face_perception build/face_owner install/face_owner
```

- [ ] **Step 1.2: 建立目錄結構**

```bash
mkdir -p face_perception/face_perception
mkdir -p face_perception/launch
mkdir -p face_perception/config
mkdir -p face_perception/resource
mkdir -p face_perception/test
```

- [ ] **Step 1.3: 建立 `face_perception/setup.py`**

```python
from glob import glob

from setuptools import setup

package_name = "face_perception"

setup(
    name=package_name,
    version="1.0.0",
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
        "opencv-python",
    ],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS2 face perception package: YuNet detection + SFace recognition + IOU tracking",
    license="BSD-3-Clause",
    entry_points={
        "console_scripts": [
            "face_identity_node = face_perception.face_identity_node:main",
        ],
    },
)
```

- [ ] **Step 1.4: 建立 `face_perception/setup.cfg`**

```ini
[develop]
script_dir=$base/lib/face_perception
[install]
install_scripts=$base/lib/face_perception
```

- [ ] **Step 1.5: 建立 `face_perception/package.xml`**

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>face_perception</name>
  <version>1.0.0</version>
  <description>ROS2 face perception: YuNet + SFace + IOU tracking</description>
  <maintainer email="roy@pawai.dev">Roy</maintainer>
  <license>BSD-3-Clause</license>

  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <depend>sensor_msgs</depend>
  <depend>cv_bridge</depend>

  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <test_depend>ament_pep257</test_depend>
  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

- [ ] **Step 1.6: 建立 resource marker 和 __init__.py**

```bash
touch face_perception/resource/face_perception
touch face_perception/face_perception/__init__.py
touch face_perception/test/__init__.py
```

- [ ] **Step 1.7: 驗證 scaffold build 通過**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select face_perception
```

Expected: build 成功（node 還沒有，但 package 結構正確即可）。若 entry_point import 失敗是預期內的（下一步建 node）。

- [ ] **Step 1.8: Commit scaffold**

```bash
git add face_perception/
git commit -m "feat(face_perception): scaffold ROS2 package structure

Agent 1: face recognition ROS2 integration"
```

---

## Task 2: face_identity_node.py（核心）

**Files:**
- Create: `face_perception/face_perception/face_identity_node.py`
- Reference (不改): `scripts/face_identity_infer_cv.py`

- [ ] **Step 2.1: 建立 `face_perception/face_perception/face_identity_node.py`**

完整程式碼（從原 script 逐行搬入，argparse → declare_parameter）：

```python
#!/usr/bin/env python3
"""ROS2 face identity node: YuNet detection + SFace recognition + IOU tracking.

Ported from scripts/face_identity_infer_cv.py (argparse → declare_parameter).
Original script retained as fallback.
"""
import json
import os
import pickle
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


def resolve_model_path(path: str, model_name: str) -> Path:
    model_path = Path(path)
    if not model_path.exists():
        raise FileNotFoundError(f"Cannot find {model_name} model: {model_path}")
    return model_path


def list_face_images(db_dir: Path):
    items = []
    if not db_dir.exists():
        return items
    for person_dir in sorted(db_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        for img in sorted(person_dir.glob("*.png")):
            items.append((person_dir.name, img))
    return items


def compute_db_counts(db_dir: Path):
    counts = {}
    if not db_dir.exists():
        return counts
    for person_dir in sorted(db_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        counts[person_dir.name] = len(list(person_dir.glob("*.png")))
    return counts


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class FaceIdentityNode(Node):
    def __init__(self):
        super().__init__("face_identity_node")

        # --- Declare all parameters (mapping table in plan doc) ---
        self.declare_parameter("db_dir", "/home/jetson/face_db")
        self.declare_parameter("model_path", "/home/jetson/face_db/model_sface.pkl")
        self.declare_parameter(
            "yunet_model",
            "/home/jetson/face_models/face_detection_yunet_legacy.onnx",
        )
        self.declare_parameter(
            "sface_model",
            "/home/jetson/face_models/face_recognition_sface_2021dec.onnx",
        )
        self.declare_parameter("det_score_threshold", 0.90)
        self.declare_parameter("det_nms_threshold", 0.30)
        self.declare_parameter("det_top_k", 5000)
        self.declare_parameter("sim_threshold_upper", 0.35)
        self.declare_parameter("sim_threshold_lower", 0.25)
        self.declare_parameter("stable_hits", 3)
        self.declare_parameter("unknown_grace_s", 1.2)
        self.declare_parameter("min_face_area_ratio", 0.02)
        self.declare_parameter("max_faces", 5)
        self.declare_parameter("track_iou_threshold", 0.3)
        self.declare_parameter("track_max_misses", 10)
        self.declare_parameter("publish_fps", 8.0)
        self.declare_parameter("tick_period", 0.05)
        self.declare_parameter("publish_compare_image", True)
        self.declare_parameter("save_debug_jpeg", False)
        self.declare_parameter("color_topic", "/camera/camera/color/image_raw")
        self.declare_parameter(
            "depth_topic",
            "/camera/camera/aligned_depth_to_color/image_raw",
        )
        self.declare_parameter("headless", False)

        # --- Read parameters into instance vars ---
        db_dir = self.get_parameter("db_dir").value
        model_path_str = self.get_parameter("model_path").value
        yunet_model = self.get_parameter("yunet_model").value
        sface_model = self.get_parameter("sface_model").value
        det_score_threshold = self.get_parameter("det_score_threshold").value
        det_nms_threshold = self.get_parameter("det_nms_threshold").value
        det_top_k = self.get_parameter("det_top_k").value
        self.sim_threshold_upper = self.get_parameter("sim_threshold_upper").value
        self.sim_threshold_lower = self.get_parameter("sim_threshold_lower").value
        self.stable_hits = self.get_parameter("stable_hits").value
        self.unknown_grace_s = self.get_parameter("unknown_grace_s").value
        self.min_face_area_ratio = self.get_parameter("min_face_area_ratio").value
        self.max_faces = self.get_parameter("max_faces").value
        self.track_iou_threshold = self.get_parameter("track_iou_threshold").value
        self.track_max_misses = self.get_parameter("track_max_misses").value
        publish_fps = self.get_parameter("publish_fps").value
        tick_period = self.get_parameter("tick_period").value
        self.publish_compare_image = self.get_parameter("publish_compare_image").value
        self.save_debug_jpeg = self.get_parameter("save_debug_jpeg").value
        color_topic = self.get_parameter("color_topic").value
        depth_topic = self.get_parameter("depth_topic").value
        headless_param = self.get_parameter("headless").value

        # --- Derived state ---
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.headless = not bool(os.environ.get("DISPLAY")) or headless_param
        self.last_log_ts = 0.0
        self.last_publish_ts = 0.0
        self.shutting_down = False
        self.last_pub_err_ts = 0.0
        self.publish_period = 1.0 / max(0.1, float(publish_fps))

        self.next_track_id = 1
        self.tracks = {}
        self.track_states = {}

        self.color = None
        self.depth = None
        self.depth_scale = 0.001

        # --- OpenCV face modules ---
        if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
            raise RuntimeError(
                "OpenCV build does not support FaceDetectorYN/FaceRecognizerSF; "
                "please install OpenCV >= 4.8 with face module"
            )

        yunet_path = resolve_model_path(yunet_model, "YuNet")
        sface_path = resolve_model_path(sface_model, "SFace")

        self.detector = cv2.FaceDetectorYN.create(
            str(yunet_path),
            "",
            (320, 320),
            det_score_threshold,
            det_nms_threshold,
            det_top_k,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(sface_path), "")

        # --- Face DB / model ---
        self.model_path = Path(model_path_str)
        current_counts = compute_db_counts(Path(db_dir))
        if self.model_path.exists():
            with self.model_path.open("rb") as f:
                self.model = pickle.load(f)
            stored_counts = self.model.get("counts", {})
            if stored_counts != current_counts:
                self.get_logger().info(
                    "Enrollment DB changed; retraining model "
                    f"(stored={stored_counts}, current={current_counts})"
                )
                self.model = self.train_model(Path(db_dir))
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                with self.model_path.open("wb") as wf:
                    pickle.dump(self.model, wf)
                self.get_logger().info(
                    f"Retrained and saved model to {self.model_path}"
                )
            else:
                self.get_logger().info(f"Loaded model from {self.model_path}")
        else:
            self.model = self.train_model(Path(db_dir))
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with self.model_path.open("wb") as f:
                pickle.dump(self.model, f)
            self.get_logger().info(f"Trained and saved model to {self.model_path}")

        # --- Publishers (topic 名稱對齊 interaction_contract v2.0，不可改) ---
        self.debug_image_pub = self.create_publisher(
            Image, "/face_identity/debug_image", 10
        )
        self.compare_image_pub = self.create_publisher(
            Image, "/face_identity/compare_image", 10
        )
        self.face_state_pub = self.create_publisher(
            String, "/state/perception/face", 10
        )
        self.face_event_pub = self.create_publisher(
            String, "/event/face_identity", 10
        )

        # --- Subscriptions ---
        self.create_subscription(Image, color_topic, self.cb_color, 10)
        self.create_subscription(Image, depth_topic, self.cb_depth, 10)
        self.timer = self.create_timer(tick_period, self.tick)

        self.get_logger().info(
            f"Identity ready, people={sorted(self.model.get('centroids', {}).keys())}, "
            f"headless={self.headless}"
        )

    # --- Static helpers (unchanged from original script) ---

    @staticmethod
    def pick_largest_face(faces: np.ndarray):
        if faces is None or len(faces) == 0:
            return None
        return max(faces, key=lambda row: float(row[2] * row[3]))

    @staticmethod
    def to_bbox(face_row: np.ndarray, img_w: int, img_h: int):
        x, y, fw, fh = face_row[:4].astype(np.int32)
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img_w, x + max(1, fw))
        y2 = min(img_h, y + max(1, fh))
        if x2 <= x1 or y2 <= y1:
            return None
        return (x1, y1, x2, y2)

    @staticmethod
    def bbox_iou(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = float(inter_w * inter_h)
        if inter_area <= 0:
            return 0.0
        area_a = float((ax2 - ax1) * (ay2 - ay1))
        area_b = float((bx2 - bx1) * (by2 - by1))
        denom = area_a + area_b - inter_area
        if denom <= 1e-8:
            return 0.0
        return inter_area / denom

    # --- Track state management (unchanged) ---

    def get_track_state(self, track_id: int):
        state = self.track_states.get(track_id)
        if state is None:
            state = {
                "candidate_name": "unknown",
                "candidate_hits": 0,
                "last_stable_name": "unknown",
                "last_stable_sim": -1.0,
                "last_known_ts": 0.0,
            }
            self.track_states[track_id] = state
        return state

    def assign_tracks(self, detections):
        assigned = []
        used_tracks = set()

        for det in detections:
            bbox = det["bbox"]
            best_track_id = None
            best_iou = 0.0
            for track_id, track in self.tracks.items():
                if track_id in used_tracks:
                    continue
                iou = self.bbox_iou(bbox, track["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_track_id = track_id

            if best_track_id is not None and best_iou >= self.track_iou_threshold:
                track_id = best_track_id
                self.tracks[track_id]["bbox"] = bbox
                self.tracks[track_id]["misses"] = 0
            else:
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracks[track_id] = {"bbox": bbox, "misses": 0}
                self._publish_face_event(
                    "track_started", track_id, "unknown", 0.0, None
                )

            used_tracks.add(track_id)
            assigned.append((track_id, det))

        drop_ids = []
        for track_id, track in self.tracks.items():
            if track_id in used_tracks:
                continue
            track["misses"] += 1
            if track["misses"] > self.track_max_misses:
                drop_ids.append(track_id)

        for track_id in drop_ids:
            lost_state = self.track_states.get(track_id, {})
            self._publish_face_event(
                "track_lost",
                track_id,
                lost_state.get("last_stable_name", "unknown"),
                max(0.0, lost_state.get("last_stable_sim", 0.0)),
                None,
            )
            self.tracks.pop(track_id, None)
            self.track_states.pop(track_id, None)

        return assigned

    # --- Embedding / recognition (unchanged) ---

    def extract_embedding_from_crop(self, image_bgr: np.ndarray, face_row: np.ndarray):
        aligned = self.recognizer.alignCrop(image_bgr, face_row)
        if aligned is None or aligned.size == 0:
            return None
        emb = self.recognizer.feature(aligned)
        if emb is None:
            return None
        emb = np.asarray(emb, dtype=np.float32).reshape(-1)
        return emb

    def train_model(self, db_dir: Path):
        samples = list_face_images(db_dir)
        if len(samples) == 0:
            raise RuntimeError(f"No face samples found under {db_dir}")

        by_person = {}
        for name, img_path in samples:
            bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if bgr is None:
                continue

            if bgr.shape[0] == 112 and bgr.shape[1] == 112:
                emb = self.recognizer.feature(bgr)
                if emb is None:
                    continue
                emb = np.asarray(emb, dtype=np.float32).reshape(-1)
                by_person.setdefault(name, []).append(emb)
                continue

            h, w = bgr.shape[:2]
            self.detector.setInputSize((w, h))
            _, faces = self.detector.detect(bgr)
            face = self.pick_largest_face(faces)
            if face is None:
                continue
            emb = self.extract_embedding_from_crop(bgr, face)
            if emb is None:
                continue
            by_person.setdefault(name, []).append(emb)

        model = {"embeddings": {}, "centroids": {}, "counts": {}}
        for name, feats in by_person.items():
            if len(feats) == 0:
                continue
            model["embeddings"][name] = feats
            model["centroids"][name] = np.mean(np.stack(feats, axis=0), axis=0)
            model["counts"][name] = len(feats)

        if len(model["counts"]) == 0:
            raise RuntimeError(
                "No valid face embeddings from DB; please re-enroll samples"
            )
        return model

    # --- Callbacks (unchanged) ---

    def cb_color(self, msg):
        with self.lock:
            self.color = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def cb_depth(self, msg):
        with self.lock:
            self.depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

    # --- Prediction / stabilization (unchanged) ---

    def predict_name(self, emb: np.ndarray):
        best_name = "unknown"
        best_sim = -1.0

        for name, centroid in self.model.get("centroids", {}).items():
            sample_embs = self.model.get("embeddings", {}).get(name, [])
            if len(sample_embs) > 0:
                sim = max(cosine_similarity(emb, sample) for sample in sample_embs)
            else:
                sim = cosine_similarity(emb, centroid)

            if sim > best_sim:
                best_sim = sim
                best_name = name

        return best_name, best_sim

    def decide_stable_name(self, track_id: int, raw_name: str, raw_sim: float):
        state = self.get_track_state(track_id)
        now = time.time()
        if raw_sim >= self.sim_threshold_upper:
            proposed = raw_name
        elif raw_sim < self.sim_threshold_lower:
            proposed = "unknown"
        else:
            proposed = state["last_stable_name"]

        if proposed == state["candidate_name"]:
            state["candidate_hits"] += 1
        else:
            state["candidate_name"] = proposed
            state["candidate_hits"] = 1

        if state["candidate_hits"] >= self.stable_hits:
            state["last_stable_name"] = state["candidate_name"]
            state["last_stable_sim"] = raw_sim
            if state["last_stable_name"] != "unknown":
                state["last_known_ts"] = now

        if (
            state["last_stable_name"] != "unknown"
            and proposed == "unknown"
            and (now - state["last_known_ts"]) < self.unknown_grace_s
        ):
            return (
                state["last_stable_name"],
                max(raw_sim, state["last_stable_sim"]),
                "hold",
            )

        return (
            state["last_stable_name"],
            max(raw_sim, state["last_stable_sim"]),
            "stable",
        )

    # --- Publishing (unchanged) ---

    def safe_publish(self, debug_img: np.ndarray, compare_img: np.ndarray | None):
        if self.shutting_down or not rclpy.ok():
            return
        now = time.time()
        if now - self.last_publish_ts < self.publish_period:
            return
        try:
            self.debug_image_pub.publish(
                self.bridge.cv2_to_imgmsg(debug_img, encoding="bgr8")
            )
            if self.publish_compare_image and compare_img is not None:
                self.compare_image_pub.publish(
                    self.bridge.cv2_to_imgmsg(compare_img, encoding="bgr8")
                )
            self.last_publish_ts = now
        except Exception as exc:  # noqa: BLE001
            if now - self.last_pub_err_ts >= 1.0:
                self.get_logger().warn(f"publish skipped: {exc}")
                self.last_pub_err_ts = now

    def _publish_face_event(self, event_type, track_id, stable_name, sim, distance_m):
        if self.shutting_down or not rclpy.ok():
            return
        msg = String()
        msg.data = json.dumps(
            {
                "stamp": time.time(),
                "event_type": event_type,
                "track_id": track_id,
                "stable_name": stable_name,
                "sim": round(sim, 4),
                "distance_m": distance_m,
            }
        )
        self.face_event_pub.publish(msg)

    def close(self):
        self.shutting_down = True
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()

    # --- Main tick (unchanged logic, self.args.xxx → self.xxx) ---

    def tick(self):
        with self.lock:
            color = None if self.color is None else self.color.copy()
            depth = None if self.depth is None else self.depth.copy()

        if color is None or self.shutting_down or not rclpy.ok():
            return

        raw = color.copy()
        h, w = color.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(color)

        detections = []
        if faces is not None and len(faces) > 0:
            face_rows = sorted(
                faces,
                key=lambda row: float(row[2] * row[3]),
                reverse=True,
            )
            if self.max_faces > 0:
                face_rows = face_rows[: self.max_faces]

            frame_area = float(color.shape[0] * color.shape[1])
            for face_row in face_rows:
                bbox = self.to_bbox(face_row, w, h)
                if bbox is None:
                    continue
                x1, y1, x2, y2 = bbox
                if ((x2 - x1) * (y2 - y1)) / frame_area < self.min_face_area_ratio:
                    continue
                detections.append({"face_row": face_row, "bbox": bbox})

        tracked_faces = self.assign_tracks(detections)
        face_count = len(tracked_faces)

        lines = []
        tick_track_info = {}
        for track_id, det in tracked_faces:
            face_row = det["face_row"]
            x1, y1, x2, y2 = det["bbox"]

            name = "unknown"
            sim = 0.0
            mode = "stable"
            ts = self.get_track_state(track_id)
            old_stable_name = ts["last_stable_name"]

            emb = self.extract_embedding_from_crop(color, face_row)
            if emb is not None:
                raw_name, raw_sim = self.predict_name(emb)
                name, sim, mode = self.decide_stable_name(track_id, raw_name, raw_sim)

            distance_m = None
            dist_txt = "N/A"
            if depth is not None:
                roi = depth[y1:y2, x1:x2]
                valid = roi[(roi > 0) & (roi < 10000)]
                if valid.size:
                    distance_m = round(
                        float(np.median(valid)) * self.depth_scale, 3
                    )
                    dist_txt = f"{distance_m:.2f}m"

            new_stable_name = ts["last_stable_name"]
            if old_stable_name != new_stable_name:
                if old_stable_name == "unknown":
                    self._publish_face_event(
                        "identity_stable",
                        track_id,
                        new_stable_name,
                        sim,
                        distance_m,
                    )
                else:
                    self._publish_face_event(
                        "identity_changed",
                        track_id,
                        new_stable_name,
                        sim,
                        distance_m,
                    )

            tick_track_info[track_id] = {
                "track_id": track_id,
                "stable_name": ts["last_stable_name"],
                "sim": round(max(0.0, ts["last_stable_sim"]), 4),
                "distance_m": distance_m,
                "bbox": [x1, y1, x2, y2],
                "mode": (
                    "stable"
                    if ts["last_stable_name"] != "unknown"
                    else "hold"
                ),
            }

            label = f"id={track_id} {name} sim={sim:.2f} d={dist_txt} {mode}"
            lines.append(label)

            color_box = (0, 255, 0) if name != "unknown" else (0, 0, 255)
            cv2.rectangle(color, (x1, y1), (x2, y2), color_box, 2)
            cv2.putText(
                color,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color_box,
                2,
            )

        compare = None
        if self.publish_compare_image:
            compare = cv2.hconcat([raw, color])
        self.safe_publish(color, compare)

        # Publish face state (every tick)
        state_tracks = []
        for tid, track in self.tracks.items():
            if tid in tick_track_info:
                state_tracks.append(tick_track_info[tid])
            else:
                ts = self.track_states.get(tid, {})
                state_tracks.append(
                    {
                        "track_id": tid,
                        "stable_name": ts.get("last_stable_name", "unknown"),
                        "sim": round(
                            max(0.0, ts.get("last_stable_sim", 0.0)), 4
                        ),
                        "distance_m": None,
                        "bbox": list(track["bbox"]),
                        "mode": (
                            "stable"
                            if ts.get("last_stable_name", "unknown") != "unknown"
                            else "hold"
                        ),
                    }
                )
        face_state_msg = String()
        face_state_msg.data = json.dumps(
            {
                "stamp": time.time(),
                "face_count": len(self.tracks),
                "tracks": state_tracks,
            }
        )
        self.face_state_pub.publish(face_state_msg)

        # Headless logging
        if self.headless:
            now = time.time()
            if now - self.last_log_ts >= 1.0:
                if len(lines) == 0:
                    self.get_logger().info(f"face_count={face_count}")
                else:
                    self.get_logger().info(
                        f"face_count={face_count} | " + " | ".join(lines)
                    )
                if self.save_debug_jpeg:
                    cv2.imwrite("/tmp/face_identity_debug.jpg", color)
                    if compare is not None:
                        cv2.imwrite("/tmp/face_identity_compare.jpg", compare)
                self.last_log_ts = now
            return

        cv2.imshow("face_identity_node", color)
        cv2.waitKey(1)


def main():
    rclpy.init()
    node = FaceIdentityNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.2: colcon build 驗證**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select face_perception
source install/setup.zsh  # Jetson 用 zsh
```

Expected: build 成功，無 error。

- [ ] **Step 2.3: 驗證 entry point 存在**

```bash
ros2 run face_perception face_identity_node --ros-args -p db_dir:="/nonexistent" 2>&1 | head -5
```

Expected: 啟動失敗但原因是 model file not found（不是 import error）。這證明 entry point 正確、參數傳遞正常。

- [ ] **Step 2.4: Commit node**

```bash
git add face_perception/face_perception/face_identity_node.py
git commit -m "feat(face_perception): add face_identity_node with declare_parameter

Ported from scripts/face_identity_infer_cv.py.
argparse → declare_parameter, all 22 params mapped.
Original script retained as fallback.

Agent 1: face recognition ROS2 integration"
```

---

## Task 3: Utility Function Tests

**Files:**
- Create: `face_perception/test/test_utilities.py`

- [ ] **Step 3.1: 建立 `face_perception/test/test_utilities.py`**

```python
"""Tests for pure utility functions in face_identity_node.

These tests can run on any machine (no ROS2, no D435, no model files needed).
"""
import numpy as np
import pytest

from face_perception.face_identity_node import (
    FaceIdentityNode,
    cosine_similarity,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_returns_zero(self):
        a = np.array([0.0, 0.0])
        assert cosine_similarity(a, a) == 0.0


class TestBboxIou:
    def test_identical_boxes(self):
        box = (10, 10, 50, 50)
        assert FaceIdentityNode.bbox_iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        a = (0, 0, 10, 10)
        b = (20, 20, 30, 30)
        assert FaceIdentityNode.bbox_iou(a, b) == 0.0

    def test_partial_overlap(self):
        a = (0, 0, 10, 10)
        b = (5, 5, 15, 15)
        # intersection = 5*5 = 25, union = 100+100-25 = 175
        assert FaceIdentityNode.bbox_iou(a, b) == pytest.approx(25.0 / 175.0)

    def test_contained_box(self):
        outer = (0, 0, 100, 100)
        inner = (10, 10, 20, 20)
        # intersection = 10*10 = 100, union = 10000+100-100 = 10000
        assert FaceIdentityNode.bbox_iou(outer, inner) == pytest.approx(100.0 / 10000.0)


class TestToBbox:
    def test_normal_face(self):
        face_row = np.array([10, 20, 50, 60, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        assert result == (10, 20, 60, 80)

    def test_clamp_to_image(self):
        face_row = np.array([-5, -5, 100, 100, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        assert result == (0, 0, 95, 95)

    def test_zero_area_returns_none(self):
        face_row = np.array([10, 20, 0, 0, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        # fw=0 → max(1, 0)=1 → x2=11, fh=0 → max(1, 0)=1 → y2=21
        # area = 1*1 > 0, so not None
        assert result is not None

    def test_face_outside_image_returns_none(self):
        face_row = np.array([700, 500, 50, 50, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        # x1=640 (clamped), x2=640 (clamped) → x2<=x1 → None
        assert result is None
```

- [ ] **Step 3.2: 在開發機上跑測試**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest face_perception/test/test_utilities.py -v
```

Expected: 全部 PASS。

> **注意**：測試 import `FaceIdentityNode` 會帶入 `cv2`、`rclpy`、`cv_bridge`、`sensor_msgs` 依賴。在無 ROS2 的開發機上無法直接跑。請在 Jetson 上測試，或在 `colcon test --packages-select face_perception` 中執行。

- [ ] **Step 3.3: Commit tests**

```bash
git add face_perception/test/test_utilities.py
git commit -m "test(face_perception): add utility function unit tests

cosine_similarity, bbox_iou, to_bbox — 11 test cases.

Agent 1: face recognition ROS2 integration"
```

---

## Task 4: Launch File + Config YAML

**Files:**
- Create: `face_perception/launch/face_perception.launch.py`
- Create: `face_perception/config/face_perception.yaml`

- [ ] **Step 4.1: 建立 `face_perception/config/face_perception.yaml`**

Operational defaults for Jetson（覆蓋 code defaults 中不適合的值）：

```yaml
# Operational defaults for Jetson + D435.
# These override code defaults where needed.
face_identity_node:
  ros__parameters:
    # YuNet legacy needed for Jetson OpenCV 4.5.4
    yunet_model: "/home/jetson/face_models/face_detection_yunet_legacy.onnx"
    sface_model: "/home/jetson/face_models/face_recognition_sface_2021dec.onnx"
    db_dir: "/home/jetson/face_db"
    model_path: "/home/jetson/face_db/model_sface.pkl"
    # Operational thresholds (more permissive than code default 0.90)
    det_score_threshold: 0.35
    min_face_area_ratio: 0.001
    # Disable compare image (saves bandwidth)
    publish_compare_image: false
    # Always headless on Jetson (no DISPLAY)
    headless: true
    # Max tracked faces
    max_faces: 5
    publish_fps: 8.0
```

- [ ] **Step 4.2: 建立 `face_perception/launch/face_perception.launch.py`**

```python
"""Minimal launch file for face_perception package.

Usage:
  ros2 launch face_perception face_perception.launch.py
  ros2 launch face_perception face_perception.launch.py headless:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("face_perception")
    default_config = os.path.join(pkg_dir, "config", "face_perception.yaml")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config_file",
                default_value=default_config,
                description="Path to face_perception config YAML",
            ),
            Node(
                package="face_perception",
                executable="face_identity_node",
                name="face_identity_node",
                parameters=[LaunchConfiguration("config_file")],
                output="screen",
            ),
        ]
    )
```

- [ ] **Step 4.3: rebuild 驗證 launch + config 都被包進去**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select face_perception
source install/setup.zsh
# 確認 config 和 launch 被安裝
ls install/face_perception/share/face_perception/config/
ls install/face_perception/share/face_perception/launch/
```

Expected: 兩個目錄各有一個檔案。

- [ ] **Step 4.4: Commit launch + config**

```bash
git add face_perception/launch/ face_perception/config/
git commit -m "feat(face_perception): add launch file and Jetson config yaml

Operational defaults: det_score=0.35, yunet_legacy, headless, no compare image.

Agent 1: face recognition ROS2 integration"
```

---

## Task 5: Operational Scripts

**Files:**
- Create: `scripts/start_face_identity_tmux.sh`
- Create: `scripts/clean_face_env.sh`

- [ ] **Step 5.1: 建立 `scripts/clean_face_env.sh`**

```bash
#!/usr/bin/env bash
# clean_face_env.sh — 清理人臉辨識相關殘留 process
# 用法: bash scripts/clean_face_env.sh
set -euo pipefail

echo "=== Cleaning face perception environment ==="

# Kill face identity processes
pkill -f "face_identity_node" 2>/dev/null && echo "  killed face_identity_node" || true
pkill -f "face_identity_infer_cv" 2>/dev/null && echo "  killed face_identity_infer_cv" || true

# Kill realsense camera (only if requested)
if [[ "${1:-}" == "--with-camera" ]]; then
    pkill -f "realsense2_camera_node" 2>/dev/null && echo "  killed realsense2_camera_node" || true
    pkill -f "rs_launch.py" 2>/dev/null && echo "  killed rs_launch.py" || true
fi

# Kill foxglove bridge (only if requested)
if [[ "${1:-}" == "--with-foxglove" ]] || [[ "${1:-}" == "--all" ]]; then
    pkill -x foxglove_bridge 2>/dev/null && echo "  killed foxglove_bridge" || true
fi

# Kill all if --all
if [[ "${1:-}" == "--all" ]]; then
    pkill -f "realsense2_camera_node" 2>/dev/null && echo "  killed realsense2_camera_node" || true
    pkill -f "rs_launch.py" 2>/dev/null && echo "  killed rs_launch.py" || true
fi

# Kill tmux session if exists
tmux kill-session -t face_identity 2>/dev/null && echo "  killed tmux session 'face_identity'" || true

echo "=== Done ==="
```

- [ ] **Step 5.2: 建立 `scripts/start_face_identity_tmux.sh`**

```bash
#!/usr/bin/env bash
# start_face_identity_tmux.sh — 一鍵啟動人臉辨識 pipeline (tmux)
# 用法: bash scripts/start_face_identity_tmux.sh
#
# 啟動 3 個 pane:
#   0: RealSense D435 camera
#   1: face_identity_node (ROS2 package)
#   2: foxglove_bridge
set -euo pipefail

SESSION="face_identity"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Preflight checks ---
echo "=== Preflight checks ==="

# Check ROS2
if ! command -v ros2 &>/dev/null; then
    echo "ERROR: ros2 not found. Source ROS2 setup first."
    exit 1
fi

# Check D435 connected
if ! ros2 pkg list 2>/dev/null | grep -q realsense2_camera; then
    echo "WARNING: realsense2_camera package not found. Camera launch may fail."
fi

# Check model files
YUNET="/home/jetson/face_models/face_detection_yunet_legacy.onnx"
SFACE="/home/jetson/face_models/face_recognition_sface_2021dec.onnx"
FACE_DB="/home/jetson/face_db"

for f in "$YUNET" "$SFACE"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Model file not found: $f"
        exit 1
    fi
done

if [[ ! -d "$FACE_DB" ]]; then
    echo "ERROR: Face DB directory not found: $FACE_DB"
    exit 1
fi

# Check face_perception package is built
if ! ros2 pkg list 2>/dev/null | grep -q face_perception; then
    echo "ERROR: face_perception package not found."
    echo "  Run: colcon build --packages-select face_perception && source install/setup.zsh"
    exit 1
fi

echo "=== Preflight OK ==="

# --- Clean previous session ---
bash "$REPO_DIR/scripts/clean_face_env.sh" --all 2>/dev/null || true

# --- ROS2 source preamble (Jetson 用 zsh，不可混用 setup.bash) ---
PREAMBLE="source /opt/ros/humble/setup.zsh && cd $REPO_DIR && source install/setup.zsh"

# --- Create tmux session ---
echo "=== Starting tmux session: $SESSION ==="

# Pane 0: RealSense D435 camera
tmux new-session -d -s "$SESSION" -n main
tmux send-keys -t "$SESSION:main" \
    "$PREAMBLE && echo '--- Starting D435 camera ---' && ros2 launch realsense2_camera rs_launch.py depth_module.profile:=640x480x30 rgb_camera.profile:=640x480x30 align_depth.enable:=true" Enter

sleep 3  # Wait for camera to initialize

# Pane 1: face_identity_node
tmux split-window -v -t "$SESSION:main"
tmux send-keys -t "$SESSION:main.1" \
    "$PREAMBLE && echo '--- Starting face_identity_node ---' && ros2 launch face_perception face_perception.launch.py" Enter

# Pane 2: foxglove_bridge
tmux split-window -v -t "$SESSION:main"
tmux send-keys -t "$SESSION:main.2" \
    "$PREAMBLE && echo '--- Starting foxglove_bridge ---' && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter

# Layout: even vertical split
tmux select-layout -t "$SESSION:main" even-vertical

echo ""
echo "=== Face identity pipeline started ==="
echo "  tmux attach -t $SESSION"
echo "  Foxglove: ws://<jetson-ip>:8765"
echo "  Topics:"
echo "    /state/perception/face"
echo "    /event/face_identity"
echo "    /face_identity/debug_image"
echo ""
echo "  Stop: bash scripts/clean_face_env.sh --all"
```

- [ ] **Step 5.3: chmod +x**

```bash
chmod +x scripts/start_face_identity_tmux.sh scripts/clean_face_env.sh
```

- [ ] **Step 5.4: Commit scripts**

```bash
git add scripts/start_face_identity_tmux.sh scripts/clean_face_env.sh
git commit -m "feat(face_perception): add tmux start and clean scripts

start_face_identity_tmux.sh: preflight + D435 + node + foxglove
clean_face_env.sh: kill face processes + tmux session

Agent 1: face recognition ROS2 integration"
```

---

## Task 6: Docs Update

**Files:**
- Modify: `docs/人臉辨識/README.md`

- [ ] **Step 6.1: 更新 `docs/人臉辨識/README.md`**

在「標準啟動」章節之前，新增 ROS2 package 啟動方式：

```markdown
## ROS2 Package 啟動（推薦）

```bash
# 前提：已 colcon build + source install/setup.zsh

# 一鍵啟動（camera + node + foxglove_bridge）
bash scripts/start_face_identity_tmux.sh

# 或手動 launch
ros2 launch face_perception face_perception.launch.py

# 自訂 config
ros2 launch face_perception face_perception.launch.py \
  config_file:=/path/to/custom.yaml

# 單獨啟動 node（不用 launch file）
ros2 run face_perception face_identity_node --ros-args \
  -p det_score_threshold:=0.35 \
  -p headless:=true
```

清場：

```bash
bash scripts/clean_face_env.sh --all
```

> **Fallback**：若 ROS2 package 有問題，原始 script 仍可用：
> `python3 scripts/face_identity_infer_cv.py --headless ...`
```

在文件最下方補一段：

```markdown
## ROS2 Package 結構

```
face_perception/
├── face_perception/
│   ├── __init__.py
│   └── face_identity_node.py    # 核心 node（from face_identity_infer_cv.py）
├── launch/
│   └── face_perception.launch.py
├── config/
│   └── face_perception.yaml     # Jetson operational defaults
├── test/
│   └── test_utilities.py
├── setup.py
└── package.xml
```

參數完整對照表見 [implementation plan](../superpowers/plans/2026-03-17-face-perception-package.md)。
```

- [ ] **Step 6.2: Commit docs**

```bash
git add docs/人臉辨識/README.md
git commit -m "docs(face_perception): update README with ROS2 package launch instructions

Agent 1: face recognition ROS2 integration"
```

---

## Task 7: Jetson Smoke Test Checklist

> 此 task 必須在 Jetson + D435 實機上執行。

- [ ] **Step 7.1: Build on Jetson**

```bash
cd /home/jetson/elder_and_dog
colcon build --packages-select face_perception
source install/setup.zsh
```

- [ ] **Step 7.2: 一鍵啟動**

```bash
bash scripts/start_face_identity_tmux.sh
tmux attach -t face_identity
```

Expected: 3 個 pane 都正常啟動，無 error。

- [ ] **Step 7.3: 驗證 topic 發布**

在另一個 terminal：

```bash
source /opt/ros/humble/setup.zsh
source install/setup.zsh

# 確認 topic 存在
ros2 topic list | grep -E "(face_identity|perception/face)"

# 確認 state topic 有資料（站在 D435 前面）
ros2 topic echo /state/perception/face --once

# 確認 event topic（走進 D435 視野觸發 track_started）
ros2 topic echo /event/face_identity --once

# 確認 debug image
ros2 topic hz /face_identity/debug_image
```

Expected:
- `/state/perception/face` 有 JSON 輸出，含 `face_count`、`tracks`
- `/event/face_identity` 有 `track_started` 事件
- `/face_identity/debug_image` 穩定 > 6 Hz

- [ ] **Step 7.4: 驗證 Foxglove 可看**

- 在 Foxglove 連線 `ws://<jetson-ip>:8765`
- 開 Image panel → `/face_identity/debug_image`
- 確認看到帶框影像
- 開 Raw Messages panel → `/state/perception/face`
- 確認看到 JSON state

- [ ] **Step 7.5: 驗證參數覆蓋**

```bash
# 確認 config yaml 生效
ros2 param get /face_identity_node det_score_threshold
# Expected: Double value is: 0.35 (from yaml, not code default 0.90)

ros2 param get /face_identity_node headless
# Expected: Boolean value is: True
```

- [ ] **Step 7.6: 驗證 identity_stable 事件**

讓已註冊的人站在 D435 前：

```bash
ros2 topic echo /event/face_identity
```

Expected: 看到 `event_type: identity_stable` + 正確的 `stable_name`。

- [ ] **Step 7.7: 驗證 clean script**

```bash
bash scripts/clean_face_env.sh --all
ros2 topic list | grep face
```

Expected: 無 face 相關 topic（node 已停）。

- [ ] **Step 7.8: 驗證 fallback（原 script 仍可用）**

```bash
python3 scripts/face_identity_infer_cv.py \
  --db-dir /home/jetson/face_db \
  --model-path /home/jetson/face_db/model_sface.pkl \
  --yunet-model /home/jetson/face_models/face_detection_yunet_legacy.onnx \
  --sface-model /home/jetson/face_models/face_recognition_sface_2021dec.onnx \
  --det-score-threshold 0.35 \
  --min-face-area-ratio 0.001 \
  --max-faces 5 \
  --publish-fps 8 \
  --no-publish-compare-image \
  --headless
```

Expected: 正常啟動、topic 有發。

- [ ] **Step 7.9: Commit（如果有任何 Jetson 上的修正）**

```bash
# 只加有改動的檔案，不要 git add -A
git add face_perception/ scripts/start_face_identity_tmux.sh scripts/clean_face_env.sh
git commit -m "fix(face_perception): Jetson smoke test fixes

Agent 1: face recognition ROS2 integration"
```

---

## 完成標準

| # | 項目 | 驗收方式 |
|---|------|---------|
| 1 | `ros2 launch face_perception face_perception.launch.py` 能起 | Jetson 實測 |
| 2 | `/state/perception/face` 有 JSON 輸出 | `ros2 topic echo` |
| 3 | `/event/face_identity` 有事件輸出 | `ros2 topic echo` |
| 4 | Foxglove 看得到 debug_image | Foxglove 連線 |
| 5 | 原 script 仍可當 fallback | `python3 scripts/face_identity_infer_cv.py` |
| 6 | `clean_face_env.sh --all` 能乾淨停掉 | 驗證無殘留 |
| 7 | unit tests 全 pass | `python3 -m pytest face_perception/test/ -v` |
