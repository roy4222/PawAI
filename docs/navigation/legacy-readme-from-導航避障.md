# 導航避障

> Status: **yaw 物理錨定 ✅ −π/2 (v6 定案) / Phase 3 v6 map 重建待供電升級 / Phase 4 K1 baseline 待 map**（2026-04-30 morning 更新）

> **2026-04-30 morning — yaw 物理錨定一次定案**：放棄 Foxglove 視覺猜法（4/29 試 4 次失敗），改用 `scan_health_check.py` 物理錨定。Go2 正前方 0.8m 放物體 → scan 量到在 angle=90° bin → 補正 yaw=−π/2 = −1.5708 rad。7 scripts + mount-measurement.md 一次更新；Foxglove 視覺驗證 base_link +x 對齊 Go2 正前方通過。**今天不重建 map v6**：2464 模組 4/30 早上又跳電（root cause: 輸入上限 30V < Go2 滿電 33.6V），暫退回 XL4015（4-38V/75W）撐到 KREE DL241910 (22-40V→19V/10A/190W) 到貨。Phase 3 等供電穩了再開。
>   Commit: `560ca79` / 證據: [`research/2026-04-29-mount-measurement.md`](research/2026-04-29-mount-measurement.md) §v6 物理錨定證據

> **2026-04-29 — LiDAR mount 上機 + Phase 1-3**：mount 量測（x=−0.035, y=0, z=0.15）✅；Phase 2 寫了 `scan_health_check.py`（4-條件 PHANTOM gate）+ `start_scan_only_tmux.sh`（3-window）；Phase 3 重建 4 張 map（v2 yaw=0 / v3 −π/2 / v4 +π/2 / v5 π）全因 yaw 錯而 deprecated。**供電升級 XL4015 → 2464 升降壓恒壓恒流模組**（19:52 後不再跳電）。明天用物理錨定（Go2 正前方 0.8m 放物體）一次定案 yaw → v6 → Phase 4 K1。
>   Plan: `/home/roy422/.claude/plans/abstract-sleeping-hoare.md` / 量測 + 修正歷史: [`research/2026-04-29-mount-measurement.md`](research/2026-04-29-mount-measurement.md) / map QA: [`research/maps/README.md`](research/maps/README.md)

> **2026-04-26 evening — nav_capability S2 平台化**：把 P0 reactive 邏輯抽象成「平台層」，提供 4 actions / 3 services / 3 state topics 給 interaction_executive 與 PawAI Brain。WSL 70 tests pass；Jetson Phase 10 KPI 中 K9/K10 ✅，K8 移出實機（fake publisher 撞 driver 事故），K1/K2/K4/K5/K7 推遲。
>   Spec: [`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-26-nav-capability-s2-design.md`](../superpowers/specs/2026-04-26-nav-capability-s2-design.md) / Plan: [`docs/navigation/plans/2026-04-26-nav-capability-s2.md`](../superpowers/plans/2026-04-26-nav-capability-s2.md)

> **2026-04-26 morning — Nav2 動態避障實機驗證**：0.8m goal 走 50cm 現場確認；昨天 lethal 是暫態（costmap 髒污 / particle filter）非位置固有問題；v3.7 nav2_params 不需改；用戶判定 map 髒污要重新建圖（已備份舊 map 為 `.bak.20260426-094853`）。
>   詳見實機 log [`research/2026-04-26-nav2-dynamic-obstacle-log.md`](research/2026-04-26-nav2-dynamic-obstacle-log.md)
> **2026-04-25 上 Go2 機身**：/scan 10.40Hz；Cartographer pure scan-matching 建圖完成 → Nav2+AMCL stack 全打通；卡 inflation lethal space。
>   詳見整合紀錄 [`research/2026-04-25-rplidar-a2m12-integration-log.md`](research/2026-04-25-rplidar-a2m12-integration-log.md)
> **2026-04-24 LiDAR 到貨並驗證通過**：Jetson 上 /scan 10.57Hz / 1800 點/圈 / 60% valid。
> P0 設計定稿為「劇本式 A→B + 停障 + 續行」，不承諾一般動態繞障。
> **Spec**: [`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`](../superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md)
> **Plan**: [`docs/navigation/plans/2026-04-24-p0-nav-obstacle-avoidance.md`](../superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md)
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

