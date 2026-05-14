"""object_perception_node — YOLO26n ONNX object detection on D435 RGB."""

import json
import threading
import time

import cv2
import numpy as np
import rclpy
from rcl_interfaces.msg import ParameterDescriptor, ParameterType
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String

from object_perception.coco_classes import (
    COCO_CLASSES,
    COLOR_ZH,
    class_color,
    class_name_zh,
)

# CJK font lookup for debug overlay — cv2.putText cannot render zh-TW.
# Use PIL with a system Noto/CJK font; cache the truetype handle once.
try:
    from PIL import Image as PILImage, ImageDraw, ImageFont  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover — Pillow ships with most ROS2 setups
    _PIL_AVAILABLE = False

_CJK_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",  # macOS dev box fallback
)


def _resolve_cjk_font(size: int = 16):
    """Return a PIL ImageFont supporting CJK, or None if no font found."""
    if not _PIL_AVAILABLE:
        return None
    import os
    for path in _CJK_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


# ----------------------------------------------------------------------
# 5/6: HSV 12-colour analysis on bbox crop. Per-pixel classification with
# V/S gates (so brown / black / white / gray work — they need value, not
# just hue). OpenCV HSV ranges: H ∈ [0,180], S ∈ [0,255], V ∈ [0,255].
# Returns peak colour + (peak_pixels / total_pixels).
#
# Classification priority (mutually exclusive masks):
#   1. black   V < 50
#   2. white   S < 40 AND V ≥ 200
#   3. gray    S < 40 AND 50 ≤ V < 200
#   4. brown   warm hue (5..25) AND V < 130 (chromatic & dark)
#   5. pink    red side (H ≥ 160 OR ≤ 5) AND S < 150 AND V ≥ 180
#              OR magenta band (150 < H < 165)
#   6. red     H ≤ 8 OR H ≥ 165
#   7. orange  8 < H ≤ 22
#   8. yellow  22 < H ≤ 35
#   9. green   35 < H ≤ 85
#  10. cyan    85 < H ≤ 100
#  11. blue    100 < H ≤ 130
#  12. purple  130 < H ≤ 150
#
# Returns ("Unknown", 0.0) if peak / total < 0.25 (too fragmented to
# commit) — protects against speckled / multi-coloured surfaces.
# Module-level (vs class staticmethod) so unit tests can import without
# pulling in rclpy. ObjectPerceptionNode._analyze_bbox_color delegates here.
# ----------------------------------------------------------------------
def analyze_bbox_color(image_bgr, x1: int, y1: int, x2: int, y2: int) -> tuple[str, float]:
    h, w = image_bgr.shape[:2]
    x1c = max(0, min(x1, w - 1))
    x2c = max(0, min(x2, w))
    y1c = max(0, min(y1, h - 1))
    y2c = max(0, min(y2, h))
    if x2c <= x1c or y2c <= y1c:
        return ("Unknown", 0.0)
    crop = image_bgr[y1c:y2c, x1c:x2c]
    if crop.size == 0:
        return ("Unknown", 0.0)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    H = hsv[..., 0]
    S = hsv[..., 1]
    V = hsv[..., 2]

    # Achromatic gates first.
    m_black = V < 50
    m_white = (S < 40) & (V >= 200) & ~m_black
    m_gray = (S < 40) & ~m_black & ~m_white
    chromatic = ~(m_black | m_white | m_gray)

    # Brown — warm hue (orange-yellow) with low V. Subset of chromatic.
    m_brown = chromatic & (H >= 5) & (H <= 25) & (V < 130)
    rest = chromatic & ~m_brown

    # Pink — red-magenta side, lighter / less saturated than red.
    m_pink_red_side = rest & ((H >= 160) | (H <= 5)) & (S < 150) & (V >= 180)
    m_pink_magenta = rest & (H > 150) & (H < 165)
    m_pink = m_pink_red_side | m_pink_magenta
    rest = rest & ~m_pink

    m_red = rest & ((H <= 8) | (H >= 165))
    m_orange = rest & (H > 8) & (H <= 22)
    m_yellow = rest & (H > 22) & (H <= 35)
    m_green = rest & (H > 35) & (H <= 85)
    m_cyan = rest & (H > 85) & (H <= 100)
    m_blue = rest & (H > 100) & (H <= 130)
    m_purple = rest & (H > 130) & (H <= 150)

    masks = {
        "black": m_black, "white": m_white, "gray": m_gray,
        "brown": m_brown, "pink": m_pink,
        "red": m_red, "orange": m_orange, "yellow": m_yellow,
        "green": m_green, "cyan": m_cyan, "blue": m_blue, "purple": m_purple,
    }
    counts = {k: int(m.sum()) for k, m in masks.items()}
    total = float(sum(counts.values()))
    if total <= 0:
        return ("Unknown", 0.0)
    peak = max(counts, key=counts.get)
    ratio = counts[peak] / total
    if ratio < 0.25:
        return ("Unknown", 0.0)
    return (peak, round(float(ratio), 3))


