# 物體辨識 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界（規劃中，尚未實作）

- **所屬 package**：待建（可能在 `vision_perception` 內）
- **上游**：D435 RGB camera
- **下游**：interaction_executive_node

## 規劃 Topic

| Topic | 類型 | 頻率 | Schema |
|-------|------|------|--------|
| `/event/object_detected` | String (JSON) | 事件式 | `{"class": str, "confidence": float, "bbox": [4], "timestamp": float}` |

## 輸入

- `/camera/color/image_raw`（D435 RGB）

## 依賴（規劃）

- `ultralytics`（YOLO26n / YOLO11n）
- TensorRT FP16
- D435 RealSense

## 預設辨識目標

水杯、藥罐、遙控器等日常物品（3/26 會議決策：預設目標，非自由搜尋）

## 接手確認清單

- [ ] Sprint Day 8 Go/No-Go 結果？
- [ ] ultralytics 可在 Jetson 安裝？
- [ ] TensorRT 轉換成功？
- [ ] RAM 增量 < 1.1GB？
