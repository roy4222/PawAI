# Demo Operator Runbook Plan — 6/18 五幕現場操作手冊

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫群：PawAI Demo Flow Reliability Sprint（Cloud A）｜本份：Demo Operator Runbook Plan

---

## 13 段索引

1. Goal　2. Current state　3. Problems / gaps　4. Scope　5. Forbidden scope　6. Tasks　7. Pure software tasks　8. Jetson / Go2 HITL tasks　9. Tests　10. Rollback　11. Done criteria　12. Execution order　13. 6/18 presentation impact

交叉引用（同計畫群五份 + 既有真相來源）：
- master：[`2026-06-13-demo-flow-reliability-master-plan.md`](2026-06-13-demo-flow-reliability-master-plan.md)
- conductor：[`2026-06-13-demo-phase-conductor-plan.md`](2026-06-13-demo-phase-conductor-plan.md)
- online/offline：[`2026-06-13-online-offline-fallback-plan.md`](2026-06-13-online-offline-fallback-plan.md)
- s1 nav：[`2026-06-13-s1-low-risk-navigation-plan.md`](2026-06-13-s1-low-risk-navigation-plan.md)
- Lane 1 ISM：[`2026-06-13-lane1-brain-ism-staged-enable-plan.md`](2026-06-13-lane1-brain-ism-staged-enable-plan.md)
- Lane 3 CLI：[`2026-06-13-lane3-cli-v2-completion-plan.md`](2026-06-13-lane3-cli-v2-completion-plan.md)
- nav 階梯：[`../../navigation/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)
- nav claim wording：[`../../navigation/2026-06-13-nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)
- Roy HITL queue：[`../../runbook/2026-06-13-roy-hitl-queue.md`](../../runbook/2026-06-13-roy-hitl-queue.md)
- post-refactor 驗收：[`../../runbook/2026-06-13-post-refactor-acceptance-report.md`](../../runbook/2026-06-13-post-refactor-acceptance-report.md)

---

## 1. Goal

讓**一名操作員**（Roy 或代操）能照固定順序跑完 6/18 demo 五幕，全程：

