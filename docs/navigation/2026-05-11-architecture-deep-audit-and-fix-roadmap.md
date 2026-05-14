# Navigation Architecture Deep Audit — 5/11 撞牆事件根因 + 修法路線圖

> **Status**: authoritative
> **Date**: 2026-05-11 night
> **Scope**: 完整盤點 PawAI 導航避障 stack（RPLIDAR + D435 + reactive_stop + twist_mux + Nav2 + Go2 driver）的設計缺陷，給出 demo 前能落地的修法。
> **Trigger**: 5/11 B5 burndown 在家裡 motion 測試時 Go2 撞到 1.5m 處障礙物。經三線並行調查（local docs / local code / 網路 best practice）發現問題不只一個。
> **Authority**: 本檔取代任何 reactive_stop 參數、Nav2 obstacle_layer 配置、感測器分工的舊敘述。`docs/navigation/CLAUDE.md` 與 `docs/pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md §4` 引用本檔。

---

## 0. TL;DR

> ⚠️ **2026-05-11 night errata（Roy 訂正）**：原版本把「修一件解 80%」放在 Nav2 obstacle_max_range，方向錯。1.5m 仍在 Nav2 1.8m 視距內，**那不是主因**。**真正主因 = reactive_stop release gate 漏洞**（clear zone 沉默 → mux 0.5s timeout → 控制權還給仍在發 0.5 m/s 的 `/cmd_vel_joy` teleop）。修法路線見 §6（已重排）。

**撞牆不是單一 bug，是多層設計缺陷疊加**。修法 P0 順序（按 Roy 5/11 night 訂正）：

1. **Release gate** — reactive_stop 在 clear/slow zone 也持續發 0（不要沉默），讓 mux 不 timeout 把控制權還給舊命令
2. **Test discipline** — kill teleop publisher，不允許 0.5 m/s hot-publish
3. **Threshold enlarge**（保守）：`danger 0.6→1.1m / slow 1.0→1.7m`（LiDAR 視距）—**不是 audit 原版寫的縮小到 0.5m**（方向相反）
4. Nav2 `obstacle_max_range 1.8→3.0` 是 enhancement，不是 P0 主因（1.5m 仍在 1.8m 內）
5. D435 主線整合留 demo 後（detour profile 5/03 spec 已存在）

完整 6 層缺陷見 §1.2，分層修法見 §6。

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
        ⚠️ 原 audit 寫「Nav2 obstacle_max_range=1.8m 看不到 1.5m+ 障礙」是錯的：
        1.5m 仍在 1.8m 視距內，Nav2 看得到。但本次 mux 走 teleop 不走 nav，
        Nav2 視野範圍跟撞牆無關。把 obstacle_max_range 拉大是 enhancement、
        不是 P0 修法。
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

### 1.2 撞牆缺陷層級（Roy 5/11 訂正後）

| # | 層 | 缺陷 | 嚴重度 |
|:---:|---|---|:---:|
| 1 | reactive_stop | safety_only 在 clear/slow zone 完全沉默 → mux 0.5s timeout 後 teleop priority 100 接管，舊 0.5 m/s 自動恢復 | **🔴 demo 致命（真主因）** |
| 2 | reactive_stop | clear 是「解除煞車」不是「安全恢復」— 沒有「需要重新確認新命令」的 gate | **🔴 demo 致命（真主因）** |
| 3 | reactive_stop | danger=0.6m 對 Go2 機身太近（LiDAR 視距，機鼻在 base_link 前 ~0.40m）。**修法應 enlarge 到 1.1-1.2m**（保守 demo 安全），不是縮小 | **demo 級** |
| 4 | test protocol | B5 測試時 `/cmd_vel_joy` 持續 hot-publish 0.5 m/s — clear 後立刻接管。test 紀律問題、不只是代碼 | **demo 致命（協議級）** |
| 5 | Nav2 | local_costmap.obstacle_max_range=1.8m vs RPLIDAR 8m 視距 — **enhancement 不是主因**（1.5m 仍在 1.8m 內、Nav2 看得到，且本次 mux 走 teleop 不走 nav） | **demo 級 enhancement** |
| 6 | Nav2 | D435 主線未進 obstacle_layer。**detour profile** 已在 `2026-05-03-d435-rplidar-fusion-detour.md` 設計 `/scan_d435 + d435_scan` 配置，但非 demo 主線 | **demo 級 enhancement** |

「demo 致命」= 不修 demo 不能上 nav 段。
「demo 級 enhancement」= demo 後做、不是這次撞牆主因。

