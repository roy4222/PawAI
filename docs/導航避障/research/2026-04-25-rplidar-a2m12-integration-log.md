# RPLIDAR A2M12 整合紀錄

> Status: **進行中**（卡 Gate P0-B 的 odom source）
> 期間：2026-04-24（到貨桌上驗證）→ 2026-04-25（上 Go2 機身 + 嘗試 SLAM 建圖）
> 目的：替代 Go2 內建 LiDAR（18% 覆蓋率 / 5Hz），作為 P0 導航避障的 360° 主感測器

## 硬體規格

| 項目 | 值 |
|------|---|
| 型號 | Slamtec RPLIDAR A2M12 |
| 介面 | USB（CP2102 UART Bridge）|
| Driver | `sllidar_ros2`（Slamtec 官方）|
| 工作距離 | 0.20 - 12 m（spec 16 m 是理論值，實機驗證上限 12 m）|
| 取樣率 | 16 kHz |
| 掃描頻率 | 10 Hz（標稱），實測 10.4-10.94 Hz |
| 點數/圈 | 1800（角度解析度 0.2°，比 datasheet 0.225° 更密）|
| 高度需求 | 1 RU 機身上方平面（裝在 Go2 背上）|

## 4/24 到貨 — 桌上驗證

**驗證環境**：Jetson 桌上接 RPLIDAR（兩條 USB：資料 + 輔助電源），未上 Go2 機身。

**步驟與結果**：

1. CP210x driver enumerate ✅
   ```
   $ lsusb | grep CP210
   Bus 001 Device 004: ID 10c4:ea60 Silicon Labs CP210x UART Bridge
   ```

2. udev rule 設定 `/dev/rplidar` symlink（0777） ✅
   ```
   $ ls -la /dev/rplidar
   lrwxrwxrwx 1 root root 7 /dev/rplidar -> ttyUSB0
   ```

3. clone + build sllidar_ros2 到 `~/rplidar_ws/` ✅

4. `ros2 launch sllidar_ros2 sllidar_a2m12_launch.py`
   - `/scan` **10.57 Hz**
   - **1800 points/scan**
   - **60% valid**（其餘為 0/inf，符合 RPLIDAR 反射特性）
   - range：0.20 - 7.94 m（中位數 1.08 m，房間環境）

5. Foxglove bridge 可視化 ✅（port 8765）

**結論**：硬體 OK，驅動 OK，桌上驗證遠優於 Go2 內建 LiDAR。

**對照舊 Go2 內建 LiDAR 痛點**：

| 歷史痛點 | RPLIDAR A2M12 現況 |
|---------|------------------|
| 7.3Hz 靜止 / 4-6Hz 行走 / burst+gap | 10.57Hz 穩定，無 gap |
| 18% 覆蓋率（22/120 有效點） | 360° 完整，1600 點/圈 |
| Python LZ4 decode 單核滿載 | 純 C++ serial driver，CPU 近零 |
| 7 輪優化才達 5Hz | 開箱即 10Hz |

## 4/24 架構決策翻案

舊判定（2026-04-01）：「Full SLAM 永久關閉」，理由是 Go2 內建 LiDAR 5Hz 品質差，業界 SLAM 門檻 7Hz。

新實測：RPLIDAR 10.5Hz > 7Hz → **Full SLAM / Nav2 路線復活為 P0 主線**。

P0 spec + plan 同日定稿：
- Spec：`docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`（803 行）
- Plan：`docs/superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md`（17 tasks, gate-by-gate TDD）

P0 承諾：劇本式 A→B + 停障 + 續行（不承諾一般動態繞障）。

## 4/25 上機（裝到 Go2 機身）

**步驟**：

1. RPLIDAR 物理裝到 Go2 背上（裝置位置：base_link 上方約 z=0.10 m，估測值，**待精確量測**）
2. USB cable 接到 Jetson
3. 重新跑 `ros2 launch sllidar_ros2 sllidar_a2m12_launch.py`

**實機驗證 /scan 品質（Gate P0-A 重驗）**：

| 項目 | 桌上 (4/24) | Go2 機身 (4/25) |
|------|:-----------:|:----------------:|
| 頻率 | 10.57 Hz | **10.40 Hz** ✅ |
| std dev | n/a | **3 ms** ✅ |
| 點數/圈 | 1800 | 1800 ✅ |

