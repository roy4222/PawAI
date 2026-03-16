# 手勢辨識系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 用手勢指揮機器狗
- **靜態手勢**：停止 (手掌張開)、跟我來 (招手)、OK (OK 手勢)
- **動態手勢**：指向方向 (指向某方向)
- **4/13 Demo 目標**：wave / stop / point / ok 四種手勢，成功率 ≥ 70%

---

## 技術選型結論（2026-03-16 更新）

### 推薦方案：分層策略

| 優先序 | 方案 | 理由 |
|:------:|------|------|
| **首選** | **DWPose + TensorRT**（RTMPose 為備援） | 社群回報 Orin Nano ~45 FPS（待本機驗證）、原生 TensorRT、含 21×2 手部 keypoints |
| 次選 | trt_pose_hand (NVIDIA) | 官方 ROS2 wrapper、6 類手勢內建、Jetson Nano 上 ~40 FPS |
| **不推薦** | ~~MediaPipe Hands~~ | Jetson ARM64 無官方 pip wheel、GPU delegate 不可用、CPU-only <5-25 FPS |

### DWPose vs RTMPose 差異

- **DWPose**：RTMPose 的蒸餾版，whole-body 133 keypoints，是本專案的目標方案
- **RTMPose**：MMPose 原版，提供 body-only (17) / hand-only (21) / whole-body 等多種 config，ONNX/TensorRT 匯出路徑較成熟，是**備援路線**——如果 DWPose TensorRT 匯出有問題，可退回 RTMPose whole-body config

兩者**不是完全等價替換**：DWPose 蒸餾後精度略優（尤其手部），但 RTMPose 的社群資源和匯出文件更豐富。

### ⚠️ MediaPipe 在 Jetson 上的已知問題

> **重要**：這是 2026-03-16 深入調查後的結論，推翻了先前的初步評估。

1. **無法 `pip install`**：PyPI 無 Linux ARM64 wheel，必須從 source build（需 Bazel，耗時 1-2 小時）
2. **GPU 加速不可用**：即使 build 成功，TFLite GPU delegate 在 Jetson 上無法正確初始化
3. **CPU-only 效能差**：有使用者回報 Jetson Orin Nano 上 <5 FPS（TFLite CPU delegate）
4. **社群 wheel 過舊**：PINTO0309/mediapipe-bin 停在 v0.8.5，不支援新版 Task API
5. **JetPack 6.x 建構困難**：CUDA 12.6 + 新 linker 導致編譯失敗

**結論**：MediaPipe 適合開發機 demo（x86 筆電/桌機），但**不適合 Jetson 部署**。

---

## 方案比較（Jetson Orin Nano 8GB）

| 方案 | Keypoints | FPS (Orin Nano) | 記憶體 | 安裝難度 | 手勢分類 |
|------|-----------|:---------------:|:------:|:--------:|:--------:|
| **DWPose** (RTMPose 蒸餾) | 133 (17 body + 6 foot + 68 face + 21 hand×2) | ~45 FPS † | ~200MB | TensorRT export | 需自建 |
| **RTMPose** (MMPose) | 21 hand / 17 body 可選 | 預估 30+ FPS | ~150MB | ONNX/TensorRT | 需自建 |
| **trt_pose_hand** | 21 hand | ~40 FPS (Nano) | ~150MB | TensorRT | **6 類內建** |
| MediaPipe Hands | 21 hand | <5-25 FPS (CPU) | ~200-350MB | ❌ 無 ARM64 wheel | 需自建 |
| MoveNet Lightning | 17 body only | 無 hand keypoints | — | TFLite | N/A |

> † DWPose 45 FPS 數據來自[社群實作文章](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)，非官方 benchmark。需以本專案 Jetson Orin Nano + JetPack 6.x 實測確認。

### 推薦落地順序

