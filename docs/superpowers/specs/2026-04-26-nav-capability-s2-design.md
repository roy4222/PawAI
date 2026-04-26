# Nav Capability S2 — Design Spec

**Status**: Design (waiting for user approval)
**Date**: 2026-04-26
**Author**: roy422 + Claude (collaborative brainstorming)
**Supersedes**: None
**Related**:
- [`docs/導航避障/README.md`](../../導航避障/README.md) — current state (P0-D 完成)
- [`docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`](2026-04-24-p0-nav-obstacle-avoidance-design.md) — 4/24 P0 spec
- [`docs/導航避障/research/2026-04-26-nav2-dynamic-obstacle-log.md`](../../導航避障/research/2026-04-26-nav2-dynamic-obstacle-log.md) — 4/26 實機 log
- AMIGO ROS2 研究筆記（commit 96e830cc）

---

## 1. 目標與定位

### 1.1 一句話定位

> 導航避障模組（`nav_capability`）提供「**可被互動 / 守護任務呼叫的安全移動能力**」：能定位、移動到目標、執行預設 route、遇障暫停、障礙清除後續行、可取消，並持續回報狀態。**它不負責辨識人臉、語音、手勢、物體，也不決定業務劇本。**

### 1.2 在專案中的位置

```
Layer 3（中控）  interaction_executive / pawai_brain
                       │ (action call)
                       ▼
─────────────────────────────────────────
Layer 2.5（新）  nav_capability  ◀── 本 spec 範圍
                       │
                       ▼
Layer 2（規劃）  Nav2 (DWB + AMCL + map_server)  ◀── 不動演算法
                       │
                       ▼
─────────────────────────────────────────
Layer 1.5（既有） twist_mux  ◀── 升級為 4 層
                       │
                       ▼
Layer 1（驅動）   go2_robot_sdk (driver + reactive_stop)  ◀── 微調 publisher
                       │
                       ▼
                      Go2
```

### 1.3 任務範圍（S2 Standard）

選擇 S2 中間檔的理由：S1（minimum）會把編排責任丟給 interaction_executive，當其他六大模組都還沒整合時會變成「導航做完但沒人會用」；S3（extended）含跟隨模式風險高、5/13 ROI 差。S2 是「導航自己能用 mock 訊號演完整 demo」的最小集，且對其他模組整合最好接。

### 1.4 Mission 對齊

CLAUDE.md 寫明「互動 70% / 守護 30%」。本 spec 不決定業務劇本，但**為兩種典型互動行為提供基礎能力**：
- 互動：使用者觸發 → Go2 移動到目標位置（goto_named / goto_relative / goto_standoff）
- 守護：預定 route 巡視 → 遇人停 → 走開續行（run_route + pause/resume）

### 1.5 不在範圍

明確劃線：

| 不在 spec 範圍 | 為什麼 |
|--------------|--------|
| 物體辨識 / 人臉辨識 / 語音意圖 / 手勢識別 | 對應 perception 模組責任 |
| 業務劇本（手勢過來、找瓶子、跟隨）| `interaction_executive` / `pawai_brain` 責任 |
| Nav2 演算法替換（DWB → MPPI、NavfnPlanner → Smac）| 5/13 後重測，本次不動 |
| Cartographer 演算法 | 不動 |
| Go2 driver 控制橋（既有 `RobotControlService` 不動）| 已有 clamp / deadband，比 AMIGO 成熟 |
| **動態繞障策略** | DWB 自己能繞算 bonus，本 spec 只承諾「停障 pause / resume」 |
| 跟隨模式 | D435 視角窄、人轉身會丟，5/13 ROI 差 |
| Frontier exploration / 多房間切換 | 教室單一空間不需要 |
| Nvblox / STVL / 3D LiDAR | 硬體 / 容器 / 算力不對齊 |

---

## 2. Architecture

### 2.1 Pkg 結構

| Pkg | 既有 / 新建 | 責任 |
|-----|:---:|------|
| `go2_robot_sdk` | 既有 | driver、`reactive_stop_node`、odom（主體不動，僅 publisher topic 微調）|
| **`nav_capability`** | **新建** | 對外 API、Route Runner、Pose Logger、State Broadcaster |
| `go2_interfaces` | 既有 | 加 4 個 action schema + 3 個 service schema |
| `interaction_executive` | 既有 | 本 spec 不動；之後接 `nav_capability` 上做業務劇本 |

