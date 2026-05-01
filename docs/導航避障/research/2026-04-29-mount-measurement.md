# RPLIDAR Mount 量測（v7 — 4/30 evening 脖子前方背板平台）

依 [`2026-04-27-lidar-dev-roadmap.md`](../lidar開發/2026-04-27-lidar-dev-roadmap.md) Phase 1。
v3-v6（4/24-4/30 上午）皆為背部安裝，v7 起改為**脖子前方 3D 列印背板平台**。

## v7 量測值（4/30 evening）

| 量 | 值 | 量法 |
|----|----:|------|
| **x** | **+0.175 m** | 雷達中心在 Go2 機身正中線上往前 17.5cm；量法：機身全長 75cm（前緣 20cm + 後緣 55cm 從雷達中心起算）→ base_link 在幾何中心（前緣後方 37.5cm）→ 雷達中心 = +37.5−20 = +17.5cm |
| **y** | **0.0 m** | 左右各 20cm 對稱，雷達在中軸上 |
| **z** | **+0.18 m** | 雷達離地 0.50m − Go2 base_link 站立離地 ~0.32m ≈ 0.18m |
| **yaw** | **0 rad** | 雷達 motor 已調整為跟 Go2 正前同向，4/30 evening `scan_health_check.py` 物理驗證通過（物體 0.8m 在 angle=0° 偵測到 0.83m）|
| **pitch / roll** | **±0°（待確認）** | 平面背板水平，建議水平儀復測 |

### v7 物理錨定證據（4/30 evening）

**測試方法**：scan-only stack（TF + sllidar，無 cartographer / AMCL）+ Go2 正前方 0.8m 放物體。

**結果**（`scan_health_check.py --duration 5`，30 樣本/角度）：
```
deg     cnt     median
355.0°  30     0.8278m   ← 物體左邊緣
350.0°  30     0.8305m
345.0°  30     0.8408m
340.0°  30     0.8567m
 10.0°  30     0.8352m
 15.0°  30     0.8516m   ← 物體右邊緣
其餘: 1.0-5.3m（房間結構/牆）
```

**判讀**：物體訊號集中在 angle=0° 兩側 ±15° → laser frame 0° 物理上對齊 base_link +x → yaw=0 正確。PHANTOM PASS、scan 10.45 Hz、TF tf2_echo 顯示 RPY [0,0,0]。

## v6 量測值（4/30 上午，背部安裝，已 superseded）

| 量 | 值 | 量法 |
|----|----:|------|
| **x** | **−0.035 m** | RPLIDAR 中心相對 Go2 質心後方 3.5cm（前緣 33cm + 後緣 26cm，body 中心在 29.5cm，雷達在 26cm 處 → 中心後 3.5cm） |
| **y** | **0.0 m** | 左右各 15cm 對稱，雷達在中軸上 |
| **z** | **0.15 m** | base_link 上方 15cm（用戶 4/30 evening 釐清此值是「背上高度」非離地高度，舊值不精確） |
| **yaw** | **−1.5708 rad（−π/2，−90°）** | 雷達 0° 朝向 Go2 **右方**（−y），需軟體補正 90° |
| **pitch / roll** | **±0°** | 手機水平儀確認（user 4/29 確認「水平了 0度」）|

水平儀照片：_TODO 補貼_（user 之後補進本檔案 `images/2026-04-29-level-photo.jpg`）

## TF 命令（Humble，v7）

```bash
ros2 run tf2_ros static_transform_publisher \
  --x 0.175 --y 0 --z 0.18 --yaw 0 \
  --frame-id base_link --child-frame-id laser
```

v6 命令（已 superseded）：
```bash
# x -0.035 y 0 z 0.15 yaw -1.5708
```

### Yaw 修正歷史

