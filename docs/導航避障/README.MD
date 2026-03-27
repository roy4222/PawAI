# Go2 導航避障系統 — 完整計畫

> 專案：老人與狗 (Elder and Dog)  
> 平台：Unitree Go2 + Jetson Orin Nano 8GB + 3D LiDAR + Intel RealSense D435  
> 軟體主線：ROS2 Humble + Nav2 + AMCL + DWB

**更新日期：** 2026-03-27
**當前階段：** 策略轉向 — LiDAR 正式棄用，改用 D435 Depth 反應式避障
**核心策略：** 最簡方案優先，demo 保命層

---

## 快速導讀（30 秒）

- **3/26 決策**：Go2 Pro 3D LiDAR 透過 WebRTC 傳輸，實測 0.03-2Hz，gap_max > 1.0s，**正式棄用**
- **新方案**：D435 ROI Depth Threshold（~50 行 numpy），反應式避障
- **預估工時**：10-12 小時（含 30 次防撞測試）
- **優先級**：P2 加分項，不搶 P0 穩定性
- **Sprint 排程**：Day 6-7（4/2-4/3）實作 + hardening
- **詳細研究**：[2026-03-25-reactive-obstacle-avoidance.md](./2026-03-25-reactive-obstacle-avoidance.md)
- **實作計畫**：[Sprint B-prime](../mission/sprint-b-prime.md) Day 6-7

> 以下為歷史記錄（3/3 版本的 LiDAR + Nav2 方案），保留供參考。

**詳細落地計畫**：[落地計畫_v2.md](./落地計畫_v2.md)  
**每週執行細節**：[weekly_plan.md](./weekly_plan.md)  
**研究綜整（最新）**：[Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md](./Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md)  
**開源專案決策**：[開源專案/](./開源專案/)

---

## 1. 安全第一

- **急停機制與操作模式**：系統分為 `mapping`、`navigation`、`guard` 三種模式；任何模式皆可觸發急停，`guard` 模式優先權最高，可中斷導航控制輸出。
- **安全不變量**：`footprint`、`footprint_padding`、`inflation_radius` 與停車規則屬於不可任意跳過的硬條件；未滿足時不得進入下一輪測試。
- **無 TF → 無運動 gate**：若 `map -> odom -> base_link` 或感測關聯 TF 缺失、過期、跳時，直接封鎖 `/cmd_vel` 輸出，禁止「盲動」。
- **碰撞防護層級**：
  1. 規劃層（Planner）避免穿越障礙區
  2. 控制層（Controller）抑制高風險軌跡
  3. 監督層（Safety Supervisor / Guard）最終裁決停車與降級
- **建議安全工具**：Nav2 官方 `nav2_collision_monitor`（獨立於 costmap 的緊急停車/減速區域過濾 `/cmd_vel`），或 `diff_drive_controller` 的 `reference_timeout: 0.5`（無速度指令 500ms 即停）。

## 2. 系統總覽

### 2.1 架構圖（text-based）

```text
3D LiDAR ──────┐     Intel RealSense D435 ──┐
               │                             │
               v                             v
  pointcloud_to_laserscan          PointCloud2 (depth)
         │                                   │
         v                                   v
       /scan ──────────┐  /camera/.../obstacle_point ──┐
                       │                               │
                       v                               v
              Local/Global Costmap (voxel_layer: scan + d435)
                       │
                       v      TF Tree (map/odom/base_link/camera_link)
                AMCL Localization        │
                       │                 │
                       v                 v
              SmacPlannerHybrid ──────> DWB Controller
                       │                 │
                       +── Nav2 ─────────+
                              │
                              v
                   Safety Supervisor Layer
              (TF gate / collision_monitor / mode guard)
                              │
                              v
                           /cmd_vel
```

### 2.2 TF 座標系

- `base_link`：機器狗本體控制基準。
- `odom`：短期連續運動座標。
- `map`：全域定位座標。
- `front_camera`：Go2 預設相機框架（非 `camera_link`）。
- `camera_link`：Intel RealSense D435 相機框架（定義於 `go2_with_realsense.urdf`）。
- `camera_mount_link`：D435 安裝支架框架。

### 2.3 關鍵 Topics 與 ownership