### 2.2 為什麼新建 `nav_capability` 而不放 `go2_robot_sdk`

- driver 是硬體抽象，沒有 ROS2 編排語意
- `nav_capability` 是 ROS2 編排，跟硬體解耦（理論上換 quadruped 也能用）
- 將來 unit test 不用拖 WebRTC 依賴
- task hook（`tts` / 未來 `face_check` / `object_scan`）不該污染 driver domain

### 2.3 Node 列表（`nav_capability` 內）

| Node | 責任 |
|------|------|
| `nav_action_server_node` | 4 個 action server 入口，包裝 Nav2 NavigateToPose |
| `route_runner_node` | run_route action 的 FSM（idle / planning / moving / paused / waiting / tts）|
| `log_pose_node` | log_pose action server，訂 `/amcl_pose` 寫入 JSON |
| `state_broadcaster_node` | 持續發 heartbeat / status / safety topic |
| `pause_resume_service_node` | 三個 service 端點（pause / resume / cancel）|

實作上前三個可以合併成一個 process，看 colcon build 後測試效率決定。

---

## 3. 對外介面（Public Interfaces）

### 3.1 4 個 Actions

#### A1. `/nav/goto_relative`

```
# go2_interfaces/action/GotoRelative.action
# Goal
float32 distance         # m, 正數=往前 / 負數=後退
float32 yaw_offset       # rad, 預設 0
float32 max_speed        # m/s, 預設 0.5（≤ 0.7 安全上限）
---
# Result
bool    success
string  message          # "reached" | "obstacle_timeout" | "cancelled" | "amcl_lost"
float32 actual_distance
---
# Feedback (10 Hz)
float32 progress         # 0.0 - 1.0
float32 distance_to_goal
```

**實作備註**：v1 一律走 Nav2 `NavigateToPose`（需要 map frame）— 用當前 `map → base_link` TF 算 map-frame goal pose（current_xy + R(current_yaw + yaw_offset) · [distance, 0]）。**不**支援純 odom relative goal（避免實作分裂成兩套控制邏輯，受 Nav2 / direct cmd_vel 兩條 path）。AMCL 不在線時直接 reject + 回 `"amcl_lost"`。純 odom 路徑列入 §14 T5（5/13 後 P1）。

#### A2. `/nav/goto_named`

```
# go2_interfaces/action/GotoNamed.action
# Goal
string  name              # 從 named_poses.json 查
float32 standoff          # 預設 0.0；> 0 時退到該點前 standoff 公尺（standoff helper）
bool    align_yaw_to_target  # standoff > 0 時生效，預設 true
float32 max_speed
---
# Result
bool    success
string  message           # "reached" | "name_not_found" | ...
geometry_msgs/Pose final_pose
---
# Feedback (10 Hz)
float32 progress
string  current_state     # "planning" | "moving" | "approaching"
```

**`standoff` 設計理由**：併入 `GotoNamed` option 而不獨立成 action — standoff 是 goal transform，不是獨立任務。等之後 object module 給 target pose 時再升級成獨立 action。

#### A3. `/nav/run_route`

```
# go2_interfaces/action/RunRoute.action
# Goal
string  route_id          # 從 routes/{id}.json 載入
bool    loop              # 預設 false
---
# Result
bool    success
uint32  waypoints_completed
uint32  waypoints_total
string  message           # "completed" | "obstacle_timeout" | "cancelled" | "bad_route"
---
# Feedback (1 Hz)
uint32  current_waypoint_index
string  current_waypoint_id
string  current_state     # "planning" | "moving" | "paused" | "waiting" | "tts"
```

**只支援 3 種 task**：`normal` / `wait` / `tts`。其他模組要做 `face_check` / `object_scan` 等業務 hook，自己訂閱 `/event/nav/waypoint_reached` 自己決定。

#### A4. `/log_pose`

```
# go2_interfaces/action/LogPose.action
# Goal
string  name              # "teacher" 等
string  note              # optional
string  log_target        # "named_poses" | "route"
string  route_id          # log_target=route 時必填
string  task_type         # log_target=route 時必填，"normal" | "wait" | "tts"
---
# Result
bool    success
string  saved_path
geometry_msgs/Pose recorded_pose
```

### 3.2 3 個 Services

