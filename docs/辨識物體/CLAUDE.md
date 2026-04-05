# 物體辨識 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。

## 現況（2026-04-05）

- `object_perception/` ROS2 package 已建立並在 Jetson 跑穩（commits `37f06c0`, `4c0e026`）
- YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16
- 預設偵測 COCO 80 class 全開，`class_whitelist` 參數可縮減
- 28 tests PASS（WSL + Jetson 雙邊）
- Go/No-Go gate 已通過（Day 9 Phase B）

## 不能做

- **不要在 Jetson 上 `pip install ultralytics`** — 會拉升 torch 2.11+cu130 + numpy 2.2.6，破壞 Jetson 專用 torch wheel（4/4 已踩坑，耗時環境救援）
- 不要改 `COCO_CLASSES` 的 class name 命名規則（COCO 原名空格一律改底線，例 `dining_table` / `cell_phone`）
- 不要改 `/event/object_detected` schema 的欄位名（`stamp` / `event_type` / `objects[]`），contract v2.4 已凍結
- 不要用 PyTorch FasterRCNN 或其他模型（舊方案已棄用）

## 踩過的坑（寫給後人看）

1. **TensorRT provider 參數值必須是字串 `"True"` / `"False"`，不是 `"1"` / `"0"`**
   - 用錯會 silent fallback 到 CPU provider
   - 錯誤訊息：`The value for the key 'trt_fp16_enable' should be 'True' or 'False'`
   - 修復：`{"trt_engine_cache_enable": "True", "trt_fp16_enable": "True"}`

2. **rclpy 的 `declare_parameter("class_whitelist", [])` 無法從空 list 推斷型別**
   - 必須用 `ParameterDescriptor(type=ParameterType.PARAMETER_INTEGER_ARRAY)`
   - 錯誤訊息：`ParameterUninitializedException: The parameter 'class_whitelist' is not initialized`

3. **yaml 裡的 `class_whitelist: []` 會覆蓋 declared default 成「未初始化」**
   - 不要在 yaml 裡寫 `key: []`，改為註解掉讓 declare 的 default 接管
   - 或在 yaml 寫非空 list（例 `[0, 16, 39, 41, 56, 60]`）

4. **bbox 座標必須轉 Python int**
   - ONNX 輸出是 float32，JSON 序列化前要 `int()`，face_perception 踩過 `np.int32` 的坑
   - 使用 `rescale_bbox()` 已處理

5. **Letterbox 逆座標轉換**
   - YOLO 輸出 bbox 在 640x640 letterboxed space
   - 要逆 pad + 逆 scale 回原圖像素座標，`ObjectPerceptionNode.rescale_bbox()` 已實作

## 改之前先看

- `docs/辨識物體/README.md`（模組現況）
- `docs/辨識物體/AGENT.md`（介面契約）
- `object_perception/object_perception/coco_classes.py`（COCO 80 name mapping）
- `docs/architecture/contracts/interaction_contract.md` §4.8（/event/object_detected schema）

## 測試

```bash
# 本地（WSL，不需 Jetson）
python3 -m pytest object_perception/test/ -v
# 預期 28 tests PASS

# Jetson 上
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && \
  source install/setup.zsh && python3 -m pytest object_perception/test/ -v"
```

## 下一步（Day 11+）

- Executive 整合：訂閱 `/event/object_detected` → TTS 回報
- `start_full_demo_tmux.sh` 加 object window
- 整合場景驗收（配合其他感知模組）
