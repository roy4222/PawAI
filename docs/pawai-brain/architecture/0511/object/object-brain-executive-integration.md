# Object Brain and Executive Integration

這份文件看 `/event/object_detected` 發出後怎麼進 Brain 與 Executive。object 的互動品質主要靠下游保護，否則 PawAI 會一直碎念或講錯顏色。

## 1. Brain recent object cache

Brain 訂閱：

```text
/event/object_detected
```

handler：

```text
pawai_brain/pawai_brain/conversation_graph_node.py::_on_object_detected()
```

它把 raw JSON 丟給：

```text
pawai_brain/pawai_brain/capability/world_snapshot.py::apply_object_detected_json()
```

cache 策略：

| 規則 | 說明 |
| --- | --- |
| maxlen | 8 |
| window | 30 秒 |
| dedup | 每個 class 只保留最新一筆 |
| exclude | `person` 被排除 |
| color gate | `color_confidence < 0.6` 時丟掉 color |
| order | 最新在前 |

## 2. Prompt injection

格式化在：

```text
pawai_brain/pawai_brain/conversation_graph_node.py::_format_recent_objects()
```

輸出格式：

```text
紅色的杯子（5 秒前）
椅子（12 秒前）
```

最多注入 3 筆：

```text
return "、".join(parts[:3])
```

未知 class 會靜默跳過，不會把 raw English 塞進 prompt。

## 3. 為什麼 person 被排除

Object node 仍會 publish `person`，因為 Studio/UI 可以顯示。

但 Brain recent_objects 會排除 `person`：

```text
_OBJECT_EXCLUDE_CLASSES = ("person",)
```

原因：

- 人已經由 face_identity / pose 處理。
- object path 沒有 identity、distance、track。
- 不排除會出現「黑色的人」這種怪描述。

## 4. Executive object_remark

檔案：

```text
interaction_executive/interaction_executive/brain_node.py::_on_object()
```

它只取 production payload 的第一個 detection：

```text
objects[0]
```

觸發 `object_remark` 的 gate：

| gate | 目的 |
| --- | --- |
| `AttentionState == ENGAGED` | 人真的停下來互動才講 |
| no active skill/sequence | 不打斷正在做的動作 |
| no pending confirm | 不打斷 OK 確認流程 |
| not tts_playing | 不插嘴 |
| `build_object_tts()` not None | class 在 TTS 白名單 |
| class 60s dedup | 同類物件不要一直講 |

## 5. TTS 白名單

Executive 的中文表是 subset，不是完整 COCO 80。這是刻意設計：

```text
UI 可以顯示 80 類；
PawAI 主動說話只對室內有意義的類別。
```

`build_object_tts()` 對 `person` 直接 return None，避免和 face/stranger path 打架。

範例：

| class/color | TTS |
| --- | --- |
| `cup`, `red` | 看到紅色的杯子了，你要喝水嗎？ |
| `book`, None | 看到書了，在看書啊 |
| `laptop`, `blue` | 看到藍色的筆電了 |
| `person`, `black` | 不說 |
| `frisbee`, `red` | 不說 |

## 6. 最大限制：沒有 distance 和 instance tracking

object event 沒有：

```text
distance_m
track_id
instance_id
depth
```

所以 Executive 不能說：

- 「杯子離你很近」
- 「同一個杯子還在」
- 「左邊那個杯子」
- 「我正在靠近杯子」

現在只能說「最近看過 cup/chair/book」。如果要做拿取、靠近、指物導航，object payload 要加 depth 或和 D435 point cloud 對齊。

## 7. 和使用者目前理解的對照

使用者理解大致正確：

- 可以看出 COCO 物體與 12 色。
- 可以回答「手上拿的東西」和「現在看到什麼」。
- 顏色容易受光線影響。
- COCO 室內物件集偏少。

需要補上的點：

- Brain 只保留 30 秒 recent object，不是永久記憶。
- Executive 只取第一個 detection 做 object_remark。
- object 沒有 state topic，也沒有距離。
- person 在 Brain/Executive 會被過濾，不代表 object node 沒看到人。
- 顏色有兩層門檻：object node `0.25` Unknown gate，Brain `0.6` color confidence gate。

