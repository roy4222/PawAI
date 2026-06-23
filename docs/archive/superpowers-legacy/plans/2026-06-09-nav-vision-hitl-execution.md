# 6/9 導航 + 視覺 HITL 執行計畫 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 多數 task 是**硬體 HITL（Roy 在 Go2 + Jetson 前手動執行）**，不是 subagent 可代跑的 code。只有 Phase 3 是 WSL code task，可用 superpowers:subagent-driven-development 或 superpowers:executing-plans。Steps 用 checkbox（`- [ ]`）追蹤。

**Goal:** 把 6/9 已寫好的 WSL 端工具（nav blocker fix / indoor-tight profile / LiDAR 扇區 / object 矩陣 harness）部署上 Jetson，跑硬體 HITL 證明它們真的有效，蒐集 demo 決策數據，並把 6/18 可講台詞鎖定到誠實範圍。

**Architecture:** 先 commit + deploy（Phase 0）→ NAV stack 跑一段 HITL（Phase 1）→ 清掉、換 brain stack 跑 VISION HITL（Phase 2，8GB 兩 stack 互斥不可同跑）→ 補幾個 optional WSL 工具（Phase 3）→ 把 HITL 結果寫回 claim 表 + 鎖 demo 台詞（Phase 4）。

**Tech Stack:** ROS2 Humble / nav_capability (AMCL + Nav2 + reactive_stop) / RPLIDAR A2M12 / D435 / Go2 Pro WebRTC / object_perception (YOLO26n TRT) / brain stack / pytest。

**真相來源：** `docs/pawai-brain/research/2026-06-09-nav-vision-execution-research.md`（truth table、資料模板、claim 表都在那）。本 plan 是它的執行序。

**誠實底線（報告 §1）：** 目前只有 4 個能力 HARDWARE_PROVEN（short goto / safe-stop / face / cup，皆窄版單點）。本計畫的目的是**把更多能力從 WIRED_RUNTIME 升到 HARDWARE_PROVEN，或誠實標記為未達**——不是預設它們會過。

---

## 前置狀態（執行前確認）

- 本地 `main` 已與 `origin/main` 同步（先前 3 commit `3a8ecb6`/`f2a0df4`/`8eaef29` 已在 origin；6/9 review 確認 `origin/main...HEAD = 0 0`）。
- 今天 WSL dev **未 commit**：3 改 + 4 新 + 2 docs（見 Task 0.1）= 本 Phase 0 唯一要 commit/push 的東西。
- 全部 `py_compile` 過、`benchmarks/test/test_object_matrix.py` 11 passed、新 code flake8 乾淨。
- ⚠️ 供電不穩（6/7 掉電 2 次）→ HITL 前先穩定電源。

---

## 📊 HITL 執行結果 Log（唯一 scoreboard，每測一項就填）

### Phase 0 ✅（2026-06-09）
- 0.1 commit `a38ca96` pushed origin/main（9 檔，pre-commit 綠）。
- 0.2 deploy：rsync + `colcon build nav_capability`；Jetson install/ 含 `goto_max_duration_s`、新 scripts 在、`REACTIVE_PROFILE` 在。

### Task 1.1 orphan-goal — ⚠️ 降級，非完全解（HARDWARE 實測 6/9）
- 重現：goto1 accepted(2.0s) → SIGINT → **client cancel 沒送出**（rclpy 預設 SIGINT 先關 context → RCLError，非 KeyboardInterrupt）→ `_goto_active` 卡 → followup ×2 rejected、server `still active` ×2。
- 自癒：orphan 靠**既有 `no_progress_timeout`(~10-13s)** END 掉 goto1 → 之後 goto 又能 accept。**不需重啟 navcap**。`goto_max_duration_s=120` 是 jitter-progress 後備（本次未輪到）。
- **結論**：致命版（永久卡死、要重啟）✅ 消除；client-side Ctrl-C cancel ⚠️ 未完全成功。**post-demo 修**：client `rclpy.init(signal_handler_options=NO)` 讓 KeyboardInterrupt 進自家 handler 才送得出 cancel。
- demo 台詞：「client/SSH 掛掉約 10 秒內自動恢復、不需重啟」。**不可講**「即時恢復」。

### Task 1.2 lidar_front_sector — ✅ live 可用
- 輸出 `±15°=1.29 ±20°=1.05 ±30°=0.97 nearest=0.97@+22.5°`，當場定位側前家具 +22.5°/0.97m（= open_space ±30° 誤擋本案）。

