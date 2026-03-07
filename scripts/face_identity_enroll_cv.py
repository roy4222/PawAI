#!/usr/bin/env python3
import argparse
import os
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


class FaceEnrollNode(Node):
    def __init__(self, args):
        super().__init__("face_identity_enroll_cv")
        self.args = args
        self.bridge = CvBridge()
        self.headless = not bool(os.environ.get("DISPLAY")) or args.headless

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

        self.person_dir = Path(args.output_dir) / args.person_name
        self.person_dir.mkdir(parents=True, exist_ok=True)

        self.saved = 0
        self.last_save_ts = 0.0
        self.last_preview_ts = 0.0

        self.create_subscription(Image, args.color_topic, self.cb_color, 10)
        self.debug_image_pub = self.create_publisher(
            Image, "/face_enroll/debug_image", 10
        )

        self.get_logger().info(f"Enroll person={args.person_name}")
        self.get_logger().info(f"Output dir={self.person_dir}")
        self.get_logger().info(f"Headless={self.headless}")

    @staticmethod
    def pick_largest_face(faces: np.ndarray):
        if faces is None or len(faces) == 0:
            return None
        return max(faces, key=lambda row: float(row[2] * row[3]))

    def cb_color(self, msg):
        if self.saved >= self.args.samples:
            self.get_logger().info("Target samples reached, shutting down")
            rclpy.shutdown()
            return

        img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        draw = img.copy()
        h, w = img.shape[:2]

        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)

        if faces is None or len(faces) == 0:
            cv2.putText(
                draw,
                f"captured={self.saved}/{self.args.samples}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )
            self.debug_image_pub.publish(
                self.bridge.cv2_to_imgmsg(draw, encoding="bgr8")
            )
            now = time.time()
            if self.headless and now - self.last_preview_ts >= 1.0:
                cv2.imwrite("/tmp/face_enroll_debug.jpg", draw)
                self.last_preview_ts = now
            if not self.headless:
                cv2.imshow("face_enroll", draw)
                cv2.waitKey(1)
            return

        face = self.pick_largest_face(faces)
        if face is None:
            return

        x, y, fw, fh = face[:4].astype(np.int32)
        x = max(0, x)
        y = max(0, y)
        x2 = min(w, x + max(1, fw))
        y2 = min(h, y + max(1, fh))

        aligned = self.recognizer.alignCrop(img, face)
        if aligned is None or aligned.size == 0:
            return
        aligned = cv2.resize(aligned, (112, 112), interpolation=cv2.INTER_AREA)

        now = time.time()
        cv2.rectangle(draw, (x, y), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            draw,
            f"captured={self.saved}/{self.args.samples}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

        if now - self.last_save_ts >= self.args.capture_interval:
            out_file = self.person_dir / f"{self.args.person_name}_{self.saved:04d}.png"
            cv2.imwrite(str(out_file), aligned)
            self.saved += 1
            self.last_save_ts = now
            self.get_logger().info(
                f"saved {out_file} ({self.saved}/{self.args.samples})"
            )

        self.debug_image_pub.publish(self.bridge.cv2_to_imgmsg(draw, encoding="bgr8"))
        if self.headless and now - self.last_preview_ts >= 1.0:
            cv2.imwrite("/tmp/face_enroll_debug.jpg", draw)
            self.last_preview_ts = now

        if not self.headless:
            cv2.imshow("face_enroll", draw)
            cv2.waitKey(1)


def parse_args():
    p = argparse.ArgumentParser(description="Enroll face samples from ROS2 color topic")
    p.add_argument("--person-name", required=True)
    p.add_argument("--samples", type=int, default=30)
    p.add_argument("--capture-interval", type=float, default=0.25)
    p.add_argument("--output-dir", default="/home/jetson/face_db")
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
    p.add_argument("--color-topic", default="/camera/camera/color/image_raw")
    p.add_argument("--headless", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    rclpy.init()
    node = FaceEnrollNode(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
