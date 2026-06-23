# Nav Capability And Brain Integration

## nav_capability 的角色

`nav_capability` 是 PawAI 對 Nav2 的高階封裝。它讓上層不要直接打 `/goal_pose`，而是透過 action/service 走有 gating、有 timeout、有 pause/resume 的 wrapper。

主要檔案：

```text
nav_capability/launch/nav_capability.launch.py
nav_capability/nav_capability/nav_action_server_node.py
nav_capability/nav_capability/route_runner_node.py
nav_capability/nav_capability/capability_publisher_node.py
nav_capability/nav_capability/state_broadcaster_node.py
go2_robot_sdk/go2_robot_sdk/depth_safety_node.py
```

## Nodes

| Node | 職責 |
|------|------|
| `nav_action_server_node` | `/nav/goto_relative`、`/nav/goto_named`，轉成 Nav2 `/navigate_to_pose` |
| `route_runner_node` | `/nav/run_route`，以及 `/nav/pause|resume|cancel` |
| `log_pose_node` | 寫 named pose / route JSON |
| `state_broadcaster_node` | 發 `/state/nav/heartbeat`、`/state/nav/status`、`/state/nav/safety` |
| `capability_publisher_node` | 發 `/capability/nav_ready` |
| `depth_safety_node` | 發 `/capability/depth_clear` |

## Actions / Services

| 介面 | 用途 |
|------|------|
| `/nav/goto_relative` | 以目前 AMCL pose 為基準，走相對距離 |
| `/nav/goto_named` | 到 named poses JSON 中的目標點 |
| `/nav/run_route` | 執行 route JSON waypoint sequence |
| `/nav/pause` | 發 `/state/nav/paused=true`，取消/暫停目前 route/goto |
| `/nav/resume` | 發 `/state/nav/paused=false`，讓 wrapper 重送 goal |
| `/nav/cancel` | 取消 route |

## `/nav/goto_relative` 流程

```text
/nav/goto_relative goal
  -> 檢查是否已有 active goto
  -> 等 /odom，確認 driver alive
  -> 檢查 AMCL covariance
  -> 由當前 map pose 算相對 goal
  -> 送 Nav2 /navigate_to_pose
  -> 監聽 /state/nav/paused
       paused=true  -> cancel Nav2 goal
       paused=false -> re-send same Nav2 goal
  -> 10s 無位移 >= 0.05m -> no_progress_timeout
```

AMCL gate：

```text
covariance_xy > 0.5       -> reject
0.3 < covariance_xy <= 0.5 and distance > 0.5m -> reject
covariance_xy <= 0.3      -> normal
```

這就是為什麼 5/12 F7 現象會顯示為：

```text
goal accepted
但 /cmd_vel_nav 沒 publisher
10s no_progress_timeout
Go2 完全不動
```

它表示 wrapper 可能送出 goal 了，但 Nav2 controller 沒產生 final cmd。

## Capability Gates

### `/capability/nav_ready`

來源：

```text
nav_capability/nav_capability/capability_publisher_node.py
```

目前 basic gate：

```text
/amcl_pose 曾出現
covariance_xy < covariance_threshold
pose age < max_pose_age_s
```

限制：
- 還沒檢查 map_server/amcl/controller lifecycle。
- 還沒檢查 `map -> base_link` TF。
- 還沒檢查 costmap freshness。
- 可能 false positive。

### `/capability/depth_clear`

來源：

```text
go2_robot_sdk/go2_robot_sdk/depth_safety_node.py
```

語意：

```text
true  = recent depth frame + ROI 內沒有近距離危險
false = 沒 frame / stale / compute error / ROI 有障礙
```

它是 fail-closed latched Bool。

限制：
- 它不是 controller。
- 不 publish `/cmd_vel`。
- 不 call `/nav/pause`。
- 不會讓已經跑起來的 Nav2 goal 自動停車。

## Executive WorldState

檔案：

```text
interaction_executive/interaction_executive/world_state.py
interaction_executive/interaction_executive/safety_layer.py
```

WorldState 訂閱：

```text
/capability/nav_ready
/capability/depth_clear
/state/nav/paused
/state/reactive_stop/status
/state/nav/safety
```

目前要注意兩個 schema drift：
- `reactive_stop_node` 發的是 `reactive_stop_active`，但 `WorldState._on_reactive_stop()` 讀的是 `obstacle_active`。這可能讓 `world.obstacle` 不會正確反映 reactive danger。
- `state_broadcaster_node` 的 `/state/nav/safety` 目前沒有 `unsafe` 欄位，但 `WorldState._on_nav_safety()` 讀 `unsafe` 來設定 `nav_safe`。

fail-closed default：

```python
nav_ready = False
depth_clear = False
nav_paused = False
```

SafetyLayer 規則：

```text
NAV step:
  require nav_ready == true
  require depth_clear == true
  block if nav_paused
  block if nav_safe false

MOTION step:
  block if nav_paused
  require depth_clear == true
  block if obstacle active
```

## Skill Contract 現況

檔案：

```text
interaction_executive/interaction_executive/skill_contract.py
```

已有 NAV skill contract：

| Skill | NAV step | Gate |
|-------|----------|------|
| `nav_demo_point` | `goto_relative distance=1.2` | `nav_ready`, `depth_clear`, confirmation |
| `approach_person` | `goto_face stop_distance=1.0` | `nav_ready`, `depth_clear`, `robot_stable` |
| `patrol` | `run_route` | `nav_ready`, `depth_clear` |
| `follow_user` | `follow_user` | high-risk |
| `follow_face` | `follow_face` | high-risk |
| `goto_named` | `goto_named` | high-risk |

但目前要注意：`interaction_executive_node.py` 的 NAV executor 還是：

```text
NAV executor is not implemented in Phase A
return nav_unimplemented_phase_a
```

所以目前「Brain/Executive 知道 NAV skill，也會做 safety gate」，但「真正把 NAV step 送到 `/nav/goto_relative`」這段還沒在 Executive 主線完成。實機 nav demo 主要靠：
- `nav_capability` action 手動/Studio 呼叫。
- tmux monitor window 直接送 action。
- 後續再補 Executive NAV executor。

## Brain 現況

Brain/persona 可以理解導航能力，但真正的安全仲裁在 Executive。對話層可以產生 `nav_demo_point` 這種 skill 意圖；若要讓語音直接觸發機器狗走，必須先完成：

```text
LLM/Brain skill -> Executive plan -> NAV executor -> /nav/goto_relative action
```

目前缺最後一段 NAV executor。

## 對明天開發的影響

1. 若你要「現場手動測 nav」，直接用 `nav_capability` action。
2. 若你要「語音說往前走，Go2 真的走」，要先補 Executive NAV executor。
3. 若你只要 Demo 說明「它有導航能力」，可以先展示 `/nav/goto_relative` action + Studio/Foxglove。
4. 所有 NAV/MOTION 都必須等 `nav_ready=true`、`depth_clear=true`。