### Task 1.3 indoor-tight 誤擋修正 — ✅ 感測層已驗（HARDWARE 6/9）
- 只重啟 reactive_stop_node 帶 `front_arc_deg:=18 danger:=1.0 slow:=1.4 slow_speed:=0.2 normal:=0.3 offset:=π`（保留 AMCL，免重設 initialpose）。
- **before（±30°）**：zone=`danger`、front_min=0.97m（+22.5° 側前家具誤判）。
- **after（±18°）**：zone=`slow`、front_min=**1.22m**（家具排除）→ **誤擋解除** ✅。enable_nav_pause 重設 true。
- 台詞：「修正窄場誤擋感測原因（±30°→±18° 排除側前家具），zone 由 danger 變 slow」。**未講**「能自主穿越」（motion 待 safe-stop 重測一併證）。
- 坑：tmux pane target 用 `$SESS:reactive` 被 zsh `:r` modifier 吃掉 → hardcode `nav-cap-demo:reactive`；param get racing 節點啟動會 hang（service timeout），等節點起完再查。

### Task 1.5 safe-stop（indoor_tight）— ✅ 正前障礙安全停（HARDWARE 6/9）
- goto 0.5m → Go2 **accepted（無誤擋，indoor-tight 也補上 motion 證據）** → 走 → zone `clear→slow→danger` → `reactive_stop_active=true`、Go2 停、**不撞不暴衝**。final `obstacle_distance=0.784m`。
- ⚠️ **margin 薄**：danger 1.0m + Nav2 ~0.5 m/s 慣性 → 停 front 0.78m ≈ 機鼻離障礙 ~0.4m。窄錐+0.5 速度已知風險（progressive 下 indoor_tight 低速 0.2 **不套用**，速度由 Nav2 controller 設）。demo 障礙擺遠或 danger 調 1.1。
- 台詞：「遇正前障礙會停下、不撞」。**不講**側向（±18-30° 不覆蓋）或低速續行（Nav2 仍受 Go2 MIN_X floor 影響）。

### Task 1.6 stop-resume — ⚠️ 機制成立但 6/18 不採用 auto-resume（HARDWARE 6/9）
- 障礙物擋 Go2（danger）→ goto active(paused) → **Roy 移開障礙 → Go2 自動續行走完 goal**（server-side resume，client 已死照樣 resume）→ **auto-resume 確認**。
- 但 Roy 實測觀察：障礙移開後 Go2 resume 太急，容易貼近/撞到前方物體；不適合 6/18 現場主秀。
- 台詞降級：「遇障會停，操作員確認安全後重新下達或遙控輔助」。**不可講**「淨空後自動續行」作為 demo 主能力。
- ⚠️ **resume 速度偏快（Roy 實感）**：根因**不是** LiDAR rate（~11.3Hz，0.5m/s 下 ~4.5cm/frame 夠快），是 **Go2 sport MIN_X=0.5 m/s floor** → nav(progressive) Go2 只能 ~0.5 起步、resume 直接 lunge 到 0.5；indoor_tight 低速 0.2 **不套用於 nav**。
- ⚠️⚠️ **實測 resume lunge 危險（6/9）**：resume 後 Go2 走完 0.5m goal **停在 front 0.21m（機鼻幾乎貼牆）** — 短 goal 在 reactive 來得及 danger-halt 前就走完、衝到 0.21m。reactive_stop 在「短距+0.5 floor+已近障礙」的 resume **擋不住**。
- **結論台詞**：auto-resume 機制成立，但 **tight space 禁 demo auto-resume**（會 lunge 貼牆）。安全版退回「操作員確認安全後重新下達」；6/18 若空間緊或人多，直接遙控/Studio 輔助進場，不把避障續行當主秀。要再 demo 續行 → danger 調 1.2m + 留足空間 + 長 goal。真低速走 standalone/patrol v0。

### 現況校正（別 overclaim）
- **D435 沒融入導航主迴路**：`depth_safety_node` 只發 `/capability/depth_clear`（不發 cmd_vel、不 pause Nav2），launcher `pointcloud.enable:=false`。現在 = 2D LiDAR stop-based safety，**不是** depth+LiDAR fusion。fusion = §9 / 獨立 **P2**（depth→/scan_d435→costmap）。
- **目前測的是 nav primitive（goto_relative），不是 patrol behavior** → 它不自己轉彎/掉頭是合理的。patrol = Phase 1.5 prototype。
- **DimOS = 獨立 P2 研究（今天不切框架，避免雙 driver/runtime）**：docs（`docs/navigation/research/2026-05-02-dimos-analysis.md`）**未**證明「Go2 內建 3D LiDAR 直接可靠導航」；thesis 寫它用 **D435 + VoxelGrid costmap + spatial memory + 行為層** 做巡邏（繞過內建 LiDAR ~18% 覆蓋）。值得借的是 **D435 VoxelGrid + 行為層 + FollowHuman/ReplanLimiter**，非整包導入。精準待查：①用 utlidar 還 D435？②真接 Nav2/costmap 還自做 VoxelGrid？③patrol 是實機/影片/script？④能否只借 VoxelGrid/FollowHuman/spatial-memory？⑤怎麼處理 WebRTC LiDAR 低覆蓋。
- **D435 fusion P2 進度序（Roy 6/9，現場不硬接，是新導航分支非小調參）**：① D435 shadow test（**不動狗**，錄 `/scan_d435_shadow` vs `/scan_rplidar` 比 D435 補到哪些 RPLIDAR 漏障）→ ② 接 Nav2 local costmap（D435 當 observation source 或 STVL voxel layer）→ ③ 靜態障礙 3/5 能否繞/更準停 → ④ reactive patrol。**今天不做、不准宣稱已融合。**

