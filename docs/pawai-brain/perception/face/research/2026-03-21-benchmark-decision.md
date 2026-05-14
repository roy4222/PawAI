# 人臉辨識模型選型調查

> 最後更新：2026-03-21

## 目標效果
- 偵測 + 識別 D435 視野內的人臉，距離 0.5-3m
- 4/13 Demo 目標：已知人臉識別成功率 ≥ 80%，偵測延遲 < 200ms

## 候選模型

| # | 模型 | 框架 | 輸出 | Installability | Runtime viability | GPU 路徑 | 實測性能 | 納入原因 | 預期淘汰條件 |
|---|------|------|------|:-:|:-:|:-:|---|---|---|
| 1 | YuNet 2023mar | OpenCV DNN | bbox + 5-point | verified | verified | cpu_only | **71.3 FPS** (L1 實測) | 現有主線，CPU-only | — |
| 2 | YuNet legacy | OpenCV DNN | bbox + 5-point | verified | **failed** | cpu_only | 0 FPS | OpenCV 4.13 不相容 | ~~已淘汰~~ |
| 3 | SCRFD-500M | ONNX Runtime | bbox + 5-point | verified | verified | cuda | **34.7 FPS** (L1 實測) | InsightFace 推薦 | — |
| 4 | SFace (recognition) | OpenCV DNN | 128-d embedding | verified | verified | cpu_only | 待測 | 現有識別主線 | — |

### 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|
| MediaPipe Face Detection | Jetson ARM64 無 wheel，GPU delegate 不可用 | community_only |
| RetinaFace-R50 | 模型太大 (~100MB)，Jetson 記憶體預算不足 | community_only |

## 社群調查摘要
- **YuNet**：OpenCV Zoo 內建，`cv2.FaceDetectorYN`，無額外依賴。Jetson 上走 CPU（OpenCV DNN 的 CUDA backend 不支援 FaceDetectorYN）。~6.6 Hz 已在 3/18 實測。
- **SCRFD-500M**：InsightFace 系列輕量偵測器。ONNX 格式，可走 CUDAExecutionProvider。社群在 Jetson 上有部署案例但需驗證。
- **SFace**：OpenCV Zoo 內建識別模型，128 維 embedding，餘弦相似度匹配。已驗證可用。

## Jetson 資源約束
- 人臉偵測+識別合計 RAM 增量目標：< 500MB
- GPU 預算：盡量 0%（CPU-only 最佳），允許最多 10%
- 與 RTMPose 共存時 GPU 已 91-99%，人臉模組不應再吃 GPU

## L2 共存測試（3/21 實測）

| Target | Companion | FPS | vs L1 | 備註 |
|--------|-----------|:---:|:-----:|------|
| pose_lw | yunet@8Hz (CPU) | 16.5 | -6% | CPU+GPU 分離，最佳共存 |
| pose_lw | scrfd@8Hz (GPU) | 15.8 | -10% | GPU 輕微競爭 |

## 決策（3/21 回填）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| **YuNet 2023mar** | **JETSON_LOCAL** | jetson | 71.3 FPS CPU-only，對 pose 干擾最小（-6%），系統最佳解 |
| SCRFD-500M | JETSON_LOCAL | jetson（備援） | 34.7 FPS CUDA，精度預期更高，但佔 GPU 使 pose 多掉 4% |
| YuNet legacy | REJECTED | — | OpenCV 4.13 不相容 dynamic shape |
| SFace | JETSON_LOCAL | jetson | 現有識別主線，待獨立 L1 benchmark |
