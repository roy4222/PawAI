# Jetson Orin Nano 8GB + Go2 Pro SLAM/Nav2 整合路線圖（Gate 式執行版）

**目標**: 在 NVIDIA Jetson Orin Nano SUPER 8GB 上實現 Go2 Pro 的 SLAM 建圖與 Nav2 自主導航

**狀態**: 🔄 Gate A 驗證中  
**最後更新**: 2026-02-24  
**預估時程**: 1-2 週驗證 + 1-2 週功能開發

---


### ⚠️⚠️⚠️ 修改 nav2_params.yaml 後必須 build（重大教訓 2026-02-28）

**問題**: 修改 `go2_robot_sdk/config/nav2_params.yaml` 後直接重啟，但 Nav2 一直使用舊參數，導致調參無效、反覆 ABORTED，浪費三小時。

**根因**: ROS2 啟動時讀取的是 `install/` 目錄下的檔案，不是 source 目錄。必須 `colcon build` 才會把修改從 source 複製到 install。

**正確流程**:
```bash
# 1. 修改 go2_robot_sdk/config/nav2_params.yaml
# 2. 務必 build（關鍵步驟）
colcon build --packages-select go2_robot_sdk

# 3. 確認 install 檔案已更新
grep 'max_vel_x\|inflation_radius' install/go2_robot_sdk/share/go2_robot_sdk/config/nav2_params.yaml

# 4. 重啟節點（這次才會讀到新參數）
zsh scripts/start_nav2_localization.sh

# 5. 驗證 live 參數（確保生效）
zsh scripts/ros2w.sh param get /controller_server FollowPath.max_vel_x
```

**檢查清單**:
- [ ] 修改 YAML 後有執行 `colcon build`
- [ ] 啟動後檢查 live 參數 (`ros2 param get`) 確認已更新
- [ ] 若 live 參數與檔案不一致 → 表示 build 未執行或失敗


## ⚠️ 關鍵修正（執行前必讀）

### Frame 設定不一致（已修正）
**問題**: 原本 nav2_params.yaml 混用 odom/map，造成 costmap/BT/定位互相打架

**修正方案**: 
- **建圖模式** (Gate B): 只用 SLAM，不用 AMCL
- **導航模式** (Gate C/D): 關閉 SLAM，只用 AMCL + 載入的地圖
- **不要混用**: slam_toolbox localization 與 AMCL 二選一

### 地圖載入路徑（已設定）
**問題**: map_server.yaml_filename 原本為空

**修正**: Gate C/D 啟動時需指定地圖路徑：
```bash
ros2 launch go2_robot_sdk robot.launch.py \
    slam:=false nav2:=true \
    map:=/home/jetson/go2_map.yaml
```

### Jetson 8GB 優化參數（已更新到 yaml）

**1. slam_toolbox 優化** (`mapper_params_online_async.yaml`):
```yaml
slam_toolbox:
  ros__parameters:
    throttle_scans: 2           # 原 1，降低計算頻率
    map_update_interval: 2.0    # 原 1.0，拉長更新週期
    max_laser_range: 10.0       # 原 20.0，減少計算量
    minimum_time_interval: 0.2  # 原 0.1，降低更新頻率
```

**2. Nav2 優化** (`nav2_params.yaml`):
```yaml
# AMCL 降低粒子數
amcl:
  ros__parameters:
    max_particles: 1000         # 原 2000
    min_particles: 500
    save_pose_rate: 1.0         # 提高至 1Hz

# Local costmap 降低負載
local_costmap:
  local_costmap:
    ros__parameters:
      update_frequency: 5.0     # 降低更新頻率
      publish_frequency: 2.0
      resolution: 0.075         # 原 0.05，降低解析度
      width: 6                  # 保持
      height: 6
      inflation_radius: 0.15    # 縮小膨脹半徑

# Controller 降低採樣
controller_server:
  ros__parameters:
    controller_frequency: 10.0
    FollowPath:
      vx_samples: 10            # 原 20
      vtheta_samples: 15        # 原 20
      sim_time: 1.0             # 原 1.2
      max_vel_x: 0.3            # 降低最大速度
      max_vel_theta: 0.5
```

**3. pointcloud_to_laserscan 優化** (`robot.launch.py`):
```python
parameters=[{
    "target_frame": "base_link",
    "min_height": -0.25,
    "max_height": 0.5,
    "range_min": 0.2,
    "range_max": 10.0,          # 原 30.0，改為 10m
    "angle_increment": 0.0087,  # ~720 beams
}]
```