1. **Phase 1**：楊先在 x86 筆電用 MediaPipe 做概念驗證 demo（驗證 UX 流程與事件格式）
2. **Phase 2**：Roy 在 Jetson 部署 DWPose/RTMPose + TensorRT，重新校正分類閾值
3. **Phase 3**：整合進 ROS2 `gesture_perception_node`

> **⚠️ 移植風險提醒**：MediaPipe Hands（21 keypoints）與 DWPose hand（21×2 keypoints, COCO-WholeBody）的 keypoint 定義、索引順序、座標系統不同。Phase 1 的 x86 demo **只驗證 UX 互動流程與 ROS2 事件格式**，不驗證最終分類閾值。Phase 2 部署 DWPose 時，角度閾值、距離比、手勢規則都需要對照 COCO-WholeBody keypoint 定義重新校正。

---

## 邊緣端 (Jetson 8GB) - 即時反應

### 手部關鍵點偵測

#### DWPose（首選）

- RTMPose 的蒸餾版本，MMPose 生態系
- 133 個 keypoints（[COCO-WholeBody](https://github.com/jin-s13/COCO-WholeBody) 標準）：17 body + 6 foot + 68 face + 21 hand×2
- 社群文獻回報 Jetson Orin Nano 上 ~45 FPS（TensorRT FP16），**需以本專案 Jetson 實測確認**
- 同時取得手部 + 身體 landmarks，一個模型兩種用途

#### trt_pose_hand（次選）

- NVIDIA-AI-IOT 官方維護
- 21 keypoints + 6 類手勢 (fist/pan/stop/fine/peace/no hand)
- TensorRT 原生，有 ROS2 wrapper（`ros2_trt_pose_hand`）
- 直接命中「邊緣即時反應」需求

### 靜態手勢分類

**常見做法**：Landmarks → 小型分類器

- Landmarks 角度/距離特徵 + MLP/線性 SVM
- 延遲低、可控、易加入自訂手勢
- 4 種手勢用**規則分類器**就足夠，不需要訓練模型

| 手勢 | 分類邏輯 | 關鍵 Landmarks |
|------|---------|---------------|
| wave 👋 | 手掌張開 + 五指伸展 + 手腕高於肩膀 | 所有指尖 + 手腕 |
| stop ✋ | 手掌朝前 + 五指伸展 + 手腕在胸前 | 所有指尖 + 手腕 + 肩膀 |
| point 👉 | 食指伸展 + 其他手指握拳 | 食指指尖/根部 + 其他指尖 |
| ok 👌 | 拇指與食指形成圓環 + 其他三指伸展 | 拇指尖 + 食指尖距離 |

### 動態手勢 (揮手辨別)

**方法**：追蹤 landmarks 時間序列

| 方法 | 特點 |
|------|------|
| **規則** | 軌跡方向/速度/來回偵測（10-20 幀 buffer） |
| **DTW/HMM** | 時間序列匹配 |
| **輕量 RNN/TCN** | 深度學習分類（overkill for 4 gestures） |

**限制**：
- 遮擋造成 landmarks 抖動
- 快速運動失真
- 相機視角改變

---

## 雲端端 (5×RTX 8000) - 精細理解

### 3D 手部姿態/網格重建

| 方案 | 功能 | 備註 |
|------|------|------|
| **FrankMocap** | 單目影像 → 身體/手/臉 3D pose | 開源 |
| **InterHand2.6M** | 雙手互動 3D dataset + baseline | 研究用 |
| **HaMeR** | Transformer 做 3D hand mesh recovery | 較新 |

### 是否需要上雲端？

| 需求 | 建議 |
|------|------|
| 基本指令 (停止/跟隨/指向/OK) | **邊緣端即可**，<100ms |
| 連續手語/複雜多模態 | 上雲端用更強模型 |

**分工策略**：
- 邊緣：手部偵測 → 低延遲指令
- 雲端：精細姿態/語義確認 (補充判斷)

---

## RGB-D 深度應用

### 深度在手勢辨識的優勢

1. **3D 幾何問題**：減少單目 scale/遮擋/背景歧義
2. **安全規則**：「手在 0.5-2m 才生效」
3. **指向估計**：3D pointing ray

### 資料分工建議

```
Jetson 端：
  ↓ D435 aligned_depth
  ↓ 取 ROI 深度統計
  ↓ 計算 3D 座標
  ↓ 只傳 3D 座標 (不上完整 depth)
```

若需上雲：`compressed_depth_image_transport` (PNG 壓縮)

---

## 機器人整合

### <100ms 延遲達成

1. 手勢辨識**必須在邊緣端完成**
2. 雲端只做「可選再確認」或「高階語義」
3. 使用 DWPose/RTMPose (TensorRT) 或 trt_pose_hand

### ROS2 控制串接

```
gesture_perception_node → /event/gesture_detected (std_msgs/String JSON)
  ↓
Interaction Executive
  ↓
呼叫 Sport Service (StopMove/跟隨模式等)
```

**Event Schema**（對齊 `interaction_contract.md` v2.0）：
```json
{
  "stamp":       1710000000.123,
  "event_type":  "gesture_detected",
  "gesture":     "wave",
  "confidence":  0.87,
  "hand":        "right"
}
```

---

## 手勢定義與 Skill 對應

| 手勢 | 類型 | 對應 Skill | 優先序 |
|------|------|------------|:------:|
| wave 👋 | 靜態+動態 | `follow_person()` | P1 |
| stop ✋ | 靜態 | `stop()` | P1 |
| point 👉 | 靜態 | `navigate_to(direction)` | P1 |
| ok 👌 | 靜態 | `confirm()` | P1 |

### 多模態衝突處理

**問題**：語音說「停止」但手勢是「跟隨」

**常見策略**：
- 優先級設定 (語音 > 手勢 或反之)
- 置信度比較
- 最後指令優先

---

## 記憶體預算（與現有模組共存）

| 模組 | 記憶體占用 | 狀態 |
|------|:--------:|:----:|
| Ubuntu + ROS2 | ~2.0 GB | 常駐 |
| D435 影像串流 | ~0.8 GB | 常駐 |
| YuNet 人臉偵測 | ~0.1 GB | 常駐 |
| Sherpa-onnx KWS | ~0.05 GB | 常駐 |
| faster-whisper (觸發式) | 0.4-1.0 GB | 觸發 |
| Piper TTS (觸發式) | 0.3-0.8 GB | 觸發 |
| **DWPose 手勢+姿勢** | **~0.2 GB** | **常駐** |
| 安全餘量 | ≥ 0.8 GB | 必須 |
| **合計（全開）** | **~4.7-5.9 GB** | ✅ |

剩餘空間：8GB - 5.9GB = **~2.1GB**，充足。

---

## 參考資源

### 首選方案
- [DWPose / RTMPose (MMPose)](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)
- [DWPose Wholebody on Jetson](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)

### 次選方案
- [trt_pose_hand (NVIDIA)](https://github.com/NVIDIA-AI-IOT/trt_pose_hand)
- [ros2_trt_pose_hand (ROS2 wrapper)](https://github.com/NVIDIA-AI-IOT/ros2_trt_pose_hand)

### MediaPipe（僅限 x86 開發機 demo）
- [MediaPipe Hands](https://mediapipe-studio.webapps.google.com/studio/demo/hands)
- [MediaPipe Jetson 安裝問題](https://forums.developer.nvidia.com/t/does-jetson-orin-nano-support-mediapipe/290797)
- [MediaPipe ARM64 無 wheel (Issue #5965)](https://github.com/google-ai-edge/mediapipe/issues/5965)

### 雲端精細理解
- [FrankMocap](https://github.com/facebookresearch/frankmocap)
- [InterHand2.6M](https://github.com/facebookresearch/InterHand2.6M)
- [HaMeR](https://github.com/geopavlakos/hamer)
