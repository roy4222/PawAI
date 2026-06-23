# Act1 demo_forward — Roy 第一次 live 測試 Runbook（e-stop 在手）

> 日期：2026-06-15　狀態：**NEEDS_ROY_ESTOP_TEST**（code 改好、邏輯驗過、**真機 motion 尚未驗**）
> 配套：`scripts/start_reactive_forward_demo.sh` / `scripts/act1_forward.sh` / `scripts/act1_voice_trigger.py`
> 定位：✅ 短距直行 + 正前障礙安全停車　❌ 不是自主避障 / 不是動態繞障 / 不是走到人面前

---

## 0. 為什麼要這份（6/15 撞車根因 + 修法）

6/15 上一版走「整合 mux」路徑撞牆。**根因（Cloud 唯讀調查，非臆測）**：
`twist_mux` 4.x **沒有 output timer、純 event-driven**，每個 input 有 0.5s timeout。一旦
reactive 對 `/cmd_vel_obstacle` 的供給中斷 0.5s（enable=false 變沉默 / node 被殺 / enable
開太久結尾才 force-stop）→ mux 停止輸出 → driver 收不到新 `/cmd_vel` → **Go2 繼續執行上一個
Move(0.6) 滑行 2-3s（sport timeout）→ 撞**。standalone 直連沒有這層中介。

**修法**：改回 **6/15 已實機驗過會停的 standalone `/cmd_vel` 直連**（reactive 每個 0 直達
driver → StopMove）。已驗證的部分：
- ✅ reactive danger→發 0、driver zero→StopMove 的**單元邏輯**（42 tests，`go2_robot_sdk/test/`）。
- ❌ **真機「狗真的走 + 真的停」尚未在本 build 驗過** → 就是這份 runbook 要做的事。

---

## 1. 前置（缺一不可）

1. **Go2 撞後實體狀態確認**：站得穩、無損、driver 連得上（`ros2 node list | grep go2_driver`=1）。
2. **實體 e-stop 遙控器在手**，整個過程不離手。它是最終急停，永遠優先於任何軟體。
3. **場地**：正前方淨空 ~1.5–2m，左右無貼牆家具（孤立空間，不是 6/14 那種右前角有牆的窄場）。
4. **brain demo 已起**：`pawai demo start --with-lidar`，`/scan_rplidar` ~11–12Hz。

---

## 2. 啟動 Act1（standalone + 唯一 publisher，fail-safe）

```bash
# 預設(ACT1_KILL_COMPETITORS=1)就會殺 /cmd_vel 競爭者(twist_mux/teleop/joy)+啟動後驗 publisher==1。
# brain 動作走 /webrtc_req、不用 /cmd_vel，殺這三個不影響 face/object/gesture/safety/TTS。
bash ~/elder_and_dog/scripts/start_reactive_forward_demo.sh
```

腳本尾端會印 **`✓ reactive 就緒、無競爭 node、/cmd_vel publisher=2`**；若印 **`🔴 拒絕`**
代表競爭 node（twist_mux/teleop/joy）還在 → 已自動關閉 session，照提示處置後重跑（**不要硬上**）。
亦可 `tmux attach -t act1react`：
- window `verify`：`競爭者` 必須 **(none)**（**這才是關鍵**）、`reactive enable` **False**、
  `/cmd_vel publisher` **=2 正常**（reactive + voice node 的 stop-pub，協調不打架；只要競爭者空就對）。
- window `reactive` / `voice`：分別是 reactive node 與語音觸發器。

> **競爭者非空 或 reactive 沒起 → 不要進 motion**（gate 偵測到競爭 node / publisher>2 已會自動拒絕，仍親眼確認一次）。

---

## 3. 驗收（兩步，e-stop 在手，每步不穩立刻按）

### Step 1 — Clear path（前方淨空）
```bash
bash ~/elder_and_dog/scripts/act1_forward.sh
```
**期望**：Go2 往前走一小段（FORWARD_S 預設 **1.0s @0.6m/s ≈ 0.6m**，6/15 撞車後從 2.0s 縮短）→ 超時自動 force-stop + 鎖回。
**通過**：0 撞、0 亂轉、走完自己停、`enable=False`。

### Step 2 — Blocked path（測停障）
```bash
bash ~/elder_and_dog/scripts/act1_forward.sh
```
- **正前 ~1.0m 放障礙**（< danger 1.5）：Go2 **一啟動就 danger、原地不動**（reactive 立刻發 0）。
- **正前 ~1.8–2.2m 放障礙**（> danger 1.5）：Go2 走近到 ~1.5m 處 reactive 發 0 → 停（看「走近後停」）。
**期望**：兩種擺法都不撞。
**通過**：障礙前停住、不撞。
（也可先 `act1_forward.sh hold` 驗立即急停。）

### Step 3 — 語音 / Studio 文字觸發（前方淨空）
- 語音說「往前走」或 Studio 文字輸入「往前走一點」。
- **期望**：聽到「好，我往前走一點。」→ Go2 前進一小段 → 停。
- 前方有障礙時說「往前走」→ **期望**：聽到「前方有障礙，我先停在這裡。」→ **不動**。
- 感知未就緒（`/scan_rplidar` stale）→ 「目前前方感知尚未就緒，我先不移動。」→ 不動。

