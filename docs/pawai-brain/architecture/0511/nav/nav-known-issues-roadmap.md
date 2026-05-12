# Navigation Known Issues And Roadmap

## P0 / 現場優先

### F7：goal accepted 但 `/cmd_vel_nav` 不出

5/12 night 現象：

```text
/nav/goto_relative accepted
nav lifecycle active
/capability/nav_ready=true
/capability/depth_clear=true
/state/nav/paused=false
/cmd_vel_nav 無 publisher
/cmd_vel = 0
10s no_progress_timeout
```

優先查：
- fresh restart 是否恢復。
- Nav2 controller_server 是否 active 且有 log。
- `/navigate_to_pose` 是否真的收到 goal。
- planner 是否找不到 path。
- AMCL pose 是否落在 lethal cell。
- 長時間 runtime 是否造成 DDS/stale state。

## 重要已知限制

### 1. `progressive` mode 仍依賴操作紀律

`progressive` 是現在 capability demo 主線，但它不是完整 release gate。它的安全前提是沒有 hot teleop。

必查：

```bash
ros2 topic info /cmd_vel_joy -v
```

### 2. `nav_ready` 還是 basic gate

目前 `capability_publisher_node` 只看：

```text
/amcl_pose exists
covariance_xy < threshold
pose age < max_pose_age_s
```

未完成：
- lifecycle active check。
- `map -> base_link` TF check。
- local/global costmap freshness。
- controller/planner readiness。

### 3. D435 depth gate 不會 stop active nav

`depth_safety_node` 只 publish `/capability/depth_clear`。它可阻止新技能，不會自動取消已在跑的 Nav2 goal。

要讓 D435 對正在跑的 nav 生效，需要其中一種：
- depth_safety 觸發 `/nav/pause`。
- D435 轉 `/scan_d435` 或 PointCloud2 進 Nav2 local costmap。
- 遷移到 Nav2 collision_monitor。

### 4. Executive NAV executor 未完成

Skill contract 裡有 NAV step，但 `interaction_executive_node.py` 對 NAV 回：

```text
nav_unimplemented_phase_a
```

若要語音/Brain 真的叫 Go2 走，要補：

```text
SkillStep ExecutorKind.NAV
  -> ActionClient /nav/goto_relative
  -> ActionClient /nav/goto_named
  -> ActionClient /nav/run_route
```

### 5. detour profile 不可直接用

已知問題：
- 仍可能用舊 `safety_only=true`，會 auto promote hold_brake。
- `danger=0.40m` 回到撞牆風險。
- `nav2_params_detour.yaml` 沒同步主線 5/12 tuning。
- D435 TF 還是臨時值。

### 6. 文件 drift

subagent/code audit 發現：
- root `CLAUDE.md` 仍有 `safety_only=true` 和舊 `0.6/1.0` 敘述。
- `docs/navigation/CLAUDE.md` 有些 `/nav/pause` 舊描述，和目前 goto action 訂 `/state/nav/paused` 不完全一致。
- `scripts/start_nav2_amcl_demo_tmux.sh` 還示範 `/goal_pose --once`，但 demo 主線應走 `/nav/goto_relative`。

處置：以 `docs/navigation/research/2026-05-11-nav-avoidance-deep-research.md`、`reactive_stop_node.py`、`start_nav_capability_demo_tmux.sh` 為準。

### 7. WorldState schema drift

程式碼目前有兩個欄位名稱不一致風險：

```text
reactive_stop_node publishes: reactive_stop_active
WorldState reads: obstacle_active

state_broadcaster publishes: reactive_stop_active / obstacle_zone / driver_alive ...
WorldState reads: unsafe
```

影響：
- `world.obstacle` 可能不會被 reactive danger 正確設成 true。
- `world.nav_safe` 可能長期維持 true，因為 `/state/nav/safety` 沒有 `unsafe` 欄位。

短期現場仍靠 `/capability/nav_ready`、`/capability/depth_clear`、`/state/nav/paused` 三個 gate；demo 後應修 schema 對齊並補測試。

## Demo 後 Roadmap

### B2.1 D435 fusion

把 D435 從 gate 變成 Nav2 obstacle source：

```text
D435 depth -> /scan_d435 or PointCloud2
Nav2 local_costmap observation_sources: scan + d435
```

參考：

```text
docs/navigation/specs/2026-05-03-d435-rplidar-fusion-detour.md
```

### B2.2 base_link projection

目前 threshold 是 LiDAR 視距。更正確做法：

```text
LaserScan point -> base_link frame
計算 Go2 機鼻到障礙物距離
threshold 用機鼻距離，不用 LiDAR 原始距離
```

這能避免 LiDAR mount 位置改了，安全距離又失真。

### B2.3 遷移 Nav2 collision_monitor

長期應用 Nav2 官方 `collision_monitor`：

```text
Stop / Slowdown / Approach polygons
基於 TTC 或 polygon distance
接在 controller output 下游
```

好處：
- 不必自製 mux priority 200 的 pseudo-controller。
- 更接近業界作法。
- D435 + RPLIDAR 多 source 更自然。

### B2.4 nav_ready 升級

加入：
- map_server/amcl/controller/planner/bt lifecycle。
- `map -> base_link` TF 查詢。
- scan freshness。
- costmap topic freshness。
- `/cmd_vel_nav` publisher sanity。

### B2.5 Executive NAV executor

補上：

```text
ExecutorKind.NAV goto_relative -> /nav/goto_relative
ExecutorKind.NAV goto_named    -> /nav/goto_named
ExecutorKind.NAV patrol        -> /nav/run_route
```

並確保：
- SafetyLayer gate 在 action 前。
- action cancel 和 TTS/skill interruption 有一致處理。
- failure message 能回給 Brain/Studio。

## 現場保守策略

如果明天只求穩：

1. 主展示 Brain/語音/感知。
2. Nav 只展示 `goto_relative 0.3m` 或 0.5m。
3. reactive stop 只展示 danger 停車，不展示 detour。
4. 每次 nav demo 前 fresh restart stack。
5. capability mode 嚴格確認 `/cmd_vel_joy` 無 publisher。
