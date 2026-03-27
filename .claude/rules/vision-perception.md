---
paths:
  - "vision_perception/**"
  - "docs/手勢辨識/**"
  - "docs/姿勢辨識/**"
  - "docs/modules/gesture/**"
  - "docs/modules/pose/**"
  - "docs/modules/navigation/**"
---
# vision_perception 規則
詳見 `docs/手勢辨識/CLAUDE.md` + `docs/姿勢辨識/CLAUDE.md`（模組內規則真相來源）
## 快速提醒
- gesture enum v2.0 凍結，不要改；GESTURE_COMPAT_MAP（fist→ok）不要移除
- fallen 判定閾值（bbox_ratio > 1.0 AND trunk_angle > 60°）不要動，除非有完整測試
- 主線全 MediaPipe CPU-only，RTMPose 是備援（GPU 91-99% 滿載）
- Jetson 部署：executable 裝到 `bin/` 而非 `lib/vision_perception/`，需手動 symlink
- 測試：`python3 -m pytest vision_perception/test/ -v`
