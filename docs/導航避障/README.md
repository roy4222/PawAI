# 導航避障

> Status: current

> 雙層反應式避障：D435 前方精確防撞 + LiDAR 360° 安全防護。不做 SLAM/Nav2 自主導航。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 桌測通過 + 行走測試通過 |
| 版本/決策 | D435 ROI + LiDAR reactive safety（SLAM/Nav2 永久關閉） |
| 完成度 | 60% |
| 最後驗證 | 2026-04-01 |
| 入口檔案 | `vision_perception/vision_perception/obstacle_avoidance_node.py` |
| 測試 | `python3 -m pytest vision_perception/test/test_obstacle_detector.py -v`（7 tests） |

## 架構決策（2026-04-01 最終判定）

| 路線 | 判定 | 理由 |
|------|:----:|------|
| D435 前方防撞 | **主線** | 30fps, USB 直連, 桌測通過 |
| LiDAR 360° safety | **主線** | 靜止 7.3Hz / 行走 4-6Hz, 無 burst+gap |
| CycloneDDS | **永久關閉** | Go2 Pro 韌體不支援 |
| Full SLAM | **永久關閉** | 5Hz 品質差, 業界最低門檻 7Hz |
| Nav2 global planner | **永久關閉** | controller_freq=3Hz 不實用 |

## 啟動方式

```bash
# D435 避障（需 camera node 先跑）
ros2 launch vision_perception obstacle_avoidance.launch.py

# LiDAR 避障（Go2 driver 自帶）
ros2 launch go2_robot_sdk robot.launch.py enable_lidar:=true decode_lidar:=true
```

## 核心流程

```
                    ┌─── D435 depth (30fps, 前方 87°) ───┐
                    │                                      │
                    ▼                                      │
        obstacle_avoidance_node                            │
        (ROI depth threshold)                              │
                    │                                      │
                    ▼                                      │
        /event/obstacle_detected ──► interaction_executive_node
                                         │
        Go2 LiDAR (5-7Hz, 360°) ────────►│  OBSTACLE_STOP
        /point_cloud2 → /scan            │  → ACTION_DAMP
                                         │  → debounce 2s
                                         │  → 恢復
                                         ▼
                                    Go2 (/webrtc_req)
```

## LiDAR 頻率實測（2026-04-01）

| 條件 | /point_cloud2 Hz | Gap > 1s |
|------|:----------------:|:--------:|
| 靜止 + 純 driver | 7.3 | 0 |
| 靜止 + 16 nodes | 7.3 | 0 |
| 行走 0.3 m/s | 4-6 | 0 |

舊結論（0.03-2Hz burst+gap）已被推翻。詳見 `research/2026-04-01-lidar-frequency-retest.md`。

## D435 避障參數

| 參數 | 預設 | 說明 |
|------|------|------|
| threshold_m | 0.8 | 危險距離（Damp） |
| warning_m | 1.2 | 警告距離（log only） |
| obstacle_ratio_trigger | 0.15 | 15% ROI 像素觸發 |
| debounce_frames | 3 | 連續 3 幀才觸發 |
| roi_top/bottom | 0.4/0.8 | 中央帶狀 ROI |

## 已知問題

- Go2 行走時 Jetson 曾斷電一次（供電波動 / USB 拉扯）
- LiDAR 行走中頻率降 ~35%（7.3→4-6Hz）
- D435 + LiDAR 雙層融合尚未實作（目前各自獨立）
- 上機 10x 防撞測試待做

## 開發路線圖（2026-04-01 確定）

### 優先做（Sprint 剩餘時間）

| # | 功能 | 感測器 | 預估 | 說明 |
|:-:|------|--------|:----:|------|
| 1 | **LiDAR 360° reactive stop** | LiDAR /scan | 1-2hr | 訂閱 /scan，任意方向 < 閾值 → Damp。最實用的主安全功能 |
| 2 | **D435 + LiDAR 雙層安全** | 兩者 | 1hr | LiDAR 全向粗偵測 + D435 前方精細偵測，兩者都發 obstacle event |
| 3 | **受控前進 + 遇障自動停** | 兩者 | 0.5-1hr | 語音「過來」→ 前進 → 遇障自動 Damp。Demo 最有展示性 |
| 4 | **三段速度控制** | D435 | 1hr | 遠（>1.2m）正常走、中（0.8-1.2m）減速、近（<0.8m）停 |

### 可選（視時間）

| # | 功能 | 說明 |
|:-:|------|------|
| 5 | 簡單後退脫困 | 前方停住 → 後方 LiDAR 安全 → 小退一步 |
| 6 | 左右偏向避障 | D435 分左/中/右 ROI，哪邊空就小轉 |
| 7 | 安全圍欄 | 展場邊界距離限制 |
| 8 | 簡單跟隨 | D435 depth 保持前方人距離（複雜度高） |

### 永久不做

- Full SLAM 建圖
- Nav2 全域導航
- 自主到目標點
- 完整繞障路徑規劃

### 待做（基礎）

- Go2 上機 10x 防撞測試（D435）
- `start_full_demo_tmux.sh` 加 obstacle window
- 降級策略測試（Damp-only / 停用）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | D435 避障研究、LiDAR 重測數據、LiDAR 根因分析 |
| archive/ | 舊 LiDAR+Nav2 落地計畫（已永久關閉） |
