# Nav 避障深度研究 — 5/11 撞牆事件 → 4-mode 重設計

> **Status**: research-frozen-after-fix
> **Date**: 2026-05-11 deep night（撞牆事件 + 三線 subagent 並行調查 + Roy 訂正 + 4-mode 重設計 + Roy code review 4 fix）
> **Owner**: Roy
> **Authority**: 本檔是研究與 todo 真相來源，**修法執行細節**見
> [`../2026-05-11-architecture-deep-audit-and-fix-roadmap.md`](../2026-05-11-architecture-deep-audit-and-fix-roadmap.md)。
> **取代**：`docs/pawai-brain/plans/2026-05-12-reactive-stop-safety-fix-plan.md`（68fe29b 創、被刪；Top 4 fix 多數被 4-mode 設計超越）。

---

## 0. Executive Summary

5/11 晚 Nav burndown B5 motion 階段 Go2 撞 1.5m 處障礙物。經三線 subagent 並行調查（local docs / local code / 網路 best practice）+ Roy 4 輪 code review 訂正後，找出**多層設計缺陷疊加**而非單一 bug。修法不是調個 threshold 而是**重設計 reactive_stop 的「永遠 publish 0」哲學成 4-mode 狀態機**。

關鍵洞察：

1. **真主因不是 Nav2 視野不夠遠**（1.5m 在 1.8m 內，Nav2 看得到），是 reactive_stop 在 clear zone 沉默 → mux 0.5s timeout → 仍 hot-publishing 0.5 m/s 的 `/cmd_vel_joy` 接管。
2. **danger 0.6m 的歷史源頭沒人知道**：3/25 D435 ROI 設計用 0.8/1.5m，4/24 RPLIDAR 整合時隨手改成 0.6/1.0m，無 commit message、無 decision log。45 天三次架構翻案，從沒做「舊參數是否仍適用」的 audit。
3. **「永遠 publish 0」是 permanent brake，不是 release gate** — Roy 5/11 night 點出這個命名陷阱：它把 nav_capability 主路徑鎖死，nav goal 永遠不會穿過 mux。修法是把 binary `safety_only` 升級成 4-mode 狀態機（`hold_brake` / `progressive` / `released` / `disabled` / `""`）。
4. **業界標準是 `nav2_collision_monitor`**，不是自製 reactive_stop。長期遷移目標但 demo 後做。

修法分 4 階段：
- **B0** Critical Path（5/11 night ✅ code 已落地）— 4-mode 狀態機 + threshold 1.1/1.7 + hysteresis + 69 tests
- **B1** Demo readiness（5/12-5/13）— Nav2 obstacle_max_range / inflation / footprint / TF 精量
- **B2** Demo 後 — D435 fusion / base_link projection / collision_monitor 遷移
- **B3** 流程性修法 — CLAUDE.md 升等（✅）/ decision log 規範 / 翻案 SOP

---

## 1. Background — 撞牆事件完整重建

### 1.1 物理時序

```
t=0s    物體放 Go2 前方 0.5m → reactive_stop zone=danger
        /cmd_vel_obstacle 持續發 0 @10Hz
        teleop 持續發 0.5 m/s @10Hz 在 /cmd_vel_joy
        mux：obstacle priority 200 蓋過 teleop 100 → /cmd_vel = 0
        Go2 站著不動 ✅

t=86s   Roy 移開物體 → zone 從 danger → slow → clear
        舊版 safety_only=true 在 clear/slow 完全沉默

t=86.5s mux 等不到 obstacle channel 訊號 0.5s → timeout → 切 teleop priority 100
        /cmd_vel = 0.5 m/s
        Go2 driver 收到 0.5 → Move (api_id=1008) → Go2 開始走

t=86-91s Go2 全速 0.5 m/s 走 5 秒 → 朝前方 1.5m 處的障礙物
        Nav2 不在這條路徑（teleop 直接穿過 mux）

t=91s   reactive_stop zone 進入 slow (front_min=0.97m)，但 safety_only 在 slow 也沉默
        Go2 繼續全速

t=92s   sensor noise 在 1m boundary 振盪 slow ↔ clear
        clear_debounce_frames=3 → 0.3s 連續 clear 才算 clear
        但 0.3s × 0.5 m/s = 0.15m，距離已大量逼近

t=93s   zone slow → danger (front_min=0.57m) → reactive_stop 終於 publish 0
        但 LiDAR 視距 0.57m 對應 Go2 機鼻只剩 0.57 - 0.40 = 0.17m
        加 0.5 m/s × 0.3s 反應 = 0.15m → 機鼻位移 = 0
撞
```

