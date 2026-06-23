# Pose Classifier Rules

這份文件深挖 `pose_classifier.py`。姿勢效果差不是單一 threshold 問題，而是 2D 骨架在不同距離、遮擋、半身入鏡時會失真，規則又彼此重疊。

## 1. 輸入與輸出

入口：

```text
vision_perception/vision_perception/pose_classifier.py::classify_pose()
```

輸入：

| 參數 | 意義 |
| --- | --- |
| `body_kps` | COCO 17 點，shape `(17, 2)` |
| `body_scores` | 每個 keypoint visibility / confidence |
| `bbox_ratio` | keypoint bbox width / height |
| `image_height` | frame 高度，用於 fallen ankle-on-floor gate |

輸出：

```python
(pose_name | None, confidence)
```

其中 confidence 是 keypoint 平均分數；真正 publish event 時會改成 vote ratio。

## 2. Classification order

`classify_pose()` 是 first match wins：

```text
1. fallen
2. akimbo
3. standing
4. knee_kneel
5. sitting
6. crouching
7. bending
8. None
```

順序很重要：

- `fallen` 必須最前面，因為是 safety-critical。
- `akimbo` 是 standing 變體，所以要在 `standing` return 前檢查。
- `knee_kneel` 必須在 `sitting/crouching` 前，不然會被吞掉。
- `sitting` 要在 `crouching/bending` 前，因為角度會重疊。

## 3. 7 種姿勢規則

| pose | 主要規則 | 目前狀態 |
| --- | --- | --- |
| `standing` | hip_angle > 155 且 knee_angle > 155 | 較穩 |
| `sitting` | trunk < 35、hip≈knee y 或 knee.y < hip.y、ankle 明顯低於 hip、knee_angle < 145 | 可用，但需要往前傾才容易觸發時要看鏡頭角度 |
| `crouching` | hip_angle < 145、knee_angle < 145、trunk_angle > 10 | 容易和 sitting / knee_kneel 重疊 |
| `bending` | trunk > 30、knee_angle > 130、hip_angle < 160、bbox_ratio <= 1.0 | 可用，但和 fallen 靠 deep-bending guard 分開 |
| `fallen` | trunk > 60、0 <= vertical_ratio < 0.45、torso_visibility >= 0.5、非 deep bending、ankle_on_floor | 安全主線，最需要小心誤判 |
| `akimbo` | standing + 雙肘外撐 + elbow y 在合理高度 + wrist 可見時 elbow angle 60-140 | 實機不穩 |
| `knee_kneel` | 雙膝 y 差、kneel ankle near knee 或 hidden、stand leg 有支撐 | 實機不穩 |

## 4. Fallen gate

Fallen 是四層 gate：

```text
trunk_angle > 60
AND 0 <= vertical_ratio < 0.45
AND torso_visibility >= 0.5
AND not deep_bending
AND ankle_on_floor
```

各 gate 意義：

| gate | 防什麼 |
| --- | --- |
| `trunk_angle > 60` | 身體接近水平 |
| `vertical_ratio < 0.45` | 站著/坐著時 shoulder 到 hip 的垂直差仍大，不該算跌倒 |
| `vertical_ratio >= 0` | 擋 MediaPipe 把 shoulder 標到 hip 下面的垃圾 frame |
| `torso_visibility >= 0.5` | 肩膀/髖部不可靠時不要報 fallen |
| `deep_bending` guard | 彎腰摸地，腿仍朝下，不是跌倒 |
| `ankle_on_floor` | 腳踝要在畫面下半部，避免推車/椅子/半身入鏡誤報 |

目前 N7 放寬：

```text
vertical_ratio: 0.40 -> 0.45
ankle_y / image_height: 0.70 -> 0.60
```

這讓蜷縮跌倒和遠距跌倒比較容易被接住，但也代表誤判風險會比之前高，所以 fallen 的測試不能少。

## 5. 為什麼姿勢是最難的

2D pose 沒有深度語意，很多狀態投影後很像：

| 真實動作 | 2D 看起來像 |
| --- | --- |
| 坐下前傾 | crouching / bending |
| 彎腰摸地 | fallen |
| 單膝跪地 | sitting / crouching |
| 雙手叉腰 | standing，因 wrist 常被遮住 |
| 半身入鏡 | fallen garbage frame |
| 遠距離小人 | keypoint score 低，角度抖 |

所以明天不要只靠單張截圖調參。要看 debug log 裡的：

```text
raw=...
hip=...
knee=...
trunk=...
bbox_r=...
torso_vis=...
arm_vis=...
vote=...
```

## 6. 目前最需要修的 classifier 點

P0：不要動 fallen 主 gate，除非同時跑完整 `test_pose_classifier.py`。

P1：針對「坐下要往前傾才觸發」收現場資料。

要看 sitting 失敗時到底落到哪裡：

```text
raw=None?
raw=standing?
raw=crouching?
trunk_angle 是否 >= 35?
knee_angle 是否 >= 145?
hip≈knee y 是否沒成立?
```

P1：`akimbo` 不要回到 wrist-near-hip 規則。

現有程式已刻意用 elbow-bowed-out，因為 wrist 叉腰時常被身體遮住或漂移。

P1：`knee_kneel` 現場要看 standing-side ankle visibility。

目前 standing-side ankle 是 mandatory，如果鏡頭切掉腳，單膝跪會直接失敗。

## 7. 測試覆蓋

核心測試：

```bash
pytest vision_perception/test/test_pose_classifier.py
pytest vision_perception/test/test_mediapipe_pose_mapping.py
pytest vision_perception/test/test_event_builder.py
```

`test_pose_classifier.py` 已覆蓋：

- standing / sitting / crouching / bending
- fallen / curled fallen / ankle-on-floor
- bending not fallen
- frontal standing not fallen
- low torso visibility not fallen
- akimbo basic / arms dangling
- knee_kneel / ankle hidden

這些測試多數是 synthetic，不等於實機穩定。實機還是要錄 log 看 keypoint 值。