| Topic | 主要擁有者 | 角色 |
|---|---|---|
| `/point_cloud2` | LiDAR 驅動/轉換節點 | 原始點雲輸入 |
| `/scan` | `pointcloud_to_laserscan` 管線 | Nav2 近場障礙感知（LiDAR）|
| `/camera/realsense2_camera_node/depth/obstacle_point` | realsense2_camera | D435 深度障礙點雲 |
| `/amcl_pose` | AMCL | 定位估計輸出 |
| `/local_costmap/costmap_raw` | Nav2 local costmap | 近場避障代價圖 |
| `/navigate_to_pose/_action/status` | Nav2 action server | 任務狀態追蹤 |
| `/cmd_vel` | Controller + 安全監督層 | 最終速度命令 |

### 2.4 硬體平台

- 計算平台：Jetson Orin Nano 8GB
- 機器人：Unitree Go2
- 主感測器：3D LiDAR（遠場 360° 障礙感知）
- 輔助感測器：Intel RealSense D435 深度攝影機（近場 0.3-3m 前向障礙補強）

### 2.5 感測器互補策略

| 感測器 | 有效範圍 | 視角 | 角色 | 優勢 |
|--------|---------|------|------|------|
| 3D LiDAR | 0.3-12m | 360° | 主感測 | 全方位、高精度、不受光線影響 |
| RealSense D435 | 0.3-3m | 87°×58° | 近場補強 | 偵測低矮/半透明障礙物、填補 LiDAR 近場盲區 |

**互補邏輯**：
- LiDAR 負責全域障礙感知（global + local costmap）
- D435 僅作為 **local costmap 的第二觀測源**，強化近場（0.3-1.5m）偵測能力
- D435 同時作為 `nav2_collision_monitor` 的獨立短程急停源
- 若 D435 離線 → 自動回退至 LiDAR-only 模式，不影響導航安全主線
## 3. 現況基線

- 目前主線：`Nav2 + AMCL + DWB`
- 下表為當前參數基線（主線操作與評估以此為起點）

| 類別 | 基線值 |
|---|---|
| Controller | DWB, 20Hz, `max_vel_x=0.22`, `max_vel_theta=0.30` |
| Footprint | `[[0.3, 0.15], [0.3, -0.15], [-0.3, -0.15], [-0.3, 0.15]]` |
| `footprint_padding` | `0.05` |
| Local costmap | `6x6m`, `0.05m resolution`, `update 8Hz` |
| Inflation | `inflation_radius=0.35`, `cost_scaling_factor=2.0` |
| Obstacle layer | `obstacle_max_range=3.0`, `raytrace_max_range=3.5` |
| Planner | `SmacPlannerHybrid (Reeds-Shepp)`, `min_turning_radius=0.30` |
| AMCL | `OmniMotionModel`, `max_particles=2000`, `max_beams=60` |
| Progress checker | `movement_time_allowance=20.0`, `required_movement_radius=0.03` |
| DWB Critics | `BaseObstacle(0.40)`, `PathAlign(16.0)`, `GoalAlign(10.0)`, `PathDist(24.0)`, `GoalDist(16.0)`, `RotateToGoal(0.25)` |
| LiDAR stride | `LIDAR_POINT_STRIDE default: 8` |

## 4. 已診斷問題與根因分析

### 4.1 風險排序（Top 5）

1. `LIDAR_POINT_STRIDE=8`（丟棄 87.5% 點雲）— 🔴 致命
2. `inflation_radius=0.35`（Go2 體長 0.6m，僅 5cm 緩衝）— 🟠 高危
3. `movement_time_allowance=20s`（卡住判定過慢）— 🟡 中危
4. `BaseObstacle.scale=0.40`（避障權重不足）— 🟡 中危
5. `obstacle_max_range=3.0`（偵測距離偏短）— 🟢 低危

### 4.2 Oracle 補充發現（系統性根因）

- **TF/時間完整性**：sensor timestamps 與 DDS QoS 若不一致，容易產生 TF extrapolation、延遲與控制誤判。
- **四足特有動態問題**：足部滑移與 `odom` 跳動會放大 AMCL 不確定性，導致局部路徑追蹤抖動。
- **近場盲區對齊問題**：感知可視範圍必須與 `footprint + inflation + collision monitor` 保護範圍一致，否則會出現「看見但來不及停」或「能停但感測不到」的落差。

### 4.3 D435 整合現況（Gap Analysis）