**Roy 訂正前的版本錯誤地把 #5（Nav2 視距）標為 demo 致命**，實際它跟今天撞牆無關。今天撞牆的真因鎖在 #1 + #2 + #4。

---

## 2. 文件層 root cause（為什麼今天才發現）

來自 subagent 1 + 2 的歷史考古（Roy 5/11 訂正後）：

```
2026-03-25  D435 ROI 方案定案 → stop_threshold=0.8m / slow_threshold=1.5m
            （reactive_stop_research.md L344-345 / 451-452 親自確認）
            注意：不是後來的 0.6/1.0
2026-04-14  決定加買 RPLIDAR（D435 鏡頭角度限制上機全失敗，4/3 停用）
2026-04-24  RPLIDAR 到貨 → 架構翻案：D435 ROI 改 RPLIDAR + cartographer + Nav2
            ⚠️ 此時 reactive_stop_node.py 預設值改成 danger=0.6m / slow=1.0m
               — 無 decision log、無 commit message 解釋為何從 0.8/1.5 改 0.6/1.0
            ⚠️ 沒對新感測器 + 新 mount（LiDAR 反裝 yaw=π）+ Go2 機鼻位置重算
2026-05-01  capability gate 上線 → safety_only mode 假設只配 teleop
            ⚠️ 沒考慮 Nav2 / teleop 持續 publish 場景下 clear zone 沉默的後果
2026-05-03  detour profile 設計（`2026-05-03-d435-rplidar-fusion-detour.md`）
            含 `/scan_d435 + d435_scan` Phase 1/2 配置 — 但「不接 main local_costmap」
            是明確設計（CLAUDE.md「D435 是 safety gate，不接進 Nav2 local costmap」）
2026-05-10  demo spec freeze → P0 nav 進入主舞台
            ⚠️ 沒人 review「safety_only clear zone 沉默 + teleop hot-publish 後果」
2026-05-11  撞牆
```

**流程 bug**：每次架構翻案沒做「舊參數是否仍適用 + 上下游語境是否變了」的 audit。

`docs/navigation/CLAUDE.md` 5/1 寫過「safety_only ... clear zone shadow nav」警告，但被當成工程細節，沒升等成「demo 致命設計缺陷」。

**0.6/1.0 真正源頭 verdict（subagent 1 考古結論）**：⭐⭐ 推測為 4/24 RPLIDAR 整合時隨手改值，無記錄、無 review。**不是 3/25 D435 ROI 方案的繼承**（那邊明確是 0.8/1.5）。

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
│ ⚠️ D435 主線未進 Nav2 costmap（明確設計）              │
│   detour profile 已在 2026-05-03 spec 設計            │
│   `/scan_d435 + d435_scan` 但 demo 後再落地           │
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

## 5. 修法路線圖（2026-05-11 night Roy 訂正後）

> ⚠️ **重要：reactive_stop 永遠只發 0、不發任何正速度**。
> `/cmd_vel_obstacle` priority **200**（高於 teleop 100 / nav 10）= **主動命令通道**，不是被動限速。
> 在 slow zone 發 0.2 m/s 等於「主動命令 Go2 走 0.2 m/s」— 不是「限制」。
> 因此 reactive_stop 的工作是「鎖死前進」直到上游主動清掉舊命令或重發新命令。

### B0 — Critical Path（5/12 早 AM 必修，~3h，做完才能 motion 重測）

