# 導航避障

> Status: current

> D435 深度攝影機反應式避障，Go2 行走時的 demo 保命層。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 開發中 |
| 版本/決策 | D435 ROI Depth Threshold v1（LiDAR 正式棄用） |
| 完成度 | 5% |
| 最後驗證 | — |
| 入口檔案 | `vision_perception/vision_perception/obstacle_avoidance_node.py`（待建） |
| 測試 | `python3 -m pytest vision_perception/test/test_obstacle_detector.py -v`（待建） |

## 啟動方式

```bash
# Sprint B-prime Day 6 後可用
ros2 launch vision_perception obstacle_avoidance.launch.py
```

## 核心流程

```
D435 depth stream (/camera/aligned_depth_to_color/image_raw)
    ↓
obstacle_avoidance_node（256x192 ROI, numpy threshold < 0.5m）
    ↓
/event/obstacle_detected（JSON: distance_min, obstacle_ratio）
    ↓
interaction_executive_node（OBSTACLE_STOP state, Go2 Damp）
    ↓
obstacle cleared（debounce 2s）→ 回到前一狀態
```

## 輸入/輸出

| Topic | 方向 | 類型 | 說明 |
|-------|:----:|------|------|
| `/camera/aligned_depth_to_color/image_raw` | 輸入 | Image | D435 深度影像 |
| `/event/obstacle_detected` | 輸出 | String (JSON) | 障礙物事件 |

## 已知問題

- D435 + Go2 導航未實測（Sprint Day 6 才開始）
- 反應式方案無路徑規劃，僅適合小範圍移動
- 與 face_perception RGB pipeline 的資源競爭未評估

## 下一步

- Sprint B-prime Day 6-7（4/2-4/3）：實作 + 30 次防撞測試
- Pass/Warning/Fail metrics 判定
- 降級策略已預定義（全功能 / Damp-only / 停用）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | D435 避障研究、LiDAR 根因分析、開源專案評估 |
| archive/ | 舊 LiDAR+Nav2 落地計畫、過時週計畫 |
