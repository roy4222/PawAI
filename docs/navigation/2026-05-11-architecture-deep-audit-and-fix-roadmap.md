# Navigation Architecture Deep Audit — 5/11 撞牆事件根因 + 修法路線圖

> **Status**: authoritative
> **Date**: 2026-05-11 night
> **Scope**: 完整盤點 PawAI 導航避障 stack（RPLIDAR + D435 + reactive_stop + twist_mux + Nav2 + Go2 driver）的設計缺陷，給出 demo 前能落地的修法。
> **Trigger**: 5/11 B5 burndown 在家裡 motion 測試時 Go2 撞到 1.5m 處障礙物。經三線並行調查（local docs / local code / 網路 best practice）發現問題不只一個。
> **Authority**: 本檔取代任何 reactive_stop 參數、Nav2 obstacle_layer 配置、感測器分工的舊敘述。`docs/navigation/CLAUDE.md` 與 `docs/pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md §4` 引用本檔。

---

## 0. TL;DR

**撞牆不是單一 bug，是 6 層設計缺陷疊加**。最快「修一件解 80%」的選項：**Nav2 local_costmap.obstacle_max_range 從 1.8m 拉到 2.5-3.0m**（`go2_robot_sdk/config/nav2_params.yaml:231`）。

但只修這一條只解掉 Nav2 視野盲區，沒解掉 reactive_stop 的「clear zone 沉默 → mux timeout → teleop 接管」漏洞，也沒解掉 0.6m danger threshold 對 Go2 機身太近的問題。**完整 demo 級修法見 §6**。

---

## 1. 撞牆事件完整重建

### 1.1 物理時序

```
t=0s    物體放 Go2 前方 0.5m → reactive_stop zone=danger
        /cmd_vel_obstacle 持續發 0 @ 10Hz
        teleop 開始發 0.5 m/s @ 10Hz 在 /cmd_vel_joy
        mux：obstacle priority 200 蓋 teleop priority 100 → /cmd_vel = 0
        Go2 站著不動 ✅
t=86s   Roy 移開物體 → zone: danger → slow → clear
t=86s   reactive_stop 在 safety_only 模式下「clear zone 完全停發訊號」
        /cmd_vel_obstacle 沉默
t=86.5s mux 0.5s timeout → 切 teleop priority 100
        /cmd_vel = 0.5 m/s
        Go2 driver 收到 0.5 → Move (1008) → Go2 開始走
t=86-91s Go2 全速 0.5 m/s 走，朝前方 1.5m 處的障礙物
        Nav2 不在這條路徑（teleop 直接穿過 mux）
        但即使 Nav2 在路徑：local_costmap.obstacle_max_range=1.8m，看不到 1.5m+ 障礙
t=91s   reactive_stop zone slow (front_min=0.97m)，但 safety_only 不在 slow 發訊號
        Go2 繼續全速
t=92s   zone 振盪 slow ↔ clear（sensor noise）
        clear_debounce_frames=3 → 0.3s 連續 clear 才算 clear
        但 0.3s @ 0.5m/s = 0.15m，距離已經逼近
t=93s   zone slow → danger (front_min=0.57m)
        reactive_stop 終於發 0
        但 LiDAR 0.57m 對應 Go2 機鼻只剩 0.57m - 0.40m = 0.17m
        加 0.5m/s × 0.3s 反應 = 0.15m → 機鼻已到 0
撞
```

### 1.2 撞牆 6 層原因（全部都要修才完整）

| # | 層 | 缺陷 | 嚴重度 |
|:---:|---|---|:---:|
| 1 | reactive_stop | safety_only 在 clear zone 完全沉默 → mux timeout 後沒人擋 | **demo 致命** |
| 2 | reactive_stop | 沒有 resume ramp / hold — 二元切換「停 → 全速」 | **demo 致命** |
| 3 | reactive_stop | danger=0.6m 是 D435 ROI 時代沿用，沒對 Go2 機械尺寸 (機鼻在 base_link 前 ~0.40m) 校準 | **demo 致命** |
| 4 | reactive_stop | 沒 slow zone 漸進減速（safety_only 連 slow 也不發） | **demo 級** |
| 5 | Nav2 | local_costmap.obstacle_max_range=1.8m，遠小於 RPLIDAR 8m 視距 → controller 對 1.8m+ 障礙視而不見 | **demo 致命** |
| 6 | Nav2 | D435 完全沒整合進 obstacle_layer，只當 Bool gate；近距盲區（LiDAR 看不到的腳邊低物）無人管 | **demo 級** |

「demo 致命」= 不修 5/18 demo 不能上場。
「demo 級」= 不修 demo 會有看得到的不穩定但能 hack 過。

---

## 2. 文件層 root cause（為什麼今天才發現）

來自 subagent 1 的歷史考古：

