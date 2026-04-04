# 導航避障

> Status: **disabled** (Demo 停用，程式碼保留)

> 雙層反應式避障：D435 前方精確防撞 + LiDAR 360° 安全防護。不做 SLAM/Nav2 自主導航。
> **2026-04-03 決定 Demo 停用**，原因見下方「停用決策」。

## 停用決策（2026-04-03）

**結論**：Demo 不啟用導航避障，列為未來改善。

**測試過程**：
- threshold 從 0.8m → 1.2m → 1.5m → 2.0m，3 輪 come_here 防撞測試全部撞上
- **根因**：D435 裝在 Go2 頭上偏上方，低於鏡頭高度的障礙物在遠處看不到，只有 ~0.4m 才進入 FOV
- **延遲鏈**：debounce 100ms + rate limiter 200ms + WebRTC 300ms + Go2 減速 500-1000ms ≈ 1-1.5s
- 硬體鏡頭角度問題，軟體無法克服

**影響**：
- `start_full_demo_tmux.sh` 已移除 d435obs / lidarobs windows
- `enable_lidar:=false`（不解碼 LiDAR）
- Executive 中 come_here 功能暫停
- 20 個 unit tests（D435 7 + LiDAR 13）保留在 CI，程式碼不刪

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Demo 停用**（程式碼 + tests 保留） |
| 版本/決策 | D435 ROI + LiDAR reactive safety（SLAM/Nav2 永久關閉） |
| 完成度 | 實作完成，上機驗證未通過 |
| 最後驗證 | 2026-04-03（停用決策） |
| 入口檔案 | D435: `obstacle_avoidance_node.py` / LiDAR: `lidar_obstacle_node.py` |
| 測試 | D435: 7 tests / LiDAR: 13 tests（共 20 tests） |

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

# LiDAR 避障（需 Go2 driver + LiDAR 先跑）
ros2 run vision_perception lidar_obstacle_node
# 或用 launch file
ros2 launch vision_perception lidar_obstacle.launch.py

# Go2 driver with LiDAR
ros2 launch go2_robot_sdk robot.launch.py enable_lidar:=true decode_lidar:=true

# 全功能 Demo（含雙層避障）
bash scripts/start_full_demo_tmux.sh
```

## 核心流程

```
        D435 depth (30fps, 前方 87°)          Go2 LiDAR (5-7Hz, 360°)
                    │                                    │
                    ▼                                    ▼
        obstacle_avoidance_node              lidar_obstacle_node
        (ROI depth threshold)                (/scan → 360° check)
                    │                                    │
                    │  /event/obstacle_detected           │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    interaction_executive_node
                      │  OBSTACLE_STOP → StopMove(1003)
                      │  debounce 2s → 恢復
                      │
                      │  Safety guard (forward 模式):
                      │  - D435 heartbeat 看門狗（>1s stale → 停）
                      │  - 未收到 heartbeat → 拒絕前進
                      │
                      ▼
                 Go2 (/webrtc_req + /cmd_vel)
```

### Heartbeat Topics
- `/state/obstacle/d435_alive`：D435 obstacle chain 2Hz heartbeat
- `/state/obstacle/lidar_alive`：LiDAR obstacle chain 2Hz heartbeat

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

### 硬體
- Go2 行走時 Jetson 曾斷電一次（供電波動 / USB 拉扯）
- LiDAR 行走中頻率降 ~35%（7.3→4-6Hz）
- **LiDAR 覆蓋率僅 18%**（22/120 有效點）— Go2 voxel 編碼硬體限制，不可修
- LiDAR 定位為「補充感知」，D435 才是前方防撞主力

### 避障邏輯
- `pcl2ls_min_height` 必須設為 -0.7（Go2 LiDAR z=-0.575m）
- **OBSTACLE_STOP 改用 StopMove(1003)**，不用 Damp(1001)（Damp 會讓 Go2 癱軟摔倒）
- **fallen 誤判會擋住 come_here**：pose 把站在鏡頭前的人判為 fallen → EMERGENCY（30s timeout）→ 期間所有 speech intent 被忽略

### WebRTC
- **Jetson 休眠後 WebRTC DataChannel 靜默斷連**：driver 不知道 DC 已斷，持續發 "WebRTC request sent" 但 Go2 不動。修復：重啟 go2 driver window
- **Go2 重開機後 ICE 連線可能 FROZEN→FAILED**：通常第二個 candidate 成功，但需等 10s+

### Foxglove 3D 可視化（2026-04-02 踩坑記錄）
- **URDF parameter 名稱**：foxglove_bridge ROS2 用 `節點名.參數名` 格式，必須寫 `/go2_robot_state_publisher.robot_description`，不是 `/robot_description`
- **TF tree 斷裂**：Go2 tree（odom→base_link）和 D435 tree（camera_link→...）是兩棵獨立樹，需要 `static_transform_publisher base_link camera_link`（啟動腳本 camtf window）
- **QoS whitelist 不能用 `[".*"]`**：會把 `/tf_static`（RELIABLE+TRANSIENT_LOCAL）也強制成 BEST_EFFORT → static TF 收不到。正確值：`["/(point_cloud2|scan|camera/.*/image_raw)"]`
- **LiDAR decayTime**：預設 0（只顯示瞬間）對 2-4Hz LiDAR 太快，必須 ≥3.0
- **Display frame 不會自動套用**：import layout 後必須手動在 3D panel 設 Fixed Frame = `base_link`
- **pointSize 太小看不到**：LiDAR 稀疏點需要 pointSize ≥6，colorMode flat 比 turbo 更適合 debug

### USB 喇叭
- **ALSA device drift**：USB 喇叭 card number 重開機後會飄，用 `plughw:CD002AUDIO,0`（by-name）取代 `plughw:3,0`（by-number）

## 開發路線圖（2026-04-01 確定）

### 已完成（Day 7, 2026-04-01）

| # | 功能 | 狀態 | 說明 |
|:-:|------|:----:|------|
| 1 | **LiDAR 360° reactive stop** | DONE | 13 tests + Jetson 驗證 |
| 2 | **D435 + LiDAR 雙層安全** | DONE | 雙 publisher → executive source-agnostic |
| 3 | **受控前進 + 遇障自動停** | DONE | come_here → cmd_vel 0.3 → obstacle → StopMove |
| — | **Safety guard** | DONE | heartbeat 看門狗 + 三道防線（未收到/stale/state） |
| — | **Foxglove 3D dashboard** | DONE | URDF + LiDAR + D435 depth 可視化 layout |

### 待做

| # | 功能 | 說明 |
|:-:|------|------|
| 4 | **三段速度控制** | 遠正常 / 中減速 / 近停 |

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

- Go2 上機 10x 防撞測試（**1/10 PASS**，剩 9 輪，Go2 沒電中斷）
- 降級策略測試（停用 LiDAR / 停用 D435 / 全停用）
- ~~Foxglove 3D dashboard 實際連線微調~~ ✅（2026-04-02 完成）
- Sensor guard 上機驗證 ✅（2026-04-02 PASS）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | D435 避障研究、LiDAR 重測數據、LiDAR 根因分析 |
| archive/ | 舊 LiDAR+Nav2 落地計畫（已永久關閉） |