### 1.2 缺陷層級（Roy 5/11 訂正後）

| # | 層 | 缺陷 | 嚴重度 |
|:-:|---|---|:-:|
| 1 | reactive_stop | safety_only 在 clear/slow zone 完全沉默 → mux 0.5s timeout 後 teleop priority 100 接管 | 🔴 真主因 |
| 2 | reactive_stop | clear 是「解除煞車」不是「安全恢復」— 沒有「需要重新確認新命令」的 gate | 🔴 真主因 |
| 3 | reactive_stop | danger=0.6m 對 Go2 機身太近（LiDAR 視距 vs 機鼻位置）。**修法是 enlarge 到 1.1m 不是縮小** | demo 級 |
| 4 | test protocol | B5 測試時 `/cmd_vel_joy` 持續 hot-publish 0.5 m/s — clear 後立刻接管。協議級問題、不只代碼 | 🔴 真主因 |
| 5 | Nav2 | local_costmap.obstacle_max_range=1.8m vs RPLIDAR 8m — **enhancement 不是主因**（1.5m 在 1.8m 內） | 級 enhancement |
| 6 | Nav2 | D435 主線未進 obstacle_layer。detour profile 已設計但非主線 | 級 enhancement |

**真主因 = #1 + #2 + #4**。Nav2 視野範圍跟撞牆無關。

---

## 2. Investigation Methodology

### 2.1 三線並行 subagent 調查

| Subagent | 範疇 | 輸出 |
|---|---|---|
| **#1 Local docs** | 全 repo nav 相關 docs / 歷史 spec / archive | 設計演進時間線、踩過的坑、5 個盲點清單 |
| **#2 Local code** | reactive_stop / lidar_geometry / twist_mux / driver / Nav2 配置 | 7 個 Q&A、3 個新發現、code-level 修法位置 |
| **#3 網路 best practice** | Nav2 / Unitree Go2 / RPLIDAR + D435 fusion / collision_monitor | 業界三段 zone 參數、collision_monitor 推薦、5 公開參考專案 |

每個 subagent 控制 1500-1800 字輸出。

### 2.2 Roy 4 輪 code review

每輪 review 都修錯，無 review 不 commit：

| Review 輪 | 點出 bug 數 | 重點 |
|---|---|---|
| **Phase A errata** | 4 | obstacle_max_range claim / threshold direction / 0.6 origin / D435 detour |
| **B0 design check** | 4 | release gate 命名 / nav_capability 鎖死 / nav_pause 矛盾 / CLAUDE.md 釋放策略 |
| **4-mode review** | 4 | safety_hold mux 缺失 / nav_capability teleop 沒 enforce / progressive resume teleop / test stale |
| **後續 docs sync** | (進行中) | audit / project-status 同步當前 state |

---

## 3. Findings

### 3.1 文件層 root cause（為什麼今天才發現）

過去 45 天 3 次架構翻案，**每次都沒做「舊參數是否仍適用 + 上下游語境是否變」的 audit**：

```
2026-03-25  D435 ROI 方案定案 → stop_threshold=0.8m / slow_threshold=1.5m
            （research/2026-03-25-reactive-obstacle-avoidance.md L344-345）
2026-04-01  Full SLAM 永久棄用宣告（Go2 內建 LiDAR 18% 覆蓋）
2026-04-14  決定加買 RPLIDAR
2026-04-24  RPLIDAR 到貨 → 架構翻案：D435 ROI 改 RPLIDAR + cartographer + Nav2
            ⚠️ reactive_stop_node.py 預設值改成 danger=0.6m / slow=1.0m
               — 無 decision log、無 commit message、無 review
            ⚠️ 沿用了舊閾值，沒對新感測器 + 新 mount + Go2 機鼻位置重算
2026-05-01  capability gate 上線 → safety_only mode 假設只配 teleop
            ⚠️ 沒考慮 Nav2 / teleop hot-publish 場景下 clear zone 沉默後果
2026-05-03  detour profile 設計（spec/2026-05-03-d435-rplidar-fusion-detour.md）
            含 /scan_d435 + d435_scan Phase 1/2 配置；但 CLAUDE.md 明確寫
            「D435 是 safety gate，不接進 Nav2 local costmap」是設計決策
2026-05-10  demo spec freeze → P0 nav 進入主舞台
            ⚠️ 沒人 review「safety_only clear zone 沉默 + teleop hot-publish 後果」
2026-05-11  撞牆
```