```
2026-03-25  D435 ROI 方案定案 → danger=0.6m / slow=1.0m（D435 規格邊界）
2026-04-14  決定加買 RPLIDAR
2026-04-24  RPLIDAR 到貨 → 架構翻案：D435 ROI 改 RPLIDAR + cartographer + Nav2
            ⚠️ 沿用了 0.6m / 1.0m 閾值，沒對新感測器 + 新 mount + Go2 機鼻位置重算
2026-05-01  capability gate 上線 → safety_only mode 假設只配 teleop
            ⚠️ 沒考慮 Nav2 整合後 clear zone 的「誰負責漸進減速」
2026-05-10  demo spec freeze → P0 nav 進入主舞台
            ⚠️ 沒人 review 過去設計參數是否仍適用
2026-05-11  撞牆
```

**流程 bug**：每次架構翻案沒做「過去設計參數是否仍適用」的 audit。

`docs/navigation/CLAUDE.md` 5/1 寫過「safety_only=true ... clear zone 會 0.60 m/s shadow nav」，但被當成工程細節，沒升等成「設計缺陷」。

---

## 3. 當前 stack dataflow（code 確認）

```
┌─ 感測器 ─────────────────────────────────────────────┐
│ RPLIDAR A2M12  → /scan_rplidar (LaserScan, 10Hz)     │
│ D435           → /camera/camera/aligned_depth_to_color│
│                  (16UC1, 30Hz, 640x480)              │
│ Go2 odom       → /odom + TF: odom→base_link          │
│ TF static      → base_link→laser (x=0.175, z=0.18,   │
│                  yaw=π) ← LiDAR 反裝                 │
└──────────────────────────────────────────────────────┘
            ↓                          ↓
┌─ 感測器處理 ─────────────────────────────────────────┐
│ reactive_stop_node (訂 /scan_rplidar)                │
│  ├ params: danger=0.6m, slow=1.0m, front=±30°,       │
│  │         front_offset_rad=π                        │
│  ├ safety_only=true → clear/slow 完全不發            │
│  ├ 發 /cmd_vel_obstacle (Twist, 10Hz, RELIABLE)      │
│  └ 發 /state/reactive_stop/status (String JSON)      │
│                                                       │
│ depth_safety_node (訂 D435 depth)                    │
│  ├ stop_distance=0.4m, ROI=25%×40%, danger_ratio=20% │
│  ├ 發 /capability/depth_clear (Bool, 5Hz, latched)   │
│  └ fail-closed: false if frame_age > 1.0s            │
│                                                       │
│ ⚠️ D435 完全沒進 Nav2 costmap！只當 capability gate   │
└──────────────────────────────────────────────────────┘
            ↓
┌─ Nav2 stack ─────────────────────────────────────────┐
│ Nav2 BT navigator                                    │
│ ├ AMCL: scan_topic=/scan_rplidar, max_range=8.0m     │
│ ├ SmacPlannerHybrid (global) — 看 obstacle_max=2.5m  │
│ ├ DWB controller — 看 obstacle_max=1.8m ⚠️           │
│ ├ Footprint: [0.3, ±0.15] (0.6×0.30)                 │
│ ├ min_vel_x=0.45, max_vel_x=0.70                     │
│ └ 發 /cmd_vel_nav (Twist)                            │
└──────────────────────────────────────────────────────┘
            ↓
┌─ twist_mux 仲裁 ─────────────────────────────────────┐
│ priorities: emergency(255) > obstacle(200)           │
│             > teleop(100) > nav2(10)                 │
│ timeouts: 各 0.5s                                    │
│                                                       │
│ ⚠️ 漏洞：reactive_stop clear 沉默後 0.5s timeout →   │
│    mux 切到次優先 (teleop 100, 可能 nav 10)，         │
│    沒有「需要重新 confirm」的 gate                    │
│                                                       │
│ 發 /cmd_vel (mux 仲裁結果)                            │
└──────────────────────────────────────────────────────┘
            ↓
┌─ Go2 driver (StopMove fix 後) ───────────────────────┐
│ robot_control_service.handle_cmd_vel()               │
│ ├ deadband ±0.01, clamp x∈[-0.5,0.5]                 │
│ ├ post-deadband zero → StopMove (api_id=1003)        │
│ ├ 1Hz dedupe（防 reactive 10Hz spam）                │
│ └ 非零 → Move (api_id=1008)                          │
│                                                       │
│ webrtc_adapter — DataChannel send                    │
│ └ buffer backlog 警告 64KB / error 512KB             │
└──────────────────────────────────────────────────────┘
            ↓
       Go2 Sport Mode (MIN_X=0.5 m/s 門檻)
```

---

## 4. 業界 best practice 對照（subagent 3）