| Service | Type | 行為 |
|---------|------|------|
| `/nav/pause` | `std_srvs/Trigger` | **3 件事一起做**：(1) cancel 當前 Nav2 active goal（用 NavigateToPose action client cancel），(2) 記住 `current_waypoint_index`（route 中才有），(3) 由 `reactive_stop_node` 持續 publish `/cmd_vel_obstacle = 0`（priority 200 蓋 Nav2）保證真停。state → `paused`。**不假裝凍結 Nav2 active goal**（避免 BT timeout）。 |
| `/nav/resume` | `std_srvs/Trigger` | **3 件事一起做**：(1) 用同一個 waypoint 發出**新的** NavigateToPose goal（新 goal、新 BT context），(2) `reactive_stop_node` 停止 publish `/cmd_vel_obstacle`（讓 Nav2 cmd_vel 通過 mux），(3) state → `moving`。 |
| `/nav/cancel` | `go2_interfaces/srv/Cancel` (custom: `bool safe_stop`) | 取消當前 action，Nav2 cancel goal，state → `idle`。`safe_stop=true` 平滑減速；`false` 立刻 zero velocity。所有 cross-package interface schema 統一放 `go2_interfaces`（`nav_capability` 是 `ament_python` pkg，不在內部生 IDL）。|

### 3.3 1 個 Event Topic

```
/event/nav/waypoint_reached  (std_msgs/String, JSON payload)
{
  "route_id": "demo_0513",
  "waypoint_id": "wp2",
  "task": "wait",
  "pose": {"x": 1.8, "y": 0.6, "yaw": 0.2},
  "timestamp": "2026-04-30T15:23:01+08:00"
}
```

`interaction_executive` 訂閱此 topic 後可自行決定 face_check / object_scan / 等業務動作。

### 3.4 State Topics（先用 `std_msgs/String` JSON，避免 custom msg 拖 CMake / rosidl 成本）

| Topic | Type | Rate | 內容 |
|-------|------|:---:|------|
| `/state/nav/heartbeat` | `std_msgs/Header` | 1 Hz | nav_capability 活著 |
| `/state/nav/status` | `std_msgs/String` JSON | 10 Hz | 主狀態（見下）|
| `/state/nav/safety` | `std_msgs/String` JSON | 10 Hz | 安全狀態 |

**`/state/nav/status` JSON schema**：
```json
{
  "state": "idle|planning|moving|paused|waiting|tts|succeeded|failed",
  "active_goal": {
    "type": "relative|named|route|null",
    "id": "demo_0513|null",
    "started_at": "2026-04-30T15:20:00+08:00"
  },
  "distance_to_goal": 1.23,
  "eta_sec": 4.5,
  "amcl_covariance_xy": 0.18
}
```

**`/state/nav/safety` JSON schema**：
```json
{
  "reactive_stop_active": false,
  "obstacle_distance": 1.45,
  "obstacle_zone": "normal|slow|danger|emergency",
  "lidar_alive": true,
  "amcl_health": "green|yellow|red",
  "pause_count_recent_10s": 0
}
```

### 3.5 介面摘要表

| 類型 | 數量 | 名稱 |
|------|:---:|------|
| Action | 4 | goto_relative, goto_named, run_route, log_pose |
| Service | 3 | pause, resume, cancel |
| Event topic | 1 | /event/nav/waypoint_reached |
| State topic | 3 | heartbeat, status, safety |

---

## 4. twist_mux 升級

### 4.1 既有狀態

`go2_robot_sdk/config/twist_mux.yaml` 目前只有：
- `joy → /cmd_vel_joy`
- `navigation → /cmd_vel`

`robot.launch.py` 啟動 Nav2 時也未 remap `/cmd_vel`。導致 Nav2 與 reactive_stop 必須**互斥使用**（README 已聲明）。

### 4.2 升級後

```yaml
# go2_robot_sdk/config/twist_mux.yaml (升級版)
topics:
  - {name: emergency, topic: /cmd_vel_emergency, timeout: 0.5, priority: 255}
  - {name: obstacle,  topic: /cmd_vel_obstacle,  timeout: 0.5, priority: 200}
  - {name: teleop,    topic: /cmd_vel_joy,       timeout: 0.5, priority: 100}
  - {name: nav2,      topic: /cmd_vel_nav,       timeout: 0.5, priority: 10}

locks:
  - {name: e_stop_lock, topic: /lock/emergency, timeout: 0.0, priority: 255}
```

### 4.3 必須同步的 launch / node 改動

