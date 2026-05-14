---
title: "物體辨識可行性研究報告"
version: "1.0"
date: "2026-03-25"
author: "PawAI System Architecture"
status: "DRAFT — 待 Jetson 實測驗證"
decision: "有條件建議執行（CONDITIONAL GO）"
---

# 物體辨識可行性研究報告

> **一句話決策**：YOLO26n 在 Jetson Orin Nano 8GB 上部署可行，TensorRT FP16 推理預估 10-15 FPS，RAM 增量 0.6-1.1GB 在現有三感知 CPU-only 架構下可容納。建議以 3 天 Sprint 完成 Phase 0-4，納入 4/13 交付。

---

## 目錄

1. [摘要與決策建議](#1-摘要與決策建議)
2. [背景](#2-背景)
3. [YOLO26 技術評估](#3-yolo26-技術評估)
4. [Jetson Orin Nano 8GB 部署可行性](#4-jetson-orin-nano-8gb-部署可行性)
5. [D435 深度整合設計](#5-d435-深度整合設計)
6. [ROS2 整合架構（Clean Architecture）](#6-ros2-整合架構clean-architecture)
7. [P0 偵測類別](#7-p0-偵測類別)
8. [與現有系統的整合點](#8-與現有系統的整合點)
9. [實作路線圖](#9-實作路線圖)
10. [風險與緩解](#10-風險與緩解)
11. [與其他方案的比較](#11-與其他方案的比較)
12. [參考資料](#12-參考資料)

---

## 1. 摘要與決策建議

### 決策：CONDITIONAL GO（有條件建議執行）

| 維度 | 評估 | 信心度 |
|------|------|:------:|
| 技術可行性 | YOLO26n TensorRT FP16 推理 ~1.4ms，Python E2E 預估 10-15 FPS | 中高 |
| 資源可行性 | RAM 增量 0.6-1.1GB，三感知 CPU-only 時 GPU 空閒可用 | 中高 |
| 時程可行性 | 3 天 Sprint（Phase 0-4），距 4/13 尚餘 19 天 | 高 |
| 整合風險 | 與 Whisper CUDA 時間分割共存需驗證 | 中 |

### 前置條件（GO 的門檻）

1. **Phase 0 環境驗證通過**：`ultralytics` 在 Jetson 可成功匯出 TensorRT engine 且推理無 crash
2. **RAM 實測**：YOLO26n TensorRT engine 載入後，系統總 RAM 不超過 6.8GB（保留 0.8GB 安全餘量）
3. **GPU 共存**：YOLO26n + Whisper small 時間分割推理無死鎖或 OOM

### 若前置條件未滿足

- **RAM 超標**：降至 INT8 量化（模型體積再減 ~50%）或降解析度至 320x320
- **GPU 衝突**：YOLO26n 改走 CPU（預估 3-5 FPS，仍可作為低頻補充感知）
- **TensorRT 匯出失敗**：改用 ONNX Runtime GPU 路徑（效能略降但相容性更好）

---

## 2. 背景

### 2.1 專案需求

物體辨識是教授 3/18 會議定案的**核心五功能之一**（語音、人臉、手勢/姿勢、物體辨識、AI 大腦）。在 `docs/mission/README.md` v2.2 的八大功能閉環中列為 **P1**，排序第 6，要求 4/13 文件繳交前完成。

核心使用情境：
- **室內物件感知**：「桌上有杯子」「椅子在左邊」
- **人物互動輔助**：偵測 person 與 face_perception 互補
- **場景描述**：結合 LLM 提供環境語意理解
- **展示亮點**：Go2 能「看到」並「說出」周圍物品

### 2.2 現狀

| 項目 | 狀態 |
|------|------|
| 程式碼 | **Zero code**。舊 `coco_detector` package 僅存 `__pycache__`，原始碼已刪除 |
| 設計文件 | `docs/pawai-brain/perception/object/README.md` v1.1（2026-03-11），含完整介面定義與 D435 整合設計 |
| 模型選定 | YOLO26n（設計文件已決策，但尚未 benchmark 驗證） |
| ROS2 介面 | 設計文件已定義 topic，但尚未納入 `interaction_contract.md` v2.1 |

### 2.3 時程壓力

- **距 4/13 文件繳交**：19 天
- **距四功能整合測試開始（3/26）**：1 天
- **核心語音/人臉/手勢/姿勢已穩定**：物體辨識是剩餘最大缺口
- **團隊人力**：物體辨識模組指定開發者尚需確認（設計文件未標注負責人）

---

## 3. YOLO26 技術評估

### 3.1 YOLO26 vs YOLO11 對比

YOLO26 是 Ultralytics 於 2025 年 5 月發布的最新一代 YOLO 架構，核心改進為 NMS-free 設計與效率提升。

| 指標 | YOLO26n | YOLO11n | YOLO26s | YOLO11s |
|------|:-------:|:-------:|:-------:|:-------:|
| **mAP^val (COCO)** | 40.1% | 39.5% | 47.1% | 47.0% |
| **Parameters** | 2.4M | 2.6M | 9.7M | 9.4M |
| **FLOPs** | 6.0G | 6.5G | 24.6G | 21.5G |
| **CPU ONNX (ms)** | 67.8 | 90.2 | 163.2 | 201.7 |
| **T4 TensorRT (ms)** | 1.4 | 1.5 | 2.1 | 2.5 |
| **NMS-free** | Yes | No | Yes | No |
| **Architecture** | ADown + RepConv + ALSS | C3k2 + SPPF | ADown + RepConv + ALSS | C3k2 + SPPF |

> 數據來源：Ultralytics 官方 benchmark，T4 GPU TensorRT FP16。Jetson Orin Nano 算力約為 T4 的 25-35%，實際速度需現場測試。

### 3.2 NMS-free 架構優勢

傳統 YOLO 系列需要後處理 NMS（Non-Maximum Suppression）步驟，這會帶來：
- **不確定延遲**：NMS 耗時與偵測框數成正比，擁擠場景延遲飆升
- **TensorRT 匯出困難**：NMS 通常是 PyTorch 後處理，無法併入 TensorRT engine
- **部署複雜度**：需維護 Python 後處理邏輯

YOLO26 採用 **one-to-one label assignment**，模型直接輸出最終偵測結果：
- **推理延遲恆定**：不受場景複雜度影響
- **端到端 TensorRT**：整個模型（含後處理）可完全編譯為 TensorRT engine（`end2end=True`）
- **部署簡化**：輸出即最終結果，無需額外 NMS code

### 3.3 Pose Estimation 能力

YOLO26 支援 Pose estimation 任務（YOLO26n-pose / YOLO26s-pose），與現有 MediaPipe Pose 能力重疊：

| 指標 | YOLO26n-pose | MediaPipe Pose (CPU) |
|------|:------------:|:--------------------:|
| Keypoints | 17 (COCO) | 33 (BlazePose) |
| FPS（Jetson 預估） | 8-12 | 18.5（L1 實測） |
| GPU 需求 | 是（CUDA/TensorRT） | 否（CPU-only） |
| 多人偵測 | 原生支援 | 單人 |

**評估結論**：YOLO26-pose 目前不建議替代 MediaPipe Pose。理由：
1. MediaPipe Pose CPU-only 已達 18.5 FPS，不佔 GPU
2. YOLO26-pose 需 GPU，會與 YOLO26n detection 競爭
3. MediaPipe 提供 33 點（含手指），YOLO26 僅 17 點
4. 替換風險高且收益有限——但作為**未來統一化**選項值得持續觀察

### 3.4 支援任務矩陣

| 任務 | YOLO26 支援 | 本專案用途 |
|------|:-----------:|-----------|
| Detection | Yes | **P0 主線**：物體偵測 |
| Segmentation | Yes | P2 未來：精確輪廓 |
| Classification | Yes | 不需要（detection 已含類別） |
| Pose | Yes | 觀察中（見 3.3） |
| OBB (Oriented Bounding Box) | Yes | 不需要（室內場景非旋轉物體） |

### 3.5 授權

- **License**：AGPL-3.0
- **學術使用**：完全合法，無需商業授權
- **本專案適用**：學術專題，符合 AGPL-3.0 條款
- **注意**：若未來商業化需切換至 Ultralytics Enterprise License

---

## 4. Jetson Orin Nano 8GB 部署可行性

### 4.1 TensorRT FP16 性能預估

| 指標 | T4 GPU（官方） | Jetson Orin Nano（推估） | 推估依據 |
|------|:-------------:|:----------------------:|----------|
| 純推理延遲 | 1.4ms | 4-6ms | Orin Nano 算力約 T4 的 25-35% |
| 前後處理 + Python overhead | — | 20-40ms | Python GIL + numpy + image resize |
| **E2E 單幀延遲** | — | **25-50ms** | 純推理 + 前後處理 |
| **預估 FPS** | — | **10-15 FPS** | 含 D435 讀取 + ROS2 publish |

> **關鍵假設**：使用 `model.export(format="engine", half=True)` 匯出 TensorRT FP16 engine，推理時走 `model.predict()` 的 TensorRT 路徑。Python overhead 是最大瓶頸，非推理本身。

### 4.2 RAM 預算分析

**現有系統 RAM 佔用（三感知 CPU-only 模式，3/23 壓測數據）**：

| 項目 | RAM 佔用 |
|------|:--------:|
| Ubuntu + ROS2 基礎系統 | ~1.5-2.0 GB |
| D435 + 影像串流 | ~0.6-1.0 GB |
| face_perception (YuNet CPU) | ~0.1 GB |
| vision_perception (MediaPipe Pose+Gesture CPU) | ~0.4 GB |
| 其他 ROS2 nodes | ~0.3 GB |
| **小計（三感知 idle）** | **~3.0-3.8 GB** |
| speech_processor (Whisper CUDA idle) | ~1.0-1.5 GB |
| **小計（含語音 idle）** | **~4.0-5.3 GB** |

**加入 YOLO26n 後預估**：

| 項目 | 預估增量 |
|------|:--------:|
| TensorRT FP16 engine 載入 | ~0.3-0.5 GB |
| CUDA context 共享（已存在時） | ~0 GB |
| 推理時 GPU 記憶體 | ~0.2-0.4 GB |
| Python process + Ultralytics runtime | ~0.1-0.2 GB |
| **YOLO26n 總增量** | **~0.6-1.1 GB** |

**RAM 結算**：

| 情境 | 總佔用 | 剩餘 | 安全性 |
|------|:------:|:----:|:------:|
| 三感知 + YOLO26n（無語音） | ~3.6-4.9 GB | 3.1-4.4 GB | 安全 |
| 四感知 + 語音 idle | ~4.6-6.4 GB | 1.6-3.4 GB | 安全（>0.8GB） |
| 四感知 + 語音推理中 | ~5.0-6.8 GB | 1.2-3.0 GB | 可接受 |
| **最壞情境** | **~6.8 GB** | **~0.8 GB** | **臨界** |

**結論**：RAM 預算在可控範圍內，但最壞情境下貼近 0.8GB 安全線。需 Phase 0 實測確認。

### 4.3 GPU 共存分析

**現有 GPU 使用狀況（3/23 三感知壓測）**：

| 模組 | GPU 佔用 | 模式 |
|------|:--------:|------|
| face_perception (YuNet) | 0% | CPU-only |
| vision_perception (MediaPipe Pose) | 0% | CPU-only |
| vision_perception (Gesture Recognizer) | 0% | CPU-only |
| **三感知合計** | **0%** | GPU 完全空閒 |

**YOLO26n 加入後**：

| 模組 | GPU 佔用 | 觸發模式 |
|------|:--------:|----------|
| YOLO26n TensorRT | 30-50%（推估） | 常駐（10-15 FPS） |
| Whisper Small CUDA | 60-80%（推估） | 觸發式（語音偵測時才跑） |
| **同時推理** | **90-130%** | **時間分割** |

**GPU 時間分割策略**：
- Whisper 是**觸發式**：只有偵測到語音時才跑 CUDA 推理（每次 ~1-3 秒）
- YOLO26n 是**常駐式**：持續推理但可降頻（如 5 FPS）
- **衝突窗口**：Whisper 推理期間（~1-3s），YOLO26n 推理會被 GPU scheduling 延遲
- **預期影響**：Whisper 推理期間 YOLO26n FPS 下降 30-50%，但不會 OOM
- **緩解措施**：YOLO26n node 可訂閱 `/state/interaction/speech` 狀態，語音推理時主動降頻或暫停

### 4.4 INT8 量化備案

若 FP16 資源不足，可進一步量化至 INT8：

| 指標 | FP16 | INT8 | 差異 |
|------|:----:|:----:|:----:|
| 模型體積 | ~5 MB | ~2.5 MB | -50% |
| GPU 記憶體 | ~0.3-0.5 GB | ~0.15-0.3 GB | -40-50% |
| 推理速度 | ~4-6ms | ~2-4ms | +30-50% |
| mAP 損失 | 基準 | -0.5~1.5% | 可接受 |

INT8 量化需要 calibration dataset（~100-500 張），可用 COCO val2017 子集。

### 4.5 TensorRT 匯出注意事項

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.export(
    format="engine",        # TensorRT engine
    half=True,              # FP16
    imgsz=640,              # 輸入解析度
    device=0,               # GPU device
    simplify=True,          # ONNX 簡化
    workspace=4,            # TensorRT workspace (GB)
    # YOLO26 NMS-free 特有：
    # end2end=True 不需要額外指定，YOLO26 預設 NMS-free output
)
```

**YOLO26 NMS-free 輸出格式**：
- 傳統 YOLO：`[batch, num_anchors, 85]`（需 NMS 後處理）
- YOLO26：`[batch, max_det, 6]`（直接輸出 `[x1, y1, x2, y2, confidence, class_id]`）
- **不需要 `end2end=True` 參數**——YOLO26 架構本身就是端到端

**Jetson 匯出注意**：
- 必須在 Jetson 本機匯出（TensorRT engine 與 GPU 架構綁定）
- 首次匯出耗時 5-15 分鐘（TensorRT optimization）
- 匯出後的 `.engine` 檔案可重複使用，不需每次重新匯出
- `workspace=4` 可能需調低至 `2`（Jetson 統一記憶體限制）

---

## 5. D435 深度整合設計

> 本節設計已在 `docs/pawai-brain/perception/object/README.md` v1.1 詳細定義，此處摘要關鍵技術決策。

### 5.1 RGB 偵測 + Aligned Depth → 3D 座標

```
D435 RGB ──────→ YOLO26n 偵測 → bbox (x1, y1, x2, y2) + class + confidence
                      │
D435 Aligned Depth ───┤
                      ↓
               深度取樣（bbox 中心 5x5/9x9 中位數）
                      ↓
               CameraInfo 內參 → 反投影 3D 座標 (x, y, z)
                      ↓
               發布 Detection3DArray + 事件 JSON
```

### 5.2 深度取樣策略

**取樣方法**：bbox 中心點周圍 5x5（近距離）或 9x9（遠距離）像素區域：

1. 擷取 bbox 中心 NxN 區域的 depth 值
2. 過濾無效值（`depth == 0`、`NaN`、離群值 > 3 sigma）
3. 取有效值的**中位數**作為代表深度
4. 有效像素比例 < 50% 時，標記 `depth_valid: false`

**為何不用單點深度**：D435 深度圖在物體邊緣常有空洞或噪點，單點採樣容易得到無效值。中位數濾波能有效抑制深度噪點。

### 5.3 有效範圍

| 距離範圍 | D435 精度 | 用途 | 處理方式 |
|----------|:---------:|------|----------|
| < 0.3m | 無效（盲區） | — | 不發布 3D，僅 2D |
| 0.3-1.5m | 高（±1-2cm） | 主要互動範圍 | 完整 3D 座標 |
| 1.5-3.0m | 中（±3-5cm） | 環境感知 | 3D 座標（標註精度等級） |
| > 3.0m | 低（>10cm） | 僅供參考 | 2D bbox 為主 |

### 5.4 時間同步

使用 ROS2 `message_filters.ApproximateTimeSynchronizer`：

```python
from message_filters import ApproximateTimeSynchronizer, Subscriber

rgb_sub = Subscriber(self, Image, '/camera/camera/color/image_raw')
depth_sub = Subscriber(self, Image, '/camera/camera/aligned_depth_to_color/image_raw')
info_sub = Subscriber(self, CameraInfo, '/camera/camera/color/camera_info')

sync = ApproximateTimeSynchronizer(
    [rgb_sub, depth_sub, info_sub],
    queue_size=10,
    slop=0.033  # 33ms ≈ 1 frame @ 30fps
)
sync.registerCallback(self._synced_callback)
```

### 5.5 3D 反投影計算

```python
import numpy as np

def pixel_to_3d(u, v, depth_m, camera_info):
    """將像素座標 + 深度轉換為相機座標系 3D 點"""
    fx = camera_info.k[0]  # focal length x
    fy = camera_info.k[4]  # focal length y
    cx = camera_info.k[2]  # principal point x
    cy = camera_info.k[5]  # principal point y

    x = (u - cx) * depth_m / fx
    y = (v - cy) * depth_m / fy
    z = depth_m
    return [x, y, z]  # camera_color_optical_frame
```

---

## 6. ROS2 整合架構（Clean Architecture）

### 6.1 Package 設計

建議新建 `object_perception` package（而非修改已刪除的 `coco_detector`），理由：
- `coco_detector` 原始碼已不存在，僅剩 `__pycache__`
- 新 package 命名與 `face_perception` / `vision_perception` 一致
- 避免歷史包袱，Clean start

### 6.2 目錄結構（Clean Architecture 四層）

```
object_perception/
├── package.xml
├── setup.py
├── setup.cfg
├── config/
│   └── object_perception.yaml          # ROS2 參數預設值
├── launch/
│   └── object_perception.launch.py     # Launch file
├── object_perception/
│   ├── __init__.py
│   │
│   ├── domain/                          # 領域層：純邏輯，無外部依賴
│   │   ├── __init__.py
│   │   ├── entities.py                  # DetectedObject dataclass
│   │   └── interfaces.py               # IObjectDetector / IDepthProvider ABC
│   │
│   ├── application/                     # 應用層：協調推理 + 深度融合
│   │   ├── __init__.py
│   │   └── object_detection_service.py  # 核心服務（推理 + 深度 + 事件建構）
│   │
│   ├── infrastructure/                  # 基礎設施層：具體實作
│   │   ├── __init__.py
│   │   ├── yolo26_adapter.py           # Ultralytics YOLO26 wrapper
│   │   └── d435_depth_provider.py      # D435 深度取樣實作
│   │
│   └── presentation/                    # 表現層：ROS2 node entry point
│       ├── __init__.py
│       └── object_perception_node.py    # ROS2 node（訂閱/發布/參數）
│
└── test/
    ├── __init__.py
    ├── test_entities.py
    ├── test_detection_service.py
    └── test_depth_provider.py
```

### 6.3 領域層設計

```python
# domain/entities.py
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class DetectedObject:
    """單一偵測到的物體"""
    class_name: str               # e.g., "cup"
    class_id: int                 # COCO class ID
    confidence: float             # 0.0 - 1.0
    bbox_xyxy: List[int]          # [x1, y1, x2, y2]
    center_3d: Optional[List[float]] = None  # [x, y, z] meters, camera frame
    depth_valid: bool = False
    track_id: Optional[int] = None

@dataclass
class DetectionFrame:
    """一幀的完整偵測結果"""
    timestamp: float
    frame_id: str                 # "camera_color_optical_frame"
    objects: List[DetectedObject] = field(default_factory=list)
    inference_ms: float = 0.0
```

```python
# domain/interfaces.py
from abc import ABC, abstractmethod
from typing import List
import numpy as np

class IObjectDetector(ABC):
    @abstractmethod
    def detect(self, image: np.ndarray) -> List[dict]:
        """回傳 [{"bbox": [x1,y1,x2,y2], "class_id": int,
                   "class_name": str, "confidence": float}, ...]"""
        ...

    @abstractmethod
    def warmup(self) -> None:
        """模型預熱（TensorRT 首次推理較慢）"""
        ...

class IDepthProvider(ABC):
    @abstractmethod
    def sample_depth(self, depth_image: np.ndarray,
                     bbox: List[int],
                     camera_info: dict) -> tuple:
        """回傳 (center_3d, depth_valid)"""
        ...
```

### 6.4 基礎設施層設計

```python
# infrastructure/yolo26_adapter.py
class YOLO26Adapter(IObjectDetector):
    """Ultralytics YOLO26 wrapper，實作 IObjectDetector 介面"""

    def __init__(self, model_path: str, confidence_threshold: float = 0.5,
                 target_classes: list = None, device: str = "cuda:0"):
        from ultralytics import YOLO
        self._model = YOLO(model_path)
        self._conf_threshold = confidence_threshold
        self._target_classes = target_classes  # None = 全部 80 類
        self._device = device

    def detect(self, image: np.ndarray) -> List[dict]:
        results = self._model.predict(
            image,
            conf=self._conf_threshold,
            classes=self._target_classes,  # COCO class IDs to filter
            device=self._device,
            verbose=False
        )
        # YOLO26 NMS-free: results[0].boxes 已是最終結果
        detections = []
        for box in results[0].boxes:
            detections.append({
                "bbox": box.xyxy[0].cpu().numpy().astype(int).tolist(),
                "class_id": int(box.cls[0]),
                "class_name": results[0].names[int(box.cls[0])],
                "confidence": float(box.conf[0]),
            })
        return detections

    def warmup(self) -> None:
        """空圖推理觸發 TensorRT/CUDA JIT 編譯"""
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self.detect(dummy)
```

### 6.5 ROS2 介面定義

#### 發布 Topics

| Topic | Message Type | 頻率 | 說明 |
|-------|--------------|:----:|------|
| `/perception/object/detections` | `vision_msgs/Detection2DArray` | 10-15 Hz | 2D 偵測結果（主要消費者：PawAI Studio） |
| `/perception/object/3d_detections` | `vision_msgs/Detection3DArray` | 10-15 Hz | 3D 偵測結果（含深度，`enable_3d=true` 時） |
| `/events/object_detected` | `std_msgs/String` (JSON) | 觸發式 | 高層事件（新物體出現/消失時觸發） |
| `/perception/object/debug_image` | `sensor_msgs/Image` | 5-10 Hz | 視覺化 debug 圖（可透過參數關閉） |

#### 訂閱 Topics

| Topic | Message Type | 說明 |
|-------|--------------|------|
| `/camera/camera/color/image_raw` | `sensor_msgs/Image` | D435 RGB |
| `/camera/camera/aligned_depth_to_color/image_raw` | `sensor_msgs/Image` | D435 Aligned Depth |
| `/camera/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 相機內參 |

#### ROS2 參數

| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `model_path` | string | `"yolo26n.engine"` | TensorRT engine 路徑 |
| `confidence_threshold` | double | `0.5` | 偵測信心閾值 |
| `target_classes` | string[] | `["person","chair","table","cup","bottle","dog"]` | 偵測類別白名單 |
| `enable_3d` | bool | `true` | 是否啟用深度整合 |
| `enable_debug_image` | bool | `true` | 是否發布 debug 圖 |
| `depth_topic` | string | `"/camera/camera/aligned_depth_to_color/image_raw"` | 深度 topic |
| `inference_device` | string | `"cuda:0"` | 推理裝置 |
| `publish_rate_hz` | double | `10.0` | 最大發布頻率 |
| `depth_sample_size` | int | `5` | 深度取樣區域邊長（5=5x5） |

#### 事件 JSON Schema（對齊 `docs/pawai-brain/perception/object/README.md` v1.1）

```json
{
  "event_type": "object_detected",
  "source": "object_perception",
  "timestamp": 1710000000.123,
  "frame_id": "camera_color_optical_frame",
  "payload": {
    "class_name": "cup",
    "class_id": 41,
    "confidence": 0.87,
    "bbox_xyxy": [120, 80, 220, 210],
    "center_3d": [0.62, -0.14, 1.08],
    "depth_valid": true,
    "track_id": 7
  }
}
```

---

## 7. P0 偵測類別

### 7.1 P0 必測類別（6 類）

| 類別 | COCO ID | 用途 | 風險 | 選擇理由 |
|------|:-------:|------|:----:|----------|
| `person` | 0 | 人員偵測，與 face_perception 互補 | 低 | COCO 最強類別，大目標 |
| `chair` | 56 | 家具感知，場景描述 | 低 | 室內常見，大目標，辨識穩定 |
| `table` | 60 | 家具感知，場景描述 | 低 | dining table，室內常見 |
| `cup` | 41 | 小物件尋找，展示亮點 | 中 | 小目標，遮擋風險，但 Demo 價值高 |
| `bottle` | 39 | 小物件尋找，展示亮點 | 中 | 小目標，透明物體深度不穩定 |
| `dog` | 16 | 寵物互動，專案主題呼應 | 中 | 動態目標，但 COCO 訓練充分 |

### 7.2 選擇理由

本專案定位為**室內陪伴場景**，核心互動空間為客廳/臥室。P0 類別覆蓋：
- **人物**（person）：最基本的互動對象
- **家具**（chair, table）：空間理解的錨點
- **小物件**（cup, bottle）：「幫我找杯子」是高展示價值的情境
- **寵物**（dog）：專案名稱「老人與狗」的核心元素

### 7.3 P1 擴充候選

| 類別 | COCO ID | 優先理由 |
|------|:-------:|----------|
| `sofa` | 57 | 家具補充 |
| `laptop` | 63 | 電子產品 |
| `backpack` | 24 | 個人物品 |
| `remote` | 65 | 小物件（高難度） |
| `book` | 73 | 扁平物體（高難度） |

> P1 類別在 4/13 前根據 Demo 需求決定是否納入。非標準 COCO 類別（如 toy, slipper）需 fine-tuning，本階段不考慮。

---

## 8. 與現有系統的整合點

### 8.1 與 face_perception 共用 D435

- **共用感測器**：兩個 package 都訂閱 D435 的 RGB topic
- **無衝突**：ROS2 topic 訂閱是 publish-subscribe 模式，多個 subscriber 各自獨立
- **深度互補**：face_perception 目前使用 D435 depth 做距離估計，object_perception 也使用 aligned depth
- **注意**：不可同時對 D435 做不同 resolution/fps 設定。兩個模組須對齊 D435 launch 參數

### 8.2 與 interaction_router / llm_bridge 的事件流

```
object_perception_node
    │
    ├─ /events/object_detected ──→ interaction_router ──→ 高層決策事件
    │                                                      │
    │                                                      ├─ /event/interaction/object_report
    │                                                      └─ （未來：觸發 Go2 動作）
    │
    └─ /events/object_detected ──→ llm_bridge_node ──→ 場景描述 context
                                    （將偵測結果注入 LLM prompt）
```

**典型情境**：
1. YOLO26n 偵測到 `cup` 在 (0.6m, -0.1m, 1.1m)
2. `interaction_router` 收到事件，判斷是否需要主動通知（e.g., 新物體出現）
3. 使用者問「桌上有什麼？」→ `llm_bridge` 將最近偵測結果注入 LLM context
4. LLM 回覆：「桌上有一個杯子和一個瓶子」

### 8.3 與 PawAI Studio 的 WebSocket Bridge

`/perception/object/detections` 和 `/perception/object/debug_image` 可透過 Foxglove Bridge 直接串流至 PawAI Studio 前端，提供：
- **即時物體偵測 overlay**（debug_image）
- **3D 散點圖**（3d_detections → 前端視覺化）
- **偵測歷史**（事件 log）

### 8.4 Topic Naming 慣例

遵循專案既有慣例：
- **感知狀態**：`/perception/{module}/{data_type}`（如 `/perception/object/detections`）
- **高層事件**：`/events/{event_name}`（如 `/events/object_detected`）
- **Debug 圖**：`/perception/{module}/debug_image`（與 `/face_identity/debug_image` 對齊）

---

## 9. 實作路線圖

### 總計：~3 天（有效工作日）

| Phase | 工作內容 | 時間 | 驗收標準 | 依賴 |
|:-----:|---------|:----:|---------|------|
| **0** | 環境驗證 | 0.5d | Jetson 上 `ultralytics` 可 import、YOLO26n.pt 可下載、TensorRT engine 可匯出 | Jetson 網路 |
| **1** | 最小 ROS2 Node | 1.0d | 訂閱 D435 RGB → YOLO26n 推理 → 發布 Detection2DArray + debug_image，5 分鐘無 crash | Phase 0 |
| **2** | 深度整合 | 0.5d | 啟用 aligned depth → 發布 Detection3DArray，depth_valid 正確標記 | Phase 1 |
| **3** | 共存壓測 | 0.5d | face + vision + object + speech 四感知同跑 60s，RAM < 6.8GB、無 OOM | Phase 2 |
| **4** | Demo 整合 | 0.5d | events/object_detected → interaction_router 可收到，PawAI Studio 可顯示 debug_image | Phase 3 |

### Phase 0：環境驗證（0.5 天）

```bash
# 1. 安裝 ultralytics（Jetson 上）
uv pip install ultralytics

# 2. 驗證 import
python3 -c "from ultralytics import YOLO; print('OK')"

# 3. 下載 YOLO26n 並匯出 TensorRT
python3 -c "
from ultralytics import YOLO
model = YOLO('yolo26n.pt')
model.export(format='engine', half=True, imgsz=640, workspace=2)
print('TensorRT export OK')
"

# 4. 單張圖片推理測試
python3 -c "
from ultralytics import YOLO
model = YOLO('yolo26n.engine')
results = model.predict('https://ultralytics.com/images/bus.jpg', verbose=True)
print(f'Detected {len(results[0].boxes)} objects')
"
```

**Phase 0 的 Kill Switch**：若 TensorRT 匯出失敗或 RAM 超標，立即評估 ONNX Runtime 備案或降級至 320x320 解析度。

### Phase 1：最小 ROS2 Node（1 天）

- 建立 `object_perception` package 骨架
- 實作 `YOLO26Adapter`（推理核心）
- 實作 `object_perception_node.py`（訂閱 RGB → 推理 → 發布 Detection2DArray + debug_image）
- 不含深度整合，純 2D 偵測
- unit test：`test_entities.py`

### Phase 2：深度整合（0.5 天）

- 實作 `D435DepthProvider`
- 加入 `ApproximateTimeSynchronizer`
- 發布 Detection3DArray + 事件 JSON
- unit test：`test_depth_provider.py`

### Phase 3：共存壓測（0.5 天）

```bash
# 四感知 + 語音同跑壓測腳本（參考 scripts/start_stress_test_tmux.sh）
bash scripts/start_object_stress_test_tmux.sh 60
# 監控：RAM、GPU、溫度、FPS
```

### Phase 4：Demo 整合（0.5 天）

- `interaction_router` 新增 object event 處理規則
- `llm_bridge` 注入偵測 context
- PawAI Studio Foxglove panel 設定
- End-to-end smoke test

---

## 10. 風險與緩解

| # | 風險 | 可能性 | 影響 | 緩解措施 |
|---|------|:------:|:----:|----------|
| R1 | TensorRT 匯出失敗（YOLO26 架構 op 不支援） | 低 | 高 | 改用 ONNX Runtime GPU；或退回 YOLO11n（NMS 版本，已驗證 TensorRT 支援） |
| R2 | GPU 記憶體爭搶（Whisper + YOLO 同時推理 OOM） | 中 | 高 | 時間分割策略：語音推理時 YOLO 暫停；或 YOLO 改走 CPU（3-5 FPS） |
| R3 | Python inference overhead 導致 FPS < 10 | 中 | 中 | 降解析度 640→320（FPS 約 x2-3）；或降發布頻率至 5 Hz |
| R4 | RAM 超過 6.8GB 安全線 | 低-中 | 高 | INT8 量化（RAM 減 40-50%）；或關閉 debug_image（省 ~0.1GB） |
| R5 | MediaPipe 0.10.18 鎖定與 ultralytics 版本衝突 | 低 | 中 | `uv pip install` 隔離；或 ultralytics 固定版本避免拉升 MediaPipe |
| R6 | D435 aligned depth 與 RGB 時間同步不穩 | 低 | 低 | `ApproximateTimeSynchronizer` slop 放寬至 50ms；或改用事後 depth lookup |
| R7 | 小物件（cup/bottle）偵測不穩定 | 中 | 低 | 降低 confidence_threshold 至 0.3（增加 recall）；Demo 時使用高對比度物體 |
| R8 | `ultralytics` 在 Jetson ARM64 安裝困難 | 低 | 高 | 已知 Jetson AI Lab 有 ultralytics wheel；或手動安裝 dependencies |

### 最壞情境降級方案

若所有 GPU 路徑都失敗：
1. **YOLO26n CPU ONNX**：67.8ms/frame ≈ 15 FPS（官方 CPU 數據，Jetson CPU 可能 3-8 FPS）
2. **YOLO26n CPU + 降解析度 320x320**：預估 8-15 FPS
3. **最後手段**：雲端推理（送 RGB frame 到 RTX 8000，延遲 100-300ms，但不受 Jetson 限制）

---

## 11. 與其他方案的比較

### 11.1 vs coco_detector（已刪除的舊方案）

| 維度 | coco_detector (FasterRCNN) | YOLO26n |
|------|:-------------------------:|:-------:|
| 模型大小 | ~160 MB | ~5 MB |
| mAP (COCO) | ~37% (ResNet-50-FPN) | 40.1% |
| Jetson FPS | 1-3 FPS (CPU-only) | 10-15 FPS (TensorRT) |
| 深度整合 | 無 | 有（D435 aligned depth） |
| NMS | 需要 | 不需要 |
| 部署難度 | 高（torchvision + CPU 推理慢） | 低（Ultralytics 一鍵匯出） |
| 狀態 | **原始碼已刪除** | 建議採用 |

**結論**：YOLO26n 在所有維度全面優於 FasterRCNN。舊方案無復活價值。

### 11.2 vs YOLOE（開放詞彙偵測）

| 維度 | YOLOE-26l-seg | YOLO26n |
|------|:------------:|:-------:|
| 能力 | 開放詞彙 + 分割 | 固定 80 類偵測 |
| 模型大小 | ~100+ MB | ~5 MB |
| Jetson 可行性 | 困難（RAM + GPU 不足） | 可行 |
| 適用位置 | **雲端 RTX 8000** | **本地 Jetson** |
| 延遲 | 200-500ms (雲端含網路) | 25-50ms (本地) |

**結論**：YOLOE 適合作為雲端 B 線（`docs/pawai-brain/perception/object/README.md` §3.1 的 B 線候選），不適合本地部署。未來可作為「使用者問什麼就偵測什麼」的進階能力。

### 11.3 vs Qwen-VL（視覺問答）

| 維度 | Qwen-VL-7B | YOLO26n |
|------|:----------:|:-------:|
| 能力 | 視覺理解 + 自然語言 | 固定類別偵測 |
| 模型大小 | ~15-20 GB | ~5 MB |
| Jetson 可行性 | 不可能 | 可行 |
| 適用位置 | **雲端 RTX 8000** | **本地 Jetson** |
| 互補性 | 高（語意理解） | 高（即時感知） |

**結論**：Qwen-VL 是雲端 C 線候選。可與本地 YOLO26n 互補：YOLO26n 提供即時偵測結果，Qwen-VL 在需要時提供深度語意理解（「那個紅色的東西是什麼？」）。

### 11.4 方案選型矩陣

| 方案 | 本地即時 | 精度 | 開放詞彙 | 語意理解 | RAM | 建議位置 |
|------|:-------:|:----:|:--------:|:--------:|:---:|----------|
| **YOLO26n** | **10-15 FPS** | 40.1% | No | No | 0.6-1.1 GB | **Jetson 主線** |
| YOLOE-26l | 不適用 | 更高 | **Yes** | No | ~10+ GB | 雲端 B 線 |
| Qwen-VL | 不適用 | N/A | **Yes** | **Yes** | ~20+ GB | 雲端 C 線 |
| YOLO26x | 不適用 | 54.6% | No | No | ~5+ GB | 雲端 A 線 |

---

## 12. 參考資料

### 模型與框架

| 資源 | URL |
|------|-----|
| Ultralytics YOLO26 官方文件 | https://docs.ultralytics.com/models/yolo26/ |
| YOLO26 GitHub Release | https://github.com/ultralytics/ultralytics |
| YOLO26 vs YOLO11 Benchmark | https://docs.ultralytics.com/models/yolo26/#supported-tasks-and-modes |
| Ultralytics TensorRT 匯出指南 | https://docs.ultralytics.com/modes/export/#tensorrt |
| Ultralytics Jetson 部署指南 | https://docs.ultralytics.com/guides/nvidia-jetson/ |

### 專案內部文件

| 文件 | 路徑 |
|------|------|
| 物體辨識模組設計 v1.1 | `docs/pawai-brain/perception/object/README.md` |
| ROS2 介面契約 v2.1 | `docs/contracts/interaction_contract.md` |
| PawAI Mission v2.2 | `docs/mission/README.md` |
| 3/23 三感知壓測數據 | `docs/archive/2026-05-docs-reorg/research-misc/` + MEMORY.md |
| Benchmark 框架規格 | `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-19-unified-benchmark-framework-design.md` |

### 硬體規格

| 資源 | 說明 |
|------|------|
| Jetson Orin Nano Datasheet | 67 TOPS (INT8), 8GB LPDDR5, NVIDIA Ampere GPU (1024 CUDA cores) |
| Intel RealSense D435 | 1280x720 RGB + 1280x720 Depth, USB 3.0, 0.3-3m 有效範圍 |
| NVIDIA T4 (benchmark 參考) | 65 TFLOPS (FP16), 16GB GDDR6 |

---

## 版本紀錄

| 版本 | 日期 | 修改內容 |
|------|------|----------|
| v1.0 | 2026-03-25 | 初版可行性研究報告 |
