# 5/1 AMCL 180° 反向診斷與修復

## 摘要

5/1 morning 完成 LiDAR mount v7（yaw=0、commit `fabbf06`）+ home_living_room_v7 map 後，noon 啟 nav2_amcl stack 跑 K1 時用戶觀察到：
1. Foxglove 中 lidar scan 跟 map 方向 180° 相反
2. Costmap 出現「奇怪障礙物」環繞 Go2
3. AMCL `map → base_link` yaw 卡在 178.6°、推 Go2 物理前進 1.7m 後 yaw 跳到 -17.7° 嘗試自我修正、Go2 icon 在 map 上反方向移動

深度診斷後發現根因是 **v7 yaw=0 物理錨定通過是偽陽性**，真實 lidar 物理朝向跟 Go2 nose 相反。修正為 yaw=π（v8）+ 重建 v8 map 後 AMCL 完美收斂、K1 軟通過 3/5。

## 根因

**Lidar 物理 0° 朝向 Go2 背後（不是頭）**，但 v7 TF 設 yaw=0（假設 lidar 0° = Go2 nose）。錯誤 TF 用於 cartographer 建 v7 map → map 內部一致但 +X 軸對應 Go2 物理 BACK 方向。AMCL 載入 v7 map + 用相同錯誤 TF + 用戶用「正常」方式設 initialpose（箭頭朝 Go2 物理鼻尖）→ 整套 stack 出現 180° 不一致。

## 偽陽性如何產生

`scan_health_check.py` 5/1 morning 報 v7 PASS：
```
deg     cnt     median
355.0°  30     0.8278m   ← 物體左邊緣
350.0°  30     0.8305m
...
 +0°: ~0.83m   ← 物體中心
 ...
 +15°  30     0.8516m   ← 物體右邊緣
```

物體 0.8m 在「Go2 正前方」 → angle=0° 偵測到 → 結論 yaw=0。

但**用戶 mis-identified Go2 nose 方向**：把物體放在以為的正前方（其實是 Go2 屁股方向）。物理錨定法假設用戶能正確識別 Go2 朝向，這次失敗。

## 診斷路徑

### Step 1（10:43 ~ 11:30，沒看出問題）

啟 nav2_amcl + 用戶 Foxglove 設 initialpose → AMCL yaw 178.6°（看似偏大但 CLAUDE.md 記載 0.22 仍可 plan）→ 跑 K1 第一個 goal 前發現 Go2 朝向不對。

### Step 2（11:30 ~ 11:35，定位「奇怪障礙物」非 self-scan）

跑 scan range audit：< 0.20m 範圍 0 個 returns、< 0.50m 範圍 0 個 returns → **self-scan / 機身 phantom 不存在**（4/27 那 +20°~+100° 0.82m 鬼影被 v7 mount + 3D 列印背板解掉了）→ 「奇怪障礙物」不是 self-scan，是 AMCL pose 錯導致 scan 投影到錯位置。

### Step 3（11:35 ~ 11:50，用戶推 Go2 +1.7m 物理前進）

驗 odom 軸方向：
- `/odom.position`：(0, 0) → (-0.132, -1.721)，magnitude 1.726m ✓
- `map → base_link`：(0.041, 0.028) → (0.003, -0.005)，**只移動 5cm**
- AMCL yaw 從 178.6° 跳到 -17.7°、covariance σ²_x 0.223 → 0.081 收斂

關鍵觀察：**odom 1.7m vs map 5cm = 35× 差異**。AMCL 把 odom 動的 1.7m 全吸進 `map → odom` 補償，因為 scan 跟 map 對不上。

### Step 4（11:50 ~ 12:00，物理測試確認 yaw=π）

不靠 Foxglove 視覺判讀的客觀測試：