| 元件 | 改動 |
|------|------|
| `robot.launch.py`（Nav2 IncludeLaunchDescription）| 加 `cmd_vel_topic: /cmd_vel_nav` |
| `reactive_stop_node.py` | publisher 從 `/cmd_vel` 改 `/cmd_vel_obstacle` |
| Joy node | 確認既有發到 `/cmd_vel_joy`（既有應該已是）|
| Emergency 觸發源（未實作）| 同時發 `/cmd_vel_emergency = 0` + `/lock/emergency = std_msgs/Bool true` |

### 4.4 Lock 機制澄清

twist_mux 的 lock topic 是 `std_msgs/Bool`，**不是 Twist**。lock 生效時所有低於該 priority 的 publisher 都被擋下。emergency 必須**同時**發 cmd_vel_emergency（zero velocity）+ lock topic。

---

## 5. Route JSON v2 Schema

```json
{
  "schema_version": 1,
  "route_id": "demo_0513",
  "frame_id": "map",
  "map_id": "classroom_5_13",
  "created_at": "2026-04-30T14:00:00+08:00",
  "initial_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
  "waypoints": [
    {
      "id": "wp1",
      "task": "normal",
      "pose": {"x": 1.20, "y": 0.40, "yaw": 0.0},
      "tolerance": 0.30,
      "timeout_sec": 30
    },
    {
      "id": "wp2",
      "task": "wait",
      "pose": {"x": 1.80, "y": 0.60, "yaw": 0.20},
      "tolerance": 0.30,
      "timeout_sec": 30,
      "wait_sec": 3
    },
    {
      "id": "wp3",
      "task": "tts",
      "pose": {"x": 2.50, "y": 1.00, "yaw": 1.50},
      "tolerance": 0.30,
      "timeout_sec": 30,
      "tts_text": "我到了"
    }
  ]
}
```

### 5.1 欄位說明

| 欄位 | 必填 | 說明 |
|------|:---:|------|
| `schema_version` | ✓ | 強制檢查；不符直接 reject |
| `route_id` | ✓ | 唯一識別 |
| `frame_id` | ✓ | 必為 `"map"`，避免 odom/map 混淆 |
| `map_id` | ✓ | 綁定哪張 map（map 換了 route 飛牆的防呆）|
| `initial_pose` | ✓ | 建議起始位置（log_pose 寫入時自動帶當前 pose）|
| `waypoints[*].task` | ✓ | `"normal"` / `"wait"` / `"tts"` 三選一 |
| `waypoints[*].tolerance` | ✓ | 該點容忍距離，預設 0.30m |
| `waypoints[*].timeout_sec` | ✓ | 該點 timeout，預設 30s |
| `waypoints[*].wait_sec` | task=wait | 停留秒數 |
| `waypoints[*].tts_text` | task=tts | 要說的字串（直接 publish `/tts std_msgs/String`）|

### 5.2 檔案位置

`nav_capability/config/routes/{route_id}.json`

---

## 6. Named Poses Schema

```json
{
  "schema_version": 1,
  "map_id": "classroom_5_13",
  "poses": {
    "teacher": {"x": 1.20, "y": 0.40, "yaw": 0.0},
    "desk":    {"x": 2.50, "y": 1.10, "yaw": 1.57},
    "door":    {"x": 0.00, "y": 0.00, "yaw": 3.14}
  }
}
```

檔案位置：`nav_capability/config/named_poses/{map_id}.json`

---

## 7. Data Flow

### 7.1 Flow A — Goal 從觸發到 Go2 執行

```
External trigger (mock CLI / interaction_executive future)
   │
   ▼ Action call
nav_action_server_node
   │
   ├──> compute goal:
   │     - relative: 用 /odom 算 (current + Δ)
   │     - named:    從 JSON 查 + 套 standoff helper
   │     - route:    iterate waypoints (route_runner_node)
   │
   ▼ Nav2 NavigateToPose action client
Nav2 controller_server (DWB)
   │
   ▼ /cmd_vel_nav  (priority 10)
twist_mux
   │
   ▼ /cmd_vel
go2_driver_node.RobotControlService (clamp + deadband, 既有)
   │
   ▼ WebRTC msg 1008 (Move)
Go2 sport mode
```

### 7.2 Flow B — Pause / Resume（route 中人擋路）