- **v3（4/29 ~16:00）**：yaw=0，假設雷達 0° 對齊 Go2 正前 → 錯誤
- **v4（4/29 ~17:50）**：發現 Foxglove 中 lidar scan 朝向跟 Go2 真實朝向差 90°，雷達 0° 實際朝 Go2 右側 → 改 yaw=−π/2 = −1.5708 rad
- **v5（4/29 ~19:00）**：靠 Foxglove 視覺再次猜測，改 yaw=π → 仍錯（map 看起來反 180°）
- **v6（4/30 ~10:00）✅ 物理錨定定案**：放棄視覺猜測，改用 `scan_health_check.py` 物理錨定法
- 後果：4/29 共試 4 個 yaw 值（0/−π/2/+π/2/π），建 4 張 map（v2-v5）全 deprecated。**4/30 一次定案後不再回頭**

#### v6 物理錨定證據（4/30）

**測試方法**：scan-only stack（TF + sllidar，無 cartographer / AMCL）+ Go2 正前方 0.8m 放物體 → 看 LaserScan 原始 angle bin

**結果**：
```
deg    cnt    median    ...
85.0°  30    0.6540m   ← 物體最近表面
90.0°  30    0.6534m   ← 最近 bin（即 lidar 0° + 90° CCW）
95.0°  30    0.6543m
```
其他角度 1.0–3.0m（房間結構），物體訊號乾淨。

**判讀**：
- 物體物理上在 base_link +x（Go2 正前）
- 在 LaserScan 中於 angle=90° 出現 → laser frame +y = base_link +x
- 即 lidar 的 0° 軸物理上指向 base_link −y（Go2 右方）
- 補正：base_link → laser yaw = **−π/2 = −1.5708 rad**

**驗證 TF**：
```
$ ros2 run tf2_ros tf2_echo base_link laser
- Rotation: in RPY (degree) [0.000, 0.000, -90.000]
```
✅ 與物理推論一致

**為何此方法可信而視覺不可信**（4/29 教訓）：
- 視覺判讀依賴 map 對齊 → 但 map 由錯誤 yaw 建出時也會「內部一致」，看起來合理但實際反向
- 物理錨定只看 raw LaserScan 角度，不依賴 map / AMCL / Foxglove camera convention

`ros2 run tf2_ros static_transform_publisher --help` 確認 Humble 支援 `--yaw` 命名 flag（v2.2 第 15 點要求驗證點）。

## 已更新檔案（5 scripts + build_map.sh echo）

- `scripts/start_nav_capability_demo_tmux.sh:47`
- `scripts/start_nav2_amcl_demo_tmux.sh:50`
- `scripts/start_nav2_demo_tmux.sh:52`
- `scripts/start_lidar_slam_tmux.sh:35`
- `scripts/start_reactive_stop_tmux.sh:36`
- `scripts/build_map.sh:23`（echo 註釋更新）

## 驗收（Phase 1）

- [x] 量值寫進本文件
- [x] `ros2 run tf2_ros tf2_echo base_link laser` 顯示 `[-0.035, 0.000, 0.150]` + RPY `[0, -0, 0]`
- [x] 5 個 scripts + build_map.sh echo 全更新（git diff 一致）
- [ ] 水平儀照片補貼（非 blocker）

## 驗收（Phase 2 — Scan 健康）

跑時間：2026-04-29 16:09，scan-only stack。

- [x] `/scan_rplidar` 平均 10.46 Hz（target ≥ 10.4 Hz）
- [x] PHANTOM 檢查 PASS（無連續弧形 + range fixed + jitter < 5mm + ≥ 67% stable 的弧段）
- [x] CSV 基線存：[`baseline-scans/2026-04-29-baseline.csv`](baseline-scans/2026-04-29-baseline.csv)
- [x] SYMMETRY 警告 15 條（房間不對稱，預期；左側 75-110° ~0.62m 為傢俱/牆面）

### 旋轉復測（user review 要求，4/29 16:30）

為驗 75-110° 緊密弧段是真實牆 vs mount/機身 phantom：

1. Pose A：原地，min @ 90° = 0.622m，tight band 75-110°
2. Go2 順時針旋轉 ~30° 後抓 Pose B：min @ 140-145° = 0.652m，tight band 120-160°

| deg | Pose A | Pose B | Δ |
|----:|--:|--:|--:|
| 90° | 0.622m ← min | 1.446m | +0.82m |
| 145° | 1.520m | 0.652m ← new min | −0.87m |

