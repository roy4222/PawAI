# Track B 導航實機結果（2026-06-08，居家小空間 HITL）

> 場地：Roy 家客廳，淨空 ~1.1-1.5m（窄、雜物多）。操作：Foxglove 按鈕設 goal/initialpose（非語音）。
> 主線結論：**該證明的核心全證了；剩下的卡點是「空間太小」與「session orphaned-goal 累積」，不是 nav 能力問題。**

## 1. 達成的核心結果

| 項目 | 結果 | 證據 |
|---|---|---|
| **NAV-1 / F7** | ✅ **RESOLVED** | 首發 goto 0.3m → `success=reached, actual=0.270m`，無 no_progress abort；Roy 目視 Go2 真的往前走 |
| **短距位移特性** | ⚠️ discrete-step | 0.3m→0.27m、0.5m→0.27m，都 ~3.45s `reached`。Go2 sport-mode 一個步幅後 goal close（目標在「一步+容差」內就達標）|
| **NAV-2 安全停** | ✅ WORKS | 接近牆 1.03m → reactive_stop danger → nav_paused → Go2 停、0 撞 0 暴衝（多次） |
| **NAV-3 blocked-goal 不死** | ✅ 關鍵發現 | 被 reactive_stop 擋住的 goto 撐 278s 無 no_progress_timeout abort → goal 存活 → 自動續行可行 |

## 2. 感測器實際參與（Roy 問：2D LiDAR + 三陣攝影機？）

**只有 2D RPLIDAR `/scan_rplidar` 進導航迴路**（AMCL + costmap + reactive_stop）。
- Go2 內建光達：啟動但發 `/scan`，無人訂閱（空轉）。
- D435 depth：發 `/capability/depth_clear`，但 `depth_safety_node` 明註「非 controller、不 pause Nav2」，本輪未 gate 任何避障。
- RGB / 物體 / 人臉 / 語音：與 nav goal **零連接**。
- ⟹ 歪斜不可能來自相機，只能是 RPLIDAR/TF/步態。

## 3. 「歪斜」根因（待錄資料確認）

排序：H1 四足步態 yaw drift（~60%）＞ H2 DWB 短距修正不足（~30%）＞ H3 LiDAR TF 偏移（~10%）。
**鎖定法**：goto 全程錄 `/cmd_vel_nav` angular.z + `/amcl_pose` yaw；來回 2-3 趟 —— 固定偏一邊=TF(H3)，每趟亂=步態(H1)。（本輪因 orphaned-goal 未錄到完整波形。）

## 4. ⭐ 最大發現：reactive_stop 居家誤擋根因 + 修法已驗證

**症狀**：Go2 正前方明明淨空，卻被報 danger/nav_paused（Roy：「前面根本沒障礙物」）。
**診斷（真實 /scan_rplidar）**：正前方 ±15° = 1.56m 淨空；但 `front_arc_deg=30`（±30° 寬錐）把**右前角 -30° 家具(0.84m)**算進前方危險。**不是 TF bug**（front_offset=π 正確），是**安全層錐角太寬 + danger 1.1m 太保守**。
**修法驗證 ✅**：重啟 reactive_stop 收窄到 **±15° + danger 1.0 + 低速 0.2**：

| | ±30°（原）| ±15°（修）|
|---|---|---|
| obstacle_distance | 0.84m | 1.16-2.12m |
| zone | danger | **slow/clear** |
| nav_paused | **true（鎖死）** | **false（放行）** |

⟹ 收窄錐角即解誤擋（sensing 層已證）。安全前提：±15° 必須綁低速 ≤0.2 m/s。

## 5. 為什麼最後沒拍到「修法後 Go2 走給你看」

不是 nav 壞 —— 是 **orphaned-goal 累積**：
- nav_action_server 是 single-goal server；被擋住的 goto（278s 那筆）client 被我 kill 後，**server 端 goal 仍 active**。
- `send_relative_goal.py` 有 **double `rcl_shutdown` bug**，client crash/被殺時不會 cancel goal → 每次失敗都留一個 orphan。
- 加上 SSH 反覆 255 中斷 goto → orphan 一直累積 → 後續 goto 全被 `rejecting goto_* — another goto still active` 擋掉。
- 重啟 navcap 清一次，但下一筆 goto 又 crash 又留 orphan。

## 6. Backlog（這輪冒出來，非今天 demo 前必做）

1. **`send_relative_goal.py` double-shutdown bug**：crash/kill 時不 cancel goal → 留 orphan。修：try/finally 正確 cancel + 單次 shutdown。
2. **nav_action_server orphaned-goal**：client 斷線時 server 應自動 cancel/timeout active goal，否則 single-goal server 永久卡死。
3. **indoor-tight profile 永久化**：新建 `scripts/start_nav_tight_low_speed_tmux.sh`（±15-20° + danger 1.0 + 低速），居家窄場用；保留主線 ±30° 給開放空間。
4. **Nav2 Collision Monitor PoC**（demo 後 ~7/2）：polygon footprint 取代錐角，從根解 off-path 側前誤擋。需卡尺實測機身。
5. **D435→local costmap 融合（light）**：depth→/scan_d435 進 obstacle layer + DenoiseLayer，補 2D 盲區。
6. **目標導向導航**：goto_named 已 ready，但需更大空間才有意義（學校場地）；物體導向（看到物體→map 座標→走過去）需 4 層新開發（object 加 depth + 像素→map + brain 決策 + 繞障）≈ 4-5 天，超出 6/18。
7. **歪斜診斷**：下次在較大空間用 goto_named >1m，全程錄 angular.z + yaw 鎖 H1/H2/H3。

## 7. demo 能講 / 不能講

- ✅ 能講：「短距自主移動（LiDAR + Nav2 + AMCL）」「遇障在安全距離前安全停下、不撞」「居家窄場用收窄安全錐避免誤擋」。
- ❌ 不能講：乾淨 0.5m+ 連續導航、route 巡場、動態繞障、看到物體走過去（皆未達或需大空間/新開發）。
