# 人臉辨識模型選型調查

> 最後更新：2026-03-19

## 目標效果
- 偵測 + 識別 D435 視野內的人臉，距離 0.5-3m
- 4/13 Demo 目標：已知人臉識別成功率 ≥ 80%，偵測延遲 < 200ms

## 候選模型

| # | 模型 | 框架 | 輸出 | Installability | Runtime viability | GPU 路徑 | 社群性能參考 | 納入原因 | 預期淘汰條件 |
|---|------|------|------|:-:|:-:|:-:|---|---|---|
| 1 | YuNet (legacy) | OpenCV DNN | bbox + 5-point | verified | verified | cpu_only | ~6.6 Hz (Jetson 3/18 實測) | 現有主線，穩定 | — |
| 2 | SCRFD-500M | ONNX Runtime | bbox + 5-point | likely | unknown | cuda | 推估 15+ Hz | InsightFace 推薦，更快更準 | 安裝失敗 or FPS 無明顯提升 |
| 3 | SFace (recognition) | OpenCV DNN | 128-d embedding | verified | verified | cpu_only | 已驗證 | 現有主線 | — |

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

## 決策（Stage 4 回填）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| | | | |