**結論**：實機品質與桌上等級一致，Gate P0-A 在 Go2 機身上也通過。

## 4/25 嘗試 SLAM 建圖（Gate P0-B）— 失敗

### 環境準備（Plan Task 1 Step 1-3，已完成）

```bash
sudo apt install ros-humble-slam-toolbox \
                 ros-humble-nav2-bringup \
                 ros-humble-navigation2 \
                 ros-humble-twist-mux \
                 ros-humble-nav2-map-server \
                 ros-humble-nav2-amcl
mkdir -p /home/jetson/maps
```

`scripts/build_map.sh` 寫好並 sync 到 Jetson `~/elder_and_dog/scripts/`。

### 第一輪嘗試：static fake odom

`slam_toolbox` 啟動需要 TF chain `map → odom → base_link → laser`。Plan 沒寫誰提供 `odom → base_link`。

**嘗試**：用 `static_transform_publisher` 發 fake static `odom → base_link` 與 `base_link → laser`，期望 slam_toolbox 用 scan matching 自己估計位姿。

**結果失敗**：scan 在 Foxglove 動，但 /map 不長。

**根因**：slam_toolbox 用 odom delta 判定是否新增 keyframe（預設 `minimum_travel_distance: 0.5`）。fake static odom 永遠是 0 位移，slam 認為機器人沒動，不更新 map。即使把 `minimum_travel_distance` 降到 0.05、`correlation_search_space_dimension` 從 0.5 加到 3.0，仍因「初始 guess 永遠在原點」而 scan matcher 找不到收斂解。

### 第二輪嘗試：用 Go2 driver 的 /odom

啟動 Go2 driver minimal 模式，期望它提供 `/odom` 與 `odom → base_link` TF：

```bash
export ROBOT_IP=192.168.123.161
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

`/odom` 18.7 Hz，TF chain 完整。但建圖出現經典 **starburst（雪花狀）** 失敗：白色 ray 從中心向四面八方射出（8 m 範圍），但綠色軌跡（實際走過範圍）只有 30 cm。

**根因**：Go2 driver 抓的 odom 來源是 `rt/utlidar/robot_pose`（`webrtc_topics.py:21`），這是 **Go2 內建 utlidar (內建 LiDAR + IMU 融合) 跑的 SLAM 結果**。而 Go2 內建 LiDAR 就是 4/1 已驗證 18% 覆蓋率 / 5Hz 那顆。

**結論**：
- 無論你用 Unitree 遙控器走腿、還是手推，Go2 driver 給的 odom 都是「壞 LiDAR 跑 SLAM 的結果」
- Unitree SDK 沒有公開純 leg encoder odom topic
- **不能用 Go2 driver 的 /odom 做 Nav2 落地**

### 衍生問題：/scan topic 衝突

過程中發現 sllidar 與 Go2 driver 的 /scan 衝突：
- sllidar 預設發 `/scan`（1800 點，frame=laser）
- Go2 driver 也發 `/scan`（120 點，Go2 內建 LiDAR）
- slam_toolbox sensor descriptor 鎖在第一個收到的 scan，後續 1800/120 不一致全被 reject：
  ```
  LaserRangeScan contains 1800 range readings, expected 120
  Message Filter dropping message: ...
  ```

**fix**：sllidar remap `/scan` 為 `/scan_rplidar`，slam_toolbox 對應改 `scan_topic: /scan_rplidar`。

  注意 sllidar launch 不支援 remap arg，要用 `ros2 run sllidar_ros2 sllidar_node --ros-args ... -r /scan:=/scan_rplidar`。

### 第三輪嘗試：rf2o_laser_odometry（純 LiDAR 算 odom）

放棄 Go2 driver odom，改用 RPLIDAR 自己算 odom。

**步驟**：

1. clone `https://github.com/MAPIRlab/rf2o_laser_odometry.git` 到 `~/rplidar_ws/src/`
2. `colcon build --packages-select rf2o_laser_odometry --cmake-args -DCMAKE_BUILD_TYPE=Release` ✅（51s）
3. 啟動 rf2o 訂閱 `/scan_rplidar` → 一直 `Waiting for laser_scans....`

**根因**：QoS 不匹配
- sllidar publisher：RELIABLE / VOLATILE
- rf2o subscriber：BEST_EFFORT / VOLATILE（`CLaserOdometry2DNode.cpp:49`）