| # | 修法 | 檔案 | 工時 |
|:-:|---|---|:-:|
| **B0.1** | **Release gate（hold 0）**：clear/slow zone 持續 publish `Twist(0)` 到 `/cmd_vel_obstacle`（仍 priority 200），讓 mux 不 0.5s timeout 把控制權交還給 teleop。reactive_stop 在任何 zone 都只發 0，永不發正速度 | `reactive_stop_node._tick()` | 45 min |
| **B0.2** | **Teleop 殘留 protocol**：B5 motion 測試 protocol 寫死「測試前必 kill `/cmd_vel_joy` publisher」，改用「人工發單個短脈衝命令」模擬 nav goal | `nav-root-cause-burndown.md §B5 protocol` | 15 min docs |
| **B0.3** | **Threshold enlarge（保守）**：`danger 0.6→1.1m` / `slow 1.0→1.7m`（LiDAR 視距）。給 Go2 機鼻 + 反應時間 + 慣性 buffer。**方向是 enlarge，不是縮小** | `reactive_stop_node.py:51-52` 預設 + `scripts/start_*_tmux.sh` 啟動 param | 15 min |
| **B0.4** | **Hysteresis / hold timer**：clear_debounce 從 frame count(3) 改時間門檻 0.5s + 出 zone hold 1.0-1.5s 才升級。`/cmd_vel_obstacle` 在 clear zone 仍持續發 0，避免抖動 | `reactive_stop_node.py:62, 174-179` | 30 min |
| **B0.5** | **慢速 + 人工 e-stop test protocol**：B5 motion 重測用 `0.15-0.2 m/s` 慢速、單脈衝命令、e-stop / Ctrl-C 隨手 | docs only | 15 min |
| **B0.6** | Unit tests 覆蓋 release gate（所有 zone 持續發 0）+ hysteresis（時間門檻）+ threshold（1.1/1.7）。仿 `test_robot_control_service.py` 11 條 mock controller pattern | `go2_robot_sdk/test/test_reactive_stop_release_gate.py` 新 | 45 min |

**B0 不做**（嚴格）：
- ❌ reactive_stop 發任何正速度（即使是 0.2 m/s 限速也不行）
- ❌ velocity ramp（reactive_stop 沒這責任，ramp 是 nav controller 的工作）
- ❌ 自動「障礙清除後恢復前進」邏輯

### B1 — Demo readiness（5/12 PM / 5/13 場測前，~3h）

> ⚠️ **B1.1 不是剛剛撞牆主因**（1.5m 在 1.8m 內、Nav2 看得到，且本次 mux 走 teleop 不走 nav）。**enhancement，不要排在 release gate 前**。

| # | 修法 | 檔案 | 工時 |
|:-:|---|---|:-:|
| B1.1 | local_costmap.obstacle_max_range 1.8→3.0（與 RPLIDAR 8m 視距更接近，提早規劃繞行；**enhancement**）| `nav2_params.yaml:231` | 5 min + 實機 |
| B1.2 | inflation_radius 0.30→0.45（Go2 半徑 0.35 + 0.10 buffer） | `nav2_params.yaml` | 5 min |
| B1.3 | Footprint 改實際 0.65×0.30 | `nav2_params.yaml` | 5 min |
| B1.4 | base_link → laser TF 精量到 ±0.01m（卡尺 + Foxglove `/scan_rplidar` 對齊驗證） | static TF launch | 1h |
| B1.5 | front_offset_rad 改名 `laser_to_physical_front_rad` + docstring 註明跟 TF yaw=π 的雙重套用關係 | `reactive_stop_node.py:56-58` + `lidar_geometry.py:20-22` | 30 min |
| B1.6 | reactive_stop status JSON 加診斷欄位（clear_streak / hysteresis_timer / since_last_zone_change） | `reactive_stop_node._tick_status()` | 30 min |

### B2 — Demo 後

| # | 修法 |
|:-:|---|
| B2.1 | D435 detour profile 從 spec 落地（按 `2026-05-03-d435-rplidar-fusion-detour.md` Phase 1 → 2，加進 main local_costmap）|
| B2.2 | base_link projection — 用 TF 算「機鼻到障礙物」距離，threshold 改成機鼻距離（自適應 mount 改變） |
| B2.3 | 切換到 Nav2 collision_monitor（業界標準三 polygon Stop/Slowdown/Approach），棄用自製 reactive_stop |
| B2.4 | STVL spatio-temporal voxel layer 取代 VoxelLayer（對 RealSense motion blur 更穩） |
| B2.5 | 動態障礙物跟蹤（temporal tracking + Kalman），降低 zone bouncing |

### B3 — 流程性修法（避免下次架構翻案再踩同樣坑）

| # | 修法 | 狀態 |
|:-:|---|:-:|
| B3.1 | `docs/navigation/CLAUDE.md` 把「safety_only clear zone shadow nav」升等成 architecture-critical 段落，故事化描述 + 4-mode 表格 + 釋放策略 | ✅ commit `0f5a16f` |
| B3.2 | nav 相關 spec 任何 threshold 改動必填「decision log」段（防 0.6/1.0 那種無記錄漂移） | ⏳ demo 後 |
| B3.3 | 架構翻案 SOP checklist：每次翻案必跑「舊參數是否仍適用 + 上下游語境是否變」audit | ⏳ demo 後 |

---

### B0 → 4-mode 演進（5/11 night Roy review 重設計）

