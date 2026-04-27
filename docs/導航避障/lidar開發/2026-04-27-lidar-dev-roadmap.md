# LiDAR 支架印好後 — 完整開發路徑（7 階段，v2.2）

## Context

User 已選好 mount STL（自決），本 plan 從**「支架印好、Go2 已裝上 RPLIDAR」**開始，到「自動巡邏 + reactive 安全層 demo 級可用」結束。

User 對 v1 提了 7 點技術修正，v2 全部納入；對 v2 又提了 5 點實作級修正並 read-only 驗證為 v2.1；對 v2.1 又提了 6 點 wording / 驗收細節為 **v2.2（本版）**。

### 修正歷程

**v2 修正**（v1 → v2）：
1. K8 mux test 不進實機 stack（會撞 Go2，已 4/26 22:30 驗證）
2. Scan health 用 scan-only stack，不啟 Go2 driver / Nav2 / reactive
3. AMCL beamskip 必須連 `laser_model_type: likelihood_field_prob` 一起改
4. Route JSON schema 用真實的 `id/task/pose/tolerance/timeout_sec`，沒 `named_pose`
5. **不承諾**「動態繞障人擋路自動繞」demo（DWB 小空間會抖卡）
6. Lifecycle race 先重現再決定要不要修
7. Scan 對稱性差只是 warning，不能當 fail gate（房間本來就不對稱）

**v2.1 修正**（v2 → v2.1，read-only 驗證後生效）：
8. static TF 5 個 scripts 都要加 `--yaw` flag（v2 寫 6 個，read-only 確認 `build_map.sh` 只有 echo 註釋，TF 是它呼叫的 `start_lidar_slam_tmux.sh` 提供 → 實際 5 個）
9. PHANTOM fail gate 不再要求 `intensity ≥ 12`，改用「連續弧形 + range 幾乎固定 + jitter 低 + 多輪穩定」
10. K1/K2 CLI 改用真實 flags（`send_relative_goal.py --help` 確認只支援 `--distance` / `--yaw-offset` / `--max-speed`）
11. `laser_max_range: 8.0` 標 `indoor practical cap`，不寫成 datasheet 結論
12. Map backup 改安全 loop（避免 brace expansion 在缺檔時失效）
13. Brain 整合移到 bonus，**不列導航主驗收項**

**v2.2 修正**（v2.1 → v2.2，wording / 驗收細節）：
14. 標題「6 scripts 同步」改「5 scripts + build_map.sh echo」
15. `static_transform_publisher --yaw` 開工前先 `--help` 驗證 Humble 是否支援
16. PHANTOM stable 條件量化：30 樣本中 ≥ 20 樣本（≥ 67%）出現同一角度段
17. beamskip 與 likelihood_field_prob 改用「應與一起切換測」（不寫成「必須」）
18. K1/K2 驗收以 action result 為準（success / failed / cancelled），sleep 只是視覺間隔
19. Phase 3 重建 map 改保守表述（「保險做法」而非「舊 map 不能用」）

User 主時程：**先做 PawAI Brain MVS → 5/8 deadline → 5/9 起本 plan 開工**。Phase 1-2 可在裝完雷達當天順手做（不依賴 brain 進度）。

## 7 階段路徑總覽

```
1. Mount 量測 + TF 更新（5 scripts + build_map.sh echo）  ← 30 分鐘（裝完當天必做）
2. Scan 健康驗證（scan-only stack）         ← 1 小時
3. SLAM 重建圖                              ← 1.5 小時
4. AMCL 校正（laser range 先 → beamskip 後） ← 1.5 小時
5. Nav2 K1/K2                              ← 1 小時
6. 動態安全 K5/K7（reactive + pause + emergency）← 1.5 小時
7. 自動巡邏 K4 + Brain                      ← 2-4 小時
```

**最低限度 demo（5/13 必到）**：1 + 2 + 3 + 4 + 5
**目標 demo**：上述 + 6 + 7
**不在範圍**：「人擋路自動繞」、進階導航（5/13 後）

---

## Phase 1 — Mount 量測 + TF 更新（30 分鐘）

裝完雷達**當天必做**。沒這步後面全錯。

### 1.1 — 量四個值（毫米級 / 度級）

| 量 | 定義 | 量法 |
|----|------|------|
| **x** | RPLIDAR 中心相對 Go2 質心前後（前 +、後 −）| 鋼尺 |
| **y** | RPLIDAR 中心相對 Go2 質心左右（左 +、右 −）| 鋼尺 |
| **z** | base_link 上方雷達中心高度 | 鋼尺 |
| **yaw** | 雷達 0° 朝向相對 Go2 正前的偏差 | 雷達上方畫朝前標誌線、從正上方眼睛對齊機身中軸 |