### 4.1 感測器分工
- **LiDAR 主，D435 補**：LiDAR 360° 長距離、低處理開銷；D435 補 LiDAR 平面打不到的盲區（地面/腳邊低物、高處懸掛、玻璃對 LiDAR 雷）
- 居家場景強烈建議**兩個都上**（玻璃門 / 黑色家具 / 桌椅腳對 LiDAR 是 failure mode）

### 4.2 三段 zone 推薦（quadruped + 0.5 m/s）

| Zone | 機鼻距離 | Action | 對應 LiDAR 視距（base_link 前 0.175m）|
|---|---|---|---|
| **Danger** | 0.10-0.15m | 緊急停 | LiDAR 0.45-0.55m |
| **Slow** | 0.40-0.60m | linear ramp 0.3-0.5×nominal | LiDAR 0.80-1.00m |
| **Clear** | >0.6m | 全速 / Nav2 | LiDAR >1.0m |

**Hysteresis**：進 zone 立即觸發，**離開後 hold 1.0-2.0s** 才升級。

### 4.3 Resume gate（demo 級簡化）
```
clear 觸發 → hold 1.5s → velocity ramp 0 → nominal (0.5s) → release
```
直接 boolean flip 是撞牆 #1 主因。

### 4.4 業界標準是 Nav2 collision_monitor，不是自製 reactive_stop
- `nav2_collision_monitor` 直接掛 controller_server 下游 filter cmd_vel
- 三 model：Stop / Slowdown / Approach（基於 TTC）
- 跟 obstacle_layer 不衝突，是 Nav2 官方設計
- **Demo 後遷移；demo 前先把 reactive_stop 補完**

### 4.5 Nav2 雙感測器 obstacle_layer 最小設定
```yaml
local_costmap:
  plugins: ["voxel_layer", "inflation_layer"]
  voxel_layer:
    observation_sources: scan pointcloud
    scan:        # RPLIDAR
      topic: /scan_rplidar
      obstacle_max_range: 8.0      # ← 不是 1.8！
      raytrace_max_range: 10.0
    pointcloud:  # D435
      topic: /camera/camera/depth/color/points  # 或 /scan_d435
      data_type: PointCloud2
      min_obstacle_height: 0.10    # 過濾地板
      max_obstacle_height: 1.5
      obstacle_max_range: 2.5
      raytrace_max_range: 3.0
  inflation_layer:
    inflation_radius: 0.45         # Go2 半徑 0.35 + 0.10 buffer
```

### 4.6 公開參考（subagent 3 找的）
- **eppl-erau-db/amigo_ros2** — Go2 + Jetson + D435i + RPLIDAR A3 完整 ROS2 整合（最接近 PawAI 配置）
- **abizovnuralem/go2_ros2_sdk** — 已 fork
- **Sayantani-Bhattacharya/unitree_go2_nav** — Go2 + Nav2 + SLAM
- **OpenMind/OM1-ros2-sdk** — RPLIDAR + SLAM + Nav2
- arXiv 2410.00572 — quadruped reactive avoidance

---

## 5. 修法路線圖

### Tier 0 — 5/12 早 AM 必修（demo 致命）

| # | 修法 | 檔案 | 工時 |
|:-:|---|---|:-:|
| **T0.1** | reactive_stop clear/slow 也低頻發 cmd_vel（防 mux timeout）| `reactive_stop_node.py:185-197` | 30 min |
| **T0.2** | danger 0.6→0.50m（緊急停），slow 1.0→0.85m，加 slowdown_ratio | `reactive_stop_node.py:51-58` + 啟動 script | 30 min |
| **T0.3** | 加 hysteresis + resume hold 1.5s + velocity ramp 0.5s | `reactive_stop_node.py` 新 logic | 1.5h |
| **T0.4** | local_costmap.obstacle_max_range 1.8→3.0m（與 RPLIDAR 視距一致）| `nav2_params.yaml:231` | 5 min + 實機驗 |
| **T0.5** | clear_debounce_frames 3→5 + 改時間門檻 0.5s | `reactive_stop_node.py:62` | 15 min |
| **T0.6** | 修法落地後重測 B5 motion，確認新閾值在 0.2 m/s 慢速也安全 | Jetson 實機 | 1h |

T0 全部 ~4 小時。**做完才能 motion 測**。

### Tier 1 — 5/12 PM / 5/13 場測前（demo 級）