- **已就緒**：`go2_with_realsense.urdf` 已定義完整 `camera_link` TF（`camera_mount_link → camera_link`，安裝於 Head_upper）
- **未連接 Nav2**：`nav2_params.yaml` 的 `observation_sources` 僅有 `scan`，無 D435 深度來源
- **未啟動驅動**：`robot.launch.py` 未包含 `realsense2_camera` 節點啟動
- **未安裝 depthimage_to_laserscan**：無深度轉雷射掃描管線
- **參考實作存在**：OM1 專案已驗證 D435 可用於 Go2 障礙偵測（`D435Provider`）

**D435 整合後 nav2_params.yaml 目標配置（僅 local costmap 片段）：**

```yaml
local_costmap:
  local_costmap:
    ros__parameters:
      plugins: ["voxel_layer", "inflation_layer"]
      voxel_layer:
        plugin: "nav2_costmap_2d::VoxelLayer"
        observation_sources: scan d435
        scan:
          topic: /scan
          data_type: LaserScan
          marking: true
          clearing: true
          obstacle_max_range: 3.0
          raytrace_max_range: 4.0
        d435:
          topic: /camera/realsense2_camera_node/depth/obstacle_point
          data_type: PointCloud2
          marking: true
          clearing: true
          obstacle_max_range: 2.0
          raytrace_max_range: 2.5
          min_obstacle_height: 0.05
          max_obstacle_height: 1.2
```

### 4.4 D435 整合風險與緩解

| 風險 | 嚴重度 | 緩解措施 |
|------|---------|----------|
| TF/extrinsics 不匹配 | 🟠 高 | 以 RViz 驗證 camera_link → base_link TF，以實際障礙物比對 costmap 表現 |
| 深度雜訊/假障礙 | 🟠 高 | 啟用 decimation+temporal+spatial 濾波器；設 `min_obstacle_height: 0.05` 過濾地板 |
| 計算/延遲尖峰 | 🟡 中 | 424×240 @ 15fps，停用 RGB；監控 tegrastats，超過 15% CPU 增量則降頻 |
| D435 離線/當機 | 🟢 低 | 自動回退 LiDAR-only，D435 是輔助而非必要 |
## 5. 開源專案研究與採納決策

| 專案 | 定位 | 立即採納 | 條件採納 | 暫不採納 |
|---|---|---|---|---|
| Odin-Nav-Stack | ROS1 導航棧 | 安全外圈、可觀測性、有界恢復 | Heading 對齊、障礙記憶衰減 | 全棧移植、NeuPAN |
| OM1 | AI Runtime | 安全監督層、模式治理、失敗分類 | 語義導航、Zenoh 互通 | 全棧替換、LLM 控制閉環 |
| NavDP | Sim-to-Real 研究 | 服務化接口、MPC 旁路、深度管線參考 | Shadow mode 策略對比 | 端到端主線替換 |
| LoGoPlanner | 研究基準 | 深度前處理、A/B 評估模式、MPC shadow | Guarded-assist 建議器 | 直接接管主導航 |
| visualnav-transformer | GNM/ViNT/NoMaD | 資料前處理、Shadow 評測 | 視覺子目標建議器 | 直接接管 `cmd_vel` |

採納決策詳見：

- `docs/導航避障/開源專案/Odin_採納決策.md`
- `docs/導航避障/開源專案/OM1_採納決策.md`
- `docs/導航避障/開源專案/NavDP_採納決策.md`
- `docs/導航避障/開源專案/LoGoPlanner_採納決策.md`
- `docs/導航避障/開源專案/visualnav-transformer_採納決策.md`
- `docs/導航避障/開源專案/NavDP_採納轉移路線圖.md`

## 6. 三階段落地路線

### Phase A：安全與穩定止血（Week 1-2）

- **A1 感測密度**：執行 stride A/B（`8 -> 2 -> 1`），以 `/scan` 穩定率、有效回波、CPU 使用率共同決策。
- **A2 安全包絡**：同步調整 `inflation/footprint/recovery`，先達成 0 碰撞再談速度體感。
- **A3 可觀測性**：建立 incident packet 與 debug cockpit，讓每次失敗可被分類與追溯。
- **A4 D435 近場補強（Stride 修復後）**：
  - 安裝 `realsense2_camera` ROS2 驅動
  - 切換 URDF 至 `go2_with_realsense.urdf`
  - 將 D435 PointCloud2 加入 local costmap `voxel_layer` 作為第二觀測源
  - 配置 `nav2_collision_monitor` 以 D435 作為短程急停源（0.2-1.5m）
  - D435 參數：424×240 @ 15fps，停用 RGB，啟用 decimation + temporal + spatial 濾波器

