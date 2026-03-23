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
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
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

        # --- Subscriptions (BEST_EFFORT to match D435 ROS2 driver QoS) ---
        image_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )
        self.create_subscription(Image, color_topic, self.cb_color, image_qos)
        self.create_subscription(Image, depth_topic, self.cb_depth, image_qos)
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
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
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
                        "bbox": [int(v) for v in track["bbox"]],
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