`docs/navigation/CLAUDE.md` 5/1 寫過：

> reactive_stop_node `safety_only=true` 必須用於 mux 模式（priority 200）— **clear zone 會 0.60 m/s 永久 shadow nav**

但被當成「工程細節」沒升等成「設計缺陷」。Subagent 1 verdict：⭐⭐ 推測，無 review。

### 3.2 0.6/1.0 真實源頭考古

**Subagent 1 + grep 親自確認**：

| 日期 | 來源 | 值 |
|---|---|---|
| 2026-03-25 | `research/2026-03-25-reactive-obstacle-avoidance.md` L344-345, 451-452 | `stop_threshold=0.8m` / `slow_threshold=1.5m`（D435 ROI 方案）|
| 2026-04-24+ | `reactive_stop_node.py` 預設值改 `danger=0.6m` / `slow=1.0m` | **無 decision log** |

可信度 **⭐⭐ 推測**：
- 4/24 RPLIDAR 整合時改值，可能保守縮小（0.8 → 0.6 / 1.5 → 1.0）但無記錄
- 沒做與新感測器性能（RPLIDAR 10Hz vs D435 30Hz）配對的分析
- 沒做與 Go2 機械尺寸（機鼻在 base_link 前 0.4-0.6m）的對齊

**修法**：5/11 B0.3 enlarge 回 `danger=1.1m / slow=1.7m`（保守安全），不是縮小。

### 3.3 業界 best practice 對照（subagent 3）

#### 三段 zone 推薦（quadruped + 0.5 m/s）

| Zone | 機鼻距離 | 對應 LiDAR 視距（base_link 前 0.175m）| Action |
|---|---|---|---|
| **Danger** | 0.10-0.15m | LiDAR 0.45-0.55m | 緊急停 |
| **Slow** | 0.40-0.60m | LiDAR 0.80-1.00m | linear ramp 0.3-0.5×nominal |
| **Clear** | >0.6m | LiDAR >1.0m | 全速 / Nav2 |

**Hysteresis**：進 zone 立即觸發，**離 zone 後 hold 1.0-2.0s** 才升級。

#### Resume gate（demo 級簡化）

```
clear 觸發 → hold 1.5s → velocity ramp 0 → nominal (0.5s) → release
```

直接 boolean flip 是業界撞牆 #1 主因。

#### 業界標準是 nav2_collision_monitor

- 直接掛 `controller_server` 下游 filter cmd_vel
- 三 model：Stop / Slowdown / Approach（基於 TTC 算動態 buffer）
- 跟 Nav2 obstacle_layer 不衝突，是官方設計
- **長期應遷移**；demo 前先把自製 reactive_stop 補完

#### 公開參考專案（subagent 3 推薦）

| 專案 | 為何相關 |
|---|---|
| `eppl-erau-db/amigo_ros2` | Go2 + Jetson + D435i + RPLIDAR A3 完整 ROS2 整合（最接近 PawAI 配置）|
| `abizovnuralem/go2_ros2_sdk` | PawAI 已 fork |
| `Sayantani-Bhattacharya/unitree_go2_nav` | Go2 + Nav2 + SLAM |
| `OpenMind/OM1-ros2-sdk` | RPLIDAR + SLAM Toolbox + Nav2 |
| arXiv 2410.00572 | Quadruped reactive avoidance（waverider + RMPs）|

### 3.4 Mux 仲裁設計 trade-offs

`twist_mux` 是 ROS package（無 fork），priorities + 0.5s timeout 統一：

```yaml
emergency  255  /cmd_vel_emergency  timeout 0.5s
obstacle   200  /cmd_vel_obstacle   timeout 0.5s
teleop     100  /cmd_vel_joy        timeout 0.5s
nav2        10  /cmd_vel_nav        timeout 0.5s
```

設計假設 **「沉默 = 不要管」**，但 reactive_stop 的「沉默」應被解讀為「保持上一次決定」— **這是設計層面的衝突**。

