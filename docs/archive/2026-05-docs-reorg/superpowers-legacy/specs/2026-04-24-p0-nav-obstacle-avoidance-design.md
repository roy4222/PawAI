# P0 導航避障系統設計規格

> **Status: current**
> Date: 2026-04-24
> Author: 盧柏宇
> Scope: P0 動態避障（A→遇障→停→TTS→續行→B）設計定稿 + PawAI Brain 三層架構整合 + 實作 phasing + 5/13 學校 Demo 計畫
> Supersedes (部分): [`docs/導航避障/README.md`](../../導航避障/README.md) 的「架構決策（2026-04-01 最終判定）」章節 — Full SLAM / Nav2 從「永久關閉」改為 P0 主線

---

## 關於本 Spec

### 與 4/11 PawAI Brain Spec 的關係

**繼承**（不改）：
- 三層架構（Safety Layer / Policy Layer / Expression Layer）
- Skill Contract 格式（preconditions / expected_outcome / fallback）
- `/state/pawai_brain` 結構化觀測
- 降級路徑（LLM → RuleBrain → Safety-only）
- Safety event 立即清空 skill queue

**擴充**（新增至現有 spec）：
- PawAI Skills 加 `patrol_route`（Policy Layer, navigation category）
- Safety Layer 加 Emergency State Machine + Obstacle FSM
- Expression Layer 加 `safety_tts` 與 `navigation status_tts` 兩類固定模板（永不經 LLM）
- `/state/pawai_brain.safety_flags` 擴充欄位

### 觸發契機

- 2026-04-24 外接 RPLIDAR A2M12 到貨並完成桌上驗證（10.57Hz / 1800 pts / 60% valid）
- 舊 Go2 內建 LiDAR 的 18% 覆蓋率與 burst+gap 問題完全解決
- 「Full SLAM 永久關閉」判定（2026-04-01，基於 5Hz 品質差）**失效**，SLAM/Nav2 路線復活
- 4/18 老師會議強調「守護」場景價值，導航避障是守護能力的實體基礎

---

## 1. 目標與範圍

### 1.1 P0 硬承諾（主線，不可砍）

**Demo 畫面定義（劇本 E）**：

```
Go2 站在 A 點待命
→ 主持人觸發（語音/按鈕）patrol_route
→ Go2 自主往 B 點走（0.2 m/s）
→ 路中有人或紙箱擋住
→ Go2 停下
→ 播固定台詞「前方有障礙，請讓路」
→ 障礙物離開
→ 連續 3 秒確認淨空
→ 自動續行
→ 到達 B 點停下
→ 播「已到達目的地」
```

**不承諾**：
- 一般動態繞障（邊走邊繞過移動物）
- 多 waypoint 巡邏
- 折返（A→B→A）
- 未建圖區域自主探索
- 跨門檻、樓梯、不同地板材質

### 1.2 P1 Stretch Goal（有條件做）

**C 方案：單一靜態障礙簡單繞行一次**

- 前提：**2026-05-06 家中排練 KPI 4/5 通過才啟動**
- 最晚開工：2026-05-07
- 最晚收斂：2026-05-10
- 5/10 沒做出來直接砍，不帶 Demo

### 1.3 硬邊界

- **場地**：小會議室 4-6m × 4-6m（家中客廳先驗 → 學校小會議室 Demo）
- **速度**：0.2 m/s（5/6 KPI 穩後可升 0.25/0.3，不升到 0.5）
- **障礙物類型**：人站立 + 紙箱/椅子兩種靜態障礙
- **路徑**：近似直線 3-4m，單一 goal（P0 無中繼 waypoint）
- **時程**：2026-05-13 帶去學校，2026-05-19 開始三天驗收

### 1.4 KPI

**2026-05-06 家中排練驗收門檻**：

| 成功次數 / 5 次 | 判定 | 後續動作 |
|:-----:|:----:|------|
| 4-5/5 | **GO** | 正常進 5/7 Stretch C |
| 3/5 | **YELLOW** | 不做 C，全力補 P0 |
| ≤2/5 | **NO-GO** | 降級 Demo（改純反應式守護 + 錄影） |

**成功定義**（單次試跑）：
- 到達 B 點誤差 <30cm
- 遇障停下反應時間 <1.5s
- 障礙清空後 <4s 續行
- 全程無 Go2 撞擊、無 emergency latch 觸發

---

## 2. 整體架構（對齊 PawAI Brain 三層）

### 2.1 導航避障如何嵌入三層