理論上 BEST_EFFORT sub 可訂 RELIABLE pub，DDS 實作（Cyclone DDS）上 silent fail。

**fix（部分）**：patch rf2o 源碼為 RELIABLE
```cpp
// 原：rclcpp::QoS(rclcpp::KeepLast(1)).best_effort().durability_volatile()
// 改：rclcpp::QoS(rclcpp::KeepLast(5)).reliable().durability_volatile()
```

重 build 後仍 `Waiting for laser_scans...`，**仍未通**。推測 ros2 daemon stale 或 subscription register 延遲。**4/25 session 結束時尚未解開**。

## 4/25 結束狀態

**已完成**：
- ✅ Gate P0-A 桌上驗證（4/24）
- ✅ Gate P0-A 機身重驗（4/25）— /scan 10.40 Hz
- ✅ slam_toolbox / nav2 / twist_mux / map_server / amcl apt install
- ✅ `/home/jetson/maps/` 建立
- ✅ `scripts/build_map.sh` 寫好並 sync
- ✅ 識別並 fix /scan topic 衝突（remap 到 /scan_rplidar）
- ✅ rf2o source clone + RELIABLE QoS patch + Release build
- ✅ 量化記錄 Go2 driver odom 來源不可用（`rt/utlidar/robot_pose` = 壞 LiDAR SLAM）

**未完成**：
- ❌ Gate P0-B SLAM 建圖（卡 odom source）
- ❌ rf2o `/odom_rf2o` 第一次發布（QoS patch 後仍 Waiting）
- ❌ `home_living_room.{pgm,yaml}` 產出

## 已知問題（待解決）

### 1. rf2o subscription 不通（最高優先）

**狀況**：QoS RELIABLE patch 後仍 `Waiting for laser_scans....`

**下次 session 嘗試順序**：
1. `ros2 daemon stop && ros2 daemon start` 清 DDS 快取
2. 重啟 sllidar + rf2o
3. `ros2 topic info /scan_rplidar --verbose` 確認雙方 QoS profile
4. 若仍不通，改 sllidar 源碼為 BEST_EFFORT 發布（標準 sensor_data QoS）
5. 若還不通，改用 `topic_tools/relay` 跨 QoS 中繼

### 2. Go2 driver odom 不可用於 Nav2

**狀況**：`/odom` 來源是 `rt/utlidar/robot_pose`（內建 SLAM），Unitree 不公開 leg-only odom

**長期決策**：
- Nav2 落地必須用外接 LiDAR odom（rf2o / scan-matcher）
- Go2 driver 的 `/odom` 純粹忽略
- 後續 Plan Task 2-3（AMCL / Nav2 單點）的 odom source 預設改用 rf2o

### 3. base_link → laser 物理位置未量測

**狀況**：當前用估測值 z=0.10 m, x=0, y=0

**影響**：
- 2D 建圖只看 XY 平面，z 無影響（建圖階段可接受）
- AMCL / Nav2 階段：footprint 計算與 obstacle padding 會偏（影響繞障判定 ~10-15 cm）

**待做**：物理量尺量測 RPLIDAR 中心相對 Go2 base_link 的精確 x/y/z（5/13 學校 demo 前必做）

### 4. Plan Task 1 缺 TF chain + odom source 細節

**狀況**：Plan 寫「啟 sllidar + slam_toolbox」就完事，沒講 odom 從哪來、TF chain 怎麼連

**改善**：之後寫 nav 相關 plan 必須明列：
- 每個 task 依賴的 frame chain
- 每個 task 訂閱什麼 topic / 發布什麼 TF
- TF 發布者是誰（static / dynamic / 哪個 node）

### 5. LaserScan range count 對 slam_toolbox 是 hard constraint

**狀況**：`LaserRangeScan contains 1800 range readings, expected 120`

**啟示**：
- 任何訂 `/scan` 的下游套件（slam_toolbox / Nav2 costmap）都會鎖在第一個 LaserScan 的 range count
- 所有 RPLIDAR 整合必須走 `/scan_rplidar` namespace，不能依賴 default `/scan`

## 下一步（接手時的執行順序）

