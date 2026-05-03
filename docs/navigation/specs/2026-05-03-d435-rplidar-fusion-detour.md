# D435 + RPLIDAR 融合自動繞行 — 窄場景 detour demo design

**Date**: 2026-05-03 evening
**Status**: Spec for tonight's last task; user approved 3-phase progressive approach
**Goal**: 在 Go2 居家窄場景（房間縱深 ≤ 2.5m, box 1.0m 距離）內，達成 DWB 自動繞開靜態障礙物，**結合 RPLIDAR + D435 兩個 sensor**

---

## Context

5/3 一整天完成 Demo A（K-STATIC-AVOID-CONTROLLED PASS, 「停 → 拿走 → 繼續」）。剩唯一沒拿到的 demo 是 **Stage 2 / Demo B：自動繞開**。

User 明確要求：
- 必須結合 D435 + RPLIDAR
- 真實居家空間（縱深 2.5m / box 1m / 一側 80cm 一側 60cm）— 不能用寬場景偷
- 三層成功標準（不是 all-or-nothing）

User 已驗證 D435 進 Nav2 costmap 風險清單（TF / 高度過濾 / clearing / CPU / 與 RPLIDAR 衝突 / 不一定救 DWB），決定走「漸進三段式」：先 RPLIDAR-only 試 detour profile，有繞行跡象才加 D435 融合。

物理現實：
- Go2 base_link → 鼻尖 ≈ 35cm
- DWB 規劃需要 footprint half-x (30cm) + inflation 才能動，所以 box 距 base_link 必須 > 60cm（主線 inflation 0.30）或 > 45cm（detour profile inflation 0.15）
- Go2 sport mode `min_vel_x = 0.50 m/s`，DWB 設 0.45 接近底線 + `max_vel_y = 0`（quadruped 側移風險高，不開）
- 曲線繞行最小半徑 ≈ 0.5m

---

## Architecture：3-phase 漸進

```
Phase 1 (純可視化)  →  Phase 2 (local_costmap only)  →  Phase 3 (Go2 短 goal 試)
   D435 → /scan_d435      D435 marking + clearing       DWB 嘗試繞行
   Foxglove 對齊驗證       不送 Go2 goal                  reactive_stop 兜底
   無 Nav2 影響           無 Go2 motion                  Go2 物理移動
```

每階段 gate 分明：前一階段沒過不准進下一階段，避免變數混淆。

---

## Phase 1：D435 → `/scan_d435` 可視化（不影響 Nav2）

### Components
- `depthimage_to_laserscan_node`（已 install on Jetson）
- Foxglove panels（RGB + depth + scan）

### 啟動命令

```bash
ros2 run depthimage_to_laserscan depthimage_to_laserscan_node \
  --ros-args \
  -r depth:=/camera/camera/aligned_depth_to_color/image_raw \
  -r depth_camera_info:=/camera/camera/aligned_depth_to_color/camera_info \
  -r scan:=/scan_d435 \
  -p scan_height:=10 \
  -p output_frame:=camera_depth_optical_frame \
  -p range_min:=0.30 \
  -p range_max:=3.0
```

### 成功標準（gate to Phase 2）
1. `ros2 topic hz /scan_d435` ≥ 10 Hz
2. Foxglove `/scan_d435` 在 RGB 上的 box 位置視覺對齊（容差目視 < 10cm）
3. 拿走 box → 對應 angle bin range 變大（inf 或接近 max）
4. TF chain `base_link → camera_depth_optical_frame` 正確（用 `tf2_echo` 或 Foxglove TF panel 驗證朝向合理）

### 失敗時動作
- TF 偏 → 手動調 `static_transform_publisher` 參數，或先量 D435 物理 mount 角度後重設
- Topic 沒資料 → 檢查 D435 driver 是否還活著
- **Phase 1 沒過絕對不進 Phase 2**

---

## Phase 2：`/scan_d435` 加進 `local_costmap`（不加 global, DWB 不動）

### Components
- 新檔 `go2_robot_sdk/config/nav2_params_detour.yaml`（從主線 cp + 改）
- `robot.launch.py` 加 `nav_params_file` launch arg（前置改動）
- 新檔 `scripts/start_nav_capability_demo_tmux_detour.sh`

### Yaml 改動範圍

**只改 local_costmap.obstacle_layer**，其他保留主線：

```yaml
local_costmap:
  local_costmap:
    obstacle_layer:
      observation_sources: scan d435_scan
      scan: { ... }   # 不動，與主線同
      d435_scan:      # 新加
        topic: /scan_d435
        data_type: "LaserScan"
        marking: True
        clearing: True
        inf_is_valid: True
        obstacle_max_range: 2.0
        raytrace_max_range: 2.5
        min_obstacle_height: 0.0
        max_obstacle_height: 2.0

# global_costmap 完全不動
# DWB FollowPath 完全不動  ← 關鍵：debug isolation
# inflation_layer 暫時也不動  ← Phase 3 才調
```