```
┌────────────────────────────────────────────────────────────┐
│  Layer C: Expression Layer                                 │
│  ─────────────────────────────                            │
│  interaction_tts（chat / greet / acknowledge）← LLM 可參與  │
│  safety_tts         （固定 2 句）              ← 永不經 LLM │
│  navigation status_tts（固定 4 句）            ← 永不經 LLM │
│  Studio trace narration                                    │
└────────────────────────┬───────────────────────────────────┘
                         │ skill + reply_text
┌────────────────────────▼───────────────────────────────────┐
│  Layer B: Policy Layer                                     │
│  ─────────────────────────────                            │
│  PawAI Skills                                              │
│    • interaction skills（chat / greet / acknowledge_gesture）│
│    • guardian skills（alert_unknown_person）               │
│    • navigation skills（patrol_route） ← P0 新增           │
│      └─ 內部呼叫 Nav2 stack（deterministic，非 LLM）       │
│  PawAI Memory（per-person, greeting_cooldown）             │
│  Policy Override（deterministic rules 永遠可覆蓋 LLM）      │
└────────────────────────┬───────────────────────────────────┘
                         │ skill_contract + action
┌────────────────────────▼───────────────────────────────────┐
│  Layer A: Safety Layer（deterministic，最高優先）            │
│  ─────────────────────────────                            │
│  Obstacle Guard    ← lidar_obstacle_node → /event/obstacle │
│  Emergency Gate    ← 鍵盤 hotkey / Studio 按鈕 / Foxglove   │
│    ├─ Latched state（trigger/reset service）               │
│    ├─ twist_mux 最高優先 zero Twist                         │
│    └─ WebRtc api_id 1003 (StopMove) 雙保險                  │
│  Pre-action Validation（readiness + banned_api）           │
│  Safety event → 立即清空 skill queue、中斷 patrol_route     │
└────────────────────────┬───────────────────────────────────┘
                         │
              twist_mux (priority-ordered)
                         │
                  Go2 Driver (WebRTC)
```

### 2.2 資料流（P0 時）

```
RPLIDAR /scan (10.5Hz) ────► lidar_obstacle_node ──► /event/obstacle_detected
                                                         │
Nav2 /cmd_vel_nav ───────────────────────────────┐       │
                                                  ▼       ▼
鍵盤 hotkey ──► emergency_stop.py ──► /pawai/safety/trigger_emergency (service)
Studio 按鈕 ──► WebSocket ──► FastAPI ──► (same service)
Foxglove    ──► Service Call ──────────► (same service)
                                                  │
                                                  ▼
                                        Executive (Safety Layer)
                                                  │
                                          priority arbitration
                                                  ▼
                                        twist_mux
                                           ├── emergency (255)
                                           ├── obstacle  (200)
                                           ├── teleop    (100)
                                           └── nav2      (10)
                                                  │
                                                  ▼
                                        Go2 Driver (/webrtc_req + WebRTC)
```

---

## 3. Safety Layer 細節

### 3.1 Emergency State Machine（不是 Bool topic）

**兩個狀態、兩個轉換**：

```
┌─────────────────────────┐    trigger_emergency
│        NORMAL           │ ──────────────────────┐
│  Nav2 cmd_vel 可通過    │                       │
│  obstacle auto-recovery │                       ▼
└─────────────────────────┘    ┌──────────────────────────────┐
         ▲                     │   EMERGENCY_LATCHED          │
         │                     │   ─────────────────────      │
         │ reset_emergency     │   • 所有 cmd_vel 被阻擋       │
         │ (明確呼叫)          │   • twist_mux emergency = 0  │
         │                     │   • 持續發 StopMove(1003)    │
         └─────────────────────│   • obstacle 事件不參與控制   │
                               │     決策（觀測仍保留）        │
                               │   • **凍結所有恢復類請求**    │
                               │     （nav2/teleop/patrol）   │
                               │   • 重複 trigger = 冪等      │
                               │   • TTS 播一次「緊急停止」    │
                               └──────────────────────────────┘
```

**進入 EMERGENCY_LATCHED 的三件事（原子操作）**：
1. State 變 `EMERGENCY_LATCHED`（Executive 記憶體變數）
2. 連發 5 次 zero `Twist` 到 `/cmd_vel_emergency`（twist_mux 最高優先 input）
3. 送 `StopMove(1003)` 到 `/webrtc_req`（WebRTC 直接硬停）

**為什麼 state machine 不是 bool topic**：
- Bool topic 有 race condition — 誰最後 publish 蓋掉誰
- State 在 Executive 內部變數，**只有 service call 能改**
- 重複觸發冪等、reset 明確
- 斷線重連時 state 不會漂移

### 3.2 Service 介面

**P0 使用 `std_srvs/Trigger`**（簡單夠用），spec 註記可升級：

```
/pawai/safety/trigger_emergency  (std_srvs/Trigger)  ← 觸發鎖死
/pawai/safety/reset_emergency    (std_srvs/Trigger)  ← 明確解鎖
```

**可升級路徑**（P1 或後續版本）：改為自定義 srv，帶 `source`（keyboard/studio/foxglove）+ `reason`（manual_stop/demo_abort/unsafe_motion）。debug 與稽核更強。

**三個入口都 funnel 到同一個 service**，無 race、無優先級衝突：

