# Nav Root-Cause Burndown — 5/11–5/12 家裡排除法

> **Status**: ready-to-execute
> **Date**: 2026-05-10 night
> **Owner**: Roy
> **目的**：5/12 晚移交學校前，把導航失敗的可能原因排除到**只剩「家裡空間不足」**這一個假設。
> **不做**：完整 Nav 調優、新功能、跑 1m 大距離測試（家裡空間不夠，做了沒意義）。

---

## 1. 為什麼要做這個

家裡光達、D435 都是好的，但移動性過低。問題是：**到底哪一層壞了？** 不可能到學校才開始 debug。

到學校前要得到結論：

> LiDAR、D435、TF、odom、Nav2、cmd_vel mux、reactive_stop、AMCL、`goto_relative 0.3-0.5m` 都各自驗過。
> 若導航還是不穩，最可能原因就是**家裡場地太小 / 反光 / 轉向空間不足**。
> 到學校後只驗證大空間是否解除限制。

---

## 2. 七大可能性逐項排除

每項都要填結論（pass/fail），fail 一定要在 5/12 晚前找到根因或 demo 降級。

### B1. LiDAR 健康（RPLIDAR A2M12）

**測試指令**（家裡 Jetson）：
```bash
# 開 sllidar
ros2 launch sllidar_ros2 sllidar_a2m12_launch.py

# 另開 terminal 看頻率
ros2 topic hz /scan_rplidar              # 預期 8-10 Hz
ros2 topic echo /scan_rplidar --once \
  | python3 -c "import sys,yaml; d=yaml.safe_load(sys.stdin); \
  r=d['ranges']; print('len:', len(r), 'min:', min([x for x in r if x>0]), \
  'front (idx 0):', r[0])"
```

**Pass criteria**：
- [ ] `/scan_rplidar` 穩定 8-10 Hz
- [ ] ranges 長度合理（A2M12 約 720 點）
- [ ] 前方紙箱（1m 處放）→ ranges[idx_front] ≈ 1.0m，不是 0 或 inf

**Fail 動作**：檢查 USB / 電源 / udev rule。記錄。

---

### B2. D435 健康

**測試指令**（注意專案用 double namespace `/camera/camera/...`）：
```bash
ros2 launch realsense2_camera rs_launch.py \
  enable_color:=true enable_depth:=true align_depth.enable:=true \
  pointcloud.enable:=false
ros2 topic hz /camera/camera/color/image_raw
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
```

**Pass criteria**：
- [ ] color 30 Hz、aligned depth 30 Hz
- [ ] Foxglove Image panel 看 aligned_depth 有資料、不是全黑或全白
- [ ] 移除 / 放回障礙物，depth 圖明顯改變

**Fail 動作**：檢查 USB 3.0 線、電源、launch args（必須 `enable_depth:=true align_depth.enable:=true`）；確認 namespace 是 `/camera/camera/`（不是 `/camera/realsense2_camera/`）。

---

### B3. TF / 前方方向

家裡實機高風險：之前曾 `front_offset_rad:=3.14159` 修方向。

**測試指令**：
```bash
# 1. 看 TF tree
ros2 run tf2_tools view_frames
# → 確認 base_link → laser、base_link → camera_link 都有

# 2. Foxglove 開 3D panel + /scan_rplidar，前方放紙箱
# 觀察：紙箱在 Go2 機身正前方？還是後方/左右顛倒？
```

**Pass criteria**：
- [ ] TF tree 完整（無斷裂）
- [ ] 紙箱出現在 Go2 正前方 ±0.3m 範圍
- [ ] `front_offset_rad` 設定有效（檢查 sllidar launch 參數）

**Fail 動作**：
- 若顛倒 180°：確認 `front_offset_rad:=3.14159` 仍套用
- 若側向偏移：量機械安裝角度

---

### B4. Go2 控制鏈（cmd_vel + mux + driver）

**測試指令**：
```bash
# 1. teleop 直接推 Go2
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --remap cmd_vel:=/cmd_vel_teleop

# 2. 確認 mux 把 teleop 通過
ros2 topic echo /cmd_vel | head -5

# 3. 觀察 Go2 是否前進、轉向、停止
```

**Pass criteria**：
- [ ] teleop 推 0.5 m/s 前進，Go2 抬腳前進（spec 已知 MIN_X=0.50）
- [ ] 鬆鍵後 Go2 停（不滑行 >0.3s）
- [ ] mux priority 順序正確：teleop > nav，且不被 reactive_stop 永久蓋掉

**Fail 動作**：
- 不抬腳：確認 `min_vel_x ≥ 0.45`、Go2 sport mode on
- 持續輸出 0：reactive_stop clear zone 設定錯，看 §B5

---

### B5. reactive_stop 單獨測

**測試指令**：
```bash
bash scripts/start_reactive_stop_tmux.sh
# teleop 推 Go2 前進 → 紙箱前 0.5m 應自動停 → 移開紙箱應 resume
```

**Pass criteria**：
- [ ] 紙箱 ≤0.5m → cmd_vel 變 0、Go2 立刻停
- [ ] 移開紙箱 1s 內 → cmd_vel 恢復、Go2 繼續
- [ ] clear zone 60cm 不會在無障礙時 false-positive 壓 cmd_vel

