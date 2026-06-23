# 6/18 Demo Convergence — Tonight HITL Runbook (2026-06-14)

> **For the operator (Roy) at the Go2 + Jetson.** This is an execution runbook, not a code plan. Each step = **command → expected output → abort判準**. Tick the boxes. Use `python3 -m pytest` form on dev; on Jetson use `.zsh` + ROS sourced.
> **不要再發散。** 今晚只做：deploy → no-motion profiling → S2–S5 单测 → S1 低速 reactive_stop 障礙停 → 完整五幕 rehearsal。**不碰 goto_relative、不換模型、不做動態繞障、不開 auto-advance。**

**Goal:** 把 6/18 live 五幕收斂成「最小可跑 + 有 fallback」的真機驗收，今晚產出一張 go/no-go 表 + 兩輪 rehearsal。

**Approach:** 五幕分兩個 stack 時段（Act1 nav stack ／ Act2–5 brain stack，各自起 Go2 driver、8GB + 單一 Go2 連線互斥、中間操作員過場）。FLOOR=手動切幕 + canned；auto-advance 今晚不碰。S1 走 standalone reactive_stop 障礙停（A 版），不穩就降 B（遙控+LiDAR 證據）/ C（影片）。

**Environment:** Jetson Orin Nano 8GB（zsh / `setup.zsh`）、Go2 Pro（WebRTC 192.168.123.161）、RPLIDAR A2M12、D435、USB 喇叭/麥、e-stop 在手。SSH `jetson-nano`，Jetson repo `~/elder_and_dog`。

---

## §0 鎖定決策（憲法，今晚不再 re-litigate）

- **Act1 = A 障礙停**：standalone `reactive_stop`，不建圖、不設 initialpose、LiDAR-only、~0.5 m/s（Go2 MIN_X 底線，不能慢爬）。fallback ladder：A 障礙停 → B 遙控+Foxglove/LiDAR 證據 → C 影片。**A+「自動找 Roy」不做。**
- **S1 claim**：只講「低速前進 + LiDAR 偵測障礙停下 + Studio/Foxglove 即時感知」。**不講**自主導航 / 動態繞障 / D435+LiDAR 融合 / 深度避障 / 可靠走滿 2m。
- **offline_mode**：先 merge canonical 版（§1），現場 offline 切換以 `ros2 param set` 為保險，Studio toggle 為加分。
- **object**：今晚只錄 baseline 證據（cup/bottle/phone/chair × 0.7/1.0/1.5m），**不換 runtime 模型**（yolo26n@640 維持）；26s = BLOCKED。
- **auto-advance 今晚完全不碰**，6/18 全程手動切幕（Studio hidden 鈕 / `ros2 param set demo_phase`）。
- **8GB 互斥**：nav stack 與 brain stack 不同跑；兩個 tmux 腳本互斥；切換要先清乾淨再起下一個。
- **紅線（任一觸發，motion 立即停）**：Go2 一開始就明顯歪 / LiDAR 0Hz 或 topic 不穩 / 前方 danger 但 Go2 還在走 / 機鼻 <0.4–0.5m 還沒停 / 側邊家具進路徑 / 障礙在掃描平面上卻不停（offset/TF 反了）/ 需連續靠 e-stop 才收得住。e-stop = `nav_capability/scripts/emergency_stop.py engage` 或 Go2 `StopMove(1003)`；**禁對運動中 Go2 送 `Damp(1001)`**。

---

## §1 Pre-flight：merge offline_mode + 同步 main（~10 分，Cloud 主導，Roy 等綠）

> 目的：把 `codex/pre618-offline-mode`（`3c0a949`，brain `/brain/offline_mode` subscriber + 5 測，418 綠）合進 main，讓 deploy 拿到 canonical 版（與你草稿同碼 + 有測）。

- [ ] **Step 1.1 — Cloud：push branch + 開 PR + 等 CI 綠 + admin rebase-merge**（CI launch_testing 修法已在 main，預期全綠）。
- [ ] **Step 1.2 — Roy：丟掉本機未 commit 草稿、拉 canonical**
```bash
cd ~/newLife/elder_and_dog   # 開發機
git checkout -- interaction_executive/interaction_executive/brain_node.py
git pull --ff-only origin main
```
Expected：`brain_node.py` 變成 merged 版（含 `_set_offline_mode` + subscriber + 測試）。
Abort：若 pull 有衝突 → `git status` 看哪檔，多半是 brain_node.py，直接 `git checkout --` 再 pull。