### Phase B：控制體感優化（Week 3-4）

- **B1 DWB Critics 調優**：依單變數 A/B 原則，降低 stop-go、猶豫、過度旋轉。
- **B2 MPPI 選擇性評估**：僅在 DWB 已通過 Gate 且 Jetson 資源有 headroom 時進行。
- **MPPI Jetson 注意事項**：官方建議 `batch_size` 降至 ~1000（8GB 記憶體限制），`iteration_count` 保持 1，監控 thermal throttling。

### Phase C：架構升級評估（Week 5+）

- **C1 Cartographer（條件性）**：僅當主瓶頸確認為定位一致性時導入。
- **C2 D435 進階應用（條件性）**：在 Phase A 基礎整合穩定後，評估 depth-to-costmap 精細化調整、D435 輔助的視覺子目標建議。
- **C3 AI 模型評估（研究化）**：採 shadow/sandbox 策略，不直接接管實機閉環。

> **注意**：Isaac ROS Visual SLAM 對 D435（無 IMU）支援度不足，經評估暫不採用。若未來升級至 D435i，可重新考慮。
## 7. Gate 定義（進階硬條件）

- **G1 安全**：0 碰撞（至少 200 次短距或 10 小時）。
- **G2 可靠**：成功率 `>= 95%`，`ABORT <= 5%`。
- **G3 感測新鮮度（主判準）**：
  - 必報 `gap95/gap99/gap_max`、`age95/age99`
  - 連續避障模式要求：`gap99 <= 0.5s`、`gap_max <= 1.0s`、`age99 <= 0.2s`
  - 若未達標：禁止連續導航，僅允許停車定位或降級模式
- **G4 stale-stop**：必須啟用感測逾時停車（stale-data stop）；故障注入 3 秒感測黑屏時不得繼續前進。
- **G5 資源**：無 CPU 飽和，記憶體穩定。D435 處理不超過額外 15% CPU。

> 註：`/scan` 平均 Hz 僅作輔助觀察，不可作為單一通過條件。

## 8. 啟動與操作指南

### 8.1 環境變數

- `GO2_LIDAR_DECODER`
- `LIDAR_POINT_STRIDE`
- `MAP_YAML`
- `FOXGLOVE`
- `ENABLE_VIDEO`
- `PUBLISH_COMPRESSED_IMAGE`
- `ENABLE_REALSENSE` — 是否啟動 D435 驅動（預設 `false`，Phase A4 後設為 `true`）

### 8.2 每日操作流程

流程：`preflight -> launch -> set_initial_pose -> postlaunch -> test -> shutdown`  
（完整週期與判讀規則請見 `docs/導航避障/weekly_plan.md`）

```bash
# 1) preflight
zsh scripts/go2_ros_preflight.sh prelaunch

# 2) launch
GO2_LIDAR_DECODER=wasm LIDAR_POINT_STRIDE=<chosen_stride> \
  MAP_YAML=/home/jetson/go2_map.yaml \
  zsh scripts/start_nav2_localization.sh

# 3) set_initial_pose
sleep 25
zsh scripts/set_initial_pose.sh 0.0 0.0 0.0

# 4) postlaunch
zsh scripts/go2_ros_preflight.sh postlaunch

# 5) test（示例）
zsh scripts/check_gate_c_rates.sh 5 10
python3 scripts/nav2_goal_autotest.py --distance 0.5 --timeout 45

# 6) shutdown
zsh scripts/go2_ros_preflight.sh prelaunch
```

### 8.3 Debug Cockpit

建議 tmux pane 佈局（對齊 Week 2 診斷流程）：

- Pane 1：`/cmd_vel`
- Pane 2：`/navigate_to_pose/_action/status`
- Pane 3：速率總覽（`check_gate_c_rates.sh`）
- Pane 4：`/local_costmap/costmap_raw` 速率

## 9. 測試方法論

- **固定座標 A↔B 循環**：使用固定絕對目標，不用 `--distance` 相對目標作為最終驗收依據。
- **單變數 A/B 原則**：每輪只改一個關鍵變數，避免多因子混疊。
- **必填紀錄欄位**：成功/失敗、原因分類、參數版本（含日期與 commit）。
- **失敗分類標準**：感測稀疏 / costmap / controller / TF時間。

## 10. 關鍵文件索引

