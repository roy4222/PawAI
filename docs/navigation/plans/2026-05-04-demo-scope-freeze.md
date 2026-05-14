# 2026-05-04 — Demo Scope Freeze (5/12 demo)

> **目的**:把 5/12 demo 的功能 scope、戰略 framing、bug backlog、驗收條件、禁忌一次寫清楚,讓團隊對齊。本檔**不**改任何 ROS code,code 改動拆獨立 PR(Phase 2,見 §15)。
> **狀態**:Phase 1 文件凍結 — 5/4 寫定後 5/12 demo 前不再大改。
> **作者**:Roy + Claude (PawAI)

---

## 1. 戰略 Framing

> **Safety-Gated Navigation for Quadruped Embodied Interaction**
> 四足機器人具身互動之安全閘控導航系統

- **RPLIDAR** 提供 2D SLAM、AMCL 定位、Nav2 主導航
- **D435** 提供前方近距離 safety gate(**不進 costmap**,降級為純 capability source)
- **Executive** 根據 `nav_ready` / `depth_clear` / `nav_paused` + Go2 狀態決定是否允許移動
- 對障礙的**預設行為 = stop + resume**,不是 detour

三層分工口號:

> **Nav2 負責「怎麼走」、Safety Gate 負責「現在能不能走」、Executive 負責「為什麼要走」。**

---

## 2. 功能 Scope

### P0 — Demo 主線(5 項生死線)