**Trade-offs**：
- 修法 A：reactive_stop 永遠 publish 0（4-mode hold_brake）→ ✅ 安全但鎖死 nav
- 修法 B：reactive_stop 在 clear zone 漸進減速發正速度 → ❌ priority 200 是主動命令通道，發 0.45 m/s = 主動命令 Go2 走 0.45（不是「限制」）
- 修法 C：mux fork 改 timeout 行為 → ⚠️ 影響面大、demo 風險高
- 修法 D：teleop priority 改低於 nav → ⚠️ 違反人類 override > 自動的 safety 慣例

**選 A**：4-mode 狀態機，操作員顯式切 mode 釋放控制權。trade-off 是「demo 操作多一步」換「絕對安全」。

---

## 4. Design Evolution — B0.1 → 4-mode

### 4.1 B0.1（initial fix，commit `4ec8350`）

**`safety_only=True` 改成永遠 publish 0**：clear/slow zone 不再沉默，hold mux priority 200 不放。

問題：
- 命名「release gate」誤導 — 實質是 permanent brake
- 同一個 script（nav_capability）啟用後鎖死 nav goal
- 「主動發新 nav goal 即可」的釋放策略不對 — nav goal 不會穿過 mux

### 4.2 4-mode 狀態機（commit `0f5a16f`）

把 binary `safety_only` 升級成 4 + 1 mode：

| mode | 行為 | 用途 |
|---|---|---|
| `hold_brake` | 永遠 publish 0 | B5 stop 驗證 / demo emergency hold |
| `progressive` | danger=0、slow/clear silent | nav 主驅動（**必 kill teleop**）|
| `released` | 不 publish、LiDAR 仍更新 zone state | 操作員主動釋放 |
| `disabled` | 完全 off | 全停 reactive |
| `""` | standalone (0/slow/normal) | nav 不在的 demo 備援 |

`safety_only=True` 自動 promote 到 `hold_brake`（向後相容）。

`decide_velocity()` 重寫成 mode dispatcher 回 `Optional[float]`：
- `float` → publish that
- `None` → 不 publish

`_tick()` 改用 `if vel is not None: self._publish(vel)`。

`_on_param_change` 支援 runtime mode 切換：
```bash
ros2 param set /reactive_stop_node mode released
```

### 4.3 Roy code review 4 bug fix（commit `d804a58`）

| # | Bug | 修法 |
|:-:|---|---|
| 1 | safety_hold script 沒啟 mux → cmd_vel_obstacle 沒 subscriber → hold_brake 不生效 | 改用 `robot.launch.py teleop:=false joystick:=false`（含 driver + twist_mux）|
| 2 | nav_capability 註解寫「kill teleop」但 robot.launch.py 預設啟 teleop_twist_joy + joy_node | 啟動加 `teleop:=false joystick:=false` enforcement |
| 3 | progressive mode resume 後 teleop 仍可能 hot-publish → mux 給 teleop 而不是 nav | resume 時 log warn 提醒 check `/cmd_vel_joy` |
| 4 | test source-string `test_emergency_publishes_in_both_modes` 名稱與 4-mode 設計矛盾 | rename → `test_emergency_behavior_per_mode`，用 `decide_velocity` 測 5 mode |

### 4.4 釋放 3 步驟（取代「主動發新 nav goal」單步驟）

```
1. ros2 param set /reactive_stop_node mode released  (or disabled)
2. pkill -f teleop_twist_joy && pkill -f teleop_twist_keyboard
3. 主動發 nav goal（單脈衝命令，不要 -r hot-publish）
```

**三步缺一個 Go2 都不會走** — 這是 feature 不是 bug。

---

## 5. 修法路線圖（4 階段）

完整路線圖見
[`../2026-05-11-architecture-deep-audit-and-fix-roadmap.md §5-6`](../2026-05-11-architecture-deep-audit-and-fix-roadmap.md)。

### B0 — Critical Path（5/11 night ✅ 已完成 code）

