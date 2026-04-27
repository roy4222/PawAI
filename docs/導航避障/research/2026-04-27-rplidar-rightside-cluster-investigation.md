# 2026-04-27 RPLIDAR 右側 0.82m 鬼障礙調查

## 摘要

跑 Phase 10 K1 warmup goal（`goto_relative 0.3m`）時 nav_action_server 拒絕，回 `amcl_lost`。AMCL covariance σ_y 從 0.52 漂大到 0.72，**Go2 完全沒動的情況下 AMCL 發散**。`/state/nav/safety` 顯示 `obstacle_distance=0.819m, zone=slow`。

User 現場確認：**Go2 前方真的沒東西**。

阻塞 K1 / K2 / K4 / K5 / K7 全部 KPI 驗收。**這個問題從 4/25 上機就存在，但未被察覺**（4/25 只驗了 scan rate，沒做角度 / 強度 audit）。

## 證據（30 樣本，5 秒，Go2 完全靜止）

完全不對稱，**Go2 右側被一個 ~85° 寬的物體包住**：

| 角度 | 距離 | intensity | jitter (5s) |
|---:|---:|---:|---:|
| -100° | 7.40m | 4 | 0.179m |
| -90° | 2.72m | 15 | — |
| 0° (正前) | 1.19m | 15 | 0.003m |
| **+15°** | **0.84m** | **15** | — |
| **+20°** | **0.82m** | **15** | **0.002m** |
| **+30°** | **0.84m** | **15** | — |
| **+60°** | **0.99m** | **15** | 0.011m |
| **+90°** | **0.82m** | **15** | **0.003m** |
| **+100°** | **0.82m** | **15** | — |
| +110° | inf | 0 | — |
| -180° | 1.25m (14/30 valid) | 15 | 0.020m |

特徵：

- **intensity 全部 = 15**（max）→ 強反射，**不是雜訊或 ghost**
- **jitter < 3mm** → 跟雷達 rigidly 連動
- 30/30 hit rate → 不是 multipath
- 角度範圍曲線平滑（0.82 → 0.99 → 0.82）→ 是某個曲面物體
- **左右完全不對稱** → 不是 RPLIDAR 自身罩 / motor cap

## 同步發現的平台 latent bug

`lifecycle_manager_localization` 自動 STARTUP **沒完成** — `map_server` 與 `amcl` 都卡在 `inactive` 狀態（雖然 process 都活著、tmux 8 window 都綠）。`lifecycle_manager_navigation` 卻是 active，所以 controller_server / velocity_smoother 都跑起來了，但沒人發現 localization 沒跑。

**手動 fix**：

```bash
ros2 lifecycle set /map_server activate
ros2 lifecycle set /amcl activate
```

兩個都成功 transition 到 active。`/map_server` 開始發 `/map`、`/amcl` 開始接受 initialpose 並發 `/amcl_pose`。

**未做**：root cause 為何自動 STARTUP fail（startup script 30s wait 內 amcl 還沒 ready？race？），先 workaround 通行，留作 5/13 前 todo。

## 三個假設（按可能性）

| H | 描述 | 旋轉 90° 後 0.82m 物體出現位置 |
|---|------|---|
| **H1（最可能）** | RPLIDAR 沒在 Go2 旋轉中心 — 掃到 **Go2 自身揹包 / 拓展模組 / 電池蓋** | **仍在 +15°~+100°**（跟著 Go2 一起轉）|
| H2 | Go2 站太靠近某固定外部家具（沙發 / 桌腳 / 牆角）右側 | **跑到 +105°~+190°**（外部物體角度位移 90°）|
| H3 | RPLIDAR mount yaw 偏 ~70° | 跟 H1 結果一樣，但 fix 方式不同 |

H1 / H3 機率 ≥ 70%。理由：強 intensity + 極穩 + ~85° 連續弧 + [4/25 integration log 第 75 / 212 行明寫 mount xyz yaw 從沒量過](2026-04-25-rplidar-a2m12-integration-log.md)。

## 三天 KPI 卡住的真因

不是 LiDAR 壞、不是 Nav2 壞，是**順序錯了**：

1. **mount 從 4/25 第一天就沒量過** — `z=0.10` 是估測值，xyz yaw 全部都沒量。文件 [`2026-04-25-rplidar-a2m12-integration-log.md`](2026-04-25-rplidar-a2m12-integration-log.md) §3 自己寫「待精確量測 — 5/13 demo 前精量」，但 todo 一直延宕
2. **4/25 桌上驗證 10.4Hz 通過 → 直接上機，沒做 scan angular audit** — 沒人跑過 30 樣本角度分布，所以 +15°~+100° 0.82m 的 85° 連續弧 phantom 從第一天就在資料裡，但被跳過
3. **4/26 上午判定「lethal 是暫態 / map 髒污」 → 整個下午重建地圖** — 但根因是 scan 本身就有 phantom，重建新 map 上面還是會被同一個鬼障礙污染
4. **4/26 下午+晚上做 nav_capability S2 平台抽象（4 actions / 3 services / 70 unit tests / 22+ commits）** — 抽象層 K9/K10 過了，但 K1（最基本「Go2 走 0.5m」）從沒成功一次。底層 LiDAR 物理沒打穩，平台層蓋再多都是空中樓閣
5. **4/26 晚 covariance 0.53 紅當下沒查根因，推到 4/27** — 今天直接重啟 covariance 變 0.72，問題沒走，反而更糟

