# 2026-04-26 — Nav2 動態避障 + 反應式停障 fallback

**接 4/25 P0-D 卡 lethal space**。今日雙管齊下：
- **方案 A（上午）**：先**診斷**再階梯調 costmap 參數，最低目標 0.5m 自主前進。
- **方案 B（下午）**：開發 reactive_stop_node 作 5/13 Demo fallback。

---

## A0：診斷階段（先做、不改參數）

### A0.1 啟動現有 stack（v3.7 參數不動）

```bash
cd ~/elder_and_dog
bash scripts/clean_full_demo.sh
bash scripts/start_nav2_amcl_demo_tmux.sh
# 等 30s lifecycle active
ros2 lifecycle get /amcl
ros2 lifecycle get /map_server
ros2 lifecycle get /controller_server
```

### A0.2 Foxglove 設 initial pose

- 加 panel：3D + Map（顯示 `/global_costmap/costmap`、`/local_costmap/costmap`）+ robot footprint
- Publish 工具：topic `/initialpose`，schema `PoseWithCovarianceStamped`，frame `map`
- 點 Go2 真實位置 + 拖朝向

### A0.3 收集診斷資料

```bash
# 1. AMCL 位置與 covariance
ros2 topic echo /amcl_pose --once

# 2. TF chain
ros2 run tf2_ros tf2_echo map base_link

# 3. nav2 window 觀察 bt_navigator + planner_server 訊息
#    抓「Starting point in lethal space」具體訊息

# 4. 嘗試清 costmap 看是否解除
ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap '{}'
ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap '{}'
sleep 5
python3 scripts/send_relative_goal.py --distance 0.5
```

### A0.4 記錄結果（第一次 run，斷電前）

| 項目 | 觀察值 |
|------|--------|
| AMCL initial position | (-0.756, 0.383)，yaw -174°（朝負 x） |
| AMCL covariance 對角元素 | x: 0.227, y: 0.262（**理想 < 0.05**，偏大但不阻擋規劃）|
| TF map → base_link | (-0.762, 0.402, 0)，與 amcl_pose 一致 ✅ |
| TF map → odom | (-0.772, 0.391, **-0.379**)（z 偏移因 Go2 站立高度 + AMCL 補償）|
| Plan 失敗訊息 | **沒出現！** Plan 一發即成功 |
| 清 costmap | 沒做（不需要，本來就 work）|

### A0.4b 0.5m goal 結果

- 發 5 個相同 goal（preemption 連發）
- bt_navigator log:
  - `Begin navigating from (-0.75, 0.28) to (-1.24, 0.34)`
  - `Reached the goal!` × 多次
  - `Goal succeeded`
- amcl_pose 變化：(-0.75, 0.28) → (-0.87, 0.20)，移動 14cm
- **現場驗證**：用戶確認 Go2 真的走了 ~14cm（與 amcl 數據一致）✅
- Plan 計算時間：< 0.5s
- 無 spin recovery 觸發、無 lethal log

### A0.5 case 判定（第一次 run）

**case = 直接成功**（不是預期的 A/B/C/D）

**為什麼昨天 lethal、今天不 lethal**：
- 昨天 AMCL 估計位置 (1.56, -0.16)
- 今天 AMCL 估計位置 (-0.87, 0.20)
- **不同區域 inflation 包圍程度不同** — (1.56, -0.16) 可能在 RPLIDAR 散射污染或牆角附近，被 inflated obstacle 包住；(-0.87, 0.20) 則相對乾淨
- Fresh start 沒累積 costmap 髒污

**結論**：v3.7 nav2_params **不需修改**，但問題可能在「敏感區域」復現。需要驗證 Go2 走到不同位置是否仍 work。

---

## 中斷：Jetson 跳電重開

第一次 run 完成 0.5m goal 後 Jetson 跳電（XL4015 已知供電不穩問題）。
重開後 SSH 約 ~3 分鐘恢復，環境乾淨，重啟 nav2-amcl stack 順利。

---

## 第二次 run（斷電後）