```bash
# 1. 清 DDS 快取
ros2 daemon stop && ros2 daemon start

# 2. 啟 sllidar (remap)
ros2 run sllidar_ros2 sllidar_node --ros-args \
  -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 \
  -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Sensitivity \
  -r /scan:=/scan_rplidar

# 3. 啟 rf2o (吃 /scan_rplidar，發 /odom_rf2o + odom→base_link TF)
ros2 run rf2o_laser_odometry rf2o_laser_odometry_node --ros-args \
  -p laser_scan_topic:=/scan_rplidar -p odom_topic:=/odom_rf2o \
  -p publish_tf:=true -p base_frame_id:=base_link -p odom_frame_id:=odom \
  -p freq:=20.0

# 4. 驗證 /odom_rf2o 有資料
ros2 topic hz /odom_rf2o   # 期望 ~20Hz

# 5. base_link → laser static TF（先用估測值）
ros2 run tf2_ros static_transform_publisher \
  --x 0 --y 0 --z 0.10 --frame-id base_link --child-frame-id laser

# 6. slam_toolbox（吃 /scan_rplidar + odom）
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false \
  slam_params_file:=/tmp/slam_lidar_only.yaml

# 7. Foxglove (8765) 連線確認 /map 有累積

# 8. 推 Go2 繞客廳一圈

# 9. save_map
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "{name: {data: '/home/jetson/maps/home_living_room'}}"
```

**不要起 Go2 driver。**
**不要起 fake static odom→base_link（rf2o 會發）。**

## 備案

如果 rf2o 還是跑不起來：
- 嘗試 `laser_scan_matcher`（scan_tools repo，社群有 humble port）
- 改用 `cartographer_ros`（功能完整但 setup 複雜）
- 最後手段：放棄 SLAM 建圖，改 P0 spec 為「無地圖反應式 collision_monitor 直線 + 停障」（縮回去 4/1 棄用方案）

## 4/25 PM — Path A v3.5: cartographer pure scan-matching 翻盤成功 ✅

> 4/25 PM 從卡 odom 一路試到地圖產出，路線變了 4 次，最終靠 **cartographer + RPLIDAR 純 scan-matching** 過關。本節為 Gate P0-B 結案紀錄。

### 完整時序（從早上卡關到傍晚過關）

| 階段 | 路線 | 結果 |
|------|------|------|
| v1 草案 | slam_toolbox `lidar-only no-odom`（誤判 Issue #221 closed-WONTFIX 為 supported） | User pushback：「slam_toolbox needs odom→base_link motion prior」推翻 |
| v2 路線 | slam_toolbox + Go2 driver `/odom` 作 prior | **全死**。async/sync mode + throttle 1/2/5 全試，全部 `Mapper FATAL ERROR - unable to get pointer in probability search!` exit -6 |
| 真因確認 | nano-flann KD-tree 在 ARM64 + Humble 有已知 bug（GitHub issues #553、#436、#226），yaml 怎麼調都救不回 | 砍 slam_toolbox 路線 |
| v3a 切 cartographer | cartographer + use_odometry=true + Go2 odom（Issue #1440 Configuration 1） | **跑得起來但 starburst 失真**（Go2 utlidar SLAM odom 的 noise 拉壞 cartographer pose graph） |
| v3.5 採納版 | cartographer + **use_odometry=false** + provide_odom_frame=true（純 scan-matching） | ✅ **Gate P0-B 過關** — 客廳輪廓清楚，無 starburst |

### v3.5 架構決策（user 17:18 採納為永久架構）

> User: 「看起來效果不錯，之後就乖乖用 RPLIDAR-A2M12 LiDAR 光達就好了，不要管 go2 內建的雷達了」

**永久路線**：
- SLAM 唯一感測 = **RPLIDAR-A2M12（外接 2D LiDAR）**
- Odom = **cartographer 自己用 RPLIDAR scan-matching 估計**，無外部 odom 訊號
- Go2 完全不參與 SLAM（不啟 Go2 driver、不訂 `/odom`）— 變成純粹的「移動載具」
- Go2 內建雷達永久棄用