## 修復路徑

### Step 1（user 動作 + 邏輯診斷）

1. user 用搖桿原地左轉 Go2 90°
2. 重抓 scan 30 樣本，比對 0.82m cluster 是否仍在 +15°~+100°
3. 同時記錄 odom yaw 變化作驗證

### Step 2 — 判定假設

| 觀察 | 結論 | 修復路徑 |
|------|------|---------|
| 0.82m cluster 仍在 +15°~+100° | **H1 / H3**（自身結構或 mount 偏）| Step 3a |
| 0.82m cluster 移到約 +105°~+190° | **H2**（外部家具）| Step 3b |
| 介於兩者 | 自身 + 外部混合 | 兩個 fix 都做 |

### Step 3a — H1/H3 修復

**今天先用 angle blank-out filter 通行 KPI**（不改 mount 物理位置）：

修改 `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`：

加參數 `blank_angle_ranges_deg`（如 `"15:105"` 表示 +15° 到 +105° 全濾掉）。
在 `compute_front_min_distance()` 與訂閱 callback 把這些角度的 ranges 設為 inf。

對應 unit test：`go2_robot_sdk/test/test_reactive_stop_node.py` 加 `test_blank_angle_filter_excludes_blanked_arc`。

並在 `scripts/start_nav_capability_demo_tmux.sh` 對 reactive_stop_node 啟動加：

```bash
-p blank_angle_ranges_deg:='15:105'
```

AMCL 部分（`go2_robot_sdk/config/nav2_params.yaml`）改 `laser_min_range: 1.1`，過濾 1.1m 內所有 beam（自身結構在 0.82m，1.1m 安全 margin）。

**根本解決留作 5/13 demo 前 todo**：精確量 mount xy yaw，更新 static TF。

### Step 3b — H2 修復

不改 code。User 把 Go2 移到客廳開闊處（轉身觀察 1.5m 內無家具），重點 initialpose，等 covariance 收斂直接跑 K1。

### Step 4 — 驗收

1. `ros2 topic echo /state/nav/safety --once` → `zone: clear` 且 `obstacle_distance > 1.5m`
2. AMCL covariance σ_x, σ_y < 0.3m（GREEN）
3. warmup goal `goto_relative 0.3m` → success=true、actual_distance ≈ 0.30m
4. 進 K1：`goto_relative 0.5m × 5` ≥ 4/5 ✅

## 物理 mount 升級（5/13 demo 前長期 fix）

amigo_ros2 README 連結 `pant_tilt_v2-1` 已 link rot（GrabCAD 404）。MakerWorld 找到 8 個 Go2 背架候選（前 3 推薦）：

1. **宇树Go2 背部拓展板** / Unitree Go2 Back Expansion Board
2. **Unitree GO2 Back Plate**
3. **Base Unitree Go 2 - T-Track 30**

短期 demo 替代：**3M VHB 雙面膠把 RPLIDAR 黏在 Go2 原廠背蓋**，水平靠手機水平儀（±3°），線材從側邊綁出。量 RPLIDAR 中心相對 Go2 base_link 的 x/y/z，更新 `scripts/start_nav_capability_demo_tmux.sh:47` static TF。

## 未做工作（不阻塞今日 KPI）

- nav2 `do_beamskip: true` 與 `beam_skip_*` 三閾值 tune
- reactive_stop_node 加 cluster minimum points（單點 outlier reject）
- mount xyz yaw 精量寫進 4/25 integration log，更新 static TF
- 寫 `scripts/scan_health_check.py` 給未來 demo 前 sanity（自動標記異常 cluster）
- root-cause `lifecycle_manager_localization` 自動 STARTUP fail

## 關鍵檔案

| 檔案 | 用途 |
|------|------|
| `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py` | front-arc 偵測、未來加 blank filter |
| `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py` | scan 純邏輯 helpers |
| `go2_robot_sdk/config/nav2_params.yaml` L11-19 | AMCL beamskip / laser_min_range |
| `scripts/start_nav_capability_demo_tmux.sh` L47 | static TF base_link → laser |
| [`docs/導航避障/research/2026-04-25-rplidar-a2m12-integration-log.md`](2026-04-25-rplidar-a2m12-integration-log.md) §3 / §第 75 行 | mount 量測 todo（4/25 起未做）|
| `~/.claude/plans/snug-seeking-cascade.md` | 完整 plan（plan-mode 文件）|

## 來源

- [Slamtec RPLIDAR A2M12 datasheet](https://bucket-download.slamtec.com/f65f8e37026796c56ddd512d33c7d4308d9edf94/LD310_SLAMTEC_rplidar_datasheet_A2M12_v1.0_en.pdf)
- [nav2_amcl 文檔](https://docs.ros.org/en/iron/p/nav2_amcl/) — `do_beamskip` 與 `beam_skip_*`
- [Unitree Go2 Back Expansion Board (MakerWorld)](https://makerworld.com/) — 搜尋「宇树Go2 背部拓展板」
