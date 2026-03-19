# 姿勢辨識系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 辨識人體姿勢，觸發對應行為
- **4 種基本姿勢**：站立 (standing)、坐下 (sitting)、蹲下 (crouching)、跌倒 (fallen)
- **4/13 Demo 目標**：4 種姿勢辨識成功率 ≥ 70%（Demo B）
- **跌倒偵測為安全功能**：辨識到 fallen → 觸發語音警報 + PawAI Studio 強制展開 PosePanel

---

## 技術選型結論（2026-03-16）

### 推薦方案：與手勢辨識共用 wholebody 推理

| 優先序 | 方案 | 理由 |
|:------:|------|------|
| **主路徑** | **rtmlib + RTMPose wholebody** | `pip install rtmlib` 即可用、支援 onnxruntime-gpu / TensorRT EP、一個模型同時產出 body + hand keypoints（手勢+姿勢共用） |
| 升級選項 | DWPose wholebody (TensorRT) | RTMPose 蒸餾版，手部精度略優；但 Jetson 上零成功記錄，待 RTMPose 路徑穩定後再評估是否值得切換 |
| 備援 | body-only + hand-only 雙模型 | 若 wholebody 在 Jetson 上無法穩定達到展示需求（FPS、手部檢出率或記憶體餘量不足），降級為分開推理 |
| 次選 | trt_pose (NVIDIA) | TensorRT 原生、Jetson Nano 上 社群值：ResNet 15-16 FPS / DenseNet 9-10 FPS |
| **不推薦** | ~~MediaPipe Pose~~ | Jetson ARM64 無官方 pip wheel、社群值：CPU-only ~7-20 FPS |
| 不推薦 | MoveNet | 只有 17 keypoints、無手部、Jetson GPU delegate 有問題 |

### DWPose vs RTMPose 差異

> 詳見 [`../手勢辨識/README.md`](../手勢辨識/README.md) § DWPose vs RTMPose 差異

- **RTMPose**：MMPose 原版，提供 body-only / hand-only / wholebody 等多種 config，ONNX/TensorRT 匯出路徑較成熟。**本專案主路徑（經由 rtmlib 部署）**
- **DWPose**：RTMPose 的蒸餾版，wholebody 133 keypoints，精度略優（尤其手部）。**升級選項 — 待 RTMPose 路徑穩定後再評估**

### 為什麼跟手勢辨識共用 DWPose？