| Item | Status | Commit |
|---|:-:|---|
| B0.1 release gate（4-mode state machine 取代 always-0）| ✅ | `0f5a16f` |
| B0.2 teleop 殘留 protocol（B5 測試前 kill `/cmd_vel_joy`）| ✅ docs only | (本檔 / CLAUDE.md) |
| B0.3 threshold 1.1m / 1.7m | ✅ | `4ec8350` |
| B0.4 hysteresis（clear_debounce 3 → 5 frames）| ✅ | `4ec8350` |
| B0.5 慢速 + 人工 e-stop test protocol | ✅ docs only | (CLAUDE.md / scripts comments) |
| B0.6 unit tests（25 + 17 = 42 條 release gate）| ✅ | `4ec8350` / `0f5a16f` |

**剩餘 5/12 早 AM ~1h**：
- 處理 working tree drift（burndown.md / safety-fix-plan deletion）
- Sync to Jetson + colcon build
- 三 script 各跑一次（hold_brake / progressive / standalone）+ runtime mode 切換驗證

### B1 — Demo readiness（5/12 PM / 5/13 場測前，~3h）

| Item | 檔案 | 狀態 |
|---|---|:-:|
| B1.1 local_costmap.obstacle_max_range 1.8 → 3.0 | `nav2_params.yaml` | ⏳ |
| B1.2 inflation_radius 0.30 → 0.45 | `nav2_params.yaml` | ⏳ |
| B1.3 footprint 改實際 0.65×0.30 | `nav2_params.yaml` | ⏳ |
| B1.4 base_link → laser TF 精量 ±0.01m | static TF | ⏳ |
| B1.5 front_offset_rad docstring 雙重套用警告 | `lidar_geometry.py` | ✅ `0f5a16f` |
| B1.6 status JSON 診斷欄位（mode / publishes_zero_continuously / threshold / clear_streak / since_last_zone_change_sec）| `reactive_stop_node._tick_status()` | ✅ `4ec8350` `0f5a16f` |

### B2 — Demo 後（estimated ~10h）

| Item | 描述 |
|---|---|
| B2.1 D435 detour profile 從 spec 落地 | 按 `2026-05-03-d435-rplidar-fusion-detour.md` Phase 1 → 2，加進 main local_costmap obstacle_layer |
| B2.2 base_link projection — 機鼻距離 | 用 TF 算「機鼻到障礙物」，threshold 改成機鼻距離（自適應 mount 改變）|
| B2.3 切換 Nav2 collision_monitor | 業界標準三 polygon Stop/Slowdown/Approach；棄用自製 reactive_stop |
| B2.4 STVL voxel layer | 取代 VoxelLayer，對 RealSense motion blur 更穩 |
| B2.5 動態障礙物跟蹤 | temporal tracking + Kalman，降 zone bouncing |

### B3 — 流程性修法

| Item | Status | Commit |
|---|:-:|---|
| B3.1 CLAUDE.md 升等成 architecture-critical 4-mode 段 | ✅ | `0f5a16f` `f366acd` |
| B3.2 nav 相關 spec threshold 改動必填 decision log | ⏳ | demo 後 |
| B3.3 架構翻案 SOP checklist | ⏳ | demo 後 |

---

## 6. Todo List（按優先級 + dependency）

### 🔴 P0 — 5/12 早 AM 必做（demo blocker）

| # | Todo | Owner | 預估 | Dependency |
|:-:|---|---|:-:|---|
| T1 | 處理 working tree drift（burndown.md M / safety-fix-plan D / start_pawai_brain_tmux.sh M） | Roy | 15 min | Step 0b 決定 (a/b/c) |
| T2 | `~/sync once` + Jetson `colcon build --packages-select go2_robot_sdk` | Roy | 10 min | T1 |
| T3 | 跑 `start_reactive_stop_safety_hold_tmux.sh`（hold_brake 鎖死驗證）3 場景 | Roy | 30 min | T2 |
| T4 | runtime `ros2 param set mode released` 驗證釋放 + 後續 nav goal pass | Roy | 15 min | T3 |
| T5 | 跑 `start_nav_capability_demo_tmux.sh`（progressive）+ goto_relative 0.3m | Roy | 30 min | T2 |
| T6 | 量 `base_link → 機鼻` 距離（卡尺，更新 `base_to_nose_x` 預估值） | Roy | 10 min | (none) |

### 🟠 P1 — 5/12 PM / 5/13 場測前