**B0.1 命名陷阱**：原 B0.1 把 `safety_only=True` 的「always publish 0」叫 release gate，但實質是 permanent brake，**不是釋放閘**。Roy 5/11 night code review 點出 4 個衍生 bug：

| # | Roy review bug | 修法 |
|:-:|---|---|
| 1 | nav_capability 主腳本啟 hold_brake → mux priority 200 鎖死 → nav goal 永遠不會穿過 mux | 改 `mode=progressive`（搭配 teleop discipline） |
| 2 | 註解寫「kill teleop」但腳本透過 `robot.launch.py` 啟 teleop_twist_joy + joy_node | 改加 `teleop:=false joystick:=false` enforcement |
| 3 | enable_nav_pause 在 hold_brake 下發 /nav/resume → nav state vs mux 矛盾 | hold_brake 下不發 resume；progressive 下發 warn log |
| 4 | safety_hold script 沒啟 mux → cmd_vel_obstacle 沒人 subscribe → hold_brake 不生效 | 改用 `robot.launch.py teleop:=false joystick:=false`（含 mux）|

**4-mode 狀態機取代 binary safety_only**（commit `0f5a16f` + `d804a58`）：

| mode | 行為 | 用途 | 啟動 script |
|---|---|---|---|
| `hold_brake` | 永遠 publish 0 到 /cmd_vel_obstacle | B5 stop 驗證 / demo emergency | `start_reactive_stop_safety_hold_tmux.sh`（**新建**）|
| `progressive` | danger=0、slow/clear silent | nav 主驅動（必 kill teleop） | `start_nav_capability_demo_tmux.sh`（改）|
| `released` | 不 publish，LiDAR + zone 仍更新 | 操作員主動釋放 | runtime `ros2 param set` |
| `disabled` | 完全 off | 全停 reactive 影響 | runtime `ros2 param set` |
| `""` | standalone（0/slow/normal） | nav 不在的 demo 備援 | `start_reactive_stop_tmux.sh`（改）|

`safety_only=True` 自動 promote 到 `mode=hold_brake` 維持向後相容。

**釋放策略**（取代「主動發新 nav goal」單步驟）：
1. `ros2 param set /reactive_stop_node mode released` 或 `disabled`
2. `pkill -f teleop_twist_joy && pkill -f teleop_twist_keyboard`（清殘留 hot-publisher）
3. 主動發 nav goal（單脈衝命令，不要 `-r` hot-publish）
4. **三步缺一個 Go2 都不會走**

3 個啟動 script 互斥使用（cmd_vel_obstacle / cmd_vel 雙 publisher 衝突）。

---

## 6. 5/12 早 AM 落地計畫（Roy 訂正 + 4-mode 重設計後）

### 已完成（5/11 night code 全部落地，commits `4ec8350` → `f366acd` → `0f5a16f` → `d804a58`）

- ✅ B0.1 release gate（4-mode state machine 取代「always publish 0」單一邏輯）
- ✅ B0.3 threshold 1.1 / 1.7
- ✅ B0.4 hysteresis 5 frames（≈0.5s）
- ✅ B0.6 unit tests 42 條（69 passed 含既有）
- ✅ B1.5 lidar_geometry docstring 4-mode + double-yaw 雙重套用警告
- ✅ B1.6 status JSON 診斷欄位（mode / publishes_zero_continuously / threshold / clear_streak / since_last_zone_change_sec）
- ✅ scripts 拆 3 種模式（safety_hold / progressive 在 nav_capability / standalone）
- ✅ docs/navigation/CLAUDE.md B3.1 升等 architecture-critical
- ✅ Roy review 4 bug fix（mux 啟動、teleop enforce、resume warn、test per-mode）

### 5/12 早 AM 剩餘（~1h）

```bash
# Step 0: 處理 working tree 殘留（5/11 沒解的）
cd /home/roy422/newLife/elder_and_dog
git status
# M docs/pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md（drift，待 Roy 決定）
# D docs/pawai-brain/plans/2026-05-12-reactive-stop-safety-fix-plan.md（68fe29b 創、被刪）
# 三選一：(a) restore 後合併、(b) 內容 merge 進本 audit / 4-mode 段落、(c) commit 當前狀態

# Step 1: Sync to Jetson + colcon build
~/sync once && ssh jetson-nano "cd ~/elder_and_dog && colcon build --packages-select go2_robot_sdk"

# Step 2: B5 motion 重測（kill teleop / 慢速 / 三 script 各跑一次）
#   2a. start_reactive_stop_safety_hold_tmux.sh（hold_brake 鎖死驗證）
#       場景：物體放 0.5m / 1.5m / 拔 USB 三 case，每 case 看 /cmd_vel = 0
#   2b. ros2 param set /reactive_stop_node mode released（驗證釋放）
#   2c. start_nav_capability_demo_tmux.sh（progressive 模式）
#       場景：發 goto_relative 0.3m，物體放/移開，看 zone 與 nav 行為
```

