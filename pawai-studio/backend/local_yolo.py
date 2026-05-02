"""
local_yolo_mjpeg.py — YOLO 測試腳本 (實例分割 + 顏色分析)
════════════════════════════════════════════════════════════════
用 Python 跑 YOLO26n-seg（實例分割模型）辨識物體，
再用 HSV 分析顏色，開啟硬體鏡頭及背景 HTTP Server。
網頁端可直接接收 http://localhost:8081/video_feed 看到畫面。

啟動方式：
    # 若你目前在 PawAI repo 根目錄
    cd pawai-studio\\backend
    py local_yolo_mjpeg.py
    
    # 若你已在 backend 目錄
    py local_yolo_mjpeg.py
════════════════════════════════════════════════════════════════    
"""
import time
import json
import os
import cv2
import sys
import socket
import threading
import numpy as np
from urllib import request as urllib_request, error as urllib_error
from http.server import BaseHTTPRequestHandler, HTTPServer

MOCK_SERVER  = os.getenv("MOCK_SERVER_URL", "http://localhost:8000").rstrip("/")
CAMERA_ID    = 0
SEND_FPS     = 5
CONF_THRESH  = 0.30
MODEL_NAME   = "yolov8n-seg.pt"  # 實例分割模型（邊緣友善版本）

# 全域變數，存放最新的影像編碼
latest_jpeg = None
lock = threading.Lock()

class MJPEGHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): 
        pass  # 隱藏存取 log

    def do_OPTIONS(self):
        # 處理 CORS 預檢請求
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With")
        self.end_headers()

    def do_GET(self):
        if self.path == '/video_feed':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            while True:
                with lock:
                    jpeg_bytes = latest_jpeg
                if jpeg_bytes is not None:
                    try:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-type: image/jpeg\r\n')
                        self.wfile.write(b'Content-length: ' + str(len(jpeg_bytes)).encode() + b'\r\n\r\n')
                        self.wfile.write(jpeg_bytes)
                        self.wfile.write(b'\r\n')
                    except Exception:
                        break
                time.sleep(0.04)  # ~25 FPS

def run_server():
    server = HTTPServer(('0.0.0.0', 8081), MJPEGHandler)
    server.serve_forever()

def load_yolo():
    import os
    from ultralytics import YOLO
    
    # 禁用自動下載，只使用本地檔案
    os.environ['YOLO_SKIP_VALIDATION'] = 'true'
    
    MODEL_PATH = "yolov8n-seg.pt"
    print(f"[YOLO] 載入模型: {MODEL_PATH}")
    
    # 驗證檔案存在
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] 模型檔案不存在: {MODEL_PATH}")
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
    
    model = YOLO(MODEL_PATH, task="segment", verbose=False)
    print(f"[YOLO] ✓ 模型載入成功")
    return model

def detect_color_from_bbox(roi_hsv):
    """從 ROI bbox 區域計算顏色。
    
    Args:
        roi_hsv: bbox 內的 HSV 影像
        
    Returns:
        color_name: 顏色名稱
    """
    if roi_hsv.size == 0:
        return "Unknown"
    
    # 計算平均 HSV
    h_mean = np.mean(roi_hsv[:, :, 0])
    s_mean = np.mean(roi_hsv[:, :, 1])
    v_mean = np.mean(roi_hsv[:, :, 2])
    
    print(f"[COLOR] H={h_mean:.1f} S={s_mean:.1f} V={v_mean:.1f}", flush=True)
    
    # 改進的顏色判定邏輯（考慮飽和度 + 亮度）
    if v_mean < 50:
        return "Black"
    elif v_mean > 220 and s_mean < 30:
        return "White"
    elif s_mean < 30:
        return "Gray"
    
    # 色調範圍（OpenCV HSV: H=0-180）
    if (h_mean < 10 or h_mean > 170) and s_mean > 30:
        return "Red"
    elif 10 <= h_mean < 20:
        return "Orange"
    elif 20 <= h_mean < 35:
        return "Yellow"
    elif 35 <= h_mean < 80:
        return "Green"
    elif 80 <= h_mean < 100:
        return "Cyan"
    elif 100 <= h_mean < 130:
        return "Blue"
    elif 130 <= h_mean < 160:
        return "Purple"
    elif 160 <= h_mean <= 170:
        return "Pink"
    else:
        return "Unknown"

