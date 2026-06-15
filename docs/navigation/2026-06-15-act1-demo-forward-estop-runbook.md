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

## 2. 啟動 Act1（standalone + 唯一 publisher）

```bash
# brain demo 預設有 twist_mux + joy 也發 /cmd_vel → 必須讓 reactive 成唯一 publisher。
# brain 動作走 /webrtc_req、不用 /cmd_vel，殺這三個不影響 face/object/gesture/safety/TTS。
ACT1_KILL_COMPETITORS=1 bash ~/elder_and_dog/scripts/start_reactive_forward_demo.sh
```

**啟動後務必看 `verify` window**（`tmux attach -t act1react` → window `verify`）：
- `/cmd_vel publisher count` **必須 = 1**（就是 reactive）。≠1 → **停**，先查競爭 publisher。
- `競爭者 (twist_mux/teleop/joy)` 必須 **(none)**。
- `reactive enable` 必須 **False**（鎖住、無 motion）。

> 三項任一不對 → 不要進 motion。

---

## 3. 驗收（兩步，e-stop 在手，每步不穩立刻按）

### Step 1 — Clear path（前方淨空）
```bash
bash ~/elder_and_dog/scripts/act1_forward.sh
```
**期望**：Go2 往前走一小段（≤~1.4m 上限或更短）→ 超時自動 force-stop + 鎖回。
**通過**：0 撞、0 亂轉、走完自己停、`enable=False`。

### Step 2 — Blocked path（正前方 ~0.8–1.0m 放障礙）
```bash
bash ~/elder_and_dog/scripts/act1_forward.sh
```
**期望**：Go2 一啟動就偵測到 danger（或走極短距離）→ reactive 發 0 → 停。
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

- standalone 直連已消除「mux 中介層 timeout 滑行」，但若 **reactive node 在前進中被殺**，
  driver 仍會因 Go2「最後 Move 滑行」滑 2-3s。→ 過程中 reactive 不要去 kill；e-stop 是底線。
- **治本**＝ driver 層加「cmd_vel 供給 watchdog」（>Ns 沒收到且上一個非零 Move → 自動 StopMove），
  把 Go2 sport 最後-Move 滑行在 actuation 層收口。改 actuation、需真機校 → **排 post-6/18**
  （見 unified-demo plan LT-6 / Cloud A 調查報告修法 D）。本次**不做**。