- 每一幕只觸發該幕功能（用 `demo_phase` gate 自發社交，安全鏈/明確指令不受影響）。
- 每一幕都知道：要切哪個 phase、預期 TTS 是什麼（online + offline 兩套）、驗證點看哪個 topic/trace、出錯時往哪個 rollback 退。
- 開場有安全前置（反映 §4 即時硬體：Go2 剛撞牆、nav stack 還在跑、D435 MIPI error、8GB 互斥）。
- 三個 post-refactor 洞（face / confirm / nav，見 §5 of master）各有獨立 runbook 段，誠實標 proven / needs-HITL / FAILED。
- 對外 claim 一律走 [`nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md) 的 S1–S8 可講句 + F1–F10 禁講句。

**本份不寫 code。** 這是「操作手冊的計畫」：定義 runbook 章節骨幹、每步驟對映哪個既有 CLI/topic/trace、哪些步驟依賴尚未實作的新 CLI（demo phase / demo mode / status brain 區塊 / face delete），並把這些依賴交叉引用回 conductor / fallback / Lane 3。

---

## 2. Current state

### 2.1 已存在的機制（可直接寫進 runbook，anchor 已實測）

- **demo_phase gate**（conductor 計畫骨幹的 code 現實）：
  - `interaction_state.py:33` `PHASE_ALLOWED_KINDS = { all:{greet,object,gesture}, s2_face:{greet}, s3_object:{object}, s4_gesture:{gesture}, quiet:frozenset() }`（已用 `grep` 確認 line 33/35/36/37/38）。
  - `interaction_state.py:42` `phase_allows(demo_phase, kind)`。
  - `brain_node.py:496` declare `demo_phase` 預設 `all`；`:539` 讀取；`:311` runtime set callback（unknown phase 拒絕、保留舊值，已確認 line 311-320）；`:333` `_phase_allows()`。
  - phase 只 gate **自發社交 proposal**：greet `:1747` / object `:1945` / gesture `:1348`（`brain_node.py:327-330` 設計註解：安全鏈、明確語音/文字指令、Studio skill_request 不受 phase 影響；priority safety > explicit > phase）。
  - **錄影 SOP 既有**：`ros2 param set /brain_node demo_phase s3_object`（`brain_node.py:330` 註解）。
- **runtime toggle topic / param**（demo 現場免重啟）：
  - `/brain/reset_context`（`std_msgs/Empty`，`brain_node.py:252`）→ 清 PendingConfirm（`:2199`）、object_remark dedup（`:2205`）、上一段 active_plan（contract v2.11）；**不清** `_state.attention`。
  - `/brain/gesture_enabled`（`std_msgs/Bool`，`:258`）與 `ros2 param set /brain_node gesture_enabled` 同效；關閉時 cancel in-flight PendingConfirm（`:426`）。
  - runtime param callback（`:274`）支援即時切：`gesture_enabled` / `stranger_alert_enabled` / `greet_require_sitting` / `greet_cooldown_s` / `demo_phase` / 以及 ISM 系列（`ism_enabled` `:292`、`ism_stage_2a_demo_phase` `:293`…2d `:296`）。
- **既有 CLI**（`tools/pawai_cli/pawai_cli/main.py`，已 `grep` 確認）：`demo start|stop`、`smoke brain|vision|object|nav|full`（`:920/927/971/1016/1155/1295`）、`health brain|nav`、`status`、`face list|enroll|rebuild|test`、`evidence pull`、`doctor`、`contract check`、`readiness`、`logs`、`docs`、`net wifi`。
- **既有 Studio**：Gesture On/Off toggle（gateway POST `/api/gesture_enabled` → `/brain/gesture_enabled`，`brain_node.py:254-258`）、Evidence Center（trace 檢視）皆**已存在**。⚠️ **current phase chip / offline-mode 指示燈為 PLANNED**（current phase = conductor T-C4 needs-HITL；offline-mode = fallback 計畫 needs-HITL）——落地前操作員靠 `ros2 param get /brain_node demo_phase` 與終端 env 自行確認。

### 2.2 尚未實作的依賴（runbook 會引用，但標「PLANNED — 需 Lane 3 / conductor」）

- `pawai demo phase <phase>`（新；conductor + Lane 3 T3-?）。在它落地前，runbook **主路徑用 `ros2 param set /brain_node demo_phase <phase>`**（已驗的 SOP），CLI 版本只列為 future。
- `pawai demo mode online|offline`（新；fallback 計畫）。落地前用 env override（`TTS_PROVIDER` / `ASR_PROVIDER_ORDER` / `LLM_ENDPOINT`，見 §9 of master）+ 重啟 demo。
- `pawai status` 的 brain runtime 區塊（新；Lane 3 T3-6，顯示 `ism_shadow_enabled` / `ism_enabled` / `ism_stage_2*` / `demo_phase` / `gesture_enabled` / `stranger_alert_enabled`）。落地前用 `ros2 param get /brain_node <name>` 逐項查。
- `pawai face delete <name>`（新；Lane 3 T3-5）。**B4 bug**：現有 `face delete`（`main.py:2017-2018`）/ `face rebuild`（`:2045`）只 `rm -f .../model_sface.pkl`，**不刪 T5S-5 的 `model_sface.npz`** → 刪人/重訓不生效（已 `grep` 確認兩處只含 `.pkl`）。runbook 的 face_db 衛生段必須標此 bug 與 workaround（手動 `rm` npz）。

### 2.3 即時硬體狀態（handoff 2026-06-13 EOD）

- Jetson 上 **nav stack 還在跑**（tmux `nav-cap-demo`，9 windows，含 `go2_driver` + `reactive_stop` + `nav2` + LiDAR）。
- **剛發生 Go2 撞擊**：`goto_relative 0.3m` 第一發走歪撞牆，Roy e-stop。
- D435 **Right MIPI error / Hardware Error**（nav 不需 D435；但 face/vision 受影響）。
- nav stack 與 brain demo stack **8GB 互斥**（不能同跑）。
- 完成度：軟體 AFK ~95% / Pre-6/18（軟體+HITL）~63% / v2 北極星 ~33%。剩餘幾乎全是 Roy 在場 HITL。

---

## 3. Problems / gaps

| # | 問題 | 影響 runbook 的點 |
|---|------|------------------|
| G1 | nav stack 還開著、Go2 剛撞牆 | runbook **開場第 0 步必須先 stop nav stack + 確認 Go2 停穩**，否則 brain 段起不來（8GB 互斥）且 Go2 可能殘留 active goal |
| G2 | 8GB 互斥 | S1（nav 段）與 S2–S5（brain 段）必須**分段切換 stack**，不是一條 tmux 跑到底；runbook 要寫明「S1 結束 → stop nav → 起 brain → S2 開始」的 stack 交接 |
| G3 | D435 MIPI error | S2/S3/S4 依賴 camera（face/pose/object）；runbook 開場要有「重插 D435 USB + 確認 `/camera/.../color/image_raw` 有 frame」前置 |
| G4 | `demo phase` / `demo mode` / `status brain` / `face delete` CLI 未實作 | runbook 主路徑全部用 `ros2 param set` / env override / `ros2 param get` / 手動 `rm`；CLI 版本只列 future（避免操作員照不存在的指令打） |
| G5 | phase 切換不清 pending_confirm / active_plan / cooldown | 換幕之間（尤其 S3→S4、S4→S5）必須手動 `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}`，否則上一幕殘留 confirm/plan 污染下一幕 |
| G6 | face re-enroll 脆（B4 + 幽靈目錄 + demo start 重訓） | face_db 衛生 SOP 必須在 S2 前一晚跑、發表日重驗（needs-HITL） |
| G7 | confirm 目標 `thumbs_up→OK→wiggle`，HITL#2 只驗過 `peace→OK→WeGo` | S4 runbook 必須標兩條觸發路徑差異，現場先試目標路徑、不行立刻退驗過的 peace 路徑 |
| G8 | nav motion FAILED（0.3m 撞牆） | S1 是高風險；runbook 要有「e-stop 就位 + initialpose 朝向校正 + indoor_tight + n 次未過則退影片」的硬性前置；對外 claim 退保守 |

---

## 4. Scope

**本份計畫產出**：一份 operator runbook 的**規劃骨幹**（章節、每步驟對映、trace/rollback 表）+ 平台支援度表 + 三洞 runbook 段。

涵蓋：

1. 開場安全前置（Go2 停穩 / stop nav / D435 重插 / 8GB stack 交接 / e-stop 就位）。
2. 五幕逐幕 operator 步驟（切 phase、預期 TTS online+offline、該幕驗證點、trace reason、rollback）。
3. 三個 post-refactor 洞的 runbook 段（face / confirm / nav）。
4. Studio operator controls（現有面板，不大改 UI）。
5. CLI 操作清單（含標 PLANNED 的新指令）。
6. 平台支援度表（PowerShell / WSL / macOS / Jetson-only）。
7. 每步 rollback + 能力分級 + 誠實底線。

---

## 5. Forbidden scope

- 不換模型當主線；不做 benchmark dashboard；不做 live SLAM 主線；不做 autonomous approach Roy 主線；不大改 Studio UI；不完整重寫 CLI；不進 Phase 3/4/5。（與計畫群共同 §11）
- **不在 runbook 寫任何「自主巡邏 / 動態繞障 / D435 已融合 / auto-resume / 聽懂走到 Roy 身邊 / 即時恢復」**（F1–F10 禁講句，見 claim wording）。
- runbook **不得指示操作員對移動中 Go2 送 Damp(1001)**（會摔狗）。
- **本份不寫 code**，連 runbook 的 markdown 正文都不產出——只產「runbook 的計畫」。實際 runbook 文件由 master 計畫排程後、CLI/conductor 落地後再寫。

---

## 6. Tasks（總表，逐項標三類 + tests + HITL + rollback）

> 標記：[pure software] = 開發機/WSL 可做、無硬體；[Jetson needed] = 需 SSH 上 Jetson（無 Go2 motion）；[Go2 motion needed] = 需 Go2 會動、e-stop 就位。

### T-RB-1　開場安全前置章節 [pure software]（寫文件）
撰寫「第 0 步」清單（Go2 停穩確認 / stop nav stack / D435 重插 / stack 交接 / e-stop 就位）。內容見 §8.0。
- tests：T-RB-9 dry-run review（同事照唸能不能照做）。
- HITL：發表日當天 Roy 照第 0 步跑一次、確認每項可執行。
- rollback：若 nav stack 清不掉 → `pawai demo stop --force`（搶 lock）+ 手動 `pkill -9 go2_driver; pkill -9 reactive_stop`。

### T-RB-2　五幕逐幕步驟章節 [pure software]（寫文件）
每幕一節（S1–S5），固定六欄：切 phase / 預期 TTS(online) / 預期 TTS(offline) / 驗證點 / trace reason / rollback。內容見 §8.1–8.5。
- tests：對照 `PHASE_ALLOWED_KINDS` 表，確認每幕 allow/suppress 寫對（與 §8 conductor 對映表一致）。
- HITL：五幕真機跑一遍、每幕只觸發該幕功能。
- rollback：見每幕 rollback 欄。

### T-RB-3　face_db 衛生 + re-enroll runbook 段 [Jetson needed]
撰寫 §8.6.1，含 B4 npz workaround、幽靈目錄移出、`enroll → rebuild → 重啟 face node` SOP、發表日重驗 checklist。
- tests：`pawai face list` 確認只剩 `roy`；`pawai face test` sim ≥ 0.7。
- HITL：發表日早上重 enroll + 重驗 sim（needs-HITL，proven 僅一次）。
- rollback：sim < 0.7 → 退「不秀具名問候、改 generic greet」或用前一晚 backup pkl/npz 還原。

### T-RB-4　confirm wiggle runbook 段 [Go2 motion needed]
撰寫 §8.6.2，標 `thumbs_up→OK→wiggle`（目標）vs `peace→OK→WeGo`（HITL#2 驗過）差異、30s timeout 不黑洞、param 路徑（`thumbs_up_demo_ack` / `peace_wego_confirm`）。
- tests：`smoke vision`（手勢 event 出得來）。
- HITL：現場先試目標路徑，失敗退 peace 路徑（needs-HITL 重驗）。
- rollback：confirm 卡住 → `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}` 清 PendingConfirm；手勢誤觸 → `ros2 param set /brain_node gesture_enabled false`。

### T-RB-5　nav motion runbook 段 [Go2 motion needed]
撰寫 §8.6.3，含 initialpose 朝向校正 SOP（LiDAR 紅點對齊牆）、indoor_tight ±18° 低速、goto 前朝向 sanity、e-stop 就位、n 次未過退影片。對外 claim 走 S1（C1/C2，標單點/低樣本）。
- tests：`smoke nav --static`（零 motion，verify wiring）；`scripts/lidar_front_sector.py`（±15/20/30° 扇區最近距離）。
- HITL：[Go2 motion needed] 0.3m → 0.5m，每發前確認朝向 + 前方淨空；撞 1 次即停。
- rollback：撞牆/走歪 → e-stop（`emergency_stop.py engage`）+ `pawai demo stop`；6/18 前 n=3 未過 → S1 改純影片 fallback（demo snapshot 保底）。

### T-RB-6　Studio operator controls 章節 [pure software]（寫文件）
列現有可用面板（current phase / offline mode / gesture toggle / Evidence Center trace），不大改 UI。內容見 §8.7。
- tests：起 Studio（`bash pawai-studio/start.sh`）確認面板渲染、gesture toggle POST 通。
- HITL：發表日 Studio 開在筆電、操作員能即時看 phase + trace。
- rollback：Studio 掛 → 退純 `ros2 param get` + `pawai evidence pull` 看 trace（不靠 UI）。

### T-RB-7　CLI 操作清單章節 [pure software]（寫文件）
列出每步用哪個 CLI；新指令（demo phase / demo mode / status brain / face delete）標 **PLANNED**，給「落地前 workaround」一欄。內容見 §8.8。
- tests：每個既有指令在開發機跑 `--help` 確認存在。
- rollback：N/A（純文件）。

### T-RB-8　平台支援度表 [pure software]（寫文件）
PowerShell / WSL / macOS / Jetson-only 四欄，標每類指令哪裡原生跑。內容見 §8.9。
- tests：交叉對照 §3 of task（CLI 走 SSH→Jetson、Windows PS 對 zsh/.env/rsync 脆）。
- rollback：N/A。

### T-RB-9　runbook dry-run review [pure software]
找一位沒參與的人照 runbook 唸一遍、標所有「照不下去」的步驟。
- tests：dry-run review notes。
- HITL：發表日前 48h。
- rollback：N/A。

---

## 7. Pure software tasks

下列 task 完全在開發機/WSL 寫 markdown、不碰硬體：T-RB-1、T-RB-2、T-RB-6、T-RB-7、T-RB-8、T-RB-9。

**誠實底線（寫在 runbook 開頭與每洞段）**：

- AFK 完成的東西只能說「code merged + 單測綠」（needs-HITL），**HITL 過才算 proven**。
- 能力分級三級貼在每幕標題旁：
  - **proven**：已真機 HITL 驗過（引日期/commit/test 數）。
  - **needs-HITL**：merged + 單測綠，待 Roy 在場真機驗。
  - **research-only**：只有 spec / 研究，禁當主線。

---

## 8. Jetson / Go2 HITL tasks（runbook 正文骨幹）

> 以下是 runbook 各章節的**內容規劃**（給寫 runbook 的人照填）。實際操作前置見 §4 / §3。

### 8.0 開場安全前置（第 0 步，[Go2 motion needed] 環境）

依序（任一項不過就停下排除，不往下）：

1. **確認 Go2 停穩**：目視 Go2 站定不動；若仍在動 → e-stop `python3 scripts/emergency_stop.py engage`（mux pri 255 + lock）。**禁對移動中 Go2 送 Damp(1001)（會摔）**。
2. **清 nav stack**：`pawai demo stop`（依 lock lane 路由 cleanup）；若殘留 → `pawai demo stop --force` + `pkill -9 go2_driver; pkill -9 reactive_stop; pkill -9 nav2; pkill -9 robot_state; pkill -9 sllidar`（逐一，因 `killall python3` 只殺 launch parent）。`tmux ls` 確認 `nav-cap-demo` 不在。
3. **確認 Go2 殘留 goal 清掉**：若 nav 異常退出，`nav_action_server` 可能留 orphaned active goal（6/8 HITL 已知）→ 重啟 navcap launch 才清；S1 若要用 nav，這步必做。
4. **8GB stack 交接決策**：本場若先跑 S1（nav 段）→ S1 結束後 stop nav、**再起 brain demo**（S2–S5）；nav 與 brain **不可同時開**。
5. **D435 健康**：`ros2 topic hz /camera/.../color/image_raw`；若無 frame 或 MIPI error → 重插 D435 USB（換 port）、`pawai demo stop` 後重起。S2/S3/S4 依賴 camera，這步不過就先不進 S2。
6. **e-stop 就位**：操作員手放 e-stop（S1/S4 有 Go2 motion）；遙控器在手邊。
7. **demo mode 決策**：網路差 → 用 offline（見 §9 of master / fallback 計畫）。落地前 workaround：`TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' LLM_ENDPOINT="http://127.0.0.1:1/" bash scripts/start_full_demo_tmux.sh`；CLI 版 `pawai demo mode offline` 為 PLANNED。
8. **起 brain demo + 確認**：`pawai demo start`（lane=brain）；**不要只信 CLI 的 `✓ Demo running`**（6/4 CRLF 假成功教訓）→ `tmux ls` + `ros2 node list` 數 node。
9. **demo 安全旗標**：`ros2 param set /brain_node stranger_alert_enabled false`（**6/9 卡死全系統真兇**，demo 建議關）；確認 `demo_phase=all`（起始態）。

