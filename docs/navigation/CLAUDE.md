# 導航避障 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。`.claude/rules/` 中的對應檔案只是薄橋接。

## Phase A capability gates (5/2 加入,Executive 已接;5/3 調 threshold)

- **`/capability/depth_clear`** (Bool, latched, fail-closed):D435 ROI 前方 1m 內 < 0.4m 障礙 → false。**沒收到 frame / stale > 1s / compute error → false**(由 `depth_safety_node` 保證)
- **`/capability/nav_ready`** (Bool, latched, **v0.5 basic**):AMCL 收到 pose + covariance < threshold(`nav_capability.launch.py` default **5/3 改 0.45**, demo tmux script 也改 0.45,對齊 nav_action_server YELLOW upper 0.50)。**day 2 升級** = lifecycle service + TF `map → base_link` 可查 + costmap healthy
- **`/state/nav/paused`** (Bool, latched):全域 pause 狀態,由 `route_runner` 的 `/nav/pause`/`/nav/resume` service **無條件** publish。`nav_action_server` 訂這個做 cancel + re-send(BUG #2 5/2 已修,commit `a3bdd2e`)
- **D435 是 safety gate,不接進 Nav2 local costmap**(明確不做)— 障礙偵測由 reactive_stop_node + LiDAR + D435 ROI 三條獨立鏈路覆蓋
- **Foxglove 看 D435 點雲** 需要靜態 TF `base_link → camera_depth_optical_frame`(Go2 URDF 沒含 D435 mount;5/2 用 `static_transform_publisher --x 0.30 --y 0 --z 0.20` 暫時頂著,正式 mount 校正排到 5/13 後)

## 不能做

- **不要對移動中的 Go2 送 `Damp` (api_id=1001)**（5/2 摔倒事件）— Damp 是馬達軟鬆弛、僅限 idle 站穩後使用。移動中的 emergency stop 必須用 `emergency_stop.py engage`（mux pri 255 + lock）+ `StopMove` (api_id=1003, **topic 必填 `rt/api/sport/request`**)。詳 [`docs/navigation/plans/2026-05-02-dynamic-obstacle-demo.md`](plans/2026-05-02-dynamic-obstacle-demo.md)
- **不要 hand-write 不完整 `WebRtcReq`**（5/2 教訓）— `api_id=1003` 在 `rt/api/sport/request` 是 StopMove，在 `rt/api/obstacles_avoid/request` 是 obstacle Move（不是停車！）。publish 時 5 個欄位都要寫
- 不要修改 D435 camera launch 參數（那是 face_perception 的領域）
- 不要動 `nav2_params.yaml` 的 footprint（60×30cm 短於 Go2 真實 70×31cm，但 4/26 實機驗證仍 work；正式校正排到 5/13 demo 後）
- 不要在 `start_nav2_amcl_demo_tmux.sh` / `start_reactive_stop_tmux.sh` 同時跑（cmd_vel 衝突）— 互斥使用
- **不要再靠 Foxglove map/scan 視覺猜 yaw**（4/29 試 4 次失敗）— 用 `scan_health_check.py` 物理錨定（Go2 正前方 0.8m 放物體，看 angle bin）
- **不要每改 yaw 就重建一張 map**（4/29 浪費 4 張）— cartographer 會用任何 yaw 建出內部一致的 map，視覺差異不能當判讀依據
- **不要用「物體放置法」做物理錨定**（5/1 v7 偽陽性教訓）— 用戶識別 Go2 鼻尖方向可能錯。用「**用戶站位置法**」：用戶站在 Go2 物理頭前 0.5m，看 lidar 哪個 angle bin 偵測到、無歧義
- **不要假設 v8 mount yaw=π 只要改 TF scripts** — `reactive_stop_node` 內部 `compute_front_min_distance` 也假設 laser 0° = Go2 前方、必須一起改（5/1 Phase 7.2 Go2 撞紙箱事件、commit `e3270da` 修）
- **不要 rsync 帶 `--delete` + trailing slash 多 source 到 Jetson**（5/3 災難）— `rsync nav_capability/ go2_robot_sdk/ scripts/ jetson:dest/` 會 flatten contents 合併到 dest + delete source 沒有的檔案 → `scripts/` 內檔案被刪光、頂層出現孤兒目錄。正確：**source 不帶 trailing slash + 不 `--delete`**
- **不要在 Jetson 跑 `colcon build`** — setuptools `--editable`/`--uninstall` 不相容，會 fail。改靠 editable install + source rsync（python source 改動立刻生效，launch.py / yaml 要手動 cp 到 `install/.../share/`）
- **不要假設 `~/.local/lib/python3.10/site-packages/{nav_capability,go2_robot_sdk}-*.dist-info/entry_points.txt` 永遠完整**（5/3 教訓）— `colcon build` fail 時新增的 console_scripts 不會進 metadata，`load_entry_point` 拿 StopIteration → launch 起不來。手動 echo append 那 .txt 即可（`cp .bak.<ts>` 自動備份）

### 2026-05-04 新增 3 條(Demo Scope Freeze)

詳見 [`plans/2026-05-04-demo-scope-freeze.md`](plans/2026-05-04-demo-scope-freeze.md)。

- **不要直接 `ros2 topic pub /goal_pose`** — bt_navigator subscriber QoS 是 BEST_EFFORT,直接 pub 會 race。所有 demo goal 走 `nav_action_server`(`/nav/goto_relative` / `/nav/goto_named` / `/nav/run_route`)。手動測試的 `scripts/send_relative_goal.py` Phase 2 PR 7 會改寫成走 action,在那之前**僅供開發機 debug 用,不進 demo 流程**
- **不要在 demo 週(5/4–5/12)動硬體** — LiDAR mount / D435 angle / Jetson 供電 / Go2 背包線材 / 場地佈置全部凍結。精校排 5/13 後
- **不要再無限加 `nav_ready` check** — 升級**只做** lifecycle(map_server/amcl)+ TF(`map → base_link`)+ `/scan` freshness 三項。其他(planner / controller / bt_navigator / costmap stale / driver process)延後。理由:check 越多 false negative 越多,demo 當天反而被自己擋死

## 5/3 demo 教訓（K-STATIC-AVOID-CONTROLLED PASS / detour FAIL）

- **AMCL covariance 卡 0.30-0.42 plateau** 是常態:沒動就不收斂,初始 initialpose 後 60s 進 GREEN 偶爾,多數時候卡 YELLOW。建議:重設 initialpose + 等 60-90s,或物理推 Go2 0.3m 配合
- **Forward warmup 是雙刃刀** — 收斂 cov 但破壞場景(推 Go2 進 box 0.3-0.5m)。用 0.3m 不要 0.5m,且每次 warmup 後重量 front
- **Box 距離 sweet spot:1.0-1.5m**(對 1.5m demo goal):太近(< 1.0m)DWB「No valid trajectory」+ BT spin recovery collision、太遠(> 1.7m)reactive 不觸發
- **xy_goal_tolerance 5/3 改 0.10**(從 0.15) — 但仍會出現「Go2 走 0.4m 撞 box stop → tolerance 內判 reached」情況,demo 變成兩個 0.5m goal 接龍最穩
- **DWB 不會自動繞行** — 當前 yaml 是「保守安全停」profile,要 detour 必須改 `robot.launch.py:77` 加 `nav_params_file` arg + 寫 `nav2_params_detour.yaml`(PathAlign 12→10、forward_point_distance 0.2→0.5、GoalAlign 10→6、BaseObstacle 0.80→0.40、inflation 0.30→0.35)+ 寬場景

## 改之前先看

### Nav2 主線
- `go2_robot_sdk/config/nav2_params.yaml`（AMCL + DWB + costmap，v3.7 已驗證）
- `scripts/start_nav2_amcl_demo_tmux.sh`（5-window 啟動）
- `scripts/send_relative_goal.py`（讀 amcl_pose 算前方相對 goal）

### Reactive fallback
- `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`（≈ 130 行）
- `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py`（純 Python helpers）
- `scripts/start_reactive_stop_tmux.sh`（4-window）

### 舊 D435 / vision_perception 模組
- `vision_perception/vision_perception/obstacle_detector.py`（D435 depth，4/3 停用）
- `vision_perception/vision_perception/lidar_obstacle_detector.py`（LaserScan 純邏輯，可參考）

## 常見陷阱

### Nav2 / AMCL
- **`/goal_pose` QoS 是 BEST_EFFORT**（bt_navigator 訂閱端）— publisher 必須匹配，否則訊息直接丟（4/26 踩過）。`ros2 topic pub --once` 預設 RELIABLE 會 race，要加 `--qos-reliability best_effort`
- **不要連發太密集的 goal**：5 個 goal 1.5s 內連發會讓 controller preempt 太頻繁，`Reached the goal!` 在距離 0.5m 就誤觸發。`send_relative_goal.py` 預設 `--repeat 1` 已修
- **昨天 lethal 是暫態**（4/26 判定）：costmap 髒污 / particle filter 漂移，不是位置固有 / 不是 inflation 過大 / 不是 footprint padding。不要為了「修 lethal」盲改 inflation_radius
- **首次 plan 失敗 → BT 自動 clear costmap → 重 plan 通常成功**：這是 v3.7 的設計行為，但 spin recovery 對 quadruped 無效（Go2 MIN_X=0.50 m/s 下無法原地轉），所以 plan 連續失敗會卡死
- **AMCL covariance 0.22 偏大但仍可規劃**：理想 < 0.05 但需 Go2 移動才會收斂；實機驗證 0.22 仍能成功 plan
- **Foxglove `/initialpose` 設定後**：等 AMCL 發 `map → odom` TF（log 看 `Setting pose: ...`）才能發 goal
- **5 個 nav2 lifecycle 不一定要全 active**：amcl + map_server active 即 Go2 可動；controller_server / planner_server / bt_navigator / behavior_server 第二次 `lifecycle get` 可能 hang（service competing），實際都活著

### Reactive stop
- **/cmd_vel QoS 是 RELIABLE**（go2_driver_node 訂閱端）— reactive_stop_node 已用 RELIABLE
- **/scan_rplidar QoS 是 BEST_EFFORT**（sllidar publisher）— reactive_stop_node 訂閱端用 BEST_EFFORT
- **第一筆 cmd_vel = 0 warmup**：避免與 Go2 driver 已啟動的 stand mode 衝突
- **Hysteresis 3 frame 防抖**：danger → 非 danger 需連 3 frame 確認才解除
- **v8 mount yaw=π 必須設 `front_offset_rad: 3.14159`**（5/1 撞紙箱事件、commit `e3270da` 修）— `compute_front_min_distance` 寫死「laser 0° = Go2 前方」、yaw=π 後不對、需用 offset 補正。`scripts/start_nav_capability_demo_tmux.sh` 與 `start_reactive_stop_tmux.sh` 已加 `-p front_offset_rad:=3.14159`，自寫 launch 命令也要加
- **`/nav/pause` 只有 route_runner_node 接、`nav_action_server`（serving `/nav/goto_relative`）沒接**（5/1 發現 BUG #2，待修）— 只有 `/nav/run_route` 才能完整觸發 reactive_stop 的 pause/resume。送 goto_relative 時 reactive_stop 透過 `/cmd_vel_obstacle=0` mux priority 200 強制停車，但 obstacle 移除後不會自動 continue（5/13 demo 前必修）

### 環境 / 部署
- **Jetson 供電升級至 2464 升降壓恒壓恒流模組**（4/29 night）— XL4015 在 Go2 運行下 4/29 16:30-17:30 跳電 3 次（10 分鐘內），換 2464 後（35W 自然散熱、過流/過壓/過溫多重保護）穩定。Memory `project_jetson_power_issue.md` 已更新。
- **ros2 daemon 偶爾 sync 慢**：剛啟動的 publisher，topic hz 第一次抓不到很正常，等 5-10s 重試
- **重新建圖前先備份（safe loop，避免 brace expansion 缺檔靜默失敗）**：
  ```bash
  BACKUP_TS=$(date +%Y%m%d-%H%M%S)
  for ext in yaml pgm pbstream; do
    src="/home/jetson/maps/home_living_room.${ext}"
    [[ -f "$src" ]] && cp "$src" "${src}.bak.${BACKUP_TS}"
  done
  ```

### Yaw 校正 / mount TF（4/29 經驗）
- **base_link → laser yaw 不能用 Foxglove map/scan 視覺猜**：每改 yaw cartographer 會用該 yaw 建出**內部一致**的 map，視覺對比失去意義。4/29 試 0 / ±π/2 / π 全錯
- **物理錨定才是黃金標準**：用 `scan_health_check.py` 在 Go2 正前方 0.8m 放已知物體 → 看物體距離 ≈ 0.8m 落在哪個 angle bin → 直接判讀 yaw
- **scan-only stack（不啟 cartographer / nav）**：`bash scripts/start_scan_only_tmux.sh`（3-window：tf + sllidar + monitor）— 純物理層測試用
- **scan-only stack 沒 Foxglove**：要視覺驗證需在 monitor window 手動 `ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765`

## 驗證指令

### 單元測試
```bash
# reactive_stop_node 純邏輯（17 cases）
cd go2_robot_sdk && python3 -m pytest test/test_reactive_stop_node.py --no-cov

# vision_perception 既有 lidar_obstacle_detector
python3 -m pytest vision_perception/test/test_lidar_obstacle_detector.py -v
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

### Build
```bash
# 改 reactive_stop_node 後
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
ros2 pkg executables go2_robot_sdk | grep reactive_stop_node  # 確認 entry point
```

### 實機 sanity（Nav2 demo 啟動後）
```bash
ros2 lifecycle get /amcl                                # active
ros2 topic hz /scan_rplidar                            # ~10.4 Hz
ros2 topic hz /cmd_vel                                 # ~10 Hz（goal 啟動後）
ros2 topic info /goal_pose -v                          # 確認 BEST_EFFORT 訂閱端
ros2 run tf2_ros tf2_echo map base_link                # AMCL pose 與現場一致
ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap '{}'
```
