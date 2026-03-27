# 導航避障 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。`.claude/rules/` 中的對應檔案只是薄橋接。

## 不能做

- 不要修改 D435 camera launch 參數（那是 face_perception 的領域）
- 不要引入 Nav2 或 SLAM 依賴（已棄用）
- 不要擴大 ROI 超過 256x192（記憶體預算限制）

## 改之前先看

- `vision_perception/vision_perception/obstacle_detector.py`（核心邏輯）
- `vision_perception/vision_perception/obstacle_avoidance_node.py`（ROS2 包裝）
- `docs/導航避障/README.md`（模組現況）

## 常見陷阱

- D435 depth uint16 單位是 mm，要除以 1000 轉 m
- depth 值 0 或 NaN 是無效讀數，必須過濾
- obstacle_cleared debounce 2s + min duration 1s，防止 stop/recover 抖動

## 驗證指令

```bash
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
colcon build --packages-select vision_perception
```