| # | 修法 | 檔案 | 工時 |
|:-:|---|---|:-:|
| T1.1 | D435 啟動 `depth_to_laserscan` 或 PointCloud2 → 加進 obstacle_layer 第二個 observation source | 新 launch + `nav2_params.yaml` | 2-3h |
| T1.2 | base_link → laser TF 精量到 ±0.01m（卡尺 + 地圖對齊驗證） | TF static publisher | 1h |
| T1.3 | front_offset_rad 改名 `laser_to_physical_front_rad` + docstring 註明跟 TF yaw 的關係 | `reactive_stop_node.py:56-58` + `lidar_geometry.py` | 30 min |
| T1.4 | DWB min_vel_x 確認 ≥0.45 + footprint 改成實際 0.65×0.30 | `nav2_params.yaml` | 30 min |
| T1.5 | Nav2 inflation_radius 0.30→0.45（Go2 半徑 0.35 + 0.10 buffer） | `nav2_params.yaml` | 5 min + 實機 |
| T1.6 | reactive_stop status 加診斷欄位（clear_streak / hysteresis_timer） | `reactive_stop_node.py` | 30 min |

### Tier 2 — Demo 後

| # | 修法 |
|:-:|---|
| T2.1 | 切換到 Nav2 collision_monitor（Stop/Slowdown/Approach 三 polygon），棄用自製 reactive_stop |
| T2.2 | base_link projection — 用 TF 算「機鼻到障礙物」距離，自適應 mount 改變 |
| T2.3 | STVL spatio-temporal voxel layer 取代 VoxelLayer（對 RealSense 更穩） |
| T2.4 | 動態障礙跟蹤（temporal tracking + Kalman），降低 zone bouncing |

---

## 6. 5/12 早 AM 落地計畫（給 Roy 直接執行）

```bash
# Step 1: 拿這份 audit 上 Jetson
~/sync once

# Step 2: 改 reactive_stop_node.py（T0.1 + T0.2 + T0.3 + T0.5）
#   - safety_only mode：clear 也發 0（低頻 1Hz refresh，避免完全沉默）
#   - slow zone 發 slow_speed=0.20 m/s（or 0 if MIN_X 限制）
#   - resume_hold_sec=1.5, resume_ramp_sec=0.5
#   - clear_debounce 改時間門檻 0.5s

# Step 3: 改 nav2_params.yaml（T0.4 + T1.5）
#   - local_costmap obstacle_max_range: 1.8 → 3.0
#   - inflation_radius: 0.30 → 0.45

# Step 4: 改啟動 script danger/slow params
#   start_reactive_stop_tmux.sh + start_nav_capability_demo_tmux.sh
#   -p danger_distance_m:=0.50 -p slow_distance_m:=0.85

# Step 5: Jetson rebuild
ssh jetson-nano "cd ~/elder_and_dog && colcon build --packages-select go2_robot_sdk"

# Step 6: B5 motion 重測（先用 0.2 m/s 慢速，不是 0.5）
#   驗收順序：danger 鎖死 → 移開 → hold 1.5s → ramp 0→0.2 → 再放回 → 立即停
```

**5/13 場測前必過的驗收**：
- (a) reactive_stop danger 鎖死 100%（10 次中 0 次穿過）
- (b) clear → resume 速度 ramp 可見（不是一次跳到 0.5）
- (c) Nav2 看得到 3m 外障礙（Foxglove 看 local_costmap inflation 範圍對）
- (d) 連續 30 秒在有障礙環境跑不撞

---

## 7. 與其他文件的關係

- **取代**：`docs/navigation/CLAUDE.md` 中關於 reactive_stop 參數的舊敘述（5/1 「safety_only ... clear zone 會 shadow nav」需更新成 5/11 audit 結論）
- **取代**：`docs/navigation/research/2026-03-25-reactive-obstacle-avoidance.md` §4.4 的 0.6m/1.0m 閾值
- **被引用於**：`docs/pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md §4 B5`、`references/project-status.md`
- **未影響**：`docs/contracts/interaction_contract.md`（topic 沒變）、`docs/mission/`（專案方向沒變）

---

## 8. 三 subagent 報告原文位置（轉錄已壓縮）

完整原始輸出留在當天 conversation log。本檔已綜合三方共識：
- **Subagent 1（local docs audit）**：時間線重建 + docs 預警證據 + 5 個盲點
- **Subagent 2（local code audit）**：dataflow 完整圖 + 7 個 Q&A + Nav2 obstacle_max_range 1.8m 是新發現
- **Subagent 3（網路 best practice）**：collision_monitor 推薦 + 三段 zone 參數 + 公開參考專案

---

## 9. 結論

今天「導航避障到底是不是空間問題」的答案：

**不是。今天抓到 6 層真系統設計缺陷，跟空間無關**。學校大空間能掩蓋部分問題（更多反應時間），但 reactive_stop / mux / Nav2 / D435 的結構性漏洞還在，demo 上場仍會撞。

**5/12 早 AM 必須做完 Tier 0 六項才能繼續 B5 motion 測試**。Tier 1 在 5/12-5/13 場測前完成。Tier 2 留 demo 後。

如果 5/12 中午 Tier 0 沒做完 → demo 走降級路徑（reactive_stop 單獨 demo / 純靜態 demo），不上 nav。

---

**End of Architecture Deep Audit — 2026-05-11 night**