```
RPLIDAR /scan_rplidar (10.4 Hz)
   │
   ▼
reactive_stop_node
   │
   ├──> if d < 0.6m (danger):
   │     publish /cmd_vel_obstacle = 0  (priority 200, 蓋 Nav2)
   │     [if enable_nav_pause==true]:  service call /nav/pause
   │
   ├──> if d ≥ 1.0m for 3 frames (clear):
   │     stop publishing /cmd_vel_obstacle
   │     [if enable_nav_pause==true]:  service call /nav/resume
   │
   └──> if pause > 15s (route_runner timer):
         service call /nav/cancel

route_runner_node (FSM)
   ├── pause: 記住 current_waypoint_index, 停送 Nav2 goal
   ├── resume: 用同一個 waypoint 重發新的 NavigateToPose goal
   │           (不假裝凍結 Nav2 — 上一個 goal 已 cancel)
   └── cancel: state → idle, 廣播 obstacle_timeout
```

**`enable_nav_pause` 參數設計**（修正自 4/26 review #4）：
- `reactive_stop_node` 加 ROS param `enable_nav_pause`（型別 `bool`，預設 `false`，可在 runtime 用 `ros2 param set` 切換）
- 預設：reactive 只發 `/cmd_vel_obstacle`，**不主動 call** `/nav/pause` / `/nav/resume`
- 啟用 nav demo 時：在 `start_nav2_amcl_demo_tmux.sh` 啟動後 `ros2 param set /reactive_stop_node enable_nav_pause true`，reactive 才會主動 trigger pause/resume
- 避免 reactive fallback 單獨跑時誤觸 nav services

### 7.3 Flow C — Emergency Override

```
Joy button / safety trigger
   │
   ├──> publish /cmd_vel_emergency = 0  (priority 255)
   └──> publish /lock/emergency = true  (lock 生效)
   │
   ▼
twist_mux
   ├── lock 生效 → 所有其他 priority 全擋
   └── output /cmd_vel = 0
   │
   ▼
Go2 立即停
```

---

## 8. Error Handling Matrix

| # | Failure mode | Detection | Response |
|:-:|--------------|-----------|----------|
| E1 | AMCL covariance 過大（位置不可信）| 訂 `/amcl_pose`，取 `pose.covariance` 對角元素 [0]+[7] 即 σ²x+σ²y，作為 `covariance_xy`；三段門檻：green < 0.3 / yellow 0.3-0.5 / red > 0.5 | green: 正常；yellow: 只允許 distance ≤ 0.5m 的 goal；red: reject 新 goal + 回 `"amcl_lost"` |
| E2 | Goal 在 lethal cell（map 髒）| Nav2 plan 失敗 | retry 2 次 + service call `clear_costmap` → 仍失敗回 `"unreachable"` |
| E3 | Obstacle pause > 15s | `route_runner_node` pause timer | cancel route + state → idle + 廣播 `"obstacle_timeout"` |
| E4 | RPLIDAR heartbeat lost > 1s | watchdog on `/state/obstacle/lidar_alive` | force `/cmd_vel_obstacle = 0` + reject 新 goal |
| E5 | Go2 driver disconnect | 訂 `/odom` timeout > 2s（**TODO**: 未來加 driver heartbeat / connection health topic） | abort 所有 active action + state → failed |
| E6 | Cancel 時 Nav2 還在跑 | wait_for_result race | cancel → wait Nav2 acknowledge → 才回 cancel success（≥ 0.3s gap）|
| E7 | Route JSON malformed / schema_version mismatch | 啟動時 validate | refuse to load + log + result `"bad_route"` |
| E8 | Named pose 不存在 | JSON key lookup miss | reject + result `"name_not_found"` + 列出可用 names |
| E9 | Waypoint timeout（單點 30s 走不到）| per-waypoint timer | route 整體判失敗（不 skip，避免 demo 飛點）|
| E10 | TTS task 但 `/tts` 沒人訂閱 | 1s 內無 ack | log warning，繼續走（不阻塞 route）|

### 8.1 AMCL covariance 三段門檻說明（修正自 4/26 review #2）

4/26 實機觀察 covariance 0.22 仍能成功 plan + 走 0.8m。所以原設計「> 0.5 reject」可保留為硬上限，但加 yellow 區段允許短距 goal：