---

## Gate 式驗證流程

> **核心原則**: 先求穩再求全開。每個 Gate 有明確 go/no-go 條件，不通過不進下一關。

### 2026-02-24 實測紀錄（今日踩坑與進度）

#### 已確認進度
- ✅ `raw voxel` 上游頻率穩定：`/utlidar/voxel_map_compressed` 約 **7.35 Hz**
- ✅ 清場後 `point_cloud2/scan` 可回到約 **7.3 Hz**（符合 Gate A 門檻）
- ✅ 網路本身穩定：`ping` 0% packet loss，RTT 約 0.2ms

#### 今日主要踩坑
1. **多個殘留 go2_driver_node 同時在跑**
   - 現象：`/point_cloud2` Publisher count = 3，導致 `hz` 結果失真
   - 影響：看起來像「頻率忽高忽低/超卡」，實際是多實例互相干擾

2. **直接用 `ros2 launch` 測試時忘記帶 `ROBOT_IP`**
   - 現象：`Robot IPs: ['']`，並出現 `Invalid URL 'http://:9991/con_notify'`
   - 影響：根本無法建立 WebRTC 連線

3. **`robot_cpp.launch.py` 預設會開影像與 TTS**
   - 現象：H264 decode warnings (`non-existing PPS`, `decode_slice_header error`)
   - 影響：消耗 CPU，干擾 LiDAR 效能判讀

4. **`decode_lidar=false` 時看到 `missing positions/uvs`**
   - 現象：log 顯示 LiDAR decode missing positions/uvs
   - 說明：這是 raw voxel 模式的預期行為，不代表上游壞掉

#### 已落地修正
- `start_go2_wired_webrtc.sh`：新增 `PUBLISH_RAW_VOXEL`，並固定 `enable_tts:=false`
- `robot.launch.py`：新增 `enable_tts`（預設 false），並降低 `pointcloud_to_laserscan` `range_max`
- `robot_cpp.launch.py`：補齊 `enable_video/decode_lidar/publish_*` 參數並支援關閉 TTS
- WebRTC driver：避免 `enable_video=false` 時仍強制開 video stream

#### 實測結論（今天）
- **根因不是網路延遲**，而是「測試環境殘留多實例 + 本地解碼路徑負載」混在一起
- 正確清場後，當前 pipeline 已能達到 Gate A 的頻率要求

#### 2026-02-25 Gate B 追測（新增）
- 觀測到 `/scan` 約 **2.9~3.2 Hz**，且有單次 **1.24s / 1.85s** 卡頓
- `/map` 有輸出（SLAM 在跑），但 `scan` 頻率未達 Gate A/Gate B 的穩定標準
- 判定：**Gate B 暫時 NO-GO**（先穩定 `scan` 再進入正式建圖）

#### 2026-02-25 已套用降載修正（新增）
- `scripts/start_slam_mapping.sh`：將 `foxglove:=false`、`teleop:=false`（降低非必要負載）
- `robot.launch.py`：`pointcloud_to_laserscan` 新增 `queue_size: 2`、`angle_increment: 0.0349`、`scan_time: 0.1`
- `mapper_params_online_async.yaml`：`throttle_scans: 2`、`map_update_interval: 2.0`、`max_laser_range: 10.0`、`minimum_time_interval: 0.2`、`enable_interactive_mode: false`

#### 2026-02-25 第二輪降載（throughput-first）
- 觀測：`/point_cloud2` 與 `/scan` 同步掉到約 **2 Hz**，代表瓶頸不只在 `pointcloud_to_laserscan`，而是整體 CPU 爭用（driver decode + SLAM）
- 新增降載：
  - `scan_buffer_size: 5`（原 10）
  - `do_loop_closing: false`（先保頻率，暫時關閉閉環）
  - `correlation_search_space_dimension: 0.3`（原 0.5）
  - `correlation_search_space_resolution: 0.02`（原 0.01）
  - `loop_search_maximum_distance: 2.0`（原 3.0）
- 策略：先讓 `/point_cloud2`、`/scan` 回到穩定 >5Hz，再回頭逐步恢復 map 精度參數

