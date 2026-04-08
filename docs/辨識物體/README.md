# 物體辨識

> Status: current

> 預設目標物辨識（6 個 P0 class），YOLO26n ONNX + ORT TensorRT EP。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Executive 整合完成**，cup 觸發 TTS 通過 |
| 版本/決策 | YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16（不裝 ultralytics） |
| 完成度 | 70%（Executive 整合完成，Demo 腳本已加入，待擴充白名單+TTS） |
| 最後驗證 | 2026-04-06（cup → TTS「你要喝水嗎？」✅，bottle ❌） |
| 模型檔案 | Jetson: `/home/jetson/models/yolo26n.onnx`（9.5MB） |
| TRT Cache | `/home/jetson/trt_cache/`（首次啟動 3-10 分鐘，之後秒起） |
| Package | `object_perception/`（ROS2 Python，entry: `object_perception_node`） |

## 核心流程

```
D435 RGB (/camera/camera/color/image_raw)
    ↓
object_perception_node（YOLO26n ONNX, ORT TensorRT EP FP16）
    ├→ /event/object_detected（JSON: objects[] 陣列，per-class cooldown 5s）
    └→ /perception/object/debug_image（bbox overlay, Foxglove 可視化）
    ↓
interaction_executive_node（物體辨識結果 → TTS 回報）[待整合]
```

## Event Schema

```json
{
  "stamp": 1775371004.13,
  "event_type": "object_detected",
  "objects": [
    {"class_name": "chair", "confidence": 0.878, "bbox": [336, 240, 462, 474]}
  ]
}
```

- 每 tick 可能偵測多物件，統一用 `objects` 陣列
- `bbox`: Python int `[x1, y1, x2, y2]` 像素座標（逆 letterbox 後）
- `class_name`: 見下方 P0 類別表
- Per-class cooldown 5s：同 class 連續偵測不重複發 event

## 實測資源

### 4/4 Phase B（四核心全開壓測）
| 指標 | 值 |
|------|---|
| FPS | 15.0 穩定（70 秒零掉幀） |
| RAM 增量 | +1GB（3667/7620 MB） |
| GPU | 0%（TensorRT EP） |
| 溫度 | 56°C |
| 功耗 | 8.9W |

### 4/5 Phase C（ROS2 node 單獨跑 5 分鐘穩定性）
| 指標 | 值 |
|------|---|
| Debug image Hz | 6.3-6.8 Hz（publish_fps=8.0） |
| Event 發布 | 正確（per-class cooldown 5s 生效） |
| RAM | 2312 → 2319 MB（+7MB，無 leak） |
| 溫度 | 48°C（持平略降） |
| Node process CPU | 38.5% |
| ONNX providers | TensorRT + CUDA + CPU |

## 偵測類別 — COCO 80 class（預設全開）

自 v0.2（2026-04-05）起，node 預設辨識**完整 COCO 80 類**。完整類別 ID → name 映射見 `object_perception/object_perception/coco_classes.py`。

### Class whitelist（可選縮減）

ROS2 參數 `class_whitelist` 控制：
- `[]`（預設）— 全開 80 類
- `[0, 16, 39, 41, 56, 60]` — 縮減為原 P0 6 類

Launch 時覆寫：
```bash
ros2 launch object_perception object_perception.launch.py \
  class_whitelist:='[0, 16, 39, 41, 56, 60]'
```

或改 `config/object_perception.yaml`。

### 常用 P0 subset（Demo 展示目標）

| Class | COCO ID | 命名 | 用途 |
|-------|:-------:|------|------|
| person | 0 | `person` | 人物偵測 |
| dog | 16 | `dog` | 專題主題 |
| bottle | 39 | `bottle` | 小物展示 |
| cup | 41 | `cup` | 小物展示 |
| chair | 56 | `chair` | 環境理解 |
| dining table | 60 | `dining_table` | 環境理解 |

### 命名規則

COCO 原名含空格者統一改底線（JSON consistency）：
- `dining table` → `dining_table`
- `cell phone` → `cell_phone`
- `traffic light` → `traffic_light`
- `teddy bear` → `teddy_bear`
- 等等（共 15 個原含空格名稱）

## 部署路徑

**不在 Jetson 上裝 ultralytics**（會覆蓋 Jetson torch wheel，4/4 已踩坑）。

1. WSL 上用 ultralytics 匯出：`yolo26n.pt` → `yolo26n.onnx`（`format='onnx', imgsz=640, simplify=True, opset=17`）
2. scp 到 Jetson `/home/jetson/models/`
3. Jetson 上用 `onnxruntime-gpu`（已有）直接載入，TensorRT EP + FP16

YOLO26n 是 NMS-free，output shape `(1, 300, 6)` = `[x1, y1, x2, y2, conf, class_id]`，後處理只需 threshold filter。

## 啟動方式

```bash
# Jetson 上（需 D435 先跑）
ros2 launch realsense2_camera rs_launch.py enable_depth:=false pointcloud.enable:=false
# 另一個 window
source install/setup.zsh
ros2 launch object_perception object_perception.launch.py
```

**TRT 參數陷阱**：`trt_engine_cache_enable` 和 `trt_fp16_enable` 的值必須是 `"True"`/`"False"` 字串，不是 `"1"`/`"0"`，否則會 fallback 到 CPU。

## Executive 整合（Day 10 晚完成）

`interaction_executive_node` 已訂閱 `/event/object_detected`，支援 3 個高價值 class 的 TTS 話術（其他 COCO 77 class 靜默忽略）：

| class | TTS 話術 |
|-------|---------|
| `cup` | 「你要喝水嗎？」 |
| `bottle` | 「喝點水吧」 |
| `book` | 「在看書啊」 |

**行為約束**：
- 只在 IDLE 狀態觸發（Greeting / Conversing / Emergency 不被打斷）
- Per-class 5s cooldown dedup（避免同物品反覆觸發）
- Priority 5（低於 face / speech / gesture / obstacle / fall）
- 未來擴展新 class：修改 `interaction_executive/state_machine.py` 的 `OBJECT_TTS_MAP`

## 實測結果（4/6 上機驗證）

| 物品 | 結果 | 備註 |
|------|:----:|------|
| cup 杯子 | ✅ | threshold 0.5，觸發 TTS「你要喝水嗎？」 |
| cell phone 手機 | ✅ | 適當光線下可辨識 |
| book 書本 | ⚠️ | 平放時困難，翻開展示可辨識（threshold 0.3 下偶爾偵測） |
| bottle 水瓶 | ❌ | 未偵測到，Demo 不展示 |

## 已知問題

- **光線不足時小物體幾乎無法辨識** — Demo 必須開燈
- 物體需在一定高度且正對攝影機角度才能偵測到
- YOLO26n 是 Nano 版（9.5MB），小物件偵測率低
- 平放的扁平物體辨識困難（書本、手機平放）
- **Jetson 供電不穩**：累積斷電 8+ 次
- 追蹤、3D depth、target selection 未做

## 下一步

- [ ] 決定白名單物品（室內 COCO 篩選）+ 每個物品 TTS 回應（黃旭，4/9 分工）
- [ ] yolo26s 升級評估（mAP +6.3%，~20MB，改善小物件）
- 見分工文件：`pawai-studio/docs/0410assignments/go2-jetson/object-huang.md`

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 物體辨識可行性研究（YOLO26n 評估） |
