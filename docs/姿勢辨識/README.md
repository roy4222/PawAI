# 姿勢辨識系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 辨識人體姿勢，觸發對應行為
- **4 種基本姿勢**：站立 (standing)、坐下 (sitting)、蹲下 (crouching)、跌倒 (fallen)
- **4/13 Demo 目標**：4 種姿勢辨識成功率 ≥ 70%（Demo B）
- **跌倒偵測為安全功能**：辨識到 fallen → 觸發語音警報 + PawAI Studio 強制展開 PosePanel

---

## 技術選型結論（2026-03-16）

### 推薦方案：與手勢辨識共用 DWPose

| 優先序 | 方案 | 理由 |
|:------:|------|------|
| **首選** | **DWPose + TensorRT**（RTMPose 為備援） | 社群回報 Orin Nano ~45 FPS（待本機驗證）、133 keypoints 含 body + foot + hand + face、一個模型同時搞定手勢+姿勢 |
| 次選 | trt_pose (NVIDIA) | TensorRT 原生、Jetson Nano 上 ResNet 15-16 FPS / DenseNet 9-10 FPS |
| **不推薦** | ~~MediaPipe Pose~~ | Jetson ARM64 無官方 pip wheel、CPU-only ~7-20 FPS |
| 不推薦 | MoveNet | 只有 17 keypoints、無手部、Jetson GPU delegate 有問題 |

### DWPose vs RTMPose 差異

> 詳見 [`../手勢辨識/README.md`](../手勢辨識/README.md) § DWPose vs RTMPose 差異

- **DWPose**：whole-body 133 keypoints 蒸餾版，本專案目標方案
- **RTMPose**：MMPose 原版，ONNX/TensorRT 匯出較成熟，備援路線

### 為什麼跟手勢辨識共用 DWPose？

