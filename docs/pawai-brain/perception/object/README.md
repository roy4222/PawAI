# 物體辨識

> Status: current

> 預設目標物辨識（6 個 P0 class），YOLO26n ONNX + ORT TensorRT EP。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Brain 全鏈路通**：12 colour HSV + zh class label + colour-aware TTS（5/6 Jetson 上機驗證） |
| 版本/決策 | YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16（不裝 ultralytics） |
| 完成度 | 85%（顏色 / 中文 / 32 class TTS whitelist 落地；小物件距離問題未解）|
| 最後驗證 | 2026-05-06（chair brown/black、cup gray、person cyan 全鏈路觀察到 brain `object_remark` 觸發 zh TTS）|
| 模型檔案 | Jetson: `/home/jetson/models/yolo26n.onnx`（大小待實測） |
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

## 模型比較（yolo26n vs yolov8n vs yolo26s）

> **狀態**: 待實測。下表只列**比較維度與當前角色**；mAP / FPS / 模型大小等具體數字 **5/12 demo 後**才補（需自家 Jetson + class_whitelist 條件下的 benchmark 才有意義，引用上游 README 的全 80-class 數字會誤導）。

| 模型 | 角色 | 比較維度 |
|---|---|---|
| **yolo26n** | **主線**（5/12 demo 已上機驗證） | 待實測：mAP / 大小 / Jetson FP16 FPS / 小物件偵測率 |
| yolov8n | MOC §5 對比候選；目前未上機 | 同上；要進主線需先做 A/B |
| yolo26s | 升級候選（post-demo） | 同上；MOC 提到改善小物件，需驗證 |

> MOC §5 寫「yolo26n 和 yolov8n 辨識物體效果比較」— 5/12 demo 不做完整 A/B（時程不足），保留為 post-demo 評估項。**yolo26n 已經是上機驗證主線**，不切換。
> 真實數字補在 [`research/`](./research/) 子資料夾的 benchmark 報告，更新到此表前先 cite 來源。

## HSV 顏色偵測（5/6 12 色升級）

> MOC §5：「要可以偵測顏色」。
> 程式：`object_perception/object_perception/object_perception_node.py::analyze_bbox_color`（module-level，可單元測試；class staticmethod 委派之）
> 歷史：5/5 落地 4 色（commit `4f638ae`）→ 5/6 升 12 色（commit `d9fef2d`）

### 演算法（per-pixel 分類取 mode）

```
YOLO bbox → crop ROI → cv2.cvtColor(BGR→HSV)
  → 12 個互斥 mask（V/S 守門優先於 hue band）
  → peak mask pixels / total pixels = ratio
  → ratio < 0.25 視為「太碎」回 "Unknown"
```

### 12 色分類

| 優先 | 標籤 | 規則（OpenCV: H 0-180, S/V 0-255）|
|:---:|:---:|---|
| 1 | black | V < 50 |
| 2 | white | S < 40 AND V ≥ 200 |
| 3 | gray | S < 40 AND 50 ≤ V < 200 |
| 4 | brown | warm hue 5-25 AND V < 130（chromatic & dark）|
| 5 | pink | (red side H ≥ 160 OR ≤ 5 + S < 150 + V ≥ 180) OR magenta band 150-165 |
| 6 | red | H ≤ 8 OR ≥ 165（不是 brown / pink）|
| 7 | orange | 8 < H ≤ 22 |
| 8 | yellow | 22 < H ≤ 35 |
| 9 | green | 35 < H ≤ 85 |
| 10 | cyan | 85 < H ≤ 100 |
| 11 | blue | 100 < H ≤ 130 |
| 12 | purple | 130 < H ≤ 150 |

**為什麼 brown / pink 要先過 V/S，不只看 hue**：brown 的 hue 在 orange/yellow band 但 V 偏低；pink 在紅或洋紅側但通常 S 較低 V 較高。單純擴 hue band 會把咖啡色椅子歸成 yellow / red。

### Event 寫入規則

Saturation 過低或 ratio < 0.25 → 不寫 `color` / `color_confidence`（前端視為無色）。

例子（咖啡色椅子）：
```json
{
  "objects": [
    {"class_name": "chair", "confidence": 0.51, "bbox": [..],
     "color": "brown", "color_confidence": 0.367}
  ]
}
```

### 中文顯示 + TTS 渲染

- 三份 zh dict（perception node `coco_classes.py:COLOR_ZH` / brain `OBJECT_COLOR_ZH` / frontend `object-config.ts:COLOR_ZH`）— 互不依賴，避免 ROS2 跨 package import；keep in sync 於檔頂註明
- `紅 / 橘 / 黃 / 綠 / 青 / 藍 / 紫 / 粉紅 / 咖啡 / 黑 / 白 / 灰`
- Studio 物體 panel `live-detection.tsx` 渲染：「咖啡色 椅子」（COLOR_ZH + getLabel(class_name)）
- Brain `build_object_tts(class_name, color)` 產出：`看到{COLOR_ZH}的{class_zh}了` + 可選 personality suffix

### 80 類中文 + zh 渲染（debug overlay）

