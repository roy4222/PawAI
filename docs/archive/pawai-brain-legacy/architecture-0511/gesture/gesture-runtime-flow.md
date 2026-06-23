# Gesture Runtime Flow

這份文件只看手勢辨識在系統裡的 runtime 位置：相機進來、哪個 node 處理、發什麼 topic、誰消費事件。

## 1. 系統位置

手勢辨識住在 `vision_perception`，不是 `pawai_brain` 本體。它和 pose 共用 `VisionPerceptionNode`，再把辨識結果送到 Brain / Executive。

主要檔案：

| 角色 | 檔案 |
| --- | --- |
| perception orchestrator | `vision_perception/vision_perception/vision_perception_node.py` |
| MediaPipe Gesture Recognizer backend | `vision_perception/vision_perception/gesture_recognizer_backend.py` |
| MediaPipe Hands / RTMPose 靜態規則分類 | `vision_perception/vision_perception/gesture_classifier.py` |
| Wave 動態偵測 | `vision_perception/vision_perception/dynamic_gesture_detector.py` |
| gesture event schema | `vision_perception/vision_perception/event_builder.py` |
| runtime config | `vision_perception/config/vision_perception.yaml` |
| launch defaults | `vision_perception/launch/vision_perception.launch.py` |
| executive consumer | `interaction_executive/interaction_executive/brain_node.py` |
| brain context consumer | `pawai_brain/pawai_brain/conversation_graph_node.py` |

## 2. Runtime 架構圖

```text
D435 RGB
  /camera/camera/color/image_raw
        |
        v
vision_perception_node.py
  - 讀 image frame
  - 根據 gesture_backend 選 backend
  - static gesture: vote + stable gate
  - wave gesture: motion detector bypass
        |
        v
/event/gesture_detected
  std_msgs/String JSON:
  {
    "event_type": "gesture_detected",
    "gesture": "thumbs_up",
    "confidence": 0.8,
    "hand": "Right",
    "stamp": ...
  }
        |
        +----------------------+
        |                      |
        v                      v
interaction_executive       pawai_brain
brain_node.py               conversation_graph_node.py
  - palm pause                 - cache recent gesture
  - wave hello                 - world_state for LLM
  - thumbs_up -> confirm       - answer "我在做什麼"
  - ok -> confirm
```

## 3. Topic 與事件

手勢辨識對外只有一個主要事件：

```text
/event/gesture_detected
```

event 由 `build_gesture_event()` 建立，位於：

```text
vision_perception/vision_perception/event_builder.py
```

目前 schema 重要欄位：

| 欄位 | 意義 |
| --- | --- |
| `event_type` | 固定為 `gesture_detected` |
| `gesture` | canonical gesture 名稱，例如 `palm`、`thumbs_up`、`wave` |
| `confidence` | 多數投票比例，不一定是模型原始 confidence |
| `hand` | `Left` / `Right`，可能為空 |
| `stamp` | event builder 產生的時間 |

注意：`event_builder.py` 裡的 `GESTURE_COMPAT_MAP = {}` 是空的，所以現在不會自動把 `stop` 轉成 `palm`，也不會把 `point` 轉成 `index`。上游 backend 輸出什麼，event 大多就送什麼。

## 4. 目前 backend 現況

文件舊版寫「Recognizer 是主線」，但本地 launch/config 現況需要明天實機確認：

| 來源 | 目前值 |
| --- | --- |
| `vision_perception/config/vision_perception.yaml` | `gesture_backend: "rtmpose"` |
| `vision_perception/launch/vision_perception.launch.py` | launch arg default `gesture_backend="rtmpose"` |
| `scripts/start_vision_debug_tmux.sh` | 實際 debug 用 `gesture_backend:=mediapipe` |
| `scripts/start_stress_test_tmux.sh` | stress test 用 `gesture_backend:=mediapipe` |
| `gesture_recognizer_backend.py` | 已實作 Recognizer，但需要 `.task` model |

所以現在要把「文件認知」改成比較準確的說法：

```text
設計上：Recognizer 是理想主線。
目前 repo 預設：rtmpose。
目前 debug script：mediapipe。
目前真正上機使用哪條：看 launch 指令，不要只看文件。
```

這個落差會直接影響手勢名稱：

| backend | 可能輸出 |
| --- | --- |
| Recognizer | `palm`, `fist`, `index`, `thumbs_up`, `peace` |
| MediaPipe Hands + classifier | `stop`, `point`, `fist`，加上 OK override |
| RTMPose + classifier | 同樣走規則分類，但手部點穩定性較差 |

## 5. 明天第一個要檢查的點

明天到學校不要先調 threshold，先確認實際跑哪條 backend：

```bash
ros2 param get /vision_perception gesture_backend
ros2 param get /vision_perception inference_backend
ros2 topic echo /event/gesture_detected
```

如果 event 裡看到：

- `palm` / `index` / `peace`：比較像 Recognizer canonical path。
- `stop` / `point`：比較像 legacy classifier path。
- 只有 `fist` 偶爾出現、其他不穩：可能是 RTMPose hand kp 不適合手勢。

## 6. 開發判斷

目前手勢不是「完全沒做」，而是已經有完整 pipeline，但有三個主要風險：

1. **backend 設定不一致**：文件、config、debug script 不同步。
2. **gesture 命名不一致**：`palm/index/peace` 和 `stop/point/victory` 混在不同層。
3. **Executive policy 不夠保守**：`thumbs_up` / `peace` 進 confirm path，不受 conversation gate 保護，容易造成 wiggle/stretch 誤觸提示。

