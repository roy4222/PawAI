# Nav Metrics — Storage Schema

> **文件類型**：SQLite DDL + ROS2 event schema + state machine 規則
> **日期**：2026-05-24
> **配套**：[`../CAPABILITY-LADDER.md`](../CAPABILITY-LADDER.md)、[`nav-kpi-matrix.md`](nav-kpi-matrix.md)
> **決策來源**：Q4 SQLite + fusion-ready / Q6 run 粒度 + DB 生命週期 / Q8 mission boundary

---

## 0. 檔案佈局

```text
runtime/nav_metrics/                              # gitignored
├── runs/
│   └── 2026-05-24/                               # 一日一資料夾
│       ├── session-abc123.db                     # 一 session 一檔
│       └── session-def456.db
├── latest_baseline_md_path.txt                   # 指向 docs/.../baselines/latest.md，給 CLI 抓
└── recorder.log

docs/navigation/metrics/                          # git-tracked
├── nav-kpi-matrix.md                             # KPI 定義
├── schema.md                                     # 本檔
└── baselines/
    ├── latest.md                                 # 每次 report 覆寫
    ├── accepted.md                               # 穩定基準，手動 promote
    └── history/
        ├── 2026-05-24-1500-baseline.md           # 重要場測 snapshot
        └── 2026-05-27-demo-baseline.md
```

**規則**：
- 每個 session 一份 `.db` 檔，避免單檔變巨大、跨 session 競爭寫入
- 跨 session 比較由 `nav_kpi_report.py` 用 `ATTACH DATABASE` 多 DB join 完成
- `.db` 永遠 gitignored；只有 markdown baseline 進 git
- `accepted.md` 變更走 PR review，promote 是明確指令不是隱含動作

---

## 1. SQLite Tables（DDL）

### 1.1 `session_meta`

凍結 session 開始那一刻的環境，事後重現用。

```sql
CREATE TABLE session_meta (
    session_id              TEXT PRIMARY KEY,        -- UUID v4
    started_at_ns           INTEGER NOT NULL,        -- ROS2 monotonic ns（與 events join 用）
    ended_at_ns             INTEGER,                 -- 同上，nullable until stop_session
    started_at_wall         REAL NOT NULL,           -- wall clock unix epoch（給人讀 + log 排序）
    ended_at_wall           REAL,                    -- 同上
    session_source          TEXT NOT NULL,           -- 'manual' | 'auto'
    operator                TEXT,                    -- 啟動者 (env USER)
    jetson_hostname         TEXT,
    ros_distro              TEXT,                    -- 'humble'

    -- Code provenance
    git_sha                 TEXT NOT NULL,
    git_branch              TEXT NOT NULL,
    dirty_flag              INTEGER NOT NULL,        -- 0/1
    recorder_version        TEXT NOT NULL,           -- nav_metrics_recorder_node 自己的 git_sha

    -- Runtime provenance (Q8.4 修正：必須是 runtime 路徑，不是 source)
    nav2_params_source_path TEXT,                    -- e.g. go2_robot_sdk/config/nav2_params.yaml
    nav2_params_runtime_path TEXT NOT NULL,          -- e.g. install/.../share/.../nav2_params.yaml
    nav2_params_hash        TEXT NOT NULL,           -- sha256 of file at runtime_path
    executive_yaml_hash     TEXT,                    -- interaction_executive/config/executive.yaml

    -- Test profile（重複欄位方便 query 不必 join runs）
    environment             TEXT NOT NULL,           -- enum (見 §2.1)
    sensor_profile          TEXT NOT NULL,           -- enum (見 §2.2)
    nav_profile             TEXT NOT NULL,           -- enum (見 §2.3)

    -- Physical calibration（Open Q1 修正：硬體常數寫 metadata，跨 session 比較才能 sanity check）
    go2_nose_offset_m       REAL NOT NULL DEFAULT 0.50,  -- LiDAR base_link → Go2 機鼻；5/13 後卡尺量完更新
    lidar_mount_yaw_rad     REAL NOT NULL DEFAULT 3.14159,  -- v8 mount yaw=π，配 front_offset_rad
    d435_mount_xyz          TEXT NOT NULL DEFAULT '0.30,0.00,0.20',  -- 5/2 hardcoded；5/13 後精校

    extra_notes             TEXT,                    -- 自由欄位

    CHECK (session_source IN ('manual', 'auto')),
    CHECK (dirty_flag IN (0, 1))
);
```