`object_perception_node._publish_debug_image` 5/6 起切 PIL CJK rendering（cv2.putText 不支援中文），讀 `coco_classes.COCO_CLASSES_ZH` 顯示 80 類中文 label，font 從 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` 載入，無 CJK 字型則 fallback ASCII。

## Scene 6 `object_remark` 整合（5/12 Sprint）

### 觸發條件

```
/event/object_detected: { class_name: "cup", color: "red", confidence: ≥0.5 }
    ↓
brain_node 規則 `object_remark` 命中（class ∈ {cup, bottle, ...} + color 非空）
    ↓
SkillPlan(object_remark) → say_template 渲染 `{class}` + `{color}`
    ↓
TTS：「咦，你拿著紅色的杯子！」
```

### Event Schema 擴充（5/5 起）

```json
{
  "event_type": "object_detected",
  "objects": [
    {
      "class_name": "cup",
      "confidence": 0.878,
      "bbox": [336, 240, 462, 474],
      "color": "red",          // 新增（HSV 結果，可為 null）
      "color_confidence": 0.72  // 新增
    }
  ]
}
```

> Schema 變動需同步 `docs/contracts/interaction_contract.md` v2.6（contract 升版）。本 README 為先描述，contract 升版時 cross-link。

### 個性化回覆範例（傳給 brain，由 LLM 改寫）

| class | color | TTS（demo baseline 範例）|
|---|:---:|---|
| cup | red | 「咦，你拿著紅色的杯子！」 |
| cup | blue | 「藍杯子，看起來很涼」 |
| bottle | red | 「紅瓶子，喝點水吧」 |
| bottle | green | 「綠色瓶子是茶嗎？」 |
| 其他 | * | LLM 動態生成 |

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

## Brain 整合（5/6 改寫，取代 5/5 state_machine 路徑）

實際生產路徑走 `interaction_executive/brain_node.py:_on_object` → `build_object_tts` → `object_remark` skill，**不**經 `state_machine.py:OBJECT_TTS_MAP`（後者已不在實際 wire 上）。

### TTS whitelist（~32 class）

只對常見家居物件開口；其他 48 類（飛盤、紅綠燈、滑雪板等）UI 仍顯示，但 brain 靜默：

```
cup, bottle, book, person, dog, cat, chair, couch, bed, dining_table,
tv, laptop, cell_phone, remote, keyboard, mouse, backpack, handbag,
umbrella, clock, vase, potted_plant, teddy_bear, scissors, wine_glass,
fork, knife, spoon, bowl, banana, apple, orange
```

### 模板：colour preamble + optional personality suffix

```python
# 標準格式：「看到 {COLOR_ZH 顏色} 的 {class_zh}」
build_object_tts("cup", "red")     == "看到紅色的杯子了，你要喝水嗎？"   # special suffix
build_object_tts("laptop", "blue") == "看到藍色的筆電了"                # no suffix
build_object_tts("chair", "brown") == "看到咖啡色的椅子了"
build_object_tts("cup", "Unknown") == "看到杯子了，你要喝水嗎？"        # 無顏色
build_object_tts("frisbee", "red") is None                            # 不在 whitelist
```

`OBJECT_TTS_SPECIAL_SUFFIX` 只 cup / bottle / book 三個有 personality phrase（5/6 user 回饋：suffix 接在 colour preamble 後，不替換）。

### 行為約束

- Cooldown 5s（在 brain `_emit_with_cooldown`）
- payload 兩種格式都吃：production `{"objects": [...]}` 與 legacy flat `{"label", "color"}`
- 不在 active sequence 中才觸發（brain `_has_active_sequence` 守門）

### 棄用路徑

`interaction_executive/state_machine.py:OBJECT_TTS_MAP`（5/5 設計，cup / bottle / book 三類英文模板）— 還在檔案裡但未被 wire；新增類別不要改它。

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
- YOLO26n 是 Nano 版（小物件偵測率低，模型大小待實測）
- 平放的扁平物體辨識困難（書本、手機平放）
- **Jetson 供電不穩**：累積斷電 8+ 次
- 追蹤、3D depth、target selection 未做

## 下一步

- [x] **B4-4 HSV 顏色偵測**（5/5 commit `4f638ae` 落地 4 色；5/6 commit `d9fef2d` 升 12 色 + brown / pink / 黑灰白）
- [x] **Scene 6 `object_remark` 整合**（5/6 commit `545cd33` brain pipeline，real-machine 觀察 chair brown / chair black 觸發 zh TTS）
- [x] **Event schema 升版 v2.5**（5/6 commit `545cd33` 補 color / color_confidence；commit `d9fef2d` 升 12 色 enum）
- [ ] **小物件偵測距離問題**：`input_size` 640 → 960 A/B（YOLO26n 訓練 640，調 960 不保證好；需 mAP + Jetson FPS 雙軸驗證）
- [ ] 室內 dataset 進階（post-demo）：MOC §5 提「資料集目前用 coco 看是否要用多一點室內」— 5/12 demo COCO 80 + 12 colour 即可，post-demo 再評估 OpenImages / Objects365 finetune
- [ ] yolo26s 升級評估（mAP / 大小 / Jetson FPS / 小物件偵測率 全部待實測）
- [ ] 平放扁平物體（書本、手機）辨識率改善（光線 + 角度 + threshold tuning）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 物體辨識可行性研究（YOLO26n 評估） |
