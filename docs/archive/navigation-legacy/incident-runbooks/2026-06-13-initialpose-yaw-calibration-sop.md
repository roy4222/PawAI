# initialpose 朝向校正 + scan-overlay SOP（no-motion）

> **日期**：2026-06-13　**狀態**：SOP（操作員流程，**零 Go2 motion**）
> **task**：plan6 NS-5（[`docs/archive/superpowers-legacy/plans/2026-06-13-plan6-navigation-safety-s1-fallback.md`](../superpowers/plans/2026-06-13-plan6-navigation-safety-s1-fallback.md) §6 NS-5）
> **上游**：根因計畫 [`2026-06-13-nav-motion-incident-root-cause-plan.md`](2026-06-13-nav-motion-incident-root-cause-plan.md)、措辭 [`2026-06-13-nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md)、診斷集 [`2026-06-13-no-motion-diagnostics-sop.md`](2026-06-13-no-motion-diagnostics-sop.md)
> **這份是什麼**：設 `/initialpose` 後，**人工**確認 Go2 在地圖上的朝向（yaw）對不對的 no-motion 操作流程。這是 [`nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md) §5 **fallback②（遙控 + Foxglove LiDAR 證據）** 的操作依據，也是任何未來 motion HITL（plan6 §8）的硬前置（θ_error<5°）。

---

## 0. 鐵則

1. **本 SOP 全程零 Go2 motion**：設 initialpose、讀 TF、讀 covariance、Foxglove overlay 都是「定位 / 讀數」動作，**不發任何 goal / cmd_vel / Move / goto / DriveOnHeading**。Go2 站立不動。
2. **θ_error 是 sanity hint，不是 auto-gate**：本流程算出的 θ_error 是給操作員人工判斷用，**不修改任何 covariance 門檻值**（0.30 / 0.50 / 0.20 硬鎖，不放寬）。靜態安全閘目前 yaw-blind（c[35] 不查），所以 yaw 對不對**只能靠這個人工流程**把關。
3. **「設了 initialpose 且 nav_ready=true ≠ 朝向對 ≠ 可安全移動」**：position covariance 收斂不代表 yaw 收斂。任何 motion 仍需 Roy 明確授權 + e-stop + plan6 §8 HITL gate。
4. e-stop 終端就位（`nav_capability/scripts/emergency_stop.py engage` 待命，不按）。

---

## S5-1 讀外參（確認 LiDAR 前向軸）

```bash
# base_link → laser 外參（v8 反裝 mount，期望 yaw≈π=3.14159）
ros2 run tf2_ros tf2_echo base_link laser

# reactive_stop 的前向補正（須 == π，且與上面 TF 一致）
ros2 param get /reactive_stop_node front_offset_rad
```

- 期望：兩處 yaw 都 ≈ π。**`front_offset_rad` 與 TF yaw 是兩處獨立補正、必須一致**——不一致先停、修外參，不要繼續設 initialpose。

---

## S5-2 物理錨定（5/1 黃金標準；移動的是人，不是 Go2）

```bash
python3 scripts/lidar_front_sector.py --once
```

- **操作員站到 Go2 機鼻正前方約 0.5m**（移動的是操作員，Go2 不動）。
- 讀 `nearest(±30°) @ 角度`：人在正前方 → 角度應落 **±180° bin**（反裝 mount，front_offset=π）。
- **不對則停**：先修外參 / 反裝補正，**不准**進 S5-3。
- 此工具對齊 reactive_stop_node 同款幾何（`compute_front_min_distance` + `front_offset_rad`），**直接用 `scripts/lidar_front_sector.py`，勿重建**。

---

## S5-3 Foxglove fixed frame 設定（scan-overlay 基礎）

- **讀 scan（點雲 / LaserScan `/scan_rplidar`）→ fixed frame 用 `base_link`**（看相對機身的障礙幾何）。
- **讀定位（map / amcl_pose / 路徑）→ fixed frame 用 `map`**（看 Go2 在地圖上的位置與朝向）。
- scan-overlay 判讀：在 Foxglove 把 `/scan_rplidar` 疊在 `map` 上看點雲是否「貼合牆面」——點雲與地圖牆面有明顯角度偏移 = yaw 沒對齊（與 S5-4 的 θ_error 互為佐證）。**這是目視 sanity，不是自動 gate**。

> scan-overlay 在 plan6 NS-1 是一個**預設 off 的可選軟體閘**（`enable_scan_overlay_gate=false`）；本 SOP 只描述**目視判讀**，不啟用任何自動閘。

---

## S5-4 設 initialpose 後讀朝向（核心校正）

1. 在 Foxglove / RViz 用 **2D Pose Estimate** 設 `/initialpose`：對準 Go2 **真實位置 + 真實朝向**（朝向錯一截，goto「前方」就走歪——這是事件根因 R1）。
2. 讀完整 covariance（**人工讀 c[35]**）：

```bash
ros2 topic echo /amcl_pose --once
#   c[0]=σ²x  c[7]=σ²y（position）  c[35]=σ²yaw（朝向不確定度）
#   c[35] 大 = 朝向沒收斂 → 不准發 goal。
```

3. 比現場真值算 `θ_error`：

```bash
ros2 run tf2_ros tf2_echo map base_link
#   讀 rotation → 換算 AMCL 估的 yaw，跟現場 Go2 實際朝向（用地面標記/牆面為基準）比，得 θ_error。
```

---

## S5-5 判定（人工 sanity，非 auto-gate）

| θ_error | c[35] | 判定 | 動作 |
|---|---|---|---|
| `≤5°` | 收斂 | 朝向 OK | 可進 fallback②（遙控+Foxglove 證據）；motion HITL 仍需 Roy+e-stop |
| `5–10°` | 任意 | 邊界 | **重設 initialpose**，重跑 S5-4；**不准發 goal** |
| `>10°` | 任意 | 不合格 | **重設 initialpose**；先回 [診斷集 D2/D3](2026-06-13-no-motion-diagnostics-sop.md) 查外參；**不准發 goal** |

- **`|θ_error|>5–10°` → 重設、不准發 goal**。這是 sanity hint（human-readable），**不是 auto-gate**——靜態閘目前不查 yaw（R5），所以這層人工把關是 yaw 唯一防線。
- 本判定**不改任何 param / 門檻值**；只決定「操作員要不要重設 initialpose」。

---

## 對外措辭綁定（fallback② 用）

- 本 SOP 校正完成後，S1 對外只講 [`nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md) §5 **fallback② 可講句**：S2（safe-stop，配 §3 標準說法）、S4（窄場安全錐）、S6（拒絕有理由）、加「nav 在 Studio/Foxglove 顯示即時感知環境（非寫死）」。
- **禁講**（§4 F1-F10）：自主導航（F1 巡邏 / 整段）、動態繞障（F2）、D435 已融合（F3）、auto-resume（F4）、即時恢復（F10）、「聽懂過來就走到 Roy 身邊」（F6）。**「設了 initialpose、靜態檢查過」不可包裝成「可安全自主移動」**。

---

## 收尾

- 本 SOP **不改任何 runtime / param / 門檻值 / URDF**——純操作流程，刪檔即回退。
- 判讀結果（θ_error、c[35]、scan-overlay 目視）回填 plan6 Required Evidence。