### 1.2 `runs`

一個 mission attempt = 一個 row（Q6.1 + Q8.1）。

```sql
CREATE TABLE runs (
    run_id              TEXT PRIMARY KEY,            -- UUID v4
    session_id          TEXT NOT NULL,
    goal_id             TEXT,                        -- action goal uuid (nullable for older flows)

    -- Test scenario (Q6 結構化欄位，給 SQL query 用)
    phase               INTEGER NOT NULL,            -- 6 | 7 | 8 | 12 ...
    goal_type           TEXT NOT NULL,               -- enum (見 §2.4)
    scenario_tag        TEXT,                        -- 自由欄位給人讀
    distance_m          REAL,                        -- 標稱距離 (對 goto_relative 是 goal 的 distance；其他 NULL)
    obstacle_type       TEXT,                        -- enum (見 §2.5)
    obstacle_distance_m REAL,                        -- 標稱障礙距離

    -- Lifecycle timestamps（全 ROS2 monotonic ns，跨表 join 統一單位）
    accepted_at_ns      INTEGER NOT NULL,            -- mission accepted
    started_at_ns       INTEGER,                     -- 第一筆 cmd_vel_nav 出現 (可能等於 accepted_at_ns)
    ended_at_ns         INTEGER,                     -- result event 收到
    elapsed_sec         REAL,                        -- (ended_at_ns - accepted_at_ns) / 1e9，計算欄位給 report 方便

    -- Outcome
    outcome             TEXT,                        -- enum (見 §2.6)，nullable until ended
    outcome_message     TEXT,                        -- nav_action_server 給的 message
    actual_distance_m   REAL,                        -- GotoRelative.Result.actual_distance
    final_pos_error_m   REAL,                        -- computed: EUCLID(goal_pose, result_pose) — 兩個 pose 都從 /event/nav/mission JSON 取，避免時間對齊誤差
    accepted_pose_x     REAL,                        -- 從 /event/nav/mission accepted event
    accepted_pose_y     REAL,
    accepted_pose_yaw   REAL,
    goal_pose_x         REAL,
    goal_pose_y         REAL,
    goal_pose_yaw       REAL,
    result_pose_x       REAL,                        -- 從 /event/nav/mission terminal event
    result_pose_y       REAL,
    result_pose_yaw     REAL,

    -- Pre/post AMCL snapshot
    amcl_cov_xy_start   REAL,
    amcl_cov_xy_end     REAL,

    FOREIGN KEY (session_id) REFERENCES session_meta(session_id),
    CHECK (outcome IS NULL OR outcome IN (
        'SUCCEEDED', 'ABORTED_NO_PROGRESS', 'ABORTED_PLAN_FAIL', 'ABORTED_SAFETY_GATE',
        'CANCELED_USER', 'CANCELED_PREEMPT', 'TIMEOUT_EXTERNAL', 'UNKNOWN'
    ))
);

CREATE INDEX idx_runs_session ON runs(session_id);
CREATE INDEX idx_runs_phase_scenario ON runs(phase, scenario_tag, goal_type);
```

### 1.3 `waypoint_events`

`run_route` 的 sub-event（Q8.1 — waypoint 不是新 run，是 event）。

```sql
CREATE TABLE waypoint_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    session_id          TEXT NOT NULL,
    waypoint_index      INTEGER NOT NULL,
    waypoint_name       TEXT,
    event_type          TEXT NOT NULL,               -- 'reached' | 'aborted' | 'skipped'
    timestamp_ns        INTEGER NOT NULL,            -- ROS2 monotonic ns（synthetic row 可填 mission ended_at_ns 作 placeholder）
    pose_x              REAL,                        -- nullable: synthetic row pose 未知時填 NULL
    pose_y              REAL,
    pose_yaw            REAL,
    reason              TEXT,                        -- aborted/skipped 的原因（e.g. depth_clear_false, planner_fail）
    notes               TEXT,
    synthetic           INTEGER NOT NULL DEFAULT 0,  -- Round 3 Finding 4：1 = 從 mission result 反推的不完整 row，0 = 真實 /event/nav/waypoint

    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    CHECK (event_type IN ('reached', 'aborted', 'skipped')),
    CHECK (synthetic IN (0, 1))
);

CREATE INDEX idx_waypoint_run ON waypoint_events(run_id);
```