| # | 功能 | 對應 |
|---|------|------|
| 1 | LiDAR SLAM + AMCL 定位(GREEN/YELLOW/RED 三級分級) | `home_living_room_v8.{pbstream,yaml,pgm}`、`nav2_params.yaml` |
| 2 | `nav_demo_point` 固定點導航 ≥ 4/5 PASS | Storyboard Scene 2 ★Wow A |
| 3 | D435 + LiDAR 雙源 reactive stop | `reactive_stop_node` + `depth_safety_node` |
| 4 | Pause-Resume 或 safe abort | `route_runner` + `nav_action_server`(BUG #2 已修 `a3bdd2e`) |
| 5 | 30 分鐘供電連測 0 斷電 | 2464 升降壓恒壓恒流模組驗收 |

### P1 — Wow 加分(時間夠才做)

| # | 功能 | 條件 |
|---|------|------|
| 6 | `approach_person` 1 PASS | Scene 7 ★★Wow C(可砍) |
| 7 | Detour profile | ★ Wow,**條件: B1+B2 修完後**,失敗就回 stop+resume |
| 8 | Studio / Foxglove 顯示 nav_ready level + reasons | 答辯加分 |

### P2 — 不做(寫進 future work)

- D435 點雲進 Nav2 voxel layer / costmap
- `depthimage_to_laserscan` fusion
- 連續 person following
- 自主探索 / 多房間搜尋
- 樓梯 / 懸崖偵測
- VLM 任務規劃

---

## 3. 架構

```
使用者語音 / Studio
        │
        ▼
┌─────────────────────────┐
│ Interaction Executive    │
│  WorldState + SafetyLayer│  ← /capability/nav_ready
│  capability fail-closed  │  ← /capability/depth_clear
│                          │  ← /state/nav/paused
└────────────┬─────────────┘
             │ goto_relative / goto_named action
             ▼
┌─────────────────────────┐
│ nav_action_server        │
│  - max_speed enforce(B1) │  ← Phase 2 PR 1
│  - pause/resume          │
│  - 10s pose-progress to  │
│  - YELLOW gate by param  │  ← B4: launch override
└────────────┬─────────────┘
             │ /goal_pose (BEST_EFFORT)
             ▼
┌─────────────────────────┐
│ Nav2                     │
│  AMCL(分級) + BT + DWB   │
│  Go2-safe BT             │  ← Phase 2 PR 5
│  (Spin/BackUp 移除)       │
└────────────┬─────────────┘
             │ /cmd_vel
             ▼
┌─────────────────────────┐
│ cmd_vel mux              │ ← /cmd_vel_obstacle pri 200 (reactive_stop)
│  255: emergency_stop     │
│  200: reactive           │
│  100: nav                │
└────────────┬─────────────┘
             ▼
        Go2 Driver → Go2 Pro
```

---

## 4. 三層 Capability Gate

| Capability | 來源 | Fail-closed 條件 |
|---|---|---|
| `/capability/nav_ready` | `nav_capability/capability_publisher_node.py` + `nav_ready_check.py` | **現況**: AMCL pose latched + covariance ≤ 0.20 + age ≤ 300s。**升級 target**(Phase 2 PR 4): + lifecycle(map_server/amcl active) + TF(`map → base_link`)+ `/scan` freshness |
| `/capability/depth_clear` | `go2_robot_sdk/depth_safety_node.py` | D435 ROI < 0.4m 障礙 / frame stale > 1s / compute error |
| `/state/nav/paused` | `route_runner_node` + `nav_action_server` | `/nav/pause` service 觸發(BUG #2 5/2 已修 `a3bdd2e`) |

---

## 5. AMCL 三級分級

| Level | covariance_xy | 允許行為 |
|---|---|---|
| GREEN | ≤ 0.30 | 長距離 goal、`approach_person` |
| YELLOW | 0.30 – 0.50 | 短距離 / 固定 demo point only(B4 修完後可 launch param override) |
| RED | > 0.50 / stale | 拒絕所有移動 |

---

## 6. Emergency Stop 三層語意

| 類型 | 觸發 | 實作 | 可否 resume |
|---|---|---|---|
| Normal Stop | 抵達 / cancel | `StopMove` (api_id=1003, `rt/api/sport/request`) | ✅ 可重發 goal |
| Reactive Pause | 短暫障礙 | `cmd_vel_obstacle=0` mux pri 200 + `/state/nav/paused` | ✅ 障礙清除自動 |
| Emergency Stop | 即將碰撞 / 異常 | `emergency_stop.py engage` (mux pri 255 + lock) + StopMove | ❌ 需人工 clear |
| **禁止** | 移動中送 `Damp` (api_id=1001) | — | 5/2 摔倒事件 |

---

## 7. P0 Bug Backlog(5/3 夜間紀錄,Phase 2 PR 順序)

### B1. `nav_action_server` v1 不 enforce max_speed 🔴

- **症狀**:送 0.5m goal,Go2 實際走 1.04m(2x overshoot)
- **位置**:`nav_capability/nav_capability/nav_action_server_node.py:321-326`
- **現況**:程式只 log warn「ignored in v1」,沒有真實限速
- **影響**:warmup 永遠超走 → 破壞 detour 場景 → 從未真正進到 DWB 試繞階段
- **修法概念**:動態 set `controller_server.FollowPath.max_vel_x` ROS param;goal accept 時降速、goal end 時還原
- **前置驗證**:Nav2 controller_server 是否接受 runtime param update + DWB plugin 參數名
- **估工**:0.5–1 天

### B2. AMCL covariance 卡 0.30–0.45 plateau 🔴

- **症狀**:Go2 站著不動,cov 永遠不收斂到 GREEN
- **根因**:`update_min_d=0.10` + `update_min_a=0.10`,靜止狀態 AMCL 完全不更新
- **位置**:`go2_robot_sdk/config/nav2_params.yaml` amcl section
- **影響**:必須 forward warmup → 觸發 B1 → 場景被破壞
- **修法概念**:`update_min_d: 0.10 → 0.05`、`recovery_alpha_slow: 0 → 0.001`
- **前置驗證**:實機 bag,監測 CPU + noise sensitivity
- **估工**:0.5 天

### B3. `capability_publisher` 沒 parameter callback 🟡

- **症狀**:`ros2 param set /capability_publisher_node covariance_threshold 0.45` 無效
- **位置**:`nav_capability/nav_capability/capability_publisher_node.py`
- **修法概念**:`add_on_set_parameters_callback` 支援 runtime tune
- **估工**:30 min

### B4. `nav_action_server` YELLOW gate threshold 寫死 🟡

- **症狀**:cov 0.31 vs 0.30 差 0.01 就拒 1.6m goal
- **位置**:`nav_action_server_node.py:344` `if 0.3 < cov <= 0.5 and abs(goal.distance) > 0.5`
- **修法概念**:改 launch param,demo mode 可 override
- **估工**:1 hr

### B5. `actual_distance` 計算用 send-time pose 🟡

- **症狀**:`actual_distance` 報告值 ≠ 真實位移
- **位置**:`nav_action_server_node.py:391-394`
- **影響**:log 數據不可信,debug 困難
- **修法概念**:`start_pose` 在 goal accept 時鎖定,`actual_distance = current - start_pose`
- **估工**:30 min

---

## 8. 5/3 環境陷阱清單(已踩過,參考用)

| # | 陷阱 | 解法 |
|---|------|------|
| E1 | Jetson `colcon build` 撞 setuptools 不相容(`--uninstall not recognized`) | WSL build → rsync → cp 到 `install/share` |
| E2 | `~/.local/.../entry_points.txt` 缺 entry → `StopIteration` / `load_entry_point fail` | 手動 echo append 那 .txt(`cp .bak.<ts>` 自動備份)。5/3 已修補 3 個:reactive_stop / capability_publisher / depth_safety |
| E3 | rsync 多 source + trailing slash + `--delete` 災難 | source 不帶 trailing slash + 不用 `--delete`:`rsync -avz src1 src2 jetson:dest/` |
| E4 | tmux send-keys 長命令被截斷 | 拆成 source 1 + source 2 + 主命令三段 send-keys |
| E5 | zsh vs bash setup 混淆 | Jetson 統一 `setup.zsh`(CLAUDE.md 已寫) |
| E6 | `ros2 daemon` 偶爾 stale,`node list` 突然 0 nodes | `ros2 daemon stop && sleep 1 && ros2 daemon start` |
| E7 | SSH timeout 在多 ros2 cli 並發時 | 序列化 / `ServerAliveInterval` / 改用單一 python script |
| E8 | `/scan_d435` QoS mismatch artifact(`hz` 報「not published」但 publisher 在) | sub 加 `--qos-durability transient_local --qos-reliability reliable` |
| E9 | `base_link → camera_depth_optical_frame` TF 不存在(two unconnected trees) | `static_transform_publisher --x 0.30 --y 0 --z 0.20` 暫時頂著。精校排 5/13 後 |
| E10 | `robot.launch.py:77` nav2 yaml 寫死 | 5/3 已修加 `nav_params_file` LaunchArgument |

---

## 9. 操作教訓(流程改善)

| # | 教訓 |
|---|------|
| O1 | AMCL global re-init 對「位置 OK 只是 cov 卡」是退步:`/amcl/reinitialize_global_localization` 後 cov 0.45 → 10,粒子完全散開。**只在真的迷路時用,不是 cov plateau 解法** |
| O2 | Forward warmup 雙刃刀:收斂 cov 但破壞場景。**B1 沒修前不要 forward warmup** |
| O3 | 場景測試前必跑 `scan_health_check.py` 確認 box 距離,**地板膠帶固定起點與障礙**(5/3 R3 R1 加場景校準後 PASS) |
| O4 | 一次只動一個變數:D435 source 與 DWB tuning 不要一起改 |

---

## 10. 物理極限(不是 bug,要接受)

| # | 限制 | 影響 |
|---|------|------|
| P1 | Go2 sport mode `min_vel_x = 0.50 m/s` 硬限(韌體) | DWB `min_vel_x: 0.45` 接近底,低速貼邊修正不可能 |
| P2 | Quadruped `max_vel_y = 0`(不開 lateral,穩定性) | DWB 只能曲線繞,最小半徑 ~0.5m |
| P3 | 房間縱深 2.5m / 一側 0.6m | 對 0.5m 曲線半徑屬於物理可繞下限 |
| P4 | D435 mount TF 是 hack 估算(`--x 0.30 --y 0 --z 0.20`) | D435 進 costmap 障礙位置可能偏 5-10cm。**反正不進 costmap**,精校排 5/13 後 |

---

## 11. 凍結清單(5/12 前不動)

- LiDAR mount yaw = π(v8)、3D 列印背板
- Jetson 供電:2464 升降壓恒壓恒流模組
- D435 mount(精校排 5/13 後)
- 場地、demo 起點、demo goal、障礙位置(地板膠帶標記)
- `home_living_room_v8` map(`.pbstream` + `.yaml` + `.pgm`)
- Go2 背包 / 線材 / 外接模組位置

---

## 12. Demo 主腳本

### Demo A — Safety-Gated Point Navigation(主線)

```
1. PawAI Studio 顯示 nav_ready = GREEN
2. 使用者:「PawAI,去展示點」
3. Executive 檢查 capability gate
4. nav_action_server 接受 goal
5. Go2 沿規劃路徑前進
6. 中途:人/箱子站到前方
7. depth_clear → false
8. /nav/pause 觸發 → cmd_vel_obstacle=0
9. Go2 StopMove 停下
10. 障礙移除 → depth_clear stable 3 frames
11. resume → 抵達 demo point
12. 語音回報:「我到了」
```

### Demo B — Voice-Triggered Approach(P1 加分)

```
1. 使用者站在 Go2 前 1.8m
2. face_identity 偵測 + 語音:「靠近我」
3. Executive 檢查 depth_clear + nav_ready ≥ YELLOW
4. goto_relative 0.5m × 1-2 次
5. 停在 ~1m 安全距離
6. 回報:「我離你約一公尺」
```

---

## 13. 驗收 V1–V9(End-to-End,Phase 2 各 PR 通過後做)

| V | 內容 | 對應 Phase 2 PR |
|---|------|---|
| V1 | Bug fix:0.5m goal 實走 0.45–0.55m + 60s 內 cov 收斂到 ≤ 0.30 | PR 1 + PR 2 |
| V2 | nav_ready 升級:reasons 包含 lifecycle / tf / scan / covariance 四項 | PR 4 |
| V3 | Go2-safe BT:plan fail → clear costmap → retry → safe abort,不出現 spin / backup | PR 5 |
| V4 | Goal 路徑統一:`grep -rn "ros2 topic pub.*goal_pose" scripts/` 0 hits | PR 7 |
| V5 | `nav_demo_point` 5×baseline ≥ 4/5 PASS | PR 1+2 後 |
| V6 | 30 min 供電連測 0 斷電 | 獨立 |
| V7 | Pause-Resume E2E:障礙觸發 pause → 移除 resume → 抵達 goal | PR 1+2 後 |
| V8 | `approach_person` 1 PASS(P1 加分) | PR 1+2 後 |
| V9 | Detour profile(★ Wow,可砍):需另寫 `nav2_params_detour.yaml` | PR 1+2 修完才有意義 |

---

## 14. 答辯 Framing 三句話

1. **分層感測融合** — LiDAR 穩定 2D 幾何導航 + D435 近距語意安全 + Executive 任務閘控,不是亂塞 sensor fusion
2. **安全閘控** — 每個移動 command 必須通過三 capability gate(`nav_ready` / `depth_clear` / `nav_paused`)+ AMCL 三級分級。**AI 提意圖、底層做安全驗證**
3. **互動式導航** — 不是傳統「點地圖走過去」,而是「靠近我 / 去展示點 / 往前一點 / 停下」,符合 PawAI 具身互動定位

### 設計決策 framing(可直接放報告)

> 本系統最初嘗試將 D435 深度資料直接整合至 Nav2 costmap,但在 Go2 四足平台上,由於相機視角、機身晃動、TF 誤差與地面深度雜訊,點雲式 costmap 容易造成局部代價地圖污染,進而導致 DWB 無有效軌跡。
>
> 因此最終架構採用分層式安全閘控設計:RPLIDAR-A2M12 負責 2D SLAM、AMCL 定位與 Nav2 主導航;D435 不直接參與全域或局部路徑規劃,而是作為前方近距離 safety gate,在移動前與移動中檢查前方是否存在障礙風險。Executive 則根據 `nav_ready`、`depth_clear`、`paused` state 與 Go2 狀態決定是否允許導航命令下發。
>
> 此設計犧牲部分自動繞行能力,但顯著提升四足平台 demo 的安全性與可預測性。

---

## 15. Phase 2 預告(本檔不做,獨立 PR)

| PR | 內容 | 前置驗證 |
|---|---|---|
| PR 1 | B1 + B5 — `nav_action_server` distance/speed correctness | 先驗證 Nav2 controller_server 是否接受 runtime param update + DWB 參數名 |
| PR 2 | B2 — AMCL params(`update_min_d` / `recovery_alpha_slow`)+ 60s 收斂驗證 | 實機 bag,監測 CPU + noise sensitivity |
| PR 3 | B3 + B4 — `capability_publisher` parameter callback + YELLOW gate launch param | 確認 param 命名與 launch override 路徑 |
| PR 4 | `nav_ready_check.py` 加 lifecycle + TF + scan freshness | 確認 package 是否已有 lifecycle client pattern,避免阻塞 service call |
| PR 5 | Go2-safe BT(移除 Spin / BackUp,保留 Wait) | 先確認 Nav2 Humble BT plugin names + default tree XML |
| PR 6 | `scripts/preflight_nav_demo.sh`(複用 `scan_health_check.py`) | 獨立 PR |
| PR 7 | Goal 路徑統一 — `send_relative_goal.py` 改走 `/nav/goto_relative` action | 獨立 PR,不混 nav2 params |

**順序原則**:PR 1 → PR 2 → PR 3 同支線(bug fix);PR 4–7 各自獨立。
**PR 1+2 解鎖之後**再決定 detour 是否值得進 V9 Wow。

---

## 16. 關鍵檔案路徑(Phase 2 引用,本 plan 不改)

```
nav_capability/nav_capability/
  nav_action_server_node.py       ← B1, B4, B5
  capability_publisher_node.py    ← B3
  nav_ready_check.py              ← PR 4 升級
  route_runner_node.py
go2_robot_sdk/
  config/nav2_params.yaml         ← B2 + Go2-safe BT
  go2_robot_sdk/reactive_stop_node.py  (269 行,已穩,不動)
  go2_robot_sdk/depth_safety_node.py
interaction_executive/interaction_executive/
  world_state.py                  (已訂三 capability,不動)
  safety_layer.py                 (27 cases 過,不動)
scripts/
  start_nav_capability_demo_tmux.sh
  start_nav2_amcl_demo_tmux.sh
  start_reactive_stop_tmux.sh
  send_relative_goal.py           ← PR 7 改寫
  preflight_nav_demo.sh           ← PR 6 新建
```

---

## 17. 引用

- **5/2 Phase A 主線設計**:`docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md`
- **5/2 Phase A 實作**:`docs/navigation/plans/2026-05-01-phase-a-nav-attack.md`
- **5/3 D435 fusion 嘗試紀錄**:`docs/navigation/plans/2026-05-03-d435-fusion-phase1-plan.md`
- **5/3 Stage 1 + recovery 紀錄**:`docs/navigation/plans/2026-05-03-stage1-and-recovery.md`
- **AMCL 180° 修復紀錄**:`docs/navigation/research/2026-05-01-amcl-180-degree-diagnosis.md`
- **介面契約**:`docs/contracts/interaction_contract.md`