> CLI doc（`6731d33`）+ object benchmark（`ac4495c`/`a499115`）**暫不 merge**，等今晚 HITL 收尾批次合（純加法、無衝突）。

---

## §2 Phase A — Deploy + Build + Smoke（0:00–0:45）

- [ ] **Step A.1 — Deploy**
```bash
pawai jetson deploy
```
Expected：rsync 完成、無 `$'\r'` 錯（CRLF）、無 `--delete` 轟 runtime/。
Abort：若腳本「靜默成功但其實沒跑」→ 下一步用 `tmux ls` 抓。`.env` CRLF：`ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local"`。

- [ ] **Step A.2 — Jetson build 改過的 packages（rsync 不會 rebuild install/）**
```bash
ssh jetson-nano
cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh
colcon build --packages-select interaction_executive speech_processor
source install/setup.zsh
```
Expected：`Finished <<< interaction_executive` / `speech_processor`，無 error。
Abort：`option --editable not recognized` → `pip install --user "setuptools<70"`。build fail → 停，貼 log。

- [ ] **Step A.3 — 起 brain demo stack**
```bash
bash .claude/skills/brain-studio-lane/scripts/start.sh demo
# 或 Jetson 上：bash scripts/start_full_demo_tmux.sh
```
Expected：tmux 13 windows 起來；TTS=edge_tts、USB 喇叭。

- [ ] **Step A.4 — 親眼驗（不信 CLI 的 ✓）**
```bash
ssh jetson-nano "tmux ls; ros2 node list | sort"
```
Expected：看到 brain_node / 5 perception / tts / asr / gateway 等；node 數對。
Abort：node 數不對 / 缺 brain_node → 停，看該 window log。

- [ ] **Step A.5 — Smoke**
```bash
pawai smoke brain      # SSH 上 Jetson 跑 5 輪語音 E2E
pawai smoke vision
pawai smoke object
pawai smoke nav --static   # no-motion nav smoke
```
Expected：smoke brain 5/5 出聲；vision/object 有事件；nav --static 綠。
Abort：任一紅 → 停修，**不進 Phase B**。

---

## §3 Phase B — Co-run Profiling（no-motion，0:45–1:45）

> **角色（已釐清）**：今晚 profiling 不是測「brain+full nav 共存」（Act1 是 standalone reactive_stop、與 brain 各自起 Go2 driver、本就分時段，共存 moot）。今晚 profiling = **(1) brain 套自身 8GB 健康度、(2) 之後切換成本參考**。全程 **零 motion、不發 cmd_vel/goto**。

- [ ] **Step B.1 — 配置 A：brain baseline**
```bash
bash scripts/corun_profile.sh --config A --duration 240 --interval 5
python3 scripts/corun_profile_parse.py --config A
```
Expected：CSV 寫到 `runtime/profiling/2026-06-13-configA.csv`；逐指標 PASS/WARNING/FAIL；RAM used、temp、object/face Hz。
Abort：`OOM-RISK ABORT`（RAM 持續 >6.5GB ≥10s）→ 立即清場，記錄。

- [ ] **Step B.2 — 配置 B：brain + raw LiDAR/Foxglove（不開完整 Nav2）**
```bash
bash scripts/corun_profile.sh --config B --duration 240 --interval 5
python3 scripts/corun_profile_parse.py --config B
```
Expected：加 sllidar 後 RAM/temp 變化、LiDAR Hz ~10。
Abort：同 B.1。**不要在 demo Jetson 同跑 brain 套 + nav 套的 Go2 driver。**

- [ ] **Step B.3 — 判讀**：brain baseline 穩否？切換成本（停 brain 套→起 nav 套 約多久）？
判定：brain baseline 不穩 → 先修 brain，S1 全退 fallback；brain 穩 → 照計畫進 Phase C/D。

---

## §4 Phase C — S2–S5 单测（手動切幕，1:45–2:45）

> 用 Studio `?dev=1` hidden 五幕鈕，或 `ros2 param set /brain_node demo_phase <phase>`。先**不開 auto**。

- [ ] **Step C.1 — S2 身分感知問候**
```bash
ros2 param set /brain_node demo_phase s2_greet
# Roy 進框（known face）
```
Expected：known face 進場即問候（不靠遮臉重進場 gotcha #1）；**不卡 sitting**（gotcha #2）；20s cooldown 不重發。台詞「Roy，歡迎回來，我已確認你平安在這裡」。
Abort：sim<0.7 判 unknown → 先 `pawai face enroll roy` + rebuild + 重啟 face node（face_db 先 `ls` 確認真檔名、移走 `_backup*`）。

