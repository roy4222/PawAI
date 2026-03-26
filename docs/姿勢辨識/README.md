# 姿勢辨識系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 辨識人體姿勢，觸發對應行為
- **5 種姿勢**：站立 (standing)、坐下 (sitting)、蹲下 (crouching)、跌倒 (fallen)、彎腰 (bending)
- **4/13 Demo 目標**：5 種姿勢辨識成功率 ≥ 70%（Demo B）
- **跌倒偵測為安全功能**：辨識到 fallen → 觸發語音警報 + PawAI Studio 強制展開 PosePanel

---

## 技術選型結論（2026-03-25 更新）

### 主線方案：MediaPipe Pose（CPU-only）

| 優先序 | 方案 | 理由 |
|:------:|------|------|
| **主線** | **MediaPipe Pose** | CPU 18.5 FPS（Jetson 實測），GPU 0%，三感知壓測通過（RAM 1.2GB, temp 52°C），3/23 場景驗證通過 |
| 備援 | **rtmlib + RTMPose lightweight** | GPU 加速可用，但 balanced mode 91-99% GPU 滿載；lightweight 未測但預期更快 |
| 備援 | trt_pose (NVIDIA) | TensorRT 原生、Jetson Nano 上 社群值：ResNet 15-16 FPS / DenseNet 9-10 FPS |
| 不推薦 | MoveNet | 只有 17 keypoints、無手部、Jetson GPU delegate 有問題 |

> **決策變更紀錄（3/21）**：原推薦 RTMPose wholebody 為主路徑，但 Jetson 實測 GPU 91-99% 滿載。3/21 決策改為全 MediaPipe CPU pipeline，GPU 0% 的特性有利於多感知共存。MediaPipe Pose CPU 18.5 FPS 已足夠展示需求。

### 與手勢辨識的架構關係

**現行架構（3/25）**：MediaPipe Pose + MediaPipe Gesture Recognizer 各自獨立運行，皆為 CPU-only，GPU 0%。

```
D435 camera frame
  ↓
vision_perception_node（統一入口）
  ├── MediaPipe Pose（CPU, 18.5 FPS）→ pose_classifier → /event/pose_detected
  └── MediaPipe Gesture Recognizer（CPU, 7.2 FPS）→ /event/gesture_detected
```

**備援架構**：RTMPose wholebody 單模型同時產出 body + hand keypoints，一次推理兩個分類器。但 GPU 91-99% 滿載，已降為備援。

---

## MediaPipe Pose 在 Jetson 上的實測結果

> **2026-03-21 實測推翻先前調查結論**：MediaPipe Pose 在 Jetson ARM64 上可以正常運行（CPU-only），確定為主線方案。

**Jetson 實測數據（3/21-3/23）**：
- **FPS**：18.5 FPS（CPU-only，pose_complexity=1）
- **GPU 佔用**：0%（純 CPU 推理）
- **RAM 佔用**：三感知同跑（face+pose+gesture）1.2GB
- **溫度**：52°C（三感知壓測 60s）
- 33 keypoints（含 3D 座標），pose_classifier 使用其中的 body keypoints 做角度法分類

**先前調查（3/16，已推翻）曾認為**：
1. ~~無法 pip install~~（實際可用）
2. ~~GPU 加速不可用~~（CPU-only 即已足夠）
3. ~~CPU-only 效能差~~（實測 18.5 FPS，完全可用）

**結論**：MediaPipe Pose CPU-only 18.5 FPS 已足夠展示需求，且 GPU 0% 有利於多感知共存。

---

## 方案比較（Jetson Orin Nano 8GB — 2026-03-25 實測數據更新）

| 方案 | Body Keypoints | FPS (Orin Nano) | GPU 佔用 | 3D 座標 | 狀態 |
|------|:--------------:|:---------------:|:--------:|:-------:|:----:|
| **MediaPipe Pose** | 33 | **18.5 (CPU 實測)** | **0%** | ✅ 有 | **主線** |
| RTMPose wholebody (rtmlib) | 17 body + 6 foot + hand/face | **3.8-7.5 (GPU 實測)** | 91-99% | ❌ 2D | 備援 |
| trt_pose | 17-18 | 社群值：15-16 FPS (Nano) | — | ❌ 2D | 未測 |
| MoveNet Lightning | 17 | 無 Jetson 數據 | — | ❌ 2D | 不推薦 |