### 成功標準（gate to Phase 3）
1. Box 放進 D435 視野 → Foxglove `/local_costmap/costmap` 2-3s 內看到 obstacle marking（彩色框）
2. 拿走 box → 2-3s 內 marking 清掉（clearing 正常）
3. `ros2 topic hz /local_costmap/costmap_updates` 正常（2 Hz）
4. **不送 Go2 goal** — 純 costmap 行為驗證

### 失敗時動作
- Marking 不出現 → 檢查 D435 TF（同 Phase 1）+ depth 高度過濾
- Clearing 慢/沒清 → `obstacle_max_range` 調小、檢查 raytrace 設定
- RPLIDAR 與 D435 衝突 → log 看是哪個 source 引入殘影
- **Phase 2 沒過絕對不進 Phase 3**

---

## Phase 3：Go2 短 goal 試 detour（detour mode 啟動）

### 場景配置（user 確認的窄場景）

| 維度 | 值 | 備註 |
|---|---|---|
| Box 距 Go2 鼻尖 | **1.0m** | 房間最大可給 |
| Goal | **1.6m** | 越過 box 60cm |
| 左側淨空 | ≥ 0.8m | 主要繞行方向 |
| 右側淨空 | ≥ 0.6m | 次要 |
| 後方淨空 | ≥ 0.5m | recovery 用 |

### Detour mode 參數（detour profile 才改、不影響 Demo A 主線）

| 參數 | 主線值 | Detour 值 | 理由 |
|---|---|---|---|
| `reactive_stop_node danger_distance_m` | 0.60 | **0.40** | 給 DWB 多 20cm 繞行空間 |
| `reactive_stop_node slow_distance_m` | 1.0 | **0.80** | 緩衝區對應縮 |
| `local_costmap.inflation_layer.inflation_radius` | 0.30 | **0.15-0.20** | 把 box 周圍禁區從 60cm 縮到 45-50cm |
| `controller_server.FollowPath.BaseObstacle.scale` | 0.80 | **0.30-0.40** | 障礙成本降，敢繞 |
| `controller_server.FollowPath.PathAlign.scale` | 12.0 | **8-10** | 路徑黏著降 |
| `controller_server.FollowPath.PathAlign.forward_point_distance` | 0.2 | **0.5** | lookahead 拉長 |
| `controller_server.FollowPath.GoalAlign.scale` | 10.0 | **5-6** | goal 對齊降 |

**不動**：
- `min_vel_x = 0.45`（Go2 sport mode 物理硬限）
- `max_vel_y = 0`（quadruped 側移風險）
- `xy_goal_tolerance = 0.10`（5/3 已調）
- AMCL params

### Watchdog（emergency 兜底）

5/3 結構：
- `front_min < 0.30m` 持續 1s → emergency stop
- `vx > 1.0 m/s` → emergency stop
- `lat_drift > 0.6m` → emergency stop
- Max 60s timeout

emergency action: `python3 nav_capability/scripts/emergency_stop.py engage` + `StopMove (api_id=1003, topic=rt/api/sport/request)`

### 三層成功標準（user 定義）

| 層 | 條件 | 解讀 |
|---|---|---|
| **L1**（最低） | `/scan_d435` + Foxglove 對齊（Phase 1 通過） | D435 sensor pipe 通了 |
| **L2** | local_costmap mark/clear 正常（Phase 2 通過） | D435 + RPLIDAR 融合進 costmap 通了 |
| **L3**（理想） | Go2 DWB lat_drift > 0.2m 且越過 box 或 az 非零 | 真自動繞開 |

L1+L2 = 進展（明天還可以調）；L1+L2+L3 = 真 demo 可宣稱自動繞開。

### Phase 3 失敗時動作

- DWB 又 `No valid trajectory` → 確認場景 ≥ 上述最小值；不行表示 quadruped 物理極限
- DWB 試但被 reactive 接管 → reactive danger 已降到 0.40，再降風險高（撞紙箱事件記憶）
- 連 3 輪 L3 fail → **退守 B2 waypoint detour**，話術改「**透過預設路點規劃避開預知障礙物**」

---

## 對齊 user 的 4 個重點限制

| # | 限制 | Spec 怎麼遵守 |
|---|---|---|
| 1 | D435 不進 global_costmap | yaml 只改 `local_costmap.obstacle_layer` |
| 2 | 不同時大改 DWB 與 D435 | Phase 2 只加 D435 source，Phase 3 才調 DWB（即使如此 DWB 改動是 detour profile，不影響主線）|
| 3 | 不關 reactive_stop | 始終保留，只調 danger 距離 |
| 4 | Foxglove 必須看到對齊 | Phase 1 強制 gate |

---

## Files to be modified