| 入口 | 實作 | 角色 |
|------|------|------|
| 鍵盤 hotkey | `scripts/emergency_stop.py`（q=trigger, r=reset）| **Primary kill switch** |
| Studio 按鈕 | React button → WebSocket → FastAPI → ROS service call | Secondary convenience |
| Foxglove | Service Call panel 直接打 service | Demo/debug 用 |

### 3.3 Obstacle Guard FSM（跟 Emergency 是兩條獨立線）

```
Obstacle FSM（auto-recovery）:
┌────────────┐  obstacle detected   ┌──────────────────┐
│  CLEAR     │ ───────────────────► │  OBSTACLE_STOP   │
│            │                      │  • zero Twist    │
│            │                      │  • safety_tts 1次│
│            │  3s 連續 clear       │  • patrol_handler│
│            │ ◄────────────────────│    .pause()      │
└────────────┘                      └──────────────────┘

Emergency 永遠 override Obstacle：
if emergency_latched:
    ignore obstacle events (but still observe/publish for Studio)
```

**debounce 已在 lidar_obstacle_node 做**（連續 3 frames），Executive 這邊只做狀態轉換。

**obstacle pause 超過 15s → 升級為 abort patrol**（不讓 Nav2 永遠掛著）：
```python
if obstacle_stop_duration > 15.0:
    patrol_handler.cancel()
    state = IDLE
    publish navigation_status_tts("定位失準，停止巡邏")  # 或另加一句
```

### 3.4 safety_tts 作為架構規則

**寫入 spec §5 命名體系**（跨 spec 硬規則）：

| TTS 類型 | 來源 | LLM 參與？ | 例句 |
|---------|------|:--------:|------|
| `interaction_tts` | Expression Layer | ✅ 可 | 「你在看書呀」|
| `safety_tts` | Safety Layer | ❌ 永不 | 「前方有障礙，請讓路」|
| `navigation status_tts` | Safety Layer | ❌ 永不 | 「已到達目的地」|

**P0 白名單（6 句固定模板）**：

```python
# safety_tts.py 模組負責這兩類（合併實作，不拆模組）
SAFETY_TTS = {
    "obstacle_warning":    "前方有障礙，請讓路",
    "emergency_triggered": "緊急停止，請協助處理",
}
NAVIGATION_STATUS_TTS = {
    "patrol_start":        "開始巡邏",
    "arrived":             "已到達目的地",
    "patrol_abort":        "定位失準，停止巡邏",
    "patrol_timeout":      "巡邏超時，已停止",
}
```

**反洗版規則**：
- `obstacle_warning` 每次進入 OBSTACLE_STOP 只播一次
- 同一 obstacle session 內不重播（就算停 10 秒）
- 離開 OBSTACLE_STOP 後，**下次新的 obstacle** 才會再播

**實作位置**：Executive 內新增 `safety_tts.py` 模組（同一檔案處理 safety + navigation status 兩類），publish 到現有 `/tts` topic（不改 `std_msgs/String` 契約）。`interaction_tts` 發送前檢查 `safety_flags.tts_playing`，讓路給 safety/navigation TTS。

### 3.5 twist_mux Priority 配置

修改 `go2_robot_sdk/config/twist_mux.yaml`：

```yaml
topics:
  emergency:
    topic:    /cmd_vel_emergency
    timeout:  0.5
    priority: 255                  # 最高
  obstacle:
    topic:    /cmd_vel_obstacle
    timeout:  0.5
    priority: 200
  teleop:
    topic:    /cmd_vel_teleop
    timeout:  0.5
    priority: 100
  nav2:
    topic:    /cmd_vel_nav
    timeout:  0.5
    priority: 10                   # 最低
```

**優先級排序**：`emergency > obstacle > teleop > nav2`

**刻意選擇**：`obstacle > teleop` — P0 不開「人工強制越過障礙」口子。

### 3.6 Pre-action Validation

進入 `patrol_route` skill 前，Safety Layer 檢查：

```python
def can_start_patrol(state) -> tuple[bool, str]:
    # Safety gate
    if state.emergency_latched:
        return False, "emergency_latched"
    # Nav stack readiness
    if not state.map_loaded:
        return False, "no_map"
    if not state.amcl_converged:
        return False, "localization_not_ready"
    # 感測鏈 heartbeat
    if not state.scan_heartbeat_ok:
        return False, "scan_stale"
    if not state.nav_stack_ready:
        return False, "nav_stack_not_ready"
    if not state.twist_mux_alive:
        return False, "twist_mux_not_alive"
    # 硬體
    if state.battery_low:
        return False, "low_battery"
    return True, "ok"
```

失敗 → 用 `safety_tts` 或 `interaction_tts` 解釋原因（看是安全阻擋還是狀態不足）。

---

## 4. Policy Layer 細節

### 4.1 patrol_route Skill Contract