| 區段 | 範圍 | 行為 |
|------|------|------|
| Green | covariance_xy < 0.3 | 全部 action 正常允許 |
| Yellow | 0.3 ≤ covariance_xy ≤ 0.5 | 只允許 distance ≤ 0.5m 的 goal；route 中段不切斷但廣播 warning |
| Red | covariance_xy > 0.5 | reject 所有新 goal，回 `"amcl_lost"`，建議使用者重設 initial pose |

---

## 9. Testing

### 9.1 L1 — Unit Tests（純 Python，no ROS）

`nav_capability/test/`：
- `test_relative_goal_math.py` — yaw + distance → x, y, yaw 計算
- `test_standoff_math.py` — target_xy + dist → goal_xy + goal_yaw
- `test_route_validator.py` — JSON schema 校驗（schema_version、tolerance、timeout 等）
- `test_named_pose_lookup.py` — name found / not_found / multi_map
- `test_pause_resume_fsm.py` — idle → moving → paused → resumed → moving 狀態轉移
- `test_waypoint_timeout_logic.py` — timeout 觸發判斷

**目標**：~25 cases，全離線，CI 跑 < 5s。

### 9.2 L2 — Integration Tests（Mock Nav2）

`nav_capability/test/integration/`：
- `test_goto_relative_with_mock_nav2.py`
- `test_run_route_with_mock_obstacle_pause.py`
- `test_cancel_during_route.py`
- `test_emergency_lock_blocks_all.py`
- `test_nav_action_lifecycle.py` — goal → feedback → result

Mock Nav2 用 `nav2_simple_commander` 或自寫 fake action server。
**目標**：~10 cases，CI 跑 < 30s。

### 9.3 L3 — 實機驗收

見 §10 KPI。

---

## 10. KPI / 完工驗收

### 10.1 P0（5/13 前必驗 — 8 項）

| # | 場景 | 通過標準 | 你列為核心 |
|:-:|------|---------|:---------:|
| K1 | `goto_relative 0.5m` × 5 次 | ≥ 4 次成功（80%）| |
| K2 | `goto_relative 0.8m` × 5 次 | ≥ 4 次成功 | |
| K4 | `run_route` 3-waypoint × 3 次 | 全 3 次完成 | |
| K5 | **Pause/Resume**：人擋 0.6m → 停 → 走開 → < 5s 續行 × 3 次 | 全 3 次續行 | ⭐ |
| K7 | **Emergency lock**：route 中按 emergency → < 1s 停 | 全 3 次停 | ⭐ |
| K8 | **twist_mux 4 層優先級** | 用 fake publisher 驗 nav < teleop < obstacle < emergency 各層覆蓋 | ⭐ |
| K9 | State topic 不間斷 60s | heartbeat ≥ 95% rate, status/safety ≥ 90% | ⭐ |
| K10 | `log_pose` × 5 名稱 → 寫入 JSON 後讀回一致 | 全 5 一致 | |

### 10.2 P1（5/13 加分項，非必驗 — 3 項）

| # | 場景 | 通過標準 |
|:-:|------|---------|
| K3 | `goto_named` 5 個命名點各 2 次 | 8/10 成功 |
| K6 | **Pause timeout**：人擋 > 15s → cancel | 1 次正常 cancel + state idle |
| K11 | 連跑 5 次 route 後 AMCL covariance | < 0.3（不爆增）|

### 10.3 P0 / P1 拆分理由（修正自 4/26 review #3）

K3 (5 個命名點各 2 次) 5/13 不一定需要這麼多命名點，可降級。
K6 (pause timeout) 與 K11 (covariance 累積) 是「壓力測試」性質，5/13 demo 不必驗，5/13 後再補。

---

## 11. Risk & Mitigation

| 風險 | 機率 | 影響 | 緩解 |
|------|:----:|:----:|------|
| Nav2 cancel + 重發 goal 時序衝突（BT 紊亂）| 中 | 高 | wait_for_result + 0.3s gap before 重發 |
| AMCL covariance 跑久爆增 | 中 | 中 | E1 三段監控；廣播 warning |
| Go2 driver disconnect 中 action 還在跑 | 中 | 高 | E5 watchdog + abort（TODO: driver heartbeat topic）|
| Route JSON schema 升級不向前相容 | 低 | 中 | `schema_version` 強制檢查；migrate script |
| reactive_stop 與 nav_capability pause/resume race | 中 | 中 | service idempotent；500ms debounce；`enable_nav_pause` flag |
| Jetson 跳電（XL4015）route 跑一半 | 中 | 高 | 不在 spec scope（硬體問題），但 state 要能 recover |
| 動態繞行：DWB 在小教室狹縫不穩 | 高 | 低 | 5/13 不承諾，bonus only |

