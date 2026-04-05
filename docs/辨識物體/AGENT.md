# 物體辨識 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界

- **所屬 package**：`object_perception/`
- **核心節點**：`object_perception_node`
- **上游**：D435 RGB camera（`/camera/camera/color/image_raw`）
- **下游**：`interaction_executive_node`（待整合）

## Topic

| Topic | 類型 | 方向 | Schema |
|-------|------|------|--------|
| `/event/object_detected` | `std_msgs/String`（JSON）| pub | `{stamp, event_type, objects: [{class_name, confidence, bbox}]}` |
| `/perception/object/debug_image` | `sensor_msgs/Image`（BGR8）| pub | bbox overlay，~6.5 Hz |
| `/camera/camera/color/image_raw` | `sensor_msgs/Image` | sub | D435 RGB 輸入 |

QoS：event 用 Reliable depth=10，debug_image 用 depth=1（latest only），camera sub 用 BEST_EFFORT depth=1。

## 依賴

- `onnxruntime-gpu 1.23.0`（Jetson AI Lab wheel）
- TensorRT EP + FP16（需要 `trt_cache_dir` 可寫入）
- `cv_bridge`, `opencv-python`, `numpy`
- 模型檔案：`/home/jetson/models/yolo26n.onnx`（9.5MB）
- **不裝 ultralytics**（4/4 踩坑，會破壞 Jetson torch wheel）

## 預設辨識目標（P0 白名單，6 class）

person, dog, bottle, cup, chair, dining_table

模型本身是 COCO 80 class，`P0_CLASSES` dict 在 node 裡過濾。

## 參數（`config/object_perception.yaml`）

| 參數 | 預設 | 說明 |
|------|------|------|
| `model_path` | `/home/jetson/models/yolo26n.onnx` | ONNX 模型路徑 |
| `trt_cache_dir` | `/home/jetson/trt_cache/` | TensorRT engine cache |
| `color_topic` | `/camera/camera/color/image_raw` | D435 RGB |
| `confidence_threshold` | 0.5 | 過濾閾值 |
| `input_size` | 640 | YOLO letterbox 尺寸 |
| `tick_period` | 0.067 | 推理 tick（~15Hz 上限） |
| `publish_fps` | 8.0 | Debug image 發布 rate 上限 |
| `class_cooldown_sec` | 5.0 | Per-class event 去重 cooldown |

## 接手確認清單

- [x] Sprint Day 8 Go/No-Go 結果 — **GO**（4/4 Phase B 15 FPS 穩定）
- [x] 不裝 ultralytics — 改用 ONNX Runtime 直接推理
- [x] Phase C 完成 — ROS2 node 在 Jetson 單獨跑 5 分鐘穩定
- [x] Contract v2.3 登記 — `/event/object_detected` active
- [ ] Executive 整合 — 訂閱 event + state machine 處理
- [ ] `start_full_demo_tmux.sh` 加入 window
- [ ] 整合場景驗收（配合其他感知模組）

## 陷阱備忘

1. **TRT provider 參數**：`trt_engine_cache_enable` / `trt_fp16_enable` 值必須是 `"True"`/`"False"` 字串，不是 `"1"`/`"0"`。用錯會 fallback 到 CPU，錯誤訊息是 `"The value for the key 'trt_fp16_enable' should be 'True' or 'False'"`。
2. **bbox 必須轉 Python int**：ONNX 輸出是 float32，JSON 序列化前要 `int()`，face_perception 踩過 `np.int32` 的坑。
3. **Letterbox 逆座標**：輸出的 bbox 是 640x640 letterboxed space，要逆 pad + 逆 scale 回原圖像素座標。
4. **TRT cache 首次啟動**：3-10 分鐘編譯 engine，node log 會印 warning。後續啟動秒起。
5. **D435 必須先啟動**：node 沒有 camera 會 idle（只等 frame，不 crash）。