### 本專案實測（2026-03-21 ~ 03-23, Jetson Orin Nano + JetPack 6.x）

**主線：MediaPipe Pose（3/21 確定）**

| 項目 | 數值 |
|------|------|
| 方案 | MediaPipe Pose（CPU-only） |
| 輸入 | D435 640x480@15Hz RGB |
| **推理 FPS** | **18.5 FPS** |
| GPU 使用率 | **0%** |
| 溫度 | 52°C（三感知壓測 60s） |
| RAM | 三感知共跑 1.2GB / 7.4GB（餘量充足） |
| pose_detected | ✅ standing/sitting/crouching/fallen/bending 全穩定 |

**L3 三感知壓測結果（3/23）**：face(CPU) + pose(CPU) + gesture(CPU) 同跑 60s → RAM 1.2GB, temp 52°C, GPU 0%。

**備援：RTMPose wholebody（3/18 實測，已降為備援）**

| 項目 | 數值 |
|------|------|
| 方案 | rtmlib 0.0.15 + onnxruntime-gpu 1.23.0（Jetson AI Lab wheel） |
| 模型 | RTMPose wholebody balanced（YOLOX-m + rtmw-dw-x-l） |
| **推理 FPS** | **~7.5 FPS**（隨機噪聲）/ **~3.8 Hz debug_image**（真實 D435 + face 同跑） |
| GPU 使用率 | 91-99%（幾乎滿載） |
| 溫度 | GPU 66°C |

**結論**：MediaPipe Pose CPU 18.5 FPS + GPU 0% 遠優於 RTMPose GPU 滿載方案，且三感知共存零衝突。

---

## 姿勢分類方法

### 方法一：角度法（推薦，最直觀）

用 body landmarks 計算關節角度，規則分類：

| 角度 | Landmarks | 站立 | 坐下 | 蹲下 | 跌倒 |
|------|-----------|:----:|:----:|:----:|:----:|
| **髖關節角度** (肩→髖→膝) | shoulder, hip, knee | >155° | 100-150° | <145° | 不定 |
| **膝關節角度** (髖→膝→踝) | hip, knee, ankle | >155° | — | <145° | 不定 |
| **軀幹角度** (肩→髖→垂直線) | shoulder, hip | 0-15° | <35° | >10° | >60° |

> **3/23 Jetson 實測角度範圍**（MediaPipe Pose, D435 640x480@15Hz）：
> - 站: hip=168-180°, knee=164-180°, trunk=1-10°
> - 坐: hip=91-129°, knee=69-132°, trunk=2-22°
> - 蹲: hip=36-65°, knee=32-57°, trunk=5-17°

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
# 實際分類規則（pose_classifier.py, 3/22 更新，6 類 first-match）
def classify_pose(body_kps, body_scores, bbox_ratio):
    hip_angle = angle(shoulder, hip, knee)
    knee_angle = angle(hip, knee, ankle)
    trunk_angle = trunk_angle(shoulder, hip)

    # 1. 跌倒優先判斷（安全功能）
    if bbox_ratio > 1.0 and trunk_angle > 60:
        return "fallen"
    # 2. 站立（3/23 調參：160→155）
    if hip_angle > 155 and knee_angle > 155:
        return "standing"
    # 3. 彎腰（3/22 新增）
    if trunk_angle > 35 and hip_angle < 140 and knee_angle > 130 and bbox_ratio <= 1.0:
        return "bending"
    # 4. 蹲下（3/23 調參：<80→<145 + trunk>10 前傾條件）
    if hip_angle < 145 and knee_angle < 145 and trunk_angle > 10:
        return "crouching"
    # 5. 坐下（3/23 調參：70-130→100-150）
    if 100 < hip_angle < 150 and trunk_angle < 35:
        return "sitting"
    # 6. 模糊
    return None

    # 投票機制：pose_vote_frames=20（連續 20 幀多數決）
    # confidence = 投票比例（非模型信心度）
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
  ├── 推理: RTMPose wholebody (rtmlib)
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

### event_action_bridge 姿勢→動作映射（2026-03-18）

| 姿勢 | Go2 動作 | TTS | Cooldown |
|------|---------|-----|:--------:|
| `fallen` | — | "偵測到跌倒！請注意安全" | 10s |

> 其他姿勢（standing/sitting/crouching）目前不觸發 Go2 動作，僅透過 `/event/pose_detected` 更新前端狀態。