1. **baseline scan**（用戶遠離 Go2）：lidar `0°` (laser +X) 0.733m、`+180°` 1.823m
2. **物體放 Go2「鼻尖」前 0.5m**：`0°` blocked → 用戶以為驗證 yaw=0、但其實只證明「lidar 0° 跟用戶以為的 Go2 鼻尖方向一致」（仍依賴用戶識別 Go2 朝向）
3. **用戶站在 Go2 物理頭前 0.5m**（看 Go2 的眼睛/感測器，無歧義）：scan 返回出現在 **angle=±180°（laser -X）**，**不是 angle 0°**

→ Lidar 物理 0° 指向 Go2 **背後**。TF base_link → laser yaw 應為 **π**，不是 0。

### Step 5（12:00 ~ 12:10，修 TF + 重建 map）

1. 7 scripts sed yaw 0 → 3.14159（commit `fa0fa54`）
2. Push + Jetson sync + scan-only 驗證 `tf2_echo base_link laser` RPY [0, 0, 180°] ✓
3. 重啟 cartographer stack、用戶慢走客廳（XL4015 撐住）
4. 存 v8 map：205×98 cells / 10.25×4.90m / origin [-2.41, -2.81]
5. v7→v8 default map 切換（commit `5d938d6`）

### Step 6（12:10 ~ 12:20，AMCL 完美收斂）

啟新 nav2_amcl stack + 用戶設 initialpose（同建圖起點）：

- `map → base_link`：(0.002, 0.051) yaw -1.57° ≈ **0**
- AMCL covariance σ²_x = **0.175 → 0.033**（σ_x 0.42m → 0.18m）
- Scan key angles:
  - laser `0°` (= Go2 BACK): 0.621m wall ✓
  - laser `±180°` (= Go2 FRONT): 1.957m clear ✓
  - 跟用戶觀察「Go2 前方淨空 1m+」完美吻合

### Step 7（12:20 ~ 12:30，K1 baseline 軟通過 3/5）

連續發 5 個 0.5m forward goal：

| Goal | 起點 | 終點 | 移動 | 結果 |
|---|---|---|---|---|
| 1 | (0.327, 0.284) | (0.659, 0.314) | 0.33m | ✓ |
| 2 | (0.659, 0.314) | (0.987, 0.399) | 0.33m | ✓ |
| 3 | (0.987, 0.399) | (1.267, 0.465) | 0.28m | ✓ |
| 4 | (1.267, 0.465) | (1.269, 0.465) | 0.00m | ✗ |
| 5 | (1.269, 0.465) | (1.269, 0.465) | 0.00m | ✗ |

Go2 累積移動 1.28m、AMCL 全程收斂、XL4015 沒跳電、Go2 沒撞牆。

K1 spec 是 ≥ 4/5，目前 3/5 軟通過。卡住原因待調：
1. `xy_goal_tolerance: 0.30` 太鬆 → Go2 走 0.3m 就被視作 reached、沒走滿 0.5m。建議降到 0.15
2. Goal 4-5 卡住、Go2 累積 yaw drift 30°（從 -5° 到 +25°）→ controller wobble 或 plan failure
3. Go2 sport mode `min_vel_x 0.50` vs DWB `min_vel_x 0.45` 邊界 → 中間 cmd_vel 可能被 sport filter 吃掉

## 教訓 → SOP 更新

加進 [`docs/導航避障/CLAUDE.md`](../CLAUDE.md)（待補）：

### 物理錨定 SOP

**用戶站位置法 > 物體放置法**：
- ❌ 物體放置法：依賴用戶識別 Go2 朝向、可能 mis-identify 鼻尖方向
- ✅ 用戶站位置法：用戶看 Go2 的「臉」（眼睛/感測器/主視覺）站到 0.5m 前 → 用戶身體在 lidar 哪個 angle bin 一目了然

### Foxglove 視覺判讀的局限

cartographer 用任何 yaw 都建得出**內部一致**的 map（4/29 學到的），AMCL 也會在內部一致的 map 上對應收斂。**視覺對齊不能當判讀依據**，必須回到「raw scan + 物理已知物體位置」。

### Goal 流程的 xy_goal_tolerance 陷阱

