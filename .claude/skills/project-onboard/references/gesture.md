# 手勢辨識（vision_perception — gesture backend）

## 這個模組是什麼

Layer 2 感知模組，負責手勢偵測與分類。主線走 MediaPipe Gesture Recognizer（CPU，7.2 FPS），
偵測到手勢後發布 `/event/gesture_detected`，Brain world_state_builder 讀 `current_gesture` 注入對話情境。
3/23 場景驗證通過，v2.0 event schema 凍結。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/gesture/gesture.md` | 主總覽 + 兩種 backend + 0511 freeze 快照 |
| `docs/pawai-brain/architecture/0511/gesture/gesture-runtime-flow.md` | D435 → MediaPipe → gesture event publish 完整 flow |
| `docs/pawai-brain/architecture/0511/gesture/gesture-pipeline-backends.md` | Recognizer vs MediaPipe Hands 兩種 backend 比較 |
| `docs/pawai-brain/architecture/0511/gesture/gesture-executive-brain-integration.md` | event → interaction_router → Brain current_gesture 注入 |
| `docs/pawai-brain/architecture/0511/gesture/gesture-debug-runbook.md` | 手勢識別不穩 / MediaPipe crash / 距離調整 debug checklist |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `vision_perception/vision_perception/vision_perception_node.py` | 主 ROS2 節點（pose + gesture 共用）|
| `vision_perception/vision_perception/gesture/gesture_recognizer.py` | MediaPipe Gesture Recognizer 包裝 |
| `vision_perception/config/vision_perception.yaml` | backend 選擇、mock mode 預設 |
| `vision_perception/launch/vision_perception.launch.py` | 一鍵 launch（含 use_camera、backend 選擇）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/event/gesture_detected` | vision_perception_node → | 手勢事件 JSON v2.0（gesture, confidence, hand, bbox）|
| `/vision_perception/status_image` | vision_perception_node → | 狀態儀表板圖（8Hz，Foxglove 可視化）|

**v2.0 gesture enum**：wave / stop / point / ok / thumbs_up / peace / fist / open_palm  
GESTURE_COMPAT_MAP：fist → ok（合約相容舊 v1.0）

## 已知陷阱

- **手勢距離**：最佳識別距離 1.5-3m，太近（< 0.5m）或太遠（> 4m）識別率急降
- **`wave → hello` 在 3/23 移除**：demo 期 hello 統一由 llm_bridge 處理，不在 event_action_bridge 裡
- **Recognizer backend 每 tick 都跑**（gesture_every_n_ticks 無效）；MediaPipe Hands backend 才有 gesture_every_n_ticks 設定
- **RTMPose GPU 91-99% 滿載**：face+gesture 同跑時，gesture 改走 CPU（MediaPipe）才安全
- **zsh glob 問題**：launch args 陣列參數加引號 `'["whisper_local"]'`（同語音模組）

## 開發入口

```bash
# Gesture Recognizer 模式（推薦）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe gesture_backend:=recognizer max_hands:=2

# Mock 模式（不需相機）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=mock use_camera:=false mock_scenario:=stop

# 驗證
ros2 topic echo /event/gesture_detected

# Build
colcon build --packages-select vision_perception && source install/setup.zsh
```