| 檔案 | 性質 |
|---|---|
| `go2_robot_sdk/launch/robot.launch.py` | edit (line 77 + add `nav_params_file` LaunchArgument) — **前置必驗 Demo A launcher 不傳 arg 仍可啟** |
| `go2_robot_sdk/config/nav2_params_detour.yaml` | **新檔**（從主線複製 + Phase 2/3 改動） |
| `scripts/start_nav_capability_demo_tmux_detour.sh` | **新檔**（含 depthimage_to_laserscan window，順序：tf → sllidar → d435 → depthimage_to_laserscan → robot/nav2 → reactive → navcap → foxglove → monitor） |
| `scripts/demo_waypoint_detour.sh` | **新檔**（B2 fallback，命名「**手動路點繞行示範**」）|

不改：
- 主線 `nav2_params.yaml`
- 主線 `start_nav_capability_demo_tmux.sh`
- 任何 source code（nav_action_server / reactive_stop / capability_publisher / depth_safety）
- Demo A 主線完全不破壞

---

## Testing approach

### 單元
- `bash -n scripts/*.sh` 語法
- `python3 -m py_compile go2_robot_sdk/launch/robot.launch.py`
- yaml lint：`python3 -c "import yaml; yaml.safe_load(open('go2_robot_sdk/config/nav2_params_detour.yaml'))"`

### Smoke（每 Phase gate）
- Phase 1：`ros2 topic hz /scan_d435` + Foxglove 視覺
- Phase 2：`/local_costmap/costmap` Foxglove 視覺 + box 進出
- Phase 3：watchdog log + Go2 物理行為

### Demo A 不破壞驗證（B-prereq 必驗）
- 修完 `robot.launch.py` 後，**先用主線 launcher 跑一次 Demo A**（不傳 nav_params_file）
- 確認 Demo A 行為跟昨晚相同（`bash scripts/start_nav_capability_demo_tmux.sh` → 9 windows + 7 nav nodes + nav_round_reset READY）
- **這個驗證沒過就 revert robot.launch.py 改動**

---

## 風險與緩解

| 風險 | 影響 | 緩解 |
|---|---|---|
| D435 TF 不準 → costmap 障礙位置偏 | DWB 繞錯方向、可能撞 | Phase 1 強制目視對齊 gate；不對齊不進 Phase 2 |
| Inflation 0.15 太小 → Go2 footprint 邊緣擦 box | 物理碰撞 | watchdog `front < 0.30` emergency stop 兜底 |
| reactive 0.40 + Go2 站立反應延遲 → 真撞 | 碰撞 | 現場人盯著、emergency_stop 隨手按 |
| Phase 3 連 5 輪 fail | 今晚拚不到自動繞開 | B2 waypoint fallback，話術降一階 |
| 修 robot.launch.py 把主線 launcher 弄壞 | Demo A 也錄不了 | 修完強制驗主線 launcher，沒過就 revert |
| AMCL cov 又卡 YELLOW | Goal 1.6m 被 yellow gate 拒（需 GREEN） | 5/3 已調 launch covariance_threshold 0.45；如果還卡，等收斂或重設 initialpose |

---

## 不做（明確 out-of-scope）

- 不關 reactive_stop（最後一道安全線）
- 不開 max_vel_y（quadruped 側移風險）
- 不換 controller（不切 MPPI/TEB，9 天內 tuning 來不及）
- 不在 Jetson 跑 colcon build（已知 setuptools 不相容 → editable install + source rsync）
- 不動 Demo A 主線 yaml / launcher
- 不動 nav_action_server 程式碼
- 不做 TTS（user 5/3 明確說不要）
- 不做 D435 進 global_costmap
- 不做 voxel_layer / pointcloud（先 LaserScan 路徑足夠）

---

## Demo 話術（按結果分檔）

**L3 過（真自動繞開）**：
> 「Go2 結合 RPLIDAR 主動避障 + D435 深度感測，在居家窄場景下自主感知障礙物並即時繞開到達目標位置」

**L1+L2 過、L3 fail**：
> 「D435 + RPLIDAR 融合進入 Nav2 costmap、Foxglove 即時可視化，後續 Go2 路徑規劃將以此感測融合為基礎」（demo 不演 Go2 實機繞，只展示融合 + 看到障礙）

**全 fail，走 B2**：
> 「透過預設路點規劃避開預知障礙物」（**禁用「即時自動繞開」**）

---

## 完成標準

今晚收工要拿到至少：
- L1 + L2 通過（D435 進 local_costmap 融合可運作）
- 4 個檔案 + spec doc 全 commit
- 結果 append 到 `docs/navigation/plans/2026-05-03-stage1-and-recovery.md`
- 更新 `references/project-status.md`

L3 拿到是 bonus，沒拿到也算今晚完成（B2 兜底 + 明天再試）。
