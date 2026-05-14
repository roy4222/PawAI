> **⚠️ PARTIALLY OUTDATED** — 分層原則（Presentation → Application → Domain → Infrastructure）仍可參考，但落地狀況與文件描述有差距：
> - `go2_robot_sdk` — **唯一完整落地**的四層分層模組
> - `face_perception` — 文件中描述的目錄已不存在於 repo，人臉模組已重構（見 `docs/pawai-brain/perception/face/`）
> - `speech_processor` — 未採用 Clean Architecture 分層（扁平結構，無 domain/application/infrastructure 子目錄）
> - `gesture_module` — 尚未建立
>
> 系統層架構見 [Pawai-studio/specs/system-architecture.md](../../pawai-brain/studio/specs/system-architecture.md)。

# Clean Architecture 分層原則

**文件定位**：PawAI 專案採用的軟體架構原則與實作規範  
**適用範圍**：所有 Layer 2 感知模組（face_perception、speech_processor、gesture_module）  
**版本**：v1.0  
**定案日期**：2026-03-08

---

## 1. 為什麼採用 Clean Architecture

### 1.1 問題背景

傳統 ROS2 節點常見問題：
- 🤯 **高度耦合**：ROS2 訂閱/發布邏輯與商業邏輯混在一起
- 🧪 **難以測試**：需要啟動 ROS2 環境才能單元測試
- 🔄 **難以置換**：更換演算法或感測器需要大規模重構
- 👥 **協作困難**：不同模組風格不一致，整合成本高

### 1.2 Clean Architecture 解決方案

```
依賴方向向內：外層依賴內層，內層不依賴外層

┌─────────────────────────────────────┐
│  Presentation (ROS2 Node)           │  ← 框架特定程式碼
│  - ROS2 subscribers/publishers      │
│  - 節點初始化、參數宣告             │
└──────────────┬──────────────────────┘
               │ 依賴
┌──────────────▼──────────────────────┐
│  Infrastructure (外部適配)          │  ← 外部函式庫適配
│  - YuNetDetector (cv2.FaceDetectorYN)
│  - ROS2FacePublisher (rclpy)        │
│  - IOUTracker (numpy)               │
└──────────────┬──────────────────────┘
               │ 實作介面
┌──────────────▼──────────────────────┐
│  Application (使用案例)             │  ← 商業邏輯
│  - FacePerceptionService            │
│  - 協調檢測/追蹤/發布流程           │
└──────────────┬──────────────────────┘
               │ 依賴
┌──────────────▼──────────────────────┐
│  Domain (領域核心)                  │  ← 純商業邏輯
│  - FaceDetection, FaceTrack         │
│  - IFaceDetector, IFaceTracker      │
│  - 無任何框架依賴                   │
└─────────────────────────────────────┘
```

**核心好處**：
- ✅ **可測試性**：Domain + Application 可脫離 ROS2 單元測試
- ✅ **可置換性**：更換演算法只需新增 Infrastructure 實作
- ✅ **可維護性**：每層職責單一，程式碼意圖清晰
- ✅ **協作性**：統一結構，團隊成員快速上手

---

## 2. 四層結構詳解

### 2.1 Domain Layer（領域層）

**職責**：定義商業實體與抽象介面，**完全不依賴外部框架**

**內容**：
- `entities/` - 資料類別（dataclass）
- `interfaces/` - 抽象介面（ABC）
- `constants/` - 常數定義

**範例**：

```python
# domain/entities/face_data.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class FaceDetection:
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    identity: Optional[FaceIdentity] = None

@dataclass
class FaceTrack:
    track_id: int
    bbox: tuple[int, int, int, int]
    confidence: float
    distance_m: Optional[float] = None
```

```python
# domain/interfaces/face_detector.py
from abc import ABC, abstractmethod
import numpy as np
from ..entities.face_data import FaceDetection

class IFaceDetector(ABC):
    @abstractmethod
    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        """檢測人臉，返回檢測結果列表"""
        raise NotImplementedError
```

**驗證原則**：
- ❌ 不能有 `import rclpy`
- ❌ 不能有 `import cv2`（除非是純數學運算）
- ✅ 只能有標準函式庫 + numpy（基本數學）

---

### 2.2 Application Layer（應用層）

**職責**：協調 Domain 實體與介面，實現使用案例

**內容**：
- `services/` - 使用案例服務
- `use_cases/` - 特定場景邏輯（如有需要）

**範例**：