### 環境
- nav2-amcl stack 重啟順利、5 windows 全活
- amcl + map_server lifecycle active、Go2 driver WebRTC 連通、`/scan_rplidar` 10.9 Hz
- 用戶重設 /initialpose，Go2 真實位置確認

### 0.8m goal 第 1 次（A3-保守 第一輪）

| 項目 | 觀察值 |
|------|--------|
| 起始位置 | (1.19, 0.56)，yaw -174.9° |
| 起始 covariance（x, y）| 0.190, 0.022 |
| 計算 goal | (0.39, 0.49) |
| 終點 amcl_pose | (0.69, 0.43) |
| amcl 計算移動距離 | **0.50m** |
| 現場驗證移動 | **~50cm（用戶確認）** |
| nav2 結果 | `Reached the goal! Goal succeeded` |
| Plan log | `Begin navigating from (1.19, 0.56) to (0.39, 0.49)` 5 次 preemption（連送 5 個 goal）+ 最終 succeeded |
| 撞牆 | 否 |
| lethal / abort | 無 |

### 關鍵發現：昨天 lethal 不是位置固有問題

- 起始位置 (1.19, 0.56) **接近昨天 lethal 出現的 (1.56, -0.16)**（差 ~0.4m）
- 今天該區域 plan 成功，**證明昨天的 lethal 是暫態**：
  - 可能成因：舊 costmap 殘留、RPLIDAR 在不同角度的散射污染、particle filter 漂移、AMCL 收斂前發 goal
- 不是 inflation_radius 0.25 過大、也不是 footprint padding 太大、也不是 map 本身問題
- **結論**：v3.7 nav2_params **不需修改**

### A3-保守 通過項目

- ✅ DWB 能穩定連續控制（0.50m 連續移動）
- ✅ AMCL pose 不會跳，與現場吻合（誤差 ≤ 5cm）
- ✅ Go2 在 0.45-0.70 m/s 設定下能安全停住（無撞牆、無 overshoot）
- ✅ costmap 在 0.8m 距離不會再次 lethal

---

## 待續：第 2 次 0.8m goal repeat

用戶移動 Go2 重設 pose 中，等就緒後做第二次 0.8m goal 確認可重複性。

### A0.5 決策

- **case A** — 清 costmap 後 OK → 髒污問題，把 clear 加到啟動腳本尾端
- **case B** — footprint 在黑格上 → 重設 initial pose（往 free space 挪 30cm），仍不行則 map GIMP 修圖
- **case C** — footprint 在紫格上 → 進 A1 階梯一調 inflation
- **case D** — footprint 在 free 格但仍 plan 失敗 → 看 plan 訊息決定

**今天觀察到：__（填入 case 與根因）__**

---

## A1：階梯式調 inflation（僅 case C 才執行）

### 階梯一（先試）

`go2_robot_sdk/config/nav2_params.yaml`：

| Line | 區塊 | 參數 | 舊值 | 新值 |
|------|------|------|------|------|
| 144 | controller_server.general_goal_checker | xy_goal_tolerance | 0.30 | 0.50 |
| 174 | FollowPath (DWB) | xy_goal_tolerance | 0.25 | 0.50 |
| 224 | local_costmap.obstacle_layer.scan | obstacle_max_range | 1.8 | 1.5 |
| 230 | local_costmap.inflation_layer | inflation_radius | 0.25 | 0.15 |
| 273 | global_costmap.inflation_layer | inflation_radius | 0.22 | 0.15 |

不需 colcon build（純 yaml）。重啟 nav2 window 即可。

### 階梯二（階梯一仍 lethal 才用）

⚠️ inflation 0.10 是 **P0 demo compromise**；正式值應 ≥ 0.18（footprint_padding + safety margin）。
5/13 Demo 後重新校正。

| Line | 參數 | 階梯二值 |
|------|------|---------|
| 224 | obstacle_max_range | 1.0 |
| 230 | local inflation_radius | 0.10 |
| 273 | global inflation_radius | 0.10 |

### 結果