### PawAI Studio 特殊行為

- `pose_detected (fallen)` → **強制展開 PosePanel**（見 `ui-orchestration.md`）
- 其他姿勢 → 正常更新 PosePanel 狀態

---

## 與手勢辨識共用架構

### 現行架構：MediaPipe 獨立推理（3/21 確定）

```
D435 RGB frame (15 FPS)
  ↓
vision_perception_node（統一入口，CPU-only）
  ├── MediaPipe Pose（18.5 FPS）→ pose_classifier → /event/pose_detected
  │                                                → /state/perception/pose (v2.1 內部)
  └── MediaPipe Gesture Recognizer（7.2 FPS）→ /event/gesture_detected
```

**主線**：MediaPipe Pose + Gesture Recognizer 各自獨立推理，皆為 CPU-only，GPU 0%。
**備援**：rtmlib + RTMPose wholebody 單模型（GPU 密集，已降為備援）。

**好處**：
- GPU 0%，與 face_perception（YuNet CPU）完美共存
- 分類器獨立，好 debug（哪邊錯一眼看出來）
- 三感知壓測通過：RAM 1.2GB, temp 52°C

### Node 架構（已落地）

**方案 A：單一 Node（現行）**
```
vision_perception_node          ← 統一入口
  ├── MediaPipe Pose（CPU, 18.5 FPS）
  │   └── pose_classifier → /event/pose_detected
  └── MediaPipe Gesture Recognizer（CPU, 7.2 FPS）
      └── → /event/gesture_detected
```

> Phase 1 起即採用方案 A（單一 Node），延遲低、好 debug。

---

## 操作限制與已知問題（3/26 會議確認）

### 有效辨識距離
- **有效範圍**：D435 前方約 **4-5m** 以內
- 超過此距離人體 keypoints 偵測率下降，姿勢分類不可靠

### 幽靈跌倒偵測（Phantom Fall Detection）
- **問題**：偶爾在無人跌倒時誤報 `fallen` 事件並觸發語音警告
- **原因**：bbox 寬高比 + trunk angle 判定在某些坐姿/蹲姿下觸發邊界值
- **緩解**：投票 buffer（20 幀多數決）已大幅降低誤報，但未完全消除

### 多人場景
- **僅支援單人追蹤**：多人同時出現時，MediaPipe Pose 只追蹤一人，且可能在人之間跳轉
- 多人場景下 pose 判定不穩定，可能把不同人的關節拼在一起

### 坐姿角度問題
- **側面坐姿**：身體不正面面向攝影機時，hip_angle 和 trunk_angle 計算偏差，sitting 與 standing 易混淆
- **建議**：Demo 時操作者正面面向攝影機（±30°）

---

## 記憶體預算（三感知共存實測）

**L3 壓測實測結果（2026-03-23）**：

| 模組 | 記憶體占用 | GPU |
|------|:--------:|:---:|
| face_perception（YuNet CPU） | 包含在下方 | 0% |
| MediaPipe Pose（CPU） | 包含在下方 | 0% |
| MediaPipe Gesture Recognizer（CPU） | 包含在下方 | 0% |
| **三感知合計** | **1.2GB** | **0%** |
| **溫度** | **52°C** | — |

加上 ROS2 + D435 + 其他常駐，剩餘 ≥ 6GB。遠優於原 RTMPose GPU 方案。

---

## 落地順序（2026-03-25 更新）

| Phase | 時間 | 內容 | 狀態 |
|:-----:|------|------|:----:|
| 1 | 3/16-3/18 | `vision_perception_node` mock mode + 23 unit tests + Jetson smoke test | ✅ 完成 |
| 2 | 3/18 | RTMPose wholebody balanced on Jetson（rtmlib + onnxruntime-gpu），~3.8-7.5 FPS | ✅ 完成 |
| 2b | 3/21 | 決策：全 MediaPipe CPU（pose+gesture），GPU 0%，~18.5 FPS (pose) | ✅ 完成 |
| 3 | 3/22 | bending 新增 + FPS 優化（2.5→8.5 FPS）+ 骨架可視化 + 型別安全 + 32 tests | ✅ 完成 |
| 4 | 3/23 | 三感知壓測通過（face+pose+gesture, RAM 1.2GB, temp 52°C）+ pose debug log 加入 + 閾值第一輪實機調參（standing/sitting/crouching 全穩定） | ✅ 完成 |
| 5 | 4/6-4/13 | 端到端測試 + Demo B 微調 | 待做 |