### 1.2 — 用手機水平儀驗 ±3°（拍照存證）

### 1.3 — 同步更新 5 個 scripts 的 static_transform_publisher

read-only 驗證後確認真正含 `static_transform_publisher` 命令的是這 5 個（`build_map.sh` 只有 echo 註釋，TF 由它 delegate 的 `start_lidar_slam_tmux.sh` 提供）：

- `scripts/start_nav_capability_demo_tmux.sh`
- `scripts/start_nav2_amcl_demo_tmux.sh`
- `scripts/start_nav2_demo_tmux.sh`
- `scripts/start_lidar_slam_tmux.sh`
- `scripts/start_reactive_stop_tmux.sh`

**目前 5 個 scripts 都長這樣**（沒 `--yaw`）：
```bash
ros2 run tf2_ros static_transform_publisher \
  --x 0 --y 0 --z 0.10 \
  --frame-id base_link --child-frame-id laser
```

**改成 4 軸**（**新增 --yaw 參數**）：
```bash
ros2 run tf2_ros static_transform_publisher \
  --x <measured_x> --y <measured_y> --z <measured_z> \
  --yaw <measured_yaw_rad> \
  --frame-id base_link --child-frame-id laser
```

⚠️ **開工前先驗證 Humble 是否支援 `--yaw` 命名 flag**：

```bash
ros2 run tf2_ros static_transform_publisher --help
```

若不支援命名 flag（舊版本只接 positional），改用 positional 7 引數格式（`x y z yaw pitch roll frame_id child_frame_id`）：

```bash
ros2 run tf2_ros static_transform_publisher \
  <x> <y> <z> <yaw_rad> 0 0 base_link laser
```

附加：`scripts/build_map.sh` 第 23 行 echo「z=0.10」也要更新成新值（純文字提示）。

**建議重構**（5/13 後 follow-up）：抽到 `scripts/lib/static_tf.sh` 或讀 env var，避免漂移。**5/13 前直接 5 處改完即可**。

### 1.4 — 驗收
- [ ] 量值寫進 `docs/導航避障/research/2026-05-XX-mount-measurement.md`
- [ ] 水平儀照片附在文件
- [ ] `ros2 run tf2_ros tf2_echo base_link laser` 顯示新值（含 yaw）
- [ ] 5 個 scripts 都加 `--yaw` flag，git diff 一致
- [ ] `build_map.sh` echo 文字更新

---

## Phase 2 — Scan 健康驗證（scan-only stack，1 小時）

**這是必經關卡**。Scan 不乾淨 → SLAM 把 phantom 寫進 map → 永久污染。

### 2.1 — 建立 scan-only stack（5 分鐘）

**只啟三件事**：static TF + sllidar + scan_health_check.py。
**不啟**：Go2 driver / Nav2 / reactive_stop / mux / teleop。

新增 `scripts/start_scan_only_tmux.sh`（3-window）：
```
window 0: tf       — static_transform_publisher base_link → laser
window 1: sllidar  — sllidar_ros2 sllidar_node（同既有設定）
window 2: monitor  — 手動跑 scan_health_check.py / topic hz / topic echo
```

理由：scan health 階段不需要 Go2 動，也不需要 nav 任何 plugin。剝離後不會被 reactive_stop 干擾、不會被 mux 灌 cmd_vel、不會被 nav 攪。

### 2.2 — 寫 `scripts/scan_health_check.py`（30 分鐘）

純 Python + rclpy，規格：

```
1. 訂閱 /scan_rplidar 連續抓 30 樣本（5 秒）
2. 列印 360° 每 5° 一筆 (deg, range, intensity, jitter)
3. PHANTOM ALERT（fail gate）— 必須四項全中才 FAIL:
   a. 連續 ≥ 10° 範圍角度
   b. 該範圍內 range 幾乎固定（max-min < 50mm）
   c. 該範圍內 jitter < 5mm（30 樣本內 30 次 reading 的標準差或 max-min）
   d. 30 樣本中 ≥ 20 樣本（≥ 67%）出現同一角度段 phantom = stable
   intensity 只當輔助欄位列印，不作為必要條件
   理由：RPLIDAR intensity 受材質與角度影響大，不可靠
4. SYMMETRY WARN（warning only，不 fail）:
   左右 ±θ range 差異 > 50% 列印 WARN
   理由：房間本身不對稱很正常
5. 輸出 CSV /tmp/scan_health.csv 給 Foxglove / 試算表
```

**Permanent script**（commit 進 repo）。未來每次 demo 前先跑。

### 2.3 — 跑驗證
```bash
ssh jetson-nano
bash scripts/start_scan_only_tmux.sh
sleep 8
python3 scripts/scan_health_check.py --duration 5 --csv /tmp/scan.csv
```