| 階梯 | inflation 值 | 結果 | 備註 |
|------|------------|------|------|
| 一 | 0.15 | TBD | |
| 二 | 0.10 | TBD（若需要）| compromise 標明 |

---

## A2：相對 goal 自主前進

### 工具

- 手動：Foxglove "2D Goal Pose" 工具，點 Go2 前方 0.5m
- 程式：`python3 scripts/send_relative_goal.py --distance 0.5`（讀 /amcl_pose 自動算前方目標）

### 通過標準（A 最低標）

- [ ] 0.5m goal 規劃成功（無 lethal log）
- [ ] cmd_vel.linear.x ≥ 0.45 m/s
- [ ] Go2 抬腳走到目標
- [ ] xy_goal_tolerance 內停下
- [ ] 無 spin recovery 觸發

### 結果

| Run | distance | reach time | recovery | 備註 |
|-----|----------|-----------|---------|------|
| 1 | 0.5m | TBD | yes/no | |
| 2 | 0.5m | TBD | yes/no | |
| 3 | 1.0m | TBD | yes/no | |

---

## A3：動態避障測試（bonus，非硬目標）

僅 A2 通過後嘗試。

### 流程

1. `python3 scripts/send_relative_goal.py --distance 1.5`
2. Go2 啟動移動後，人走入路徑
3. Foxglove 觀察 `/local_costmap/costmap` 是否出現 obstacle、是否 < 2s replan 繞過

### 結果

| Run | 障礙位置 | replan time | 結果 | 備註 |
|-----|---------|------------|------|------|
| 1 | 距離 0.8m | TBD | success/abort/crash | |

---

## B：反應式停障 Node

### 程式碼

- 主程式：`go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`（≈ 130 行）
- 純邏輯：`go2_robot_sdk/go2_robot_sdk/lidar_geometry.py`
- 啟動腳本：`scripts/start_reactive_stop_tmux.sh`（4 windows）
- 測試：`go2_robot_sdk/test/test_reactive_stop_node.py`（17 cases pass）

### 行為

| 條件 | cmd_vel.linear.x |
|------|------------------|
| LiDAR 中斷 > 1s（emergency stop）| 0.0 |
| 前方 ±30° d < 0.6m（danger）| 0.0 |
| 0.6m ≤ d < 1.0m（slow）| 0.45（MIN_X）|
| d ≥ 1.0m（normal）| 0.60 |

加 hysteresis：danger → 非 danger 需連 3 frame 確認才解除（避免抖動）。
warmup：第一筆 cmd_vel = 0 讓 Go2 sport mode handshake 穩定。

### 啟動

```bash
cd ~/elder_and_dog
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
bash scripts/start_reactive_stop_tmux.sh
```

### 驗收 4 場景

| # | 場景 | 期望 cmd_vel | 結果 |
|---|------|------------|------|
| 1 | Go2 站客廳前方 2m 空地 | 0.60 | TBD |
| 2 | 人走到前方 80cm | 0.0 | TBD |
| 3 | 人退到 1.5m | 0.60（3 frame debounce 後）| TBD |
| 4 | 拔 RPLIDAR USB | 0.0（1s 內）| TBD |

### Demo 中關閉 reactive

```bash
ros2 param set /reactive_stop_node enable false
```

---

## 風險摘記

- Risk 1：A0 case B → initial pose 在黑格 → 改 map（5/13 前優先序低）
- Risk 2：階梯二仍 lethal → 多重原因（footprint padding / map / pose）→ 轉 B 主線，週末 deep dive
- Risk 3：reactive 在 Demo 觀眾誤觸 → 用 enable param 切換
- Risk 4：cmd_vel 與 driver stand mode 衝突 → warmup 0.0 已處理

---

## 收工 checklist

- [ ] 方案 B 4 場景驗收通過
- [ ] 方案 A 至少 case 確認 + 階梯一試過
- [ ] `references/project-status.md` 更新進度
- [ ] `docs/導航避障/README.md` 加 Demo 切換說明（Nav2 vs reactive）
- [ ] 影片：Nav2 demo + reactive demo 各一段
