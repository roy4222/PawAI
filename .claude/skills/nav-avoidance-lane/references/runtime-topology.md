# Runtime Topology — Nav Avoidance Lane

## Mode：mapping（建圖）

```
┌─────────────────────────────────────┐
│ tmux session: lidar-slam (5 windows)│
├─────────────────────────────────────┤
│ tf            base_link → laser     │
│ sllidar       /scan_rplidar 10Hz    │
│ carto         cartographer_node     │
│ carto_grid    /map (occupancy grid) │
│ foxglove      ws://0.0.0.0:8765     │
└─────────────────────────────────────┘

無 go2_driver — cartographer pure scan-matching，自己 own odom→base_link TF
（GO2_PUBLISH_ODOM_TF=0 設給 driver 用，但 mapping mode 根本不啟 driver）

建完圖存圖 3 步：
  1. ros2 service call /finish_trajectory ...
  2. ros2 service call /write_state ... filename: /home/jetson/maps/<name>.pbstream
  3. ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/<name>
```

底層腳本：`scripts/start_lidar_slam_tmux.sh`

## Mode：amcl（已建圖跑 goto）

```
┌─────────────────────────────────────┐
│ tmux session: nav2-amcl (5 windows) │
├─────────────────────────────────────┤
│ tf            base_link → laser     │
│ sllidar       /scan_rplidar 10Hz    │
│ driver        go2_driver_node       │
│               → /odom + odom→base_link TF │
│ nav2          map_server + amcl + planner + controller │
│ foxglove      設 /initialpose 給 AMCL │
└─────────────────────────────────────┘

⚠️ 與 mapping 不同：driver 必須發 odom→base_link TF（無 GO2_PUBLISH_ODOM_TF env override）

cmd_vel 流向：
  使用者 /goal_pose → bt_navigator → planner → controller → /cmd_vel → driver → Go2
```

底層腳本：`scripts/start_nav2_amcl_demo_tmux.sh`

## Mode：capability（完整能力層）

```
┌──────────────────────────────────────────────────────────┐
│ tmux session: nav-cap-demo (9 windows)                   │
├──────────────────────────────────────────────────────────┤
│ tf            base_link → laser                          │
│ sllidar       /scan_rplidar 10Hz                         │
│ d435          /camera/camera/aligned_depth_to_color/...  │
│ robot         driver + nav2 + twist_mux + amcl           │
│ reactive      reactive_stop_node (mode=progressive)      │
│               → /cmd_vel_obstacle (priority 200 in mux)   │
│               (legacy `safety_only=true` 自動 promote 成 │
│                mode=hold_brake，現在主線是 progressive)  │
│ navcap        nav_capability 6 nodes:                    │
│               nav_action_server (/nav/goto_relative)     │
│               route_runner_node (/nav/run_route)         │
│               log_pose_node     (/log_pose)              │
│               state_broadcaster (/state/nav/heartbeat)   │
│               capability_publisher (/capability/nav_ready)│
│               depth_safety_node  (/capability/depth_clear)│
│ pause-enable  /nav/{pause,resume,cancel} 服務            │
│ foxglove      ws://0.0.0.0:8765                          │
│ monitor       topic echo 集中觀察                        │
└──────────────────────────────────────────────────────────┘

twist_mux 優先級：
  /cmd_vel_emergency → priority 255 (emergency stop)
  /cmd_vel_obstacle  → priority 200 (reactive_stop)
  /cmd_vel_joy       → priority 100 (teleop)
  /cmd_vel_nav       → priority 10  (nav2 planner，最低)

reactive_stop 5/11 修正（撞牆 fix）：
  mode=progressive   → danger=0、slow/clear 沉默（不 shadow nav）
  danger_distance_m=1.1   ← 5/11 上機從 0.6m 上拉（機鼻 buffer）
  slow_distance_m=1.7
  front_offset_rad=π    ← LiDAR 反裝補償

⚠️ progressive 在 clear zone 沉默，0.5s 後 mux obstacle 200 過期 → 降級競爭。
   實際 mux priority：emergency 255 / **obstacle 200 / teleop 100 / nav 10**（nav 最低）。
   capability mode 安全前提是「**沒有 teleop hot publisher 在跑**」 — 這樣 obstacle
   沉默後就只剩 nav 10，nav 接管。
   有 teleop hot publisher → teleop 100 永遠贏 nav 10 → Go2 吃舊 teleop 速度（5/11 撞牆 root cause）。
```

底層腳本：`scripts/start_nav_capability_demo_tmux.sh`

env：
- `NAV_NAMED=$HOME/elder_and_dog/runtime/nav_capability/named_poses/main.json`
- `NAV_ROUTES=$HOME/elder_and_dog/runtime/nav_capability/routes`
- `MAP=$HOME/maps/home_living_room_v8.yaml`

## Mode：fallback（standalone reactive_stop）

```
┌──────────────────────────────────────┐
│ tmux session: reactive-stop (4 windows)│
├──────────────────────────────────────┤
│ tf            base_link → laser      │
│ sllidar       /scan_rplidar          │
│ driver        go2_driver_node        │
│ reactive      reactive_stop_node     │
│               (mode="" + safety_only=false, standalone) │
│               → /cmd_vel directly (3 段速：0/slow 0.45/normal 0.60) │
└──────────────────────────────────────┘

⚠️ 與 capability mode 互斥：
  fallback：reactive 標準模式 (mode="")，直發 /cmd_vel 3 段速 → shadow 任何 nav planner
  capability：reactive mode=progressive，走 /cmd_vel_obstacle (mux 200) → 跟 nav 漸進協調

fallback 用途：
  - nav2 場測前先驗證 LiDAR + driver + reactive 鏈路通
  - nav2 失敗時的純安全 fallback（demo 5/13 備援）
  - B5 burndown 階段的訊號層測試
```

底層腳本：`scripts/start_reactive_stop_tmux.sh`

## TF 樹（所有 mode 共通）

```
map (僅 amcl/capability)
 ↓
odom (driver 發，或 cartographer 發)
 ↓
base_link (Go2 機身中心)
 ↓ static
laser (RPLIDAR，前 17.5cm 上 18cm 反裝)
```

LiDAR 安裝座標（固定，static_transform_publisher）：
```
--x 0.175  --y 0  --z 0.18  --yaw 3.14159 --frame-id base_link --child-frame-id laser
```

## 切換流程

```
情境：剛建完圖，要驗 AMCL
─────────────────────────
nav-avoidance-lane cleanup --handoff none
→ 清 cartographer + sllidar
nav-avoidance-lane start amcl
→ 自動帶對的 MAP_YAML
```

```
情境：amcl demo 不順，先回 fallback 驗證鏈路
──────────────────────────────────────
nav-avoidance-lane cleanup --handoff none
nav-avoidance-lane start fallback
```

```
情境：nav 都測完，切回 brain 開發
────────────────────────────
nav-avoidance-lane cleanup --handoff brain
brain-studio-lane start e2e --studio
```