| # | Todo | Owner | 預估 |
|:-:|---|---|:-:|
| T7 | B1.1-1.3 nav2_params.yaml（obstacle_max_range / inflation / footprint） | Claude + Roy | 30 min code + 30 min 實機驗 |
| T8 | B1.4 base_link → laser TF 精量到 ±0.01m（卡尺 + Foxglove `/scan_rplidar` 對齊）| Roy | 1h |
| T9 | B6 AMCL 場測（home / 學校場地）| Roy | 1h |
| T10 | B7 goto 0.3m / 0.5m motion 測試 | Roy | 1h |

### 🟡 P2 — Demo 後（5/19+）

| # | Todo | 預估 |
|:-:|---|:-:|
| T11 | B2.1 D435 detour profile 落地（按 5/03 spec Phase 1 → 2） | 2-3h |
| T12 | B2.2 base_link projection helper + 改 threshold 用機鼻距離 | 4h |
| T13 | B2.3 遷移到 Nav2 collision_monitor（Stop/Slowdown/Approach 三 polygon） | 6-8h |
| T14 | B2.4 STVL voxel layer 取代 VoxelLayer | 3h |
| T15 | B2.5 動態障礙跟蹤（temporal tracking + Kalman） | 4-6h |

### 🟢 P3 — 流程性（demo 後 / 持續）

| # | Todo | 預估 |
|:-:|---|:-:|
| T16 | B3.2 nav spec threshold 改動 decision log 規範（template + git hook 提醒）| 1h |
| T17 | B3.3 架構翻案 SOP checklist（list pre-flight check items）| 1h |
| T18 | reactive_stop subscribe `/cmd_vel_joy` 自動 detect hot-publisher + log（取代 demo discipline）| 2h |
| T19 | mux input topology 文件化到 `docs/navigation/setup/` | 1h |
| T20 | nav stack pre-flight smoke test script（驗 mux topics / cmd_vel chain / TF）| 2h |

---

## 7. Open Questions / 待確認

| 問題 | 影響 | 解法 |
|---|---|---|
| `base_to_nose_x` 推估 0.50m，實際是？ | B0.3 threshold + B2.2 projection 精度 | 5/12 早 AM 卡尺量（T6）|
| 學校場地大空間下 1.1m danger 是否仍嫌保守？ | 5/13 場測 nav 流暢度 | 5/13 場測時 fine-tune |
| progressive mode + nav 在學校大空間能否 demo 跑通？ | 主 demo 路徑能否上 nav 段 | 5/12 PM B7 motion + 5/13 場測 |
| Go2 sport mode `MIN_X=0.5 m/s` 對 Nav2 controller min_vel_x 的影響？ | 短距離 goal 可能無法精確停 | 之前已驗 0.45 OK，再場測確認 |
| RPLIDAR 對學校場地的反光 / 玻璃失敗模式？ | nav 場測穩定性 | 5/13 場勘看實測 |
| 三 script 互斥啟動，demo 場切換成本？ | 操作流暢度 | 提供「kill all + restart」單一指令簡化切換 |

---

## 8. Sources / References

### 內部文件

- [`../2026-05-11-architecture-deep-audit-and-fix-roadmap.md`](../2026-05-11-architecture-deep-audit-and-fix-roadmap.md) — 完整修法路線圖（B0/B1/B2/B3）
- [`../CLAUDE.md`](../CLAUDE.md) — 4-mode architecture-critical 故事化敘述 + 釋放 3 步驟
- [`./2026-03-25-reactive-obstacle-avoidance.md`](./2026-03-25-reactive-obstacle-avoidance.md) — 原 D435 ROI 設計（0.8/1.5m 來源）
- [`../specs/2026-05-03-d435-rplidar-fusion-detour.md`](../specs/2026-05-03-d435-rplidar-fusion-detour.md) — D435 detour profile（B2.1 落地依據）
- [`../research/2026-04-25-rplidar-a2m12-integration-log.md`](./2026-04-25-rplidar-a2m12-integration-log.md) — RPLIDAR 整合實機紀錄
- [`../../pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md`](../../pawai-brain/plans/2026-05-11-nav-root-cause-burndown.md) — 7 項排除法
- [`../../../references/project-status.md`](../../../references/project-status.md) — 5/11 night 進度同步

### 程式碼（修法權威位置）