### 2.4 — 解讀

| 結果 | 行動 |
|------|------|
| 無 PHANTOM ALERT | ✅ 進 Phase 3 |
| 有 PHANTOM ALERT（連續弧形）| 拆 mount 修：檢查線材是否纏繞、雷達是否被自身遮擋 |
| 只有 SYMMETRY WARN | 接受（房間不對稱），記錄到 mount-measurement.md |

### 2.5 — 驗收
- [ ] scripts/scan_health_check.py 通過 PHANTOM 檢查
- [ ] /scan_rplidar 10.4 Hz 穩定
- [ ] 基線 CSV 存進 `docs/導航避障/research/baseline-scans/`

---

## Phase 3 — SLAM 重建圖（1.5 小時）

新 mount 會改變 laser frame 與 scan 投影品質。即使只是 z 高度改、yaw 很小，舊 map 也可能因 TF 偏差或 scan 投影差異產生定位漂移。**為避免舊 map 污染與 TF 偏差，demo 前重建 map**（保險做法）。

```bash
# 1. 備份舊 map（安全 loop，避免 brace expansion 在缺檔時靜默失敗）
BACKUP_TS=$(date +%Y%m%d-%H%M%S)
for ext in yaml pgm pbstream; do
  src="/home/jetson/maps/home_living_room.${ext}"
  if [[ -f "$src" ]]; then
    cp "$src" "${src}.bak.${BACKUP_TS}"
    echo "backed up: $src"
  else
    echo "warn: $src not found, skipped"
  fi
done

# 2. 啟 cartographer 5-window
bash scripts/build_map.sh home_living_room_v2

# 3. 遙控 Go2 慢速繞客廳
# 規則：≤ 0.15 m/s、含閉環（回原點）、避免速轉、避免動態障礙物入鏡

# 4. 三步驟存圖
ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory "{trajectory_id: 0}"
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState \
  "{filename: '/home/jetson/maps/home_living_room_v2.pbstream', include_unfinished_submaps: true}"
ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/home_living_room_v2 \
  --ros-args -p map_subscribe_transient_local:=true
```

### 驗收
- [ ] 新 map yaml + pgm + pbstream 三檔
- [ ] RViz / Foxglove 看 map：牆壁清晰、無虛影、家具邊界對齊
- [ ] 玻璃處（4/25 log §354 已知問題）若有穿透虛影，**用 GIMP 在 .pgm 手動 mask**

---

## Phase 4 — AMCL 校正（laser range 先 → beamskip 後）

**分兩步測**，因為 beamskip 改錯比沒改更糟。

### 4.1 — 步驟 A：先只改 laser range（10 分鐘 + 跑 K1 驗證）

`go2_robot_sdk/config/nav2_params.yaml`：

```yaml
amcl:
  ros__parameters:
    laser_min_range: 0.20    # 改自 -1.0（過濾 A2M12 < 0.20m 雜訊）
    laser_max_range: 8.0     # indoor practical cap, not sensor max
                             # （A2M12 名義 12m，但室內 8m 已足夠且過濾遠距散射）
    # laser_model_type / do_beamskip 暫不動
```

跑一次 K1（goto_relative 0.5m × 5）測 baseline。如果 ≥ 4/5 通過 = 不需要 beamskip，**收工**。

### 4.2 — 步驟 B：beamskip 升級（如果步驟 A 不夠）