> 能力分級：開場前置本身 = proven（CLI/pkill/e-stop 都驗過）；但「S1 用 nav」整體 = FAILED（見 §8.6.3）。

### 8.1 S1 — nav 移動到現場（demo_phase=quiet；[Go2 motion needed]；能力=FAILED，今天剛撞牆）

| 欄 | 內容 |
|----|------|
| stack | **nav 段**（與 brain 互斥）。`bash scripts/start_nav_capability_demo_tmux.sh`，env `REACTIVE_PROFILE=indoor_tight ROBOT_IP=192.168.123.161 MAP=/home/jetson/maps/home_living_room.yaml`。若 brain 已在跑且 S1 走「brain 報詞 + 遙控/影片」則 brain 設 `demo_phase=quiet`（全 suppress，對映 `quiet`）。 |
| 切 phase | brain 段：`ros2 param set /brain_node demo_phase quiet`（CLI 版 `pawai demo phase quiet` PLANNED）。 |
| 預期 TTS(online) | S1 主要靠 nav 動作；若 brain 在報詞 → canned「我正在移動到巡檢位置。」 |
| 預期 TTS(offline) | 同上 canned（local TTS piper/edge，可預 render WAV，latency≈0）。 |
| 動作（高風險） | initialpose 朝向校正（Foxglove 設 `/initialpose`，LiDAR 紅點對齊牆）→ `scripts/lidar_front_sector.py` 確認 ±15° 淨空 → `ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.3}"`（先 0.3m，過了再 0.5m）。 |
| 驗證點 | 只 S1 動作觸發；`/state/nav/status`（含 covariance JSON，YELLOW gate ≤0.30 才准 >0.5m）、`/state/nav/safety`、`/state/nav/paused`(latched)。 |
| trace reason | nav 拒絕理由走 `/state/nav/status`；reactive_stop danger → `/state/nav/safety`。 |
| rollback | 走歪/撞 → **e-stop 立即**（`emergency_stop.py engage`）→ `pawai demo stop`。6/18 前 n=3 未過 → **S1 退純影片 fallback**（三層：遙控輔助 + Studio 證據 → snapshot 影片）。 |
| claim | 對外只講 **S1**「室內已知地圖、操作員下令的短距自主移動(0.3–0.5m)」標 C1 HARDWARE_PROVEN_LOW_SAMPLE / C2 NEEDS_RETEST 單點；**今天剛撞牆 → 未重驗成功前一律退保守/影片**，禁講 F6/F9「聽懂走到 Roy 身邊 / 可靠導航」。詳 [`s1-low-risk-navigation-plan.md`](2026-06-13-s1-low-risk-navigation-plan.md) + [`nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)。 |

> ⚠️ `reactive_stop` 的 `danger_distance_m`/`front_arc_deg`/`front_offset_rad` **只在 `__init__` 讀，`ros2 param set` 改不了 → 必須 kill 重啟帶參數**。indoor_tight = ±18° + danger 1.0 + 低速 ≤0.2 m/s（窄錐綁低速，否則側向覆蓋不足）。

### 8.2 S2 — 辨識 Roy 並問候（demo_phase=s2_face；[Jetson needed]；能力=needs-HITL）

| 欄 | 內容 |
|----|------|
| stack | brain 段（nav 已 stop）。 |
| 切 phase | `ros2 param set /brain_node demo_phase s2_face`（allow=greet、suppress object/gesture，對映 `PHASE_ALLOWED_KINDS["s2_face"]`）。**切前先 `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}`** 清上一幕殘留。 |
| 預期 TTS(online) | LLM 生成的問候，內含「Roy / 歡迎回來」語意。 |
| 預期 TTS(offline) | canned「Roy，歡迎回來，我看到你了。」 |
| 觸發條件（硬依賴） | known face stable（`/event/face_identity` 的 `identity_stable`）+ 最近 `greet_sitting_window_s`(3s) 內 pose=sitting + `greet_cooldown_s`(20s)/人 cooldown。**只在 unknown→known 進場轉變觸發**（要重現需遮臉/離框 ~5s 再回來）。 |
| 驗證點 | 只 greet 觸發、object/gesture 不應冒出（phase suppress）；`/state/perception/face` 看 identity；trace 有 greet 決策。 |
| trace reason | greet 抑制 → `gate=demo_phase reason=phase:s2_face:object/gesture`（`brain_node.py:349` `_suppressed`）；greet 沒觸發 → 看 sitting/cooldown/identity 哪個沒滿足。 |
| rollback | sitting 不穩 → `ros2 param set /brain_node greet_require_sitting false` + 台詞去掉「坐下來了」；face 認不出 → 見 §8.6.1 face_db；完全失靈 → `demo_phase all` 放開、口頭帶過。 |

### 8.3 S3 — 坐下 + 杯子提醒（demo_phase=s3_object；[Jetson needed]；能力=needs-HITL）

| 欄 | 內容 |
|----|------|
| 切 phase | `reset_context` → `ros2 param set /brain_node demo_phase s3_object`（allow=object、suppress greet/gesture，對映 `s3_object`）。 |
| 預期 TTS(online) | LLM 生成、含「杯子 / 補充水分」語意。 |
| 預期 TTS(offline) | canned「我看到杯子了，記得補充水分。」 |
| 觸發 | pose=sitting 餵 state + object cup remark（cup 0.7m HITL 已知場景，commit `b1f5058`）。 |
| 驗證點 | 只 object remark 觸發、greet/gesture 不冒出。 |
| trace reason | greet/gesture 抑制 → `reason=phase:s3_object:greet/gesture`；object 沒觸發 → object dedup（`brain_node.py:2205` 走 reset 清）或 cup 沒偵到（D435/object node）。 |
| rollback | object 重複報 → `reset_context` 清 dedup；cup 偵不到 → 看 object node、必要時口頭帶。 |

### 8.4 S4 — thumbs_up → OK → wiggle confirm（demo_phase=s4_gesture；[Go2 motion needed]；能力=needs-HITL，目標路徑未驗）

| 欄 | 內容 |
|----|------|
| 切 phase | `reset_context` → `ros2 param set /brain_node demo_phase s4_gesture`（allow=gesture、suppress greet/object，對映 `s4_gesture`）。確認 `gesture_enabled=true`。 |
| 預期 TTS(online) | confirm 詢問句（如「你要我 WeGo 一下嗎？比 OK 我就開始。」LLM 或 canned）。 |
| 預期 TTS(offline) | canned「你要我 WeGo 一下嗎？比 OK 我就開始。」 |
| 觸發（**標差異**） | **目標路徑** thumbs_up → OK → Go2 wiggle（`thumbs_up_demo_ack` param）；**HITL#2 驗過的是** peace → OK → WeGo（`peace_wego_confirm` param）。現場**先試目標、失敗立刻退 peace**。 |
| 驗證點 | 只 gesture confirm 觸發；PendingConfirm `timeout_s=30.0`、`stable_s=0.5`（`brain_node.py:186`）→ 30s 不黑洞。 |
| trace reason | greet/object 抑制 → `reason=phase:s4_gesture:greet/object`；confirm timeout → PendingConfirm 30s 自然清。 |
| rollback | confirm 卡 → `reset_context` 清 PendingConfirm；手勢誤觸/連發 → `ros2 param set /brain_node gesture_enabled false`（cancel in-flight confirm，`:426`）；wiggle 不動 → 退 peace→WeGo 已驗路徑。Go2 motion → e-stop 就位。 |

### 8.5 S5 — backflip 安全拒絕（demo_phase=quiet；[Jetson needed]；能力=proven 端到端 6/10 S5）

| 欄 | 內容 |
|----|------|
| 切 phase | `reset_context` → `ros2 param set /brain_node demo_phase quiet`（全 suppress 自發社交，對映 `quiet`）。 |
| 預期 TTS(online) | 安全拒絕回覆（SafetyLayer，phase-independent，不受 quiet 影響）。 |
| 預期 TTS(offline) | canned「這個動作不安全，我不能執行。」 |
| 觸發 | 語音/文字明確指令「翻跟斗 / backflip」→ SafetyLayer reject（明確指令不受 phase 影響，priority safety > explicit > phase）。 |
| 驗證點 | quiet 下 greet/object/gesture 全不冒出，**只** SafetyLayer reject 出聲。 |
| trace reason | reject 走 SafetyLayer 決策 trace（拒絕理由可讀）；自發社交全 suppressed。 |
| rollback | reject 沒出聲 → 確認指令進得來（ASR/文字）、SafetyLayer 規則命中；TTS 卡 → `TTS_PROVIDER=piper` 重起或口頭。 |

> S5 是**最穩的一幕**（6/10 已端到端驗過 SafetyLayer reject），建議排在順序末尾收尾。

### 8.6 三個 post-refactor 洞 runbook 段

#### 8.6.1 face re-enroll + face_db 衛生（needs-HITL；proven 僅一次 HITL#2 sim 0.87 / 6/8 0.73–0.81）[Jetson needed]

- **脆點**：`pawai demo start` 會重訓 face；**B4 bug**（`main.py:2017-2018`/`:2045` 只刪 `.pkl` 不刪 `.npz`）使 delete/rebuild 不完整；`face_db/` 內**所有子目錄**都被 `train_model` 當人名 → `_backup*`/`old*` 變幽靈身份稀釋 centroid。
- **SOP（發表日早上跑）**：
  1. 備份目錄**移出** `face_db` 外（`mv /home/jetson/face_db/*_backup* /home/jetson/face_db_archive/`）。
  2. `pawai face enroll --person-name roy`（訂 `/camera/.../color/image_raw`，與 demo camera 不衝突）。
  3. `pawai face rebuild`（刪 pkl）→ **B4 workaround：手動 `rm -f /home/jetson/face_db/model_sface.npz`**（CLI 未刪 npz；待 Lane 3 T3-5 修）。
  4. 重啟 face node 重訓。
  5. `pawai face test` 確認 sim ≥ 0.7（needs-HITL 重驗）。
- **rollback**：sim < 0.7 → S2 退 generic greet（不秀具名）或還原前一晚 backup。
- 交叉引用 [`post-refactor-acceptance-report.md`](../../runbook/2026-06-13-post-refactor-acceptance-report.md)、[`roy-hitl-queue.md`](../../runbook/2026-06-13-roy-hitl-queue.md)。

#### 8.6.2 confirm wiggle（needs-HITL；proven 僅 peace→OK→WeGo 一次）[Go2 motion needed]

- **目標 vs 驗過差異（runbook 必標）**：目標 `thumbs_up → OK → wiggle`（`thumbs_up_demo_ack`）；HITL#2 實際驗 `peace → OK → WeGo`（`peace_wego_confirm`）。**現場先試目標、失敗退 peace**。
- PendingConfirm 30s timeout 不黑洞；卡住 → `reset_context`。
- **rollback**：誤觸 → `gesture_enabled false`；wiggle 不動 → 退 peace→WeGo。

#### 8.6.3 nav motion HITL（FAILED；今天 0.3m 撞牆）[Go2 motion needed]

- **根因研判**：AMCL initialpose 朝向不準 → 斜走撞 +25°/1.65m 側家具（跑了 ±30° open_space 非 indoor_tight）。
- **修法方向（HITL 前置）**：initialpose 朝向校正 SOP（LiDAR 紅點對齊牆）+ 切 indoor_tight ±18° 低速 + goto 前朝向 sanity（`lidar_front_sector.py` ±15° 淨空）。
- **安全**：e-stop 就位、`emergency_stop.py engage`、StopMove(`api_id=1003`, topic 必填 `rt/api/sport/request`)；**禁 Damp(1001)**。
- **對外底線**：n 次無撞重驗前**不可講「自主短距移動」**；6/18 前未過 → S1 純影片 fallback。詳 [`s1-low-risk-navigation-plan.md`](2026-06-13-s1-low-risk-navigation-plan.md)。

### 8.7 Studio operator controls（現有面板，不大改 UI）[pure software 起 / 看]

- **current phase 顯示**：**PLANNED**（conductor T-C4，needs-HITL）——`/state/brain` payload 加 `demo_phase` 欄位 + Studio 唯讀 chip；落地前用 `ros2 param get /brain_node demo_phase`。
- **offline mode 顯示**：**PLANNED**（fallback 計畫，needs-HITL）；落地前看啟動 env / 終端。
- **gesture toggle**：Studio Gesture On/Off → gateway POST `/api/gesture_enabled` → `/brain/gesture_enabled`（`brain_node.py:254-258`），與 `ros2 param set gesture_enabled` 同效。
- **trace（Evidence Center）**：現場看每幕決策/抑制 reason；落地的 brain runtime 區塊（`ism_*` / `demo_phase` / `gesture_enabled` / `stranger_alert_enabled`）由 Lane 3 T3-6（`pawai status` brain 區塊）+ Studio 顯示。
- 起 Studio：`bash pawai-studio/start.sh` → `http://localhost:3000/studio`。
- **rollback**：Studio 掛 → 退 `ros2 param get /brain_node <name>` + `pawai evidence pull` 看 trace JSONL。

### 8.8 CLI 操作清單（既有 + PLANNED，落地前 workaround）

| 場景 | CLI（既有） | PLANNED 新指令 | 落地前 workaround |
|------|------------|----------------|-------------------|
| 起/停 demo | `pawai demo start` / `pawai demo stop`（`--force` 搶 lock） | — | — |
| 切五幕 phase | — | `pawai demo phase <phase>` | `ros2 param set /brain_node demo_phase <s2_face\|s3_object\|s4_gesture\|quiet\|all>` |
| 切 online/offline | — | `pawai demo mode online\|offline` | env override + 重起（§9 of master / fallback 計畫） |
| 看 brain runtime | `pawai status`（基本） | `pawai status` brain 區塊（Lane 3 T3-6） | `ros2 param get /brain_node {demo_phase,gesture_enabled,stranger_alert_enabled,ism_enabled,ism_stage_2a_demo_phase}` |
| 換幕清狀態 | — | — | `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}` |
| smoke 全流程 | `pawai smoke full` | — | — |
| smoke nav（零 motion） | `pawai smoke nav --static` | — | — |
| face 衛生 | `pawai face list` / `enroll` / `rebuild` / `test` | `pawai face delete <name>`（Lane 3 T3-5，修 B4） | 手動 `rm -f .../model_sface.{pkl,npz}` |
| 拉 trace 證據 | `pawai evidence pull`（只讀） | — | — |
| gesture 開關 | — | — | `ros2 param set /brain_node gesture_enabled false` 或 Studio toggle |
| 關 stranger_alert | — | — | `ros2 param set /brain_node stranger_alert_enabled false`（demo 建議關，6/9 真兇） |
| e-stop | — | — | `python3 scripts/emergency_stop.py engage` |

> CLI 哲學：只包腳本/SSH/rsync、零 runtime 行為（唯一例外 `--with-shadow` 需 Roy 點頭）；`smoke nav` 只 static、零 motion。詳 [`lane3-cli-v2-completion-plan.md`](2026-06-13-lane3-cli-v2-completion-plan.md)。

### 8.9 平台支援度表

| 指令類別 | Windows PowerShell | WSL（開發機主線） | macOS | Jetson-only |
|----------|--------------------|--------------------|-------|-------------|
| `pawai deploy / status / smoke / face / evidence`（純 SSH wrapper） | 可（透過 ssh），但 **zsh/.env/rsync 在 PS 脆**（CRLF、引號） | ✅ 原生（POSIX shell + ssh + rsync） | ✅ 近似 WSL | — |
| `pawai demo start/stop` / `demo phase` / `demo mode`（走 SSH→Jetson） | 可（SSH wrapper），同上脆點 | ✅ | ✅ | runtime 實際在 Jetson |
| `ros2 param set/get` / `ros2 action send_goal` / `ros2 topic pub` | ❌ 原生不可（無 ROS2 runtime） | ❌（無 ROS2 runtime，需 SSH 上 Jetson 後執行） | ❌ 同 WSL | ✅ **唯一能跑 ROS2 runtime / Go2 / 感知的地方** |
| nav stack / brain demo / 感知 node | ❌ | ❌ | ❌ | ✅ Jetson-only |
| Studio frontend（Next.js 瀏覽器） | ✅ 瀏覽器開 | ✅ | ✅ | （gateway 在 Jetson/本機，UI 任一桌面平台瀏覽器開） |
| `bash scripts/*.sh`（tmux/zsh/.env） | ❌ 原生脆（用 WSL 或 SSH 上 Jetson 跑） | ✅（透過 ssh 在 Jetson 跑） | ✅ | ✅ 本機跑 |

> 結論：**操作員主控台用 WSL 或 macOS**（POSIX shell + ssh + rsync 原生）；Windows 原生只跑「純 SSH wrapper」類且對 `.env`/CRLF/引號脆。**所有 ROS2 runtime / Go2 motion / 感知一律在 Jetson**（透過 SSH 或 tmux）。Studio UI 任一桌面平台瀏覽器皆可。

---

## 9. Tests

> 本份計畫產出皆為文件，「tests」= runbook 可被照做的驗證 + 各步驟引用的既有測試指令。

- **dry-run review**（T-RB-9）：旁人照唸 runbook 不卡 = 文件通過。
- **每步驟引用的既有測試**：
  - 開場：`tmux ls` + `ros2 node list`（不信 CLI 假成功）。
  - S1：`pawai smoke nav --static`（零 motion wiring）、`scripts/lidar_front_sector.py`。
  - S2/S3/S4：`pawai smoke vision` / `pawai smoke object` / `pawai smoke brain`（單測綠 = needs-HITL）。
  - S5：`pawai smoke brain`（SafetyLayer reject 端到端，6/10 proven）。
  - face：`pawai face test`（sim ≥ 0.7）。
  - 全流程：`pawai smoke full`。
- **conductor 對映一致性檢查**：runbook 每幕 allow/suppress 必須與 `PHASE_ALLOWED_KINDS`（`interaction_state.py:33`）逐字一致。

---

## 10. Rollback

| 層級 | 觸發 | 動作 |
|------|------|------|
| 全域退保守態 | 任一幕行為失控 | `ros2 param set /brain_node demo_phase all`（回現行為）+ `ism_enabled false`（byte-identical 退路，conductor 保證）。 |
| TTS 退本地 | cloud TTS/LLM timeout | `TTS_PROVIDER=piper` 重起 / `demo mode offline`（PLANNED）/ canned phrase。 |
| 手勢退 | 誤觸/連發 | `ros2 param set /brain_node gesture_enabled false`（cancel in-flight confirm）。 |
| stranger 退 | 全系統卡 | `ros2 param set /brain_node stranger_alert_enabled false`（6/9 真兇，demo 預設關）。 |
| 換幕殘留退 | 上一幕 confirm/plan/dedup 污染 | `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}`。 |
| nav 退影片 | S1 撞/走歪、n=3 未過 | e-stop → `pawai demo stop` → S1 純影片 fallback（snapshot 保底）。 |
| face 退 generic | sim < 0.7 | S2 不秀具名、改 generic greet / 還原 backup。 |
| Studio 退 | UI 掛 | `ros2 param get` + `pawai evidence pull` 看 trace。 |
| 整 stack 退 | Jetson 環境異常 | `pawai demo stop --force` + 逐一 `pkill -9` + clean script，重起。 |

> 每一個 rollback 都是「往**現行已驗行為**退」，不引入新行為（與 conductor byte-identical 退路一致）。

---

## 11. Done criteria

- runbook 文件含：開場安全前置（§8.0）、五幕逐幕六欄表（§8.1–8.5）、三洞段（§8.6）、Studio controls（§8.7）、CLI 清單含 PLANNED + workaround（§8.8）、平台支援度表（§8.9）。
- 每幕標能力分級（S1=FAILED、S2/S3/S4=needs-HITL、S5=proven）+ 對應 claim wording（S1–S8 / F1–F10）。
- 每步驟有 trace reason + rollback。
- 三洞段誠實標 proven 次數 + 目標 vs 驗過差異（confirm）+ FAILED 反映（nav 撞牆）。
- dry-run review（T-RB-9）通過。
- 與 conductor `PHASE_ALLOWED_KINDS` 逐字一致；新 CLI 指令一律標 PLANNED + workaround，不讓操作員照不存在的指令打。

---

## 12. Execution order

1. **T-RB-1 開場安全前置**（最先，反映今天剛撞牆的硬體狀態）。
2. **T-RB-7 CLI 清單 + T-RB-8 平台表**（操作員要先知道用什麼工具、在哪跑）。
3. **T-RB-2 五幕逐幕步驟**（依賴 conductor 的 phase 對映表落定）。
4. **T-RB-6 Studio controls**（依賴 Lane 3 status brain 區塊規格）。
5. **T-RB-3/4/5 三洞段**（依賴 HITL queue 排程，發表日前 48h 內完成）。
6. **T-RB-9 dry-run review**（最後，發表日前 48h）。

> 依賴順序：conductor（phase 詞彙 + 切換清理）→ 本 runbook 五幕表；Lane 3（CLI + status brain）→ 本 runbook CLI 清單的「既有/PLANNED」分欄；fallback 計畫（online/offline + canned）→ 本 runbook 各幕 TTS 兩套。**本份不阻塞任何 code，可與 conductor / Lane 3 並行寫。**

---

## 13. 6/18 presentation impact

- **正面**：操作員照 runbook 走，五幕**照順序、不串台**（demo_phase gate 自發社交），出錯有明確 rollback，不開天窗（S1 三層 fallback 到影片）。S5 安全拒絕（proven）穩收尾，把「具身機器人懂安全邊界」這條故事講足。
- **誠實風險（必須對外照講）**：
  - S1 nav **今天剛撞牆**（FAILED）→ 對外只講 S1 保守句（C1 單點/C2 需重測），n=3 未過前**禁講「自主短距移動 / 可靠導航」**；最壞退純影片。
  - confirm **目標 thumbs_up→OK→wiggle 未驗**（只驗過 peace→OK→WeGo）→ 現場先試目標、失敗退 peace，對外講「比 OK 確認後執行動作」不指定到未驗的觸發手勢。
  - face **proven 僅一次且脆**（B4 + 幽靈目錄 + demo start 重訓）→ 發表日早上重驗、不行退 generic greet。
- **底線提醒（寫在 runbook 開頭）**：AFK 完成的只能說「merged + 單測綠」（needs-HITL）；**只有 Roy 在場真機 HITL 過的才算 proven**。對外 claim 全部以 [`nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md) 的 S1–S8 / F1–F10 為準，禁 overclaim。
- **8GB 互斥的觀眾感知**：S1（nav 段）與 S2–S5（brain 段）之間有 stack 交接（停 nav → 起 brain），現場會有約 1 分鐘空檔 → runbook 安排「操作員口頭過場 + Studio 展示前一段 trace 證據」填補，不讓觀眾以為當機。