---

## 12. 5/13 不承諾清單（明確聲明）

| 項目 | 為什麼不承諾 |
|------|------------|
| 動態繞行人 | DWB 在小教室狹縫繞行不穩，bonus only |
| 跟隨模式 | D435 視角窄，人轉身會丟 |
| Frontier exploration | 教室太小且 mission 不需要 |
| 多房間切換 | 教室是單一空間 |
| 速度 > 0.7 m/s | 安全考量 |
| 戶外 / 強光 | RPLIDAR + AMCL 不穩 |

**「不承諾 ≠ 不錄」**：實機真穩可當 bonus 段，不列為主 demo。

---

## 13. Out of Scope（補充 §1.5）

本 spec 明確不包含：
- Nav2 內部演算法替換或調參（DWB → MPPI / NavfnPlanner → SmacPlannerHybrid）
- Cartographer 演算法 / 建圖流程改動
- Go2 driver `RobotControlService` 內部邏輯
- Camera / D435 整合（face / object 模組責任）
- 業務劇本（手勢 / 語音 / 物體 → 移動意圖的 mapping）
- Migrate to MPPI 或 SmacPlannerHybrid（5/13 後再評估）
- Nvblox / STVL / 3D LiDAR layer

---

## 14. TODO / Open Questions

| # | 項目 | 何時解決 |
|:-:|------|---------|
| T1 | Driver heartbeat / connection health topic（E5 detection 改良）| Implementation plan 階段加新增 publisher（如 `/state/driver/heartbeat` 或 `/state/driver/health`），**僅作為 status 廣播，不改 `RobotControlService` 控制橋邏輯**（與 §13 Out of Scope 一致）|
| T2 | Emergency 觸發源實作（joy button / GUI button / safety relay）| Implementation plan 階段決定 |
| T3 | `nav_capability` 中 5 個 node 是否合併成單一 process | Implementation 階段量測決定 |
| T4 | Map 重建後 named_poses / routes JSON 自動 migration 工具 | 5/13 後 |
| T5 | `goto_relative` 支援純 odom path（不依賴 AMCL，5/13 後 P1）| 5/13 後評估，需要避免兩套控制邏輯分裂（可能改用 direct cmd_vel + odom feedback，與 Nav2 path 並列）|

---

## 15. Acceptance Criteria（spec 通過標準）

本 spec 通過 `roy422` review 後：
1. ✅ 進入 `superpowers:writing-plans` 階段建立 implementation plan
2. ✅ Implementation plan 拆成 ~6-7 天工作的 task 清單
3. ✅ 標準 TDD 流程開發（test 先寫，test 通過才寫 code）
4. ✅ 每完成一個 milestone 對照 §10 P0 KPI 跑驗收
5. ✅ 5/13 前 P0 KPI 全綠燈，spec 視為達成

---

## 附錄：與 AMIGO ROS2 的關係

本 spec **參考但不照抄** AMIGO（commit 96e830cc）：

| AMIGO 元件 | 我們的決定 |
|-----------|-----------|
| `LogPose.action` + `pose_log.json` | ✅ 借用概念，schema 強化（schema_version、map_id、tolerance、timeout）|
| `task_nav_to_pose_test.py`（normal vs task）| ✅ 借用 task_type 概念，但 task 砍到 normal/wait/tts 三種 |
| `BasicNavigator` + retry 6 次 + assistedTeleop | ❌ 不抄，改用 pause/resume FSM + cancel |
| `go2_driver_node.cpp` cmd_vel → SportClient | ❌ 不抄，本地 `RobotControlService` 比 AMIGO 成熟（有 clamp / deadband）|
| `nav2_mppi_controller.yaml` | ❌ 不抄，5/13 用 v3.7 DWB |
| `SmacPlannerHybrid` | ❌ 不抄，5/13 後重測 |
| `nvblox` | ❌ 硬體 / 容器 / 算力不對齊 |
| `region_map_service_node` | ❌ 教室單一空間，5/13 後可借 connected component 概念 |
| URDF `laser_joint xyz="0.22 0 0.12"` | ⚠️ 參考但 mount 不同，5/13 前需實測 base_link → laser TF |

---

**Spec END**