#### 2026-02-25 第三輪隔離（RTC 訂閱瘦身）
- 觀測：`tegrastats` 顯示單一 CPU core 長時間 100%，且 `/point_cloud2` 與 `/scan` 同步掉到 ~2Hz
- 新增 driver 參數：`minimal_state_topics`（只訂閱 `ROBOTODOM` + `ULIDAR_ARRAY`，暫時不訂閱 `LOW_STATE` / `LF_SPORT_MOD_STATE`）
- 套用位置：
  - `scripts/start_slam_mapping.sh` 預設 `minimal_state_topics:=true`
  - `start_go2_wired_webrtc.sh` 新增 `MINIMAL_STATE_TOPICS` 環境變數（預設 false）
  - `robot.launch.py` / `robot_cpp.launch.py` 新增 launch arg `minimal_state_topics`
- 目的：降低 WebRTC 訊息解析與 ROS 發布負載，優先回復 LiDAR 主鏈路頻率

#### 2026-02-25 第四輪上游優化（PointCloud2 序列化降載）
- 根因指向：`/point_cloud2` 先掉速、單核 100%，符合「Python 端點雲封包成本過高」
- 已套用：
  - `ros2_publisher.py` 改為使用 contiguous NumPy + `tobytes()` 直接填入 `PointCloud2.data`
  - `lidar_decoder.py` 新增 `point_stride` 快速路徑（`intense_limiter<=0` 時不走 UV 強度計算）
  - 新增參數 `lidar_point_stride`（default=1），可在 launch 動態調整點雲密度
- 目前 Gate B 預設：`lidar_point_stride:=4`（先換頻率，再回補精度）

#### 2026-02-25 第五輪根因修正（Decoder backend 固定）
- 新發現：`data_decoder.py` 原先優先載入 `lidar_decoder_lz4.py`，該路徑含 Python 巢狀 bit-loop，容易造成單核滿載。
- 修正：加入 `GO2_LIDAR_DECODER` backend 選擇（`wasm` / `lz4`），預設固定 `wasm`。
- 啟動腳本已預設：
  - `scripts/start_slam_mapping.sh` → `GO2_LIDAR_DECODER=wasm`
  - `start_go2_wired_webrtc.sh` → `GO2_LIDAR_DECODER=wasm`
- 可切換驗證：
  - `GO2_LIDAR_DECODER=wasm zsh scripts/start_slam_mapping.sh`
  - `GO2_LIDAR_DECODER=lz4 zsh scripts/start_slam_mapping.sh`

#### 2026-02-25 第六輪熱路徑修正（WASM float32 快速解碼）
- A/B 結果顯示 `wasm` 與 `lz4` 都約 1.6Hz，代表瓶頸不在 backend 切換本身，而在 decode 後資料轉換。
- 修正：`lidar_decoder.py` 將 WASM `positions/uvs` 直接以 `float32` 解析，避免先走 `uint8` 再轉 `float32` 的重成本路徑。
- `update_meshes_for_cloud2` 新增 dtype fast-path（對 `float32` 走零拷貝路徑）。

#### 2026-02-25 第七輪降採樣前移（Early Stride）
- 針對 `intense_limiter<=0` 的主路徑，將 `point_stride` 抽樣前移到幾何換算前，避免對全部點做 `res/origin` 向量運算。
- `start_slam_mapping.sh` 改為可調 `LIDAR_POINT_STRIDE`，目前預設 **8**（原 4）。
- 目的：先把上游 `/point_cloud2` loop 週期壓短，若頻率回升再逐步把 stride 往下調。

#### 2026-02-25 重建後驗證（關鍵）
- 現象：先前一直看到 `Using LidarDecoderLz4`，確認是 `install/` 還在舊版，並非 source tree 最新碼。
- 動作：`colcon build --packages-select go2_robot_sdk` 後再次測試。
- 結果（`GO2_LIDAR_DECODER=wasm`, `LIDAR_POINT_STRIDE=8`, 10s）：
  - `/point_cloud2` 約 **5.11~5.14 Hz**
  - `/scan` 約 **5.11~5.15 Hz**
- 判定：**Gate B frequency 重新達標（GO）**。

#### 清場腳本補強（避免污染）
- `scripts/go2_ros_preflight.sh` 新增第二階段 `pkill -9` 強制清理殘留進程。
- prelaunch 若仍偵測到 publisher 會輸出警告，提示有污染風險。

#### 每次測試前固定清場（重要）
```bash
zsh scripts/go2_ros_preflight.sh prelaunch
```

#### 清場後驗證（必做）
```bash
# 啟動後再做一次，確保只有單一發布者
zsh scripts/go2_ros_preflight.sh postlaunch
```
- 預期：每個 topic 的 Publisher count 應為 1，再開始量測 `hz`

