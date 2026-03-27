# 物體辨識

> Status: current

> 預設目標物辨識（水杯、藥罐等日常物品），YOLO26n + TensorRT。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 研究完成，待實作 |
| 版本/決策 | YOLO26n TensorRT FP16（預設目標，非自由搜尋） |
| 完成度 | 0%（程式碼未建，研究已完成） |
| 最後驗證 | — |
| 入口檔案 | 待建 |
| 測試 | 待建 |

## 核心流程

```
D435 RGB (/camera/color/image_raw)
    ↓
object_detection_node（YOLO26n TensorRT FP16, ~1.4ms 推理）
    ↓
/event/object_detected（JSON: class, confidence, bbox）
    ↓
interaction_executive_node（物體辨識結果 → TTS 回報）
```

## 預估資源

- RAM 增量：0.6-1.1GB
- 推理：TensorRT FP16 ~1.4ms，Python E2E 10-15 FPS
- GPU：與 Whisper 時間分割共存（需驗證）

## 已知問題

- 程式碼完全缺失，需從零實作
- YOLO26n 尚未正式發佈，可能用 YOLO11n 替代
- TensorRT 部署流程未驗證
- Sprint Day 8 Hard Gate 決定是否實作

## 下一步

- Sprint B-prime Day 8（4/4）：Go/No-Go gate + Phase 0
- 3/26 會議決策：改為「預設目標」而非自由搜尋

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 物體辨識可行性研究（YOLO26n 評估） |
