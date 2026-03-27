> **⚠️ SUPERSEDED** — 人臉模組規格已移至 [interaction_contract.md](./interaction_contract.md) v2.0 §3.1（state schema）+ §4.1（event schema）+ §7.1（節點參數）。現行實作為 `scripts/face_identity_infer_cv.py`。

# Face Perception 模組架構

**模組名稱**：face_perception  
**Layer**：Layer 2 (Perception Module)  
**負責人**：楊  
**版本**：v1.0 MVP  
**定案日期**：2026-03-08

---

## 1. 模組定位

### 1.1 職責

Face Perception 是 PawAI 系統的**人臉感知模組**，負責：

1. **人臉偵測**：從 RGB 影像中偵測人臉位置
2. **追蹤連續性**：維持 session-level 的 track_id 穩定
3. **深度估計**：計算人臉與機器人的距離
4. **身分識別**（可選）：辨識已知人物（SFace）
5. **事件發布**：當人臉出現/消失時發布事件

### 1.2 輸入輸出

**輸入**：
- `/camera/camera/color/image_raw` (sensor_msgs/Image) - RGB 影像
- `/camera/camera/aligned_depth_to_color/image_raw` (sensor_msgs/Image) - 深度影像

**輸出**：
- `/state/perception/face` (std_msgs/String, JSON) - 人臉狀態 (10 Hz)
- `/event/face_detected` (std_msgs/String, JSON) - 人臉偵測事件

---

## 2. 技術棧

| 組件 | 技術 | 版本 | 說明 |
|------|------|------|------|
| **偵測器** | YuNet (ONNX) | 2023mar | OpenCV FaceDetectorYN，輕量高效 |
| **追蹤器** | IOU Tracker | 自研 | 簡單 IOU 匹配，session-level 穩定 |
| **識別器** | SFace (ONNX) | 2021dec | 可選，128-dim embedding |
| **深度** | RealSense D435 | - | 對齊深度影像 |
| **框架** | OpenCV | 4.x | CUDA 加速 |

### 2.1 性能指標

| 指標 | 目標值 | 備註 |
|------|--------|------|
| 偵測延遲 | < 100 ms | Jetson CUDA 優化後 |
| 追蹤穩定性 | > 90% | Session 內 track_id 不跳動 |
| 深度精度 | ±5% | 1-3 米範圍內 |
| 發布頻率 | 10 Hz | 狀態發布 |

---

## 3. 架構設計

### 3.1 Clean Architecture 分層

```
face_perception/face_perception/
│
├── domain/                           # 無 ROS2/OpenCV 依賴
│   ├── entities/
│   │   └── face_data.py             # FaceDetection, FaceTrack, FaceIdentity
│   └── interfaces/
│       ├── face_detector.py         # IFaceDetector
│       ├── face_tracker.py          # IFaceTracker
│       ├── face_recognizer.py       # IFaceRecognizer
│       └── face_publisher.py        # IFacePublisher
│
├── application/
│   └── services/
│       └── face_perception_service.py  # 協調檢測/追蹤/發布
│
├── infrastructure/                   # 實作 Domain 介面
│   ├── detector/
│   │   └── yunet_detector.py        # YuNet 實作
│   ├── tracker/
│   │   └── iou_tracker.py           # IOU Tracker 實作
│   ├── recognizer/
│   │   └── sface_recognizer.py      # SFace 實作（可選）
│   └── ros2/
│       └── ros2_face_publisher.py   # ROS2 發布實作
│
└── presentation/                     # ROS2 節點入口
    ├── face_perception_node.py      # 主檢測節點
    └── face_interaction_node.py     # 互動觸發節點
```

### 3.2 類別圖

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation Layer                                          │
│  ┌─────────────────────┐    ┌──────────────────────────┐   │
│  │ FacePerceptionNode  │    │ FaceInteractionNode      │   │
│  │ - ROS2 Node         │    │ - ROS2 Node              │   │
│  │ - 參數管理          │    │ - 訂閱 /event/face       │   │
│  │ - 影像回調          │    │ - 發布 /webrtc_req       │   │
│  └──────────┬──────────┘    └──────────────────────────┘   │
└─────────────┼───────────────────────────────────────────────┘
              │ 依賴注入
┌─────────────▼───────────────────────────────────────────────┐
│  Infrastructure Layer                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ YuNetDetector│  │ IOUTracker   │  │ ROS2FacePublisher│  │
│  │ implements   │  │ implements   │  │ implements       │  │
│  │ IFaceDetector│  │ IFaceTracker │  │ IFacePublisher   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────┬───────────────────────────────────────────────┘
              │ 實作介面
┌─────────────▼───────────────────────────────────────────────┐
│  Application Layer                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ FacePerceptionService                                   │ │
│  │ - process(frame, depth) -> List[FaceTrack]             │ │
│  │ - 協調 detector/tracker/publisher                       │ │
│  │ - 管理事件觸發邏輯                                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────┬───────────────────────────────────────────────┘
              │ 依賴