---

## Gate A: 感測資料流驗證 ⏱️ 30 分鐘

**目標**: 確認 `/scan` 穩定輸入，TF 鏈路正確

### 啟動指令
```bash
# Terminal 1: 先清場
zsh scripts/go2_ros_preflight.sh prelaunch

# Terminal 1: 最小啟動（只開 driver + pointcloud_to_laserscan）
zsh start_go2_wired_webrtc.sh minimal

# Terminal 2: 啟動後驗證 publisher count
zsh scripts/go2_ros_preflight.sh postlaunch

# Terminal 2: 若當前 shell 沒 source ROS，請用包裝器執行 ros2 指令
# （避免 zsh: command not found: ros2）

# 確認只有這些節點在跑
zsh scripts/ros2w.sh node list
# 應該看到:
#   /go2_driver_node
#   /go2_pointcloud_to_laserscan
```

### 驗證檢查清單

| 檢查項 | 指令 | 通過條件 |
|--------|------|----------|
| **網路延遲** | `ping 192.168.123.161` | < 5ms |
| **point_cloud2 頻率** | `zsh scripts/ros2w.sh topic hz /point_cloud2` | 7-14 Hz |
| **scan 頻率** | `zsh scripts/ros2w.sh topic hz /scan` | **> 5Hz，無斷線** |
| **scan 數據** | `zsh scripts/ros2w.sh topic echo /scan --once` | ranges 有實際數值，非全 inf |
| **TF 鏈路** | `zsh scripts/ros2w.sh run tf2_tools view_frames` | odom → base_link → front_camera |

### 頻率不穩排查
如果 `/scan` 頻率掉到 < 5Hz 或斷斷續續：

```bash
# 1. 檢查點雲頻寬
zsh scripts/ros2w.sh topic bw /point_cloud2
# 如果 > 5MB/s，需要限制 Go2 driver 的 LiDAR 輸出

# 2. 檢查時間戳延遲
zsh scripts/ros2w.sh topic delay /scan
# 如果延遲 > 100ms，可能是 WebRTC 問題

# 3. 檢查 CPU 是否滿載
tegrastats
# 如果 CPU > 500%，關閉其他節點
```

### Gate A Go/No-Go
- ✅ **GO**: `/scan` 穩定 > 5Hz，TF 正常，延遲 < 100ms
- ❌ **NO-GO**: 頻率不穩或有斷線 → 先解決 WebRTC/資源問題

---

## Gate B: SLAM 建圖 ⏱️ 2-3 小時

**目標**: 只開 SLAM，完成建圖並存檔

### 啟動指令
```bash
# 推薦：用腳本（內建 prelaunch + source + Gate B 參數）
zsh scripts/start_slam_mapping.sh

# 或手動啟動（注意：同一行先 source 再 launch，避免 ros2 not found）
zsh -lc 'source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=false rviz2:=true \
enable_video:=false decode_lidar:=true publish_raw_image:=false \
publish_compressed_image:=false lidar_processing:=false enable_tts:=false'

# 確認節點
zsh scripts/ros2w.sh node list | grep slam
# 應該看到: /slam_toolbox
```

### 建圖流程
1. **手動推著 Go2 慢速走**（< 0.3 m/s）繞行環境
2. **RViz 觀察** `/map` topic，確認地圖持續更新
3. **觀察閉環**：回到起點時，地圖應自動修正對齊

### 監控資源
```bash
# 持續監控（另開 terminal）
tegrastats

# 成功標準:
# - CPU < 300%
# - RAM < 4GB
# - /map 更新 1Hz 穩定
```

### 存圖
```bash
# 完成建圖後存檔
zsh scripts/ros2w.sh service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "{name: /home/jetson/go2_map}"

# 確認檔案產生
ls -lh /home/jetson/go2_map.*
# 應該看到: go2_map.pgm, go2_map.yaml
```

### Gate B Go/No-Go
- ✅ **GO**: 地圖完整、無明顯漂移、已存檔、資源正常
- ❌ **NO-GO**: 建圖過程中卡頓/漂移 → 調整 throttle_scans 或降低移動速度

---

## Gate C: Nav2 + AMCL 定位導航 ⏱️ 3-4 小時

**目標**: 關閉 SLAM，用 AMCL + 存好的地圖跑 Nav2

