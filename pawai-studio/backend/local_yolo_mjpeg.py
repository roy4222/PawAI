"""
local_yolo_mjpeg.py — YOLO 測試腳本 (ONNX 模型 + 影像串流版)
════════════════════════════════════════════════════════════════
用 Python 跑 YOLO (ONNX 格式) 並開啟硬體鏡頭，同時在背景運行一個微型 HTTP Server。
網頁端不用再搶鏡頭，可以直接接收 http://localhost:8081/video_feed 看到畫面。

啟動方式：
    cd pawai-studio/backend
    py local_yolo_mjpeg.py
════════════════════════════════════════════════════════════════    
"""
import time
import json
import cv2
import sys
import socket
import threading
from urllib import request as urllib_request, error as urllib_error
from http.server import BaseHTTPRequestHandler, HTTPServer

MOCK_SERVER  = "http://localhost:8000"
CAMERA_ID    = 0
SEND_FPS     = 5
CONF_THRESH  = 0.30
MODEL_NAME   = "yolo26n.onnx"  # 已經換成真正的 ONNX 模型了！

# 加入更多常見物品方便測試 (加入 person, bottle, chair 等)
WHITELIST_CLASS_IDS = {
    0: "person", 39: "bottle", 56: "chair", 60: "dining table",
    41: "cup", 67: "cell phone", 73: "book",
    63: "laptop", 24: "backpack", 74: "clock",
}

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
    from ultralytics import YOLO
    print(f"[YOLO] 載入模型 {MODEL_NAME}...")
    return YOLO(MODEL_NAME, task="detect")

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

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # 強制將攝影機解析度縮放到 640x480，確保座標比例跟前端 100% 吻合！
            frame = cv2.resize(frame, (640, 480))

            now = time.time()
            results = model(frame, conf=CONF_THRESH, verbose=False)
            boxes = results[0].boxes
            objects = []
            
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0])
                    # 不管白名單，全標！(前端UI只會亮起白名單，背後的MJPEG全標)
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                    conf = round(float(box.conf[0]), 3)
                    class_name = model.names[cls_id] if hasattr(model, 'names') else str(cls_id)
                    objects.append({
                        "class_name": class_name,
                        "class_id": cls_id,
                        "confidence": conf,
                        "bbox": [x1, y1, x2, y2],
                    })

            # 直接使用 YOLO 原生繪製的畫面作為串流畫面！這樣絕對不會看不到框線！
            annotated_frame = results[0].plot()

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
                        pass
                except (urllib_error.URLError, socket.timeout, TimeoutError):
                    pass
                last_send = now

    except KeyboardInterrupt:
        print("\n[YOLO] 使用者中斷")
    finally:
        cap.release()
        print("[YOLO] ✅ 結束")

if __name__ == "__main__":
    main()