```python
patrol_route = {
    "skill_id":   "patrol_route",
    "category":   "navigation",
    "preconditions": [
        "map_loaded",
        "amcl_converged",
        "scan_heartbeat_ok",
        "nav_stack_ready",
        "twist_mux_alive",
        "not emergency_latched",
    ],
    "parameters": {
        "waypoints":   [(B_x, B_y, B_θ)],      # P0: 單 goal
        "max_vel_x":   0.2,
        "timeout_sec": 30,                      # P0 場地小，30s 保守
        "goal_tolerance_xy":  0.3,
        "goal_tolerance_yaw": 0.3,
    },
    "expected_outcome": "Go2 reaches last waypoint (within 0.3m tolerance)",
    "fallback_action":  "transition_to_idle_and_zero_twist",  # 不是 skill，是 safety 行為
    "can_be_interrupted_by": [
        "emergency_trigger",   # 立刻 cancel + latch
        "obstacle_event",      # pause（不 cancel）
    ],
    "can_enqueue":     False,   # 長時間 skill，不放進 skill_queue
}
```

### 4.2 Nav2 呼叫機制

**Policy Layer 選 skill → Executive dispatch → `PatrolRouteHandler` → Nav2 Action Client**。Brain 不直接呼叫 Nav2。

```python
# interaction_executive/skills/patrol_route_handler.py
class PatrolRouteHandler:
    def __init__(self, node):
        self._nav = ActionClient(node, NavigateToPose, "/navigate_to_pose")
        self._current_goal_handle = None
        self._state = "IDLE"
        # IDLE / NAVIGATING / PAUSED / COMPLETED / CANCELLED

    def start(self, waypoint):
        goal = NavigateToPose.Goal()
        goal.pose.pose.position.x = waypoint.x
        goal.pose.pose.position.y = waypoint.y
        goal.pose.pose.orientation = yaw_to_quat(waypoint.yaw)
        self._current_goal_handle = self._nav.send_goal_async(goal)
        self._state = "NAVIGATING"

    def pause(self):
        # Obstacle 時用：Nav2 goal 保留，twist_mux 擋住 cmd_vel
        # 優點：obstacle 清空後 twist_mux 放行，自動續行
        self._state = "PAUSED"

    def cancel(self):
        # Emergency 時用：立刻 cancel Nav2 goal
        if self._current_goal_handle:
            self._current_goal_handle.cancel_goal_async()
        self._state = "CANCELLED"

    def resume(self):
        # 從 PAUSED 回來，不用重發 goal
        self._state = "NAVIGATING"
```

**關鍵語義**：
- `obstacle → pause()`：goal 還在，twist_mux 阻擋輪子
- `emergency → cancel()`：goal 消失，要 reset 後重新 dispatch
- `pause ≠ cancel`

### 4.3 Map 載入策略（P0 預建圖）

**Phase 1（建圖，5/6 前）**：

```bash
ssh jetson-nano
ros2 launch slam_toolbox online_async_launch.py
# 手推 LiDAR 或 Go2 在家客廳 / 學校會議室繞一圈
ros2 service call /slam_toolbox/save_map \
  slam_toolbox/srv/SaveMap "{name: /home/jetson/maps/home_living_room}"
# 產出 home_living_room.pgm + home_living_room.yaml
```

**Phase 2（Demo 啟動載圖）**：

```bash
ros2 launch go2_robot_sdk robot.launch.py \
  slam:=false nav2:=true \
  map:=/home/jetson/maps/home_living_room.yaml
```

**Phase 3（Demo 前初始定位）**：

```bash
bash scripts/set_initial_pose.sh 0.0 0.0 0.0
# 或 RViz/Foxglove 點 "2D Pose Estimate"
```

**兩份地圖分離**：
- `/home/jetson/maps/home_living_room.yaml`（4/26 產出，反覆練習用）
- `/home/jetson/maps/school_meeting_room.yaml`（**必須 5/13 當天現場重建，不賭前一天地圖**）

### 4.4 Brain 如何觸發 patrol_route

**P0 支援三種觸發，全部 deterministic，不經 LLM**：

| 觸發 | 實作 | 使用時機 |
|------|------|---------|
| 語音關鍵字 | intent_rules 擴充「巡邏/去 B 點/走一下」→ 直接 dispatch | Demo 主持人說「PawAI，去那邊」|
| Studio 按鈕 | FastAPI endpoint → Brain policy call | 備援、驗收老師按 |
| 手勢（P1）| 特定手勢 → patrol_route | Stretch goal，P0 不做 |

**Policy Layer 判斷順序**：

```python
def decide_skill(intent, context):
    # 1. Safety override (deterministic)
    if safety.emergency_latched:
        return None

    # 2. Explicit navigation intent (deterministic keyword match)
    if intent.matches("patrol") and context.map_loaded:
        return patrol_route

    # 3. Other intents: LLM-driven skill selection
    return llm_select_skill(intent, available_skills)
```

### 4.5 Obstacle 發生時的 Timeline

