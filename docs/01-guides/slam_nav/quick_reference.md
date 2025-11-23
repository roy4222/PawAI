# 快速參考卡 - SLAM + Nav2（Foxglove / Headless 版）

> 路徑預設 `/home/roy422/ros2_ws/src/elder_and_dog`，全部用 zsh，Foxglove 取代 RViz。

---

## 📌 重點速記

### 頻寬優先
```
❌ 影像面板開著 → /scan 掉到 2~3 Hz → /map 幾乎 0 Hz
✅ 先關影像，只留 /scan /map /TF /RobotModel；/scan > 5 Hz 再掃描
檢查：ros2 topic hz /scan   # 目標 > 5 Hz
      ros2 topic hz /map    # 目標 ~1 Hz
```

### 地圖存檔（純 CLI）
```bash
mkdir -p /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps
ros2 run nav2_map_server map_saver_cli -f /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1
# 產出：phase1.yaml + phase1.pgm
```

### 座標取得（不要硬寫）
在 Foxglove 3D 用 Publish Point/Goal 取座標，確定在白色開放區再寫入 YAML。

---

## 🎯 Phase 1 流程（建圖 + 存圖）
```bash
# T1 驅動
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh start_go2_simple.sh    # 等 "Video frame received"

# T2 /scan 監控
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh   # 沒檔先 colcon build
export CONN_TYPE=webrtc ROBOT_IP=192.168.12.1
ros2 topic hz /scan        # 目標 >5 Hz

# T3 SLAM + Nav2 + Foxglove
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc ROBOT_IP=192.168.12.1
ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=false foxglove:=true

# Foxglove (Chrome)
# https://studio.foxglove.dev/ → ws://<Shared IP>:8765 (例 192.168.64.2:8765)
# 3D 勾 /map /scan TF RobotModel，影像面板關掉保頻寬

# T4 掃描建圖
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc ROBOT_IP=192.168.12.1
zsh TEST.sh forward; sleep 2
zsh TEST.sh left;    sleep 2
zsh TEST.sh forward; sleep 2
zsh TEST.sh right

# 存圖
ros2 run nav2_map_server map_saver_cli -f /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1
```

---

## 🎯 Phase 2 流程（載圖 + 導航）
```bash
# 載入 phase1 地圖，僅跑 Nav2
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc ROBOT_IP=192.168.12.1
ros2 launch go2_robot_sdk robot.launch.py \
  slam:=false nav2:=true rviz2:=false foxglove:=true \
  map:=/home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1.yaml

# Foxglove：
# 1) 3D Fixed frame=map，訂閱 /map OccupancyGrid
# 2) Publish Pose 設初始位姿
# 3) Publish Navigation Goal 點白色區域送目標
# 或腳本：python3 scripts/nav2_goal_autotest.py --distance 0.5（先設初始位姿）
```

---

## 📊 合格速查

### Phase 1
```
□ /scan > 5 Hz，/map ~1 Hz
□ 地圖存檔成功 (phase1.yaml/pgm)
□ TF map→odom→base_link 完整
□ 系統穩定 15 分鐘不崩
```

### Phase 2
```
□ 目標導航成功（手動或腳本）
□ Costmap 顯示正常，避障有效
□ 5 點導航成功率高（自定標準）
```

---

## 🔧 常用指令

| 任務 | 指令 |
|------|------|
| 環境準備 | `source /opt/ros/humble/setup.zsh && cd /home/roy422/ros2_ws/src/elder_and_dog && source install/setup.zsh && export CONN_TYPE=webrtc ROBOT_IP=192.168.12.1` |
| 啟動驅動 | `zsh start_go2_simple.sh` |
| SLAM+Nav2+Foxglove | `ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=false foxglove:=true` |
| 載圖 Nav2 | `ros2 launch go2_robot_sdk robot.launch.py slam:=false nav2:=true rviz2:=false foxglove:=true map:=.../phase1.yaml` |
| 檢查 /scan | `ros2 topic hz /scan` |
| 檢查 /map | `ros2 topic hz /map` |
| 檢查 TF | `ros2 run tf2_tools view_frames` |
| 儲存地圖 | `ros2 run nav2_map_server map_saver_cli -f .../maps/phase1` |
| 移動狗 | `zsh TEST.sh forward/backward/left/right/sit/stand` |
| 巡邏 | `ros2 run search_logic simple_patrol_node --ros-args -p auto_start:=true` |

---

## 🚨 5 大陷阱

| # | 陷阱 | 症狀 | 秒殺方案 |
|---|------|------|--------|
| 1 | 頻寬耗盡 | /scan < 3 Hz | 關掉 Foxglove 影像面板 |
| 2 | /map 為 0 | SLAM 未出圖 | 確認 slam:=true，移動掃描，/scan >5 Hz |
| 3 | 存圖失敗 | map_saver timeout | 先讓 /map 有頻率再存 |
| 4 | 導航不動 | 沒初始位姿 | Foxglove Publish Pose 設 /map 初始姿態 |
| 5 | 座標撞牆 | 目標貼牆 | 選白色開放區，避免黑色障礙 |

---

## 📁 重要路徑

| 檔案 | 用途 | 路徑 |
|------|------|------|
| SLAM 參數 | 迴圈閉合靈敏度 | `go2_robot_sdk/config/mapper_params_online_async.yaml` |
| Nav2 參數 | 速度/避障 | `go2_robot_sdk/config/nav2_params.yaml` |
| 巡邏點 | 巡邏路徑 | `src/search_logic/config/patrol_params.yaml` |
| 地圖存檔 | 建圖結果 | `src/go2_robot_sdk/maps/` |
| Phase1 指南 | 詳細步驟 | `docs/01-guides/slam_nav/phase1_execution_guide_v2.md` |
| Phase2 指南 | 詳細步驟 | `docs/01-guides/slam_nav/phase2_execution_guide.md` |

---

## 💡 訣竅

建圖：慢走、轉大角、經過牆角、回到起點檢查閉合。  
導航：先短距離、目標在開放區、卡住就重送或 Ctrl+C。  
除錯：重啟驅動/launch → 檢查 /scan Hz → 關高頻顯示 → 看終端紅字。  

**遇到問題先看頻寬與 /scan，90% 的問題都因為影像面板吃頻寬。** 🎯