- [ ] **Step C.2 — S3 情境關懷（cup live）**
```bash
ros2 param set /brain_node demo_phase s3_pose_object
# Roy 坐著 + 桌上放杯子
```
Expected：看到 cup → 補水台詞；sitting=bonus（不到不卡）。**順手錄 cup/bottle/phone/chair @ 0.7/1.0/1.5m 影片**（給 object benchmark；不換模型）。
Abort：pose 不穩 → 台詞**不要講「你坐著」**；cup 在掃描距離卻沒偵 → 換道具位置/角度。

- [ ] **Step C.3 — S4 意圖確認式手勢（先台詞、wiggle 可選）**
```bash
ros2 param set /brain_node demo_phase s4_gesture
# 比 peace → PawAI 問「比 OK 我就確認」→ 比 OK
```
Expected：手勢→二階段確認→「已確認 Roy 狀態正常」（**台詞版，不動 Go2**）。30s idle 不 spam。
Abort：confirm 黑洞（pending 不 timeout）→ `gesture_enabled false` 即時收。**wiggle（Go2 motion）需 e-stop，列 Phase D 之後可選。**

- [ ] **Step C.4 — S5 安全拒絕（rule-first，no LLM）**
```bash
ros2 param set /brain_node demo_phase s5_safety
# 在 Studio chat 打字輸入「PawAI，請翻跟斗」(走 demo 真實路徑：Studio→gateway text_input→brain SafetyLayer)
# 再用語音講「PawAI，請翻跟斗」各驗一次
```
Expected：rule-first 拒絕「這個動作不安全，我不能執行」；Go2 **不動**；Studio/trace 顯示 BLOCKED_BY_SAFETY 紅。`s5_safety=∅` 不擋 SafetyLayer。
Abort：若沒擋 → 確認 `UNSAFE_KEYWORDS_REJECT` 含「翻跟斗」（已含）；不要臨時換「衝向人群」（不在 keyword 清單、視覺也對不上）。

- [ ] **Step C.5 — offline 切換驗**
```bash
ros2 param set /brain_node offline_mode true     # 保險路徑（必驗）
# 若 Studio toggle 也接通（canonical merged）→ 按按鈕應同效
ros2 param set /brain_node offline_mode false     # 還原 byte-identical
```
Expected：offline=true → LLM 路徑秒回 canned、不重啟、無 silent fail；false → 還原。

---

## §5 Phase D — S1 低速 reactive_stop 障礙停（2:45–4:00，**唯一 motion 段，e-stop 強制**）

> **三階段，不要直接衝。** 全程 e-stop 在手；§0 紅線任一觸發立即停。

- [ ] **Step D.1 — Stage 1：no-motion 前置（Go2 不動）**
> ⚠ **不能直接跑 `start_reactive_stop_tmux.sh`**（它接 `/cmd_vel` → Go2 一淨空就走）。先只起 sllidar + reactive_stop 發**預設 `/cmd_vel_obstacle`（不接 driver）**，或不起 Go2 driver。
```bash
ros2 topic hz /scan_rplidar            # 應 ~10Hz
ros2 topic echo /state/nav/safety --once   # zone 狀態
# 手動把障礙放前方 → 看 zone 由 clear→slow→danger
ros2 node list | grep -iE 'go2_driver|nav2|amcl'   # 確認沒有 nav2/amcl/hot teleop 混入
```
Expected：LiDAR ~10Hz；放障礙 zone 變 danger。
Abort：LiDAR <10Hz/0Hz、有殘留 nav2/amcl → 停清場。

- [ ] **Step D.2 — Stage 2：micro motion（0.3–0.5m，空曠）**
```bash
bash scripts/start_reactive_stop_tmux.sh   # 起 sllidar + Go2 driver + reactive_stop→/cmd_vel
# 前方淨空 → Go2 以 ~0.5 m/s 直走一小段
```
Expected：Go2 真的直走、無明顯偏航。
Abort（紅線）：一歪 / 加速 / 靠近家具 → **立即 e-stop**。

- [ ] **Step D.3 — Stage 3：障礙停三輪**
> 障礙物**要夠高、跨過 2D LiDAR 掃描平面**（椅背/疊高紙箱/人站著；矮箱在掃描線下會看不到 → 不停 → 撞）。放在前方約 2–2.5m。
```bash
# 同 D.2 stack；Go2 前進 → 應在障礙前 ~1.1m 停（StopMove 1003）
```
Expected：**3 次都在障礙前安全停、0 撞、0 失控**。
Abort：障礙在掃描平面卻不停 → offset/TF 反了，立即 e-stop + 停。三輪不穩 → **Act1 降 B（遙控+LiDAR 證據）/ C（影片）**，不要再丟時間進 nav。

