# Object Debug Runbook

這份是明天到學校現場排查 object 用的順序。先確定模型與 event，再看 Brain/Executive。

## 1. 確認 node 和參數

```bash
ros2 node list
ros2 param get /object_perception_node model_path
ros2 param get /object_perception_node confidence_threshold
ros2 param get /object_perception_node class_cooldown_sec
ros2 param get /object_perception_node color_topic
```

確認模型存在：

```bash
ls -lh /home/jetson/models/yolo26n.onnx
ls -lh /home/jetson/trt_cache/
```

第一次 launch 如果卡很久，可能是在 build TensorRT cache。

## 2. 確認相機 topic

```bash
ros2 topic hz /camera/camera/color/image_raw
ros2 topic echo /camera/camera/color/image_raw --once
```

object 只訂 RGB，不訂 depth。depth 壞了不會直接影響 object detection，但會影響其他模組。

## 3. 看 object event

```bash
ros2 topic echo /event/object_detected
```

注意 per-class cooldown 是 5 秒，同一類不會每幀發。

如果完全沒 event：

| 可能原因 | 檢查 |
| --- | --- |
| model path 不存在 | `ls /home/jetson/models/yolo26n.onnx` |
| TensorRT 還在 build | 看 launch log |
| 相機沒有 frame | `ros2 topic hz color_image` |
| confidence 太高 | 暫時降 `confidence_threshold` |
| class whitelist 限制 | `ros2 param get class_whitelist` |

## 4. 看 debug image

```bash
ros2 topic hz /perception/object/debug_image
```

如果 Studio object panel 沒更新，但 `/event/object_detected` 有資料，問題可能在 gateway/frontend，不在 object node。

如果 debug image 有框但沒有中文字，可能是 CJK font fallback，不影響 event。

## 5. 顏色 debug

event 有顏色時：

```json
{
  "class_name": "cup",
  "color": "red",
  "color_confidence": 0.75
}
```

Brain 只有在 `color_confidence >= 0.6` 才會把顏色放進 prompt。

症狀對照：

| 症狀 | 原因 |
| --- | --- |
| event 有 color，但 Brain 不講顏色 | color_confidence < 0.6 |
| 咖啡色說成橘色 | 光太亮，brown V<130 不成立 |
| 白色說灰色 | V 不夠高 |
| 多色物品沒有顏色 | peak ratio < 0.25，被 Unknown gate 擋掉 |
| 手上物體顏色錯 | bbox crop 混到手或背景 |

## 6. Brain 檢查

問：

```text
你現在看到什麼？
我手上拿的是什麼？
桌上有什麼？
```

同時看 Brain trace 是否有：

```text
world_state ... objs=1
```

如果 `/event/object_detected` 有資料但 Brain 沒講：

1. class 是否是 `person`，person 會被過濾。
2. class 是否不在 `_OBJECT_CLASS_ZH`，未知 class 會被跳過。
3. object 是否超過 30 秒 window。
4. LLM 是否走 fallback，沒有使用 scene context。

## 7. Executive 檢查

```bash
ros2 topic echo /event/skill_request
ros2 topic echo /tts
```

`object_remark` 不會隨便觸發。它需要：

```text
AttentionState == ENGAGED
no active skill
no pending confirm
not tts_playing
class in TTS whitelist
same class not mentioned within 60s
```

所以 event 有物體但 PawAI 沒主動說話，不一定是壞掉，可能是 gate 正常工作。

## 8. 測試

```bash
pytest object_perception/test/test_object_perception.py
pytest pawai_brain/tests/test_world_snapshot.py
pytest interaction_executive/test/test_brain_rules.py
```

目前本地測試有一個可能過時的點：`test_color_zh_complete` 仍期待 4 色，但 code 已是 12 色。如果 object tests 失敗，先確認是不是這個測試需要更新。

## 9. 明天建議優先修

P0：現場確認 YOLO event 能穩定出 cup/book/chair/laptop。

P0：更新過時的 color test，讓測試和 12 色實作一致。

P1：建立 demo-safe 道具清單：

```text
red cup
book
chair
laptop
keyboard
cell_phone
bottle
```

P1：若要「看到更多東西」，先評估 YOLO26s，而不是立刻換 open-vocab。

P2：若要距離或指物導航，新增 depth-based `distance_m`，但這是 object payload contract 變更。
