#!/usr/bin/env python3
"""pose_backend_probe — YOLO26-pose vs MediaPipe Pose 的 sit/stand A/B 工具（Jetson 上跑）。

不動 vision_perception node，直接訂 D435 color topic（或吃單張圖），
同一幀分別餵 YOLO26n-pose ONNX 與（可選）MediaPipe Pose，
都走同一顆 pose_classifier.classify_pose 分類，逐幀並排印出結果。
給 Roy 上機判斷「pose 換不換模型」用（6/10 demo 修法 #4 的決策數據）。

用法（Jetson，先 source install/setup.zsh 讓 vision_perception 可 import）:
  # ROS 模式：訂 camera topic 跑 15 秒（demo stack 的 D435 已在跑時直接用）
  python3 scripts/pose_backend_probe.py --duration 15 --both

  # 單張圖模式（離線驗證）
  python3 scripts/pose_backend_probe.py --image /tmp/frame.jpg --both

  # 模型路徑（預設找 /home/jetson/models/yolo26n-pose_640.onnx）
  python3 scripts/pose_backend_probe.py --model ~/models/yolo26n-pose_640.onnx

輸出每幀一行:
  [yolo ] det=0.87 kp_avg=0.64 raw=sitting(0.64) two_class=sitting
  [mp   ] kp_avg=0.41 raw=None(0.00) two_class=None
"""
from __future__ import annotations

import argparse
import sys
import time

import cv2
import numpy as np

# 與 vision_perception_node 的 demo two-class 映射一致（Roy 6/9 拍板：
# 腳稍彎/蹲/彎=坐、只看 sit/stand；fallen 不在 demo 範圍）。
COARSE_TWO_CLASS = {
    "sitting": "sitting",
    "crouching": "sitting",
    "knee_kneel": "sitting",
    "bending": "sitting",
    "standing": "standing",
    "akimbo": "standing",
}


def letterbox(img, new_shape=640):
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
    top = (new_shape - nh) // 2
    left = (new_shape - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, scale, left, top


class YoloPoseBackend:
    """YOLO26n-pose end2end ONNX — output (1, 300, 57) = [x1,y1,x2,y2,conf,cls, 17*(x,y,v)]."""

    def __init__(self, model_path: str, imgsz: int, min_conf: float):
        import onnxruntime as ort

        providers = []
        avail = ort.get_available_providers()
        if "TensorrtExecutionProvider" in avail:
            providers.append(("TensorrtExecutionProvider", {
                "trt_engine_cache_enable": "True",
                "trt_engine_cache_path": "/tmp/trt_cache_pose_probe",
                "trt_fp16_enable": "True",
            }))
        if "CUDAExecutionProvider" in avail:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")
        self.sess = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.sess.get_inputs()[0].name
        self.imgsz = imgsz
        self.min_conf = min_conf
        print(f"[yolo ] session ready providers={self.sess.get_providers()}", flush=True)

    def detect(self, image_bgr):
        """Return ((kps(17,2) px, scores(17,), det_conf, bbox w/h), infer_ms)；無人 → (None, ms)."""
        canvas, scale, pad_left, pad_top = letterbox(image_bgr, self.imgsz)
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        blob = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis, ...]
        t0 = time.time()
        out = self.sess.run(None, {self.input_name: blob})[0][0]  # (300, 57)
        infer_ms = (time.time() - t0) * 1000.0
        best = None
        for row in out:
            conf = float(row[4])
            if conf < self.min_conf:
                continue
            if best is None or conf > best[4]:
                best = row
        if best is None:
            return None, infer_ms
        x1, y1, x2, y2 = best[:4]
        kpts = best[6:6 + 51].reshape(17, 3)
        kps = np.zeros((17, 2), np.float32)
        kps[:, 0] = (kpts[:, 0] - pad_left) / scale
        kps[:, 1] = (kpts[:, 1] - pad_top) / scale
        scores = kpts[:, 2].astype(np.float32)
        bw = max(1.0, (x2 - x1) / scale)
        bh = max(1.0, (y2 - y1) / scale)
        return (kps, scores, float(best[4]), bw / bh), infer_ms


def classify_and_format(tag, kps, scores, bbox_ratio, image_height, det_conf=None, infer_ms=None):
    from vision_perception.pose_classifier import classify_pose

    raw, conf = classify_pose(kps, scores, bbox_ratio, image_height=image_height)
    two = COARSE_TWO_CLASS.get(raw) if raw else None
    kp_avg = float(np.mean(scores)) if scores is not None else 0.0
    parts = [f"[{tag:<5}]"]
    if det_conf is not None:
        parts.append(f"det={det_conf:.2f}")
    parts.append(f"kp_avg={kp_avg:.2f}")
    parts.append(f"raw={raw}({conf:.2f})")
    parts.append(f"two_class={two}")
    if infer_ms is not None:
        parts.append(f"{infer_ms:.0f}ms")
    return " ".join(parts)


def run_on_frame(frame, yolo, mp_pose):
    h = float(frame.shape[0])
    lines = []
    if yolo is not None:
        det, infer_ms = yolo.detect(frame)
        if det is None:
            lines.append(f"[yolo ] no person >= min_conf ({infer_ms:.0f}ms)")
        else:
            kps, scores, conf, ratio = det
            lines.append(classify_and_format("yolo", kps, scores, ratio, h, conf, infer_ms))
    if mp_pose is not None:
        t0 = time.time()
        kps, scores = mp_pose.detect(frame)
        infer_ms = (time.time() - t0) * 1000.0
        if not np.any(scores):
            lines.append(f"[mp   ] no person ({infer_ms:.0f}ms)")
        else:
            lines.append(classify_and_format("mp", kps, scores, None, h, None, infer_ms))
    print("  ".join(lines), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="/home/jetson/models/yolo26n-pose_640.onnx")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--min-conf", type=float, default=0.35, help="person det conf floor")
    ap.add_argument("--image", default=None, help="single-image mode (skip ROS)")
    ap.add_argument("--topic", default="/camera/camera/color/image_raw")
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--hz", type=float, default=5.0, help="probe rate in ROS mode")
    ap.add_argument("--both", action="store_true", help="also run MediaPipe Pose side-by-side")
    args = ap.parse_args()

    yolo = YoloPoseBackend(args.model, args.imgsz, args.min_conf)
    mp_pose = None
    if args.both:
        from vision_perception.mediapipe_pose import MediaPipePose
        mp_pose = MediaPipePose(complexity=0, min_confidence=0.5)

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"cannot read {args.image}", file=sys.stderr)
            sys.exit(1)
        run_on_frame(frame, yolo, mp_pose)
        return

    import rclpy
    from cv_bridge import CvBridge
    from rclpy.node import Node as RclpyNode
    from sensor_msgs.msg import Image

    class Probe(RclpyNode):
        def __init__(self):
            super().__init__("pose_backend_probe")
            self.bridge = CvBridge()
            self.frame = None
            self.create_subscription(Image, args.topic, self._cb, 1)

        def _cb(self, msg):
            self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    rclpy.init()
    node = Probe()
    deadline = time.time() + args.duration
    period = 1.0 / max(0.5, args.hz)
    next_t = time.time()
    try:
        while time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if node.frame is not None and time.time() >= next_t:
                run_on_frame(node.frame, yolo, mp_pose)
                next_t = time.time() + period
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