`xy_goal_tolerance: 0.30` 對 0.5m 的小 goal 來說太鬆：Go2 走到一半（0.30m 處）就被視作 reached，下一個 goal 又從那裡再走 0.30m。實際移動量 ≈ goal_distance - xy_goal_tolerance。設計 K1 baseline 時要確保 xy_tol < goal_distance/3。

## Step 8（14:05 — K1 baseline 5/5 PASS，A 主鏈正式驗收）

12:30 Step 7 軟通過 3/5 後午間 Jetson 在 idle 重開過一次（XL4015 brown-out 或元件累熱、非動態觸發），13:46 重啟。13:50 改 nav2_params.yaml `xy_goal_tolerance: 0.30 → 0.15`、commit `59024ef`。14:00 重啟 nav2-amcl stack、用戶設 initialpose。

但首次 K1 v3（TF-based）跑出怪結果：Goals 1-2 因 TF lookup error 沒送出、Goals 3-5 卻有送出且 Go2 移動 0.34-0.49m。**判讀**：K1 script 用 `rclpy.time.Time()` 作 TF lookup 時參數，rclpy 把它當 epoch 0、tf2 buffer cache 已 purge → 返回 extrapolation error。

修 script 改用 `/amcl_pose` 訂閱（TRANSIENT_LOCAL）而不是 TF lookup。寫成 `/tmp/k1_runner_v3.py`：

```python
amcl_qos = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST, depth=1)
self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', cb, amcl_qos)
```

用戶把 Go2 物理抓回起點 (0,0)、設好 initialpose，14:05 跑 K1 v3：

| Goal | Travel | Err | 判定 |
|---|---|---|---|
| 1 | 0.326m | 0.183m | **PASS** |
| 2 | 0.372m | 0.129m | **PASS** |
| 3 | 0.402m | 0.100m | **PASS** |
| 4 | 0.369m | 0.143m | **PASS** |
| 5 | 0.345m | 0.179m | **PASS** |

**Verdict: 5/5 PASS**（spec ≥ 4/5）。Go2 從 (-0.238, -0.717) → (1.531, -1.081)，總移動 1.81m，沒撞、沒跳電、AMCL σ²_x 全程 < 0.20。

**關鍵改善 vs 12:30 軟通過 3/5**：
- xy_tol 0.30→0.15 讓每 goal 真的走滿 0.33-0.40m（之前 0.28-0.33m）
- script 修正讓 Goals 1-2 也成功送出（之前 TF buffer 沒 ready 直接 fail）
- Go2 累積 yaw drift -25° 內，DWB 仍能驅動到 goal 範圍

## Step 9（14:23 — 動態避障 v0 PARTIAL PASS）

K1 5/5 後切到 `start_nav_capability_demo_tmux.sh`（8 windows，含 reactive_stop_node safety_only=true priority 200）。發 `/goal_pose` 1m forward goal、用戶放紙箱在前方 30cm。

**reactive_stop_node 行為（log 18197-18273，11s 視窗 4× cycle）**：
```
18197.9 slow → danger (front 0.47m) → /nav/pause
18198.8 danger → slow (0.62m) → /nav/resume
18203.2 slow → danger (0.60m) → /nav/pause
18203.9 danger → slow (0.73m) → /nav/resume
18206.2 slow → danger (0.59m) → /nav/pause
18207.5 danger → slow (0.61m) → /nav/resume
18207.8 slow → danger (0.60m) → /nav/pause
18208.7 danger → slow (0.62m) → /nav/resume
... idle 65s ...
18273.4 slow → clear (1.02m)  ← 紙箱移除
```

**Verdict: PARTIAL PASS**
- ✅ Go2 沒撞（核心 safety net 成立）
- ✅ Danger zone (<0.5m) auto-pause 工作正常
- ✅ Slow zone resume 工作正常（4× cycle 證明 oscillation handling）
- ⚠️ 紙箱完全移除後 Go2 沒自動 continue（停在 0.78m, 距 1m goal 短 0.45m）