**Fallback B 寫入規則（Round 3 Finding 4 修正）**：

當 route_runner 沒實作 A 案 `/event/nav/waypoint`，recorder 從 `/event/nav/mission` 的 result payload 反推 waypoint_events 時：
- 必填 `synthetic = 1`
- 必填 `reason`（從 result.abort_reason 抄）
- `timestamp_ns` 填 mission `ended_at_ns`（per-waypoint 真實時序未知，全部 row 共用同一 timestamp）
- `pose_x/y/yaw` 必填 NULL（不能猜）
- 只能反推 `aborted` event（已知 failed_waypoint_index）+ `reached` event（已知 waypoints_completed 的前 N 個 index）

**KPI 計算端規則**：
- `per_waypoint_abort` 允許用 `synthetic=1` row 算（abort 數量本身是準確的）
- 任何需要 per-waypoint 時序 / pose 的 KPI（例如未來的 waypoint_dwell_time）**必須過濾 synthetic=0**
- baseline markdown 若包含 synthetic=1 數據，在報告 header 標 `data_source: fallback_B`，promote 階段警告

### 1.4 `sensor_observations`

時序感測樣本，source-tagged（fusion-ready 核心表，Q5 設計）。

```sql
CREATE TABLE sensor_observations (
    obs_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    run_id              TEXT,                        -- nullable: 也記 idle 期間
    timestamp_ns        INTEGER NOT NULL,            -- ROS2 stamp，ns 精度
    source              TEXT NOT NULL,               -- 'lidar' | 'd435' | 'fused' | 'nav2_costmap'
    frame_id            TEXT,                        -- e.g. 'base_link', 'camera_depth_optical_frame'

    distance_min_m      REAL,                        -- LiDAR 前方 cone min, 或 D435 ROI min depth
    zone                TEXT,                        -- 'clear' | 'slow' | 'danger' | 'unknown'
    confidence          REAL,                        -- 0-1, 來源 specific
    valid               INTEGER NOT NULL,            -- 0/1: 該 sample 是否有效
    stale               INTEGER NOT NULL,            -- 0/1: 超過 stale_threshold (1s default)

    -- Round 3 Finding 2 — reactive_stop 衍生訊號持久化
    mode                TEXT,                        -- reactive_stop mode: hold_brake/progressive/released/disabled (only set for lidar source)
    brake_command_active INTEGER,                    -- 0/1: 該瞬間 brake 是否在輸出 0 給 mux（lidar source only）
                                                     -- 在 progressive 下 = zone IN (danger, emergency)
                                                     -- 在 hold_brake 下 = 永遠 1
                                                     -- 在 released/disabled 下 = 永遠 0

    raw_topic           TEXT,                        -- 來源 ROS2 topic 名稱
    raw_payload         TEXT,                        -- 原始 status JSON dump（future-proof：新欄位增加不必改 schema）

    FOREIGN KEY (session_id) REFERENCES session_meta(session_id),
    CHECK (source IN ('lidar', 'd435', 'fused', 'nav2_costmap')),
    CHECK (zone IS NULL OR zone IN ('clear', 'slow', 'danger', 'unknown')),
    CHECK (valid IN (0, 1)),
    CHECK (stale IN (0, 1)),
    CHECK (brake_command_active IS NULL OR brake_command_active IN (0, 1)),
    CHECK (mode IS NULL OR mode IN ('hold_brake', 'progressive', 'released', 'disabled'))
);

CREATE INDEX idx_obs_session_time ON sensor_observations(session_id, timestamp_ns);
CREATE INDEX idx_obs_source_zone ON sensor_observations(source, zone);
```

**Zone 來源映射（Finding 3 修正）**：`reactive_stop_node` 的 `/state/reactive_stop/status.zone` 實際會出現 `init` / `emergency` 兩種額外狀態，但 SQL 端維持 4-zone enum 保持簡潔。recorder 訂閱端強制映射：

