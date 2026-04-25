# 導航避障

> Status: **Gate P0-A 通 / Gate P0-B 卡 odom source（rf2o 整合中）**（2026-04-25 更新）

> **2026-04-24 LiDAR 到貨並驗證通過**：Jetson 上 /scan 10.57Hz / 1800 點/圈 / 60% valid。
> **2026-04-25 上 Go2 機身**：/scan 10.40Hz 同等品質，但 SLAM 建圖卡 odom source。
>   詳見整合紀錄 [`research/2026-04-25-rplidar-a2m12-integration-log.md`](research/2026-04-25-rplidar-a2m12-integration-log.md)
> P0 設計定稿為「劇本式 A→B + 停障 + 續行」，不承諾一般動態繞障。
> **Spec**: [`docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`](../superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md)
> **Plan**: [`docs/superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md`](../superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md)
> **硬時程**：5/1 emergency hotkey 硬截止、5/6 家中 KPI 4/5、5/11-5/12 freeze、5/13 學校現場重建地圖

> D435 方案因鏡頭角度限制上機全失敗（4/3 停用），**由外接 LiDAR 360° 取代**。原 D435 避障 code 保留作歷史參考。
> 詳見 [外接 LiDAR 可行性研究](research/2026-04-08-external-lidar-feasibility.md)

## 外接 LiDAR 方案（4/8 新增）

**候選**：Slamtec RPLIDAR A2M12（$7,530，12m，16000 次/秒，360°）
**技術評估**：RAM 安全（+0.85-1.15 GB，總計 ~4.7/8 GB），CPU 是唯一風險點
**時程**：4/9 老師確認學校有無舊 LiDAR → 4/14 定案 → 到貨後 5 天整合
**目標**：直線短距移動 + 基礎避障（不做複雜路徑規劃）

## D435 方案停用決策（2026-04-03）

**結論**：D435 避障 Demo 不啟用，程式碼保留作為基礎。

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
| 狀態 | **P0-A ✅ / P0-B ✅ / P0-C ✅（AMCL stack active, initial pose 流程明日固化）/ P0-D 🟡 WIP（Nav2 stack alive，卡 costmap/inflation）** |
| 版本/決策 | D435 停用(4/3) → 外接 RPLIDAR A2M12 採購(4/14) → 到貨驗證(4/24) → P0 spec+plan 定稿(4/24) → 上機 4/25 → **SLAM 建圖完成 4/25 PM (v3.5 cartographer pure scan-matching, 永久棄 Go2 內建雷達)** → **Nav2 + AMCL stack 4/25 21:00 全打通 (v3.7 拆架構：建圖用 cartographer / 定位用 AMCL)** |
| 完成度 | P0-A ✅；P0-B ✅（pgm/yaml/pbstream 產出）；P0-C ✅ AMCL active；P0-D 🟡 WIP（/plan + /cmd_vel pipeline OK，Go2 實測 cmd_vel 門檻 MIN_X=0.50；卡 inflation lethal space，明早調 inflation_radius 即解）；P0-D.5 ~ P0-I 未開工 |
| 最後驗證 | 2026-04-25 21:00（Nav2 7 lifecycle nodes 全 active；bt_navigator 印 "Goal succeeded"；cmd_vel calibration MIN_X=0.50 m/s 確認 Go2 sport mode 啟動門檻）|
| 入口檔案 | `vision_perception/vision_perception/lidar_obstacle_node.py`（既有 P0-E 用）|
| 相關 driver | `sllidar_ros2`（Slamtec 官方）+ `cartographer_ros`（apt，**只用建圖**）+ `nav2_bringup`（apt，含 amcl + map_server + nav2 navigation）|
| 建圖配置 | `go2_robot_sdk/config/cartographer_lidar.lua`（pure scan-matching, use_odometry=false）|
| Nav2 配置 | `go2_robot_sdk/config/nav2_params.yaml`（AMCL: scan_topic=/scan_rplidar, alpha 0.4, OmniMotionModel；DWB: min_vel_x=0.45/max_vel_x=0.70）|
| 啟動腳本 | 建圖：`scripts/start_lidar_slam_tmux.sh`（5-window）；Demo：`scripts/start_nav2_amcl_demo_tmux.sh`（5-window: tf/sllidar/driver+odom_TF/nav2_bringup/fox）|
| Driver patch | `ros2_publisher.py` 加 `GO2_PUBLISH_ODOM_TF` env 開關（建圖用 0 / Nav2 用預設 1）|
| 測試 | LiDAR 13 tests（既有）+ Safety/Patrol/TTS ~14 新 tests（plan Task 5-8） |
| Spec / Plan | [spec](../superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md) / [plan](../superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md) |
| 整合紀錄 | [research/2026-04-25-rplidar-a2m12-integration-log.md](research/2026-04-25-rplidar-a2m12-integration-log.md) |

