#!/usr/bin/env python3
import argparse
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
        self.shutting_down = False
        self.last_pub_err_ts = 0.0

        self.candidate_name = "unknown"
        self.candidate_hits = 0
        self.last_stable_name = "unknown"
        self.last_stable_sim = -1.0
        self.last_known_ts = 0.0

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

        self.create_subscription(Image, args.color_topic, self.cb_color, 10)
        self.create_subscription(Image, args.depth_topic, self.cb_depth, 10)
        self.timer = self.create_timer(0.05, self.tick)

        self.get_logger().info(
            f"Identity ready, people={sorted(self.model.get('centroids', {}).keys())}, "
            f"headless={self.headless}"
        )

    @staticmethod
    def pick_largest_face(faces: np.ndarray):
        if faces is None or len(faces) == 0:
            return None
        return max(faces, key=lambda row: float(row[2] * row[3]))

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

    def decide_stable_name(self, raw_name: str, raw_sim: float):
        now = time.time()
        if raw_sim >= self.args.sim_threshold_upper:
            proposed = raw_name
        elif raw_sim < self.args.sim_threshold_lower:
            proposed = "unknown"
        else:
            proposed = self.last_stable_name

        if proposed == self.candidate_name:
            self.candidate_hits += 1
        else:
            self.candidate_name = proposed
            self.candidate_hits = 1

        if self.candidate_hits >= self.args.stable_hits:
            self.last_stable_name = self.candidate_name
            self.last_stable_sim = raw_sim
            if self.last_stable_name != "unknown":
                self.last_known_ts = now

        if (
            self.last_stable_name != "unknown"
            and proposed == "unknown"
            and (now - self.last_known_ts) < self.args.unknown_grace_s
        ):
            return self.last_stable_name, max(raw_sim, self.last_stable_sim), "hold"

        return self.last_stable_name, max(raw_sim, self.last_stable_sim), "stable"

    def safe_publish(self, debug_img: np.ndarray, compare_img: np.ndarray):
        if self.shutting_down or not rclpy.ok():
            return
        try:
            self.debug_image_pub.publish(
                self.bridge.cv2_to_imgmsg(debug_img, encoding="bgr8")
            )
            self.compare_image_pub.publish(
                self.bridge.cv2_to_imgmsg(compare_img, encoding="bgr8")
            )
        except Exception as exc:  # noqa: BLE001
            now = time.time()
            if now - self.last_pub_err_ts >= 1.0:
                self.get_logger().warn(f"publish skipped: {exc}")
                self.last_pub_err_ts = now

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
        face = self.pick_largest_face(faces)

        lines = []
        if face is not None:
            x, y, fw, fh = face[:4].astype(np.int32)
            x = max(0, x)
            y = max(0, y)
            x2 = min(w, x + max(1, fw))
            y2 = min(h, y + max(1, fh))

            frame_area = float(color.shape[0] * color.shape[1])
            if ((x2 - x) * (y2 - y)) / frame_area >= self.args.min_face_area_ratio:
                emb = self.extract_embedding_from_crop(color, face)
                if emb is not None:
                    raw_name, raw_sim = self.predict_name(emb)
                    name, sim, mode = self.decide_stable_name(raw_name, raw_sim)

                    dist_txt = "N/A"
                    if depth is not None:
                        roi = depth[y:y2, x:x2]
                        valid = roi[(roi > 0) & (roi < 10000)]
                        if valid.size:
                            dist_txt = (
                                f"{float(np.median(valid)) * self.depth_scale:.2f}m"
                            )

                    label = f"{name} sim={sim:.2f} d={dist_txt} {mode}"
                    lines.append(label)

                    color_box = (0, 255, 0) if name != "unknown" else (0, 0, 255)
                    cv2.rectangle(color, (x, y), (x2, y2), color_box, 2)
                    cv2.putText(
                        color,
                        label,
                        (x, max(20, y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        color_box,
                        2,
                    )

        compare = cv2.hconcat([raw, color])
        self.safe_publish(color, compare)

        if self.headless:
            now = time.time()
            if now - self.last_log_ts >= 1.0:
                if len(lines) == 0:
                    self.get_logger().info("face_count=0")
                else:
                    self.get_logger().info(" | ".join(lines))
                cv2.imwrite("/tmp/face_identity_debug.jpg", color)
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