| `/state/reactive_stop/status.zone` | → `sensor_observations.zone` |
|---|---|
| `init` | `unknown`（LiDAR 還沒收到第一筆 scan / node 啟動中）|
| `clear` | `clear` |
| `slow` | `slow` |
| `danger` | `danger` |
| `emergency` | `danger`（語意都是「不能前進」，emergency = danger + 已經煞死，sensor 觀測層不細分）|

需要區分 `emergency` 跟 `danger` 的場景請改看 `safety_events.event_type`（有 `emergency_engage` / `reactive_stop_engaged` 兩種獨立事件）。

**寫入頻率建議**：
- LiDAR @ 10 Hz（跟 reactive_stop_node 對齊）
- D435 @ 5 Hz（足夠捕捉 zone transitions，不至於塞爆 DB）
- 純空轉時段（無 run 進行 + zone=clear ≥ 5s）可降到 1 Hz

### 1.5 `safety_events`

reactive_stop pause/resume 配對（Q8.2）+ 其他離散安全訊號。

```sql
CREATE TABLE safety_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    run_id              TEXT,                        -- nullable: 不在 mission 期間也可能觸發
    timestamp_ns        INTEGER NOT NULL,

    source              TEXT NOT NULL,               -- 'reactive_stop' | 'depth_safety' | 'safety_layer' | 'emergency_stop'
    event_type          TEXT NOT NULL,               -- 見下方 CHECK
    reason              TEXT,                        -- short text; synthetic event 必填 reason='synthetic_session_end' 等
    distance_m          REAL,                        -- 觸發時的距離
    pair_event_id       INTEGER,                     -- engage 對 disengage 互相指 (nullable)
    command_topic       TEXT,                        -- e.g. /cmd_vel_obstacle, /cmd_vel_emergency
    synthetic           INTEGER NOT NULL DEFAULT 0,  -- Finding 4 修正：recorder 補的合成事件 (1) vs 真實 ROS event (0)

    FOREIGN KEY (session_id) REFERENCES session_meta(session_id),
    FOREIGN KEY (pair_event_id) REFERENCES safety_events(event_id),
    CHECK (source IN ('reactive_stop', 'depth_safety', 'safety_layer', 'emergency_stop')),
    CHECK (synthetic IN (0, 1)),
    CHECK (event_type IN (
        'reactive_stop_engaged', 'reactive_stop_disengaged',
        'depth_clear_false', 'depth_clear_true',
        'safety_layer_block', 'safety_layer_release',
        'emergency_engage', 'emergency_release'
    ))
);

CREATE INDEX idx_safety_session_run ON safety_events(session_id, run_id);
```

**配對規則**：
- `reactive_stop_engaged` 必跟下一個 `reactive_stop_disengaged` 配對 → 互相 fill `pair_event_id`
- session 結束時若有未配對的 `engaged` → recorder 寫一個合成 `disengaged` row：`synthetic=1` + `reason='synthetic_session_end'`，**event_type 保持乾淨 enum 值**（Finding 4 修正：不在 enum 裡塞 suffix）
- TTS / stop_margin / brake_false_positive_ratio 三個 KPI 全部從 paired event 算；計算時可選擇是否排除 `synthetic=1` 的配對（推薦：排除，因為合成 disengaged 的 timestamp 沒物理意義）

### 1.6 `kpi_snapshots`

每次 `nav_kpi_report.py` 跑完算出的 KPI 值（給 history 追蹤 + 後續 cross-session 比較）。

```sql
CREATE TABLE kpi_snapshots (
    snapshot_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    computed_at_wall    REAL NOT NULL,               -- wall clock，report 跑的時間（不是 runtime event）
    phase               INTEGER NOT NULL,
    scenario_tag        TEXT,
    kpi_name            TEXT NOT NULL,               -- e.g. 'SR', 'TTS', 'stop_margin'
    kpi_value           REAL,
    sample_count        INTEGER NOT NULL,
    threshold_status    TEXT NOT NULL,               -- 'PASS' | 'WARN' | 'FAIL' | 'INSUFFICIENT_DATA'
    baseline_value      REAL,                        -- 從 accepted.md parse
    regression_status   TEXT NOT NULL,               -- 'OK' | 'REGRESSED' | 'UNKNOWN'

    FOREIGN KEY (session_id) REFERENCES session_meta(session_id),
    CHECK (threshold_status IN ('PASS', 'WARN', 'FAIL', 'INSUFFICIENT_DATA')),
    CHECK (regression_status IN ('OK', 'REGRESSED', 'UNKNOWN'))
);
```