---

## Phase 0 — Commit + Deploy（WSL → Jetson）

### Task 0.1: Commit 今日 WSL dev + 研究/計畫文件

**Files:**
- Modify: `scripts/send_relative_goal.py`
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`
- Modify: `scripts/start_nav_capability_demo_tmux.sh`
- Create: `scripts/lidar_front_sector.py`
- Create: `benchmarks/core/object_matrix.py`
- Create: `scripts/obj_matrix_cap.py`
- Create: `benchmarks/test/test_object_matrix.py`
- Create: `docs/pawai-brain/research/2026-06-09-nav-vision-execution-research.md`
- Create: `docs/superpowers/plans/2026-06-09-nav-vision-hitl-execution.md`（本檔）

- [ ] **Step 1: 跑一次 gate 確認綠**

Run:
```bash
cd ~/newLife/elder_and_dog
python3 -m py_compile scripts/send_relative_goal.py nav_capability/nav_capability/nav_action_server_node.py scripts/lidar_front_sector.py scripts/obj_matrix_cap.py benchmarks/core/object_matrix.py
python3 -m pytest benchmarks/test/test_object_matrix.py -q
python3 -m flake8 benchmarks/core/object_matrix.py scripts/obj_matrix_cap.py scripts/lidar_front_sector.py
bash -n scripts/start_nav_capability_demo_tmux.sh
```
Expected: compile 無輸出、`11 passed`、flake8 無輸出、bash -n 無輸出。

- [ ] **Step 2: Commit（main 直上，與既有 workflow 一致）**

Run:
```bash
git add scripts/send_relative_goal.py nav_capability/nav_capability/nav_action_server_node.py \
  scripts/start_nav_capability_demo_tmux.sh scripts/lidar_front_sector.py \
  benchmarks/core/object_matrix.py scripts/obj_matrix_cap.py benchmarks/test/test_object_matrix.py \
  docs/pawai-brain/research/2026-06-09-nav-vision-execution-research.md \
  docs/superpowers/plans/2026-06-09-nav-vision-hitl-execution.md
git commit -m "feat(nav,bench): 6/9 HITL pre-flight tools — nav orphan-goal fix, indoor-tight profile, lidar sector debug, object matrix harness

