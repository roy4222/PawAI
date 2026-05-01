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

## 關鍵 commits

- `fa0fa54` fix(nav): LiDAR mount v8 — yaw 0 → π
- `5d938d6` feat(nav): home_living_room_v8 map — TF yaw=π 修正後重建

## 相關檔案

- 修正後 TF：7 scripts（`start_lidar_slam_tmux.sh`、`start_nav2_amcl_demo_tmux.sh`、`start_nav_capability_demo_tmux.sh`、`start_nav2_demo_tmux.sh`、`start_reactive_stop_tmux.sh`、`start_scan_only_tmux.sh`、`build_map.sh`）
- v8 map：`docs/導航避障/research/maps/home_living_room_v8.{pgm,yaml,png}`
- mount 量測 v8：`docs/導航避障/research/2026-04-29-mount-measurement.md`（v8 段）
- v7 yaml/pgm/png 留在 repo 但 unusable