### 1.7 `metrics_integrity_log`

recorder 自身健康度（Q8.3）— `severity=FAIL` 條目存在 = baseline 作廢；INFO/WARN 純觀測，不擋 promote。

```sql
CREATE TABLE metrics_integrity_log (
    log_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp_ns        INTEGER NOT NULL,            -- ROS2 monotonic ns
    severity            TEXT NOT NULL,               -- 'INFO' | 'WARN' | 'FAIL'
    code                TEXT NOT NULL,               -- e.g. 'TIMEOUT_EXTERNAL', 'EVENT_GAP', 'CLOCK_JUMP'
    detail              TEXT,
    CHECK (severity IN ('INFO', 'WARN', 'FAIL'))
);
```

**規則（Finding 7 修正：統一說法）**：只有 `severity=FAIL` 的條目會讓 baseline 作廢；`INFO` 和 `WARN` 純粹是觀測紀錄，不影響 promote。`promote` 拒絕條件以 §6.3 為準。

---

## 2. Enum 值字典

### 2.1 environment

```text
home    家裡測試（沙發 / 客廳 / 走廊地圖）
school  學校場地
lab     開發機 / 內部驗證
demo    正式展示場景
unknown 未標記 (auto session 預設)
```

### 2.2 sensor_profile

```text
lidar_only                    只用 RPLIDAR
lidar_d435_gate               LiDAR 主線 + D435 當 gate（Q5 主線 E1）
lidar_d435_costmap_shadow     LiDAR 主線 + D435 進 local_costmap shadow A/B（Q5 實驗線 E3-A）
lidar_d435_costmap_main       D435 進 main costmap（**禁止用於 demo，僅實驗**）
```

### 2.3 nav_profile

```text
main          go2_robot_sdk/config/nav2_params.yaml（5/12 tuning 後）
detour        nav2_params_detour.yaml（5/3 窄場景）
experimental  其他實驗 yaml
```

### 2.4 goal_type

```text
goto_relative      /nav/goto_relative
goto_named         /nav/goto_named
run_route          /nav/run_route (route 整段)
obstacle_stop_test 故意製造障礙測 Phase 8
manual_drive       手動推（非 nav，但 recorder 可以記做 baseline reference）
```

### 2.5 obstacle_type

```text
none      無障礙
box       測試箱
person    人
chair     椅子
pet       寵物 (Phase 9 future)
unknown   未分類
```

### 2.6 outcome（Q8.3）

```text
SUCCEEDED              action result success=true
ABORTED_NO_PROGRESS    F7 — 10s no_progress_timeout
ABORTED_PLAN_FAIL      planner / controller 失敗
ABORTED_SAFETY_GATE    SafetyLayer 攔截（nav_ready / depth_clear 不過）
CANCELED_USER          手動 /nav/cancel
CANCELED_PREEMPT       被新 goal preempt
TIMEOUT_EXTERNAL       recorder watchdog（mission > N min 沒收到 result）
UNKNOWN                event stream 斷裂、recorder restart 等
```

`SR` 分母排除 `TIMEOUT_EXTERNAL` 和 `UNKNOWN`。出現任一條就標 `metrics_integrity: FAIL`。

---

## 3. ROS2 Event Schema：`/event/nav/mission`

Q8.2 修正：不偷看 `_action/status`；由 `nav_action_server_node` 和 `route_runner_node` 主動發 JSON。

**Topic**：`/event/nav/mission`
**Message type**：`std_msgs/msg/String`（JSON-encoded，沿用 PawAI event 慣例）
**Publishers**：`nav_action_server_node`、`route_runner_node`
**Subscriber**：`nav_metrics_recorder_node`
**QoS**：RELIABLE + KEEP_LAST(20)

### 3.1 JSON Schema