**研究依據**：
- [Kabilankb 2024 Medium tutorial](https://medium.com/@kabilankb2003/ros2-humble-cartographer-on-nvidia-jetson-nano-with-rplidar-c0dea4480b78)：Jetson Nano + RPLIDAR + Cartographer pure scan-matching 在 Humble 上已驗證 work
- [Robotics Weekends 2018](https://medium.com/robotics-weekends/2d-mapping-using-google-cartographer-and-rplidar-with-raspberry-pi-a94ce11e44c5)：「for indoor mapping of about 50–60 m², Cartographer's internal loop closure is capable of keeping such maps consistent」
- 我們客廳 24m² + RPLIDAR 10.4Hz 在甜蜜點
- [Cartographer algo doc](https://google-cartographer-ros.readthedocs.io/en/latest/algo_walkthrough.html)：「running the correlative scan matcher... can often render the incorporation of odometry or IMU data unnecessary」

### v3.5 部署形狀

5-window tmux session（`scripts/start_lidar_slam_tmux.sh`），**無 Go2 driver**：

| Window | 用途 |
|:------:|------|
| 1 tf | static_transform_publisher base_link → laser z=0.10 |
| 2 sllidar | sllidar_node Standard mode + remap /scan → /scan_rplidar |
| 3 carto | cartographer_node `use_odometry=false` `provide_odom_frame=true` |
| 4 carto_grid | cartographer_occupancy_grid_node 從 /submap_list 算 /map |
| 5 fox | foxglove_bridge port 8765 |

**Cartographer config**（`go2_robot_sdk/config/cartographer_lidar.lua`）關鍵參數：
- `use_odometry = false` / `provide_odom_frame = true` / `published_frame = base_link`
- `min_range = 0.20` / `max_range = 8.0` / `missing_data_ray_length = 5.0`
- `use_online_correlative_scan_matching = true` / `angular_search_window = 20°`
- `submaps.num_range_data = 90` / `optimize_every_n_nodes = 35`
- `MAP_BUILDER.num_background_threads = 4`（Orin Nano 6 cores 留 2 給驅動）

### Save map 三步驟

cartographer 不像 slam_toolbox 有單一 service，要依序執行：

```bash
ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory "{trajectory_id: 0}"
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "{filename: '/home/jetson/maps/home_living_room.pbstream', include_unfinished_submaps: true}"
ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/home_living_room --ros-args -p map_subscribe_transient_local:=true
```

### 產出

```
/home/jetson/maps/home_living_room.pgm       # 583×513 cells (29.15m × 25.65m) @ 5cm/pixel
/home/jetson/maps/home_living_room.yaml      # nav2 載入用
/home/jetson/maps/home_living_room.pbstream  # cartographer 內部狀態，未來可重 load
```

### 已知 cosmetic 問題（不影響 nav2）

地圖看起來「比實際家大」— 是 RPLIDAR 雷射波**穿透窗戶玻璃**打到窗外造成的散射。物理現象，重掃也不會消失。
- ✅ 不影響 AMCL（likelihood field 比對 self-consistent）
- ✅ 不影響 Nav2 路徑規劃（Go2 永遠到不了窗外 free space）
- ⚠️ Demo 視覺上不完美 — 後續可用 GIMP 把窗外區域塗灰

### 之前列為「已知問題」的清單 — 解決方式

1. ~~rf2o subscription 不通~~ → **跳過 rf2o**。cartographer 內建 scan-matching 已夠用，外掛 rf2o 是 overkill（[官方 algo doc 確認](https://google-cartographer-ros.readthedocs.io/en/latest/algo_walkthrough.html)）。Note：rf2o 真因不是 QoS 是 base_link↔laser TF 沒準備好就啟動（[issue #15](https://github.com/MAPIRlab/rf2o_laser_odometry/issues/15)）
2. ~~Go2 driver odom 不可用於 Nav2~~ → **永久棄用 Go2 odom**。cartographer 自己估
3. ~~base_link → laser 物理位置未量測~~ → 仍用 z=0.10 估測，5/13 學校 demo 前精量
4. ~~Plan Task 1 缺 TF chain + odom source 細節~~ → v3.5 lua + tmux launcher 已明確 own 整條 TF chain
5. ~~LaserScan range count hard constraint~~ → 已通過 sllidar remap 解決

---

## 相關檔案

- `scripts/start_lidar_slam_tmux.sh`（v3.5 5-window tmux launcher）
- `scripts/build_map.sh`（v3.5 含 3 步驟 save_map prompt）
- `go2_robot_sdk/config/cartographer_lidar.lua`（v3.5 採納配置）
- `go2_robot_sdk/config/slam_lidar_only.yaml`（v2 slam_toolbox archive，**不再啟用**）
- `~/rplidar_ws/src/sllidar_ros2`（Jetson）
- `~/rplidar_ws/src/rf2o_laser_odometry`（Jetson archive，**不再啟用**）
- Spec：`docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`
- Plan：`docs/superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md`

---

## 4/25 PM 後續：v3.6 cartographer pure-loc 試錯 → v3.7 切 AMCL → Nav2 整段打通

### v3.6 嘗試：cartographer pure-localization mode（17:00-19:00, 失敗）

**動機**：建圖完成後直接做 P0-D Nav2 demo。研究選擇 cartographer pure-localization（載入 .pbstream + `pure_localization_trimmer` + 不啟 amcl/map_server），架構與 mapping mode 95% 一致，Nav2 用 `navigation_launch.py` 純導航。

**已部署**：
- `go2_robot_sdk/config/cartographer_lidar_localize.lua`（include 既有 mapping lua + 加 trimmer）
- `scripts/start_nav2_demo_tmux.sh`（v3.6 archive，**不再啟用**）
- patch `ros2_publisher.py` 加 `GO2_PUBLISH_ODOM_TF` env 開關（v3.6 設 0 讓 cartographer own 整條 TF）

**結果**：Stack 啟動、Nav2 lifecycle 全 active、bt_navigator 接受 goal — 但 cartographer pose tracking **漂移**。19:00 user 觀察到 Go2 在 (0.07, 0.04) 站著沒動，cartographer 報 pose 跳到 (12.30, 4.90)。Nav2 用錯誤起點規劃路徑，goal 失意義。

**根因**：pure-localization 在 nav2 重啟瞬間 cartographer scan-match 重新對齊 .pbstream，過程中 pose 容易跳到地圖中其他相似位置（窗外散射 + 對稱牆面造成 scan match ambiguity）。

### v3.7 架構翻案：拆「建圖 cartographer / 定位 AMCL」（19:30）

**user 決策**：「建圖用 Cartographer pure scan-matching（已成功不變），導航定位改 AMCL + Go2 odom + RPLIDAR map localization」。

**新 TF 架構**：
| TF | 發布者 |
|------|--------|
| `map → odom` | **AMCL** 發 |
| `odom → base_link` | **Go2 driver** 發（恢復 v3.5 之前棄用的 odom TF）|
| `base_link → laser` | static_transform_publisher（z=0.10）|

**為什麼 Go2 odom 在 AMCL 下能用、建圖時不能**：建圖時 cartographer 把 odom 進 pose graph optimization，long-horizon noise 累積拉壞地圖；AMCL 用 likelihood field 對齊 RPLIDAR scan，odom 只當「上一幀到這幀的短期位移估計」（200ms 內），長期由 scan match 修正。Quadruped odom cm 級短期漂移在 AMCL 容忍範圍。

### Step 0 重要實機數據：Go2 sport mode cmd_vel MIN_X = 0.50（19:55）

**起因**：v3.6 試 nav2 時發 cmd_vel 0.11 m/s Go2 沒走。Web research 發現 abizovnuralem 自家 issue #36 證實「Go2 doesn't move if velocity < 1.0 (Isaac Sim)」、自己 nav2_params.yaml 把 `max_vel_x` 從 nav2 default 0.26 改到 3.0 標 `#changed`。Quadruped trot gait 需要最小 stride，太低被韌體當「站著踏步」吃掉。

**實機 calibration（user 19:55 在現場）**：

| cmd_vel.x | 持續時間 | Go2 反應 | 結論 |
|-----------|:------:|---------|------|
| 0.35 | 2.5s | 移動 ~1cm | 被 sport mode 吃掉，**不動** |
| **0.50** | 2.5s | **移動 86cm** | **MIN_X = 0.50 m/s 確認** ✅ |

**這是給 PawAI 專案未來所有 Nav2 / cmd_vel 配置的權威基線數據。** 任何 controller / DWB 設定的 `min_vel_x` 必須 ≥ 0.45（含 5% 安全 margin），否則 Go2 拒抬腳。

### v3.7 部署細節（20:00-20:45）

**Stack 結構**（5-window，`scripts/start_nav2_amcl_demo_tmux.sh`）：
| Window | 用途 |
|:-:|------|
| 1 tf | static_transform_publisher base_link → laser z=0.10 |
| 2 sllidar | sllidar_node Standard mode + remap /scan → /scan_rplidar |
| 3 driver | Go2 driver minimal（**不設 GO2_PUBLISH_ODOM_TF env**，恢復發 odom TF）|
| 4 nav2 | `nav2_bringup/bringup_launch.py slam:=False`（自帶 amcl + map_server + navigation 全 stack）|
| 5 fox | foxglove_bridge port 8765 |

**`nav2_params.yaml` v3.7 關鍵改動**：
- AMCL: `scan_topic: /scan_rplidar`、`alpha1-4: 0.4`（quadruped slip）、`min/max_particles: 100/500`、`set_initial_pose: false`、`first_map_only: true`、`update_min_d/a: 0.10`
- DWB: `min_vel_x: 0.45`、`max_vel_x: 0.70`、`max_vel_theta: 1.20`、`acc_lim_x: 1.5`（基於 Step 0 MIN_X=0.50）
- Costmap obstacle_layer: `topic: /scan_rplidar`（local + global）、`obstacle_max_range: 1.8`、`raytrace_max_range: 2.0`、`inflation_radius: 0.25`

### v3.7 驗證 alive（20:45）

```
NODES（all active）:
/amcl ✅ /map_server ✅
/controller_server ✅ /planner_server ✅ /bt_navigator ✅
/behavior_server ✅ /smoother_server ✅ /velocity_smoother ✅ /waypoint_follower ✅
/go2_driver_node ✅ /sllidar_node ✅ /static_transform_publisher_* ✅ /foxglove_bridge ✅

TF chain:
map → odom → base_link → laser  ✅（雙 publisher 隔離無衝突）

Goal handling:
[bt_navigator] Begin navigating from (0.13, -0.13) to (0.50, 0.00)
[controller_server] Reached the goal!
[bt_navigator] Goal succeeded
```

**整套 Nav2 pipeline 確認可用**：goal_pose → bt_navigator → controller_server → cmd_vel → Go2 driver → WebRTC api_id 1008 → Go2 sport mode。

### v3.7 卡點：inflation lethal space（21:00 hard stop）

**現象**：發 1.5m goal 後 nav2 報：
```
GridBased: failed to create plan, invalid use: Starting point in lethal space!
Planning algorithm GridBased failed to generate a valid path to (3.00, 0.00)
Running spin... Turning 1.57 for spin behavior
spin failed
```

**真因**：
1. AMCL 估計 Go2 在 (1.56, -0.16) 附近
2. costmap 中該位置被 inflated obstacles 包圍（`inflation_radius: 0.25` 把 RPLIDAR 散射 + 窗外點 inflate 包住）
3. planner 拒絕規劃 → bt_navigator 觸發 spin recovery → spin 也失敗（quadruped 在低 cmd_vel 下無法原地轉）

### 4/26 接力清單（30-60 min 應可解）

1. `inflation_radius: 0.25 → 0.10`（給 Go2 多 free space）
2. `obstacle_max_range: 1.8 → 1.0`（縮 RPLIDAR 看的距離，避免遠處散射污染）
3. `xy_goal_tolerance: 0.30 → 0.50`（小空間容忍度）
4. 啟動後手動清 costmap：`ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap`
5. 改用 RViz 設 initial pose（Foxglove Publish 工具不易操作）
6. 重發 1.5m goal，期望 Go2 物理走過去

**Fallback**（若 nav2 仍卡）：寫 50 行 `reactive_forward.py`，cmd_vel 0.5 + 既有 lidar_obstacle_node 反應式停障，直接展現「RPLIDAR 即時保護 Go2」。

### v3.7 新增/改動檔案

- `go2_robot_sdk/config/nav2_params.yaml`（AMCL + DWB + costmap 全套 v3.7 改動）
- `go2_robot_sdk/go2_robot_sdk/infrastructure/ros2/ros2_publisher.py` 加 `GO2_PUBLISH_ODOM_TF` env 開關（line 27-29 + line 66-68）
- `scripts/start_nav2_amcl_demo_tmux.sh`（v3.7 主線 launcher）
- `scripts/start_nav2_demo_tmux.sh`（v3.6 cartographer pure-loc archive，**不再啟用**）
- `go2_robot_sdk/config/cartographer_lidar_localize.lua`（v3.6 archive，**不再啟用**）

### Commit 索引

| Commit | 內容 |
|--------|------|
| `b27e320` | Gate P0-B SLAM 建圖過關 — cartographer pure scan-matching (v3.5) |
| `bec13cc` | P0-D WIP — Cartographer + Nav2 + AMCL stack 整段打通（卡 inflation） |