class ObjectPerceptionNode(Node):
    def __init__(self):
        super().__init__("object_perception_node")

        # --- Parameters ---
        self.declare_parameter("model_path", "/home/jetson/models/yolo26n.onnx")
        self.declare_parameter("trt_cache_dir", "/home/jetson/trt_cache/")
        self.declare_parameter("color_topic", "/camera/camera/color/image_raw")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("input_size", 640)
        self.declare_parameter("tick_period", 0.067)
        self.declare_parameter("publish_fps", 8.0)
        self.declare_parameter("class_cooldown_sec", 5.0)
        # Empty list default needs explicit type descriptor (rclpy can't infer from [])
        self.declare_parameter(
            "class_whitelist",
            [],
            ParameterDescriptor(
                type=ParameterType.PARAMETER_INTEGER_ARRAY,
                description="COCO class IDs to detect; empty = all 80 classes",
            ),
        )

        model_path = str(self.get_parameter("model_path").value)
        trt_cache_dir = str(self.get_parameter("trt_cache_dir").value)
        color_topic = str(self.get_parameter("color_topic").value)
        self.conf_thresh = float(self.get_parameter("confidence_threshold").value)
        self.input_size = int(self.get_parameter("input_size").value)
        tick_period = float(self.get_parameter("tick_period").value)
        publish_fps = float(self.get_parameter("publish_fps").value)
        self.class_cooldown = float(self.get_parameter("class_cooldown_sec").value)

        wl = list(self.get_parameter("class_whitelist").value or [])
        self.allowed_classes: set = set(int(i) for i in wl) if wl else set(COCO_CLASSES.keys())

        self.publish_period = 1.0 / max(1.0, publish_fps)
        self.last_publish_ts = 0.0

        # --- ONNX session ---
        self.session = None
        self.input_name = None
        self._init_onnx(model_path, trt_cache_dir)

        # --- State ---
        self.lock = threading.Lock()
        self.color = None
        self.shutting_down = False

        # Dedup: class_name → last_event_time
        self._cooldowns: dict = {}
        # FPS tracking
        self._tick_times: list = []
        # Cache a CJK font handle so PIL doesn't re-open the .ttc every frame.
        self._zh_font = _resolve_cjk_font(size=18)
        if self._zh_font is None:
            self.get_logger().warning(
                "No CJK font found — debug overlay will fall back to English class names",
                once=True,
            )

        # --- Camera subscription ---
        from cv_bridge import CvBridge

        self.bridge = CvBridge()
        image_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )
        self.create_subscription(Image, color_topic, self._cb_color, image_qos)

        # --- Publishers ---
        self.event_pub = self.create_publisher(String, "/event/object_detected", 10)
        self.debug_pub = self.create_publisher(
            Image, "/perception/object/debug_image", 1
        )

        # --- Timer ---
        self.timer = self.create_timer(tick_period, self._tick)

        wl_desc = (
            f"全部 {len(self.allowed_classes)} class"
            if len(self.allowed_classes) == len(COCO_CLASSES)
            else f"{len(self.allowed_classes)} class whitelist: {sorted(self.allowed_classes)}"
        )
        self.get_logger().info(
            f"ObjectPerceptionNode started — model={model_path}, "
            f"conf={self.conf_thresh}, tick={tick_period:.3f}s, "
            f"publish_fps={publish_fps}, {wl_desc}"
        )

    # ------------------------------------------------------------------
    # ONNX init
    # ------------------------------------------------------------------
    def _init_onnx(self, model_path: str, trt_cache_dir: str):
        try:
            import onnxruntime as ort

            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            providers = [
                (
                    "TensorrtExecutionProvider",
                    {
                        "trt_engine_cache_enable": "True",
                        "trt_engine_cache_path": trt_cache_dir,
                        "trt_fp16_enable": "True",
                    },
                ),
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
            self.get_logger().warn(
                "Loading ONNX model (first launch TRT cache build may take 3-10 min)..."
            )
            self.session = ort.InferenceSession(
                model_path, sess_options, providers=providers
            )
            self.input_name = self.session.get_inputs()[0].name
            active = self.session.get_providers()
            self.get_logger().info(f"ONNX session ready — providers: {active}")
        except Exception as e:
            self.get_logger().error(f"Failed to load ONNX model: {e}")
            self.session = None

    # ------------------------------------------------------------------
    # Camera callback
    # ------------------------------------------------------------------
    def _cb_color(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warning(
                f"imgmsg_to_cv2 failed: {e}", throttle_duration_sec=5.0
            )
            return
        with self.lock:
            self.color = frame

    # ------------------------------------------------------------------
    # Letterbox preprocessing
    # ------------------------------------------------------------------
    @staticmethod
    def letterbox(img, new_shape=640):
        h, w = img.shape[:2]
        scale = min(new_shape / h, new_shape / w)
        nh, nw = int(h * scale), int(w * scale)
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
        top = (new_shape - nh) // 2
        left = (new_shape - nw) // 2
        canvas[top : top + nh, left : left + nw] = resized
        return canvas, scale, left, top

    # ------------------------------------------------------------------
    # Post-process: reverse letterbox coords
    # ------------------------------------------------------------------
    @staticmethod
    def rescale_bbox(x1, y1, x2, y2, scale, pad_left, pad_top, orig_w, orig_h):
        x1 = int(max(0, min((x1 - pad_left) / scale, orig_w - 1)))
        y1 = int(max(0, min((y1 - pad_top) / scale, orig_h - 1)))
        x2 = int(max(0, min((x2 - pad_left) / scale, orig_w - 1)))
        y2 = int(max(0, min((y2 - pad_top) / scale, orig_h - 1)))
        return x1, y1, x2, y2

    @staticmethod
    def _analyze_bbox_color(image_bgr, x1: int, y1: int, x2: int, y2: int) -> tuple[str, float]:
        return analyze_bbox_color(image_bgr, x1, y1, x2, y2)

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------
    def _tick(self):
        if self.shutting_down or self.session is None:
            return

        with self.lock:
            image = self.color.copy() if self.color is not None else None
        if image is None:
            return

        tick_start = time.monotonic()
        orig_h, orig_w = image.shape[:2]

        # --- Preprocess ---
        canvas, scale, pad_left, pad_top = self.letterbox(image, self.input_size)
        blob = canvas.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]  # (1,3,640,640)

        # --- Inference ---
        try:
            outputs = self.session.run(None, {self.input_name: blob})
        except Exception as e:
            self.get_logger().warning(
                f"Inference failed: {e}", throttle_duration_sec=5.0
            )
            return

        # --- Post-process: (1,300,6) → filter ---
        raw = outputs[0][0]  # (300, 6): x1, y1, x2, y2, conf, class_id
        detections = []
        for det in raw:
            conf = float(det[4])
            if conf < self.conf_thresh:
                continue
            class_id = int(det[5])
            if class_id not in self.allowed_classes:
                continue
            if class_id not in COCO_CLASSES:
                continue  # unexpected id (shouldn't happen for YOLO26n 0-79)
            x1, y1, x2, y2 = self.rescale_bbox(
                det[0], det[1], det[2], det[3],
                scale, pad_left, pad_top, orig_w, orig_h,
            )
            if x2 <= x1 or y2 <= y1:
                continue
            color, color_conf = self._analyze_bbox_color(image, x1, y1, x2, y2)
            detections.append({
                "class_id": class_id,  # internal-only, stripped before event publish
                "class_name": COCO_CLASSES[class_id],
                "confidence": round(conf, 3),
                "bbox": [x1, y1, x2, y2],
                "color": color,
                "color_confidence": color_conf,
            })

        # --- FPS tracking ---
        tick_end = time.monotonic()
        self._tick_times.append(tick_end - tick_start)
        if len(self._tick_times) > 60:
            self._tick_times = self._tick_times[-60:]

        # --- Dedup + Event publish ---
        self._publish_events(detections)

        # --- Debug image (rate-limited) ---
        now = time.time()
        if now - self.last_publish_ts >= self.publish_period:
            self.last_publish_ts = now
            self._publish_debug_image(image, detections)

    # ------------------------------------------------------------------
    # Event publishing with per-class cooldown dedup
    # ------------------------------------------------------------------
    def _publish_events(self, detections: list):
        now = time.time()
        # Collect new classes that pass cooldown (strip internal class_id from payload).
        # 5/5: include optional `color` + `color_confidence` from HSV analysis.
        new_objects = []
        for det in detections:
            cls = det["class_name"]
            last = self._cooldowns.get(cls, 0.0)
            if now - last >= self.class_cooldown:
                obj = {
                    "class_name": det["class_name"],
                    "confidence": det["confidence"],
                    "bbox": det["bbox"],
                }
                if det.get("color") and det["color"] != "Unknown":
                    obj["color"] = det["color"]
                    obj["color_confidence"] = det.get("color_confidence", 0.0)
                new_objects.append(obj)
                self._cooldowns[cls] = now

        if not new_objects:
            return

        msg = String()
        msg.data = json.dumps({
            "stamp": now,
            "event_type": "object_detected",
            "objects": new_objects,
        })
        self.event_pub.publish(msg)

    # ------------------------------------------------------------------
    # Debug image overlay
    # ------------------------------------------------------------------
    def _publish_debug_image(self, image: np.ndarray, detections: list):
        debug = image.copy()
        # Pre-build label strings + draw bboxes via cv2 (fast).
        # Text rendering happens in a single PIL pass at the end (CJK requires PIL).
        labels: list[tuple[int, int, str, tuple[int, int, int]]] = []
        for det in detections:
            class_id = det.get("class_id", 0)
            x1, y1, x2, y2 = det["bbox"]
            box_color = class_color(class_id)
            cv2.rectangle(debug, (x1, y1), (x2, y2), box_color, 2)

            class_zh = class_name_zh(class_id)
            color_str = det.get("color")
            parts: list[str] = []
            if color_str and color_str != "Unknown":
                parts.append(COLOR_ZH.get(color_str, color_str))
            parts.append(class_zh)
            label = " ".join(parts) + f" {det['confidence']:.2f}"
            labels.append((x1, y1, label, box_color))

        if labels and self._zh_font is not None:
            pil_img = PILImage.fromarray(cv2.cvtColor(debug, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img)
            for x1, y1, label, box_color in labels:
                # PIL text bbox for label background sizing
                left, top, right, bottom = draw.textbbox((x1, y1), label, font=self._zh_font)
                tw = right - left
                th = bottom - top
                bg_top = max(0, y1 - th - 6)
                # Note: PIL uses RGB; box_color is BGR — flip.
                rgb_bg = (box_color[2], box_color[1], box_color[0])
                draw.rectangle((x1, bg_top, x1 + tw + 4, y1), fill=rgb_bg)
                draw.text((x1 + 2, bg_top), label, font=self._zh_font, fill=(255, 255, 255))
            debug = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        elif labels:
            # No CJK font — fall back to ASCII class_name + color english
            for x1, y1, label, box_color in labels:
                ascii_label = label.encode("ascii", errors="ignore").decode() or "obj"
                (tw, th), _ = cv2.getTextSize(ascii_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(debug, (x1, y1 - th - 6), (x1 + tw, y1), box_color, -1)
                cv2.putText(
                    debug, ascii_label, (x1, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                )

        # FPS + detection count overlay
        avg_ms = (
            sum(self._tick_times) / len(self._tick_times) * 1000
            if self._tick_times
            else 0
        )
        fps = 1000.0 / avg_ms if avg_ms > 0 else 0
        info = f"FPS: {fps:.1f} | Det: {len(detections)}"
        cv2.putText(
            debug, info, (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
        )

        try:
            self.debug_pub.publish(
                self.bridge.cv2_to_imgmsg(debug, encoding="bgr8")
            )
        except Exception as e:
            self.get_logger().warning(
                f"Debug image publish failed: {e}", throttle_duration_sec=5.0
            )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    def close(self):
        self.shutting_down = True
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()


def main():
    rclpy.init()
    node = ObjectPerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
