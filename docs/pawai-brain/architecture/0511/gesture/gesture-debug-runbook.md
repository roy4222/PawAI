# Gesture Debug Runbook

這份是明天到學校現場排查手勢用的順序。先確認 runtime，再調 threshold。

## 1. 先確認 launch 到底跑哪條 backend

```bash
ros2 param get /vision_perception gesture_backend
ros2 param get /vision_perception inference_backend
ros2 param get /vision_perception gesture_vote_frames
ros2 param get /vision_perception gesture_stable_s
```

判斷：

| 結果 | 意義 |
| --- | --- |
| `gesture_backend=recognizer` | 走 MediaPipe Gesture Recognizer |
| `gesture_backend=mediapipe` | 走 MediaPipe Hands + 規則分類 |
| `gesture_backend=rtmpose` 或其他 | 走 RTMPose wholebody hand kp + 規則分類 |

目前 repo 裡 debug script 實際常用：

```bash
scripts/start_vision_debug_tmux.sh
```

裡面是：

```text
gesture_backend:=mediapipe
pose_backend:=mediapipe
publish_fps:=15
max_hands:=2
```

所以現場看到 `stop` / `point` 不代表壞掉，代表你現在很可能不是 recognizer path。

## 2. 看 event 是否正確出來

```bash
ros2 topic echo /event/gesture_detected
```

期望看到類似：

```json
{
  "event_type": "gesture_detected",
  "gesture": "thumbs_up",
  "confidence": 0.8,
  "hand": "Right"
}
```

檢查重點：

| 現象 | 可能原因 |
| --- | --- |
| 完全沒有 event | camera 沒進 frame、backend 初始化失敗、hand score 太低 |
| 只有 `stop` / `point` | 正在走 legacy classifier path |
| `thumbs_up` 太容易出現 | classifier/recognizer 太敏感，或 vote/stable 太鬆 |
| `wave` 偵測不到 | amplitude 不夠、手腕 keypoint 不穩、frame rate 太低 |
| `ok` 偵測不到 | 拇指食指圓圈太小/太斜、手被遮擋 |

## 3. 確認 Executive 有沒有收到

```bash
ros2 topic echo /event/skill_request
ros2 topic echo /tts
```

測試順序：

1. 比 `palm` 或 legacy `stop`：應該要能觸發暫停路徑。但如果 backend 發 `stop` 而 Executive 只吃 `palm`，就會失效。
2. 比 `wave`：應該走 `wave_hello`，但對話中可能被 conversation gate 壓掉。
3. 比 `thumbs_up`：不應該直接 wiggle，應該先提示 OK 確認。
4. 再比 `ok`：如果 pending 還在，才應該送出 wiggle skill。

如果比 `thumbs_up` 時直接動作，代表不是目前 `interaction_executive` 主線，可能有 legacy bridge 或其他 demo node 在旁邊處理。

## 4. 檢查 Brain 是否能回答手勢

問：

```text
我現在比什麼？
你看到我的手勢嗎？
```

如果 `/event/gesture_detected` 有出現，但 Brain 答不出來，優先看：

```text
pawai_brain/pawai_brain/conversation_graph_node.py
pawai_brain/pawai_brain/world_state_builder.py
```

目前已知 `_GESTURE_ZH` 缺 `palm/fist/index/peace`，所以 canonical gesture 可能沒有被轉成中文上下文。

## 5. Wiggle 誤觸排查

使用者提到手勢容易誤觸，尤其是 wiggle。排查順序：

1. 先看 `/event/gesture_detected` 是否真的一直出 `thumbs_up`。
2. 如果 event 沒有 `thumbs_up`，但仍有 wiggle 提示，查 legacy bridge 或其他 skill source。
3. 如果 event 有 `thumbs_up`，看 `confidence` 是不是低票數，例如 0.6。
4. 如果對話中也會提示 OK，查 `interaction_executive/brain_node.py` 的 conversation gate。

目前互動層風險：

```text
thumbs_up / peace 不在 _CONVERSATION_GATED_GESTURES
```

所以它們即使不直接動作，也會產生 confirm TTS。

## 6. 現場建議參數

如果誤觸多，先提高穩定性：

```bash
ros2 param set /vision_perception gesture_vote_frames 7
ros2 param set /vision_perception gesture_stable_s 0.5
```

如果反應太慢，再退回：

```bash
ros2 param set /vision_perception gesture_vote_frames 5
ros2 param set /vision_perception gesture_stable_s 0.3
```

如果 wave 偵測不到，先不要改 static vote，因為 wave bypass vote。要看 `dynamic_gesture_detector.py` 的 amplitude/window。

## 7. 可跑的測試

```bash
pytest vision_perception/test/test_gesture_classifier.py
pytest vision_perception/test/test_gesture_recognizer_backend.py
pytest vision_perception/test/test_event_builder.py
pytest interaction_executive/test/test_brain_rules.py
```

測試可以保護這幾件事：

| 測試 | 保護內容 |
| --- | --- |
| `test_gesture_classifier.py` | `stop/point/fist` 規則 |
| `test_gesture_recognizer_backend.py` | Recognizer label mapping |
| `test_event_builder.py` | event schema |
| `test_brain_rules.py` | Executive confirm / gate 行為 |

## 8. 明天開發 checklist

- [ ] 確認實機 launch 的 `gesture_backend`。
- [ ] 確認 event 名稱是 canonical 還是 legacy。
- [ ] 決定 alias normalize 放在哪一層。
- [ ] 補 Brain `_GESTURE_ZH` 的 canonical 名稱。
- [ ] 決定 `thumbs_up/peace` 是否要 conversation gate。
- [ ] 確認 `event_action_bridge` 是否會和 Executive 重複發 TTS。