- send_relative_goal.py: cancel in-flight goal on interrupt + guarded shutdown
- nav_action_server: goto_max_duration_s safety net (orphan-goal release)
- start_nav_capability_demo_tmux.sh: REACTIVE_PROFILE=open_space|indoor_tight
- lidar_front_sector.py: +-15/20/30 deg nearest distance + angle
- object_matrix.py + obj_matrix_cap.py: per-cell PASS/DEGRADED/FAIL CSV (11 tests)
- docs: 6/9 nav+vision execution research + HITL plan"
```
Expected: commit 成功，working tree clean。

- [ ] **Step 3: Push（只今天這個 commit；先前 3 已在 origin）**

Run: `git push origin main`
Expected: 推送 1 個新 commit，`git status` = up to date。

### Task 0.2: Deploy 到 Jetson + rebuild nav_capability

**只有 `nav_capability` 需 colcon build（改了 nav_action_server）；`scripts/` 與 `benchmarks/` 是純 python，rsync 即可。**

- [ ] **Step 1: 同步 + build**

Run（CLI 路徑）:
```bash
pawai jetson deploy --module nav      # 若 module 名不符 → 見 fallback
```
Fallback（手動）:
```bash
rsync -av --exclude={build,install,log,.git,node_modules,.venv} ~/newLife/elder_and_dog/ jetson-nano:~/elder_and_dog/
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && colcon build --packages-select nav_capability && source install/setup.zsh"'
```
Expected: build `nav_capability` 成功（`Finished <<< nav_capability`）。

- [ ] **Step 2: 驗證新 param + 新 scripts 真的落地**

Run（不需啟 stack，先確認檔案在）:
```bash
ssh jetson-nano 'zsh -lic "grep -c goto_max_duration_s ~/elder_and_dog/install/nav_capability/lib/python3.10/site-packages/nav_capability/nav_action_server_node.py; ls ~/elder_and_dog/scripts/lidar_front_sector.py ~/elder_and_dog/scripts/obj_matrix_cap.py"'
```
Expected: grep ≥1（rebuild 後的 install/ 含新 param）、兩 script 存在。
> ⚠️ 若 grep=0 → rsync 只搬了源碼沒 rebuild install/，重跑 Step 1 的 colcon build（CLAUDE.md 已知陷阱）。

**Acceptance（Phase 0）：** main pushed、Jetson `nav_capability` rebuilt 含 `goto_max_duration_s`、新 scripts 在 Jetson。

---

## Phase 1 — NAV HITL（nav stack 一段，brain stack 此時不開）

> 啟 nav 用 `nav-avoidance-lane` skill / `pawai demo start --nav capability`，別手拼。每段錄影（第三人稱 + Foxglove）。

### Task 1.1: 驗證 orphan-goal blocker 已修（最高優先）

- [ ] **Step 1: 啟 nav stack（open_space 預設）**

Run: `REACTIVE_PROFILE=open_space bash scripts/start_nav_capability_demo_tmux.sh`
等 ~50s lifecycle active，Foxglove 設 `/initialpose`（Go2 真實位置 + 朝向）。
Expected: `ros2 topic echo /capability/nav_ready --once` = `data: true`。

- [ ] **Step 2: 先重現舊 bug（修法生效的對照）—— 用 Ctrl-C 中斷在途 goto**

Run（monitor window）:
```bash
python3 scripts/send_relative_goal.py --distance 0.5
# goal accepted 後（Go2 開始走），立刻 Ctrl-C 殺掉這個 CLI
```
- [ ] **Step 3: 立刻連發 2 次 goto，確認不再被卡**

Run:
```bash
python3 scripts/send_relative_goal.py --distance 0.3
python3 scripts/send_relative_goal.py --distance 0.3
```
Expected（修法生效）: 兩次都 **goal accepted**，**不**出現 `another goto still active`。
Record: 是否 accepted、server log 有無印 cancel。

- [ ] **Step 4（OPTIONAL，有安全風險 — Ctrl-C 路徑沒過之前不要做）: 硬 kill 自癒（120s safety net）**

⚠️ 安全前提：**距離只用 0.3m、前方淨空、旁邊有人手準備 e-stop / safe-stop**。hard kill 不送 cancel → Go2 可能走到 goal 或等 120s safety net 才釋放。

Run:
```bash
python3 scripts/send_relative_goal.py --distance 0.3 &
sleep 2; kill -9 %1     # 模擬 SSH 硬斷，client 來不及 cancel
python3 scripts/send_relative_goal.py --distance 0.3   # 立刻發
```
Expected: 立刻發**可能**先被拒，但 **≤120s 後**再發必 accepted（`goto_max_duration_s` 釋放旗標），**不需重啟 navcap**。
Record: 立刻發是否被拒、等多久後 accepted、有無 `goto exceeded goto_max_duration_s` log。

**Acceptance（1.1）：** Ctrl-C 路徑連送 3 次不卡（即時）；硬 kill 路徑 ≤120s 自癒、navcap 不需重啟。
> 若硬 kill 自癒太慢影響 demo 節奏 → 記下來，Phase 3 評估加 odom-tied liveness watchdog（有誤殺風險，需另驗）。

### Task 1.2: LiDAR 前方扇區工具 live 驗證

- [ ] **Step 1: 跑工具（nav stack 已在跑，/scan_rplidar 活著）**

Run（monitor window，另開）:
```bash
python3 scripts/lidar_front_sector.py            # 2Hz 連續
# 或單發：python3 scripts/lidar_front_sector.py --once
```
Expected: 印 `front  ±  15°=x.xxm  ± 20°=x.xxm  ± 30°=x.xxm   nearest(±30°)=x.xxm @ +xx.x°`。

- [ ] **Step 2: 對照人眼判斷**

正前方放/移開障礙，確認 ±15° 讀數跟著變；側前方（~-30°）放家具，確認只有 ±30° 變、±15° 不變。
Record: 一張「前方淨空但 ±30° 抓到側邊家具」的讀數截圖（這就是 6/8 誤擋根因的活證）。

**Acceptance（1.2）：** 讀數與實景一致；能用它分辨「正前真障礙」vs「側邊家具進錐」。

### Task 1.3: indoor-tight profile 實機（窄場不誤擋 + 真的走過去）

- [ ] **Step 1: 清掉 open_space stack，改啟 indoor_tight**

Run:
```bash
pawai demo stop          # 或 nav-avoidance-lane cleanup
REACTIVE_PROFILE=indoor_tight bash scripts/start_nav_capability_demo_tmux.sh
```
- [ ] **Step 2: 確認窄場參數生效**

Run: `ros2 param get /reactive_stop_node front_arc_deg` ; `ros2 param get /reactive_stop_node danger_distance_m`
Expected: `18.0` 與 `1.0`。
> launcher banner 印 `REACTIVE_PROFILE=indoor_tight` + `REACTIVE_PARAMS=...front_arc_deg:=18.0...`（launcher 不印 `front=±18°`）。`front=±18°` 是 **reactive_stop_node 自己的啟動 log**（reactive tmux window 第一行），可一併確認。

- [ ] **Step 3: 窄場通道測 zone**

把 Go2 擺在窄通道（兩側家具、正前淨空 >1m）。
Run: `ros2 topic echo /state/reactive_stop/status --once` ; 同時跑 `lidar_front_sector.py`
Expected: `zone` = `clear`/`slow`（非 `danger`），±15° 淨空與 reactive 判定一致。

- [ ] **Step 4: 補 6/8 缺的關鍵證據 —— 修正後真的走過窄場**

Run: `python3 scripts/send_relative_goal.py --distance 0.5`（朝通道前方）
Expected: Go2 在窄場前進、`nav_paused=false`、不誤停、不撞。**錄影**。
Record: 是否走過、actual_distance、zone 全程、是否誤停。

**Acceptance（1.3）：** indoor_tight 一鍵啟動、參數生效、窄場 zone clear/slow、Go2 真的走過（錄到影片）。
> 若 Go2 仍誤停 → 降 `front_arc_deg:=15`、確認低速 ≤0.2；仍不行則 demo 只講「感測修正已驗、穿越是下一步」（報告 §7）。

### Task 1.4: 短距自走 smoke（只確認 F7 沒回來，別刷整天）

- [ ] **Step 1: 0.3m / 0.5m 各 2-3 次**

Run:
```bash
python3 scripts/send_relative_goal.py --distance 0.3   # ×2-3
python3 scripts/send_relative_goal.py --distance 0.5   # ×2-3
```
Expected: 每次 `success=True`、`actual_distance` 約 0.27m（離散步進，非校準距離——報告 §1 已標）。
Record: 每次 reached / actual_distance / 是否 no_progress。

**Acceptance（1.4）：** 無 F7（goal accept 但 0 移動 ABORT）重現即可。

### Task 1.5: 安全停障重測（兩 profile 各一次）

- [ ] **Step 1: open_space + indoor_tight 各測一次遇障停**

Run（各 profile 下）: `python3 scripts/send_relative_goal.py --distance 1.0`，途中人/箱擋路。
Expected: 在 danger 距離停下、`reactive_stop_active=true`、**不撞、不摔、不暴衝**；Foxglove 看得到 LiDAR + reactive_stop status。
Record: 停下距離、是否暴衝、profile。

**Acceptance（1.5）：** 兩 profile 都能擋路安全停。

### Task 1.6: stop-resume 實測（6/9 結論：停止擴測，降級）

> reactive_stop 用一般 mode（`progressive`），**不要 hold_brake**（hold_brake 故意不發 /nav/resume）。
> 6/9 HITL 已證明 auto-resume 機制會動，但 resume lunge 太急，停到 front 0.21m，Roy 判定 6/18 現場風險太高。**不要再花今天時間跑 2s/5s/10s 矩陣**；把 stop-resume 降級為「操作員確認安全後重新下達 / 遙控輔助」。

- [x] **Step 1: 記錄 6/9 實測結果並降級**

Observed: indoor_tight safe-stop 後移開障礙，Go2 會自動 resume，但 resume 後太急，最後 front 0.21m，機鼻幾乎貼牆。此行為不適合作為 6/18 demo 主能力。

| 測項 | 結果 | demo 判定 | 備註 |
|---|---|---|---|
| stop-resume | auto-resume 會動，但 lunge 過急 | 不採用 | safe-stop 可講；resume 不主秀 |

- [ ] **Step 2: 準備 fallback**

Runbook: 現場若要移動，障礙清除後由操作員手動 re-send、Studio button 或遙控輔助，不靠 auto-resume。
Record: fallback 是否可控、是否能在 Studio/Foxglove 顯示理由。

**Acceptance（1.6）：** stop-resume 已降級，不再追 auto-resume demo-ready。6/18 台詞固定為「操作員確認安全後重新下達 / 遙控輔助」。**禁止講**「障礙移開後會自己繼續」與「停了不會再走」（實際會 auto-resume，但不安全）。

### Task 1.7（P1，有空才做）: skew 診斷錄製

- [ ] **Step 1: 錄三 topic 跑 2-3 趟來回**

Run:
```bash
ros2 bag record -o ~/skew_$(date +%H%M) /cmd_vel_nav /amcl_pose /odom /scan_rplidar &
python3 scripts/send_relative_goal.py --distance 0.8   # 來回 2-3 趟
```
- [ ] **Step 2: 離線判讀（報告 §2d）**

判讀：一致同側偏=TF(H3)；每趟不同=步態(H1)；`/cmd_vel_nav angular.z` 本就大幅擺盪=DWB 在修(H2)。
Record: 結論指出是哪一層。

**Acceptance（1.7）：** 能指出歪斜是 TF/步態/DWB 哪一層，不只「走得歪」。

---

## Phase 1.5 — NAV-P1.5 Reactive Patrol v0（Bonus prototype，indoor-tight + safe-stop 過了才做）

> 目的：讓 Go2 在小空間**低速自主巡視 30-60s**，前方有障礙時停下或選較空方向嘗試短距移動 — 比一直 `goto_relative 0.5m` 更像四足移動感。**不是**自由巡邏/建圖/動態繞障/SLAM 探索。

**Files:** Create `scripts/reactive_patrol_v0.py`（讀 LiDAR sector → 選方向 → 發 `/nav/goto_relative`）

- 實作：**不直接發 `/cmd_vel`**，優先用現有 `/nav/goto_relative` action。每步 0.2-0.3m；前方 ±15° clear → 直走；blocked → 比左前/右前哪邊空 → `yaw_offset` ±0.5~0.8rad + 短距前進；都不空 → 停、等清場或重發。
- 安全硬閘：只在 `REACTIVE_PROFILE=indoor_tight`、`max_speed≤0.2`、`nav_ready=true`、`depth_clear=true`、e-stop 就位時允許。reactive_stop 永遠最高優先（safe-stop 不可被 patrol 蓋過）。
- 成功標準：30s 內 ≥3 個短步/轉向決策、**0 撞、0 暴衝**、遇 danger 停下。
- **能講**：低速自主巡視原型，依 LiDAR 選較安全方向。**不能講**：自由巡邏 / 完整建圖 / 動態繞障 / SLAM 探索。
- WSL-doable：sector→方向決策 + goto_relative 迴圈可 WSL 寫 + 假 LiDAR 單元測；**真實 patrol 需硬體 + e-stop**。

> Waypoint patrol（命名點 A/B/C）+ frontier exploration（邊建圖邊探索）= §9 future，今天不碰。

---

## Phase 2 — VISION HITL（清掉 nav stack，啟 brain stack）

> `pawai demo stop` 清 nav → `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`（或 `start_full_demo_tmux.sh`）。8GB 互斥，與 Phase 1 不同鏡。

### Task 2.1: 物體矩陣主測（最大缺口，決定 demo 主物體）

**Tool:** `scripts/obj_matrix_cap.py`（per-cell CSV）。先確認 object_perception 跑、白名單含目標類。

- [ ] **Step 1: 確認 object 事件活著 + 白名單**

Run: `ros2 topic echo /event/object_detected --once`
開 household 白名單: `ros2 param set /object_perception_node class_whitelist "[39,41,45,56,63,67,73]"`（bottle/cup/bowl/chair/laptop/phone/book）。若 false positive 太多，再切單類對照 `[56]`(chair)/`[63]`(laptop)/`[41]`(cup)。

- [ ] **Step 2: 跑 chair / laptop / cup × 0.7/1.0/1.5m × 光線（每格 5 trial）**

Run（每格一次，互動按 Enter 切 trial）:
```bash
for obj in chair laptop cup; do
  for d in 0.7 1.0 1.5; do
    python3 scripts/obj_matrix_cap.py --object $obj --distance $d --light normal --angle front --trials 5 --window 3
  done