---

## 4. 通過 / 不通過

- **全通過**：Act1 可作為 6/18 一個**短距前進 + 正前停障**的分段（誠實措辭，非自主避障）。
- **任一不穩**（亂轉 / 不停 / 滑行 / 觸發不可靠）：**立刻 e-stop + `act1_forward.sh hold`**，
  Act1 走 fallback（遙控輔助 / 影片），**不要硬上、不要動到已成功的 S2-S5**。

---

## 5. 收手

```bash
bash ~/elder_and_dog/scripts/act1_forward.sh hold   # 確保停 + 鎖
tmux kill-session -t act1react                       # 關 reactive + voice
# 若稍早 ACT1_KILL_COMPETITORS=1 殺了 mux/joy、之後要完整 demo → 重起 brain demo
```

---

## 6. 殘留風險（誠實揭露，治本歸 post-6/18）

- 🟢 **6/15 撞車後 danger 1.1→1.5m**：Go2 sport 速度地板 0.5（無法更慢），0.6m/s + WebRTC/sport 煞停延遲
  + LiDAR 裝機鼻後 ~0.32m → danger=1.1 時「看到 1.1m」到「機鼻停」常只剩 ~30cm，遇延遲尖峰/側前盲區就撞。
  1.5m 多 ~0.4m 緩衝。env 可調：`ACT1_DANGER_M=1.8`（更早停）/ `=1.1`（回舊調校，不建議）。
- 🔴 **±18° 窄錐 = 側前盲區（danger 加大也修不掉，最該記住）**：demo_forward 用 `front_arc_deg=18` + `normal_speed=0.6`
  （Roy 拍板，為短距正前 + 避開 Go2 MIN_X 0.5）。±18° 在 1.5m 只覆蓋正前約 **±0.49m 寬** →
  **稍微偏離正前的障礙（桌腳/牆角/人的腳）落在錐外、不算 danger、不會停**（0.6m/s + 機鼻前 0.5m 會撞）。
  ⟹ 加大 danger 只解「正前停太晚」，**不解側前盲區**：§1 仍要求正前淨空、左右無貼牆/近身家具、障礙擺正前正中。
  這與專案「窄錐必須綁低速 ≤0.2」鐵律（`docs/architecture/navigation/CLAUDE.md`）相違，能成立**完全賭在場地**：
  故 §1 要求正前淨空、**左右無貼牆/近身家具**、障礙擺**正前正中**。要側向覆蓋＝錐放寬 ±30°
  （犧牲正前精度）或速度壓 ≤0.2（但撞 Go2 MIN_X 0.5、需另解）。
- standalone 直連已消除「mux 中介層 timeout 滑行」，但若 **reactive node 在前進中被殺**，
  driver 仍會因 Go2「最後 Move 滑行」滑 2-3s。→ 過程中 reactive 不要去 kill；e-stop 是底線。
- **停車雙重保證（A-2 修 + 對抗複查）**：operator 手動跑 `act1_forward.sh` → bash `trap
  EXIT/TERM/INT` 保證 force_stop。voice 路徑 → 即使 subprocess timeout **直接 SIGKILL bash（bash
  trap 不會跑）**，voice node 的 **`finally._guarantee_stop()`（Python 端、一定執行）** 也會
  `enable=false` + 直發 0 到 /cmd_vel → StopMove。**殘留**：SIGKILL 情況下 `enable=false` 傳播
  ~1-2s 內 reactive 可能再發幾個 0.6（多走 ~1-2s）→ 由 reactive danger-stop（單一 publisher 下有效）
  + e-stop 兜底。
- **唯一 publisher gate 已 fail-closed**（對抗複查）：start 腳本輪詢等「reactive 就緒且 /cmd_vel
  剛好 1 publisher」才放行；偵測 >1 或 ~12s 等不到 → 自動關 session 拒絕（不靠人讀 verify）。
- **`_guarantee_stop` 真正讓狗停的是 `enable=false`**（對抗複查 #3）：那串 0 與 reactive 殘留的
  0.6 在 driver 是交錯流（非覆蓋），所以 `enable=false` 已改 **retry 3 次 + 失敗大聲 log**（不再
  靜默吞）；多次失敗時靠 reactive scan danger-stop + e-stop 兜底。
- **殘留 #1（低機率）**：voice node 的停車在 daemon thread，若**正好在 ~2s motion 窗按 Ctrl-C
  關 voice node**，`_guarantee_stop` 可能被 shutdown 競態殺到一半。→ 要停狗**用實體 e-stop，不要靠
  Ctrl-C voice node**（保留 daemon=true 是為了 Ctrl-C 能即時退出、不卡 14s）。
- ⚠️ **本整套 Act1 是「靜態/單元/三輪對抗複查」驗過，不是 motion 實測**：第一次 live 的「狗真的走+真的停」
  只有你手持 e-stop 能驗。
- **治本**＝ driver 層加「cmd_vel 供給 watchdog」（>Ns 沒收到且上一個非零 Move → 自動 StopMove），
  把 Go2 sport 最後-Move 滑行在 actuation 層收口。改 actuation、需真機校 → **排 post-6/18**
  （見 unified-demo plan LT-6 / Cloud A 調查報告修法 D）。本次**不做**。