┌─────────────▼───────────────────────────────────────────────┐
│  Domain Layer                                                │
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │ FaceDetection    │  │ IFaceDetector (ABC)            │  │
│  │ - bbox           │  │ - detect() -> [Detection]     │  │
│  │ - confidence     │  └────────────────────────────────┘  │
│  │ - identity       │  ┌────────────────────────────────┐  │
│  └──────────────────┘  │ IFaceTracker (ABC)             │  │
│  ┌──────────────────┐  │ - update() -> [FaceTrack]     │  │
│  │ FaceTrack        │  └────────────────────────────────┘  │
│  │ - track_id       │  ┌────────────────────────────────┐  │
│  │ - distance_m     │  │ IFacePublisher (ABC)           │  │
│  └──────────────────┘  │ - publish_state()              │  │
│                        │ - publish_event()              │  │
│                        └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 核心組件詳解

### 4.1 Domain Entities

```python
# domain/entities/face_data.py

@dataclass
class FaceIdentity:
    """人物身分資訊"""
    person_name: str      # 姓名或 "unknown"
    confidence: float     # 識別置信度

@dataclass
class FaceDetection:
    """單一人臉偵測結果"""
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float                # 偵測置信度 (0-1)
    identity: Optional[FaceIdentity] = None  # 身分（可選）

@dataclass
class FaceTrack:
    """追蹤中的人臉"""
    track_id: int                    # Session-level 追蹤 ID
    bbox: tuple[int, int, int, int]  # 邊界框
    confidence: float                # 置信度
    distance_m: Optional[float] = None       # 深度距離（米）
    identity: Optional[FaceIdentity] = None  # 身分（可選）
```

### 4.2 Application Service

```python
# application/services/face_perception_service.py

class FacePerceptionService:
    """
    人臉感知服務
    
    協調檢測、追蹤、發布流程
    """
    
    def __init__(
        self,
        detector: IFaceDetector,
        tracker: IFaceTracker,
        publisher: IFacePublisher,
        recognizer: Optional[IFaceRecognizer] = None,
        event_interval_sec: float = 2.0,
    ):
        self._detector = detector
        self._tracker = tracker
        self._publisher = publisher
        self._recognizer = recognizer
        self._event_interval_sec = event_interval_sec
        self._had_face = False
        self._last_event_sec = 0.0

    def process(
        self,
        frame_bgr: np.ndarray,
        depth_frame: Optional[np.ndarray],
        stamp_sec: float,
    ) -> list[FaceTrack]:
        """
        處理單幀影像
        
        流程：
        1. YuNet 偵測人臉
        2. SFace 識別身分（如啟用）
        3. IOU Tracker 更新追蹤
        4. 深度估計距離
        5. 發布狀態與事件
        """
        # 1. 檢測
        detections = self._detector.detect(frame_bgr)
        
        # 2. 識別（可選）
        if self._recognizer is not None and detections:
            self._recognizer.annotate(frame_bgr, detections)
        
        # 3. 追蹤
        tracks = self._tracker.update(detections, depth_frame)
        
        # 4. 發布狀態
        self._publisher.publish_face_state(tracks, stamp_sec)
        
        # 5. 觸發事件
        self._maybe_publish_event(tracks, stamp_sec)
        
        return tracks
```

### 4.3 Infrastructure Implementations

#### YuNetDetector

```python
# infrastructure/detector/yunet_detector.py

class YuNetDetector(IFaceDetector):
    """
    OpenCV YuNet 人臉檢測器實作
    
    模型資訊：
    - 輸入：320x320 (可調整)
    - 輸出：邊界框 + 5 個特徵點 + 置信度
    - 大小：~100 KB
    - 速度：~30 FPS on Jetson CUDA
    """
    
    def __init__(
        self,
        model_path: str,
        score_threshold: float = 0.9,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ):
        resolved = Path(model_path)
        if not resolved.exists():
            raise FileNotFoundError(f"模型未找到: {resolved}")
        
        self._detector = cv2.FaceDetectorYN.create(
            model=str(resolved),
            config="",
            input_size=(320, 320),
            score_threshold=score_threshold,
            nms_threshold=nms_threshold,
            top_k=top_k,
        )

    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        height, width = frame_bgr.shape[:2]
        self._detector.setInputSize((width, height))
        
        _, faces = self._detector.detect(frame_bgr)
        if faces is None:
            return []
        
        detections = []
        for row in faces:
            x, y, w, h = row[:4].astype(np.int32)
            score = float(row[-1])
            
            # 邊界框裁切
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(width, x1 + max(1, int(w)))
            y2 = min(height, y1 + max(1, int(h)))
            
            detections.append(FaceDetection(
                bbox=(x1, y1, x2, y2),
                confidence=score,
            ))
        
        return detections
```

#### IOUTracker