DWPose 一次推理輸出 133 個 keypoints（[COCO-WholeBody](https://github.com/jin-s13/COCO-WholeBody) 標準）：
- **17 body keypoints** → 餵給姿勢分類器（standing/sitting/crouching/fallen）
- **6 foot keypoints**（左右腳各 3）→ 輔助姿勢判斷（腳尖/腳跟方向）
- **21 hand keypoints ×2** → 餵給手勢分類器（wave/stop/point/fist）— 實作用 fist，v2.0 契約仍用 ok，待 3/25 benchmark 後正式切換（過渡期用 `GESTURE_COMPAT_MAP`）
- **68 face keypoints** → 備用（表情辨識等）

**只跑一個模型，分兩個分類器**，比分開跑 Hands + Pose 更省資源。

### 落地策略：先分開做，共用推理

```
D435 camera frame
  ↓
DWPose 推理（TensorRT, 社群值：~22ms/frame）
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
3. **CPU-only 效能差**：社群值：Jetson Nano 上 ~7 FPS（CPU），預估：Orin Nano 10-25 FPS
4. **model_complexity=2 太重**：~80-100ms/frame，不適合即時

**結論**：MediaPipe Pose 適合楊在 x86 筆電上做概念驗證（UX 流程與事件格式），**不適合 Jetson 部署**。

> **⚠️ 移植風險提醒**：MediaPipe Pose（33 keypoints, 含 3D 座標）與 DWPose body（17 keypoints, COCO format, 2D only）的 keypoint 集合、索引、座標系統完全不同。Phase 1 的 x86 demo **只驗證 UX 互動流程與 ROS2 事件格式**，不驗證最終分類閾值。Phase 2 部署 DWPose 時，角度閾值、高度比、投票 buffer 參數都需要對照 COCO 17-point 定義重新校正。

---

## 方案比較（Jetson Orin Nano 8GB）

| 方案 | Body Keypoints | FPS (Orin Nano) | 記憶體 | 3D 座標 |
|------|:--------------:|:---------------:|:------:|:-------:|
| **DWPose** (RTMPose) | 17 body + 6 foot + hand/face | 社群值：~45 FPS † | ~200MB | ❌ 2D |
| **trt_pose** | 17-18 | 社群值：15-16 FPS (Nano) | ~150MB | ❌ 2D |
| MediaPipe Pose | 33 | 社群值：7-25 FPS (CPU) | ~150-300MB | ✅ 有 |
| MoveNet Lightning | 17 | 無 Jetson 數據 | — | ❌ 2D |

> † DWPose 45 FPS 數據來自[社群實作文章](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)，非官方 benchmark。

### 本專案實測（2026-03-18, Jetson Orin Nano + JetPack 6.x）

| 項目 | 數值 |
|------|------|
| 方案 | rtmlib 0.0.15 + onnxruntime-gpu 1.23.0（Jetson AI Lab wheel） |
| 模型 | RTMPose wholebody balanced（YOLOX-m + rtmw-dw-x-l） |
| 輸入 | D435 640x480@30Hz RGB |
| **推理 FPS** | **~7.5 FPS**（隨機噪聲）/ **~3.8 Hz debug_image**（真實 D435 + face 同跑） |
| GPU 使用率 | 91-99%（幾乎滿載） |
| 溫度 | GPU 66°C（安全，上限 ~95°C） |
| RAM | 5.0/7.6 GB（餘 2.4GB） |
| pose_detected | ✅ 真人可觸發（sitting, crouching 正確反應） |

**結論**：balanced mode 可用但延遲偏高。若需提升 FPS，可嘗試 `lightweight` mode（未測）。

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

### 共用推理，分類器獨立

```
D435 RGB frame (30 FPS)
  ↓
[RTMPose wholebody 推理 (rtmlib)] ← 一次推理，133 keypoints
  ↓
  ├── body (17) + foot (6) → pose_classifier → /event/pose_detected
  │                                           → /state/perception/pose (v2.1 內部)
  └── hand (21×2) → gesture_classifier → /event/gesture_detected
```

**主路徑**：rtmlib + RTMPose wholebody，單模型同時產出 body + hand keypoints。
**升級選項**：DWPose wholebody（精度略優），待主路徑穩定後評估。
**備援**：若 wholebody 在 Jetson 上無法穩定達到展示需求（FPS、手部檢出率或記憶體餘量不足），降級為 hand-only + body-only 雙模型。

**好處**：
- 一個模型、一次推理、兩個分類器
- 分類器獨立，好 debug（哪邊錯一眼看出來）
- 記憶體只佔 ~200MB（不是 400MB）

### 可能的 Node 架構

**方案 A：單一 Node（推薦）**
```
vision_perception_node          ← 統一命名
  ├── RTMPose wholebody 推理 (rtmlib)
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

## 落地順序（2026-03-18 更新）

| Phase | 時間 | 內容 | 狀態 |
|:-----:|------|------|:----:|
| 1 | 3/16-3/18 | `vision_perception_node` mock mode + 23 unit tests + Jetson smoke test | ✅ 完成 |
| 2 | 3/18 | RTMPose wholebody balanced on Jetson（rtmlib + onnxruntime-gpu），~3.8-7.5 FPS | ✅ 完成 |
| 2b | 3/25 決策點 | FPS 低於 15 紅線，評估 lightweight mode 或接受現狀 | 待定 |
| 3 | 4/1-4/6 | 姿勢分類閾值校正 + 跌倒偵測穩定性測試 | 待做 |
| 4 | 4/6-4/13 | 端到端測試 + Demo B 微調 | 待做 |

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

### 與其他模組共存風險

| 共存場景 | 風險 | 對策 |
|---------|------|------|
| DWPose + Whisper ASR | ASR warmup ~12s 佔 GPU，pose FPS 會掉 | 分時排程：ASR warmup 完才開 pose 全速 |
| DWPose + YuNet 人臉 | YuNet 很輕（~100MB），低風險 | 可共存 |
| DWPose + Piper TTS | TTS 觸發式，短暫佔用 | 低風險，但播放期間 pose 可能掉 1-2 FPS |

**實測計畫**：Phase 2 部署 DWPose 時，用 `tegrastats` 記錄 GPU util / memory，確認與 Whisper 共存不超預算。

> **⚠️ 專案直接結論：在本專案中，姿勢推理 node 應在 Whisper warmup 完成後（`warmup_done: true`）才啟動全速推理。啟動序列建議：D435 → YuNet → ASR warmup → DWPose 全速。**

---

## 4/13 Demo 最小可展示版本

> **⚠️ 主線聲明：4/13 Demo 只要求 fallen 事件能觸發 + PosePanel 即時更新。其他三種姿勢（standing/sitting/crouching）屬加分項，不列為 Demo gate。** 不要因為 README 列了完整元件就自動擴 scope。

### Demo B 最小閉環

```
人站在 D435 前（0.5-4m）
  → DWPose 推理 → 17 body keypoints
  → pose_classifier 規則分類（角度法 + 高度比法 + 投票 buffer）
  → /event/pose_detected 發布（姿勢變化時）
  → PawAI Studio PosePanel 即時更新
  → fallen 觸發語音警報（/tts "偵測到跌倒，請注意安全！"）
```

### 最小 Demo 元件清單

| 元件 | 4/13 必要？ | 狀態 | 負責 |
|------|:----------:|:----:|:----:|
| D435 RGB 串流 | ✅ | 已有 | — |
| DWPose TensorRT on Jetson | ✅ | ❌ 待部署 | Roy (Phase 2) |
| pose_classifier（規則分類器） | ✅ | ❌ 待寫 | Roy/楊 (Phase 2-3) |
| `/event/pose_detected` 發布 | ✅ | schema 已定義 | Phase 3 |
| PosePanel 前端 | ✅ | ❌ 待寫 | 鄔 |
| fallen → /tts 語音警報 | ✅ | 需 Executive 串接 | Phase 4 |
| D435 depth 輔助 | 加分 | 已有 depth 串流 | Phase 3 |

### 可砍的（如果時間不夠）

- `/state/perception/pose`（v2.1 非凍結，可延後到 4/13 之後）
- 精確 confidence 數值（先用 0.8 hard-code）
- `track_id` 關聯人臉（需 bbox IOU matching，可延後）
- depth 輔助跌倒驗證（純 2D 規則也能 demo）

### 最小 Demo 驗收標準

| 指標 | 目標 |
|------|------|
| 4 種姿勢辨識成功率 | ≥ 70%（Demo B gate） |
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
