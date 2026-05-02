# 導航避障 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界

- **所屬 package**：`vision_perception`（obstacle_avoidance_node）
- **上游**：D435 depth camera
- **下游**：interaction_executive_node

## 輸出 Topic

| Topic | 類型 | 頻率 | Schema |
|-------|------|------|--------|
| `/event/obstacle_detected` | String (JSON) | 事件式（5Hz max） | `{"distance_min": float, "obstacle_ratio": float, "timestamp": float}` |

## 輸入 Topic

| Topic | 來源 | 說明 |
|-------|------|------|
| `/camera/aligned_depth_to_color/image_raw` | D435 RealSense | depth 影像（uint16 mm 或 float32 m） |

## 依賴

- `sensor_msgs`（Image）
- `cv_bridge`
- `numpy`
- D435 RealSense 硬體 + realsense2_camera_node 已啟動

## 事件流

```
D435 depth → obstacle_avoidance_node → /event/obstacle_detected → executive → Go2 Damp
```

## 接手確認清單

- [ ] D435 depth stream 有在發布？`ros2 topic hz /camera/aligned_depth_to_color/image_raw`
- [ ] obstacle node 有在跑？`ros2 node list | grep obstacle`
- [ ] 測試障礙物 < 0.5m 是否觸發事件：`ros2 topic echo /event/obstacle_detected`
