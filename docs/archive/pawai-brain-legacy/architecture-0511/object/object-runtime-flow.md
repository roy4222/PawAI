# Object Runtime Flow

這份文件只看物體辨識 runtime：相機進來、YOLO 怎麼跑、事件怎麼發、誰消費。

## 1. 系統位置

物體辨識住在獨立 ROS2 package：

```text
object_perception/
```

它不在 `vision_perception` 裡，和 pose/gesture 分開。原因是 object 用 YOLO26n ONNX + TensorRT，運算模型、設定、debug image 都和 pose/gesture 不同。

主要檔案：

| 角色 | 檔案 |
| --- | --- |
| object node | `object_perception/object_perception/object_perception_node.py` |
| COCO 80 + 中文表 | `object_perception/object_perception/coco_classes.py` |
| runtime config | `object_perception/config/object_perception.yaml` |
| launch | `object_perception/launch/object_perception.launch.py` |
| Brain cache | `pawai_brain/pawai_brain/capability/world_snapshot.py` |
| Brain prompt formatting | `pawai_brain/pawai_brain/conversation_graph_node.py` |
| Executive remark | `interaction_executive/interaction_executive/brain_node.py::_on_object()` |

## 2. Runtime 架構圖

```text
D435 RGB
  /camera/camera/color/image_raw
        |
        v
object_perception_node.py
  - letterbox 640x640
  - ONNX Runtime providers:
      TensorRT EP -> CUDA EP -> CPU EP
  - output (1,300,6)
      [x1,y1,x2,y2,conf,class_id]
  - conf threshold
  - class whitelist
  - inverse letterbox bbox
  - HSV 12-color on bbox crop
  - per-class cooldown 5s
        |
        +-----------------------------+
        |                             |
        v                             v
/event/object_detected          /perception/object/debug_image
  String JSON                    Image with bbox + zh label
        |
        +-------------------+----------------------+
        |                   |                      |
        v                   v                      v
pawai_brain              interaction_executive   studio gateway
recent_objects cache     object_remark TTS       object panel
```

## 3. Runtime config

目前設定：

```yaml
object_perception_node:
  ros__parameters:
    model_path: "/home/jetson/models/yolo26n.onnx"
    trt_cache_dir: "/home/jetson/trt_cache/"
    color_topic: "/camera/camera/color/image_raw"
    confidence_threshold: 0.5
    input_size: 640
    tick_period: 0.067
    publish_fps: 8.0
    class_cooldown_sec: 5.0
    class_whitelist: []
```

重點：

- `class_whitelist: []` 代表 80 類全開。
- node tick 約 15Hz。
- debug image 限頻 `publish_fps=8.0`。
- event 有 per-class 5s cooldown，不會每幀狂發同一類。

## 4. Event schema

Topic：

```text
/event/object_detected
```

Payload：

```json
{
  "stamp": 1715425123.4567,
  "event_type": "object_detected",
  "objects": [
    {
      "class_name": "cup",
      "confidence": 0.894,
      "bbox": [123, 456, 234, 567],
      "color": "red",
      "color_confidence": 0.75
    }
  ]
}
```

欄位說明：

| 欄位 | 意義 |
| --- | --- |
| `class_name` | COCO 80 類，空格改底線，例如 `cell_phone`、`dining_table` |
| `confidence` | YOLO 偵測信心 |
| `bbox` | 原圖座標，Python int list |
| `color` | HSV 12 色；Unknown 時省略 |
| `color_confidence` | 主要顏色比例；和 `color` 一起出現或一起省略 |

注意：沒有 `/state/perception/object`。object 目前是事件流，狀態快取在 Brain `WorldStateSnapshot` 裡。

## 5. TensorRT 注意事項

第一次載入模型可能需要很久：

```text
3-10 分鐘 TensorRT engine build
```

cache 在：

```text
/home/jetson/trt_cache/
```

ONNX Runtime provider fallback：

```text
TensorrtExecutionProvider
-> CUDAExecutionProvider
-> CPUExecutionProvider
```

明天現場要看 log 裡實際 active providers，不要只看 config。若 silent fallback 到 CPU，FPS 會掉，物體事件可能延遲。

## 6. 和 face/pose/gesture 最大差異

Object 沒有 tracking、沒有 depth、沒有 state topic。

| 模組 | 是否有 state | 是否有距離 | 是否 tracking |
| --- | --- | --- | --- |
| face | 有 `/state/perception/face` | 有 depth ROI | 有 track |
| pose | 目前只有 event | 沒有 | 沒有 |
| gesture | event | 沒有 | 沒有 |
| object | event | 沒有 | 沒有 |

所以 object 不能回答「杯子離我多遠」，也不能穩定知道「同一個杯子」是不是同一個 instance。現在只知道「最近 30 秒看過某類物件」。