```jsonc
{
  // Required
  "schema_version": "1",
  "run_id": "uuid-v4",                       // **publisher 產生（nav_action_server / route_runner），recorder 只接受**（Finding 1 修正：std_msgs/String 是單向 topic，無法做 handshake 回傳）
  "goal_id": "ros2-action-goal-uuid",
  "action": "goto_relative" | "goto_named" | "run_route",
  "event_type": "accepted" | "started" | "succeeded" | "aborted" | "canceled",

  // Timing — 統一 ROS2 monotonic ns（Finding 2 修正）
  "stamp_ns": 1716537600123456789,

  // Common payload
  "scenario_tag": "goto_0.5m_box_front_1.0m",     // nullable
  "phase": 6 | 7 | 8,                              // recorder 補

  // Action-specific
  "goal": {                                        // 對 accepted event 必填
    "distance_m": 0.5,
    "yaw_offset": 0.0,
    "max_speed": 0.5,
    "named_pose": "couch_center",                  // goto_named 用
    "route_id": "demo_loop"                        // run_route 用
  },

  // Pose 三段（Open Q2 修正：避免 recorder 在 result time 自己抓 /amcl_pose 產生時間對齊誤差）
  // 都用 map frame，由 publisher (nav_action_server / route_runner) 在對應 event 時間點抓好填入
  "accepted_pose": { "x": 1.10, "y": 0.40, "yaw": 1.50 },   // accepted event 必填：mission accept 那一刻 AMCL pose
  "goal_pose":     { "x": 1.55, "y": 0.42, "yaw": 1.57 },   // accepted event 必填：goal 解算成 map frame 後的目標 pose（goto_relative 就是 accepted_pose + 距離向量；goto_named 就是 named_pose 表）
  "result_pose":   { "x": 1.53, "y": 0.45, "yaw": 1.58 },   // terminal event 必填：result 收到那一刻 AMCL pose

  "result": {                                      // 對 succeeded/aborted/canceled 必填
    "success": true | false,
    "actual_distance_m": 0.481,
    "message": "Reached the goal!" | "F7 no_progress_timeout" | "...",
    "outcome_code": "SUCCEEDED" | "...",           // 對齊 outcome enum

    // run_route 專用（Finding 3 fallback B 案資料源）
    "waypoints_completed":   3,                    // 已通過的 waypoint 數
    "waypoints_total":       5,
    "failed_waypoint_index": 4,                    // nullable
    "abort_reason":          "depth_clear_false_at_wp4"  // nullable
  },

  // Optional snapshot
  "amcl_cov_xy": 0.32
}
```

### 3.2 Mission Lifecycle State Machine

```
nav_action_server_node 或 route_runner_node 內部：

[idle] ──goal_accept──> [accepted]──┐
                                    │
                          first cmd_vel
                                    ↓
                                [started]──> {result} ──> [terminal]
                                    │
                                cancel/abort
                                    └──────────────────────┘
                                                            │
                                                       publish event_type:
                                                         succeeded / aborted / canceled

每個 transition publish 一個 /event/nav/mission JSON。

recorder 收到 'accepted' → 新增 runs row, fill accepted_at + accepted_pose + goal_pose
recorder 收到 'started'  → fill started_at
recorder 收到 terminal   → fill ended_at, outcome, outcome_message, actual_distance_m, result_pose
                          → 從 result_pose vs goal_pose 算 final_pos_error_m
                          → run_route 額外處理 waypoint_events：
                             • A 案（canonical）：訂 /event/nav/waypoint 每筆寫 synthetic=0 完整 row（含 pose + 真實 timestamp）
                             • B 案（fallback）：從 result.waypoints_* 反推 synthetic=1 row（pose=NULL、timestamp 共用 ended_at_ns、僅供 per_waypoint_abort 計數，不可用於 per-waypoint timing/pose KPI）
```

**特殊處理**：
- 若 `accepted` 後 5 分鐘沒收到 terminal event → recorder 主動寫 `outcome=TIMEOUT_EXTERNAL` + `metrics_integrity_log(severity=FAIL, code=TIMEOUT_EXTERNAL)`
- `RunRoute` 內 waypoint event 走 **`/event/nav/waypoint`**（canonical, A 案；含 `event_type: reached | aborted | skipped` + waypoint_index + reason + pose）→ 寫 `waypoint_events` table，不切 run。舊 `/event/nav/waypoint_reached`（只發 reached）標 legacy，過渡期 recorder 可同時訂兩條相容處理，但新 code 不該繼續用
- preempt（舊 goal canceled + 新 accepted 連發 < 0.5s）→ 舊 run outcome = `CANCELED_PREEMPT`