```python
# application/services/face_perception_service.py
import time
import numpy as np
from ...domain.entities.face_data import FaceTrack
from ...domain.interfaces.face_detector import IFaceDetector
from ...domain.interfaces.face_tracker import IFaceTracker
from ...domain.interfaces.face_publisher import IFacePublisher

class FacePerceptionService:
    def __init__(
        self,
        detector: IFaceDetector,      # 依賴抽象介面
        tracker: IFaceTracker,        # 依賴抽象介面
        publisher: IFacePublisher,    # 依賴抽象介面
        event_interval_sec: float = 2.0,
    ):
        self._detector = detector
        self._tracker = tracker
        self._publisher = publisher
        self._event_interval_sec = event_interval_sec
        self._last_event_sec = 0.0

    def process(
        self,
        frame_bgr: np.ndarray,
        depth_frame: np.ndarray | None,
        stamp_sec: float | None = None,
    ) -> list[FaceTrack]:
        # 1. 檢測人臉
        detections = self._detector.detect(frame_bgr)
        
        # 2. 追蹤更新
        tracks = self._tracker.update(detections, depth_frame)
        
        # 3. 發布狀態
        self._publisher.publish_face_state(tracks, now_sec)
        
        # 4. 觸發事件（如需要）
        self._maybe_publish_event(tracks, now_sec)
        
        return tracks
```

**關鍵設計**：
- 透過**依賴注入**接收介面實作
- 不知道具體實作細節（YuNet、IOU、ROS2）
- 專注於商業流程協調

---

### 2.3 Infrastructure Layer（基礎設施層）

**職責**：實作 Domain 介面，連接外部依賴

**內容**：
- `detector/` - 人臉檢測器實作
- `tracker/` - 追蹤器實作
- `recognizer/` - 識別器實作
- `ros2/` - ROS2 發布器實作

**範例**：

```python
# infrastructure/detector/yunet_detector.py
import cv2
import numpy as np
from pathlib import Path
from ...domain.entities.face_data import FaceDetection
from ...domain.interfaces.face_detector import IFaceDetector

class YuNetDetector(IFaceDetector):
    def __init__(self, model_path: str, score_threshold: float = 0.9):
        # OpenCV 特定初始化
        self._detector = cv2.FaceDetectorYN.create(
            model_path, "", (320, 320),
            score_threshold, 0.3, 5000
        )

    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        # 實作介面方法
        height, width = frame_bgr.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(frame_bgr)
        
        if faces is None:
            return []
        
        detections = []
        for row in faces:
            x, y, w, h = row[:4].astype(np.int32)
            score = float(row[-1])
            detections.append(FaceDetection(
                bbox=(int(x), int(y), int(x+w), int(y+h)),
                confidence=score
            ))
        return detections
```

```python
# infrastructure/ros2/ros2_face_publisher.py
import json
from rclpy.node import Node
from std_msgs.msg import String
from ...domain.entities.face_data import FaceTrack
from ...domain.interfaces.face_publisher import IFacePublisher

class ROS2FacePublisher(IFacePublisher):
    def __init__(self, node: Node):
        self._state_pub = node.create_publisher(
            String, "/state/perception/face", 
            10
        )
        self._event_pub = node.create_publisher(
            String, 
            "/event/face_detected", 
            10
        )

    def publish_face_state(self, tracks: list[FaceTrack], stamp_sec: float) -> None:
        payload = {
            "stamp": stamp_sec,
            "count": len(tracks),
            "tracks": [self._track_to_dict(t) for t in tracks],
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._state_pub.publish(msg)
```

**關鍵設計**：
- 實作 Domain 定義的介面
- 將外部依賴（OpenCV、ROS2）包裝成統一介面
- 可輕易置換（如：YuNet → MediaPipe）

---

### 2.4 Presentation Layer（表現層）

**職責**：ROS2 節點入口，組裝所有依賴

**內容**：
- `face_perception_node.py` - 主檢測節點
- `face_interaction_node.py` - 互動觸發節點

**範例**：

```python
# presentation/face_perception_node.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

# Infrastructure imports
from ..infrastructure.detector.yunet_detector import YuNetDetector
from ..infrastructure.tracker.iou_tracker import IOUTracker
from ..infrastructure.ros2.ros2_face_publisher import ROS2FacePublisher

# Application imports
from ..application.services.face_perception_service import FacePerceptionService

class FacePerceptionNode(Node):
    def __init__(self):
        super().__init__("face_perception_node")
        
        # 1. 宣告參數（ROS2 特定）
        self.declare_parameter("yunet_model", "/home/jetson/face_models/yunet.onnx")
        
        # 2. 初始化 Infrastructure（外層）
        detector = YuNetDetector(
            model_path=self.get_parameter("yunet_model").value
        )
        tracker = IOUTracker(iou_threshold=0.3, max_lost=10)
        publisher = ROS2FacePublisher(node=self)
        
        # 3. 初始化 Application（注入依賴）
        self._service = FacePerceptionService(
            detector=detector,
            tracker=tracker,
            publisher=publisher,
        )
        
        # 4. 設定 ROS2 訂閱（ROS2 特定）
        self.create_subscription(
            Image, "/camera/camera/color/image_raw",
            self._on_color, 10
        )
        
    def _on_color(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, "bgr8")
        self._service.process(frame, None, time.time())
```

**關鍵設計**：
- 唯一知道 ROS2 存在的地方
- 負責**依賴注入**的組裝
- 處理框架特定的配置（參數、topic、QoS）

---

## 3. 依賴方向規則

### 3.1 依賴規則

```
Allowed:    Domain ← Application ← Infrastructure ← Presentation
Forbidden:  Domain → Application (內層不可依賴外層)
```