## nav_capability 平台層狀態卡（2026-04-26 evening 新增）

| 項目 | 值 |
|------|---|
| 狀態 | **Phase 0–9 ✅ / Phase 10 KPI ⏳（K9/K10 ✅，K8 移出實機，K1/K2/K4/K5/K7 推遲）** |
| Actions | `/nav/goto_relative` / `/nav/goto_named` / `/nav/run_route` / `/log_pose` |
| Services | `/nav/pause` / `/nav/resume` / `/nav/cancel` |
| State | `/state/nav/heartbeat` (1Hz) / `/state/nav/status` (10Hz) / `/state/nav/safety` (10Hz) |
| Event | `/event/nav/waypoint_reached` / `/event/nav/internal/status` / `/state/reactive_stop/status` |
| twist_mux | 4 層（emergency 255 > obstacle 200 > teleop 100 > nav2 10）+ Bool `/lock/emergency` |
| 入口 packages | `nav_capability/` (4 nodes + 5 lib modules) / `go2_interfaces/` (4 actions + Cancel.srv) |
| 啟動腳本 | `scripts/start_nav_capability_demo_tmux.sh`（8-window，含 safety_only=true）|
| Runtime data | `~/elder_and_dog/runtime/nav_capability/{named_poses,routes}/`（不在 install/share，commit e2b3932 修正）|
| 測試 | 38 nav unit + 5 tf_pose helper + 23 reactive unit + 4 mux integration = 70 pass（WSL）|
| Spec / Plan | [spec](../superpowers/specs/2026-04-26-nav-capability-s2-design.md) / [plan](../superpowers/plans/2026-04-26-nav-capability-s2.md) |

**重大陷阱**：
- `reactive_stop_node` `safety_only=true` **必須**用於 mux 模式（priority 200），不然 clear zone 會以 0.60 m/s 永久 shadow nav。standalone fallback（`start_reactive_stop_tmux.sh`）保持預設 `safety_only=false`。兩腳本互斥。
- `test_mux_priority.py` 是 active publisher（FakePublisher 真的發 cmd_vel），**不可在 full stack 跑**（會穿透 mux 進 go2_driver）。WSL or isolated mux 環境驗證。

## 狀態卡（4/26 morning P0 reactive 主線）

