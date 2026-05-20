# PawAI 導航避障 — Implementation Spec（北極星 §4 落地）

> 文件類型：Implementation spec（**不是** implementation plan — 不排每日任務、不指 PR 順序）
> 日期：2026-05-20
> 窗口：2026-05-22 – 2026-06-18
> 關聯：
> - [北極星 §4](2026-05-19-pawai-may-june-north-star-design.md#4-導航避障p0-a核心閉環)
> - [0511 nav 文件夾](../../pawai-brain/architecture/0511/nav/)（runtime-flow / capability-brain-integration / reactive-stop-and-mux / known-issues-roadmap / field-runbook）

---

## 1. Problem Statement

Hiwonder ROSOrin Pro 這類 ROS2 教學整合套件讓「導航避障」**看起來**完整，因為它把 LiDAR / 深度相機 / SLAM / 動態避障 / 語音 / Agent / App 包成可操作 demo package。PawAI 不缺底層架構 — Go2 版本的 nav stack 已在 `docs/pawai-brain/architecture/0511/nav/` 完整描述。**缺的是「產品化接線」與「安全成熟度」**：

- 語音 / Brain 還不能真正叫 Go2 走（Executive NAV executor 未實作，仍是 `nav_unimplemented_phase_a`）
- F7 仍是 P0 blocker：goal accepted 但 `/cmd_vel_nav` 不出，10s 後 ABORT
- `nav_ready` 只看 AMCL pose + covariance，缺 lifecycle / TF / scan / publisher sanity，可能 false positive
- D435 只是 `depth_clear` fail-closed gate，**不會** 停掉已在跑的 Nav2 goal
- `reactive_stop progressive` 依賴「無 `/cmd_vel_joy` hot publisher」的操作紀律
- Studio 沒有把 nav 狀態包成可觀測 / 可操作的產品面板

> **本 spec 的金句**
> Hiwonder 值得學的是「把導航、感知、語音、Agent、UI 包成可操作 demo package」；PawAI 要做的是 **Go2 版本的安全短距移動閉環**，而不是照搬輪式車的全功能清單。

---

## 2. 6/18 Definition of Done

| 指標 | 通過條件 |
|---|---|
| **叫得動** | Brain / Studio 觸發 → Executive NAV executor → `/nav/goto_relative` 真的送下去，不再 `nav_unimplemented_phase_a` |
| **走得短** | `goto_relative 0.3–0.5m` 在 demo 場地可重複執行 |
| **停得住** | RPLIDAR danger ≤ 1.1m 時 Go2 停下，並通過 twist_mux obstacle priority 200 接管 |
| **說得清** | 阻擋 / 停車 / 取消的原因要在 Studio 或語音明確回報（「前方有障礙我先停下來」） |
| **不暴衝** | 障礙移開後 Go2 **不自動 resume**；必須等明確 `resume` / 重送 goal / 維持停車並回報 |
| **named places** | 至少 2 個命名地點可由 `/nav/goto_named` 觸發 |
| **preflight 通過** | 每次 nav demo 前 `/cmd_vel_joy` 無 hot publisher、twist_mux inputs 正常、`map -> base_link` TF 可查、Nav2 lifecycle active、`/cmd_vel_nav` publisher sanity |

**不在 DoD 內**（明文擋掉避免 scope creep）：完整自主尋物、複雜動態人流繞行、長距離跟隨人、D435 完全進 Nav2 local costmap。

---

## 3. Current Architecture Snapshot

直接引用 0511 nav 文件，不重寫。本節只列「6/18 要碰的東西在這個 stack 裡的位置」：

```text
Sensors        : RPLIDAR A2M12 ─ /scan_rplidar         （主線）
                 D435 aligned depth ─ /capability/depth_clear  （只作 gate）
                 Go2 driver odom ─ /odom               （footstep odom，無 IMU 融合）

Localization   : Cartographer (mapping) / AMCL (runtime) → /amcl_pose, map→odom TF

Planning       : Nav2 controller_server + planner_server + bt_navigator + velocity_smoother → /cmd_vel_nav

Safety/Arbitr. : reactive_stop_node (4-mode) ─ /cmd_vel_obstacle
                 emergency_stop.py ─ /cmd_vel_emergency
                 twist_mux (emergency 255 / obstacle 200 / teleop 100 / nav2 10) ─ /cmd_vel

Capability     : nav_action_server_node ─ /nav/goto_relative, /nav/goto_named
                 route_runner_node ─ /nav/run_route, /nav/pause|resume|cancel
                 capability_publisher_node ─ /capability/nav_ready
                 state_broadcaster_node ─ /state/nav/heartbeat, /state/nav/status, /state/nav/safety

Brain/UI       : Brain → Executive (skill_contract) → 【NAV executor — MISSING】
                 Studio：可觀測 /capability/nav_ready, /capability/depth_clear 但無 nav 操作面板
```

`【MISSING】` 是 6/18 P0 唯一一條把 **Brain → Executive → Nav** 接通的 code 線（其他 P0 線多半也需要 code 或工具改動，但屬於「打磨既有」而非「接通缺口」）。

權威細節：
- `docs/pawai-brain/architecture/0511/nav/nav-runtime-flow.md`
- `docs/pawai-brain/architecture/0511/nav/nav-reactive-stop-and-mux.md`
- `docs/pawai-brain/architecture/0511/nav/nav-capability-brain-integration.md`
- `docs/pawai-brain/architecture/0511/nav/nav-known-issues-roadmap.md`
- `docs/pawai-brain/architecture/0511/nav/nav-field-runbook.md`

---

## 4. External Reference Mapping

### 4.1 Hiwonder ROSOrin Pro

| 借鑑 | 借法（敘事 / 模式，不是程式碼） |
|---|---|
| SLAM 建圖 | PawAI 已有 Cartographer，**不換**；只借「demo 前預錄場地圖」的 ritual |
| 定點 / 多點導航 | PawAI 已有 `/nav/goto_named` + route runner；借「**預錄 2–5 個 named locations + 1 條 demo route**」作敘事 |
| App 操作面板 | 借「**Studio Nav Panel**」：把 ready / depth / paused / obstacle / cmd_vel 狀態包成可看可操作 |
| Agent 高階任務 | PawAI Brain → Executive → Skill 已有同層；借「**任務拆解可視化**」（task tree timeline） |
| 動態避障 | PawAI reactive_stop 四模式已比 Hiwonder 黑盒「動態避障」更貼合 Go2 機鼻距離 — **不借** |

**明確不照搬**：輪式底盤控制、語音直接控 `/cmd_vel`、機械臂抓取 / 搬運、Gazebo 當實機驗收。

### 4.2 CMU autonomy_stack_go2

只列 future research，**本窗口不進 implementation**：

| 概念 | 為何不本窗口 | 何時可能用 |
|---|---|---|
| Point-LIO（3D LiDAR SLAM） | 吃 Go2 L1 3D LiDAR；PawAI 主線是 RPLIDAR 2D scan | 若 XL4015 供電持續炸 RPLIDAR，作 L1 LiDAR fallback 評估 |
| terrain_analysis | 需要 3D point cloud，RPLIDAR 2D 沒地形高度 | 未來若上 3D LiDAR / Velodyne |
| Motion primitive local planner | 預生候選路徑庫對 costmap 打分；和 Nav2 DWB 哲學不同 | 未來 reactive_stop 進階版方向標 |
| FAR Planner（visibility graph 探索未知空間） | PawAI 居家場景已有 Cartographer 靜態圖 | 若做戶外探索類任務 |
| 直打 sport API 繞 twist_mux | 會繞過 PawAI 用 5/11 撞牆事件血淚建立的安全鏈 | **永不照搬** |

**結論**：CMU stack 對 6/18 demo 的 implementation 借用 = 0；**作為 future direction 寫進 §6 即可**。

---

## 5. P0 Implementation Lines

**七條線**。每條註明：目標 / 涉及檔案 / 驗收 gate。**不排日期、不指 PR 順序、不分配人** — 那是後續 implementation plan 的事。

### Line A：F7 root cause + watchdog（最高優先）
- **問題**：goal accepted but `/cmd_vel_nav` not published；10s timeout ABORT；Go2 不動。5/12 出現過。
- **目標**：（1）找到 root cause（最可能：bt_navigator lifecycle / controller_server cmd_vel publisher / velocity_smoother stale），或（2）若無法根治，加 watchdog：偵測 `goal_accepted == true` 但 `/cmd_vel_nav` `Hz < threshold` 持續 N 秒 → 主動 cancel + 重新 send；同時廣播 `/state/nav/health` 給 Studio。
- **涉及**：`go2_robot_sdk/nav2_params*.yaml`、`nav_capability/nav_action_server_node`、新增 `nav_watchdog_node`（可選）。
- **驗收**：場測連跑 30 分鐘以上、≥ 10 次 `goto_relative` 連發，F7 復現率 0/10；若復現，watchdog 必須 ≤ 5s 內自動 recover。

### Line B：Executive NAV executor（接通 Brain → Nav 的 code 缺口）
- **問題**：`interaction_executive_node.py:220` 仍是 `nav_unimplemented_phase_a`。Brain 知道 NAV skill、SafetyLayer gate 也接好，但「真正把 NAV step 送到 `/nav/goto_relative`」沒做。
- **目標**：實作 NAV executor — 接 skill_contract NAV step → 過 SafetyLayer（`nav_ready` + `depth_clear` + `nav_paused`）→ 呼叫 `/nav/goto_relative` 或 `/nav/goto_named` action → 把 result / feedback 回報給 Brain + Studio。
- **涉及**：`interaction_executive/interaction_executive/interaction_executive_node.py`、skill_contract 文件、Brain persona 對應段。
- **驗收**：「PAI 過來一下」→ Brain 產生 nav skill → Executive NAV executor 真的 invoke action → Go2 走 0.3–0.5m → 通過 obstacle stop → 把「為什麼停」回給 Brain，由 TTS 說出。

### Line C：`nav_ready` 升級
- **問題**：目前只看 AMCL pose 曾出現 + covariance；缺 lifecycle active、`map -> base_link` TF freshness、scan freshness、`/cmd_vel_nav` publisher sanity。False positive 風險。
- **目標**：補三項檢查（只補三項，不無限加），AMCL covariance 維持現有門檻（`> 0.5 reject` / `0.3–0.5 短距僅可`）。
- **涉及**：`nav_capability/capability_publisher_node`。
- **驗收**：手動 kill bt_navigator / 拔 TF static publisher / stop RPLIDAR 任一情況，`/capability/nav_ready` 應在 ≤ 2s 內降 false 並廣播原因。

### Line D：reactive_stop / mux preflight
- **問題**：`reactive_stop progressive` 依賴沒有 `/cmd_vel_joy` hot publisher（5/11 撞牆主因之一）；danger 1.1m / slow 1.7m 須維持；`safety_only=true` 不可用於 nav demo（會 auto promote `hold_brake`，跑不動）。
- **目標**：把 `pawai demo preflight` 的 nav 段補完整，分兩階段檢查（避免 false FAIL）：
  - **啟動前靜態檢查**（不需 active goal）：`/cmd_vel_joy` publisher count、twist_mux topic inputs 是否註冊正確、`/cmd_vel_nav` remap / subscriber（bt_navigator 或 controller_server 是否訂閱）、`reactive_stop_node` mode、`map -> base_link` TF、Nav2 lifecycle 是否 active、`/scan_rplidar` freshness。
  - **F7 smoke goal 期間動態檢查**（送一次 `goto_relative 0.0`（無效 goal）或內建 dry-run goal 觸發 publisher）：`/cmd_vel_nav` publisher count + Hz 達門檻。
  - 任一階段不過 → 對應 FAIL 訊息，**靜態 FAIL 阻擋啟動，動態 FAIL 阻擋進入 nav demo**。
- **涉及**：`pawai_cli/demo_preflight` 模組、`scripts/start_nav_capability_demo_tmux.sh`。
- **驗收**：故意留一個 `/cmd_vel_joy` publisher、靜態 preflight 必 FAIL；故意 `safety_only=true`，靜態 preflight 必 FAIL；F7 smoke goal 階段未觀察到 `/cmd_vel_nav` publisher → 動態 preflight 必 FAIL。

### Line E：D435 active-nav policy（治理決策，不是大改）
- **問題**：D435 `depth_clear` 目前只擋**新** action，不會停**已在跑** 的 Nav2 goal。語意不一致。
- **目標**：兩條路二選一，**本窗口必須選一邊明文化**：
  - **E1 (保守，建議)**：明文寫死「D435 = gate only」— `depth_clear` 變 false 時不 stop active nav，依賴 reactive_stop 處理；Studio 上顯示「D435 status: gate only」避免老師 / 隊員誤會。
  - **E2 (積極，加分線)**：`depth_clear` false 時，呼叫 `/nav/pause` 暫停當前 goal；resume 必須由 `depth_clear` 回 true **且** 明確操作確認。
- **涉及**：`depth_safety_node`、`nav_action_server_node`、Studio 顯示。
- **驗收**：依選擇有對應行為；Studio 上 D435 policy 文字與實際行為一致。

### Line F：named locations 資產（route 列 P1）
- **問題**：`runtime/nav_capability/named_poses/` 目前空 / `routes/` 範例只有 `sample`。
- **P0 目標**：到 demo 場地後預錄 **≥ 2 個（建議 4–5）named locations**（沙發 / 主人座位 / 玄關 / 飯碗 / charging dock）。**只是資產，不需 code**。
- **P1 加分（不在 P0 驗收內）**：1 條 demo route（demo_loop），對應 §6 matrix「route patrol」。
- **涉及**：`/log_pose` action + `runtime/nav_capability/named_poses/`（P1 加分時用 `routes/`）。
- **驗收（P0）**：`/nav/goto_named <name>` 對至少 2 個 named locations 各成功 1 次。route 驗收見 §7 step 9（P1）。

### Line G：Studio Nav Panel
- **問題**：Studio 沒有 nav 操作 / 觀測面板。
- **目標**：把 `/capability/nav_ready`、`/capability/depth_clear`、`/state/nav/paused`、`/state/nav/status`、`/state/reactive_stop/status`、`/cmd_vel`（最近 1Hz）包成單一 panel：狀態燈號 + 「為什麼停」一行字 + 緊急停按鈕。
- **緊急停按鈕路徑**：呼叫既有 `emergency_stop.py engage`（或等效 service）走 Go2 `StopMove (api_id=1003)` 路徑作真正停車。`/cmd_vel_emergency` 僅作為 twist_mux input（priority 255）的副線，**不可單獨把單次 0 velocity 當急停** — twist_mux timeout 0.5s 後就不再 mask，Go2 sport mode 對 `cmd_vel=0` 也不保證停車（見 CLAUDE.md「Go2 sport mode：cmd_vel = 0 不會停車」）。
- **涉及**：`pawai-studio/frontend/` Nav panel 元件 + Studio Gateway nav topic 訂閱。
- **驗收**：demo 中任一時刻，老師看 Studio 能立刻知道「PawAI 在做什麼 / 為什麼停 / 我能不能緊急停」。

---

## 6. P0 / P1 / Future Matrix

| 功能 | 6/18 定位 | 原因 |
|---|---|---|
| 0.3–0.5m 短距移動 | **P0 必達** | DoD 第 1 條 |
| 遇障停車 + 不暴衝 | **P0 必達** | 安全紅線 |
| 語音 / Studio 觸發 nav | **P0 必達** | Line B（Executive NAV executor） |
| named places ≥ 2 | **P0 必達** | Line F，零新依賴 |
| Studio Nav Panel | **P0 必達** | Line G |
| F7 不復現 | **P0 必達** | Line A |
| preflight 補完整 | **P0 必達** | Line D |
| `nav_ready` 升級 | **P0 必達** | Line C |
| D435 policy 明文化 | **P0 必達**（選 E1 或 E2） | Line E |
| route patrol（多點巡演） | **P1 加分** | Line F 完成後自然衍生 |
| 受控場地一次靜態繞行 | **P1 加分** | 北極星 §4 加分線；失敗必降級停車 |
| D435 `depth_clear=false` 觸發 `/nav/pause` | **P1 加分**（= E2） | 若 E1 落地有餘裕再升 |
| `nav2 collision_monitor`（取代 reactive_stop 的正式替代） | **P1 加分** | 評估線 |
| 動態人流繞行 | **Future** | Go2 急停曲線差，6/18 不承諾 |
| 跟隨人 / face follow | **Future** | skill 標 high-risk，Executive NAV executor 先把基本 nav 做穩 |
| 自主尋物完整閉環 | **Future** | 需 spatial memory，超出本窗口 |
| D435 完全進 Nav2 local costmap | **Future** | observation_sources 整合工作量大 |
| IMU EKF fusion（robot_localization） | **Future** | 已知 AMCL 弱點，6/18 不修，spec 明文承認 |
| L1 LiDAR fallback（CMU 路線） | **Future** | 僅在 RPLIDAR 供電持續炸時評估 |
| Motion primitive local planner（CMU 概念） | **Future** | reactive_stop 進階版方向標 |

---

## 7. Acceptance Protocol

**每次 demo 前**（preflight 兩階段，沿用 Spec A 設計）：

1. **Dev local 階段**：`pawai demo preflight --target local` 全 PASS（Jetson-only checks 可 SKIP）。
2. **Jetson post-start 階段**：`pawai demo start --nav capability` hook preflight 全 PASS — 含 Line D 補的所有檢查。

**Nav demo 段 sequence**（30 分鐘以內可全跑）：

| # | 動作 | 通過條件 |
|---|---|---|
| 1 | F7 motion test | 連發 10 次 `goto_relative 0.3m`，`/cmd_vel_nav` 都有出；若 F7 復現，watchdog ≤ 5s 自動 recover |
| 2 | `goto_relative 0.3m` × 3 | 走完並回 succeeded；過 `nav_ready` + `depth_clear` gate |
| 3 | `goto_relative 0.5m` × 3 | 同上 |
| 4 | obstacle stop | 路徑上放障礙，Go2 應在 ≤ 1.1m 停下，Studio 顯示「前方有障礙」；TTS 播報 |
| 5 | named place（2 點輪流） | `goto_named` 兩個 named locations 各成功 1 次 |
| 6 | abort / cancel | 移動中送 `/nav/cancel`，Go2 立即停車，**不自動重送** |
| 7 | no auto-resume | 障礙移開後 Go2 必須等明確 resume 或新 goal，**絕不自動暴衝** |
| 8 | Studio visibility | 整段 demo 中 Studio Nav Panel 狀態與實際行為一致 |
| 9 | (P1 加分) route patrol | `run_route demo_loop` 跑完一圈回原點 |
| 10 | (P1 加分) 受控繞行 | 受控場地單一靜態障礙，一次成功局部重規劃 |

---

## 8. Non-goals

明文擋掉「看起來酷但會炸掉本窗口」：

- **不做** 完整自主尋物閉環
- **不做** 複雜動態人流繞行
- **不換** Nav2 / AMCL / Cartographer 主棧
- **不引入** Point-LIO / FAR Planner / terrain_analysis / motion primitive 任何 CMU 元件
- **不直打** sport API 繞過 twist_mux 安全鏈
- **不把** D435 宣稱成「完整避障」— 除非 E2 落地（即使 E2 落地，仍只是「pause active nav」不是 costmap fusion）
- **不把** Gazebo simulation 當實機驗收依據
- **不承諾** 跟隨人 / face follow 作為必達
- **不承諾** detour profile 作為必達（北極星 §4 已說明 detour profile 腳本有多處 bug，6/18 不展，除非先修）

---

## 9. Operator Safety / 切換 demo 前的清理

`nav-cap-demo` 可能以**沒有 demo lock 的 nav tmux / direct ROS launch**形式存在（`pawai status` 可能顯示「drivers running with no demo lock」）。**不要只靠 `pawai demo stop`**。切換 brain demo / 啟其他 lane 前，按嚴重程度由輕到重執行：

**Step 1：優先走 lane 清理工具**（最乾淨，會處理 lock + DDS state）
```bash
# 用 nav-avoidance-lane skill 的 cleanup（會走正確 graceful shutdown）
# 或：
pawai demo stop                   # 若有 lock owned-by-self
```

**Step 2：tmux session 級清理**（graceful，會讓內部 process 收 SIGTERM）
```bash
tmux ls                           # 看哪些 session 殘留
tmux kill-session -t nav-cap-demo 2>/dev/null || true
# 等 2-3 秒讓 ROS node 收 SIGTERM 後 graceful exit
```

**Step 3：用 `pawai status --short` 驗證**
```bash
pawai status --short
# 確認 tmux sessions: none、Go2 driver processes: (none)
```

**Step 4：仍有殘留時的 targeted graceful kill**（先 SIGTERM 不要 SIGKILL）
```bash
pgrep -af 'go2_driver|nav2|amcl|reactive_stop|twist_mux|sllidar|realsense2_camera'
# 對特定 PID 先送 SIGTERM
# kill <pid>                       # SIGTERM
# 等 5 秒後若仍存在再升級
```

**Step 5：最後手段 — `pkill -9`**（會留下 ROS/DDS stale state；用後**必須**重跑 Step 3 驗證）
```bash
# 只在 Step 4 失敗後使用；逐個 process 名 kill，不要寬鬆 pattern
pkill -9 -f 'go2_driver_node'
pkill -9 -f 'reactive_stop_node'
# ...
# 之後 pawai status --short 再次驗證；若 DDS 仍 stale，重啟 ros2 daemon：
# ros2 daemon stop && ros2 daemon start
```

**為什麼這條要寫進 spec**：5/11 撞牆事件就是「殘留 publisher 在 mux timeout 後接管」的變形。Nav demo 結束→開 brain demo 之間的乾淨切換，是 6/18 demo flow 的隱形 prerequisite。`pkill -9` 是核武，**不是預設工具** — 它會跳過 ROS2 cleanup、留 DDS shared memory / lock 殘骸，下次啟動可能 hang 或 silent fail。

---

## 10. 邊界宣告

**本文件是 implementation spec，不是 implementation plan**。
- 定「要做到什麼、怎麼驗收、哪些線是 P0 / P1 / Future」
- **不排** 每日任務
- **不指定** PR 順序或負責人
- **不指定** 哪一行 code 怎麼改

Implementation plan 由後續用 `superpowers:writing-plans` 從本 spec 拆出。

---

## 變更紀錄
- 2026-05-20 草稿建立。
- 2026-05-20 reviewer 修正五項：
  - §3 / Line B「唯一上 code」措辭收緊為「唯一接通 Brain→Executive→Nav 的 code 線」，避免低估其他 Lines 工程量
  - Line D preflight 拆兩階段（靜態 + F7 smoke goal 動態），避免 `/cmd_vel_nav` 啟動前無 publisher 造成 false FAIL
  - Line G 緊急停按鈕走 `emergency_stop.py engage` → Go2 StopMove，明文點 `/cmd_vel_emergency` 0 velocity 不可單獨當急停（Go2 sport mode cmd_vel=0 不停車）
  - Line F P0 驗收只到 ≥2 named places；route_loop 移到 P1（與 §6 matrix 一致）
  - §9 cleanup 重排五步：lane 工具 → tmux kill → status 驗證 → SIGTERM → `pkill -9` 為最後手段，明寫 DDS stale 風險與 ros2 daemon 重啟
