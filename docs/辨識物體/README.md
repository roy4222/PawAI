# 物體辨識

> Status: current

> 預設目標物辨識（6 個 P0 class），YOLO26n ONNX + ORT TensorRT EP。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Go 判定通過**，Phase C（最小 ROS2 node）待做 |
| 版本/決策 | YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16（不裝 ultralytics） |
| 完成度 | 20%（Go/No-Go 通過，ONNX 匯出完成，ROS2 node 未建） |
| 最後驗證 | 2026-04-04（Phase B 真實 D435 feed 60s 共存壓測 PASS） |
| 模型檔案 | Jetson: `/home/jetson/models/yolo26n.onnx`（9.5MB） |
| TRT Cache | `/home/jetson/trt_cache/`（首次啟動 3-10 分鐘，之後秒起） |

## 核心流程

```
D435 RGB (/camera/camera/color/image_raw)
    ↓
object_perception_node（YOLO26n ONNX, ORT TensorRT EP FP16）
    ├→ /event/object_detected（JSON: class, confidence, bbox）
    └→ /perception/object/debug_image（bbox overlay, Foxglove 可視化）
    ↓
interaction_executive_node（物體辨識結果 → TTS 回報）[待整合]
```

## 實測資源（4/4 Phase B，四核心全開）

| 指標 | 值 |
|------|---|
| FPS | **15.0 穩定**（70 秒零掉幀） |
| RAM 增量 | +1GB（3667/7620 MB） |
| GPU | 0%（TensorRT EP） |
| 溫度 | 56°C |
| 功耗 | 8.9W |

## P0 偵測目標（6 class）

| Class | COCO ID | 用途 |
|-------|:-------:|------|
| person | 0 | 人物偵測 |
| dog | 16 | 專題主題 |
| bottle | 39 | 小物展示 |
| cup | 41 | 小物展示 |
| chair | 56 | 環境理解 |
| dining table | 60 | 環境理解 |

## 部署路徑

**不在 Jetson 上裝 ultralytics**（會覆蓋 Jetson torch wheel，4/4 已踩坑）。

1. WSL 上用 ultralytics 匯出：`yolo26n.pt` → `yolo26n.onnx`（`format='onnx', imgsz=640, simplify=True, opset=17`）
2. scp 到 Jetson `/home/jetson/models/`
3. Jetson 上用 `onnxruntime-gpu`（已有）直接載入，TensorRT EP + FP16

YOLO26n 是 NMS-free，output shape `(1, 300, 6)` = `[x1, y1, x2, y2, conf, class_id]`，後處理只需 threshold filter。

## 已知問題

- Phase C（ROS2 node）尚未建立
- Executive 整合未做
- 追蹤、3D depth、target selection 未做
- **Jetson 供電不穩**：4/4 單日斷電 3 次，Demo 前必須解決
- Sprint Day 8 Hard Gate 決定是否實作

## 下一步

- Sprint B-prime Day 8（4/4）：Go/No-Go gate + Phase 0
- 3/26 會議決策：改為「預設目標」而非自由搜尋

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 物體辨識可行性研究（YOLO26n 評估） |
