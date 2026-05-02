---
paths:
  - "face_perception/**"
  - "docs/pawai-brain/perception/face/**"
  - "docs/modules/face-recognition/**"
---
# face_perception 規則
詳見 `docs/pawai-brain/perception/face/CLAUDE.md`（模組內規則真相來源）
## 快速提醒
- `to_bbox()` 回傳 `np.int32`，發 JSON 前必須轉 Python `int`
- QoS 用 BEST_EFFORT（3/23 對齊），不要改回 RELIABLE
- 模型路徑預設 `/home/jetson/face_models/`，Jetson 環境依賴
- OpenCV YuNet 2023mar 用 legacy API，不要升級到新版 API
- 測試：`python3 -m pytest face_perception/test/ -v`