```
t=0s    Executive dispatch patrol_route → Nav2 begins path planning
t=2s    Go2 走到一半，前方出現人
t=2.6s  lidar_obstacle_node 偵測 zone=danger（debounce 3 frames ≈ 600ms）
t=2.6s  Executive Safety Layer 收到 /event/obstacle_detected
t=2.6s  handler.pause() + publish zero Twist to /cmd_vel_obstacle
        （twist_mux obstacle input, priority 200；**非** emergency input）
t=2.6s  publish /tts "前方有障礙，請讓路"（safety_tts）
t=2.6s  /state/pawai_brain safety_flags.obstacle = true
t=3-8s  人還在，Nav2 持續算 path 但 cmd_vel 被 twist_mux 擋
t=8s    人走開 → lidar_obstacle_node zone=clear
t=11s   連續 3s clear → Executive handler.resume()
t=11s   twist_mux 放行 → Nav2 cmd_vel 通過 → Go2 繼續走
t=15s   到達 B → Nav2 goal SUCCEEDED → handler state=COMPLETED
t=15s   publish /tts "已到達目的地"（navigation status_tts）
```

**關鍵**：
- Nav2 goal 沒 cancel，不用重發
- Obstacle 期間 Nav2 仍在算 path（可能 replan，沒關係）
- twist_mux 是阻擋機制，不是取消機制

### 4.6 降級路徑

| 故障 | 降級行為 |
|------|---------|
| AMCL 漂移（pose std dev 過大）| Safety Layer abort patrol + navigation_status_tts「定位失準，停止巡邏」+ 回 IDLE |
| Nav2 timeout 30s | handler.cancel() + navigation_status_tts「巡邏超時，已停止」+ 回 IDLE |
| obstacle pause >15s | abort patrol（升級） |
| `/scan` heartbeat 斷 | preconditions 擋住，patrol 不啟動 |
| map 不存在 | preconditions 擋住 |
| twist_mux 無 nav2 input subscriber | preconditions 擋住 |
| goal accepted 但長時間沒 odom progress | Executive 每 5s 檢查 `/odom`，無變化超過 10s abort |
| Nav2 recovery behaviors 啟動 | **禁用（二選一）**：<br>(a) `behavior_server.behavior_plugins: []` 清空 recovery behaviors（主選，最簡）<br>(b) `bt_navigator` 改用不含 `<RecoveryNode>` 的自訂 BT XML（例 `navigate_to_pose_no_recovery.xml`）|

---

## 5. 硬規則（P0 不可違反）

| # | 規則 | 說明 |
|:-:|------|------|
| R1 | LLM 不進安全鏈 | obstacle / emergency / patrol 決策 100% deterministic |
| R2 | 所有 locomotion skill 不經 LLM | patrol/approach/move 決策全 deterministic |
| R3 | safety_tts + navigation status_tts 固定模板 | 永不經 LLM，共 6 句白名單 |
| R4 | emergency 是 latched state | 只能 service 解除，不是 bool topic |
| R5 | EMERGENCY_LATCHED 凍結所有恢復類請求 | nav2/teleop/patrol resume 全阻擋 |
| R6 | obstacle pause >15s 升級為 abort patrol | 不讓 Nav2 永遠掛著 |
| R7 | 5/11-5/12 freeze 期 | Bugfix only，禁止新功能 |
| R8 | Nav2 recovery behaviors 全關 | 避免 Demo 時 Go2 原地轉 |
| R9 | school_meeting_room 地圖必須 5/13 當天重建 | 不賭前一天地圖 |
| R10 | 5/1 emergency latch 必須通過 | 不通過不上 Go2 合體 |

---

## 6. 測試與驗收

### 6.1 測試金字塔

| 層級 | 內容 | 工具 | 在哪執行 |
|------|------|------|---------|
| Unit | state_machine emergency latch / obstacle auto-clear / patrol contract / 3s debounce | pytest | WSL + Jetson |
| Integration | `lidar_obstacle_node` + 真 `/scan` + Executive 狀態轉換 | pytest + launch_testing | Jetson（無 Go2）|
| Smoke | 一鍵啟動腳本（slam→nav2→lidar→executive→tts→hotkey）| `start_patrol_demo_tmux.sh` | Jetson（先無 Go2 再上 Go2）|
| Rehearsal | 完整 Demo 劇本走 5 次 | 人工 + stopwatch | 家中 → 學校 |

### 6.2 P0 Gate（硬 Go/No-Go）

```
Gate P0-A    RPLIDAR 桌面測試                      ✅ 2026-04-24
Gate P0-B    slam_toolbox 建圖 + save              ⏳ 4/26
Gate P0-C    載圖 + AMCL 收斂                      ⏳ 4/27
Gate P0-D    Nav2 單點到達（手持 LiDAR 模擬，無 Go2）⏳ 4/28
Gate P0-D.5  Nav2 cmd_vel → twist_mux → go2_driver ⏳ 4/29（隱性 gate，單獨驗）
Gate P0-E    obstacle → pause → resume              ⏳ 4/30
Gate P0-F    emergency latch + hotkey               ⏳ 5/1（硬截止）
Gate P0-G    safety_tts + navigation status_tts     ⏳ 5/2
Gate P0-H    Go2 上機合體（家中）                    ⏳ 5/4
Gate P0-I    家中 Demo 排練 5 次 4 成功              ⏳ 5/6（P0 cutoff）
Gate P0-J    學校場地重建地圖 + 現場排練              ⏳ 5/13 當天
```