### 啟動指令
```bash
# 推薦：用 Gate C 腳本（內建 prelaunch + source + map 參數）
MAP_YAML=/home/jetson/go2_map.yaml zsh scripts/start_nav2_localization.sh

# 預設 RVIZ2=false（適合 headless/SSH）；要開 GUI 再加 RVIZ2=true
# RVIZ2=true MAP_YAML=/home/jetson/go2_map.yaml zsh scripts/start_nav2_localization.sh

# 若 /home/jetson/go2_map.yaml 不存在，腳本會自動 fallback：
# /home/jetson/elder_and_dog/src/go2_robot_sdk/maps/phase1.yaml

# 手動等價指令（不開 SLAM、只開 Nav2 + AMCL）
ros2 launch go2_robot_sdk robot.launch.py \
    slam:=false nav2:=true rviz2:=true \
    map:=/home/jetson/go2_map.yaml \
    enable_video:=false minimal_state_topics:=true lidar_point_stride:=8

# 確認節點
ros2 node list | grep -E "amcl|bt_navigator|controller"
```

### Gate C 一行快測（含 10 秒監測）
```bash
GO2_LIDAR_DECODER=wasm LIDAR_POINT_STRIDE=8 zsh scripts/start_nav2_localization.sh & LAUNCH_PID=$!; sleep 25; zsh scripts/set_initial_pose.sh 0.0 0.0 0.0; sleep 2; timeout 10s zsh scripts/ros2w.sh topic hz /point_cloud2 | tee /tmp/hz_pc2_gatec.log; timeout 10s zsh scripts/ros2w.sh topic hz /scan | tee /tmp/hz_scan_gatec.log; timeout 10s zsh scripts/ros2w.sh topic hz /amcl_pose | tee /tmp/hz_amcl_pose_gatec.log; timeout 10s tegrastats | tee /tmp/tegrastats_gatec.log; kill $LAUNCH_PID 2>/dev/null || true; pkill -f "ros2 launch go2_robot_sdk" || true; pkill -f "go2_driver_node" || true
```
- 重點判讀：`/amcl_pose` 有穩定輸出、`/point_cloud2`/`/scan` 維持 >5Hz 即可進入導航目標測試。
- 若看到 `Can't update static costmap layer, no map received`，表示 localization stack 未啟動或 map 參數未正確注入。

### 初始化定位
1. **RViz 點擊 "2D Pose Estimate"**：設定 Go2 的初始位置和方向
2. **觀察雷射掃描**：確認雷射點與地圖牆壁對齊
3. **等待 AMCL 收斂**：粒子雲集中在正確位置

Headless 模式可直接下指令：
```bash
zsh scripts/set_initial_pose.sh 0.0 0.0 0.0
```

### 導航測試（循序漸進）

| 測試 | 操作 | 成功標準 |
|------|------|----------|
| **短距離** | RViz Nav2 Goal，目標 2-3 米 | 成功到達，無偏離路徑 |
| **轉向** | 設定需要轉彎的目標 | 平滑轉向，無原地旋轉 |
| **長距離** | 目標 5-10 米 | 穩定到達，不中斷 |
| **避障** | 路徑上放障礙物 | 偵測並繞行 |

### 監控指令
```bash
# 觀察控制輸出
ros2 topic echo /cmd_vel | grep -E "linear|angular"

# 應該看到:
# linear: x 在 0-0.3 之間變化
# angular: z 在 0-0.5 之間變化
# 不應該有突然的大值跳動
```

### 常見問題排查

**問題 1: AMCL 定位漂移**
```bash
# 檢查 AMCL 粒子數
ros2 param get /amcl max_particles
# 如果不夠，調高到 1000

# 檢查 odom 品質
ros2 topic echo /odom --once
# 移動時 odom 數值應該連續變化
```

**問題 2: 導航失敗/旋轉**
```bash
# 檢查 costmap 更新
ros2 topic hz /local_costmap/costmap
# 應該有 5Hz

# 檢查控制器輸出
ros2 topic echo /cmd_vel
# 如果一直輸出大 angular.z，可能是 RotateToGoal 參數太激進
```

### Gate C Go/No-Go
- ✅ **GO**: 10 次導航 > 8 次成功，無異常旋轉/停滯
- ❌ **NO-GO**: 頻繁失敗 → 調整 footprint、costmap 膨脹、或控制器參數

---

## Gate D: SLAM + Nav2 同時運行（進階）⏱️ 2-3 小時

**警告**: 這個 Gate 資源需求最高，Jetson 8GB 可能吃緊。

