#!/usr/bin/env python3
import argparse
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
    def __init__(self, args):
        super().__init__("face_identity_infer_cv")
        self.args = args
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.headless = not bool(os.environ.get("DISPLAY")) or args.headless
        self.last_log_ts = 0.0
        self.last_publish_ts = 0.0
        self.shutting_down = False
        self.last_pub_err_ts = 0.0
        self.publish_period = 1.0 / max(0.1, float(args.publish_fps))
        self.publish_compare_image = not bool(args.no_publish_compare_image)

        self.next_track_id = 1
        self.tracks = {}
        self.track_states = {}

        self.color = None
        self.depth = None
        self.depth_scale = 0.001

        if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
            raise RuntimeError(
                "OpenCV build does not support FaceDetectorYN/FaceRecognizerSF; "
                "please install OpenCV >= 4.8 with face module"
            )

        yunet_model = resolve_model_path(args.yunet_model, "YuNet")
        sface_model = resolve_model_path(args.sface_model, "SFace")

        self.detector = cv2.FaceDetectorYN.create(
            str(yunet_model),
            "",
            (320, 320),
            args.det_score_threshold,
            args.det_nms_threshold,
            args.det_top_k,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(sface_model), "")

        self.model_path = Path(args.model_path)
        current_counts = compute_db_counts(Path(args.db_dir))
        if self.model_path.exists():
            with self.model_path.open("rb") as f:
                self.model = pickle.load(f)
            stored_counts = self.model.get("counts", {})
            if stored_counts != current_counts:
                self.get_logger().info(
                    "Enrollment DB changed; retraining model "
                    f"(stored={stored_counts}, current={current_counts})"
                )
                self.model = self.train_model(Path(args.db_dir))
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                with self.model_path.open("wb") as wf:
                    pickle.dump(self.model, wf)
                self.get_logger().info(
                    f"Retrained and saved model to {self.model_path}"
                )
            else:
                self.get_logger().info(f"Loaded model from {self.model_path}")
        else:
            self.model = self.train_model(Path(args.db_dir))
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with self.model_path.open("wb") as f:
                pickle.dump(self.model, f)
            self.get_logger().info(f"Trained and saved model to {self.model_path}")

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

        self.create_subscription(Image, args.color_topic, self.cb_color, 10)
        self.create_subscription(Image, args.depth_topic, self.cb_depth, 10)
        self.timer = self.create_timer(args.tick_period, self.tick)

        self.get_logger().info(
            f"Identity ready, people={sorted(self.model.get('centroids', {}).keys())}, "
            f"headless={self.headless}"
        )

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

            if best_track_id is not None and best_iou >= self.args.track_iou_threshold:
                track_id = best_track_id
                self.tracks[track_id]["bbox"] = bbox
                self.tracks[track_id]["misses"] = 0
            else:
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracks[track_id] = {"bbox": bbox, "misses": 0}
                self._publish_face_event(
                    "track_started", track_id, "unknown", 0.0, None)

            used_tracks.add(track_id)
            assigned.append((track_id, det))

        drop_ids = []
        for track_id, track in self.tracks.items():
            if track_id in used_tracks:
                continue
            track["misses"] += 1
            if track["misses"] > self.args.track_max_misses:
                drop_ids.append(track_id)

        for track_id in drop_ids:
            lost_state = self.track_states.get(track_id, {})
            self._publish_face_event(
                "track_lost", track_id,
                lost_state.get("last_stable_name", "unknown"),
                max(0.0, lost_state.get("last_stable_sim", 0.0)),
                None,
            )
            self.tracks.pop(track_id, None)
            self.track_states.pop(track_id, None)

        return assigned

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

    def cb_color(self, msg):
        with self.lock:
            self.color = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def cb_depth(self, msg):
        with self.lock:
            self.depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

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
        if raw_sim >= self.args.sim_threshold_upper:
            proposed = raw_name
        elif raw_sim < self.args.sim_threshold_lower:
            proposed = "unknown"
        else:
            proposed = state["last_stable_name"]

        if proposed == state["candidate_name"]:
            state["candidate_hits"] += 1
        else:
            state["candidate_name"] = proposed
            state["candidate_hits"] = 1

        if state["candidate_hits"] >= self.args.stable_hits:
            state["last_stable_name"] = state["candidate_name"]
            state["last_stable_sim"] = raw_sim
            if state["last_stable_name"] != "unknown":
                state["last_known_ts"] = now

        if (
            state["last_stable_name"] != "unknown"
            and proposed == "unknown"
            and (now - state["last_known_ts"]) < self.args.unknown_grace_s
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
        msg.data = json.dumps({
            "stamp": time.time(),
            "event_type": event_type,
            "track_id": track_id,
            "stable_name": stable_name,
            "sim": round(sim, 4),
            "distance_m": distance_m,
        })
        self.face_event_pub.publish(msg)

    def close(self):
        self.shutting_down = True
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()

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
            if self.args.max_faces > 0:
                face_rows = face_rows[: self.args.max_faces]

            frame_area = float(color.shape[0] * color.shape[1])
            for face_row in face_rows:
                bbox = self.to_bbox(face_row, w, h)
                if bbox is None:
                    continue
                x1, y1, x2, y2 = bbox
                if ((x2 - x1) * (y2 - y1)) / frame_area < self.args.min_face_area_ratio:
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
                        float(np.median(valid)) * self.depth_scale, 3)
                    dist_txt = f"{distance_m:.2f}m"

            new_stable_name = ts["last_stable_name"]
            if old_stable_name != new_stable_name:
                if old_stable_name == "unknown":
                    self._publish_face_event(
                        "identity_stable", track_id,
                        new_stable_name, sim, distance_m)
                else:
                    self._publish_face_event(
                        "identity_changed", track_id,
                        new_stable_name, sim, distance_m)

            tick_track_info[track_id] = {
                "track_id": track_id,
                "stable_name": ts["last_stable_name"],
                "sim": round(max(0.0, ts["last_stable_sim"]), 4),
                "distance_m": distance_m,
                "bbox": [x1, y1, x2, y2],
                "mode": "stable" if ts["last_stable_name"] != "unknown" else "hold",
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

        state_tracks = []
        for tid, track in self.tracks.items():
            if tid in tick_track_info:
                state_tracks.append(tick_track_info[tid])
            else:
                ts = self.track_states.get(tid, {})
                state_tracks.append({
                    "track_id": tid,
                    "stable_name": ts.get("last_stable_name", "unknown"),
                    "sim": round(max(0.0, ts.get("last_stable_sim", 0.0)), 4),
                    "distance_m": None,
                    "bbox": list(track["bbox"]),
                    "mode": "stable" if ts.get("last_stable_name", "unknown") != "unknown" else "hold",
                })
        face_state_msg = String()
        face_state_msg.data = json.dumps({
            "stamp": time.time(),
            "face_count": len(self.tracks),
            "tracks": state_tracks,
        })
        self.face_state_pub.publish(face_state_msg)

        if self.headless:
            now = time.time()
            if now - self.last_log_ts >= 1.0:
                if len(lines) == 0:
                    self.get_logger().info(f"face_count={face_count}")
                else:
                    self.get_logger().info(
                        f"face_count={face_count} | " + " | ".join(lines)
                    )
                if self.args.save_debug_jpeg:
                    cv2.imwrite("/tmp/face_identity_debug.jpg", color)
                    if compare is not None:
                        cv2.imwrite("/tmp/face_identity_compare.jpg", compare)
                self.last_log_ts = now
            return

        cv2.imshow("face_identity_infer_cv", color)
        cv2.waitKey(1)


def parse_args():
    p = argparse.ArgumentParser(
        description="Real-time face identity inference (YuNet + SFace baseline)"
    )
    p.add_argument("--db-dir", default="/home/jetson/face_db")
    p.add_argument("--model-path", default="/home/jetson/face_db/model_sface.pkl")
    p.add_argument(
        "--yunet-model",
        default="/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
    )
    p.add_argument(
        "--sface-model",
        default="/home/jetson/face_models/face_recognition_sface_2021dec.onnx",
    )
    p.add_argument("--det-score-threshold", type=float, default=0.90)
    p.add_argument("--det-nms-threshold", type=float, default=0.30)
    p.add_argument("--det-top-k", type=int, default=5000)
    p.add_argument("--sim-threshold-upper", type=float, default=0.35)
    p.add_argument("--sim-threshold-lower", type=float, default=0.25)
    p.add_argument("--stable-hits", type=int, default=3)
    p.add_argument("--unknown-grace-s", type=float, default=1.2)
    p.add_argument("--min-face-area-ratio", type=float, default=0.02)
    p.add_argument("--max-faces", type=int, default=5)
    p.add_argument("--track-iou-threshold", type=float, default=0.3)
    p.add_argument("--track-max-misses", type=int, default=10)
    p.add_argument("--publish-fps", type=float, default=8.0)
    p.add_argument("--tick-period", type=float, default=0.05)
    p.add_argument("--no-publish-compare-image", action="store_true")
    p.add_argument("--save-debug-jpeg", action="store_true")
    p.add_argument("--color-topic", default="/camera/camera/color/image_raw")
    p.add_argument(
        "--depth-topic", default="/camera/camera/aligned_depth_to_color/image_raw"
    )
    p.add_argument("--headless", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    rclpy.init()
    node = FaceIdentityNode(args)
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
