# 手勢辨識模型選型調查

> 最後更新：2026-03-21

## 目標效果
- 辨識 wave / stop / point / fist 四種手勢
- 4/13 Demo 目標：成功率 ≥ 70%，辨識延遲 ≤ 2s
- 與 face（CPU）+ pose（共用推理）+ STT（CUDA on-demand）共存

## 候選模型

| # | 模型 | 框架 | 輸出 | Installability | Runtime viability | GPU 路徑 | 實測性能 | 納入原因 | 預期淘汰條件 |
|---|------|------|------|:-:|:-:|:-:|---|---|---|
| 1 | **RTMPose hand** (wholebody) | rtmlib + onnxruntime-gpu | 21kp×2 hands (from 133kp) | verified | verified | cuda | **9.3 FPS**（共用 pose 推理） | 與 pose 共用一次推理，零額外成本 | — |
| 2 | **MediaPipe Hands** | mediapipe 0.10.18 | 21kp×2 hands | verified | verified | cpu_only | **16.8 FPS** | CPU-only 最快，手部專用 | 精度不足 or CPU 競爭 |

### 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|
| MediaPipe Hands (舊版) | 先前記為「ARM64 無 wheel」→ 0.10.18 已修正 | local_failed → 已修正 |
| PINTO0309 hand-onnx | 待測 P2 | — |
| YOLO11n-pose-hands | 待測 P2 | — |
| trt_pose_hand | 老專案停更，JetPack 6 相容性未知 | community_only |

## 架構選擇分析

| 方案 | Pose FPS | Gesture FPS | GPU | CPU | 推理次數 |
|------|:--------:|:-----------:|:---:|:---:|:--------:|
| **A: RTMPose wholebody lw** | 17.6 | 17.6（共用） | ~90% | 低 | **1 次兩用** |
| B: MediaPipe 分開跑 | 13.5 | 16.8 | 0% | **高** | 2 次 |
| C: RTMPose body + MP hands | ~17.6? | 16.8 | ~50%? | 中 | 2 次（待測） |

**方案 A 最務實**：一次推理同時出 pose + gesture，17.6 FPS。

## Benchmark 結果（3/21 Jetson 實測）

### L1 單模型基線
| 模型 | FPS | Latency | GPU | Gate |
|------|:---:|:-------:|:---:|:----:|
| **mediapipe_hands** | **16.8** | 60ms | CPU 0% | PASS |
| rtmpose_hand (wholebody) | 9.3 | 107ms | CUDA ~95% | PASS |

MediaPipe Hands 比 RTMPose wholebody 快 1.8 倍。

**3/21 Foxglove 實測結論**：RTMPose wholebody 的手部 keypoints 在正常距離下不可靠（座標散在臉部區域，非手部），gesture classifier 收到的是噪點。MediaPipe Hands 的手部 keypoints 準確落在手上，已改為主線。

## 最終架構：同節點雙引擎（3/21 實作）

```
D435 camera frame
  ↓
vision_perception_node
  ├── RTMPose lightweight (CUDA) → body keypoints → pose_classifier → /event/pose_detected
  └── MediaPipe Hands (CPU)     → hand keypoints → gesture_classifier → /event/gesture_detected
```

Launch：`gesture_backend:=mediapipe`（預設仍為 rtmpose，需手動切換）

## 決策（3/21 更新）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| **MediaPipe Hands** | **JETSON_LOCAL** | jetson（**主線**） | 手部 keypoints 準確、16.8 FPS CPU-only、Foxglove 實測通過 |
| RTMPose hand (wholebody) | **REJECTED** | — | 手部 keypoints 在正常距離不可靠（座標偏移到臉部），不適合手勢辨識 |