- `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py` — 4-mode state machine
- `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py` — `decide_velocity()` mode dispatcher + `compute_front_min_distance()`
- `go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py` — driver `cmd_vel=0 → StopMove (1003)` + 1Hz dedupe
- `go2_robot_sdk/test/test_reactive_stop_release_gate.py` — 25+ mode-based tests
- `go2_robot_sdk/test/test_robot_control_service.py` — 11 condition-routing tests
- `scripts/start_reactive_stop_safety_hold_tmux.sh`（新）— hold_brake B5 stop 驗證
- `scripts/start_nav_capability_demo_tmux.sh`（改）— progressive nav demo
- `scripts/start_reactive_stop_tmux.sh`（改）— standalone fallback
- `go2_robot_sdk/config/twist_mux.yaml` — priority / timeout config
- `go2_robot_sdk/config/nav2_params.yaml` — DWB / costmap config

### 業界 best practice（subagent 3）

- [Nav2 Collision Monitor Configuration](https://docs.nav2.org/configuration/packages/configuring-collision-monitor.html) — Stop/Slowdown/Approach 三 model
- [Nav2 Voxel Layer Parameters](https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html)
- [Nav2 Setup Sensors Guide](https://docs.nav2.org/setup_guides/sensors/setup_sensors.html) — multi-source obstacle_layer
- [eppl-erau-db/amigo_ros2](https://github.com/eppl-erau-db/amigo_ros2) — Go2 + Jetson + D435 + RPLIDAR
- [Nav2 STVL Tutorial](https://docs.nav2.org/tutorials/docs/navigation2_with_stvl.html) — RealSense 對 STVL 比 voxel_layer 穩
- arXiv 2410.00572 — Quadruped reactive avoidance（waverider + RMPs）

### Commits（5/11）

```
b9aac4d fix(driver): cmd_vel zero routes to StopMove (api_id=1003) + 1Hz dedupe
8ae7faf docs(navigation): 5/11 撞牆事件深度 architecture audit + Tier 0/1/2 修法路線圖
f471ebd docs(navigation): Phase A errata — audit doc 4 fact corrections + 重排 P0
4ec8350 fix(reactive_stop): B0 release gate + threshold enlarge + diagnostics (5/11 B5 撞牆 fix)
f366acd docs(navigation): B3.1 升等 reactive_stop release gate 為 architecture-critical
0f5a16f refactor(reactive_stop): 4-mode 狀態機（5/11 night Roy review fix）
d804a58 fix(reactive_stop): 4 review fixes (5/11 night Roy mode redesign review)
30b01e6 docs: sync 5/11 evening — Nav 4-mode redesign + 4 review fixes 落地
```

### Subagent 報告（已壓縮，原文留 conversation log）

- **Subagent 1（local docs）**：權威文件清單、設計演進時間線、5 個盲點、reactive_stop 釋放策略待釐清
- **Subagent 2（local code）**：dataflow 完整圖、6 個 Q&A、obstacle_max_range 1.8m vs RPLIDAR 8m 發現、D435 主線未進 obstacle_layer
- **Subagent 3（網路）**：collision_monitor 推薦、三段 zone 參數、5 公開參考專案

---

## 9. Appendix — 取代 / 合併進來的 plan

### `2026-05-12-reactive-stop-safety-fix-plan.md`（68fe29b 創、被 4-mode 取代）

該 plan 提出 4 個 Top fix（總 ~3.5h）：
- Fix 1 safety_only slow zone 限速 0.45 — ❌ 被 Roy review #4「reactive_stop 永遠只發 0」否決（priority 200 是主動命令通道，發正速度 = 主動命令 Go2 走，不是限速）
- Fix 2 base_link projection + danger 0.6→0.4 投影後 — ⏳ 移到 B2.2，demo 後做。本研究 5/11 用 LiDAR 視距 enlarge 1.1/1.7 取代（簡化但保守）
- Fix 3 clear 後 dwell 1s + mux timeout 0.5→1.5s — ⚠️ 部分採納：hold_brake mode 永久 publish 0 取代 dwell timer；mux timeout 不動（影響其他 input）
- Fix 4 hysteresis 全方向 — ✅ 採納精簡版：clear_debounce 3 → 5 frames（≈0.5s）

開放問題（已轉到本研究 §7）：
- `base_to_nose_x = 0.50` 推估值 → T6 卡尺量
- dwell 1.0s + mux timeout 1.5s 經驗值 → 5/12 上機調

---

**End of Nav 避障深度研究 — 2026-05-11 deep night**
