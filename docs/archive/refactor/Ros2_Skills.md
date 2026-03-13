## ROS-MCP-Server -> ROS2 Skills 重構計畫（Go2 專用 Agent）(TO-BE)

> 目標：把目前偏通用的 `ros-mcp-server` 能力，拆成 Go2 專用、可測試、可安全落地的 Skills 架構，支援後續以 pi 打造專屬 agent。

---

## 1) 為什麼要從 MCP 轉 Skills

目前 `ros-mcp-server` 的優點是快接、通用（工具很多），但對我們這個專題有三個痛點：

1. 功能面太大，Go2 實際只用到一部分核心工具。
2. 安全邊界不夠硬（特別是移動/速度控制）。
3. 未來要做「Go2 專用 agent」，需要穩定的技能層 API，而不是通用 MCP 工具集合。

本計畫採用「分階段遷移」：先 Skill 化核心流程，再逐步淘汰 MCP 依賴。

---

## 2) 現況盤點（Repo 內證據 / AS-IS）

### 2.1 目前 MCP 工具面

`ros-mcp-server/server.py` 目前有 43 個 `@mcp.tool`，涵蓋 topic/service/action/參數/Go2 專用功能。

關鍵實際使用工具（依文件與 dev notes）：

- `find_object`
- `go2_perform_action`
- `call_service`（主要是 `/move_for_duration`、`/capture_snapshot`、`/stop_movement`）
- `check_gpu_server`
- `connect_to_robot`
- `get_topics`

參考：

- `ros-mcp-server/server.py`
- `docs/02-design/mcp_system_prompt.md`
- `docs/04-notes/dev_notes/2026-01-02-dev.md`

### 2.2 安全基礎其實已經有

`go2_robot_sdk/go2_robot_sdk/move_service.py` 已有很好的 safety primitive：

- 速度限制：`MAX_LINEAR=0.3`, `MAX_ANGULAR=0.5`
- 時間限制：`MAX_DURATION=10.0`
- 緊急停止：`/stop_movement`
- 任務結束一定發停止 `Twist()`

代表重構時應該把這些「硬限制」直接提升為 Skill Contract，而不是靠 prompt 自律。

### 2.3 現有流程依賴

`start_mcp.sh` 反映了現有啟動鏈：

- rosbridge
- go2_driver
- snapshot_service
- move_service

Skill 化後也必須保留這些依賴的可觀測與健康檢查能力。

---

## 3) 目標架構（Skills-First / TO-BE）

```
Go2 Agent (pi)
  -> Skill Router
      -> perception skills
      -> motion skills
      -> action skills
      -> system/safety skills
          -> ROS2 topics/services/actions
```

核心原則：

1. LLM/Agent 不直接發 raw `/cmd_vel`。
2. 所有移動都走安全封裝 skill（內部用 `/move_for_duration` + `/stop_movement`）。
3. Skill I/O 要 schema 化，回傳固定欄位，避免 prompt 漂移。
4. 先保留 MCP fallback，完成驗收再下線。

---

## 4) MCP Tool -> Skill 模組對照（第一版）

### 4.1 必搬（MVP）

| 現有 MCP Tool | 目標 Skill | 主要依賴 | 複雜度 |
|---|---|---|---|
| `find_object` | `skills/perception/find-object` | `/capture_snapshot` + GPU server | L |
| `check_gpu_server` | `skills/system/check-gpu` | HTTP health endpoint | S |
| `go2_perform_action` | `skills/action/perform-action` | Go2 action service/WebRTC | M |
| `list_go2_actions` | `skills/action/list-actions` | action mapping | S |
| `call_service`(move) | `skills/motion/safe-move` | `/move_for_duration` | M |
| `call_service`(stop) | `skills/motion/emergency-stop` | `/stop_movement` | S |
| `send_action_goal` | `skills/navigation/navigate-to` | Nav2 action | L |
| `get_action_status` | `skills/navigation/nav-status` | Nav2 action status | M |
| `cancel_action_goal` | `skills/navigation/cancel-nav` | Nav2 action cancel | M |
| `get_topics` + `ping_robot` | `skills/system/status` | rosbridge/ROS health | S |

### 4.2 延後搬（Phase 2+）

| 工具群組 | 建議 |
|---|---|
| `inspect_all_*`、`get_*_details` | 先不搬，保留開發/除錯用途 |
| `publish_for_durations`、`subscribe_for_duration` | 用高階 skill 取代，不暴露低階控制 |
| 參數全家桶 (`get/set/inspect parameter`) | 視需求再加，先做唯讀 status 即可 |

---

## 5) Skill 目錄與責任邊界

建議先建這個結構：

```
skills/
  perception/
    find-object/
  motion/
    safe-move/
    emergency-stop/
  navigation/
    navigate-to/
    nav-status/
    cancel-nav/
  action/
    perform-action/
    list-actions/
  system/
    status/
    check-gpu/
    connect/
  safety/
    gate/
```

每個 skill 都要有：

