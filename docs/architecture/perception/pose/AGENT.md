# 姿勢辨識 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界

- **所屬 package**：`vision_perception`（vision_perception_node 內的 pose 部分）
- **上游**：D435 RGB camera
- **下游**：interaction_executive_node

## 輸出 Topic

| Topic | 類型 | 頻率 | Schema |
|-------|------|------|--------|
| `/event/pose_detected` | String (JSON) | 事件式 | `{"pose": str, "confidence": float, "keypoints": [...], "timestamp": float}` |

## 支援姿勢 enum

`standing` / `sitting` / `crouching` / `fallen` / `bending`

## 關鍵：跌倒偵測

`fallen` 事件觸發 executive 進入 EMERGENCY 狀態。判定邏輯：
- `bbox_ratio > 1.0`（人橫躺）AND `trunk_angle > 60°`

## 依賴

- MediaPipe Pose（CPU 18.5 FPS）
- D435 RealSense RGB
- `vision_perception_node` 已啟動

## 事件流

```
D435 RGB → vision_perception_node → pose_classifier → /event/pose_detected → executive
fallen → EMERGENCY → TTS "你還好嗎"
```

## 接手確認清單

- [ ] vision node 有在跑？
- [ ] 站著/坐著 → `ros2 topic echo /event/pose_detected` 看到 standing/sitting？
- [ ] 確認 fallen 判定邏輯在 pose_classifier.py
