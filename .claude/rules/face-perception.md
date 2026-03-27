---
paths:
  - "face_perception/**"
  - "docs/人臉辨識/**"
  - "docs/modules/face-recognition/**"
---

# face_perception 模組規則

## 現況
- **狀態**：95% 完成，整合測試通過（3/25）
- **主線**：YuNet 2023mar（CPU 71.3 FPS）+ SFace 識別 + IOU 追蹤
- **權威文件**：`docs/人臉辨識/README.md`

## 關鍵檔案
- `face_perception/face_perception/face_identity_node.py`（680 行，核心 node）
- `face_perception/config/face_perception.yaml`（Jetson 路徑、閾值）
- `face_perception/test/test_utilities.py`（13 個 unit tests）

## 開發注意
- 模型路徑預設 `/home/jetson/face_models/`，Jetson 環境依賴
- OpenCV 版本：Jetson 4.5.4，YuNet 2023mar 需要 legacy API
- `to_bbox()` 回傳 `np.int32`，發 JSON 前必須轉 Python `int`
- QoS 已改 BEST_EFFORT（3/23），與其他感知模組對齊
- face_db 目前有 alice、grama 兩人

## 測試
```bash
python3 -m pytest face_perception/test/ -v
colcon build --packages-select face_perception
```

## ROS2 Topics
- `/state/perception/face`（10Hz JSON）
- `/event/face_identity`（觸發式：track_started/identity_stable/track_lost）
- `/face_identity/debug_image`（Image，~6.6 Hz）
