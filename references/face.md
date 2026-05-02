# 人臉辨識 Reference

## 定位

YuNet 偵測 + SFace 識別 + IOU 追蹤。D435 RGB+Depth → 人臉框+身份+距離。

## 權威文件

- **人臉辨識設計**：`docs/pawai-brain/perception/face/README.md`
- **ROS2 介面契約**：`docs/contracts/interaction_contract.md` (face topics)
- **Benchmark 研究**：`docs/pawai-brain/perception/face/research/2026-03-21-benchmark-decision.md`
- **Benchmark 候選**：`benchmarks/configs/face_candidates.yaml`

## 核心程式

| 檔案 | 用途 |
|------|------|
| `face_perception/face_perception/face_identity_node.py` | ROS2 node：偵測+辨識+追蹤+event/state 發布 |
| `face_perception/config/face_perception.yaml` | 參數（Jetson 模型路徑、閾值） |
| `face_perception/launch/face_perception.launch.py` | Launch 檔 |
| `scripts/start_face_identity_tmux.sh` | 一鍵啟動（D435 + face_identity_node + foxglove_bridge） |
| `scripts/clean_face_env.sh` | 環境清理 |

## 關鍵 Topics

- `/state/perception/face` — 人臉追蹤狀態 JSON（10 Hz）
- `/event/face_identity` — 身份事件（track_started / identity_stable / identity_changed / track_lost）
- `/face_identity/debug_image` — Debug 影像帶框（~6.6 Hz）

## 模型

- **YuNet**：`face_detection_yunet_legacy.onnx`（Jetson OpenCV 4.5.4 用 legacy 版）
- **SFace**：`face_recognition_sface_2021dec.onnx`
- 模型路徑：`/home/jetson/face_models/`
- Benchmark 結果：YuNet 2023mar 71.3 FPS（CPU），主線選型

## 已知陷阱

- **QoS 不匹配**：3/23 已修為 BEST_EFFORT（對齊 D435 driver），待上機驗證
- **int32 序列化 bug**：`to_bbox()` 回傳 np.int32 → json.dumps 不認 → 已轉 Python int
- **Jetson OpenCV 4.5.4**：2023mar YuNet 有相容性問題，改用 legacy 版本
- face_db 目前有 alice, grama 兩人

## 測試

- `face_perception/test/test_utilities.py` — 工具函式單元測試
- Jetson smoke：D435 + state/event/debug_image 全通（3/18）
