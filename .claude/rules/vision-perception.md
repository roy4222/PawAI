---
paths:
  - "vision_perception/**"
  - "docs/手勢辨識/**"
  - "docs/姿勢辨識/**"
  - "docs/modules/gesture/**"
  - "docs/modules/pose/**"
  - "docs/modules/navigation/**"
---

# vision_perception 模組規則

## 現況
- **手勢**：90% 完成，MediaPipe Gesture Recognizer（CPU 7.2 FPS），stop/thumbs_up/fist
- **姿勢**：92% 完成，MediaPipe Pose（CPU 18.5 FPS），standing/sitting/crouching/fallen/bending
- **整合測試**：3/25 通過，四模組同跑正常
- **權威文件**：`docs/手勢辨識/README.md`、`docs/姿勢辨識/README.md`

## 關鍵檔案
- `vision_perception/vision_perception/vision_perception_node.py`（主 node）
- `vision_perception/vision_perception/gesture_classifier.py`（100 行，靜態手勢）
- `vision_perception/vision_perception/gesture_recognizer_backend.py`（146 行，時序手勢）
- `vision_perception/vision_perception/pose_classifier.py`（114 行，姿勢分類）
- `vision_perception/vision_perception/event_action_bridge.py`（188 行，**Sprint Day 5 後由 executive v0 取代**）
- `vision_perception/vision_perception/interaction_router.py`（265 行，**Sprint Day 5 後由 executive v0 取代**）

## 開發注意
- **setup.py entry_points** 新增 node 後要 `colcon build` + `source install/setup.zsh`
- **Jetson 部署**：executable 裝到 `bin/` 而非 `lib/vision_perception/`，需手動 symlink
- **L3 壓測**：face+pose+gesture 同跑 60s → RAM 1.2GB, temp 52°C, GPU 0%
- **RTMPose** 是備援（GPU 91-99% 滿載），主線用全 MediaPipe CPU-only
- **GESTURE_COMPAT_MAP**：fist → ok（v2.0 契約相容）
- **event_action_bridge 中 wave→hello 已移除**（3/23 demo 退讓）

## 測試
```bash
python3 -m pytest vision_perception/test/ -v
colcon build --packages-select vision_perception
```

## ROS2 Topics
- `/event/gesture_detected`（手勢事件 JSON，v2.0 凍結）
- `/event/pose_detected`（姿勢事件 JSON，v2.0 凍結）
- `/vision_perception/status_image`（Foxglove 狀態圖 8Hz）
- `/event/interaction/welcome`（interaction_router，**Sprint 後 deprecated**）
- `/event/interaction/gesture_command`（**Sprint 後 deprecated**）
- `/event/interaction/fall_alert`（**Sprint 後 deprecated**）