### 6.3 P0-I KPI（5/6 家中排練）

| 成功次數 / 5 | 判定 | 後續 |
|:-----:|:----:|------|
| 4-5/5 | **GO** | 進 5/7 Stretch C |
| 3/5 | **YELLOW** | 不做 C，補 P0 |
| ≤2/5 | **NO-GO** | 降級 Demo（錄影 + 純反應式停）|

**單次成功**：
- 到達 B 誤差 <30cm
- 遇障反應 <1.5s
- 清障後 <4s 續行
- 無撞擊、無 emergency 觸發

### 6.4 5/13 學校現場排練

**3 次試跑**：

| 成功次數 / 3 | 判定 |
|:-----:|:----:|
| 2-3/3 | GO（5/19 驗收用 P0 完整劇本）|
| 1/3 | 降級（改純反應式守護 + 錄影展示）|
| 0/3 | 砍 Nav2，只做 lidar_obstacle_node 反應式停 |

---

## 7. 風險矩陣

| 風險 | 嚴重度 | 機率 | 緩解 |
|------|:----:|:---:|------|
| Jetson XL4015 斷電 | 🔴 | 高 | 5/1 前定穩定電源方案（barrel 5V/4A 或 PD 65W），永遠綁 Demo 搬 |
| AMCL 定位漂移 | 🔴 | 中 | 場地貼地標 + 每次 Demo 前 re-set pose + pose std dev 閾值 safety abort |
| WebRTC 靜默斷線 | 🟡 | 中 | Executive 監控 go2_driver heartbeat，2s 無動作 Studio 亮紅 |
| 5/13 學校場地非預期 | 🟡 | 中 | 當天提前 3 小時到場建圖、清場、跑 Gate P0-J |
| 組員零 PR 連續 2 週 | 🟡 | 已發生 | 4/25 會議 push，不交 PR 不能整合 main |
| Nav2 recovery behavior 誤觸發 | 🟡 | 中 | 已決策關閉 recovery |
| lidar_obstacle_node 誤偵測（自己身體）| 🟡 | 中 | LiDAR 架高於 Go2 身體 + `ignore_behind` + `min_obstacle_points=2` |
| safety_tts 跟 interaction_tts 撞車 | 🟢 | 低 | Executive 內部優先級 + `safety_flags.tts_playing` 協調 |
| goal accepted 但狗沒動 | 🟡 | 中 | Executive 每 5s 檢查 `/odom` 無變化 >10s → abort |

---

## 8. 時程 Gantt

```
        4/25  4/27  4/29  5/1   5/3   5/5   5/7   5/9   5/11  5/13  5/15  5/17  5/19
         │     │     │     │     │     │     │     │     │     │     │     │     │
建圖     ████─┤                                                                      (4/25-4/26)
AMCL         ░████─┤                                                                 (4/27)
Nav2 單點         ░░████─┤                                                           (4/28)
twist_mux 驗證         ░░████─┤                                                      (4/29, P0-D.5)
obstacle 整合             ░░████─┤                                                   (4/30)
emergency hotkey               ░░░░████─┤                                            (5/1 硬截止)
TTS 整合                           ░░░░████─┤                                        (5/2)
Go2 上機                              ░░░░████████─┤                                 (5/3-5/4)
家中排練                                         ░░░░████─┤                          (5/5-5/6) ← P0 cutoff
C stretch（條件）                                      ░░░░████████────┤             (5/7-5/10)
Freeze (bugfix only)                                                ░░░░████─┤       (5/11-5/12)
學校場地重建                                                               ░░░░████─┤ (5/13)
最終 rehearsal                                                                 ░░████(5/14-5/18)
驗收                                                                               ██ (5/19+)
```

**關鍵 Milestone**：
- **5/1**：emergency latch + hotkey 完成（R10 硬截止，不過不上 Go2）
- **5/4**：Go2 合體第一次試跑
- **5/6**：P0 cutoff（4/5 KPI）
- **5/11-5/12**：Freeze，bugfix only（R7）
- **5/13**：學校現場建圖 + Go/No-Go 會議

---

## 9. 實作清單

### 9.1 新增檔案（12 個）

| 路徑 | 用途 |
|------|------|
| `interaction_executive/interaction_executive/safety_layer.py` | Emergency FSM + Obstacle FSM |
| `interaction_executive/interaction_executive/skills/patrol_route_handler.py` | Nav2 action client wrapper |
| `interaction_executive/interaction_executive/safety_tts.py` | safety + navigation status 兩類固定模板（同模組）|
| `scripts/emergency_stop.py` | 鍵盤 hotkey（q=trigger, r=reset）|
| `scripts/start_patrol_demo_tmux.sh` | 一鍵啟動全 stack |
| `scripts/build_map.sh` | SLAM 建圖輔助 |
| `scripts/verify_twist_mux.sh` | Gate P0-D.5 驗證 |
| `pawai-studio/backend/routers/safety.py` | FastAPI `/safety/trigger` `/safety/reset` |
| `pawai-studio/frontend/components/EmergencyButton.tsx` | Studio 紅色大按鈕 |
| `interaction_executive/test/test_safety_state_machine.py` | Unit tests |
| `interaction_executive/test/test_patrol_route_handler.py` | Unit tests |
| `docs/mission/demo-script-p0.md` | Demo 劇本 cue sheet |