---

## 2D Pose vs 3D Pose

### 為什麼本專案選 2D？

| 維度 | 2D Pose | 3D Pose |
|------|---------|---------|
| 輸出 | (x, y, confidence) per keypoint | (x, y, z) 世界座標 |
| 代表方案 | DWPose / RTMPose / trt_pose / YOLOv8-pose | MediaPipe Pose (model_complexity=2)、MotionBERT、3D lifting |
| Jetson 可行性 | ✅ DWPose ~45 FPS `社群值，待 Jetson 實測` | ❌ MediaPipe 無 ARM64 wheel；lifting model 額外 +30ms |
| 跌倒偵測能力 | bbox 寬高比 + 關節角度 + 投票 buffer + D435 depth 輔助 | z 軸高度驟降，理論更精準但成本高 |
| 記憶體 | ~200MB (TensorRT) | +300-500MB (額外 lifting model) |

**結論**：純 2D 在 4 姿勢分類已足夠。D435 depth 補上「距離」和「高度驟降」就能做 pseudo-3D 覆蓋跌倒偵測，不需要真 3D pose estimation。

### 什麼情況才值得 3D？

- 需要精準的 3D 關節角度（例如復健動作評估）→ 本專案不需要
- 需要跨視角的姿態一致性（例如動作捕捉）→ 本專案單攝影機
- **我們的場景**：固定攝影機、正面/側面、4 種粗粒度姿勢 → 2D + depth 足矣

---

## D435 深度輔助

### 深度在姿勢辨識的 3 個用途

**1. 距離 gate（過濾背景）**

只處理 0.5-4m 內的人體，過濾背景行人或遠處物件。D435 在此範圍深度誤差 ≤ 2%。

**2. 跌倒驗證（multi-signal 之一，非單獨判定）**

hip keypoint 的 depth 值突然變化（人倒向地面），配合 bbox ratio > 1.0 + trunk angle > 60° 做 **多訊號交叉驗證**。

> **⚠️ 深度只是跌倒判定的輔助訊號之一，不可單獨作為最終判定依據。**

**3. Pseudo-3D 高度估計**

```
real_height ≈ pixel_height × depth / focal_length
```

算出真實身高比例變化，比純 pixel 更 robust（不受人走近走遠影響）。

### 資料流設計

```
DWPose 2D keypoints (x_pixel, y_pixel, confidence)
  + D435 aligned_depth (per-keypoint depth lookup, ROI median)
  = pseudo-3D (x_pixel, y_pixel, z_depth_meters)
  → 餵給 pose_classifier（角度法 + 高度比法 + depth 輔助）
```

### 不做的事

- 不做完整 point cloud 重建
- 不上傳 depth map 到雲端
- 不依賴單點 depth（用 ROI median 避免零值干擾）

---

## Jetson 推論成本分析

### 推理延遲

