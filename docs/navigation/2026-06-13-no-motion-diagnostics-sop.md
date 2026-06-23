# No-Motion 導航診斷 SOP（D2–D5）

> **日期**：2026-06-13　**狀態**：SOP（READ-ONLY 診斷集，**零 Go2 motion**）
> **task**：plan6 NS-D2（[`docs/archive/superpowers-legacy/plans/2026-06-13-plan6-navigation-safety-s1-fallback.md`](../superpowers/plans/2026-06-13-plan6-navigation-safety-s1-fallback.md) §7）
> **上游**：根因計畫 [`2026-06-13-nav-motion-incident-root-cause-plan.md`](2026-06-13-nav-motion-incident-root-cause-plan.md)、runbook [`2026-06-13-nav-incident-runbook.md`](2026-06-13-nav-incident-runbook.md)、措辭 [`2026-06-13-nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md)
> **這份是什麼**：把 goto 撞牆事件的 no-motion 根因診斷（D2 AMCL yaw / D3 LiDAR 前向軸 / D4 reactive 側向幾何 / D5 靜態 smoke + covariance）寫成**可直接貼上終端**的唯讀指令集。**每一條都是讀取 / echo / param get，不發任何 cmd_vel / Move / goto / 任何 Go2 motion。**

---

## 0. 鐵則（先讀，違反即停）

1. **本 SOP 全程零 motion**：只允許 `echo` / `tf2_echo` / `param get` / `topic hz` / 移動「障礙物」（不是移動 Go2）。**不准** `ros2 topic pub /goal_pose`、`ros2 action send_goal /nav/goto_relative`、`ros2 action send_goal /nav/drive_on_heading`、`cmd_vel`、`Move(1008)`、`DriveOnHeading`。
2. Go2 全程**站立不動、e-stop 終端就位**（`nav_capability/scripts/emergency_stop.py engage` 待命）。
3. `front_arc_deg` / `danger_distance_m` / `slow_distance_m` / `front_offset_rad` 只在 `reactive_stop_node.__init__` 讀一次 → **`ros2 param set` 改了無效**，要改 profile 必 **kill 重啟帶參數**（這是讀數會「對不上你以為的設定」的常見坑）。本 SOP 只 **`param get`** 不 set。
4. **「靜態 smoke 8/8 通過 ≠ 朝向對 ≠ 可安全移動」**——D5 過了不代表 goto 安全（這正是事件根因之一：靜態閘 yaw-blind，見 D2 c[35] 段）。任何 motion 仍需 Roy 明確授權 + e-stop + plan6 §8 HITL gate。
5. Jetson 用 zsh：`source` 用 `setup.zsh`；陣列參數加單引號（zsh glob 會炸）。所有指令在 `ros2 node list` 看得到 nav stack 在跑的前提下執行。

---

## 前置：確認環境（唯讀）

```bash
# 確認 nav stack 在跑、e-stop 待命
ros2 node list                                    # 應見 amcl / nav_action_server / reactive_stop_node / go2_driver
ros2 topic list | grep -E "amcl_pose|scan_rplidar|reactive_stop|nav_ready|depth_clear"
# e-stop 終端另開一個（不要按 engage，只是就位）
#   python3 nav_capability/scripts/emergency_stop.py engage   # ← 只在出事時才執行
```

---

## D2 — AMCL yaw / covariance（治 R1 走歪 + R5 yaw-blind 閘）

> 目的：證明 ① goto「前方」吃的是 AMCL map-frame yaw（yaw 錯 → 走歪）；② 靜態安全閘 `nav_ready` 只看 position covariance（c[0]+c[7]），**從不看 c[35]（σ²yaw）** → yaw 大錯時 `nav_ready` 仍可能 true（R5）。

```bash
# D2-1 讀完整 AMCL covariance（6x6 row-major 攤平成 36 個值）
ros2 topic echo /amcl_pose --once
#   讀法（唯讀，人工對照）：
#     c[0]  = σ²x          ← position
#     c[7]  = σ²y          ← position（nav_ready 只用 c[0]+c[7]）
#     c[35] = σ²yaw        ← 朝向不確定度（靜態閘從不查 → R5 的證據）
#   c[0]/c[7] 小但 c[35] 大 = 位置收斂、朝向沒收斂 → 仍可能被判 nav_ready=true。

# D2-2 AMCL 估的朝向 vs 現場真值
ros2 run tf2_ros tf2_echo map base_link
#   讀 rotation → 換算 yaw，跟現場 Go2 實際朝向比，估 θ_error。

# D2-3 yaw 大錯時 nav_ready 是否仍 true（R5 直接實證）
ros2 topic echo /capability/nav_ready --once
#   若 D2-2 顯示 θ_error 很大、但這裡仍 nav_ready=true → R5 yaw-blind 閘成立。
```

**covariance 收斂曲線（含 yaw 維度）**：靜止下用 covariance probe 看 c[0]+c[7] 與 c[35] 隨時間收斂（NS-4 產出 `scripts/nav_covariance_probe.py` 後）：

```bash
python3 scripts/nav_covariance_probe.py        # 訂 /amcl_pose，輸出 CSV: time, cov_xy, cov_yaw
```

> **黃帶決策表（含 yaw；NS-4 probe 上線後回填實測門檻；門檻值零變動原則：position 0.30/0.50 硬鎖，不放寬）**：
>
> | cov_xy | cov_yaw (c[35]) | 判讀 | 動作（皆 no-motion 或 needs_roy） |
> |---|---|---|---|
> | 低（收斂） | 低（收斂） | 位置 + 朝向都穩 | 可進 motion HITL gate（仍需 Roy + e-stop，plan6 §8） |
> | 低 | 高（未收斂） | 位置穩、**朝向沒收斂** | **不發 goal**；重設 initialpose 朝向（[initialpose SOP](2026-06-13-initialpose-yaw-calibration-sop.md)） |
> | 高 | 任意 | 位置未收斂 | 等收斂 / 重設 initialpose；**不發 goal** |
>
> **覆蓋率與 AMCL warmup**：靜止 AMCL 不一定靠自己收斂；plan6 把「該推 Go2 0.3m warmup」列為 **needs_roy + e-stop 的 HITL 選項**，非本 SOP 動作。

---

## D3 — LiDAR 前向軸 / 反裝 yaw=π（治 R6 外參 + reactive 沉默）

> 目的：確認 ① base_link→laser 外參 yaw≈π（v8 反裝 mount）；② reactive_stop 的 `front_offset_rad` 與該 TF yaw **必須一致**（兩處獨立補正）；③ 物理錨定（人站機鼻）落在預期 bin。

```bash
# D3-1 外參 TF（期望 yaw≈π = 3.14159）
ros2 run tf2_ros tf2_echo base_link laser

# D3-2 reactive_stop 的前向補正（須 == π，與 D3-1 一致）
ros2 param get /reactive_stop_node front_offset_rad

# D3-3 物理錨定（零 Go2 motion；操作員「站到」Go2 機鼻前 0.5m，移動的是人不是狗）
python3 scripts/lidar_front_sector.py --once
#   讀 nearest(±30°) @ 角度：人在正前方 → 角度應落 ±180°（反裝 mount，front_offset=π）。
#   若不落 ±180° → 外參/反裝補正不一致，先修 TF/param，再做任何 motion。
#   （此工具對齊 reactive_stop_node 同款幾何 compute_front_min_distance + front_offset_rad，
#    --front-offset-rad 預設 π；勿重建，直接用 scripts/lidar_front_sector.py。）

# D3-4 scan 健康度（頻率 / 有效點 / NaN 比例）
python3 scripts/scan_health_check.py
ros2 topic hz /scan_rplidar                     # 預期穩定（< 2Hz 或抖動 = scan 不健康）
```

> **`front_offset_rad=π` 與 TF yaw=π 是雙重獨立補正、必須一致**（plan6 §2.6）。任一邊改 mount 角度，兩邊都要改。

---

## D4 — reactive 側向幾何（治 R3 側向沉默 / 誤擋）

> 目的：① 讀現用 `front_arc_deg`（窄錐 vs 寬錐）；② 移動「障礙物」（不是 Go2）驗側前家具是否被誤算進前方危險；③ 確認 progressive 模式在 slow 帶會回 None（沉默）是預期行為，不是 bug。**全程 Go2 站立不動，只移箱子。**

```bash
# D4-1 現用前錐角度（open_space=30 / indoor_tight=18；param set 無效，只能 get）
ros2 param get /reactive_stop_node front_arc_deg
ros2 param get /reactive_stop_node danger_distance_m
ros2 param get /reactive_stop_node slow_distance_m

# D4-2 移箱到「側前角」+25° / 1.65m（移動的是箱子，Go2 不動）
#   → 看 reactive 是否把 off-path 家具算進前方危險
ros2 topic echo /state/reactive_stop/status
#   open_space(±30°)：+25° 的箱子在錐內 → 可能 slow/active（這就是 6/8「前面明明空卻被擋」）
#   indoor_tight(±18°)：+25° 的箱子在錐外 → 預期 zone=slow/clear、active=false（窄錐修正）

# D4-3 scan 頻率（reactive 反應的上游）
ros2 topic hz /scan_rplidar
```

> **窄錐（indoor_tight ±18°）必須綁低速 ≤0.2 m/s**（側向覆蓋變少，靠低速補反應時間，6/8 HITL）。改 profile 用 `REACTIVE_PROFILE=indoor_tight bash scripts/start_nav_capability_demo_tmux.sh`（kill 重啟），**不是** `ros2 param set`。
> **progressive 模式在 slow 帶回 None（沉默）= 設計使然**（`lidar_geometry.py` progressive 在 slow 回 None）——本 SOP 只觀測、不改判定邏輯。

---

## D5 — 靜態 smoke + 動作/能力存在性（基線健檢；**過了≠朝向對≠可安全移動**）

```bash
# D5-1 靜態 smoke（8 項全靜態，零 motion）
bash scripts/smoke_test_nav_static.sh
#   ⚠ 8/8 PASS 只代表「nav stack 起來了、靜態介面在」，
#     不代表朝向對、不代表可安全移動（靜態閘 yaw-blind，見 D2）。

# D5-2 確認可用動作（觀測；不送 goal）
ros2 action list | grep -E "goto_relative|drive_on_heading"
#   goto_relative = NOT_DEMO_READY（R1 AMCL-yaw / R2 超衝），不是 S1 主線。

# D5-3 depth_clear gate 狀態（D435 在線時的 fail-closed gate；非 costmap fusion）
ros2 topic echo /capability/depth_clear --once
#   D435 目前可能 Right MIPI / Hardware Error → depth_clear 可能 false/stale。
#   這只是 Brain 層 fail-closed gate，D435 未進 Nav2 costmap（fusion = research-only spec）。
```

---

## 判讀填表（dry-run 後逐條記錄）

| 診斷 | 指令 | 觀測值 | 判讀 |
|---|---|---|---|
| D2-1 covariance | `echo /amcl_pose --once` | c[0]=__ c[7]=__ **c[35]=__** | position vs yaw 收斂？ |
| D2-2 θ_error | `tf2_echo map base_link` | AMCL yaw=__ vs 現場=__ | θ_error≈__° |
| D2-3 R5 實證 | `echo /capability/nav_ready --once` | nav_ready=__ | yaw 大錯時仍 true？ |
| D3-1 外參 | `tf2_echo base_link laser` | yaw=__ | ≈π？ |
| D3-2 補正 | `param get ... front_offset_rad` | __ | ==π 且 == D3-1？ |
| D3-3 錨定 | `lidar_front_sector.py --once` | nearest @ __° | 落 ±180°？ |
| D4-1 前錐 | `param get ... front_arc_deg` | __ | open_space/indoor_tight？ |
| D4-2 側向 | 移箱 +25°/1.65m → `echo .../status` | zone=__ active=__ | 誤擋？ |
| D5-1 smoke | `smoke_test_nav_static.sh` | __/8 | 過≠朝向對 |
| D5-2 動作 | `ros2 action list \| grep ...` | __ | goto/drive_on_heading 存在？ |

---

## 收尾

- 本 SOP **不改任何 runtime / param / URDF**。
- 判讀結果（含原始 echo log）回填上表 + plan6 Required Evidence。
- 任何進一步 motion 走 plan6 §8 HITL（needs_roy + e-stop + plan1 profiling gate）；S1 對外措辭一律綁 [`nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md) S1-S8 / F1-F10。