- `Use when`
- `Do NOT use for`
- 核心步驟（4~7 步）
- 失敗回退（必含 stop）
- 驗收測試句

---

## 6) 分階段遷移計畫

### Phase 0：契約定義（1 週）

目標：先定規則，不先寫太多程式。

- 定義 Skill I/O schema（JSON）
- 定義安全契約（速度/角速度/時長/急停）
- 定義執行門控（沒有明確執行意圖，只回 plan 不動真機）

交付物：

- `docs/refactor/skills-schema.md`（已建立：schema 草案）
- 本文件（`Ros2_Skills.md`）

### Phase 1：核心技能 MVP（2~3 週）

優先順序：

1. `safe-move`
2. `emergency-stop`
3. `find-object`
4. `perform-action`
5. `system/status`

驗收：

- 可完成「找椅子 -> 靠近 -> 打招呼」
- 全程不直接使用 raw `/cmd_vel`
- 任何失敗都能 `stop_movement`

### Phase 2：導航技能化（2 週）

- `navigate-to`
- `nav-status`
- `cancel-nav`

驗收：

- Nav2 action 可送出、查詢、取消
- 異常可恢復且不殘留運動命令

### Phase 3：MCP 降級為 fallback（1~2 週）

- Agent 預設走 skills runtime
- MCP 僅保留 debug/回退用途
- 對外只暴露 skill API，不直接暴露通用 MCP 工具

驗收：

- 常用流程 80% 以上不再依賴 MCP tool 直接呼叫

---

## 7) 安全設計（必守）

1. 禁止 Agent 直接發 `/cmd_vel`。
2. 所有移動必經 safety gate（clamp + max duration + stop fallback）。
3. `perform-action` 預設 `demo_mode=True`。
4. 任何一步失敗，第一動作是 `emergency-stop`。
5. 真機執行要有「明確執行意圖」關鍵詞（避免聊天誤觸發）。

---

## 8) 風險與對策

| 風險 | 說明 | 對策 |
|---|---|---|
| 一次全拆導致停擺 | 同時改太多層 | 分階段 + MCP fallback |
| action 邏輯不穩 | goal/status/cancel 邊界多 | 先做最小 action skills + 重點測試 |
| 感知鏈不穩 | snapshot/GPU 依賴網路或服務 | `check-gpu` 前置檢查 + local fallback |
| 安全邏輯被繞過 | 直接 tool 呼叫 | 技能層硬限制 + 禁止 raw cmd_vel |

---

## 9) 完成定義（Definition of Done）

符合以下條件才算完成「MCP -> Skills 第一階段」：

1. 核心 5 個 skills 可獨立執行（move/stop/find/action/status）。
2. Demo 主流程不需直接調 MCP low-level tools。
3. 安全限制可被測試證明（超限會 clamp，異常會 stop）。
4. 文檔中明確標註每個 skill 的 Use when / Do NOT use for。
5. 保留 MCP fallback，但預設路徑為 skills。

---

## 10) 參考來源（本 repo）

- `ros-mcp-server/server.py`
- `go2_robot_sdk/go2_robot_sdk/move_service.py`
- `go2_robot_sdk/go2_robot_sdk/snapshot_service.py`
- `start_mcp.sh`
- `docs/02-design/mcp_system_prompt.md`
- `docs/00-overview/專題目標.md`
- `docs/04-notes/dev_notes/2026-01-02-dev.md`
- `docs/01-guides/slam_nav/Jetson 8GB 快系統實作指南.md`

---

## 11) 外部參考與可借鏡模式（調研摘要）

以下是針對「MCP -> Skills」可直接借鏡的外部來源與建議：

1. MCP 架構：`https://modelcontextprotocol.io/docs/learn/architecture.md`
2. MCP Server Concepts：`https://modelcontextprotocol.io/docs/learn/server-concepts.md`
3. ros-mcp-server upstream：`https://github.com/robotmcp/ros-mcp-server`
4. Nav2 behavior tree：`https://github.com/ros-planning/navigation2/tree/main/nav2_behavior_tree`
5. Nav2 behaviors：`https://github.com/ros-planning/navigation2/tree/main/nav2_behaviors`
6. BehaviorTree.CPP：`https://github.com/BehaviorTree/BehaviorTree.CPP`
7. ROS2 Actions 概念：`https://docs.ros.org/en/humble/Concepts/Intermediate/About-Actions.html`
8. Nav2 regulated pure pursuit：`https://github.com/ros-planning/navigation2/tree/main/nav2_regulated_pure_pursuit_controller`

重點結論：

- 建議採 Hybrid 過渡：短期保留 MCP 做 discovery/debug，執行面逐步改成 ROS2 skills/actions。
- 導航與長任務優先 Action 化（支援 feedback、cancel、timeout）。
- 安全層放在技能執行路徑，而不是只放在 prompt 規則。
- 避免一次全量重寫，維持可回退路徑（MCP fallback）直到 skills 驗收完成。