| 項目 | 數值 | 來源等級 | 出處 |
|------|------|:--------:|------|
| DWPose + YOLO TensorRT FP16 | ~22ms/frame (~45 FPS) | `社群值` | [johal.in 文章](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/) |
| DWPose FP16 精度損失 | -0.8% AP | `社群值` | 同上 |
| trt_pose ResNet (Jetson Nano) | 15-16 FPS | `社群值` | [NVIDIA trt_pose repo](https://github.com/NVIDIA-AI-IOT/trt_pose) |
| YOLOv8n-pose TensorRT (Orin Nano) | ~33 FPS (C++ pipeline) | `社群值` | [Hackster.io 實測](https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267) |
| TensorRT engine build（首次） | 5-15 min | `預估` | TRT 通用行為 |
| CUDA warmup（首幀延遲） | 5-10s | `預估` | TRT 通用行為 |
| 分類器（純 Python 規則） | <1ms | `預估` | 可忽略 |

> **所有 FPS 數據均未在本專案 Jetson Orin Nano + JetPack 6.x 上實測。Phase 2 首日必須驗證。**

### 記憶體

| 項目 | 數值 | 來源等級 |
|------|------|:--------:|
| DWPose TensorRT engine | ~200MB | `社群值` |
| DWPose + YOLO 完整 pipeline (RTX 4090) | 4.2GB VRAM | `社群值`，Jetson 統一記憶體會不同 |
| 分類器邏輯 | ~10MB | `預估` |

### 與其他模組共存（3/23 壓測驗證通過）

| 共存場景 | 風險 | 實測結果 |
|---------|------|---------|
| MediaPipe Pose + YuNet 人臉 | 極低 | ✅ 皆 CPU-only，GPU 0%，零衝突 |
| MediaPipe Pose + Gesture Recognizer | 極低 | ✅ 三感知同跑 60s，RAM 1.2GB, temp 52°C |
| MediaPipe Pose + Whisper ASR (CUDA) | 低 | Whisper 用 GPU，pose 用 CPU，互不干擾。L2 測試 Whisper+pose = -20% FPS（RTMPose 時代），MediaPipe CPU 不受影響 |
| MediaPipe Pose + edge-tts | 極低 | edge-tts 為雲端合成，不佔本地 GPU/CPU 推理資源 |

> **結論**：MediaPipe CPU-only pipeline 與所有現有模組共存零衝突，無需分時排程。

---

## 4/13 Demo 最小可展示版本

> **⚠️ 主線聲明：4/13 Demo 只要求 fallen 事件能觸發 + PosePanel 即時更新。其他三種姿勢（standing/sitting/crouching）屬加分項，不列為 Demo gate。** 不要因為 README 列了完整元件就自動擴 scope。

### Demo B 最小閉環

```
人站在 D435 前（0.5-4m）
  → MediaPipe Pose 推理（CPU, 18.5 FPS）→ 33 body keypoints
  → pose_classifier 規則分類（角度法 + 高度比法 + 20 幀投票 buffer）
  → /event/pose_detected 發布（姿勢變化時）
  → PawAI Studio PosePanel 即時更新
  → fallen 觸發語音警報（/tts "偵測到跌倒，請注意安全！"）
```

### 最小 Demo 元件清單

| 元件 | 4/13 必要？ | 狀態 | 負責 |
|------|:----------:|:----:|:----:|
| D435 RGB 串流 | ✅ | ✅ 已有 | — |
| MediaPipe Pose on Jetson | ✅ | ✅ 已完成（18.5 FPS） | Roy |
| pose_classifier（規則分類器） | ✅ | ✅ 已完成（6 類 first-match） | Roy |
| `/event/pose_detected` 發布 | ✅ | ✅ 已完成 | Phase 3 |
| PosePanel 前端 | ✅ | ❌ 待寫 | 鄔 |
| fallen → /tts 語音警報 | ✅ | ✅ event_action_bridge 已串接 | Phase 4 |
| D435 depth 輔助 | 加分 | 已有 depth 串流 | Phase 5 |

### 可砍的（如果時間不夠）

- `/state/perception/pose`（v2.1 非凍結，可延後到 4/13 之後）
- 精確 confidence 數值（先用 0.8 hard-code）
- `track_id` 關聯人臉（需 bbox IOU matching，可延後）
- depth 輔助跌倒驗證（純 2D 規則也能 demo）

### 最小 Demo 驗收標準

| 指標 | 目標 |
|------|------|
| 5 種姿勢辨識成功率 | ≥ 70%（Demo B gate） |
| 跌倒偵測響應時間 | < 2s（從跌倒到語音警報） |
| 連續運行穩定性 | 不 crash 跑完 Demo 流程（~5 分鐘） |

---

## 備取方案與切換條件（2026-03-17 調查）

### 方案總覽

| 優先序 | 方案 | Body kp | Hand kp | Jetson Orin Nano FPS | 來源等級 | TRT 成熟度 | 風險 |
|:------:|------|:-------:|:-------:|:--------------------:|:--------:|:----------:|------|
| **主方案** | DWPose (whole-body) | 17 + 6 foot | 21×2 | ~45 FPS | `社群值，待實測` | 需 ONNX→TRT 手動轉 | 轉換坑多，遮擋時手部 AP 降至 45% |
| **備案 1** | RTMPose (whole-body) | 17 | 21×2 | 預估 30+ FPS | `預估` | MMDeploy 官方路徑 | **已知 TRT 轉換精度下降**（見社群回饋） |
| **備案 2** | YOLOv8n-pose | 17 | ❌ 無 | ~33 FPS (C++ TRT) | `社群值` | Ultralytics 一鍵 export | 只有 body，手勢得另開模型 |
| **備案 3** | trt_pose | 17-18 | ❌ 無 | 15-16 FPS (Nano) | `社群值`，Orin `預估`更高 | NVIDIA 官方 TRT 原生 | 老專案少維護，只有 body |
| 不主推 | 3D lifting (MotionBERT 等) | 17+ | 看模型 | 額外 +30ms | `預估` | 不成熟 | Jetson 太重，只列不推 |

### 切換決策樹

```
Phase 2 首日：DWPose ONNX → TRT 轉換
  ├── 轉換成功 + FPS ≥ 20 + 精度可接受 → ✅ 繼續主方案
  └── 轉換失敗 / FPS < 15 / 精度崩
        ├── 還需要手勢+姿勢共用？
        │     ├── 是 → 備案 1：RTMPose whole-body (MMDeploy)
        │     │     └── RTMPose TRT 也崩？
        │     │           → 暫退 ONNX Runtime（⚠️ 僅作驗證用 fallback，
        │     │             FPS 預估 10-15，不是 demo-ready 主路徑，
        │     │             需儘速解決 TRT 轉換問題或切備案 2）
        │     └── 否（時間不夠，放棄手勢共用）
        │           → 備案 2：YOLOv8n-pose（只做姿勢）
        └── YOLOv8n-pose 也不行？
              → 備案 3：trt_pose（最保守，NVIDIA 原生 TRT）
```

### 判斷時間點

| 時間 | 決策 |
|------|------|
| Phase 2 第 1 天 | DWPose TRT 轉換 + FPS 測試。**不過就立即切備案** |
| Phase 2 第 3 天 | 備案 1/2 驗證完成。選定最終方案 |
| Phase 3 開始 | 方案鎖死，不再切換 |

---

## 社群實戰回饋（2026-03-17 調查）

> 以下坑點來自 GitHub Issues、NVIDIA Forum、學術論文與社群部落格，非本專案實測。
> 目的是提前預警，讓 Phase 2 部署時少踩坑。

### 坑 1：TensorRT 轉換精度下降

| 問題 | 具體現象 | 來源 |
|------|---------|------|
| RTMPose ONNX→TRT 後 keypoints 錯位 | 部分 keypoints 固定卡在 bbox 左上角，其餘正常 | [mmpose#2579](https://github.com/open-mmlab/mmpose/issues/2579) |
| FP16 精度暴跌 | Transformer-like 模型 mAP 從 43.8 → 23.4 | [TensorRT#2922](https://github.com/NVIDIA/TensorRT/issues/2922) |
| INT8 不校準直接崩 | 不做 calibration dataset → 結果不可用 | [TensorRT#3352](https://github.com/NVIDIA/TensorRT/issues/3352) |
| DWPose FP16 | -0.8% AP（可接受） | [johal.in](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/) |

**對策**：
1. 先用 FP16 測試，對比 ONNX Runtime 結果
2. 若精度崩 → 回退 FP32（犧牲速度）
3. INT8 必須做 calibration dataset（用 COCO val subset）
4. **轉換後立即跑 AP 對比，不要等到整合才發現**

### 坑 2：D435 深度對齊與空洞

| 問題 | 具體現象 | 來源 |
|------|---------|------|
| 深度空洞 | ~30% pixel 回傳 0mm，尤其在物件邊緣和低紋理表面 | [realsense#2723](https://github.com/IntelRealSense/librealsense/issues/2723) |
| 邊緣深度畸變 | >35cm 距離，物件邊緣深度呈波浪狀 | [realsense#10133](https://github.com/IntelRealSense/librealsense/issues/10133) |
| RGB-Depth 對齊延遲 | aligned_depth 有 ~1 frame 延遲 | [realsense#8726](https://github.com/IntelRealSense/librealsense/issues/8726) |

**對策**：
1. 開啟 IR emitter（`emitter_enabled=1`）補紋理
2. 啟用 spatial + temporal + hole-filling 後處理 filter
3. keypoint 深度取 **ROI 5×5 median**，不取單點值（避免零值）
4. depth unit 改 0.0001 可填補更多細節
5. 對齊延遲 ~33ms（1 frame @30FPS），對姿勢分類影響可接受

### 坑 3：跌倒偵測誤判

| 誤判場景 | 為什麼誤判 | 對策 |
|---------|-----------|------|
| 老人**緩慢坐下** | bbox ratio 漸變至接近 1.0 + trunk angle 緩升 | 時序分析：跌倒 <1s 驟降，坐下 >2s 漸變 |
| **彎腰撿東西** | 短暫 trunk angle >60° | 20 幀投票 buffer ~0.67s @30FPS 可過濾 |
| **躺在沙發/床上** | 水平姿態 = fallen 特徵 | D435 深度：沙發/床高度 ≠ 地板高度（0.4-0.6m vs 0m） |
| **睡在地板** | 靜態水平 = fallen | 需 Executive 層判斷：持續 >30s fallen + 無回應 → 才升級為真警報 |
| **相機角度偏斜** | 2D 座標失真，斜視角下站立也可能被誤判為坐下 | 固定安裝角度 15-30° 俯角，避免極端側視 |

> **⚠️ 核心原則：任何單一訊號都不作最終跌倒判定。** 必須 bbox ratio + trunk angle + 時序分析 + depth 輔助（如有）多訊號投票才發布 high-confidence fallen event。`fallen` 的 low-confidence 預警可以快發，但語音警報等最終動作必須等多訊號確認。

**來源**：[ACM P²Est](https://dl.acm.org/doi/10.1145/3478027)、[TDS Fall Detection](https://towardsdatascience.com/fall-detection-using-pose-estimation-a8f7fd77081d/)、[arxiv 2503.19501](https://arxiv.org/html/2503.19501v1)、[arxiv 2503.01436](https://arxiv.org/pdf/2503.01436)

### 坑 4：GPU 多任務共存

| 問題 | 具體現象 | 來源 |
|------|---------|------|
| 兩個 TRT 模型並行 | ~5% 性能降級（各佔 ~40% GPU） | [NVIDIA Forum](https://forums.developer.nvidia.com/t/jetson-orin-nano-running-two-tensorrt-parallel-models-real-time/351674) |
| 同 pipeline 合併 OOM | 不要在同一 process 載入兩個大模型 | 同上 |
| 多線程推理 hang | Orin 8GB 上 2+ YOLO 模型 threading → 死鎖 | [ultralytics#14891](https://github.com/ultralytics/ultralytics/issues/14891) |
| 同 frame 不可真並行 | detection → pose 有資料依賴 | [NVIDIA 建議](https://forums.developer.nvidia.com/t/jetson-orin-nano-running-two-tensorrt-parallel-models-real-time/351674)：不同 frame pipeline 化 |

**對策**：
1. DWPose 和 Whisper **分時排程**，不同時 warmup
2. 避免同 process 多模型 threading → 用分 process + 分 CUDA stream
3. 用 `tegrastats` 持續監控 GPU util 和 memory
4. NVIDIA 建議 pipeline 化：frame N 做 detection 時，frame N-1 做 pose

> **⚠️ 專案直接結論：在本專案中，姿勢推理 node 應避開 Whisper warmup 同時啟動。啟動序列：D435 → YuNet → ASR warmup done → DWPose 全速。若偵測到 GPU util > 90% 持續 5s，應降低 pose 推理頻率（skip frame）而非 crash。**

### 坑 5：DWPose 特有問題

| 問題 | 具體現象 | 來源 |
|------|---------|------|
| 遮擋 >50% 時手部 AP 降至 45% | 半身入鏡或多人重疊 | [DWPose Wholebody](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/) |
| bbox 截斷腳/手 | 22% case 截斷肢體末端 | 同上 |
| TRT engine 首幀延遲 | warmup 5-10s | TRT 通用行為 |

**對策**：
1. bbox 加 **1.2x height padding**，防截斷
2. 半身入鏡時：只用可見 keypoints 分類（上半身角度仍可判斷 sitting/standing）
3. 多人場景：配合人臉 track_id 做 bbox 關聯，避免混淆
4. 首幀延遲：啟動時跑一張 dummy image warmup

---

## 參考資源

### 首選方案
- [DWPose / RTMPose (MMPose)](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)
- [DWPose Wholebody on Jetson](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)
- [DWPose TensorRT 實作](https://github.com/yuvraj108c/Dwpose-Tensorrt)
- [rtmlib (輕量 RTMPose 推理庫)](https://pypi.org/project/rtmlib/)

### 備案方案
- [trt_pose (NVIDIA)](https://github.com/NVIDIA-AI-IOT/trt_pose)
- [YOLOv8 Pose - Ultralytics](https://docs.ultralytics.com/tasks/pose/)
- [YOLO on Jetson Quick Start](https://docs.ultralytics.com/guides/nvidia-jetson/)
- [YOLOv8 vs v26 on Jetson Orin Nano](https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267)

### 部署與轉換
- [MMPose 部署指南](https://mmpose.readthedocs.io/en/latest/user_guides/how_to_deploy.html)
- [MMDeploy Pose 支援](https://mmdeploy.readthedocs.io/en/stable/04-supported-codebases/mmpose.html)
- [RTMPose TRT 精度下降 Issue](https://github.com/open-mmlab/mmpose/issues/2579)
- [TensorRT FP16 精度問題](https://github.com/NVIDIA/TensorRT/issues/2922)

### D435 深度相關
- [D435 深度精度討論](https://github.com/IntelRealSense/librealsense/issues/2723)
- [D435 邊緣深度問題](https://github.com/IntelRealSense/librealsense/issues/10133)
- [D435 深度後處理指南](https://dev.intelrealsense.com/docs/depth-post-processing)
- [D435 效能調校](https://dev.intelrealsense.com/docs/tuning-depth-cameras-for-best-performance)

### GPU 多任務共存
- [Jetson Orin Nano 雙模型並行](https://forums.developer.nvidia.com/t/jetson-orin-nano-running-two-tensorrt-parallel-models-real-time/351674)
- [Concurrent Vision Inference Profiling](https://arxiv.org/html/2508.08430v1)
- [Ultralytics 多線程 hang Issue](https://github.com/ultralytics/ultralytics/issues/14891)

### 姿勢分類與跌倒偵測研究
- [Posture Detection System - LearnOpenCV](https://learnopencv.com/building-a-body-posture-analysis-system-using-mediapipe/)
- [Pose-Based Fall Detection - arxiv 2503.19501](https://arxiv.org/html/2503.19501v1)
- [Fall Detection from Videos - arxiv 2503.01436](https://arxiv.org/pdf/2503.01436)
- [Sitting Posture Detection (2025)](https://dl.acm.org/doi/10.1145/3776865.3776880)
- [Fall Detection using Pose Estimation - TDS](https://towardsdatascience.com/fall-detection-using-pose-estimation-a8f7fd77081d/)
- [Pervasive Pose Estimation for Fall Detection - ACM](https://dl.acm.org/doi/10.1145/3478027)
- [Camera Angle Fall Detection - ResearchGate](https://www.researchgate.net/publication/338317151_Fall_Detection_Depth-Based_Using_Tilt_Angle_and_Shape_Deformation)

### MediaPipe（僅限 x86 開發機 demo）
- [MediaPipe Pose](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md)
- [MediaPipe Jetson 安裝問題](https://forums.developer.nvidia.com/t/does-jetson-orin-nano-support-mediapipe/290797)

---

## Clean Architecture 重構藍圖（4/13 後）

> 參考：`docs/research/2026-03-25-go2-sdk-capability-and-architecture.md` §5.4 Phase 4a

**現狀**：與手勢辨識共用 vision_perception_node.py，pose 部分在 _tick() 內。已有 pose_classifier + mediapipe_pose 抽取。
**預估工時**：2-3 天（與手勢辨識共同重構）

### 目標結構（姿勢部分）

```
vision_perception/
├── domain/
│   ├── pose.py                 # Pose enum, PoseResult dataclass
│   ├── pose_classifier.py      # classify_pose（已有）
│   ├── event_builder.py        # build_pose_event（已有）
│   └── i_pose_backend.py       # IPoseBackend (ABC)
├── application/
│   └── pose_service.py         # 推理→分類→事件建構
├── infrastructure/
│   ├── mediapipe_pose.py       # MediaPipe Pose 封裝（已有）
│   └── rtmpose_pose.py         # RTMPose 封裝（備援）
└── presentation/
    └── (共用 vision_perception_node.py)
```

### 已完成的抽取（Phase 1）

- `pose_classifier.py` — 純函式，11 unit tests（含 bending）
- `event_builder.py` — build_pose_event，4 unit tests
- `mediapipe_pose.py` — MediaPipe Pose 封裝
- `mediapipe_pose_mapping.py` — MP→COCO keypoint 映射，6 unit tests

### 剩餘工作

1. 定義 `domain/i_pose_backend.py`（ABC）
2. 將 mediapipe_pose 改為實作 IPoseBackend
3. 拆 `_tick()` 中的 pose 部分到 `application/pose_service.py`
4. node 只保留 ROS2 接線
5. interaction_router + event_action_bridge 已獨立，不受影響
