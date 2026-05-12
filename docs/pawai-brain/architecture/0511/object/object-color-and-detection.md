# Object Detection and Color

這份文件深挖 YOLO 後處理與 HSV 12 色。使用者提到「COCO 室內物件太少、顏色受光線影響」，核心就在這裡。

## 1. YOLO26n path

`object_perception_node.py` 的流程：

```text
BGR image
  -> letterbox 640x640
  -> float32 / 255
  -> CHW + batch
  -> ONNX session.run
  -> output (1,300,6)
  -> filter conf/class
  -> rescale bbox to original image
  -> analyze bbox color
```

模型：

```text
/home/jetson/models/yolo26n.onnx
```

YOLO output：

```text
[x1, y1, x2, y2, conf, class_id] x 300
```

`class_id` 是內部欄位，publish event 前會移除。

## 2. COCO 80 限制

類別表在：

```text
object_perception/object_perception/coco_classes.py
```

目前是 COCO 80，不是開放詞彙模型。它可以認：

- cup / bottle / book / chair / couch / bed / tv / laptop / keyboard / cell_phone
- dog / cat / person
- dining_table / bowl / spoon / fork / knife

但不能穩定認：

- 遙控器以外的各種小型電子零件
- 學校場景特定物，例如白板筆、識別證、講義、麥克風型號
- 具體品牌或細分類，例如「iPhone」「水壺」「保溫瓶」「筆袋」

所以 demo 問法要避免「這是什麼牌子」「這是什麼型號」。可以問：

```text
你看到什麼？
我手上拿的是什麼？
這是什麼顏色？
桌上有什麼？
```

## 3. HSV 12 色

顏色分類函式在 `object_perception_node.py`：

```text
analyze_bbox_color(image_bgr, x1, y1, x2, y2)
```

目前 12 色：

```text
red, orange, yellow, green, cyan, blue,
purple, pink, brown, black, white, gray
```

流程：

```text
bbox crop
  -> BGR2HSV
  -> priority masks
  -> count pixels per color
  -> peak / total
  -> if ratio < 0.25: Unknown
```

priority order：

| 順序 | 顏色 | 主要條件 |
| --- | --- | --- |
| 1 | black | V < 50 |
| 2 | white | S < 40, V >= 200 |
| 3 | gray | S < 40 |
| 4 | brown | warm hue + V < 130 |
| 5 | pink | red/magenta side + high V / lower S |
| 6-12 | red/orange/yellow/green/cyan/blue/purple | hue band |

## 4. 為什麼顏色容易錯

HSV 是 rule-based，不知道物體材質、光源、陰影。

常見問題：

| 現象 | 原因 |
| --- | --- |
| 咖啡色椅子被說橘色 | brown 需要 V < 130，光太亮會被分到 orange |
| 白色物體變灰色 | V 不夠高或陰影太重 |
| 黑色物體變藍/紫 | 低光下 hue noise 放大 |
| 電視螢幕顏色亂跳 | bbox crop 含畫面內容，不是物體外殼 |
| 多色書本 Unknown | peak ratio < 0.25 |
| 手拿杯子時顏色混到手 | bbox crop 含皮膚或背景 |

Brain 端有第二層保護：

```text
color_confidence < 0.6 -> 丟掉 color
```

也就是 object node 可能發 `color_confidence=0.35`，但 Brain 不會把顏色講進 prompt。

## 5. Debug image

Debug topic：

```text
/perception/object/debug_image
```

它會畫 bbox、中文 class、顏色、confidence。中文字型會從幾個 CJK font path 找，如果找不到，就 fallback 英文。

如果 event 有出現但 debug image 沒中文字，可能只是 Jetson 沒裝 CJK font，不代表辨識壞掉。

## 6. 測試現況風險

本地 `object_perception/test/test_object_perception.py` 有一個需要注意的舊測試：

```text
test_color_zh_complete
```

它仍期待 `COLOR_ZH` 只有 4 色：

```python
{"red", "yellow", "green", "blue"}
```

但 code 目前已經是 12 色。這表示「object 37 tests PASS」這句文件描述需要現場重跑驗證，或更新舊測試。明天如果跑 object tests 失敗，先看是不是這個測試過時，而不是急著改 `COLOR_ZH` 回 4 色。

## 7. 想看到更多東西的方向

如果目標是「你現在看到什麼？」描述更清楚，有三條路：

| 方向 | 優點 | 代價 |
| --- | --- | --- |
| YOLO26s | COCO 同類別但 mAP 較高，小物件可能改善 | 模型較大、TensorRT cache 需重建 |
| GroundingDINO / OWL-ViT 類 open-vocab | 可認更多詞 | Jetson 即時性和部署複雜度高 |
| Scene caption / VLM | 描述最自然 | 延遲、網路、隱私和成本都高 |

短期 demo 最實際：

- 保留 YOLO26n。
- 道具選 COCO 內且大一點的物件：cup、bottle、book、chair、laptop、keyboard、cell_phone。
- 問法聚焦「最近看到」而不是要求開放世界辨識。