| 路徑 | 說明 |
|---|---|
| `go2_robot_sdk/config/nav2_params.yaml` | Nav2 完整參數 |
| `go2_robot_sdk/launch/robot.launch.py` | 主要啟動檔 |
| `go2_robot_sdk/urdf/go2.urdf` | Go2 機器人模型（無 RealSense）|
| `go2_robot_sdk/urdf/go2_with_realsense.urdf` | Go2 + RealSense D435 模型 |
| `scripts/start_nav2_localization.sh` | Nav2 定位啟動 |
| `scripts/go2_ros_preflight.sh` | 前後置檢查 |
| `scripts/check_gate_c_rates.sh` | 速率檢查 |
| `scripts/nav2_goal_autotest.py` | 自動化目標測試 |
| `scripts/set_initial_pose.sh` | 初始座標設定 |
| `docs/導航避障/落地計畫_v2.md` | 詳細落地計畫 |
| `docs/導航避障/weekly_plan.md` | 每週執行計畫 |
| `docs/導航避障/Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md` | 研究證據分級、Go/No-Go gate、實驗矩陣 |
| `docs/導航避障/開源專案/*.md` | 各專案採納決策 |

## 11. 關鍵待驗證（研究空缺）

1. **WebRTC vs CycloneDDS 同條件實測**：需完成 ABBA 實驗並輸出 `gap/age` 分位數比較。  
2. **burst+gap 單一主因定錨**：目前高機率為排程/佇列背壓，仍需用 profiling + trace 封口。  
3. **D435 + LiDAR 共跑瓶頸比例**：需量化 USB/CPU/RAM 對 `gap_max` 的貢獻，避免錯誤歸因。

## 12. 不做事項

1. 不在同一輪改多組關鍵參數。
2. 不在安全 gate 未過前追求高速。
3. 不把研究型模型直接接管主控制。
4. 不用 benchmark 結果直接推論實機安全。
5. 不在控制閉環中引入非確定性推理。
6. 不在 LiDAR 主線未穩定前將 D435 設為唯一安全來源。
7. 不在 D435 整合期間同時調整 LiDAR 參數（單變數原則）。

## 13. 結論

一句話：「先讓機器狗『看得見』，再讓它『跑得順』；基礎不打穩，前沿模型只是空中樓閣。」

---

## 附錄 A：術語對照表

| 英文 | 中文 | 說明 |
|------|------|------|
| stride | 點雲步進 | LiDAR 點取樣間隔（每 N 個點取 1 個）|
| inflation | 膨脹 | costmap 障礙物膨脹半徑 |
| footprint | 足跡 | 機器人佔地面積多邊形 |
| DWB | Dynamic Window B | Nav2 預設局部規劃器 |
| MPPI | Model Predictive Path Integral | Nav2 進階局部規劃器（GPU 友好）|
| AMCL | Adaptive Monte Carlo Localization | 粒子濾波定位 |
| ABORT | 任務中止 | Nav2 action 回報 status=6 |
| costmap | 代價地圖 | 障礙物與通行性的格狀表示 |
| shadow mode | 影子模式 | 旁路觀測，不控制機器人 |
| guarded assist | 守衛輔助 | 受安全層裁決的建議式控制 |

| voxel layer | 體素層 | 3D 障礙物檢測的 costmap 插件 |
| PointCloud2 | 點雲訊息 | ROS2 3D 點雲資料格式 |
| collision monitor | 碰撞監控 | Nav2 獨立安全停車模組 |
| D435 | 深度攝影機 | Intel RealSense D435 |
## 附錄 B：給未來 AI Agent 的備註

本文件是導航避障子系統的**單一真相源 (Single Source of Truth)**。若需繼續工作：

1. 先確認當前所處 Phase 與 Gate 狀態（見第 6、7 節）
2. 查看 `weekly_plan.md` 確認本週具體任務
3. 所有歷史採納決策記錄於 `開源專案/` 目錄
4. 參數基線見第 3 節，任何修改需 A/B 驗證後才可寫入預設值
5. **關鍵環境變數**：`GO2_LIDAR_DECODER=wasm`、`LIDAR_POINT_STRIDE`、`MAP_YAML`、`ENABLE_REALSENSE`
6. **已知陷阱**：`--distance` 相對目標會造成漂移，改用固定絕對座標 A↔B

---

*文件版本：v2.1 | 維護：FJU PawAI 專題組*