### B1 — Demo readiness（5/12 PM 或 5/13 場測前，~1.5h，**enhancement 不是 P0 fix**）

仍需做（不影響 5/12 早 AM B5 重測）：

- B1.1 nav2_params.yaml local_costmap.obstacle_max_range 1.8 → 3.0
- B1.2 inflation_radius 0.30 → 0.45
- B1.3 footprint 改 0.65×0.30
- B1.4 base_link → laser TF 精量到 ±0.01m

**5/13 場測前必過的驗收**：
- (a) reactive_stop danger 鎖死 100%（10 次中 0 次穿過）
- (b) **kill teleop + 移開物體**：Go2 不會自動恢復前進（核心修法驗收）
- (c) **不 kill teleop + 移開物體**：reactive_stop 仍蓋住 teleop 0.5、Go2 不撞（safety net）
- (d) 連續 30 秒在有障礙環境跑不撞、無 mux timeout 切換到 teleop 的 log

---

## 7. 與其他文件的關係

- **取代**：`docs/navigation/CLAUDE.md` 中關於 reactive_stop 參數的舊敘述（5/1 「safety_only ... clear zone 會 shadow nav」需 B3.1 升等成 architecture-critical）
- **與 `docs/navigation/research/2026-03-25-reactive-obstacle-avoidance.md` 關係**：3/25 文件用的是 `stop_threshold=0.8 / slow_threshold=1.5`（原始 D435 ROI 方案）；4/24 RPLIDAR 整合時改成 `0.6 / 1.0` 無 decision log。本檔 B0.3 把它再 enlarge 回 `1.1 / 1.7`（保守 demo 安全）
- **與 `docs/navigation/specs/2026-05-03-d435-rplidar-fusion-detour.md` 關係**：detour profile（`/scan_d435 + d435_scan`）已設計，但 demo 期不啟用、demo 後 B2.1 才落地
- **被引用於**：`docs/pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md §4 B5`、`references/project-status.md`
- **未影響**：`docs/contracts/interaction_contract.md`（topic 沒變）、`docs/mission/`（專案方向沒變）

---

## 8. 三 subagent 報告原文位置（轉錄已壓縮）

完整原始輸出留在當天 conversation log。本檔已綜合三方共識：
- **Subagent 1（local docs audit）**：時間線重建 + docs 預警證據 + 5 個盲點
- **Subagent 2（local code audit）**：dataflow 完整圖 + 7 個 Q&A + Nav2 obstacle_max_range 1.8m 是新發現
- **Subagent 3（網路 best practice）**：collision_monitor 推薦 + 三段 zone 參數 + 公開參考專案

---

## 9. 結論（Roy 5/11 night 訂正後）

今天「導航避障到底是不是空間問題」的答案：

**不是。但也不是 Nav2 視野不夠遠**。真正主因是 **reactive_stop release gate 漏洞** — clear zone 沉默後 mux 0.5s timeout，把控制權還給仍在發 0.5 m/s 的 `/cmd_vel_joy`，「clear 不是安全恢復、只是解除煞車」。

學校大空間能給更多反應時間（緩解 #3 threshold 過近），但 #1 + #2 + #4 的 release gate / test discipline 漏洞**換到大空間還在**，demo 上場仍會撞。

**5/12 早 AM 必須做完 B0 六項才能繼續 B5 motion 測試**：
- B0.1 release gate（reactive_stop 在所有 zone 都發 0）
- B0.2 + B0.5 test discipline（kill teleop、慢速、單脈衝）
- B0.3 threshold enlarge（1.1 / 1.7 保守值）
- B0.4 hysteresis（時間門檻 + 出 zone hold）
- B0.6 unit tests

B1 在 5/12-5/13 場測前完成。B2 留 demo 後。B3 流程性修法非阻塞但 5/12 內要寫進 docs。

如果 5/12 中午 B0 沒做完 → demo 走降級路徑（reactive_stop 單獨 demo / 純靜態 demo），不上 nav。

---

**End of Architecture Deep Audit — 2026-05-11 night**