```python
# infrastructure/tracker/iou_tracker.py

class IOUTracker(IFaceTracker):
    """
    IOU-based 人臉追蹤器
    
    策略：
    - 偵測與現有追蹤框計算 IOU
    - IOU > threshold 視為同一目標
    - 連續 max_lost 幀未匹配則刪除
    - 新偵測無匹配則建立新 track_id
    """
    
    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_lost: int = 10,
        depth_scale: float = 0.001,  # RealSense 深度單位轉換
    ):
        self._iou_threshold = iou_threshold
        self._max_lost = max_lost
        self._depth_scale = depth_scale
        self._next_id = 1
        self._tracks: dict[int, FaceTrack] = {}
        self._lost: dict[int, int] = {}

    def update(
        self,
        detections: list[FaceDetection],
        depth_frame: Optional[np.ndarray],
    ) -> list[FaceTrack]:
        # IOU 匹配邏輯...
        # 深度估計...
        pass

    @staticmethod
    def _iou(
        a: tuple[int, int, int, int],
        b: tuple[int, int, int, int]
    ) -> float:
        """計算兩個邊界框的 IOU"""
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        
        if inter_area <= 0:
            return 0.0
        
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        
        return inter_area / float(area_a + area_b - inter_area)
```

---

## 5. 資料格式

### 5.1 State Message (`/state/perception/face`)

```json
{
  "stamp": 1709823456.789,
  "count": 2,
  "tracks": [
    {
      "track_id": 1,
      "bbox": [100, 150, 200, 280],
      "confidence": 0.95,
      "distance_m": 1.25,
      "person_name": "unknown",
      "person_confidence": 0.0
    },
    {
      "track_id": 2,
      "bbox": [300, 180, 380, 300],
      "confidence": 0.87,
      "distance_m": 2.1
    }
  ]
}
```

### 5.2 Event Message (`/event/face_detected`)

```json
{
  "stamp": 1709823456.789,
  "event_type": "detected",
  "track": {
    "track_id": 1,
    "bbox": [100, 150, 200, 280],
    "confidence": 0.95,
    "distance_m": 1.25
  }
}
```

---

## 6. 參數配置

### 6.1 FacePerceptionNode 參數

| 參數名 | 型別 | 預設值 | 說明 |
|--------|------|--------|------|
| `color_topic` | string | `/camera/camera/color/image_raw` | RGB 影像 topic |
| `depth_topic` | string | `/camera/camera/aligned_depth_to_color/image_raw` | 深度影像 topic |
| `yunet_model` | string | `/home/jetson/face_models/face_detection_yunet_2023mar.onnx` | YuNet 模型路徑 |
| `sface_model` | string | `/home/jetson/face_models/face_recognition_sface_2021dec.onnx` | SFace 模型路徑 |
| `face_db_model` | string | `/home/jetson/face_db/model_sface.pkl` | 人臉資料庫 |
| `enable_identity` | bool | `false` | 是否啟用身分識別 |
| `identity_threshold` | float | `0.35` | SFace 識別閾值 |
| `event_interval_sec` | float | `2.0` | 事件最小間隔 |
| `tracker_iou_threshold` | float | `0.3` | IOU 匹配閾值 |
| `tracker_max_lost` | int | `10` | 最大遺失幀數 |

### 6.2 FaceInteractionNode 參數

| 參數名 | 型別 | 預設值 | 說明 |
|--------|------|--------|------|
| `face_event_topic` | string | `/event/face_detected` | 事件訂閱 topic |
| `webrtc_publish_topic` | string | `/webrtc_req` | Skill 發布 topic |
| `webrtc_topic_name` | string | `rt/api/sport/request` | WebRTC topic |
| `action_api_id` | int | `1016` | Hello skill ID |
| `interaction_cooldown_sec` | float | `5.0` | 互動冷卻時間 |

---

## 7. Launch 使用

### 7.1 基本啟動

```bash
# 僅偵測（無身分識別）
ros2 launch face_perception face_perception.launch.py enable_identity:=false
```

### 7.2 完整啟動（含身分識別）

```bash
ros2 launch face_perception face_perception.launch.py \
    enable_identity:=true \
    identity_threshold:=0.35 \
    event_interval_sec:=2.0
```

### 7.3 調試模式

```bash
# 觀察狀態輸出
ros2 topic echo /state/perception/face

# 觀察事件輸出
ros2 topic echo /event/face_detected

# 確認 skill 請求
ros2 topic echo /webrtc_req
```

---

## 8. 擴充指南

### 8.1 新增偵測器

1. 實作 `IFaceDetector` 介面
2. 在 `infrastructure/detector/` 新增實作
3. 在 `face_perception_node.py` 注入新實作

### 8.2 新增追蹤器

1. 實作 `IFaceTracker` 介面
2. 支援深度估計或 3D 追蹤
3. 替換 `IOUTracker` 注入

---

## 9. 參考資源

- [OpenCV YuNet 文件](https://docs.opencv.org/4.x/df/d20/classcv_1_1FaceDetectorYN.html)
- [OpenCV Zoo - Face Detection](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [go2_robot_sdk Clean Architecture](../go2_robot_sdk/go2_robot_sdk/)

---

*維護者：楊 (Face Owner)*  
*最後更新：2026-03-08*
