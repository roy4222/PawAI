# 姿勢辨識（vision_perception — pose backend）

## 這個模組是什麼

Layer 2 感知模組，負責人體姿勢分類（standing / sitting / crouching / fallen）。
主線走 MediaPipe Pose（CPU，18.5 FPS），偵測到關鍵姿勢後發布 `/event/pose_detected`。
fallen（跌倒）是守護輔助（30%）的關鍵觸發，Brain world_state_builder 讀 `current_pose` 注入對話情境（stale 10s）。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/pose/pose.md` | 主總覽 + 分類規則 + 0511 freeze 快照 |
| `docs/pawai-brain/architecture/0511/pose/pose-runtime-flow.md` | D435 → MediaPipe → pose classifier → event publish 完整 flow |
| `docs/pawai-brain/architecture/0511/pose/pose-classifier-rules.md` | trunk_angle / vertical_ratio / ankle 分類規則（5/11 調過）|
| `docs/pawai-brain/architecture/0511/pose/pose-executive-brain-integration.md` | pose event → interaction_router → fall_alert + Brain 注入 |
| `docs/pawai-brain/architecture/0511/pose/pose-debug-runbook.md` | 姿勢誤判 / fallen 誤觸發 / MediaPipe 跑不動 debug checklist |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `vision_perception/vision_perception/vision_perception_node.py` | 主 ROS2 節點（pose + gesture 共用）|
| `vision_perception/vision_perception/pose/pose_classifier.py` | 姿勢分類規則（trunk_angle + vertical_ratio + ankle 面積）|
| `vision_perception/config/vision_perception.yaml` | backend 設定、fallen 閾值 |
| `vision_perception/launch/vision_perception.launch.py` | 一鍵 launch |
| `vision_perception/launch/interaction_router.launch.py` | 高層事件路由（訂閱 face+gesture+pose → 互動事件）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/event/pose_detected` | vision_perception_node → | 姿勢事件 JSON v2.0（pose, confidence, track_id, bbox）|
| `/event/interaction/fall_alert` | interaction_router → | 跌倒警報（interaction_router 聚合後發）|
| `/vision_perception/status_image` | vision_perception_node → | 狀態儀表板圖（8Hz）|

**v2.0 pose enum**：standing / sitting / crouching / fallen / unknown

## 已知陷阱

- **fallen 閾值 5/11 已調整**：trunk_angle 60°（守住），vertical_ratio + ankle 有放寬（見 `pose-classifier-rules.md`）。舊 rules 文件（`docs/archive/` 下）可能有衝突，以 0511 版為準
- **Vision rule 例外**：`/home/roy422/newLife/elder_and_dog/.claude/rules/vision-perception.md` 有「fallen 閾值不要動」舊規則 — 5/11 user 明示已例外覆寫（`docs/runbook/demo-frozen-backlog.md` §Vision rule 例外）
- **fallen cooldown 10s**：event_action_bridge 中 fallen 的 cooldown 是 10s（一般動作是 3s），防止誤觸發連發
- **RTMPose balanced mode GPU 91-99% 滿載**：pose + face 同跑考慮改 pose_backend:=mediapipe 走 CPU
- **L3 三感知壓測**（3/23）：face(CPU)+pose(CPU)+gesture(CPU) 同跑 60s → RAM 1.2GB, temp 52°C，GPU 0%，安全

## 開發入口

```bash
# 主線（MediaPipe Pose，CPU）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe gesture_backend:=recognizer

# 互動路由（聚合 face+gesture+pose → welcome/gesture_cmd/fall_alert）
ros2 launch vision_perception interaction_router.launch.py

# Mock 模式
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=mock use_camera:=false mock_scenario:=stop

# 驗證
ros2 topic echo /event/pose_detected
ros2 topic echo /event/interaction/fall_alert

# Build
colcon build --packages-select vision_perception && source install/setup.zsh
```