- [ ] **Step D.4 — 錄 Act1 影片（不論 A 過不過，C 保底素材必錄）**

---

## §6 Phase E — 完整五幕 rehearsal（4:00–7:00）

- [ ] **Step E.1 — 切換彩排一次（nav→brain，必做）**
```bash
# 停 nav 套：
ssh jetson-nano "pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud; pkill -9 sllidar; pkill -9 reactive_stop"
sleep 12   # 等 Go2 WebRTC 重連（會先 FROZEN→FAILED，第二 candidate 才成功）
# 起 brain 套（§A.3）
```
Expected：brain 套乾淨起來、Go2 driver 不打架。過場台詞：「剛剛展示的是 PawAI 的空間移動與安全停障；接下來切到互動模式。」
Abort：brain 套起不來（多 driver 殘留）→ 再 pkill 一輪 + 多等。

- [ ] **Step E.2 — 第一輪：保守版**（S1 遙控/低速 + S2–S5 手動切幕 + canned fallback）。全程不開 auto。記每幕 pass/fail。

- [ ] **Step E.3 — 修最小 blocker（5:00–6:00，不開新功能）**。

- [ ] **Step E.4 — 第二輪：理想版**（S1 走 A 若三輪過、否則 B；S2–S5 仍手動 floor；低光/網路慢各測一次）。定稿每幕 fallback。

- [ ] **Step E.5 — 收工：填 go/no-go 表（§7）、`pawai evidence pull` 拉 trace、若穩 `git tag` checkpoint。**

---

## §7 go/no-go 表（收工填）

| 幕 | 採用方案 | fallback | trace 證據 | 上 6/18? |
|---|---|---|---|---|
| **Act1 Mobility** | A 障礙停（reactive_stop）/ B 遙控+LiDAR / C 影片 | B→C | scan + zone danger | ☐ |
| **Act2 Identity** | face greet（平安確認） | generic greet（不秀名） | greet trace | ☐ |
| **Act3 Caring** | cup 補水提醒 | canned cup / generic | object_detected cup | ☐ |
| **Act4 Gesture** | peace→OK 台詞確認（wiggle 可選/需 e-stop） | canned confirm | pending_confirm trace | ☐ |
| **Act5 Safety** | 翻跟斗 rule-first 拒 | typed command | BLOCKED_BY_SAFETY | ☐ |

---

## §8 Fallback ladders（全域）

- **每幕 max_wait**：S1 10–20s / S2 3–5s / S3 5–8s / S4 8–10s / S5 3–5s；逾時必有 canned（never dead air）。
- **四階 rollback**：① auto-advance（今晚不開）→ ② Studio hidden 鈕 → ③ `ros2 param set demo_phase` → ④ `demo_phase=all` + 影片。
- **TTS 退**：`TTS_PROVIDER=piper` 重起 / offline。**offline 退**：啟動前 env `LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_full_demo_tmux.sh`（proven）。
- **face 退**：sim<0.7 → generic greet。**手勢退**：`gesture_enabled false`。**最終保底**：`demo-2026-06-snapshot` 影片。

---

## §9 誠實 claim（對外措辭）

- **可講**：低速前進 + LiDAR 即時偵測前方障礙、安全停下等待；本地即時人臉辨識 + 平安確認；物體辨識轉照護語境（杯子→補水，未來可延伸藥盒/鑰匙/外出提醒）；手勢二階段意圖確認降低誤觸；高風險指令經 Safety Layer 攔截。
- **不可講**：自主導航到 Roy / 動態繞障 / D435+LiDAR 已融合 / 靠深度避障 / 可靠走滿 2m / 跌倒偵測 / 2m 物體 / 可靠顏色 / 19 色 / 即時恢復（實際 ~10s 自癒）。nav 句綁 `docs/navigation/2026-06-13-nav-618-claim-wording.md` S1-S8 / F1-F10。
- 結語：「以上不僅讓 AI 走進真實世界，從感知到行動，從行動到守護。」

---

## §10 今晚不要做

換 YOLO 模型 / 26s 進 runtime / YOLOPose/RTMPose swap / D435+LiDAR fusion runtime / live SLAM / `goto_relative` 主線 / autonomous approach / 動態繞障 / auto-advance 預設開 / CLI Typer 重寫 / Windows PowerShell native / 把藥盒/鑰匙講成已支援。