---

## 4. Recorder Service Interface

`nav_metrics_recorder_node` 對外提供三個 service（Q6.2 hybrid mode）：

| Service | Type | 用途 |
|---|---|---|
| `/nav_metrics/start_session` | 自訂 `StartSession.srv` | 開新 session_meta row，request 帶 environment / sensor_profile / nav_profile / scenario_tag / extra_notes |
| `/nav_metrics/stop_session` | `std_srvs/Trigger` | 收尾當前 session，fill `ended_at`、跑 KPI snapshot |
| `/nav_metrics/set_scenario` | 自訂 `SetScenario.srv` | mid-session 改 scenario_tag（影響後續 runs row） |

**Hybrid 行為（Q6.2 (d)）**：
- 若 recorder 啟動 5s 後仍無 `start_session` 呼叫且收到第一個 `/event/nav/mission` → auto-create session，`session_source = auto`、`environment = unknown`
- `auto` session 不能 promote 進 accepted.md
- 手動 `start_session` 永遠優先於 auto（auto session 會在 manual start 時被 stop）

---

## 5. nav2_params_hash 計算

Q8.4 修正 — 必須 hash **runtime** 路徑那份檔（Jetson 的 install/.../share/ 跟 source 不同步是常態）。

```python
def compute_runtime_yaml_hash() -> str:
    # 1. 找 runtime path
    candidates = [
        Path.home() / "elder_and_dog/install/go2_robot_sdk/share/go2_robot_sdk/config/nav2_params.yaml",
        Path("/opt/ros") / os.environ.get("ROS_DISTRO", "humble") / "share/go2_robot_sdk/config/nav2_params.yaml",
        Path(repo_root()) / "go2_robot_sdk/config/nav2_params.yaml",   # WSL fallback
    ]
    for p in candidates:
        if p.exists():
            data = p.read_bytes()
            return f"sha256:{hashlib.sha256(data).hexdigest()[:12]}:{p}"
    return "sha256:MISSING"
```

回傳值帶 path 後綴，事後看 baseline 能直接知道用的是 install 還是 source 那份。

---

## 6. 寫入 / 讀取契約

### 6.1 寫入（recorder 端）

- 所有 INSERT 在 SQLite WAL mode、`synchronous=NORMAL`（容忍 OS crash 損失 ≤ 1s 資料，換寫入速度）
- 每 60s 或 session_meta.ended_at 寫入時 `PRAGMA wal_checkpoint(TRUNCATE)`
- 所有 timestamp 用 ROS2 `Time.now().nanoseconds`，避免 wall clock skew；session_meta.started_at 例外用 wall clock 方便人讀

### 6.2 讀取（report 端）

- `nav_kpi_report.py` 接受 `--session <id>` 或 `--latest` 或 `--since <YYYY-MM-DD>`
- 跨 session 比較用 `ATTACH DATABASE 'session-xxx.db' AS s1`
- 每次 report 跑完寫一份 `kpi_snapshots` row（持久化）+ 覆寫 `baselines/latest.md`

### 6.3 Promote 時的 cross-session sanity check（Open Q1 配套）

`pawai nav metrics promote` 在覆寫 `accepted.md` 前必須擋下以下情況：

| 情況 | 行為 |
|---|---|
| `metrics_integrity_log.severity = FAIL` 任一條目 | 拒絕 promote |
| latest 與 accepted 的 `go2_nose_offset_m` 不一致 | 拒絕，提示「物理校正改變後 stop_margin 不可直接比，需重新建立 baseline」 |
| latest 與 accepted 的 `lidar_mount_yaw_rad` 不一致 | 同上 |
| latest 與 accepted 的 `nav_profile` 不一致 | 警告但允許（profile 切換是有意的） |
| latest 與 accepted 的 `nav2_params_hash` 不一致 | 警告 + diff 給人看，要求 `--force-yaml-change` flag |
| latest 任一核心 KPI = FAIL | 拒絕（FAIL 不能當新 baseline）|

理由：Open Q1 修正 — 物理常數變化會讓「數字看似一樣但意義變了」，靜默 promote 會造成 baseline 污染。

---

## 變更紀錄

- 2026-05-24 first draft（Q4 / Q6 / Q8 — fusion-ready / hybrid session / mission lifecycle）