### 3.2 import 規範

| 層級 | 允許 import | 禁止 import |
|------|------------|------------|
| **Domain** | `typing`, `dataclasses`, `abc`, `numpy` (基本數學) | `rclpy`, `cv2`, `torch` |
| **Application** | Domain 模組 | `rclpy`, `cv2` |
| **Infrastructure** | Domain 模組、外部函式庫 | Application 具體類 |
| **Presentation** | 所有層級 | - |

### 3.3 驗證指令

```bash
# 檢查 Domain 層是否有 ROS2 依賴
grep -r "import rclpy\|from rclpy" face_perception/face_perception/domain/
# 應該無輸出

# 檢查 Domain 層是否有 OpenCV 依賴
grep -r "import cv2\|from cv2" face_perception/face_perception/domain/
# 應該無輸出
```

---

## 4. 測試策略

### 4.1 分層測試

| 層級 | 測試類型 | 執行環境 |
|------|----------|----------|
| **Domain** | 單元測試 | 純 Python（無 ROS2）|
| **Application** | 整合測試 | 純 Python + Mock |
| **Infrastructure** | 功能測試 | 需要實際依賴（OpenCV）|
| **Presentation** | 端對端測試 | 需要 ROS2 環境 |

### 4.2 Domain 層單元測試範例

```python
# tests/domain/test_face_data.py
import pytest
from face_perception.domain.entities.face_data import FaceDetection, FaceTrack

def test_face_detection_creation():
    detection = FaceDetection(
        bbox=(100, 100, 200, 200),
        confidence=0.95
    )
    assert detection.bbox == (100, 100, 200, 200)
    assert detection.confidence == 0.95

def test_face_track_with_distance():
    track = FaceTrack(
        track_id=1,
        bbox=(100, 100, 200, 200),
        confidence=0.95,
        distance_m=1.5
    )
    assert track.distance_m == 1.5
```

### 4.3 Application 層 Mock 測試

```python
# tests/application/test_face_perception_service.py
from unittest.mock import Mock
import pytest
from face_perception.application.services.face_perception_service import FacePerceptionService

def test_process_triggers_event():
    # Arrange
    mock_detector = Mock()
    mock_tracker = Mock()
    mock_publisher = Mock()
    
    service = FacePerceptionService(
        detector=mock_detector,
        tracker=mock_tracker,
        publisher=mock_publisher,
        event_interval_sec=0.0,  # 無冷卻
    )
    
    mock_detector.detect.return_value = [Mock()]
    mock_tracker.update.return_value = [Mock(track_id=1)]
    
    # Act
    import numpy as np
    service.process(np.zeros((480, 640, 3)), None, 0.0)
    
    # Assert
    mock_publisher.publish_face_event.assert_called_once()
```

---

## 5. 新增模組指南

### 5.1 建立新模組的步驟

```bash
# 1. 建立目錄結構
mkdir -p my_module/my_module/{domain/{entities,interfaces},application/services,infrastructure,presentation}
touch my_module/my_module/__init__.py

# 2. 建立 Domain 實體
# my_module/domain/entities/my_data.py

# 3. 建立 Domain 介面
# my_module/domain/interfaces/my_detector.py

# 4. 建立 Application 服務
# my_module/application/services/my_service.py

# 5. 建立 Infrastructure 實作
# my_module/infrastructure/detector/my_detector_impl.py

# 6. 建立 Presentation 節點
# my_module/presentation/my_node.py

# 7. 設定 setup.py entry_points
```

### 5.2 檢查清單

- [ ] Domain 層無 ROS2/OpenCV 依賴
- [ ] Application 服務透過介面接收依賴
- [ ] Infrastructure 實作 Domain 介面
- [ ] Presentation 負責依賴注入組裝
- [ ] 單元測試可脫離 ROS2 執行

---

## 6. 常見問題

### Q1: 為什麼 Domain 層不能用 numpy？

**A**: 純數學運算可以用 numpy，但圖像處理（cv2 的 Mat 操作）不行。Domain 層應該是純資料結構 + 數學邏輯。

### Q2: 如何處理 ROS2 Message 類型？

**A**: ROS2 Message 屬於 Infrastructure 層，在 ROS2FacePublisher 中轉換：
- Domain 層使用原生 Python 型別
- Infrastructure 層負責 Domain <-> ROS2 Message 轉換

### Q3: 可以跳過 Application 層嗎？

**A**: 簡單場景可以，但不建議。Application 層隔離了 Domain 與 Infrastructure，讓兩者可以獨立演化。

### Q4: 如何處理配置參數？

**A**: 
- Presentation 層：從 ROS2 parameters 讀取
- Application/Domain：透過建構子參數傳入
- 不要在 Domain 層讀取環境變數或檔案

---

## 7. 參考資源

- [The Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [go2_robot_sdk Clean Architecture 實作](../go2_robot_sdk/go2_robot_sdk/) - 參考範例

---

*維護者：System Architect*  
*最後更新：2026-03-08*
