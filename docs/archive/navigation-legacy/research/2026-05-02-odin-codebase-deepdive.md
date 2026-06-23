# Odin Nav Stack — Codebase Deep Dive

> **Source**: https://github.com/ManifoldTechLtd/Odin-Nav-Stack
> **Commit**: `f71b5e9fe9b4ebd11e11b478ccfb3df7cd2201ca` ("<fix> env, driver, FAQ", HEAD of `main` 抓取於 2026-05-02)
> **Workspace**: ROS1 Noetic, `catkin` (整個 `ros_ws/src/CMakeLists.txt` symlink 到 `/opt/ros/noetic/share/catkin/cmake/toplevel.cmake`)
> **Purpose**: 補強 `2026-05-02-odin-stack-comparison.md` — 用真實程式碼驗證部落格筆記推論。

---

## 1. 語義導航 `object_query_node.py`（1790 行 ROS1 Python）

### 函式簽章（精確還原）

| 函式 | 簽章 | 行號 |
|---|---|---|
| `parse_navigation_command(command: str)` | → `(action, object_name, direction, index) \| None` | 354–637 |
| `find_object(object_name: str)` | → `[(class_id, class_name, x_map, y_map, z_map, score), ...]` | 201–245 |
| `calculate_target_position_relative_to_robot(object_pos_map, direction, distance)` | → `(x, y, z)` in **map frame** | 673–722 |
| `calculate_target_position_in_map(object_pos_map, direction, distance)` | 純 map-axis 偏移（fallback） | 724–756 |
| `transform_camera_to_map(camera_pos)` | quaternion → 3×3 R 手寫，非 tf2 transform_pose | 758–796 |
| `send_navigation_goal(target_pos_map)` | 發 PoseStamped 到 `/move_base_simple/goal` | 821–897 |

### 依賴 Topics

| 訂閱 | 型別 | 用途 |
|---|---|---|
| `/yolo_detections_3d` | `vision_msgs/Detection3DArray` | 主要(含 depth) |
| `/yolo_detections` | `Detection2DArray` | fallback list |
| `/yolo_class_names` | `std_msgs/String`(JSON dict) | class_id → name 映射 |

| 發布 | 型別 | 用途 |
|---|---|---|
| `/move_base_simple/goal` | `PoseStamped` | move_base 入口 |
| `/object_markers`, `/navigation_goal_marker` | `MarkerArray`, `Marker` | RViz |
| `/object_query_result` | `String`(JSON) | 給其他 node 用 |

TF: `lookup_transform(target_frame=map, source=camera_link/base_link, Time(0), Duration(0.5/1.0))`。

### 「物體右邊 1m」的真實算法（**與筆記不同，是 base_link rotation，不是相機側軸**）

關鍵在 `calculate_target_position_relative_to_robot`（673–722）:
```
1. lookup_transform(map, base_link)  → quaternion → R (3x3, base→map)
2. ex_map = (R[0][0], R[1][0], 0)   # base_link x 軸投影到 map 平面
3. ey_map = (R[0][1], R[1][1], 0)   # base_link y 軸投影到 map 平面
4. dx,dy ← {front:+x, behind:-x, left:+y, right:-y} × distance
5. offset_map = dx*ex_map + dy*ey_map     # 向量合成
6. target = (x_obj+offset_map[0], y_obj+offset_map[1], z_obj)
```
即「右邊 1m」= 物體中心沿**機器人當前朝向的右側**偏移 1m,**不是 map 絕對 +X 也不是相機光軸**。Z 維持物體高度(後續 `send_navigation_goal` 強制 z=0)。

⚠️ **沒有任何障礙檢查**。落點若落在牆內、桌下、人身上,純靠 move_base 局部 planner 拒收。我們抄時要在 `nav_capability` 端做 costmap query 拒絕 lethal cell。

### 詞庫匹配亮點(可直接抄)

- `parse_navigation_command` 中內建 **57 個英文 COCO + 60+ 中文同義詞**(`fallback_names` L439–495, `cn_obj_map` L505–564)
- 排序策略: `sorted(known_names, key=len, reverse=True)` — **長詞優先**(避免 "wine glass" 被 "wine" 截斷)
- 索引解析: `#2` / `no.2` / `2nd` / `second` / `第二個` / `第2个` 全支援(L405–423)
- 中文句型 regex: `(到|去到|走到|移动到|运动到)\s*(第N个)?\s*<物體>的(右边|左边|前边|后边)`(L566–569)

→ 對 PawAI: RuleBrain fallback 直接挪用詞庫 + regex,LLM brain 失敗時保底。

---

## 2. 自製 DWA — 真實位置與可移植性

### Obstacle Decay (`local_costmap.cpp`)
- L23 預設 `decay_factor_(0.95f)`(部落格說的 0.95 ✓);`local_planner.cpp` L51 ROS param 預設 `0.92f` 覆寫(**兩處不一致,以 ROS param 為準**)
- L140–148 `applyDecay()`: 對所有 `>0` cell `cost = cost * decay_factor_`(uint8 截斷)
- 來源資料是 `/scan`,L88–96 用 **手寫 Bresenham** 在 ray path 上標 free space,end point 標 obstacle

