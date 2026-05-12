# 物體辨識（object_perception）

## 這個模組是什麼

Layer 2 感知模組，負責場景物體偵測（YOLO26n ONNX，COCO 80 class + HSV 顏色標記）。
偵測結果注入 Brain world_state_builder 的 `recent_objects`（30s 視窗快取），讓 AI 能回答「你看到了什麼」類型的問題。
顏色辨識（HSV）在 5/5 Sprint B4-4 加入，color_confidence < 0.6 丟棄 color label。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/object/object.md` | 主總覽 + YOLO26n 選型 + 0511 freeze 快照 |
| `docs/pawai-brain/architecture/0511/object/object-runtime-flow.md` | D435 → YOLO ONNX + TRT → NMS → HSV → event publish 完整 flow |
| `docs/pawai-brain/architecture/0511/object/object-color-and-detection.md` | HSV 顏色標記算法 + class_whitelist 設定 + COCO id 對照 |
| `docs/pawai-brain/architecture/0511/object/object-brain-executive-integration.md` | world_snapshot object cache + Brain N3-A + scene_query 整合 |
| `docs/pawai-brain/architecture/0511/object/object-debug-runbook.md` | YOLO 載入失敗 / TRT cache 首次耗時 / color 標記不準 debug |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `object_perception/object_perception/object_perception_node.py` | 主 ROS2 節點（YOLO ONNX + TRT EP + HSV）|
| `object_perception/config/object_perception.yaml` | class_whitelist、模型路徑、TRT cache 路徑 |
| `object_perception/launch/object_perception.launch.py` | 一鍵 launch |
| `docs/pawai-brain/perception/object/CLAUDE.md` | 已知陷阱詳細版（TRT 字串、pip 禁令等）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/event/object_detected` | object_perception_node → | 偵測事件 JSON（objects[]，含 class_name, confidence, bbox, color?）|
| `/perception/object/debug_image` | object_perception_node → | 可視化 debug image（~6-8 Hz，Foxglove）|

**Brain N3-A object cache 邏輯**（`pawai_brain/capability/world_snapshot.py`）：
- 每 class 保留最新一筆（latest-wins）
- `person` 排除（face_identity 擁有人）
- color_confidence < 0.6 → 丟棄 color
- deque maxlen=8，`get_recent_objects(window_s=30)` 過濾並計算 age_s

## 已知陷阱

- **禁止 `pip install ultralytics`**：會破壞 Jetson torch wheel（見 `docs/pawai-brain/perception/object/CLAUDE.md`）
- **TRT provider 參數值必須是字串** `"True"` / `"False"`，不是 `"1"` / `"0"`
- **class_whitelist 空 list**：yaml 不要寫 `: []`，需用 `ParameterDescriptor(INTEGER_ARRAY)`
- **模型路徑**：`/home/jetson/models/yolo26n.onnx`（9.5MB，output `(1,300,6)` NMS-free）
- **TRT cache**：`/home/jetson/trt_cache/`，首次啟動 TensorRT 編譯 3-10 分鐘，之後復用

## 開發入口

```bash
# 前提：D435 camera 已啟動
ros2 launch realsense2_camera rs_launch.py enable_depth:=false pointcloud.enable:=false

# 啟動物體辨識（COCO 80 class 全開）
ros2 launch object_perception object_perception.launch.py

# 縮減為原 P0 6 類（person/dog/bottle/cup/chair/dining_table）
ros2 launch object_perception object_perception.launch.py \
  class_whitelist:='[0, 16, 39, 41, 56, 60]'

# 驗證
ros2 topic hz /perception/object/debug_image        # ~6-8 Hz
ros2 topic echo /event/object_detected --once       # JSON event

# Build
colcon build --packages-select object_perception && source install/setup.zsh
```