### 9.2 修改檔案（7 個）

| 路徑 | 改動 |
|------|------|
| `interaction_executive/interaction_executive/state_machine.py` | 加 `PATROL_NAVIGATING`, `PATROL_PAUSED`, `EMERGENCY_LATCHED` |
| `interaction_executive/interaction_executive/interaction_executive_node.py` | 組合 safety_layer + patrol_handler，加 service servers |
| `go2_robot_sdk/config/twist_mux.yaml` | emergency(255) / obstacle(200) / teleop(100) / nav2(10) |
| `go2_robot_sdk/config/nav2_params.yaml` | 改動以下實際參數路徑（原總稱 `goal_tolerance` / `recovery_behaviors` 不存在）：<br>• `controller_server.controller_frequency: 10.0`（原 20.0）<br>• `controller_server.FollowPath.max_vel_x: 0.2`<br>• `controller_server.general_goal_checker.xy_goal_tolerance: 0.30`（原 0.20）<br>• `controller_server.general_goal_checker.yaw_goal_tolerance: 0.30`（原 0.70）<br>• **Recovery 禁用（主選）**：`behavior_server.behavior_plugins: []`<br>• （備選）保留 behavior_server，改 bt_navigator BT XML 為自訂不含 RecoveryNode 版本 |
| `go2_robot_sdk/launch/robot.launch.py` | Nav2 `/cmd_vel` remap 為 `/cmd_vel_nav`；若採 recovery 禁用備選方案，須將 `default_nav_to_pose_bt_xml` 指向自訂 BT XML |
| `docs/mission/README.md` | P0 定義更新 |
| `docs/導航避障/README.md` | 狀態卡更新（D435 停用 → LiDAR 取代；Full SLAM 從永久關閉改為 P0 主線）|

### 9.3 地圖檔案（不存 git）

```
/home/jetson/maps/home_living_room.yaml   + .pgm   (4/26 產出)
/home/jetson/maps/school_meeting_room.yaml + .pgm  (5/13 當天產出)
```

### 9.4 依賴（Jetson）

```bash
sudo apt install ros-humble-slam-toolbox \
                 ros-humble-nav2-bringup \
                 ros-humble-navigation2 \
                 ros-humble-twist-mux \
                 ros-humble-nav2-map-server \
                 ros-humble-nav2-amcl
```

**不裝 `nav2-mppi-controller`**（ARM64 SIGILL，研究 agent 警告）。P0 用 DWB。

### 9.5 PR 切分（按 Gate 對齊）

| PR | Gate | 截止 | 負責 | 內容 |
|:--:|:----:|:----:|:----:|------|
| #1 | P0-B | 4/26 | 盧柏宇 | `build_map.sh` + SLAM 跑通 + 家中地圖 |
| #2 | P0-C + D | 4/28 | 盧柏宇 | `nav2_params.yaml` 調參 + AMCL + 單點到達 |
| #2.5 | **P0-D.5** | 4/29 | 盧柏宇 | `verify_twist_mux.sh` + `twist_mux.yaml` + mock cmd_vel 驗證 |
| #3 | P0-E | 5/1 | 盧柏宇 | `safety_layer.py` obstacle FSM + patrol pause/resume + tests |
| #4 | **P0-F** | **5/1 硬** | 盧柏宇 | `emergency_stop.py` + services + `/state/pawai_brain` + tests |
| #5 | P0-G | 5/2 | **盧恩** | `safety_tts.py` + 6 句固定模板 + interaction_tts 不撞車 |
| #6 | Studio | 5/3 | **雨桐** | `EmergencyButton.tsx` + backend `/safety/trigger` endpoint |
| #7 | P0-H + I | 5/4-5/6 | 盧柏宇 | `start_patrol_demo_tmux.sh` + Go2 上機 + 家中 KPI 4/5 |
| #8 | Stretch C | 5/7-5/10 | 盧柏宇（條件）| 單一靜態障礙繞行（P0-I 4/5 通過才啟動）|

### 9.6 團隊分工

| 成員 | 4/25 交付 | 5/1 交付 | 5/6 交付 |
|------|----------|----------|---------|
| 盧柏宇 | RPLIDAR 通（✅）+ PR #1 地圖 | PR #2-4 完成 | PR #7 家中排練 4/5 |
| 黃旭 | YOLO 本機 demo | 持續 | if stretch C 要用才介入 |
| 雨桐 | 前端 live camera | PR #6 Emergency 按鈕 | Studio 整合測試 |
| 盧恩 | Prompt 精簡 + 30 情境 | PR #5 safety_tts | Plan B 固定台詞備援 |
| 佩珍 | 姿勢後端串接 | 持續 | 不涉入導航 |

