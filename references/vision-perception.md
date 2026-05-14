# 手勢+姿勢辨識 Reference

## 定位

手勢辨識（wave/stop/point/fist）+ 姿勢辨識（standing/sitting/crouching/fallen）。
共用 vision_perception 套件，Phase 1 完成，23 unit tests pass。

## 權威文件

- **手勢辨識設計**：`docs/pawai-brain/perception/gesture/README.md`
- **姿勢辨識設計**：`docs/pawai-brain/perception/pose/README.md`
- **ROS2 介面契約**：`docs/contracts/interaction_contract.md` (gesture/pose topics)
- **視覺系統研究**：memory `project_vision_research_0322.md`

## 核心程式

| 檔案 | 用途 |
|------|------|
| `vision_perception/vision_perception/vision_perception_node.py` | 主 node：camera → 推理 → event 發布 |
| `vision_perception/vision_perception/event_action_bridge.py` | gesture/pose → Go2 動作 + TTS |
| `vision_perception/vision_perception/interaction_router.py` | 高層路由：face+gesture+pose → welcome/gesture_cmd/fall_alert |
| `vision_perception/vision_perception/vision_status_display.py` | Foxglove 狀態儀表板圖 |
| `vision_perception/config/vision_perception.yaml` | 參數（mock mode 預設） |
| `vision_perception/launch/vision_perception.launch.py` | Launch 檔（含 use_camera 開關） |

## 關鍵 Topics

- `/event/gesture_detected` — 手勢事件 JSON（v2.0 凍結）
- `/event/pose_detected` — 姿勢事件 JSON（v2.0 凍結）
- `/vision_perception/status_image` — Foxglove 狀態圖（8 Hz）
- `/event/interaction/welcome` | `/event/interaction/gesture_command` | `/event/interaction/fall_alert`

## 啟動方式

```bash
# Gesture Recognizer 模式（推薦，3/23 驗證通過）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe gesture_backend:=recognizer max_hands:=2

# Mock mode（不需相機）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=mock use_camera:=false mock_scenario:=stop

# 壓力測試（face+vision+camera 同跑）
bash scripts/start_stress_test_tmux.sh 60
```

## Benchmark 結果

| Task | 主線 | FPS | 備援 |
|------|------|:---:|------|
| pose | MediaPipe Pose | 18.5 (CPU) | RTMPose lightweight |
| gesture | Gesture Recognizer | 7.2 (CPU) | MediaPipe Hands |

L3 壓測：face(CPU)+pose(CPU)+gesture(CPU) 同跑 60s → RAM 1.2GB, temp 52°C, GPU 0%

## 已知陷阱

- **event_action_bridge**：3/23 移除 wave→hello（demo 退讓），hello 統一由 llm_bridge 處理
- **GESTURE_COMPAT_MAP**：fist → ok（v2.0 契約相容，待 3/25 正式切換）
- **RTMPose balanced mode**：GPU 91-99% 滿載，~3.8 Hz debug_image
- **Jetson 部署**：executable 裝到 `bin/` 而非 `lib/vision_perception/`，需手動 symlink

## 測試

- `vision_perception/test/test_gesture_classifier.py`
- `vision_perception/test/test_gesture_recognizer_backend.py`
- `vision_perception/test/test_pose_classifier.py`
- `vision_perception/test/test_event_builder.py`
- `vision_perception/test/test_interaction_rules.py`
- `vision_perception/test/test_mediapipe_pose_mapping.py`