**結論：真實牆**。緊密弧段跟隨 body frame 旋轉（CW 旋轉 = body frame 角度增大），實際漂移 ~50°（user 報「大概 30°」，可能轉多了或牆面非平行起始朝向）。phantom 應卡死於固定角度，這裡未發生。

CSV：
- [`baseline-scans/2026-04-29-rotation-test-pose-A.csv`](baseline-scans/2026-04-29-rotation-test-pose-A.csv)
- [`baseline-scans/2026-04-29-rotation-test-pose-B-cw30.csv`](baseline-scans/2026-04-29-rotation-test-pose-B-cw30.csv)

### build_map.sh 提示對齊（4/29 同步修正）

舊提示寫「6-window + go2drv + /odom」，但 `start_lidar_slam_tmux.sh` 實際是 5-window pure scan-matching，無 Go2 driver。已修正 `build_map.sh` 第 21-50 行：window 數、無 odom 操作步驟、Foxglove 訂閱清單。

## Phase 3 — SLAM 重建圖（4/29 16:39 完成）

| 項目 | 值 |
|---|---|
| Map ID | `home_living_room_v2` |
| 路徑 | `/home/jetson/maps/home_living_room_v2.{pbstream,pgm,yaml}` |
| 物理尺寸 | 4.35 m × 10.4 m（87 × 208 cells @ 0.05 m/pix）|
| 起點 origin | `[-2.02, -8.42, 0]` |
| 模式 | Cartographer pure scan-matching（`use_odometry=false`，無外部 odom）|
| 走法 | ≤ 0.05 m/s，小範圍核心活動區域（避跳電）|
| 倉內備份 | `docs/導航避障/research/maps/home_living_room_v2.{pgm,yaml,png}` |

### Map QA 限制（**重要 — 載入此 map 的人必讀**）

- ✅ **客廳區可用**：牆面單線、無雙影、角落直角性 OK，AMCL 可定位
- ⚠️ **走廊端 yaw drift**：pure scan-matching 在長走廊（特徵稀疏 + 兩側平行牆）累積誤差，loop closure 沒救起來。底部走廊 yaw 漂移約 5-10°
- ❌ **不作走廊 demo 驗收**：Phase 4/5 K1/K2 / Phase 7 patrol 全部限定客廳區，**不要把 goal 發到走廊底部**
- 走廊區 future work：(a) 重掃 v3 走法強制 loop（客廳→走廊頭→走廊尾→走廊頭→客廳），或 (b) 加 IMU/odom 輔助再掃

### 供電風險（demo blocker）

4/29 16:30-16:45 期間 Jetson 連續斷電 2 次（XL4015 已知問題，[`project_jetson_power_issue.md`](../../../.claude/projects/-home-roy422-newLife-elder-and-dog/memory/project_jetson_power_issue.md)）。Phase 3 為避跳電風險而**選擇縮小掃描範圍**（4.35×10.4m 而非整屋），是策略性決定不是 spec 要求。

**5/13 demo 前必處理**：Jetson 改吃 wall adapter / 加電容 / 換 DC-DC 模組。否則 K1/K2 跑到一半跳電會把問題偽裝成 Nav2 fail。

## 下一步

進 Phase 4 — AMCL 校正（已執行步驟 A）：

- [x] `nav2_params.yaml` AMCL `laser_min_range: 0.20` / `laser_max_range: 8.0`（v3.8 commit）
- [x] `start_nav_capability_demo_tmux.sh` + `start_nav2_amcl_demo_tmux.sh` 預設 map 改 `home_living_room_v2.yaml`
- [ ] 啟 AMCL stack，Foxglove 設 initialpose 在客廳區
- [ ] 觀察 covariance σ_x σ_y < 0.3m
- [ ] 跑 K1（goto_relative 0.5m × 5），≥ 4/5 通過則跳過 Phase 4B（beamskip）

**走廊區嚴禁發 goal**。所有 K1/K2 點都在客廳區範圍。