## 架構決策（2026-04-01 最終判定）

> ⚠️ **Supersedes by 2026-04-24 P0 翻案**：本表「Full SLAM / Nav2 永久關閉」的判定**失效**。
> 原判定基於 Go2 內建 LiDAR 5Hz 品質差（業界 SLAM 門檻 7Hz）。
> 外接 RPLIDAR A2M12 實測 10.57Hz > 7Hz，**Full SLAM + Nav2 路線復活為 P0 主線**。
> 以 [`docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`](../superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md) 為準。

| 路線 | 舊判定（4/1）| 新判定（4/24）| 理由 |
|------|:----:|:----:|------|
| D435 前方防撞 | 主線 | **停用** | 4/3 上機全失敗（鏡頭角度），由 LiDAR 取代 |
| LiDAR 360° safety | 主線 | **P0 主線** | RPLIDAR A2M12 10.57Hz 穩定 |
| CycloneDDS | 永久關閉 | 永久關閉 | Go2 Pro 韌體不支援 |
| Full SLAM | 永久關閉 | **P0 主線** | RPLIDAR 10.5Hz 超過 7Hz 門檻 |
| Nav2 global planner | 永久關閉 | **P0 主線（DWB，不用 MPPI）**| RPLIDAR 10Hz controller 可跑；MPPI Jetson ARM64 有 SIGILL 不用 |

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
- ~~LiDAR 行走中頻率降 ~35%（7.3→4-6Hz）~~ — Go2 內建 LiDAR 已棄用，RPLIDAR 10.4Hz 穩定
- ~~LiDAR 覆蓋率僅 18%~~（22/120 有效點）— Go2 voxel 編碼硬體限制，**已被外接 RPLIDAR 替代**
- ~~LiDAR 定位為「補充感知」，D435 才是前方防撞主力~~ — D435 已停用，**RPLIDAR 是 P0 唯一感測**
- **base_link → laser 物理位置未量測**（4/25 用估測 z=0.10）— 5/13 學校 demo 前必量測

### RPLIDAR A2M12 整合（4/25 進行中）
- **Go2 driver `/odom` 來源不可用於 Nav2**：driver 抓的是 `rt/utlidar/robot_pose`（Go2 內建 utlidar SLAM，跑在 18% 覆蓋率的內建 LiDAR 上），不是腿編碼器。Unitree SDK 不公開 leg-only odom topic
- **/scan topic 衝突**：Go2 driver 也發 `/scan`（120 點），會跟 sllidar 1800 點衝突。RPLIDAR 必須 remap 到 `/scan_rplidar`
- **slam_toolbox 對 LaserScan range count 是 hard constraint**：第一個 scan 註冊 sensor 後，後續不一致 range count 全 reject
- **rf2o subscription 卡 QoS handshake**：sllidar 發 RELIABLE，rf2o 預設 BEST_EFFORT，DDS 實作 silent fail。已 patch rf2o 源碼為 RELIABLE 重 build，但 4/25 結束時 subscription 仍未通（推測 ros2 daemon stale）。**下次 session 需 daemon restart 後重試**

### 避障邏輯

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