DWPose 一次推理輸出 133 個 keypoints（[COCO-WholeBody](https://github.com/jin-s13/COCO-WholeBody) 標準）：
- **17 body keypoints** → 餵給姿勢分類器（standing/sitting/crouching/fallen）
- **6 foot keypoints**（左右腳各 3）→ 輔助姿勢判斷（腳尖/腳跟方向）
- **21 hand keypoints ×2** → 餵給手勢分類器（wave/stop/point/ok）
- **68 face keypoints** → 備用（表情辨識等）

**只跑一個模型，分兩個分類器**，比分開跑 Hands + Pose 更省資源。

### 落地策略：先分開做，共用推理

```
D435 camera frame
  ↓
DWPose 推理（TensorRT, ~22ms/frame）
  ↓ 133 keypoints
  ├── body keypoints (17) + foot (6) → pose_classifier → /event/pose_detected
  └── hand keypoints (21×2) → gesture_classifier → /event/gesture_detected
```

這完全符合你的建議「先分開做分類器，共用底層推理」。

---

## ⚠️ MediaPipe Pose 在 Jetson 上的已知問題

> 與手勢辨識相同的問題，見 [`../手勢辨識/README.md`](../手勢辨識/README.md)

1. **無法 `pip install`**：PyPI 無 Linux ARM64 wheel
2. **GPU 加速不可用**：TFLite GPU delegate 在 Jetson 上失效
3. **CPU-only 效能差**：Jetson Nano 上 ~7 FPS（CPU），Orin Nano 推估 10-25 FPS
4. **model_complexity=2 太重**：~80-100ms/frame，不適合即時

**結論**：MediaPipe Pose 適合楊在 x86 筆電上做概念驗證（UX 流程與事件格式），**不適合 Jetson 部署**。

> **⚠️ 移植風險提醒**：MediaPipe Pose（33 keypoints, 含 3D 座標）與 DWPose body（17 keypoints, COCO format, 2D only）的 keypoint 集合、索引、座標系統完全不同。Phase 1 的 x86 demo **只驗證 UX 互動流程與 ROS2 事件格式**，不驗證最終分類閾值。Phase 2 部署 DWPose 時，角度閾值、高度比、投票 buffer 參數都需要對照 COCO 17-point 定義重新校正。

---

## 方案比較（Jetson Orin Nano 8GB）

| 方案 | Body Keypoints | FPS (Orin Nano) | 記憶體 | 3D 座標 |
|------|:--------------:|:---------------:|:------:|:-------:|
| **DWPose** (RTMPose) | 17 body + 6 foot + hand/face | ~45 FPS † | ~200MB | ❌ 2D |
| **trt_pose** | 17-18 | 15-16 FPS (Nano) | ~150MB | ❌ 2D |
| MediaPipe Pose | 33 | 7-25 FPS (CPU) | ~150-300MB | ✅ 有 |
| MoveNet Lightning | 17 | 無 Jetson 數據 | — | ❌ 2D |

> † DWPose 45 FPS 數據來自[社群實作文章](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)，非官方 benchmark。需以本專案 Jetson Orin Nano + JetPack 6.x 實測確認。

---

## 姿勢分類方法

### 方法一：角度法（推薦，最直觀）

用 body landmarks 計算關節角度，規則分類：

| 角度 | Landmarks | 站立 | 坐下 | 蹲下 | 跌倒 |
|------|-----------|:----:|:----:|:----:|:----:|
| **髖關節角度** (肩→髖→膝) | shoulder, hip, knee | >160° | 70-120° | <70° | 不定 |
| **膝關節角度** (髖→膝→踝) | hip, knee, ankle | >160° | 70-120° | <70° | 不定 |
| **軀幹角度** (肩→髖→垂直線) | shoulder, hip | 0-15° | 0-30° | 15-60° | >60° |

**關鍵 Landmarks**（DWPose 17-point COCO format）：

| ID | 名稱 | 用途 |
|----|------|------|
| 5, 6 | 左/右肩膀 | 軀幹上端 |
| 11, 12 | 左/右髖 | 核心判斷點 |
| 13, 14 | 左/右膝 | 坐/蹲判斷 |
| 15, 16 | 左/右踝 | 腿部角度 |
| 0 | 鼻子 | 高度參考 |

### 方法二：高度比法（跌倒偵測首選）

| 特徵 | 計算方式 | 閾值 |
|------|---------|------|
| **Bounding Box 寬高比** | width / height | >1.0 → 疑似跌倒（人體水平） |
| **肩-髖高度差** | abs(shoulder_y - hip_y) / body_height | <0.3 → 疑似跌倒 |
| **髖部下降速度** | Δhip_y / Δt | 突然下降 → 觸發 |

### 方法三：混合法（推薦實作方式）

```python
# 虛擬碼：4 姿勢分類
def classify_pose(landmarks, prev_landmarks, buffer):
    hip_angle = calc_angle(shoulder, hip, knee)
    knee_angle = calc_angle(hip, knee, ankle)
    trunk_angle = calc_trunk_angle(shoulder, hip)
    bbox_ratio = calc_bbox_ratio(landmarks)

    # 1. 跌倒優先判斷（安全功能）
    if bbox_ratio > 1.0 and trunk_angle > 60:
        buffer.append("fallen")
    # 2. 站立
    elif hip_angle > 160 and knee_angle > 160:
        buffer.append("standing")
    # 3. 坐下
    elif 70 < hip_angle < 130 and trunk_angle < 30:
        buffer.append("sitting")
    # 4. 蹲下
    elif hip_angle < 80 and knee_angle < 80:
        buffer.append("crouching")

    # 20 幀投票機制（減少誤報）
    if len(buffer) >= 20:
        return most_common(buffer[-20:])
```

### 跌倒偵測精度（研究數據）

| 方法 | 精度 | 召回率 | 來源 |
|------|:----:|:-----:|------|
| MediaPipe + 20-frame voting | 86.9% | 93.8% | arxiv 2503.19501 |
| MediaPipe + Transformer | 97.6% | — | MDPI Sensors 2024 |
| MediaPipe + handcrafted features | 88.8% precision | 94.1% | arxiv 2503.01436 |
| 3D pose + TCN (temporal) | 99.9% | — | Nature 2025 |

**⚠️ 真實部署注意事項**：
- 老人緩慢坐下 vs 跌倒 → 容易誤判，需要**時序分析**
- 彎腰撿東西 → 短暫觸發 fallen → 需要**投票 buffer**
- D435 深度資訊可輔助：突然高度驟降 = 更可靠的跌倒判斷

---

## ROS2 整合

### Node 設計

> 若採方案 A（推薦），此 node 為 `vision_perception_node`，同時負責手勢+姿勢。
> 若採方案 B，此 node 為 `pose_perception_node`（對齊 `interaction_contract.md` 命名）。
> 詳見下方 § 可能的 Node 架構。

```
vision_perception_node (方案 A) / pose_perception_node (方案 B)
  ├── Subscribe: /camera/color/image_raw (sensor_msgs/Image)
  ├── 推理: DWPose TensorRT
  ├── 分類: rule-based classifier
  ├── Publish: /event/pose_detected (std_msgs/String, JSON)         ← v2.0 凍結介面
  └── Publish: /state/perception/pose (std_msgs/String, JSON)      ← v2.1 擬新增（見下方說明）
```

### Event Schema（對齊 `interaction_contract.md` v2.0）

```json
{
  "stamp":       1710000000.123,
  "event_type":  "pose_detected",
  "pose":        "standing",
  "confidence":  0.92,
  "track_id":    1
}
```

**觸發規則**：
- 姿勢**變化**時發布事件（不是每幀都發）
- `fallen` 事件**立即發布**（不等投票完成，但加 low-confidence flag）
- 穩定 20 幀後才發布確認事件（high-confidence）

### State Schema（v2.1 擬新增 topic，尚未納入凍結介面）

> **⚠️ Contract 邊界說明**：`interaction_contract.md` v2.0 只凍結了 `/event/pose_detected`，
> **`/state/perception/pose` 不在 v2.0 凍結範圍內**。此 state topic 屬於 v2.1 擬新增項目，
> 4/13 前可先作為內部 topic 使用，不納入凍結介面。正式納入需經 System Architect 核准。
> `event-schema.md` v1.0 中的 `PoseState` 型別定義是**前端 store 用的資料結構**，
> 與 ROS2 layer 的 topic 凍結是兩件事。

```json
{
  "stamp":         1710000000.123,
  "active":        true,
  "current_pose":  "standing",
  "confidence":    0.92,
  "track_id":      1,
  "status":        "active"
}
```

### PawAI Studio 特殊行為

- `pose_detected (fallen)` → **強制展開 PosePanel**（見 `ui-orchestration.md`）
- 其他姿勢 → 正常更新 PosePanel 狀態

---

## 與手勢辨識共用架構

### 共用推理，分類器獨立

```
D435 RGB frame (30 FPS)
  ↓
[DWPose TensorRT 推理] ← 一次推理，~22ms
  ↓ 133 keypoints
  ├── body (17) + foot (6) → pose_classifier.py → /event/pose_detected
  │                                              → /state/perception/pose (v2.1 內部)
  └── hand (21×2) → gesture_classifier.py → /event/gesture_detected
```

**好處**：
- 一個模型、一次推理、兩個分類器
- 分類器獨立，好 debug（哪邊錯一眼看出來）
- 記憶體只佔 ~200MB（不是 400MB）

### 可能的 Node 架構

**方案 A：單一 Node（推薦）**
```
vision_perception_node          ← 統一命名
  ├── DWPose 推理
  ├── pose_classifier → /event/pose_detected
  └── gesture_classifier → /event/gesture_detected
```

**方案 B：推理 + 分類分開**
```
dwpose_inference_node → /internal/keypoints (內部 topic)
  ├── pose_perception_node → /event/pose_detected
  └── gesture_perception_node → /event/gesture_detected
```

方案 A 延遲更低（省一次 topic 傳輸），方案 B 更好 debug。
建議 Phase 1 用 A，有問題再拆成 B。

> **命名約定**：方案 A 用 `vision_perception_node`（統一入口）；方案 B 拆分時沿用 `interaction_contract.md` 中的 `pose_perception_node` / `gesture_perception_node`。前面 Node 設計段落中的 `pose_perception_node` 是方案 B 語境下的命名。

---

## 記憶體預算（與手勢辨識共用）

DWPose 一個模型同時處理手勢+姿勢，記憶體只算一次：

| 模組 | 記憶體占用 |
|------|:--------:|
| DWPose TensorRT（手勢+姿勢共用） | ~200MB |
| 分類器邏輯（純 Python 規則） | ~10MB |
| **合計** | **~210MB** |

加上現有模組，總共 ~5.1-5.9GB，剩餘 ≥ 2GB。✅

---

## 落地順序

| Phase | 時間 | 內容 | 負責 |
|:-----:|------|------|:----:|
| 1 | 3/16-3/23 | 楊在 x86 筆電用 MediaPipe Pose demo 驗證 UX 流程與事件格式 | 楊 |
| 2 | 3/23-4/1 | Roy 在 Jetson 部署 DWPose + TensorRT，重新校正分類閾值 | Roy |
| 3 | 4/1-4/6 | 整合 pose_classifier + gesture_classifier 進 ROS2 node | Roy |
| 4 | 4/6-4/13 | 端到端測試 + Demo B 微調 | Roy + 楊 |

---

## 參考資源

### 首選方案
- [DWPose / RTMPose (MMPose)](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)
- [DWPose Wholebody on Jetson](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)

### 次選方案
- [trt_pose (NVIDIA)](https://github.com/NVIDIA-AI-IOT/trt_pose)

### 姿勢分類研究
- [Posture Detection System - LearnOpenCV](https://learnopencv.com/building-a-body-posture-analysis-system-using-mediapipe/)
- [Pose-Based Fall Detection - arxiv 2503.19501](https://arxiv.org/html/2503.19501v1)
- [Fall Detection from Videos - arxiv 2503.01436](https://arxiv.org/pdf/2503.01436)
- [Sitting Posture Detection (2025)](https://dl.acm.org/doi/10.1145/3776865.3776880)
- [Fall Detection using Pose Estimation - TDS](https://towardsdatascience.com/fall-detection-using-pose-estimation-a8f7fd77081d/)

### MediaPipe（僅限 x86 開發機 demo）
- [MediaPipe Pose](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md)
- [MediaPipe Jetson 安裝問題](https://forums.developer.nvidia.com/t/does-jetson-orin-nano-support-mediapipe/290797)