done
# 主秀候選再各加逆光（至少近距 0.7/1.0）：
python3 scripts/obj_matrix_cap.py --object chair  --distance 1.0 --light backlit --angle front --trials 5
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light backlit --angle front --trials 5
python3 scripts/obj_matrix_cap.py --object cup    --distance 0.7 --light backlit --angle front --trials 5
```
> 0.7m 是近距保底判斷（你原始需求 0.7/1.0/1.5）；少了它無法判斷「拉近能不能救」。
Expected: 每格印 `CELL: PASS|DEGRADED|FAIL success=x/5 ...`，append 到 `artifacts/object_matrix/object_matrix.csv`。
Record: CSV（已自動寫）。

- [ ] **Step 3: 依 gate 定主物體（報告 §6）**

判定: 5 中 ≥4 = 主秀候選；=3 = 備援；<3 = 不上台；avg conf <0.45 = 不當主秀。
Record: 主秀物體決定（預期 chair，但**以實測為準**，不可預先 claim）。

**Acceptance（2.1）：** object_matrix.csv 有 chair/laptop/cup × 距離 × 光線數據；主物體已定。

### Task 2.2: cup 不穩專項（決定 cup 能否當備援）

- [ ] **Step 1: cup 多光線 × 背景**

Run:
```bash
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light normal  --angle front --trials 5 --notes "近距保底"
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light backlit --angle front --trials 5 --notes "深背景"
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light dim     --angle front --trials 5 --notes "淺背景"
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light side    --angle 45    --trials 5
```
Record: misclass 欄位（注意低光紅杯被報「黑色杯子」——報告 §4）。
> ⚠️ `obj_matrix_cap.py` 只輸出 per-cell CSV，**不自動存 debug image / lux / per-trial raw**。研究杯子玄學要深入 → 現場手動補照片 + lux + 背景描述，或先做 Phase 3.3 raw JSONL dump。

**Acceptance（2.2）：** cup 降級決策有數據支撐；台詞限「約 1 公尺、桌上水杯」，不講 2m/地上/絆倒。

### Task 2.3: sitting 可靠度（VIS-4 greet 硬依賴）

- [ ] **Step 1: 站/坐/站 10-20 組**

Run: `ros2 topic echo /event/pose_detected`（觀察 sitting 判定）；操作員站/坐/站各 10-20 次，數誤判。
Record: 誤判率、`pose_vote_confidence`（注意：是投票比例非分類器 conf，報告 §3）。

- [ ] **Step 2: 依 gate 決定（報告 §6）**

若 sitting 誤判 >10%:
```bash
ros2 param set /brain_node greet_require_sitting false
```
台詞改「Roy，歡迎回來，我看到你了」（去掉「坐下來了」）。
Record: greet_require_sitting 設定、台詞版本。

**Acceptance（2.3）：** sitting 可靠度有數據；greet 台詞鎖定（穩→講坐下；不穩→去掉）。

### Task 2.4: VIS-4 具名問候快速重驗

- [ ] **Step 1: 進場觸發**

遮臉/離框 ~5s 再回到鏡頭前（unknown→known 轉變才觸發，非 steady-state）。
Expected: TTS 講出「roy，歡迎回來…」；20s/人 cooldown。
Record: 是否觸發、台詞、face sim 值（過期 enroll 會掉到 ~0.2，需 re-enroll）。

**Acceptance（2.4）：** 具名問候實機觸發；若 sim 低 → `pawai face enroll/rebuild` 重訓。

### Task 2.5: gesture thumbs_up（只測這一個）

- [ ] **Step 1: idle 誤觸 + 正觸**

Run: idle 30s 數誤觸（必須=0）；比 thumbs_up 看是否簡單回應（不引出 wiggle confirm）。
Record: idle false-trigger 數、thumbs_up 是否回應。

**Acceptance（2.5）：** idle false-trigger=0；thumbs_up 可動。台詞只講「靜態手勢」，**不可洗白失敗的 wave**（recall=0，報告 §1）。

### Task 2.6: VIS-7 Studio 證據截圖

- [ ] **Step 1: 截圖證據鏈**

開 Studio frontend，跑一輪互動，截圖**同時**含：4 感知 chip（face/object/pose/gesture）+ brain trace + tts bubble。
Expected: gateway boot log 印「10 String + /tts + 2 Bool」。
Record: 截圖存證。
> **不可宣稱** LED pass/fail chip wall（前端無 `/api/scoreboard`，報告 §6）。

**Acceptance（2.6）：** 一張同框顯示完整證據鏈的截圖。

### Task 2.7: VIS-8 under-load 壓測

- [ ] **Step 1: face+object+pose/gesture+Studio video 同跑，記資源**

Run: `pawai status` / `jetson-status` skill，記 RAM/CPU/GPU/temp/object Hz/face Hz/Studio 延遲。
Record: idle baseline 已有（RAM 3.65G/CPU~80%/58.7°C）；補 under-load 數字。卡頓優先查 Studio video-bridge JPEG+WS（報告 §3）。

**Acceptance（2.7）：** 一組 under-load 資源數字；確認不過熱/不爆 RAM。

### Task 2.8: Safety refusal 快速回歸（6/18 強亮點，不可被矩陣擠掉）

- [ ] **Step 1: 「請翻跟斗」×3**

Run: Studio 文字輸入或語音「請翻跟斗」連發 3 次；同時 `ros2 topic echo /brain/skill_result`。
Expected: **blocked 3/3**、Go2 完全不動、TTS 講拒絕語、Brain trace 顯示 blocked（`banned_api` / safety gate）。
Record: 3/3 是否全 blocked、Go2 是否零移動、trace 截圖。
> 觀測權威是 terminal `/brain/skill_result`（Studio 紅 BLOCKED badge 可能被綠 completed 一閃蓋掉，6/6 audit）。

**Acceptance（2.8）：** 翻跟斗 3/3 blocked、Go2 零移動、trace 有 blocked 證據。

---

## Phase 3 — Optional WSL 工具（HITL 暴露需求才做，可 subagent/inline）

> 這 3 個 6/9 還沒做，刻意不擴張 scope。HITL 證明需要才補。

### Task 3.1（若 1.1 硬 kill 自癒太慢）: odom-tied liveness watchdog

**Files:** Modify `nav_capability/nav_capability/nav_action_server_node.py`
- [ ] 加：execute loop 中若 `_odom_alive()` 連續 N 秒 false **且** client 已無 → cancel goal。**必須**不在 AMCL/odom 瞬斷（<2s）時誤殺前進中 goal（報告 §8 T1 caveat）。需硬體驗誤殺率。

### Task 3.2（若 1.7 要常錄）: skew 錄製腳本

**Files:** Create `scripts/record_skew_diag.sh`
- [ ] 包 `ros2 bag record /cmd_vel_nav /amcl_pose /odom /scan_rplidar` + 提示跑 2-3 趟 goto，`set -euo pipefail` + grep 尾 `|| true`。

### Task 3.3（若要保留 raw 供離線 eval）: object per-trial JSONL dump

**Files:** Modify `scripts/obj_matrix_cap.py`
- [ ] 加 `--raw-jsonl` 選項：除 per-cell CSV 外，另寫每 trial 的 detected/conf/bbox JSONL（供 §9 item-5 離線 Supervision mAP）。預設關。

### Task 3.4（VIS-7 自動化）: Studio 證據檢查腳本

**Files:** Create `scripts/check_studio_evidence.sh`
- [ ] echo 4 感知 topic + `/brain/skill_result` + `/tts` 各一次，`ros2 topic info -v` 證 publisher 非 mock，確認 gateway「10 String + /tts + 2 Bool」boot log。

---

## Phase 4 — 收尾：寫回結果 + 鎖 demo 台詞

### Task 4.1: HITL 結果寫回 project-status + claim 表

**Files:** Modify `references/project-status.md`（頂部加 6/9 段）；Modify `docs/pawai-brain/research/2026-06-09-nav-vision-execution-research.md` §1 truth table（把驗過的能力升級/標記）

- [ ] **Step 1:** 把每個 Phase 1/2 task 的 Record 結果填回。能力升級規則：實機觀測到結束行為 → `HARDWARE_PROVEN`；只看到中間狀態 → 維持 `WIRED_RUNTIME`；未達 gate → 誠實標 FAIL/INSUFFICIENT。
- [ ] **Step 2:** Commit：`docs: 6/9 HITL results — <能力升級摘要>`。

### Task 4.2: 鎖 demo flow + fallback 台詞

**Files:** 視結果更新 demo flow 文件（`docs/mission/2026-06-18-demo-flow-plan.md` 或 production-plan）

- [ ] **Step 1:** 依 HITL 結果鎖 S1(nav)/S2(vision) 每段「能講 / 不能講 / fallback 台詞」（報告 §7 為基準，用實測收緊或放寬）。
- [ ] **Step 2:** 鎖主物體、greet 台詞（sitting 版/非 sitting 版）、stop-resume 台詞（auto/手動）。

**Acceptance（Phase 4）：** project-status 有 6/9 HITL 段；claim 表反映實測；demo 台詞鎖定且無 overclaim。

---

## 執行順序建議（報告 §5 + 你的判斷）

1. **Phase 0**（commit + deploy）— 30 分。
2. **先 Phase 1 NAV**（你的判斷：先收 blocker）：1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 →(1.7 有空)。
3. **清 stack，Phase 2 VISION**：2.1（矩陣 chair/laptop/cup × 0.7/1.0/1.5 × normal/backlit，最大未知）→ 2.3 sitting → 2.4 greet → 2.2 cup 專項 → 2.5 gesture → 2.6 Studio → 2.8 safety refusal → 2.7 壓測。
4. **Phase 4** 收尾鎖台詞。Phase 3 只在 HITL 暴露需求時插入。

> nav stack 與 brain stack **不能同跑**（8GB 互斥）→ 全流程 demo 是 S1(nav 鏡) + S2-S7(brain 鏡) **兩段**，不是一鏡到底。

---

## Self-Review（對照剩餘工作清單）

- ✅ nav orphan 驗證（1.1）、LiDAR 扇區（1.2）、indoor-tight 實機（1.3）、短距 smoke（1.4）、safe-stop（1.5）已收；stop-resume（1.6）已**降級為不主秀 auto-resume**；skew（1.7）保留 optional，不阻擋今天切 vision。
- ✅ object 矩陣（2.1）、cup（2.2）、sitting（2.3）、greet（2.4）、gesture（2.5）、Studio evidence（2.6）、under-load（2.7）— 涵蓋 vision 全部。
- ✅ demo flow 收尾（4.2）— 對應「沒完成 demo flow」。
- ✅ 工具部署（0.2）+ 結果寫回（4.1）。
- 註：Phase 1/2 是**硬體 HITL（Roy 執行）**，非 subagent code task；Phase 3 才是 WSL code（optional）。