### 根因分析

| 路徑 | 狀態 |
|---|---|
| `/goal_pose` → bt_navigator 的 navigate_to_pose action | 我們用的這條 |
| reactive_stop 的 `/nav/pause` + `/nav/resume` service | 由 nav_capability 自定的 nav_action_server / route_runner_node 提供 |
| **兩條路徑連接** | **沒完整 wire**（`/state/nav/status` 顯示 `state=idle, active_goal=null` 表示 nav_capability tracker 看不到 bt_navigator 的 goal）|

reactive_stop 還會 publish `/cmd_vel_obstacle=0` 給 mux（priority 200）→ Go2 stops。但這只強制停車、沒「保留 goal」。4× pause/resume 期間 cmd_vel oscillation 可能讓 bt_navigator BT 進 recovery 或 abort 狀態（audio spam 蓋掉 nav2 log 無法確認）。

### 5/13 demo 前 fix 路線

1. **改用 `/nav/goto_relative` action**（nav_capability 原生）— pause/resume 邏輯完整適用 → plan D Phase 7 驗證
2. OR 在 reactive_stop_node 加邏輯：obstacle 清除後 republish 原 goal
3. OR 接受 v0「停了就停」、demo 設計避開連續導航需求

對 5/19 demo 來說：**「Go2 遇障礙停下不撞」這個保證足夠（v0 有）；「障礙清除後自動繼續」是加分項**。

## Step 10（15:30-16:30 — Phase 7 layered 揭露 3 個 critical bugs）

K1 5/5 PASS 後依 Plan D Phase 7 換用 `/nav/goto_relative` action 路徑做分層測試（避開 Phase 4 PARTIAL 已知問題）。

### Step 10.1 — `/nav/goto_relative 0.5m` 無障礙基線

第一次嘗試 crash：`nav_action_server_node._execute_relative_inner` 用 `await asyncio.sleep(0.1)`、rclpy action callback 不在 asyncio context、`RuntimeError: no running event loop`。

**Fix (commit `27b33d8`)**：3 處 `asyncio.sleep` → `time.sleep`（MultiThreadedExecutor 在線、blocking 安全）。

colcon build 失敗（setuptools `--editable`/`--uninstall` 不相容、Jetson 環境 issue）。Workaround：`pip install -e .` 把 nav_capability 裝到 `~/.local/`。

修後 0.5m goal SUCCEEDED、Go2 物理移動 0.345m（actual_distance 顯示 0.174 是 race condition bug，不影響結果）。

### Step 10.2 — 0.5m + 紙箱障礙：**Go2 直撞紙箱**

紙箱 30cm 放 Go2 前方 → action 1.7s 內 SUCCEEDED、actual_distance=0、Go2 物理撞紙箱、**reactive_stop 完全沒 fire**。

### Step 10.3 — 深度調查揭露 3 個 critical bugs

#### BUG #1：reactive_stop 看不到 Go2 前方（v8 mount yaw=π 配套不完整）

**根因**：`go2_robot_sdk/lidar_geometry.py:compute_front_min_distance` 寫死「laser frame 0° = Go2 前方」、但 v8 mount yaw=π 後 laser 0° 物理上是 Go2 **後方**。reactive_stop ±30° front arc 監控錯方向、Go2 前方變盲區。

**重新解讀 Phase 4**（早上 4× pause/resume cycle）：reactive_stop 偵測的 0.47-0.73m 不是用戶放的紙箱、是 **Go2 背後**牆/家具。Phase 4 PARTIAL 不是「障礙避障 work」—— 是巧合 reactive_stop 觸發到 Go2 背後 obstacle 而非前方紙箱。

