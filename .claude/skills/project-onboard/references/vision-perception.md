# 手勢 + 姿勢辨識 Reference

> 最後更新：2026-03-18
> 狀態：**SKELETON** — Phase 1 mock mode Jetson 驗證通過（3/18）。Phase 2 待做：RTMPose 真推理。

## 模組定位

P1 功能。用視覺辨識人體手勢與姿勢，觸發對應行為。
手勢與姿勢共用 RTMPose wholebody 推理（主路徑），分類器獨立。

- **手勢**：wave / stop / point / fist（4 種，實作用 fist，v2.0 契約發 ok，待 3/25 正式切換）
- **姿勢**：standing / sitting / crouching / fallen（4 種，跌倒偵測是安全功能）

## 核心程式（3/18 新增）

| 檔案 | 用途 |
|------|------|
| `vision_perception/vision_perception/vision_perception_node.py` | ROS2 node：推理 + 分類 + event 發布 |
| `vision_perception/vision_perception/gesture_classifier.py` | 手勢單幀規則分類（純 Python） |
| `vision_perception/vision_perception/pose_classifier.py` | 姿勢單幀規則分類（純 Python） |
| `vision_perception/vision_perception/event_builder.py` | 共用 JSON builder（含 fist→ok compat） |
| `vision_perception/vision_perception/inference_adapter.py` | 推理介面 ABC + InferenceResult |
| `vision_perception/vision_perception/mock_inference.py` | Mock 推理（6 場景） |
| `vision_perception/vision_perception/mock_event_publisher.py` | 獨立 mock node（給前端用） |

## 啟動方式

```bash
# Phase 1：mock mode（不需相機）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=mock use_camera:=false mock_scenario:=stop

# Mock publisher（給前端開發）
ros2 launch vision_perception mock_publisher.launch.py
```

## 權威文件

| 文件 | 用途 |
|------|------|
| `docs/手勢辨識/README.md` | 手勢辨識技術選型、方案比較、分類邏輯、ROS2 整合 |
| `docs/姿勢辨識/README.md` | 姿勢辨識技術選型、角度法/高度比法、跌倒偵測、Node 架構 |
| `docs/architecture/contracts/interaction_contract.md` §4.3-4.7 | ROS2 event schema（v2.1，含 interaction_router topics） |
| `docs/Pawai-studio/event-schema.md` §1.4-1.5, §2.5-2.6 | Studio 前端 event/state schema |

## 技術選型結論

| 方案 | 角色 | 狀態 |
|------|------|------|
| **DWPose + TensorRT** | Jetson 部署主線 | 待本機驗證（社群回報 ~45 FPS） |
| **RTMPose + TensorRT** | 備援路線（匯出較成熟） | 未測 |
| trt_pose_hand | 次選（NVIDIA 官方，6 類手勢內建） | 未測 |
| ~~MediaPipe~~ | 僅限 x86 概念驗證 | Jetson ARM64 不可用 |

### 為什麼不用 MediaPipe 部署 Jetson

- PyPI 無 Linux ARM64 wheel（必須從 source build）
- TFLite GPU delegate 在 Jetson 上不能正確初始化
- CPU-only 效能差（<5-25 FPS）
- 社群 wheel 停在 v0.8.5，JetPack 6.x 建構困難

## 關鍵架構決策

### 共用推理，分類器獨立

```
D435 RGB frame → DWPose TensorRT 推理 → 133 keypoints (COCO-WholeBody)
  ├── body (17) + foot (6) → pose_classifier → /event/pose_detected
  └── hand (21×2) → gesture_classifier → /event/gesture_detected
```

### COCO-WholeBody 133 keypoints

17 body + 6 foot + 68 face + 21 hand×2 = 133。不是 169。

### Node 命名

- 方案 A（推薦）：單一 `vision_perception_node`
- 方案 B：拆分 `pose_perception_node` + `gesture_perception_node`（對齊 interaction_contract）

### Contract 邊界

- `/event/pose_detected`、`/event/gesture_detected`：v2.0 凍結介面
- `/state/perception/pose`：v2.1 擬新增，目前作為內部 topic，未納入凍結

## 已知陷阱

- MediaPipe → DWPose 移植**不能直接搬閾值**：keypoint 集合、索引、座標系統不同
- x86 demo 只驗證 UX 流程與事件格式，Jetson 部署時分類閾值需重新校正
- DWPose 與 RTMPose 不是完全等價替換（蒸餾後精度不同，匯出路徑不同）
- 45 FPS 數據來自社群文章，非官方 benchmark，需本機實測

## 開發入口

- 手勢分類邏輯：landmarks 角度/距離 → 規則分類器（不需訓練模型）
- 姿勢分類邏輯：角度法 + 高度比法 + 20 幀投票 buffer
- 跌倒偵測：bounding box 寬高比 > 1.0 + 軀幹角度 > 60° → fallen

## 落地順序

| Phase | 時間 | 內容 | 負責 |
|:-----:|------|------|:----:|
| 1 | 3/16-3/23 | 楊在 x86 用 MediaPipe 做 UX 流程 demo | 楊 |
| 2 | 3/23-4/1 | Roy 在 Jetson 部署 DWPose + TensorRT，重新校正閾值 | Roy |
| 3 | 4/1-4/6 | 整合進 ROS2 node + 接入 Interaction Executive | Roy |
| 4 | 4/6-4/13 | 端到端測試 + Demo B 微調 | Roy + 楊 |

## 驗收方式

- `/event/gesture_detected`：wave/stop/point/ok 各辨識 5 次，成功率 ≥ 70%
- `/event/pose_detected`：standing/sitting/crouching/fallen 各辨識 5 次，成功率 ≥ 70%
- 跌倒偵測延遲 < 2 秒（從跌倒動作到事件發布）
- Jetson 記憶體占用增量 < 300MB
