# 手勢辨識 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界

- **所屬 package**：`vision_perception`（vision_perception_node 內的 gesture 部分）
- **上游**：D435 RGB camera
- **下游**：interaction_executive_node

## 輸出 Topic

| Topic | 類型 | 頻率 | Schema |
|-------|------|------|--------|
| `/event/gesture_detected` | String (JSON) | 事件式 | `{"gesture": str, "confidence": float, "hand_label": str, "timestamp": float}` |

## 支援手勢 enum（v2.0 凍結）

`stop` / `thumbs_up` / `thumbs_down` / `ok` / `fist` / `point` / `wave` / `victory` / `i_love_you`

## 依賴

- MediaPipe Gesture Recognizer
- D435 RealSense RGB
- `vision_perception_node` 已啟動

## 事件流

```
D435 RGB → vision_perception_node → gesture_classifier → /event/gesture_detected → executive
```

## 接手確認清單

- [ ] vision node 有在跑？`ros2 node list | grep vision`
- [ ] 對著鏡頭比 stop → `ros2 topic echo /event/gesture_detected`
- [ ] 確認 gesture enum 與 interaction_contract v2.1 一致
