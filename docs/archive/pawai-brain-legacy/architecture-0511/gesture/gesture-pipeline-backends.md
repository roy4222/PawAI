# Gesture Pipeline and Backends

這份文件深挖 `vision_perception_node.py` 內部手勢 pipeline。重點是「每個 backend 真的會輸出什麼」，以及為什麼 wiggle 容易被誤觸。

## 1. Backend 選擇邏輯

入口在：

```text
vision_perception/vision_perception/vision_perception_node.py
```

核心參數：

| 參數 | 用途 |
| --- | --- |
| `gesture_backend` | `recognizer` / `mediapipe` / 其他值走 RTMPose wholebody |
| `gesture_vote_frames` | 靜態手勢多數投票窗口，config 目前為 5 |
| `gesture_stable_s` | 穩定時間門檻，config 目前為 0.3 秒 |
| `gesture_min_score` | hand keypoint 最低分數 |
| `max_hands` | 最多偵測幾隻手 |
| `gesture_every_n_ticks` | MediaPipe Hands path 降頻用 |
| `gesture_recognizer_model` | `.task` model 路徑 |

邏輯概念：

```text
if gesture_backend == "mediapipe":
    使用 MediaPipeHands + gesture_classifier.py
elif gesture_backend == "recognizer":
    使用 GestureRecognizerBackend
else:
    使用 RTMPose wholebody hand keypoints + gesture_classifier.py
```

## 2. Recognizer path

檔案：

```text
vision_perception/vision_perception/gesture_recognizer_backend.py
```

這條使用 MediaPipe Gesture Recognizer Task API。模型不存在時會嘗試下載：

```text
https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task
```

Jetson 現場如果沒有網路，必須事先把 model 放好，否則 recognizer path 可能初始化失敗。

內建 label mapping：

| MediaPipe label | PawAI gesture |
| --- | --- |
| `Open_Palm` | `palm` |
| `Closed_Fist` | `fist` |
| `Pointing_Up` | `index` |
| `Thumb_Up` | `thumbs_up` |
| `Victory` | `peace` |
| `Thumb_Down` | 丟棄 |
| `ILoveYou` | 丟棄 |
| `Unknown` | 丟棄 |

Recognizer path 的優點是 canonical 名稱比較乾淨，缺點是依賴 `.task` model，而且和目前 debug script 的 `mediapipe` 設定不一致。

## 3. MediaPipe Hands / RTMPose classifier path

檔案：

```text
vision_perception/vision_perception/gesture_classifier.py
```

這條不靠模型分類器，而是靠 21 個手部 keypoints 做幾何規則。

目前 `STATIC_GESTURES` 是 legacy naming：

```text
("stop", "point", "fist")
```

規則大意：

| gesture | 判斷方式 |
| --- | --- |
| `stop` | 4 根以上手指外伸 |
| `point` | 食指外伸，中指/無名指/小指至少 2 根彎曲 |
| `fist` | 3 根以上彎曲，且沒有明顯外伸 |

這是「手掌/食指/握拳」的早期版本，所以它不會自然輸出 `palm`、`index`、`peace`。如果 Executive 只吃 canonical 名稱，這條 path 會有對不上問題。

## 4. OK override

OK 不是 Recognizer label mapping 的主體，而是在 `vision_perception_node.py` 裡透過幾何 override 判斷：

```text
detect_ok_circle(hand, image_shape)
```

檔案：

```text
vision_perception/vision_perception/gesture_classifier.py
```

判斷重點：

- 拇指 tip 與食指 tip 距離要小於 hand width 的 0.30。
- 如果中指、無名指、小指全部都彎曲，會拒絕，避免把握拳誤判成 OK。

OK 的定位是「二次確認」，不是一般互動手勢。Executive 收到 OK 後會確認 pending skill。

## 5. Wave dynamic path

檔案：

```text
vision_perception/vision_perception/dynamic_gesture_detector.py
```

目前只有 Wave 真的實作。ComeHere / Circle 不在目前 pipeline 內。

`WaveDetector` 主要條件：

| 條件 | 目前值 |
| --- | --- |
| window | 1.5 秒 |
| min reversals | 2 |
| min amplitude | 50 px |
| min samples | 6 |

在 `vision_perception_node.py` 裡，wave 是 bypass path：

```text
偵測到 wrist 左右擺動
    -> 直接 publish gesture="wave"
    -> cooldown 2.5 秒
    -> 不進 static vote
```

所以 wave 的穩定度主要不是 vote frames，而是 motion detector 的 window / amplitude / cooldown。

## 6. Vote and stable gate

靜態手勢會先進 `gesture_buffer`，再做多數投票：

```text
raw gesture -> buffer -> majority vote -> stable_s gate -> publish event
```

目前 config：

```yaml
gesture_vote_frames: 5
gesture_stable_s: 0.3
```

event 的 `confidence` 是 vote ratio。例如 5 frames 裡 4 個是 `thumbs_up`，confidence 就接近 0.8。它不是模型原始信心值。

## 7. 目前最需要收斂的命名

建議明天先決定一個 canonical 表，否則 Brain / Executive / docs 會繼續分裂。

建議 canonical：

| canonical | legacy alias | 意義 |
| --- | --- | --- |
| `palm` | `stop` | 全面暫停 |
| `fist` | 無 | 靜音模式 |
| `index` | `point` | 監聽模式 |
| `ok` | 無 | 二次確認 |
| `thumbs_up` | `thumb` | wiggle 候選 |
| `peace` | `victory` | stretch 候選 |
| `wave` | 無 | 打招呼 |

最小修法是讓 event builder 或 vision node 在 publish 前統一 alias，而不是讓每個 consumer 自己猜。