---

## 10. 觀測性（`/state/pawai_brain` 擴充）

Executive 發佈 @ 2Hz，P0 新增欄位：

```json
{
  "executive_state": "patrol_navigating | patrol_paused | idle | emergency",
  "active_skill": "patrol_route | null",
  "patrol_progress": {
    "current_waypoint": 0,
    "total_waypoints": 1,
    "distance_to_goal_m": 2.3,
    "eta_sec": null
  },
  "safety_flags": {
    "emergency_latched": false,
    "obstacle_active": false,
    "obstacle_direction_deg": null,
    "tts_playing": false,
    "tts_source": "interaction | safety | navigation_status | null"
  },
  "nav_stack_ready": true,
  "scan_heartbeat_ok": true,
  "amcl_converged": true
}
```

**Optional 欄位**（P0 可不穩定提供）：
- `patrol_progress.eta_sec`：若 Nav2 feedback 不穩定計算，設 `null`
- `patrol_progress.distance_to_goal_m`：同上

Studio 用這個畫「P0 儀表板」：狀態燈號 + patrol 進度條（optional）+ 緊急按鈕。驗收老師看這個。

---

## 11. Demo 當天操作 Checklist

```
T-3hr   抵達學校 / 清空雜物 / 架 Go2 + 穩定電源
T-2.5hr ssh jetson-nano / go2_ros_preflight.sh 跑過
T-2hr   slam_toolbox 建圖 / 手推 Go2 繞一圈 / save school_meeting_room
T-1.5hr kill slam / load nav2 with new map / set initial pose
T-1hr   啟動 full stack: start_patrol_demo_tmux.sh
        確認 tmux window: driver / scan / lidar_obstacle / nav2 / executive /
                         tts / hotkey / foxglove / studio / logger
T-45m   內部排練 3 次 → Go/No-Go 會議
T-15m   確認 emergency hotkey + Studio 按鈕雙備援都能觸發
T=0     Demo！
```

---

## 12. 與其他 Spec 的關係

**嵌入**：
- [`2026-04-11-pawai-home-interaction-design.md`](2026-04-11-pawai-home-interaction-design.md) §5 PawAI Brain 三層架構
  - 本 spec 擴充 Safety Layer（Emergency FSM + Obstacle FSM）
  - 本 spec 新增 `patrol_route` 至 PawAI Skills（§5.5）
  - 本 spec 擴充 `/state/pawai_brain.safety_flags`

**Supersedes（部分）**：
- [`docs/導航避障/README.md`](../../導航避障/README.md) §「架構決策（2026-04-01 最終判定）」
  - 原「Full SLAM 永久關閉」→ P0 主線
  - 原「Nav2 global planner 永久關閉」→ P0 主線
  - 判定依據：2026-04-24 RPLIDAR A2M12 實測 10.5Hz > 7Hz SLAM 門檻
- [`docs/archive/refactor/slam-nav2.md`](../../archive/refactor/slam-nav2.md) 的 Gate A-D 流程
  - Gate A-D 復活但改名 P0-A~J，加入 P0-D.5（twist_mux 驗證）

---

## 13. 開放問題

| 問題 | 處置 |
|------|------|
| Nav2 footprint 要怎麼設才符合 Go2 實際尺寸？ | Gate P0-D 時量測 + 調 `footprint_radius`，保守加 10cm |
| AMCL `max_particles: 1000` 在 4-6m 小場地夠嗎？ | Gate P0-C 實測 pose std dev，不夠再調 |
| Collision Monitor 要不要加？（research agent 建議） | P0 不加，lidar_obstacle_node 事件驅動已夠；5/6 有餘力再加 |
| D435 PointCloud2 要不要融合進 costmap？ | P0 不做（場地可清空避開桌腳），P1 再評估 |
| Studio 斷網時 Emergency 按鈕怎麼辦？ | 不保證 — 依賴鍵盤 hotkey 作 primary |

---

## Appendix: 名詞對照

| 術語 | 定義 |
|------|------|
| P0 | Phase 0，5/13 必須展示的主線 |
| P1 | Phase 1，Stretch goal，有條件做 |
| Latched state | 觸發後鎖死，需明確 reset 才解除 |
| Pause vs Cancel | Pause = goal 保留擋 cmd_vel；Cancel = goal 取消 |
| Patrol | 本 spec 特指 A→B 單點巡邏，非多 waypoint |
| safety_tts | 安全層固定模板 TTS，永不經 LLM |
| navigation status_tts | 導航狀態固定模板 TTS，永不經 LLM |
| interaction_tts | Expression Layer 的互動 TTS，可經 LLM |
| KPI 4/5 | 家中排練 5 次成功 4 次才算 GO |