`likelihood_field_prob` 是 [Nav2 AMCL 官方文檔](https://docs.nav2.org/configuration/packages/configuring-amcl.html)中**描述包含 beamskip feature 的 likelihood field 變體**。雖然官方文件不一定寫成「必須搭配」，但社群實證 `do_beamskip` 對 `likelihood_field`（非 prob 變體）的效果不一致 — 若要測 beamskip，**應與 `do_beamskip` 一起切換測**比較穩。

```yaml
amcl:
  ros__parameters:
    laser_model_type: "likelihood_field_prob"  # 改自 "likelihood_field"
    do_beamskip: true
    beam_skip_distance: 0.5
    beam_skip_threshold: 0.3       # 30% beam mismatch 內可忽略
    beam_skip_error_threshold: 0.9
```

兩個值**一起改**，跑一次 K1，比 baseline 看是否有改善。如果不改善甚至更糟 = revert，留 likelihood_field。

### 4.3 — Lifecycle race（先重現，再決定）

4/27 遇 `lifecycle_manager_localization` 自動 STARTUP 沒完成，amcl + map_server 卡 inactive，要手動 `ros2 lifecycle set ... activate`。

**這次不預設要修**。先做：
1. 連續啟動 stack 5 次，每次 sleep 50s 後檢查 amcl/map_server lifecycle 狀態
2. **如果 5/5 都 active** → 4/27 是偶發 race，加診斷 log 即可
3. **如果 5 次中 ≥ 2 次 inactive** → 真實 race，再寫 retry 邏輯

不要花時間修一個無法穩定重現的問題。

### 驗收
- [ ] 步驟 A laser range 改完 commit
- [ ] 步驟 A K1 baseline 結果記錄
- [ ] （條件式）步驟 B beamskip + model_type 一起 commit
- [ ] Lifecycle race 5 次重複測試結果記錄

---

## Phase 5 — Nav2 K1/K2（1 小時）

**開工前先核對 CLI**（v2.1 read-only 確認 `send_relative_goal.py` 真實 flags 是 `--distance` / `--yaw-offset` / `--max-speed`，沒 `--rate` `--repeat`）：

```bash
python3 scripts/send_relative_goal.py --help
# 預期：--distance / --yaw-offset / --max-speed
# 如果跟以下命令不符，先看 --help 用真實 flags
```

```bash
ssh jetson-nano
bash scripts/start_nav_capability_demo_tmux.sh
sleep 50
# Foxglove 設 initialpose

# K1（每次發單一 goal，看 action result 是 success / failed / cancelled）
for i in 1 2 3 4 5; do
  python3 scripts/send_relative_goal.py --distance 0.5
  # sleep 是 demo 手動流程的視覺間隔，不是判定條件
  sleep 5
done

# K2
for i in 1 2 3 4 5; do
  python3 scripts/send_relative_goal.py --distance 0.8
  sleep 8
done
```

**驗收以 action result 為準，不以 sleep 結束為準**：

`send_relative_goal.py` 內部用 action client，會印出 `result.success` 或 `result.message`（例如 `amcl_lost` / `obstacle_blocked` / `timeout` / `success`）。**5 次中 ≥ 4 次 result.success=true 才算通過 K1**。sleep 只是手動流程的視覺間隔，K3/K6 等 P1 KPI 用 timeout 判定是另一回事。

### 驗收
- [ ] AMCL covariance σ_x σ_y < 0.3m（GREEN）
- [ ] K1 ≥ 4/5（依 action result.success）✅
- [ ] K2 ≥ 4/5（依 action result.success）✅
- [ ] 首次 plan 不再 lethal fail（4/26 暫態問題消失）

---

## Phase 6 — 動態安全 K5/K7（1.5 小時）

reactive_stop_node + obstacle layer 已完整。實機驗證。

### 6.1 — K5 ⭐ Pause/Resume × 3
```bash
ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \
  "{route_id: 'k4_test'}" &
sleep 5
# 人擋路 → reactive_stop 發 0 → /nav/pause 觸發 → state=paused
sleep 5
# 走開 → < 5s 內續行
```

### 6.2 — K7 ⭐ Emergency lock × 3
```bash
ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \
  "{route_id: 'k4_test'}" &
sleep 5
python3 nav_capability/scripts/emergency_stop.py engage
# < 1s 停下
sleep 3
python3 nav_capability/scripts/emergency_stop.py release
```

### 6.3 — **不承諾的事**
- ❌ **「人擋路自動繞過去」demo** — DWB 小空間 replanning 會抖、卡、停。可以 **bonus take 試錄**，但**不寫進 5/13 demo script**
- ❌ K8 mux fake_publisher 整合測試 — **WSL-only**，不能跑在實機 stack（4/26 22:30 撞過：fake_publisher 把 0.30 m/s 真灌進 mux→driver→Go2 衝出）

### 驗收
- [ ] K5 × 3 全續行 < 5s ✅
- [ ] K7 × 3 全 < 1s 停 ✅
- [ ] **承諾的 demo 三件**：reactive stop / pause-resume / emergency stop（**不含**動態繞障）

---

## Phase 7 — 自動巡邏 K4 + Brain（2-4 小時）

### 7.1 — Route JSON schema（**用真實 schema**）

`nav_capability/lib/route_validator.py` 實際要的 schema（已從 `test_route_validator.py` 確認）：

```json
{
  "schema_version": 1,
  "route_id": "patrol",
  "frame_id": "map",
  "map_id": "home_living_room_v2",
  "created_at": "2026-05-12T00:00:00+08:00",
  "initial_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
  "waypoints": [
    {
      "id": "wp1",
      "task": "tts",
      "pose": {"x": 1.20, "y": 0.50, "yaw": 0.0},
      "tolerance": 0.30,
      "timeout_sec": 30,
      "tts_text": "我到客廳了"
    },
    {
      "id": "wp2",
      "task": "wait",
      "pose": {"x": 2.50, "y": 1.00, "yaw": 1.57},
      "tolerance": 0.30,
      "timeout_sec": 30,
      "wait_sec": 3
    },
    {
      "id": "wp3",
      "task": "normal",
      "pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
      "tolerance": 0.30,
      "timeout_sec": 30
    }
  ]
}
```

**沒有 `named_pose` / `task_type` 欄位**。pose 直接寫 x/y/yaw（`map` frame）。

`task` 三個合法值：`normal` / `wait` / `tts`（從 `test_waypoint_unknown_task_fails` 推得）。
- `task: tts` 必有 `tts_text`
- `task: wait` 必有 `wait_sec`
- `task: normal` 不需

如果以後要支援「named_pose 引用」（route 寫 `{"named_pose": "alpha"}` 自動展開）= **新 feature**，要：
1. 改 `route_validator.py` 接受 named_pose 欄位
2. 加 named_pose → pose 展開邏輯
3. 加 unit test
4. **schema_version 升 2**

**5/13 前不做**，先用真實 x/y/yaw 寫 route。

### 7.2 — 流程

```bash
# (1) 用 log_pose 錄當前位置（fallback：自己量 map 座標）
# log_pose 把 amcl_pose 寫進 named_poses/main.json，但 route JSON 還是要手動寫
ros2 action send_goal /log_pose go2_interfaces/action/LogPose \
  "{name: 'living_room', log_target: 'named_poses'}"

# (2) 從 named_poses/main.json 撈 x/y/yaw 抄進 patrol.json
cat ~/elder_and_dog/runtime/nav_capability/named_poses/main.json
# 手寫 patrol.json 三個 wp 的 pose（不能引用 named_pose name）

# (3) K4 run_route × 3
for i in 1 2 3; do
  ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \
    "{route_id: 'patrol', loop: false}"
  sleep 30
done
```

### 7.3 — 導航主驗收（必過）
- [ ] patrol.json 通過 route_validator
- [ ] 3 點 patrol 跑 3 圈無 fail
- [ ] TTS 到點銜接自然
- [ ] `/event/nav/waypoint_reached` 有發出（topic echo 看得到）

### 7.4 — Brain 整合（**Bonus，不列導航主驗收**）

導航主驗收只需保證 `/event/nav/waypoint_reached` 有發。Brain 整合屬於 PawAI Brain MVS 範圍（另一份 plan），這裡只記為 bonus 路徑：

- PawAI Brain 訂 `/event/nav/waypoint_reached`
- 巡邏中 face_recognized → 暫停 → greeting → 續行
- 演示「**主動巡邏 + 互動**」（守護 30% 核心）

⚠️ 這段如沒做完不影響本 plan 驗收。Brain 整合的失敗不算導航失敗。

---

## 5/13 Demo 場景設計（兩條路徑）

### Path α — 全 Phase 通過
1. Go2 站客廳 → Brain 喊「準備巡邏」
2. patrol route：客廳 → 廚房 → 玄關 → 回客廳
3. 中途 user 擋路 → Go2 reactive stop + pause + TTS「請借過」 → 走開續行（**這是 K5，不是動態繞障**）
4. 巡邏中認到 user 臉 → 暫停 + greeting
5. user「停下來」→ emergency_stop engage（demo Safety Layer 攔截）

### Path β — 只到 Phase 5（K1/K2 通過、K5/K7 未過）
1. Go2 站桌上 → PawAI Brain 互動 demo（人臉 / 對話 / 手勢，不依賴移動）
2. 影片秀「Phase 6 動態安全」（5/12 前家裡錄好，**只錄 reactive stop / pause-resume，不錄繞障**）
3. 評審問為何不現場跑 → 答「Safety Layer 拒絕未驗收的物理移動」

---

## 並行任務（5/8 brain MVS 期間）

裝完雷達當天**順手做**：
1. **Phase 1 量測 + 5 個 scripts TF 更新**（30 分鐘）
2. **Phase 2 寫 scan_health_check.py**（純 Python，1 小時）
3. **Phase 2 跑健康驗證**（30 分鐘）
4. **Clone OpenMind/OM1-ros2-sdk 找 STL**（5 分鐘 — 萬一有寶藏）：
   ```bash
   git clone https://github.com/OpenMind/OM1-ros2-sdk /tmp/om1
   find /tmp/om1 -iname '*.stl' -o -iname '*.step' -o -iname '*.iges'
   ```

5/9 起 Phase 3-7（一次跑完約 1 整天）。

---

## 不要做的事（避免 scope 失控）

- ❌ Phase 4 之前不動 nav2_params.yaml（會干擾 Phase 3 建圖）
- ❌ Phase 2 之前不重建 map（scan 不乾淨建出來也是廢的）
- ❌ Phase 7 進階導航（frontier / MPPI / multi-floor）不塞 5/13 前
- ❌ K8 mux fake_publisher 不進實機 stack（**WSL-only**）
- ❌ 不重做 reactive_stop_node 17 cases unit test 已綠的部分
- ❌ Lifecycle race 不預先寫修法（先重現再決定）
- ❌ 不承諾「人擋路自動繞過去」demo（只承諾 reactive stop / pause-resume / emergency）
- ❌ Route JSON 不用 `named_pose` 欄位（schema 不支援）

---

## 歷史踩坑彙總（4/8 ~ 4/27）

之後開發**先看這節**，避免重蹈覆轍。每個坑都是從實機 / 文件 / 會議挖出來的真實事件。

### A. 雷達物理層

| # | 坑 | 教訓 |
|---|----|------|
| A1 | mount xyz yaw 從 4/25 上機就沒量過（z=0.10 是估測）→ 4/27 挖出 +15°~+100° 0.82m 鬼障礙 | 上機**第一天**就要量 mount + 跑 angular probe，不要只看 frequency 通過就 OK |
| A2 | 魔鬼氈固定 → Go2 走路時雷達晃，AMCL covariance 跳動 | 必須用螺絲 + 印件固定，且 fix 方向不能在掃描平面 |
| A3 | 雷達裝太低 → 掃到 Go2 自身揹包 / 拓展模組 / 電池 | 雷達中心要在 base_link 上方 ≥ 30cm（Go2 自身最高點 + 5cm margin），但 < 50cm（重心）|
| A4 | 線材繞過雷達側邊掃描平面 → 永久鬼點 | 線從**正後方往下走**，不繞雷達一圈 |
| A5 | 沒水平 → 一邊掃地板、一邊掃桌面 / 牆上 | 手機水平儀 ±3° 內，pitch / roll 都要驗 |

### B. RPLIDAR 驅動 / scan 品質

| # | 坑 | 教訓 |
|---|----|------|
| B1 | 4/25 桌上驗證 10.4Hz 通過 → 直接上機，沒做 scan angular audit | scan 健康檢查（30 樣本 angular probe + intensity + jitter）必須上機後再跑一次 |
| B2 | RPLIDAR intensity 受材質角度影響大，不能當絕對 fail gate | intensity 只當輔助欄位，fail gate 用「連續弧形 + range 固定 + jitter 低 + 多輪穩定」 |
| B3 | 窗戶玻璃**雷射穿透** → map 變胖 / 散射污染 costmap | 物理現象不可解，玻璃處在 .pgm 手動 mask 即可（4/25 log §354）|
| B4 | `angle_compensate=true` 對 mount yaw 偏移的雷達會放大誤差 | 先量 mount yaw 量準，再決定要不要開 angle_compensate |
| B5 | A2M12 名義 12m，但室內遠距讀數受散射影響 | `laser_max_range` 設 8m（indoor practical cap），不用 datasheet 上限 |

### C. AMCL / Nav2 設定

| # | 坑 | 教訓 |
|---|----|------|
| C1 | AMCL `laser_min_range=-1.0` + `laser_max_range=100.0` → 壞 beam 全進 likelihood field | 設成 0.20 / 8.0，過濾雜訊 |
| C2 | `do_beamskip=true` 對 `likelihood_field`（非 prob 變體）效果不穩定 | 兩個一起切到 `likelihood_field_prob` + `do_beamskip: true` 比較穩 |
| C3 | `lifecycle_manager_localization` 自動 STARTUP 偶發 fail（amcl/map_server 卡 inactive） | 不要預設要修；先連續啟動 5 次測重現率，5/5 都過 = 偶發，加 log 即可 |
| C4 | `inflation_radius=0.25` 把 RPLIDAR 散射 + 窗外點 inflate 包住 → costmap 鬼點 | 4/26 判定為暫態，不盲改，等實機跑出新 lethal 才動（4/25 log §473）|
| C5 | costmap `obstacle_max_range=1.8m` (local) / `2.5m` (global) → 已 v3.7 calibration | 不要動，已避免遠距散射污染（4/26 確認）|

### D. Go2 driver / 動作執行

| # | 坑 | 教訓 |
|---|----|------|
| D1 | Go2 sport mode `cmd_vel` 門檻 **MIN_X = 0.50 m/s** — DWB `min_vel_x` 必須 ≥ 0.45 否則拒抬腳 | 4/25 實機 calibration 確認，nav2_params.yaml 已調 |
| D2 | Go2 driver `_publish_transform` env 開關：`GO2_PUBLISH_ODOM_TF=0` 給 cartographer 用、`=1` 給 AMCL 用 | 建圖階段跟 demo 階段切換時要記得改 |
| D3 | Go2 OTA 自動更新 → 連外網就被更新韌體，曾造成 debug 失敗 | Demo 當天用 Ethernet 直連（192.168.123.161），不要連外網 |
| D4 | Go2 重開機後 WebRTC ICE 可能 FROZEN → FAILED，第二個 candidate 才成功 | 等 10s+，不要急著 retry |
| D5 | 多 driver instance 殘留：`killall python3` 只殺 parent | `pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud; pkill -9 joy_node` 逐一清 |

### E. tmux / mux / cmd_vel 路由

| # | 坑 | 教訓 |
|---|----|------|
| E1 | `reactive_stop_node` 在 mux 模式 (priority 200) 必須 `safety_only=true`，否則 clear zone 0.60 m/s 永遠 shadow nav | 4/26 撞過，已寫進 `start_nav_capability_demo_tmux.sh` |
| E2 | K8 `test_mux_priority.py` 不能在 full stack 跑 — FakePublisher 真灌 0.30 m/s 進 mux → driver → Go2 衝出 | 4/26 22:30 撞過，**永久 WSL-only** |
| E3 | tmux 不繼承 `LD_LIBRARY_PATH`，啟動腳本必須 export | Whisper / ctranslate2 需要這個 |
| E4 | bash-specific 腳本用 `bash -c`，不要假設 zsh 相容 | Jetson 用 zsh，混 source 會破壞環境 |

### F. cartographer / SLAM / map

| # | 坑 | 教訓 |
|---|----|------|
| F1 | slam_toolbox 在 ARM64 + Humble + RPLIDAR 永久棄用（Mapper FATAL ERROR known bug）| 用 cartographer，不要試 slam_toolbox |
| F2 | cartographer pure-localization 模式 v3.6 試過失敗（pose 漂移）| 改用 AMCL + Go2 odom 架構（v3.7）|
| F3 | 重新建圖前**先備份**：`home_living_room.{yaml,pgm,pbstream}.bak.<timestamp>` | 用 for loop 不要用 brace expansion（缺檔會靜默失敗）|
| F4 | 建圖時 Go2 速度 ≤ 0.15 m/s，含閉環回原點，避免動態障礙物入鏡 | 否則 cartographer 對位失敗 |

### G. ROS2 / 工具鏈

| # | 坑 | 教訓 |
|---|----|------|
| G1 | `/goal_pose` QoS 是 BEST_EFFORT（bt_navigator 訂閱端）| publisher 必須匹配，不要 `ros2 topic pub --once`（4/26 踩過）|
| G2 | `ros2 daemon` 偶爾 sync 慢，topic hz 第一次抓不到很正常 | 等 5-10s 重試 |
| G3 | `setup.bash` 與 `setup.zsh` 不可混用 | Jetson 用 zsh 統一 |
| G4 | zsh 的 glob 會炸掉陣列參數（如 `'["whisper_local"]'`）| 加引號或 `setopt nonomatch` |
| G5 | `clean_all.sh` 的 `set -euo pipefail` + `grep` 空結果會中斷 | 尾端 `\|\| true` |

### H. 架構決策回顧

| # | 決策 / 修法 | 為何 |
|---|-----------|------|
| H1 | 4/1 判「Go2 內建 LiDAR Full SLAM 永久關閉」→ 4/24 RPLIDAR A2M12 上機後**翻案** | 業界 SLAM 門檻 7Hz，Go2 內建 4-7Hz 不夠，A2M12 10.4Hz 過了 |
| H2 | 4/3 D435 避障**全部停用**（鏡頭角度限制 + Jetson 記憶體）| 改外接 RPLIDAR |
| H3 | nav_capability S2 平台抽象（4 actions / 3 services / 70 unit tests）優先於 K1 實機驗收 | 4/27 反思：抽象層完整但物理層 phantom 沒解 = 空中樓閣，**順序錯了** |
| H4 | brain MVS 5/8 → LiDAR 整合 5/9 起 | 物理時間（印表機）不可控；brain 你掌控 → 並行 |

### I. 通用教訓（Linus 風格反思）

1. **物理優先於抽象**：spec 寫得多漂亮、unit test 多綠，物理一個 phantom 就讓 K1 永遠不過
2. **第一性原理：raw scan 健康是底線**，AMCL / costmap / DWB 全部建立在它上面，污染了上面全爛
3. **暫態 vs 結構性問題分清楚**：4/26 lethal 是暫態（map 髒）；4/27 phantom 是結構性（mount）。**結構性問題要立刻停下來查根因，不要繞**
4. **「不要修一個無法穩定重現的 bug」**：lifecycle race / 韌體 OTA 風險 / WebRTC ICE FROZEN — 加 log 觀察，不要預先寫複雜 retry
5. **跨 5 個檔案的設定（如 static TF）就是技術債**：5/13 前手動同步 OK，5/13 後抽到 lib

---

## 關鍵檔案

| 檔案 | Phase | 動作 |
|------|:----:|------|
| 5 個 scripts（見 Phase 1.3）| 1 | static TF xyz yaw 同步更新（加 `--yaw` flag）|
| `scripts/build_map.sh` L23 | 1 | echo 文字「z=0.10」更新成新 z 值（純註釋）|
| `docs/導航避障/research/2026-05-XX-mount-measurement.md`（新建）| 1 | 量值 + 水平儀照片 |
| `scripts/start_scan_only_tmux.sh`（新建）| 2 | 3-window scan-only stack |
| `scripts/scan_health_check.py`（新建）| 2 | 30 樣本 angular probe + PHANTOM fail gate（不要求 intensity）|
| `docs/導航避障/research/baseline-scans/`（新建目錄）| 2 | 健康基線 CSV |
| `/home/jetson/maps/home_living_room_v2.{yaml,pgm,pbstream}`（新建）| 3 | 重建 map |
| `go2_robot_sdk/config/nav2_params.yaml` | 4 | laser_min/max_range（必）；laser_model_type + do_beamskip（條件式）|
| `~/elder_and_dog/runtime/nav_capability/named_poses/main.json` | 7 | 巡邏點（log_pose 寫入）|
| `~/elder_and_dog/runtime/nav_capability/routes/patrol.json`（新建）| 7 | patrol route，schema 對齊 route_validator（id/task/pose/tolerance/timeout_sec）|

---

## End-to-end 驗證（5/12 全部完成後）

```bash
# 1. raw scan 健康（scan-only stack）
bash scripts/start_scan_only_tmux.sh
python3 scripts/scan_health_check.py --duration 10
# 預期：無 PHANTOM ALERT / 10.4 Hz

# 2. AMCL 健康（full stack 啟動 + initialpose）
bash scripts/start_nav_capability_demo_tmux.sh
sleep 50
python3 scripts/peek_amcl_covariance.py
# 預期：σ_x σ_y < 0.3, σ_yaw < 10°

# 3. 全 KPI 一次跑（v2.1：真實 CLI，無 --rate / --repeat）
# K1 / K2
for i in 1 2 3 4 5; do python3 scripts/send_relative_goal.py --distance 0.5; sleep 5; done
for i in 1 2 3 4 5; do python3 scripts/send_relative_goal.py --distance 0.8; sleep 8; done
# K4
for i in 1 2 3; do ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute "{route_id: 'patrol'}"; sleep 30; done
# K5（人擋路 — reactive + pause-resume）
# K7（emergency_stop.py engage）

# 4. /event/nav/waypoint_reached 事件確認（導航主驗收）
ros2 topic echo /event/nav/waypoint_reached &
ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute "{route_id: 'patrol'}"
# 預期：每到一個 wp 發一筆 event

# 5. (Bonus，不算主驗收) Brain 整合（如 MVS 5/8 done）
ros2 topic echo /tts &
# Brain 應在 face_recognized 時觸發 greeting，路徑 reached 時 TTS
```

---

## 來源

- [Nav2 AMCL 官方文檔（laser_model_type + do_beamskip）](https://docs.nav2.org/configuration/packages/configuring-amcl.html)
- [jizhang-cmu/autonomy_stack_go2](https://github.com/jizhang-cmu/autonomy_stack_go2)
- [arpa-byte/Go2_where_r_u](https://github.com/arpa-byte/Go2_where_r_u)
- [Kodo-Robotics/go2-autonomous-patrol](https://github.com/Kodo-Robotics/go2-autonomous-patrol)
- [Slamtec RPLIDAR A2M12 datasheet](https://bucket-download.slamtec.com/f65f8e37026796c56ddd512d33c7d4308d9edf94/LD310_SLAMTEC_rplidar_datasheet_A2M12_v1.0_en.pdf)
- 既有 schema：`nav_capability/nav_capability/lib/route_validator.py` + `nav_capability/test/test_route_validator.py`
- 既有 mount log：`docs/導航避障/research/2026-04-25-rplidar-a2m12-integration-log.md` §75 / §212
- 既有 phantom 調查：`docs/導航避障/research/2026-04-27-rplidar-rightside-cluster-investigation.md`
- 既有 nav2 動態避障 log：`docs/導航避障/research/2026-04-26-nav2-dynamic-obstacle-log.md`
- nav_capability S2 spec / plan：`docs/superpowers/specs/2026-04-26-nav-capability-s2-design.md` / `docs/superpowers/plans/2026-04-26-nav-capability-s2.md`
- P0 nav 避障 spec / plan：`docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md` / `docs/superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md`
