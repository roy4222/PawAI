# 手勢辨識

> Status: current

> MediaPipe Gesture Recognizer 辨識手勢，觸發 Go2 動作。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 整合測試通過 |
| 版本/決策 | MediaPipe Gesture Recognizer (CPU 7.2 FPS) |
| 完成度 | 90% |
| 最後驗證 | 2026-03-25 |
| 入口檔案 | `vision_perception/vision_perception/gesture_classifier.py` |
| 測試 | `python3 -m pytest vision_perception/test/test_gesture_classifier.py -v` |

## 啟動方式

```bash
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  gesture_backend:=recognizer max_hands:=2
```

## 核心流程

```
D435 RGB → vision_perception_node
    ↓
MediaPipe Gesture Recognizer（CPU, 21 手部關鍵點）
    ↓
gesture_classifier.py（靜態：stop/point/fist, 時序：wave）
    ↓
/event/gesture_detected（JSON: gesture, confidence, hand_label）
    ↓
interaction_executive_node → Go2 動作
```

## 支援手勢

| 手勢 | 類型 | Go2 動作 |
|------|------|---------|
| stop | 靜態 | StopMove |
| thumbs_up | 靜態 | Content + TTS |
| ok/fist | 靜態 | Content |
| wave | 時序 | — |
| point | 靜態 | — |

## 操作限制與已知問題

- **有效範圍**：D435 前方約 **3m** 以內
- **僅支援單人操作**：多人同時出現時可能混淆
- point 手勢不穩定（MediaPipe backend）
- 時序分析幀數 buffer 未參數化
- GESTURE_COMPAT_MAP: fist→ok（v2.0 契約相容）
- 快速切換手勢時可能有延遲（投票 buffer 需要穩定幀數）

## Event Schema（v2.0 凍結）

```json
{
  "stamp":       1710000000.123,
  "event_type":  "gesture_detected",
  "gesture":     "wave",
  "confidence":  0.87,
  "hand":        "right"
}
```

## event_action_bridge 手勢→動作映射

| 手勢 | Go2 動作 | TTS | Cooldown |
|------|---------|-----|:--------:|
| `stop` | api_id 1003（緊急停止） | — | **無**（安全優先） |
| `ok` | api_id 1020（回應動作） | — | 3s |
| `thumbs_up` | api_id 1020（回應動作） | "收到！" | 3s |

## 下一步

- Sprint Day 1-3：上機驗證
- Sprint Day 4-5：整合進 executive v0

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs 自定義）、benchmark 比較、社群回饋 |