### Heading Alignment Boost (`dwa_planner.cpp`)
- L154–166 `scoreTrajectory`: `heading_score = 1.0 - clamp(diff/π, 0, 1)`
- L162–165 **核心 boost**: 若 `diff > heading_align_thresh_` 則 `heading_score *= heading_boost_`
- 預設值(`local_planner.cpp` L76–77): `heading_align_thresh=0.7 rad (~40°)`, `heading_boost=1.5`

### Bounded Recovery (`dwa_planner.cpp` L77–89)
- 所有 sample traj 都 collision 時(`best_score = -inf`),inline 算 `yaw_to_goal = atan2(goal.y, goal.x)`,直接送 `w = sign(yaw_to_goal) * 0.6 * omega_max_`,**不返回失敗**
- 取代 BT 狀態跳 RotateRecovery — 對 Go2(MIN_X=0.5 m/s 拒原地轉)其實一樣轉不動,但邏輯位置(planner 內 inline)比 BT recovery 適合 quadruped 的 reactive replan

### 可移植性到 Nav2 DWB?

❌ **不能直接移植**:
- DWB 是 plugin 架構(`nav2_core::Controller`),Odin 寫死 `move_base` 介面
- DWB 已有 `PathAlign` critic + `RotateToGoal` critic + `BaseObstacle` critic — 概念覆蓋,但不是相同算法
- decay 是 stateful local costmap,Nav2 用 STVL/voxel layer + observation_sources timeout 達成類似效果(`scan` source 的 `obstacle_max_range` + `expected_update_rate`)

✅ **可吸收**(調 Nav2 yaml,不寫 plugin):
- `PathAlign.scale` ↑ + `PathAlign.forward_point_distance` ↓ ≈ heading boost 效果
- `obstacle_max_range`/`raytrace_max_range` 加上 STVL `decay_model: 0`(exponential) 達成 decay
- inline recovery 對 Go2 用處有限(MIN_X 限制),不值得寫 DWB plugin

---

## 3. ROS1 → ROS2 移植難度

| 項目 | 難度 | 備註 |
|---|---|---|
| `object_query_node.py`(1790 行) | 🟢 **低**(2-3 天) | 純 Python + tf2 + msgs。`rospy.*` → `rclpy.*`,`vision_msgs` 兩版相容,`/move_base_simple/goal` → Nav2 action client |
| `model_planner`(C++ DWA) | 🔴 **高**(1-2 週) | 1071 行 C++,要重寫成 `nav2_core::Controller` plugin。**不值得**,Nav2 DWB 夠用 |
| `navigation_planner` config/launch | 🟡 **中** | 直接套 Nav2 yaml 即可,不需移植 |
| `odin_ros_driver`(SLAM 模組) | ⚫ **不需** | 不開源(README L24「inside Odin1, not open-sourced」) |

**結論**:只移 `object_query_node.py`,planner 全用 Nav2,**80% 價值用 10% 工**。

---

## 4. 隱藏 Gem(原文件未提)

1. **`fish2pinhole/cloud_crop_node`** — 從 SLAM 點雲依四棱錐 FOV 裁切。對 PawAI 無用(我們 2D-only),但若未來要做 3D safety zone 可參考。
2. **`fake360`**(`src/fake360.cpp`) — 把窄 FOV laser 偽造成 360° scan(補空 sector 用)。**Demo 暗黑技**:RPLIDAR 若被 Go2 機體擋住一段角度,可用此補無窮遠值騙 Nav2(我們現用 `front_offset_rad` 和 `lidar_angle_min/max` 過濾,fake360 是 plan B)。
3. **`odin_vlm_terminal/scripts/ros_vlm_terminal.py`** — VLM 場景描述終端機,值得後期看(VLM 整合到 Brain Expression 層)。
4. **Vosk 中文離線 ASR**(`object_query_node.py` L33–39, L1599+) — voice loop with VAD-by-silence(`voice_end_silence=0.8s`, `voice_min_duration=1.2s`, `voice_max_duration=4.0s`, `voice_debounce=1.5s`)。我們 SenseVoice 路線更強,但這套靜音斷句參數對 VAD 調參有參考價值。
5. **`/yolo_class_names` 用 `std_msgs/String` JSON dict 廣播 class map** — 比寫死在 launch param 優雅,object_perception 可以借用。

---

## 5. 對 `2026-05-02-odin-stack-comparison.md` 的補強/修正

| 原文件說法 | 真實程式碼 | 動作 |
|---|---|---|
| 「向量合成,不衝物體中心,算側方安全著陸點」 | ✅ 向量合成正確,❌ **無安全檢查**,純粹是物體中心 + 機器人朝向偏移 | 補 caveat |
| `decay_factor=0.95` | ⚠️ Header default 0.95,ROS param default **0.92**(實跑值) | 補註 |
| obstacle decay 加到 reactive_stop_node buffer | reactive_stop 是 stateless filter,**Nav2 STVL layer 才是對的位置** | 修建議 |
| `parse_navigation_command` 抄三函式 | 還要抄 `transform_camera_to_map` 自製 quaternion → R(避免 tf2_geometry_msgs 在 ROS2 額外依賴) | 補 |
| 雙語詞庫匹配缺口 | 詞庫 + regex 共 ~200 行,可獨立成 `nav_capability/spatial_grounding.py` 模組 | 細化 P1 |

