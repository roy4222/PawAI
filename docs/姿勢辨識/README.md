# 姿勢辨識

> Status: current

> MediaPipe Pose 辨識人體姿勢，跌倒偵測觸發緊急警報。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 整合測試通過 |
| 版本/決策 | MediaPipe Pose (CPU 18.5 FPS) |
| 完成度 | 92% |
| 最後驗證 | 2026-03-25 |
| 入口檔案 | `vision_perception/vision_perception/pose_classifier.py` |
| 測試 | `python3 -m pytest vision_perception/test/test_pose_classifier.py -v` |

## 啟動方式

```bash
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe
```

## 核心流程

```
D435 RGB → vision_perception_node
    ↓
MediaPipe Pose（CPU, COCO 17-point）
    ↓
pose_classifier.py（hip/knee/trunk 角度判定）
    ↓
/event/pose_detected（JSON: pose, confidence）
    ↓
interaction_executive_node → fallen = EMERGENCY
```

## 支援姿勢

| 姿勢 | 判定邏輯 |
|------|---------|
| standing | hip_angle > 155° |
| sitting | 100° < hip < 150°, trunk < 35° |
| crouching | hip < 145°, knee < 145°, trunk > 10° |
| fallen | bbox_ratio > 1.0 AND trunk > 60° |
| bending | trunk > 35°, hip < 140°, knee > 130° |

## 操作限制與已知問題

- **有效範圍**：D435 前方約 **4-5m** 以內
- **僅支援單人追蹤**：多人時 MediaPipe 只追蹤一人
- RTMPose balanced mode GPU 91-99%（備援方案，主線用 MediaPipe CPU 0%）
- 跌倒偵測可能誤報（椅子上趴下）
- 幽靈跌倒偵測：投票 buffer（20 幀多數決）已大幅降低誤報，但未完全消除
- 側面坐姿 hip_angle 和 trunk_angle 計算偏差，Demo 時建議正面面向攝影機

## Event Schema（v2.0 凍結）

```json
{
  "stamp":       1710000000.123,
  "event_type":  "pose_detected",
  "pose":        "standing",
  "confidence":  0.92,
  "track_id":    1
}
```

## event_action_bridge 姿勢→動作映射

| 姿勢 | Go2 動作 | TTS | Cooldown |
|------|---------|-----|:--------:|
| `fallen` | — | "偵測到跌倒！請注意安全" | 10s |

> 其他姿勢目前不觸發 Go2 動作，僅更新前端狀態。

## 下一步

- Sprint Day 1-3：上機驗證
- Sprint Day 4-5：fallen → EMERGENCY 整合進 executive v0

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs DWPose）、benchmark 比較、跌倒偵測研究 |