| 項目 | 值 |
|------|---|
| 狀態 | **P0-A ✅ / P0-B ✅ / P0-C ✅ / P0-D ✅ 0.8m goal 自主前進實機通過（v3.7 nav2_params 不需改）/ reactive_stop fallback ✅ 17 tests + dry-run 通過** |
| 版本/決策 | D435 停用(4/3) → 外接 RPLIDAR A2M12 採購(4/14) → 到貨驗證(4/24) → P0 spec+plan 定稿(4/24) → 上機 4/25 → **SLAM 建圖完成 4/25 PM (v3.5 cartographer pure scan-matching)** → **Nav2 + AMCL stack 4/25 21:00 全打通 (v3.7)** → **4/26 Nav2 動態避障實機通過（昨天 lethal 判定為暫態，非位置固有 / 非 inflation 過大；v3.7 不需修改）+ reactive_stop_node fallback 完成** |
| 完成度 | P0-A ✅；P0-B ✅；P0-C ✅；P0-D ✅ 0.8m 自主前進現場驗證（amcl 50cm + 用戶現場 50cm 確認）；reactive_stop ✅（17 tests pass + Jetson dry-run /cmd_vel 10Hz）；P0-D.5 ~ P0-I 未開工 |
| 最後驗證 | 2026-04-26 09:50（A 線 0.8m goal × 2 通過、B 線 reactive_stop dry-run 通過、cartographer 重建圖 stack 已驗 / 待用戶遙控走完 + 三步驟存圖）|
| 入口檔案 | `vision_perception/vision_perception/lidar_obstacle_node.py`（既有 P0-E 用）|
| 相關 driver | `sllidar_ros2`（Slamtec 官方）+ `cartographer_ros`（apt，**只用建圖**）+ `nav2_bringup`（apt，含 amcl + map_server + nav2 navigation）|
| 建圖配置 | `go2_robot_sdk/config/cartographer_lidar.lua`（pure scan-matching, use_odometry=false）|
| Nav2 配置 | `go2_robot_sdk/config/nav2_params.yaml`（AMCL: scan_topic=/scan_rplidar, alpha 0.4, OmniMotionModel；DWB: min_vel_x=0.45/max_vel_x=0.70）|
| 啟動腳本 | 建圖：`scripts/start_lidar_slam_tmux.sh`（5-window）；Nav2 demo：`scripts/start_nav2_amcl_demo_tmux.sh`（5-window）；reactive fallback：`scripts/start_reactive_stop_tmux.sh`（4-window）|
| 相對 goal helper | `scripts/send_relative_goal.py`（讀 /amcl_pose 算前方相對 goal，QoS BEST_EFFORT 配 bt_navigator）|
| Driver patch | `ros2_publisher.py` 加 `GO2_PUBLISH_ODOM_TF` env 開關（建圖用 0 / Nav2 用預設 1）|
| 測試 | LiDAR 13 tests（既有）+ Safety/Patrol/TTS ~14 新 tests（plan Task 5-8） |
| Spec / Plan | [spec](../superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md) / [plan](../superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md) |
| 整合紀錄 | [research/2026-04-25-rplidar-a2m12-integration-log.md](research/2026-04-25-rplidar-a2m12-integration-log.md) |

## 架構決策（2026-04-01 最終判定）

> ⚠️ **Supersedes by 2026-04-24 P0 翻案**：本表「Full SLAM / Nav2 永久關閉」的判定**失效**。
> 原判定基於 Go2 內建 LiDAR 5Hz 品質差（業界 SLAM 門檻 7Hz）。
> 外接 RPLIDAR A2M12 實測 10.57Hz > 7Hz，**Full SLAM + Nav2 路線復活為 P0 主線**。
> 以 [`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`](../superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md) 為準。

| 路線 | 舊判定（4/1）| 新判定（4/24）| 理由 |
|------|:----:|:----:|------|
| D435 前方防撞 | 主線 | **停用** | 4/3 上機全失敗（鏡頭角度），由 LiDAR 取代 |
| LiDAR 360° safety | 主線 | **P0 主線** | RPLIDAR A2M12 10.57Hz 穩定 |
| CycloneDDS | 永久關閉 | 永久關閉 | Go2 Pro 韌體不支援 |
| Full SLAM | 永久關閉 | **P0 主線** | RPLIDAR 10.5Hz 超過 7Hz 門檻 |
| Nav2 global planner | 永久關閉 | **P0 主線（DWB，不用 MPPI）**| RPLIDAR 10Hz controller 可跑；MPPI Jetson ARM64 有 SIGILL 不用 |

## 啟動方式

```bash
# === Nav2 自主導航 demo（主線，含 AMCL + map）===
bash scripts/start_nav2_amcl_demo_tmux.sh
# 等 ~30s lifecycle active → Foxglove 設 /initialpose → 發 goal：
python3 scripts/send_relative_goal.py --distance 0.8

# === 反應式停障 fallback（demo 備援，不需 map）===
# 5/13 demo 當天若 Nav2 失敗的後備。直走 + 遇障停 + 移開續行。
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
bash scripts/start_reactive_stop_tmux.sh
# 場景驗收：見 docs/navigation/research/2026-04-26-nav2-dynamic-obstacle-log.md

# === 重新建圖（map 髒污時）===
bash scripts/build_map.sh home_living_room
# 用 Unitree 遙控器繞一圈 → 三步驟存圖（finish_trajectory + write_state + map_saver_cli）

# === 舊 D435 避障（停用，保留歷史）===
ros2 launch vision_perception obstacle_avoidance.launch.py

# === 舊 LiDAR 避障（vision_perception，4/8 前的舊 node）===
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