### 啟動指令
```bash
# 全開（資源最吃重）
ros2 launch go2_robot_sdk robot.launch.py \
    slam:=true nav2:=true rviz2:=true

# 監控資源（另開 terminal）
tegrastats
```

### 資源上限
| 組件 | CPU | RAM |
|------|-----|-----|
| slam_toolbox | ~100% | ~0.5GB |
| Nav2 | ~200% | ~1.5GB |
| Driver + ROS2 | ~100% | ~0.5GB |
| **總計** | **~400%** | **~2.5GB** |

**Jetson 8GB 上限**: 6 核心 @ 600%，8GB RAM

### Gate D Go/No-Go
- ✅ **GO**: 同時建圖 + 導航，CPU < 500%，無卡頓
- ❌ **NO-GO**: CPU 飽和或 RAM 不足 → 放棄同時運行，改用「先建圖、再導航」分離模式

---

## 階段性目標總結

| Gate | 目標 | 時長 | 通過條件 | 不通過對策 |
|------|------|------|----------|------------|
| **A** | 感測資料流 | 30 分鐘 | `/scan` > 5Hz | 調查 WebRTC/資源 |
| **B** | SLAM 建圖 | 2-3 小時 | 地圖完整存檔 | 降低 throttle_scans |
| **C** | Nav2 導航 | 3-4 小時 | 10 次 > 8 成功 | 調整 AMCL/控制器參數 |
| **D** | 全開壓測 | 2-3 小時 | CPU < 500% | 放棄同時運行 |

---

## 需要特別研究的問題

### 🔴 P0: 關鍵阻礙（必須先解決）

#### 1. WebRTC 連線穩定性
**問題**: WebRTC 延遲抖動會導致 TF timeout、costmap 更新失敗

**驗證方法**:
```bash
ros2 topic delay /scan
ros2 topic echo /scan --field header.stamp
```

**解決方案**:
- 備案：改用 CycloneDDS 有線連線
- 限制點雲頻率（Go2 driver 參數）

#### 2. 點雲數據量控制
**問題**: `/point_cloud2` 數據量過大（10MB/s）

**驗證**:
```bash
ros2 topic bw /point_cloud2  # 目標 < 5MB/s
```

**解決**:
- 已將 `pointcloud_to_laserscan` range_max 從 30m 降到 10m
- 必要時限制點雲頻率

#### 3. Jetson 8GB 資源瓶頸
**問題**: 同時跑 SLAM + Nav2 + Driver 可能超過資源上限

**驗證**: `tegrastats` 持續監控

**解決**:
- 優化參數已寫入 yaml（throttle_scans: 2, max_particles: 1000 等）
- 備案：分離 SLAM 和 Nav2 時序

---

### 🟡 P1: 重要優化（驗證後進行）

#### 4. AMCL vs SLAM Localization 選擇
**建議**: 已選擇 **AMCL** 作為主要定位方案
- 資源占用較低
- 與 Nav2 整合成熟
- slam_toolbox localization 作為備案

#### 5. Controller 調校
**當前**: DWB Local Planner
**評估**: 如果路徑不平滑，可嘗試 Regulated Pure Pursuit

---

## 風險與對策

| 風險 | 等級 | 對策 |
|------|------|------|
| **WebRTC 不穩** | 🔴 高 | 改用 CycloneDDS 有線 |
| **CPU 飽和** | 🔴 高 | 分離 SLAM/Nav2 時序，或降低參數 |
| **TF timeout** | 🟡 中 | 降低 scan/costmap 更新頻率 |
| **記憶體不足** | 🟡 中 | 增加 SWAP，關閉 RViz |
| **定位漂移** | 🟡 中 | 調整 AMCL 參數 |
| **導航失敗** | 🟢 低 | 調整 footprint/costmap |

---

## 下一步行動

1. **立即**: 執行 Gate A（今天）
2. **本週**: 完成 Gate B + C
3. **下週**: 評估是否需要 Gate D，或維持分離模式

**記住**: Gate C 通過（10 次導航 8 次成功）就已經能打贏專題了！Gate D 是加分項，不是必需。

---

## 參考文件

- `go2_robot_sdk/config/nav2_params.yaml`（已優化）
- `go2_robot_sdk/config/mapper_params_online_async.yaml`（已優化）
- `start_go2_wired_webrtc.sh`（已更新）
- Nav2 調優指南: https://docs.nav2.org/tuning/index.html

---

**文件維護者**: 專題團隊  
**最後更新**: 2026-02-24  
**狀態**: 可執行版