def main():
    global latest_jpeg
    model = load_yolo()
    
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"[ERROR] 無法開啟鏡頭 {CAMERA_ID}")
        sys.exit(1)

    # 在背景啟動串流伺服器
    threading.Thread(target=run_server, daemon=True).start()
    print("[SERVER] ✅ 影像串流啟動於 http://localhost:8081/video_feed")
    print("\n[YOLO] ▶ 開始偵測（按 Ctrl+C 結束）")

    send_interval = 1.0 / SEND_FPS
    last_send = 0.0
    had_send_error = False
    last_send_error_log_at = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # 強制將攝影機解析度縮放到 640x480，確保座標比例跟前端 100% 吻合！
            frame = cv2.resize(frame, (640, 480))
            frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            now = time.time()
            results = model(frame, conf=CONF_THRESH, verbose=False)
            boxes = results[0].boxes
            masks = results[0].masks
            objects = []
            
            if boxes is not None:
                for i, box in enumerate(boxes):
                    cls_id = int(box.cls[0])
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                    conf = round(float(box.conf[0]), 3)
                    class_name = model.names[cls_id] if hasattr(model, 'names') else str(cls_id)
                    
                    # 【簡化】使用 bbox 區域直接檢測顏色
                    color_name = "Unknown"
                    try:
                        roi = frame[y1:y2, x1:x2]
                        if roi.size > 0:
                            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                            color_name = detect_color_from_bbox(roi_hsv)
                    except Exception as e:
                        print(f"[COLOR_ERROR] {e}", flush=True)
                    
                    print(f"[DEBUG] {class_name}: color={color_name}", flush=True)
                    
                    objects.append({
                        "class_name": class_name,
                        "class_id": cls_id,
                        "confidence": conf,
                        "bbox": [x1, y1, x2, y2],
                        "color": color_name,
                    })

            # 手動繪製 bounding boxes（只顯示偵測框，不顯示 segmentation 框）
            annotated_frame = frame.copy()
            if boxes is not None:
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id] if hasattr(model, 'names') else str(cls_id)
                    
                    # 繪製框線和標籤
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    label_text = f"{class_name} {conf:.2f}"
                    cv2.putText(annotated_frame, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # 更新對外廣播的 JPEG 影像
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            with lock:
                latest_jpeg = buffer.tobytes()

            if now - last_send >= send_interval:
                try:
                    payload = json.dumps({
                        "event_source": "object",
                        "event_type": "object_detected",
                        "data": {
                            "stamp": now,
                            "active": len(objects) > 0,
                            "detected_objects": objects,
                            "objects": objects
                        }
                    }).encode("utf-8")
                    req = urllib_request.Request(
                        f"{MOCK_SERVER}/mock/trigger",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib_request.urlopen(req, timeout=0.5):
                        if had_send_error:
                            print(f"[YOLO] ✅ 已恢復與 Mock Server 連線：{MOCK_SERVER}", flush=True)
                            had_send_error = False
                except (urllib_error.URLError, socket.timeout, TimeoutError) as e:
                    if (not had_send_error) or (now - last_send_error_log_at >= 5):
                        print(
                            f"[YOLO] ⚠ 無法送出 object event 到 {MOCK_SERVER}/mock/trigger：{e}",
                            flush=True,
                        )
                        last_send_error_log_at = now
                    had_send_error = True
                last_send = now

    except KeyboardInterrupt:
        print("\n[YOLO] 使用者中斷")
    finally:
        cap.release()
        print("[YOLO] ✅ 結束")

if __name__ == "__main__":
    main()