**Fail 動作**：
- 永久壓 cmd_vel：檢查 mux `safety_only:=true` 是否在 nav_capability 模式才開
- 不停：檢查 LiDAR 前方 idx 是否對齊（B3）

---

### B6. AMCL 定位

**測試指令**：
```bash
# 用既有 home_living_room_v8 地圖
MAP=/home/jetson/maps/home_living_room_v8.yaml \
  bash scripts/start_nav2_amcl_demo_tmux.sh
# Foxglove 設 /initialpose（Go2 真實位置）
ros2 topic echo /amcl_pose --once
```

**Pass criteria**：
- [ ] 設 /initialpose 後，particles 30s 內收斂（看 Foxglove 點雲變密集）
- [ ] Go2 不動時 amcl_pose 不漂（covariance 穩定）
- [ ] 手動推 Go2 走 0.5m → amcl_pose 跟著移動，不崩

**Fail 動作**：
- 不收斂：地圖太老、家裡擺設變了 → 重建一份 home 地圖
- 大漂：sensor model 參數調 → 看 nav2_params.yaml

---

### B7. `goto_relative` 短距離（最關鍵）

家裡空間有限，**只測 0.3m 和 0.5m**，不要測 1m。

**測試指令**：
```bash
MAP=/home/jetson/maps/home_living_room_v8.yaml \
  bash scripts/start_nav_capability_demo_tmux.sh
# 設 /initialpose、等 50s lifecycle active
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.3}"
# × 5 次，記錄成功/失敗
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.5}"
# × 5 次
```

**Pass criteria + 判斷邏輯**：

| 0.3m | 0.5m | 結論 |
|:---:|:---:|---|
| ≥4/5 | ≥3/5 | ✅ 系統 OK，可能空間限制；學校大空間應改善 |
| ≥4/5 | <3/5 | 🟡 0.3m OK 但 0.5m 不行 → **可能空間/轉向不足**；學校驗證 |
| <3/5 | <3/5 | 🔴 **不只是空間問題**，系統有 bug；5/12 必須找根因或走降級 |

**這就是 burndown 的關鍵判斷**。

**Fail 動作**（<3/5 兩個距離都不行）：
- 看 nav2 logs：BT navigator 失敗在哪一步？（global / local planner / controller）
- 檢查 footprint 是否包含 Go2 全身（Go2 約 0.65×0.30）
- DWB `min_vel_x` ≥ 0.45 確認
- 看 amcl pose 在 nav 過程中有沒有崩

---

## 3. 5/11 + 5/12 排程

### 5/11 晚（diagnostic 前 5 項）
- 19:00-19:30 B1 LiDAR
- 19:30-20:00 B2 D435
- 20:00-20:30 B3 TF / 前方
- 20:30-21:00 B4 cmd_vel / mux
- 21:00-21:30 B5 reactive_stop

**Day 1 Gate**：B1-B5 全 pass，或記錄 fail 根因。

### 5/12 PM（diagnostic 後 2 項，Brain freeze 後）
- 13:00-14:00 B6 AMCL
- 14:00-15:30 B7 goto_relative 0.3 / 0.5m

**Day 2 Gate**：B7 表格填完 → 結論寫進 §4。

---

## 4. 結論表（5/12 18:00 前必填）

| 項 | 結論 | 備註 / 根因 |
|---|---|---|
| B1 LiDAR | ☐ pass / ☐ fail | |
| B2 D435 | ☐ pass / ☐ fail | |
| B3 TF/front | ☐ pass / ☐ fail | |
| B4 cmd_vel/mux | ☐ pass / ☐ fail | |
| B5 reactive_stop | ☐ pass / ☐ fail | |
| B6 AMCL | ☐ pass / ☐ fail | |
| B7 goto 0.3m | ☐ ≥4/5 / ☐ <4/5 | |
| B7 goto 0.5m | ☐ ≥3/5 / ☐ <3/5 | |
| **剩餘最大假設** | ☐ 空間不足 / ☐ 其他：______ | |
| **學校 5/13-5/15 主攻** | | 依此表決定（地圖重建 / DWB 調 / footprint / 其他）|

---

## 5. 帶去學校的「假設清單」

5/12 晚出發前，產出一份只剩驗證項目的清單：

**已排除**（家裡 pass）：
- LiDAR / D435 / TF / cmd_vel / reactive_stop / AMCL（依結論表勾選）

**待學校驗證**：
- 大空間下 `goto_relative 0.5m / 1.0m / 1.5m` 成功率
- 大空間下 reactive_stop 紙箱 100% 觸發
- 30s 連續運行不撞、不卡

**若家裡 fail 的項**：
- 列出根因 + 5/13 到學校第一件事是修這個

---

## 6. 與其他 plan 的關係

- **A.Brain** 不阻塞，並行做
- **C.Runtime** 5/12 PM 開始時，B6 + B7 才在跑 → 用同一台 Jetson 注意 ROS2 session 不衝突
- **E.Mac/Network** 修完寫死 IP 後，B7 測試指令也要改走 `school_demo.env`（demo 期都統一走 env）

---

## 7. 不在這份 plan 的事

❌ DWB 大幅調優（demo 後）
❌ 換 nav stack（不切 Nav2）
❌ 訓練新 footprint（用現有）
❌ 動態避障（spec 5 P1，demo 後）
❌ 跑 1m+ 大距離測試（家裡空間不夠，無意義）

---

**End of Nav Root-Cause Burndown**