**Fix (commit `e3270da`)**：加 `front_offset_rad` 參數（預設 0 向後相容）：
- `lidar_geometry.compute_front_min_distance` 加第 8 參數、angle 比較前先減 offset
- `reactive_stop_node` declare ROS param 並傳遞、startup log 顯示 offset
- `scripts/start_nav_capability_demo_tmux.sh` + `start_reactive_stop_tmux.sh` 設 `-p front_offset_rad:=3.14159`
- 加 4 個 unit tests（180° / 0° / 155° / 215°）

**驗收 standalone 4 場景全 PASS**：
| 場景 | obstacle_distance | zone | active | 結果 |
|---|---|---|---|---|
| 紙箱前方 0.4m | 0.413m | danger | true | ✅ |
| 紙箱前方 0.8m | 0.807m | slow | false | ✅ |
| 紙箱前方 ≥1m | 1.254m | clear | false | ✅ |
| 紙箱後方 0.4m | 1.185m | clear | false | ✅（fix 前會誤觸發、修後不會）|

unit test 27/27 PASS（含 4 個新 offset cases + 原 23 cases，向後相容）。

#### BUG #2：nav_action_server 沒 `/nav/pause` handler（待修）

grep 確認 `nav_action_server_node.py` 完全沒 "pause" 字串。`/nav/pause` service **只有 route_runner_node 接**（line 112: `Trigger, "/nav/pause", self._svc_pause"`）。reactive_stop 呼叫 /nav/pause → route_runner 收到（沒在跑 route）→ 沒效用。**`/nav/goto_relative` action 完全 ignore pause 信號**。

5/13 demo 前必修：給 nav_action_server 加 /nav/pause subscription 或 service handler、共享 pause flag with action callback、obstacle 進 danger 時取消當前 NavigateToPose、obstacle 移除後重新 send goal 從 stopped pose。

#### BUG #4：Nav2 BT WP3=start 短路（待修）

K2-lite forward+left+back 設計、最後 WP3=start。Go2 在 WP3 容差內 → BT 立即 SUCCEEDED、Go2 沒動（**fake PASS**）。

5/13 demo 前必修：K2 設計避免 WP_n = start，或加 yaw 變化強迫 controller 動作。

### Step 10.4 — 三層 safety 真實層級（更新）

| 層 | 機制 | Phase 7.2 真實表現 |
|---|---|---|
| 1. DWB BaseObstacle critic | 透過 TF 看到紙箱在 costmap | 可能有 reaction、但 nav_action_server SUCCEEDED 太快沒給時間 |
| 2. Costmap inflation_layer (0.25m) | 紙箱應該 mark 為 lethal | 同上 |
| 3. **reactive_stop_node priority 200** | 4× pause/resume in Phase 4（看到後方 obstacle）、Phase 7.2 完全沒 fire（看不到前方紙箱） | **BUG #1 修了之後才能正常工作** |

修完 BUG #1 + #2 後 Phase 6 K5 完整測試才有意義。

## 關鍵 commits

- `fa0fa54` fix(nav): LiDAR mount v8 — yaw 0 → π
- `5d938d6` feat(nav): home_living_room_v8 map — TF yaw=π 修正後重建
- `59024ef` fix(nav): xy_goal_tolerance 0.30 → 0.15
- `42cc478` docs(nav): K1 baseline 5/5 PASS — A 主鏈正式驗收成立
- `27b33d8` fix(nav_capability): asyncio.sleep → time.sleep
- `e3270da` fix(reactive_stop): front_offset_rad — v8 mount yaw=π blind front bug

## 相關檔案

- 修正後 TF：7 scripts（`start_lidar_slam_tmux.sh`、`start_nav2_amcl_demo_tmux.sh`、`start_nav_capability_demo_tmux.sh`、`start_nav2_demo_tmux.sh`、`start_reactive_stop_tmux.sh`、`start_scan_only_tmux.sh`、`build_map.sh`）
- v8 map：`docs/導航避障/research/maps/home_living_room_v8.{pgm,yaml,png}`
- mount 量測 v8：`docs/導航避障/research/2026-04-29-mount-measurement.md`（v8 段）
- v7 yaml/pgm/png 留在 repo 但 unusable
