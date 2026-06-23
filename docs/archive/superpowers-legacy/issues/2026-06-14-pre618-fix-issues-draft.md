# Pre-6/18 修復 Issue 草案（2026-06-14 Live HITL 後）

> ⚠️ **這是草案，尚未發到 GitHub。** 等 Roy 審完才會用 `gh` / `to-issues` 真正建立 issue。本檔只負責把「確定要做」的項目拆成可發的 issue 結構，方便 Roy 逐條 review / 砍 / 改優先序。
>
> **本輪只做研究 + 寫計畫**：不改任何 runtime code、不發 GitHub issue。
>
> **6/18 前 Forbidden scope（每張 issue 都扣這份）**：
> - Go2 motion（除非 Roy 授權 + e-stop 在手）
> - goto_relative 當 live 主線
> - live SLAM
> - autonomous approach / 動態繞障
> - D435 + LiDAR fusion runtime claim
> - model runtime switch
> - auto-advance 預設開
> - full CLI v2 / Typer 大重寫
> - secure-default full flip（gateway auth 6/18 凍結期維持 OFF）
>
> **設計精神（每張 issue 都遵守）**：default-off / 可 rollback / 小 PR / byte-identical floor。
>
> **Live HITL 2026-06-14 結果速查**：S2 ✅（~2s greet、3m OK）／S3 ⚠（cup 辨識到但講 phone、pose 沒出）／S4 ✅（peace→OK→wiggle）／S5 ✅（秒回拒絕）／Act1 導航避障 ❌（沒成功，Stage1 LiDAR 11.9Hz 活、front±15°=2.09m、+20°=1.70m）。

---

## grill-me 拍板對照（2026-06-14，覆寫各 issue 的 Scope）

> 完整決策表見 [`../reports/2026-06-14-live-demo-iteration-findings.md`](../reports/2026-06-14-live-demo-iteration-findings.md) §6。⚠️=Roy 覆寫了原建議。

| 決策 | 拍板 | 影響 issue |
|---|---|---|
| **D1 S3 修法** | 混合：producer whitelist 收飲水（移除 phone/laptop）+ brain `OBJECT_REMARK_PRIORITY` cup>bottle（default-off param） | P0-1（Scope 採「混合」非純 param、非純 brain） |
| **D2 S3 attention** | `object_remark_attention_min=NOTICED`（只對 cup/bottle，default-off） | P0-2 |
| **D3 ⚠️ S3 pose** | 保複合句「Roy 坐著拿杯子」+ **上機修 vision pose 邊緣觸發**；cup 簡單句仍為地板層不卡 S3 | 新增 issue（vision pose periodic re-emit / `/state/pose` 訂閱，需 HITL）；非「退簡單句」 |
| **D4 S4 Studio 鈕** | 藏 GestureToggle 按鈕、偵測全程 ON、phase gate 管範圍 | P1-4（採「藏鈕保偵測」非「關偵測」） |
| **D5 S4 peace** | 接受現行 config（零 code） | P1-3 |
| **D6 S4 wiggle** | Go2 motion → e-stop；不穩退純語音 | P1-5 |
| **D7 S5 指令** | 維持 backflip/翻跟斗（零 code、不換詞） | P1-7 相關 |
| **D8 ⚠️ S5 觸發** | **語音現場喊主線** + Studio 文字補打當即時 fallback | P1-7（採語音主線，非文字主線） |
| **D9 ⚠️ Act1** | **live 障礙停版（Go2 自走遇障停）**，motion 紅線六關 + `slow_policy=stop` profile；不穩退人推障礙(零 motion)→影片 | P0-3/P0-4/P0-5（採 A live upside 為目標、B/C 為退場，非 B 預設） |
| **D10 ⚠️ offline** | **小 code 修** `set_parameters` 寫回（非 docs-only SOP） | P1-8（升級為 code fix + smoke） |
| **D11 gateway auth** | 6/18 維持 OFF | 跨 issue |
| **D12 CLI** | venv+uv（pipx post-6/18）+ 單頁 Mac checklist + start.sh Mac-compat 驗 | P0-7/P0-8/P1-11 |
| **D13 ⚠️ object A/B** | **6/15-16 跑** n@640 矩陣 + supervision offline（需 demo MP4+JSONL 素材） | P1-10/P2-1/P2-2（提前至 6/15-16，非 post-6/18） |
| **D14 auto-advance** | 全幕 manual FLOOR（不碰 auto-advance）+ 15 句 TTS 暖機 | P0-6 |

**待 Roy 動作**：DEMO_CANNED_TABLE 15 句台詞 6/15 前簽核。

**AFK 可先做（需 Roy 授權動 runtime code，每條小 PR/default-off/smoke）**：D1、D2、D4、D10。
**Roy 在場 HITL**：D3、D6/D9（motion+e-stop）、D8、D12、D13、S2 re-enroll。

---

## 目錄（依 Priority 分組）

### P0（6/18 demo 阻斷級，必須先解或先確認分支）
1. [P0-1] S3：Brain 只取 objects[0] + whitelist 含 phone → 講手機不講杯子（cup 優先序）
2. [P0-2] S3：object_remark 硬卡 attention==ENGAGED → cup 慢一拍/被吞
3. [P0-3] Act1：先確定當天跑哪個 topology（standalone reactive_stop vs progressive nav stack）
4. [P0-4] Act1：LiDAR 活著但前錐讀 2.09m 淨空 = 障礙物低於掃描平面（no-motion 前置門檻）
5. [P0-5] Act1：6/18 fallback ladder 拍板（預設 B 遙控+Foxglove，A 為 e-stop upside，C 影片保底）
6. [P0-6] demo flow：manual-floor 無 auto canned-rescue → dead-air 全靠操作員，需彩排分工
7. [P0-7] MacBook 6/18 主操作前置 checklist（閘門過後的本機隱性依賴）
8. [P0-8] 各平台逐指令行為矩陣（純 SSH 安全 vs 本機 bash 分水嶺）

### P1（會降穩定度 / 影響展示，盡量 6/18 前處理）
9. [P1-1] S2：confirm greet 在 live config 已 PASS，鎖定 config 不被改回
10. [P1-2] S2：face_db sim 老化 + face_db 衛生（demo 前 re-enroll + 清 ghost dir）
11. [P1-3] S4：只保留 peace、關其他手勢辨識（thumbs_up_demo_ack + gesture_direct_disabled）
12. [P1-4] S4：關掉 Studio 手勢按鈕（先釐清 GestureToggle vs SkillButtons）
13. [P1-5] S4：wiggle 是 Go2 實體 motion → SOP 強制 e-stop + 語音 fallback
14. [P1-6] S5：拒絕 trace / BLOCKED 紅字當鏡頭證據（safety trace 落盤 + Studio 顯示）
15. [P1-7] S5：6/18 走 Studio 文字觸發規避 ASR 誤聽（鎖定觸發詞）
16. [P1-8] offline_mode topic↔param 驗證陷阱（行為對但 ros2 param get 撒謊）
17. [P1-9] operator-runbook 過時契約備註修正（#1/#2/#3）+ dry-run
18. [P1-10] object baseline 矩陣（現役 n@640 跑 cup/bottle/phone/chair × 距離）
19. [P1-11] PawAI CLI face enroll gap（_clean_face_name 不對稱 + 無 sim 閉環）
20. [P1-12] full rehearsal checklist（6/17 回穩日五幕彩排）

### P2（6/18 後 / 加分項 / 研究記錄）
21. [P2-1] YOLO26s 換模研究（ONNX 已 export 未上 Jetson，6/18 前不換）
22. [P2-2] Supervision offline confusion matrix benchmark（WSL throwaway venv）
23. [P2-3] S3 dedup 換 take SOP（producer 5s + brain 60s 疊加）
24. [P2-4] PawAI CLI PowerShell native blocker list（明確不支援、不繞過）
25. [P2-5] post-6/18 single Go2 driver 架構重構（LT-0~LT-6）
26. [P2-6] reactive_stop path-corridor / footprint-aware 升級（post-6/18 opt-in）

---

# P0

## [P0-1] S3：Brain 只取 objects[0] + whitelist 含 phone → 講手機不講杯子

- **Title**: S3 物品關懷講「手機」不講「杯子」：brain objects[0]-only + whitelist 含 cell_phone，需加 cup 優先序
- **Priority**: P0
- **Deadline**: 6/16（需 Roy 在場 echo + 簽優先序）
- **Scope**:
  - 確認真兇：producer `_publish_events` 依 YOLO NMS 信心序建 `new_objects`，brain `_on_object` 只取 `objects[0]`，cell_phone(67) 在白名單且在 `OBJECT_CLASS_ZH`（「手機」）→ phone 信心高就永遠搶 `objects[0]` 被講。
  - P0 最小外科（brain 端、default-off）：`_on_object` 對 `ev.objects` 先做 class 優先序排序再取首個。新增 `OBJECT_REMARK_PRIORITY=('cup','bottle','bowl','book',...)` param-gated，預設沿用 `objects[0]`（byte-identical）。滿足 Roy「cup 優先、bottle 也可」。
  - 現場零 code 應急：`ros2 param set /object_perception_node class_whitelist '[41,39,45]'`（VIS-2 runtime callback 即時生效）只留 cup/bottle/bowl，踢掉 phone/laptop。
- **Forbidden scope**:
  - 不動 producer `_publish_events` 排序（會影響 Studio chip 順序，scope 太大）。
  - 不引 model runtime switch（換模型不解此題，真兇在 brain）。
  - 不大改 perception_router / zh_tables 跨 consumer 結構。
- **Evidence**:
  - Live HITL：杯子放面前~1m，UI 跳 cup 但 Brain 一直講 Roy 的手機。
  - `object_perception/object_perception/object_perception_node.py:438-451`（new_objects 建構）
  - `interaction_executive/interaction_executive/perception_router.py:128` / `brain_node.py:2245-2257`（objects[0]）
  - `pawai_contracts/pawai_contracts/zh_tables.py:22`（cell_phone='手機'）
  - `object_perception/config/object_perception.yaml:21`（whitelist 含 67）
- **Acceptance criteria**:
  - 上機 `ros2 topic echo /event/object_detected` 確認 phone 是否在 `objects[0]`、cup/phone confidence 值。
  - 套用 P0 排序 param 後：杯子在面前時 Brain 講「看到杯子了」而非手機；phone 在 objects 內也被排到 cup 之後。
  - 預設不開 param 時行為 byte-identical（沿用 objects[0]）。
- **Tests**:
  - `interaction_executive` 新增 unit test：mock objects=[phone(0.9), cup(0.6)]，開 priority param 後選 cup；不開時選 phone。
  - `ros2-test-suite --quick`（speech+face）+ brain package tests 全綠。
- **HITL required**: yes（需 Roy 在場 echo /event/object_detected + 確認 cup 浮現）
- **Rollback**: param 預設關 → 直接 byte-identical；現場 param set 可即時切回原 whitelist。
- **Suggested owner/lane**: Codex（brain-studio-lane worktree）寫 priority param + test；Roy HITL 驗證。

---

## [P0-2] S3：object_remark 硬卡 attention==ENGAGED → cup 慢一拍/被吞

- **Title**: S3 cup 慢一拍：object_remark 要求 attention==ENGAGED，S2 greet 後進 INTERACTING 需 quiet 8s 才回 ENGAGED
- **Priority**: P0
- **Deadline**: 6/16
- **Scope**:
  - 確認 `_on_object` 要求 `_attention_state_snapshot()==ENGAGED` 才發 object_remark；S2 greet 觸發後進 INTERACTING，要 active_plan 結束 + quiet_s=8.0s 才回 ENGAGED → S3 緊接 S2 時 cup 被 `attention_engaged` gate suppress。
  - P1 最小外科（default-off param）：新增 `object_remark_attention_min`（預設 `'ENGAGED'`=byte-identical），設 `'NOTICED'` 時對 cup/bottle 放寬到 NOTICED-or-better。符合 Roy「pose/距離不可卡住 S3」。
  - 用 `/brain/trace`（Plan E）直接看 cup 被哪個 gate 擋（attention_engaged vs active_plan vs tts_playing vs dedup），不需加 code。
- **Forbidden scope**:
  - 不全域縮 `quiet_s`（影響 idle 等其他路徑）；若要縮只在 demo profile。
  - 不移除 attention gate 本體（只加可調下限）。
- **Evidence**:
  - Live HITL：cup 辨識有出來但 Brain 慢一拍甚至不講。
  - `interaction_executive/interaction_executive/brain_node.py:2277`（attention gate）/ `:2283`（active_plan）/ `:2292`（tts_playing）
  - `interaction_executive/interaction_executive/attention_machine.py:271`（INTERACTING）/ `:35`（quiet_s=8.0）
- **Acceptance criteria**:
  - `/brain/trace` 過濾 `source_summary=class=cup` 找出真正 suppress gate。
  - 設 `object_remark_attention_min='NOTICED'` 後：S2 greet 緊接 S3 時 cup 仍能在 face 穩定下講出。
  - 預設值 byte-identical。
- **Tests**:
  - unit test：attention=NOTICED + param='NOTICED' → cup remark 通過；param='ENGAGED'（預設）→ 被擋。
  - brain package tests 全綠。
- **HITL required**: yes（需 Roy 在場看 /brain/trace 確認 gate）
- **Rollback**: param 預設 'ENGAGED' = byte-identical。
- **Suggested owner/lane**: Codex（brain-studio-lane）；Roy HITL 驗 trace。

---

## [P0-3] Act1：先確定當天跑哪個 topology

- **Title**: Act1 導航避障診斷分叉根：確認 6/14 當天跑 standalone reactive_stop 還是 progressive nav stack
- **Priority**: P0
- **Deadline**: 6/15（收工前 evidence pull，否則 stack 重啟即遺失）
- **Scope**:
  - Act1 失敗候選互斥（Go2 沒動 / 走歪 / reactive 沒啟 / cmd_vel 沒到 driver），必須先確定當天啟動形態，才能分流 80% 的診斷。
  - 純 no-motion 診斷：看當天 tmux session 名稱 + 啟動指令、`ros2 node list`（幾個 go2_driver）、`ros2 action list | grep goto`（有無殘留 active goal）、`pawai evidence pull` 找有無 `[PR1a]` goto log（有=progressive/goto；無=standalone）。
  - 結論寫死進 operator runbook：「Act1 用哪個腳本」避免兩條路混用。
- **Forbidden scope**:
  - 不發任何 goto/forward/motion 指令。
  - 不在此 issue 修 nav code（只做 topology 判定 + evidence 保全）。
- **Evidence**:
  - Live HITL：Act1 ❌ 沒成功；Roy 列候選含「Go2 沒動 / 走歪 / reactive 沒啟 / cmd_vel 沒到 driver」。
  - `scripts/start_nav_capability_demo_tmux.sh:98-113` / `scripts/start_reactive_stop_tmux.sh:56-63`
  - `docs/archive/superpowers-legacy/plans/2026-06-13-s1-low-risk-navigation-plan.md:13`
- **Acceptance criteria**:
  - 明確記錄當天 topology（standalone vs progressive）+ ros2 node list driver 數 + 有無 goto log。
  - `pawai evidence pull` 撈回當天 `runtime/traces/*.jsonl`（D0，只讀零 motion）。
- **Tests**:
  - 無 code 改動；驗證為 evidence pull 成功 + runbook 段落更新。
- **HITL required**: yes（需 Roy 在 Jetson 上跑 evidence pull / node list）
- **Rollback**: N/A（純診斷 + 文件）。
- **Suggested owner/lane**: Roy HITL（收工前優先做 evidence pull）；nav-avoidance-lane 整理 runbook。

---

## [P0-4] Act1：LiDAR 活著但前錐讀 2.09m 淨空 = 障礙物低於掃描平面

- **Title**: Act1 reactive_stop「沒看到障礙」no-motion 前置門檻：障礙物須高於 LiDAR ~0.50m 掃描平面
- **Priority**: P0
- **Deadline**: 6/17（回穩日 no-motion 驗證）
- **Scope**:
  - Stage1 LiDAR 11.9Hz 活、front±15°=2.09m，若障礙物放正前卻讀淨空 = LiDAR 沒偵測到（2D planar 盲區：mount z=0.18m + base_link 離地 ~0.32m → 掃描面約離地 0.50m）。矮於 ~0.50m 的障礙完全看不到。
  - operator runbook 寫死：Act1 障礙物必須 >0.6m 高、不反光、放正前方 ≤1.0m（進 danger 1.1m 內）。最穩用「人站正前」（人高度必過掃描面，trackB 6/8 NAV-2 已驗）。
  - 現場用 `lidar_front_sector.py --once` 先驗「障礙物確實被掃到」再開始 Act1（no-motion 前置門檻）。
- **Forbidden scope**:
  - 不 claim D435+LiDAR 已融合補盲區（F3，D435 現況只是 advisory 未進 costmap）。
  - 不發 motion。
- **Evidence**:
  - Stage1：LiDAR 11.9Hz、front±15°=2.09m、+20°=1.70m。
  - `docs/archive/navigation-legacy/research/2026-04-29-mount-measurement.md:76` / `2026-04-25-rplidar-a2m12-integration-log.md:306`
  - `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py:38-51` / `scripts/lidar_front_sector.py:85-96`
- **Acceptance criteria**:
  - 障礙物放正前 1.0m 時 `lidar_front_sector.py --once` 讀 ~1.0m（非 2.09m）。
  - `scan_health_check.py` 對該方向 NaN 比例正常。
  - runbook 補入「障礙物高度/材質/放置」硬性規定。
- **Tests**:
  - 無 code；驗證為 lidar_front_sector 讀數正確 + scan_health 正常。
- **HITL required**: yes（需 Jetson + 實體障礙物）
- **Rollback**: N/A（純診斷 + 文件規定）。
- **Suggested owner/lane**: Roy HITL（Jetson no-motion）；nav-avoidance-lane 整理 runbook。

---

## [P0-5] Act1：6/18 fallback ladder 拍板

- **Title**: Act1 6/18 交付 fallback ladder：預設 B（遙控+Foxglove LiDAR 證據），A（standalone reactive_stop 障礙停）為 e-stop upside，C（影片）保底
- **Priority**: P0
- **Deadline**: 6/17（回穩日由 Roy 定 B-10 當天層）
- **Scope**:
  - B 層（預設主線）：遙控/手推障礙 + Foxglove 顯示 `/scan_rplidar` 點雲 + reactive zone 狀態當「邊緣端即時感知環境」證據，零 motion（Go2 站著、移動的是障礙物）。
  - A 層（upside，需條件）：standalone reactive_stop 障礙停（trackB 6/8 NAV-2 已驗「人/箱 1.03m → danger → Go2 停、0 撞」）。前提：Roy+e-stop+障礙物高度過掃描平面+indoor_tight 窄錐重驗無誤擋+人站正前最穩。
  - C 層（保底）：S1 影片已錄（demo snapshot tag），旁白用保守版。
  - 不採 goto/progressive（綁 6/13 R1/R2 走歪根因）。
- **Forbidden scope**:
  - goto_relative / DriveOnHeading 不當 live 主線。
  - A 層不穩立即退 B/C，不硬演。
  - 台詞禁 F1-F10（自主導航/動態繞障/D435 已融合/auto-resume）；safe-stop≠繞障標準說法。
- **Evidence**:
  - Live HITL：Act1 ❌ 沒成功。
  - `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-s1-fallback-decision.md:20`
  - `docs/archive/navigation-legacy/research/2026-06-08-trackB-hitl-results.md:14`
  - `scripts/start_reactive_stop_tmux.sh:74-79`
- **Acceptance criteria**:
  - 6/17 Roy 拍板當天採哪層 + A 層前置門檻全列（lidar_front_sector 看得到 + param 驗 indoor_tight + e-stop 就位 + 場地淨空）。
  - B 層 Foxglove `/scan_rplidar` 點雲可顯示 + reactive status topic 活。
  - C 層 demo snapshot 影片 tag 存在可播。
- **Tests**:
  - 無 code；驗證為三層各自前置都備齊。
- **HITL required**: yes（Roy 拍板 + A 層需 e-stop）
- **Rollback**: 任何情況退 B/C。
- **Suggested owner/lane**: Roy（決策）；nav-avoidance-lane（備齊 B/C 前置）。

---

## [P0-6] demo flow：manual-floor 無 auto canned-rescue → dead-air 靠操作員

- **Title**: demo flow never-dead-air：manual-floor 模式 per-phase max_wait timer 永不 arm，需彩排分派計時+canned 觸發角色
- **Priority**: P0
- **Deadline**: 6/17（彩排決定每幕是否逐幕開 auto）
- **Scope**:
  - 確認 `auto_advance_phases=[]`（預設 OFF）→ `_arm_phase_wait_timer` 只在 `_auto_advance_on(phase)=True` 才 arm → `_on_phase_max_wait` 永不觸發 → brain 不會自動補話。manual-floor 下 never-dead-air 全靠操作員手按。
  - 保守版（6/18 主線）：每幕不開 auto_advance；彩排分派「計時人 + canned 觸發人」，max_wait 內沒視覺觸發就 Studio skill_request(say_canned) 或文字補話。
  - 理想版（6/17 彩排才決定）：只對 S2 開 `auto_advance_phases=['s2_greet']`（進場 greet 自動補 + max_wait rescue），S3/S4/S5 仍 manual floor，一鍵退 `[]`。
  - 必做：tts canned 暖機（15 句各發一次 /tts 進 cache），避免首句 2.4s 延遲被當 dead air（禁 mid-session 重啟 tts_node）。
- **Forbidden scope**:
  - auto-advance 不預設開（forbidden scope）；若開只能單幕現場手動 + Roy 點頭。
  - 不 mid-session 重啟 tts_node（Megaphone silent fail）。
- **Evidence**:
  - `interaction_executive/interaction_executive/brain_node.py:468-473`（timer arm gate）/ `:578-613`（canned rescue）/ `:1443-1470`（chat timeout）
  - `docs/runbook/2026-06-18-operator-runbook.md:271-278`
- **Acceptance criteria**:
  - 彩排確認 dead-air 上限 ≤ chat_wait_ms（1.5s）對語音路徑；純視覺空檔由操作員手動補話流程驗過。
  - 15 句 canned 暖機後首句 latency≈0。
  - 若逐幕開 S2 auto，驗一鍵退回 `[]`。
- **Tests**:
  - brain package tests 全綠（auto_advance_phases 為空時不 arm timer 的既有測試）。
- **HITL required**: yes（彩排 + Jetson）
- **Rollback**: `auto_advance_phases:=[]` 一鍵退回 manual floor。
- **Suggested owner/lane**: Roy HITL（彩排分工）；brain-studio-lane（暖機 SOP）。

---

## [P0-7] MacBook 6/18 主操作前置 checklist

- **Title**: MacBook operator setup checklist：CLI 閘門過後的本機隱性依賴（ssh/rsync/bash + brain-studio-lane .sh + Tailscale）
- **Priority**: P0
- **Deadline**: 6/16（6/18 主操作前要驗過）
- **Scope**:
  - 產出單頁 MacBook checklist（docs，不改 code）：
    1. `brew install tmux node` + `brew install --cask tailscale`，登入並接受 share
    2. `git clone` repo 到 `~/elder_and_dog`（不要 iCloud Drive 同步目錄）
    3. `python3 -m venv ~/.venv` + `uv pip install -e tools/pawai_cli`
    4. `~/.ssh/config` 建 `Host jetson-nano` 指向 Tailscale IP + `ssh-copy-id`
    5. `cp .env.local.example .env.local` 填 keys
    6. `pawai doctor` 全綠（注意 Tailscale CLI PATH，GUI 版 binary 不一定在 PATH）
    7. `pawai status` / `smoke brain` / `evidence pull` 走純 SSH 先驗
    8. `pawai demo start` 最後驗（需本機 bash 跑 start.sh）
  - 確認 flock 不是本機依賴（全在 Jetson run_remote），macOS 無 flock 也能 demo start lock。
- **Forbidden scope**:
  - 不加 pipx 安裝路徑（現行 218 測試/CI 假設 venv+uv，6/18 前不改安裝機制；pipx 列 post-6/18）。
  - 不改 `shell.stream` bash 呼叫核心路徑。
- **Evidence**:
  - `tools/pawai_cli/pawai_cli/main.py:803/882`（demo 走本機 bash 跑 .sh）
  - `tools/pawai_cli/pawai_cli/lock.py:18`（flock 全遠端）
  - `docs/pawai_cli/troubleshooting.md:340`（Mac 搬家 7 步）
- **Acceptance criteria**:
  - MacBook 上 `pawai doctor` 全綠。
  - `pawai status` / `smoke brain` / `evidence pull`（純 SSH）在 Mac 與 WSL 輸出等價。
  - `bash .claude/skills/brain-studio-lane/scripts/start.sh demo` 在 Mac 無 GNU-only / zsh-only 假設（HITL 驗）。
- **Tests**:
  - 無 code；驗證為 Mac 上實跑各指令 exit code。
- **HITL required**: yes（需 Roy 的 MacBook 實機）
- **Rollback**: N/A（純文件 checklist）。
- **Suggested owner/lane**: pawai-cli lane（寫 checklist）；Roy HITL（MacBook 實跑驗 start.sh）。

---

## [P0-8] 各平台逐指令行為矩陣（純 SSH vs 本機 bash 分水嶺）

- **Title**: 6/18 CLI runbook 兩層：純 SSH 指令（status/smoke/evidence/logs）跨平台等價，本機 bash 指令（demo start/stop/health）是分水嶺
- **Priority**: P0
- **Deadline**: 6/16
- **Scope**:
  - 產出指令矩陣 docs：
    - Layer A（純 SSH，Mac/WSL2 完全等價）：`status` / `smoke brain` / `evidence pull` / `logs` / `contract check --jetson`
    - Layer B（本機 bash + repo + Studio node_modules）：`demo start` / `demo stop` / `health brain`
  - 每指令標「誰跑 / 前提 / 失敗 hint」（demo start 前提=lock 未被鎖；smoke brain 前提=demo 已 start；evidence pull 前提=trace store 開）。
  - WSL checklist：repo 在 `~/`（非 /mnt/c，會被 check_repo_path 擋）+ ssh/rsync/tmux/flock 本機有 + uv 已裝。
- **Forbidden scope**:
  - 不改 demo start/stop 核心路徑。
  - 不為 cross-platform 把 bash 呼叫改 subprocess（forbidden，6/18 禁）。
- **Evidence**:
  - `tools/pawai_cli/pawai_cli/status.py:109` / `main.py:954`（smoke）/ `main.py:1870`（logs）/ `evidence.py:107`
  - `tools/pawai_cli/pawai_cli/main.py:1586/1659`（demo start/stop 走本機 bash）
- **Acceptance criteria**:
  - 矩陣文件列全指令的 Layer 分類 + 前提 + 失敗 hint。
  - 上機驗：純 SSH 三類在 Mac 與 WSL exit code/輸出對照一致。
- **Tests**:
  - 無 code；驗證為矩陣與實機行為一致。
- **HITL required**: yes（Mac + WSL 對照需實機）
- **Rollback**: N/A（純文件）。
- **Suggested owner/lane**: pawai-cli lane；Roy HITL（Mac 對照）。

---

# P1

## [P1-1] S2：confirm greet 在 live config 已 PASS，鎖定 config

- **Title**: S2 認人問候 go/no-go=GO：鎖定 executive.yaml greet_require_sitting:false 不被改回
- **Priority**: P1
- **Deadline**: 6/16
- **Scope**:
  - 確認 live demo 走 `interaction_executive.launch.py` 載 `executive.yaml`（`greet_require_sitting:false`），與 Roy「~2s greet、沒 pose 也觸發」一致；`demo_phase="all"` 使 `_phase_allows("greet")` 永真；`stranger_alert_enabled=false` 移除 6/9 黑屏真兇。
  - runbook 標明「S2 PASS 前提 = executive.yaml greet_require_sitting:false 已部署到 Jetson」。
  - 現場保底：`ros2 param set /brain_node greet_require_sitting false`（即時生效 callback）。
- **Forbidden scope**:
  - 不把 yaml 改回 true（會退回黑屏症狀）；若未來改回須同步改 skill_contract 台詞。
  - 不改 greet 觸發機制本體。
- **Evidence**:
  - Live HITL：S2 ✅（~2s greet、3m OK、pose 沒出仍觸發）。
  - `interaction_executive/config/executive.yaml:35`
  - `interaction_executive/interaction_executive/brain_node.py:2100-2107`（_on_face）/ `:774-836`（param declare）
- **Acceptance criteria**:
  - `ros2 param get /brain_node greet_require_sitting` 回 false（非 code default true）。
  - runbook 補入前提聲明。
- **Tests**:
  - 既有 brain greet 測試全綠。
- **HITL required**: no（config 已正確，僅文件 + param get 驗證；param get 可由 Roy 順手驗）
- **Rollback**: 現場 param set 可即時切。
- **Suggested owner/lane**: brain-studio-lane（runbook 聲明）；Roy 順手 param get 確認。

---

## [P1-2] S2：face_db sim 老化 + face_db 衛生

- **Title**: S2 greet 單點故障：face_db sim 老化（demo 前現場光線 re-enroll + 清 ghost dir）
- **Priority**: P1
- **Deadline**: 6/17（demo 現場時段）
- **Scope**:
  - sim 老化是 greet 整條路徑唯一單點故障（6/8 記錄 Roy 舊圖 sim 0.2→re-enroll 後 0.73-0.81）。低光只影響 RGB 端 YuNet 偵測 + SFace sim（greet 不讀 depth，低光不擋深度路徑）。
  - SOP：demo 前在現場光線下 `pawai face enroll --person-name roy` → `pawai face rebuild` → 重啟 face node → `ros2 topic echo /state/perception/face` 看 sim≥0.7；`cp -p model_sface.*` 備份。
  - face_db 衛生：移除所有 `_backup/old/.tmp` 子目錄到 face_db 外（`train_model` 把所有子目錄當人名訓進 centroid 稀釋）。
- **Forbidden scope**:
  - 不改 face_identity_node runtime（dirname 黑名單實裝列 open decision，6/18 前用 shell 清理）。
  - 不降 sim_threshold_upper 當常態（升 false-positive，與 stranger_alert 取捨）。
- **Evidence**:
  - `face_perception/config/face_perception.yaml:11-24`
  - `face_perception/face_perception/face_identity_node.py:561-598`（decide_stable）/ `:709-718`（identity_stable）
  - `docs/archive/pawai-brain-legacy/research/2026-06-08-night-vision-brain-research.md`
- **Acceptance criteria**:
  - demo 前一天在現場光線量 Roy raw_sim n≥10 確認 ≥0.7。
  - `ls -la /home/jetson/face_db/` 只有真人子目錄、無 ghost dir。
- **Tests**:
  - 無 code；驗證為 re-enroll 後 sim 量測 + face_db ls 乾淨。
- **HITL required**: yes（Jetson + 現場光線 + Roy 的臉）
- **Rollback**: 保留 re-enroll 前的 `model_sface.*` 備份可回滾。
- **Suggested owner/lane**: Roy HITL（face enroll + 清 face_db）。

---

## [P1-3] S4：只保留 peace、關其他手勢辨識

- **Title**: S4 手勢收斂：只保留 peace 觸發，thumbs_up_demo_ack=true + gesture_direct_disabled=true 關其他手勢
- **Priority**: P1
- **Deadline**: 6/16
- **Scope**:
  - 確認現行 yaml 已使 palm/fist/index/wave 進 `_on_gesture` 後不命中 `_GESTURE_DIRECT/_GESTURE_CONFIRM` → 無動作；唯一殘留是 thumbs_up 仍→wiggle。
  - 零 code：demo 啟動帶 `peace_wego_confirm:=true` + `gesture_direct_disabled:=true` + `thumbs_up_demo_ack:=true` → 只有 peace 引 wiggle confirm，其他手勢無動作；OK 維持 confirm 用（不可關）。
  - 文件化現行行為進 runbook（demo_phase=s4_gesture 隔離不被 greet/object 搶話）。
  - 若 vision 無法只發 peace 且要硬性白名單：列為計畫項（brain `_on_gesture` 加 `gesture_allowlist` declared param 預設空=現行行為），需 Roy 授權後另開、非本輪。
- **Forbidden scope**:
  - 不在 vision 層砍 recognizer 輸出（破壞 Studio gesture-panel 視覺化 + trace 證據）；過濾在 brain 層。
  - 不關 OK 幾何 override（關了 peace 無法二確認）。
  - 本輪不實作 gesture_allowlist code（只計畫）。
- **Evidence**:
  - Live HITL：S4 ✅（peace→「比OK就開始」→OK→wiggle）；Roy 要求只保留 peace。
  - `interaction_executive/config/executive.yaml:13-43`
  - `interaction_executive/interaction_executive/brain_node.py:1628-1646`（_on_gesture）/ `:859-887`（map 建構）
- **Acceptance criteria**:
  - 上機：比 palm/fist/wave 無任何 Go2 反應（只 Studio trace）。
  - thumbs_up_demo_ack=true 後比讚不引出 wiggle。
  - 只有 peace→OK→wiggle 觸發 motion。
- **Tests**:
  - brain gesture 測試全綠（_GESTURE_DIRECT 為空 + thumbs_up_demo_ack 行為）。
- **HITL required**: yes（需 Jetson 實機驗 thumbs_up/其他手勢）
- **Rollback**: 三個 param 都 default-off，移除 launch override 即回原行為。
- **Suggested owner/lane**: brain-studio-lane（launch override + runbook）；Roy HITL 驗。

---

## [P1-4] S4：關掉 Studio 手勢按鈕

- **Title**: S4 關 Studio 手勢按鈕：先釐清 Roy 指 GestureToggle（ON/OFF）還是 SkillButtons（直觸 wiggle）
- **Priority**: P1
- **Deadline**: 6/16（需 Roy 釐清需求）
- **Scope**:
  - 釐清：Studio 沒有「逐手勢觸發按鈕」。唯一手勢控制是 `GestureToggle`（POST /api/gesture_enabled，整段開關手勢辨識）；另有 `SkillButtons` 能 POST skill_request 直接觸發 wiggle/stretch（繞過手勢/OK，對 Go2 安全更關鍵）。
  - 若指 GestureToggle：純前端條件隱藏（`chat-panel.tsx:392/431`），demo 期不顯示，改用 ros2 param set 控 gesture_enabled。
  - 若指 SkillButtons：demo 期把整塊隱藏或只在 `?dev=1` dev panel 顯示，防誤點直接 wiggle。
- **Forbidden scope**:
  - 不動 gateway `/api/gesture_enabled` plumbing（byte-identical default-off 機制，前端隱藏即可）。
  - 不關 GestureToggle 的後端（S4 段需 gesture_enabled ON）。
- **Evidence**:
  - Live HITL：Roy 要求「關掉網頁手勢按鈕（peace 不太會誤觸）」。
  - `pawai-studio/frontend/components/chat/gesture-toggle.tsx:19-100`
  - `pawai-studio/frontend/components/chat/brain/skill-buttons.tsx:38-46`
- **Acceptance criteria**:
  - Roy 確認指哪個按鈕。
  - 對應前端條件隱藏後 demo 主控視圖看不到該按鈕；後端機制不變（仍可 ros2 param set）。
- **Tests**:
  - frontend lint/build 通過；gateway 行為 byte-identical。
- **HITL required**: yes（需 Roy 釐清 + 看前端）
- **Rollback**: 前端條件隱藏可 flag 切回顯示。
- **Suggested owner/lane**: brain-studio-lane（前端隱藏）；Roy（釐清需求）。

---

## [P1-5] S4：wiggle 是 Go2 實體 motion → SOP 強制 e-stop

- **Title**: S4 wiggle（api_id 1020 原地扭）屬 forbidden scope motion：SOP 強制 Roy 授權 + e-stop + 語音 fallback
- **Priority**: P1
- **Deadline**: 6/17
- **Scope**:
  - 確認 wiggle→wiggle_hip→api_id 1020（原地扭動非位移，cooldown 10s、requires_confirmation=True，不在 BANNED_API_IDS）。唯一允許的 Go2 motion，仍須 Roy 授權 + e-stop。
  - SOP：S4 wiggle 前 Roy 授權 + 操作員 e-stop（遙控器急停）在手，wiggle 期間站姿留足空間。
  - 台詞 fallback：若現場不便讓 Go2 動，peace→OK 後改發 say_canned「好，我跟你 WeGo 一下！」不發 motion（需 Roy 簽該句）。
- **Forbidden scope**:
  - 不把 wiggle 改成 direct（繞 OK 確認）；維持兩步確認。
  - 不解除 requires_confirmation。
- **Evidence**:
  - Live HITL：S4 ✅ Go2 真的 wiggle 了。
  - `pawai_contracts/pawai_contracts/skill_contract.py:110-134`（1020 + BANNED）
  - `interaction_executive/interaction_executive/safety_layer.py:22-64`
- **Acceptance criteria**:
  - runbook 列明 S4 wiggle = e-stop 必備 + Roy 授權。
  - 語音 fallback 句由 Roy 6/15 簽。
- **Tests**:
  - 無 code；驗證為 SOP 文件 + fallback 句定稿。
- **HITL required**: yes（wiggle 是 motion，e-stop 實機）
- **Rollback**: 退語音 fallback（不發 motion）。
- **Suggested owner/lane**: Roy（授權 + 簽句）；nav/brain lane（runbook）。

---

## [P1-6] S5：拒絕 trace / BLOCKED 紅字當鏡頭證據

- **Title**: S5 safety trace：BLOCKED_BY_SAFETY 落盤 runtime/traces + Studio 紅字當三層架構視覺化證據
- **Priority**: P1
- **Deadline**: 6/17
- **Scope**:
  - 確認 S5 是真實執行層 reject（非裝飾）：`request_backflip`→IE node validate→`banned_api:1301`→`BLOCKED_BY_SAFETY`+`_trace_safety_block`→gateway 落盤 `runtime/traces/*.jsonl`+WS 廣播→Studio `chat-panel.tsx:557` 紅字。
  - demo 現場驗：跑一次 S5 後 `pawai evidence pull` 確認 jsonl 有 `banned_api:1301` 那筆 + Studio frontend 紅字真的出現。
  - 6/18 把 Studio trace drawer / BLOCKED 紅字當鏡頭證據主動展示（呂奇傑 5/22 指定「三層架構唯一視覺化證據」）。
- **Forbidden scope**:
  - 不改 SafetyLayer / BANNED_API_IDS（已 proven 端到端）。
  - 不 secure-default full flip（gateway auth 維持 OFF）。
- **Evidence**:
  - Live HITL：S5 ✅ 秒回「這個動作不安全，我不能執行」。
  - `interaction_executive/interaction_executive/interaction_executive_node.py:151-160`
  - `pawai-studio/gateway/studio_gateway.py:788`（落盤）/ `trace_store.py:62`
  - `pawai-studio/frontend/components/chat/chat-panel.tsx:557`（紅字）
- **Acceptance criteria**:
  - 跑 S5 後 evidence pull 撈到 `banned_api:1301` trace。
  - Studio frontend 顯示 blocked_by_safety 紅字 + detail。
  - demo 機 gateway+frontend 起得來、trace 落盤正常。
- **Tests**:
  - 既有 36 個 safety_layer 測試全綠。
- **HITL required**: yes（需 demo 機 gateway+frontend 同跑驗紅字 + evidence pull）
- **Rollback**: N/A（純驗證 + 展示，無 code 改）。
- **Suggested owner/lane**: brain-studio-lane（驗證 + 展示流程）；Roy HITL。

---

## [P1-7] S5：6/18 走 Studio 文字觸發規避 ASR 誤聽

- **Title**: S5 主線走 Studio 文字觸發（operator S5-Trigger），語音當加分 take，鎖定觸發詞
- **Priority**: P1
- **Deadline**: 6/16
- **Scope**:
  - 確認鍵詞表固定 + ASR 誤聽（Go2 風扇 ~20% 誤辨）是唯一弱點。6/18 走 Studio 文字框觸發（100% 命中鍵詞）可完全規避。
  - SOP：S5 主線 = Studio 文字框打「後空翻/翻跟斗」；語音現場喊當加分 take。
  - 若 Roy 要新增危險詞：改 `safety_layer.py:23 UNSAFE_KEYWORDS_REJECT` + 補 parametrize test + colcon build（非零風險，僅 Roy 明確要換/加詞時做）。
- **Forbidden scope**:
  - 6/18 前不換詞（backflip 已 6/10 proven 端到端），除非 Roy/老師明確要求。
  - 不改拒絕語句結構（統一「這個動作不安全，我不能執行。」）。
- **Evidence**:
  - Live HITL：S5 ✅ 語音喊後空翻秒回。
  - `interaction_executive/interaction_executive/safety_layer.py:23`（8 詞表）/ `:71`（substring）
  - `pawai_contracts/pawai_contracts/llm_policy.py:10`（backflip 不在 LLM 可提案）
- **Acceptance criteria**:
  - runbook 寫明 S5 主線=Studio 文字觸發。
  - demo 腳本鎖定只喊收錄的「後空翻/翻跟斗」。
- **Tests**:
  - 若改詞：safety_layer parametrize test 涵蓋新詞 + 全綠。
- **HITL required**: yes（需 Roy 決策觸發方式 + 鎖腳本）
- **Rollback**: 退語音現場喊（已 proven）。
- **Suggested owner/lane**: Roy（決策觸發方式）；brain-studio-lane（runbook + 若改詞）。

---

## [P1-8] offline_mode topic↔param 驗證陷阱

- **Title**: offline_mode 行為已對但 ros2 param get 撒謊：驗證 SOP 改看 /brain/trace 或聽秒回 canned
- **Priority**: P1
- **Deadline**: 6/16
- **Scope**:
  - 確認 topic↔param 已接通（brain 有 `/brain/offline_mode` Bool subscriber，gateway publish_offline_mode 發 Bool，QoS 相容、行為正確）。真正 gap：`_set_offline_mode`/`_set_demo_phase` 不呼叫 set_parameters → topic 切換後 `ros2 param get` 仍回舊值（cache 非真值）。
  - P1 操作 SOP（零 code）：HITL §4 加「Studio offline toggle 切換後不要用 ros2 param get 驗證，改看 `/brain/trace` 出現 `reason=offline_mode` 的 say_canned 或聽是否秒回 canned」；更新 runbook 移除「param get 驗 offline」誤導。
  - 備援（proven）：若 topic 沒生效退啟動前 env override（`LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper`）。
  - P2 brain 端對齊（post-6/18）：`_set_offline_mode`/`_set_demo_phase` 在 via!='param' 時呼叫 set_parameters（避免遞迴），加單測。
- **Forbidden scope**:
  - 本輪不改 brain set_parameters（屬 post-6/18 P2）。
  - 不動 gateway topic plumbing。
- **Evidence**:
  - `interaction_executive/interaction_executive/brain_node.py:705-716`（_set_offline_mode）/ `:1419-1435`（offline 短路）
  - `pawai-studio/gateway/studio_gateway.py:858-875`
  - `docs/runbook/2026-06-18-operator-runbook.md:45`（過時聲明）
- **Acceptance criteria**:
  - 上機：Studio offline ON 後送一句語音秒回 canned（行為對）；同時 `ros2 param get` 仍回舊值（確認陷阱）。
  - runbook 驗證 SOP 改為看 trace / 聽秒回，移除 param get 誤導。
- **Tests**:
  - 無 code（本輪）；post-6/18 對齊 issue 才加單測。
- **HITL required**: yes（需 Jetson 驗 offline 行為 + param get 撒謊）
- **Rollback**: N/A（文件 SOP）。
- **Suggested owner/lane**: brain-studio-lane（runbook SOP）；Roy HITL 驗。

---

## [P1-9] operator-runbook 過時契約備註修正

- **Title**: operator-runbook 契約備註 #1/#2/#3 過時：PHASE_ALLOWED_KINDS 已含 5 canonical 幕、brain subscriber 已存在
- **Priority**: P1
- **Deadline**: 6/17（dry-run 前）
- **Scope**:
  - 更新 §契約備註：canonical 5 幕已收進 `PHASE_ALLOWED_KINDS`（`interaction_state.py:40-50`）、`/brain/demo_phase` subscriber 已存在（`brain_node.py:324-326`）、Studio 五幕鈕已可直發 canonical 名；移除「backup 用 s2_face/s3_object 等效名」的必要繞路（保留 alias 仍可用即可）。
  - 跑 P4-11 dry-run（找沒參與者照 §0-§5 唸）把過時/照不下去步驟逐條標出再修。
- **Forbidden scope**:
  - 不改 interaction_state / brain code（向後相容已成立，alias + canonical 都吃）。
  - 純 docs-only。
- **Evidence**:
  - `interaction_executive/interaction_executive/interaction_state.py:40-57`
  - `interaction_executive/interaction_executive/brain_node.py:324-326`
  - `docs/runbook/2026-06-18-operator-runbook.md:30-45`
- **Acceptance criteria**:
  - 上機 `ros2 param set /brain_node demo_phase s2_greet` 被接受（canonical 名可用）。
  - Studio 五幕鈕 POST /api/demo_phase → `ros2 topic echo /brain/demo_phase` 收到。
  - runbook 三條契約備註更新 + dry-run 抓出的步驟修正。
- **Tests**:
  - 無 code；驗證為 runbook 與 code 行為一致。
- **HITL required**: no（docs-only + dry-run 可由團隊任一人；canonical 名驗證可順手）
- **Rollback**: N/A（純文件）。
- **Suggested owner/lane**: brain-studio-lane（docs 更新 + dry-run 主持）。

---

## [P1-10] object baseline 矩陣（現役 n@640）

- **Title**: object baseline 矩陣：現役 yolo26n@640 跑 cup/bottle/phone/chair × 0.7/1.0/1.5m（零 runtime 風險）
- **Priority**: P1
- **Deadline**: 6/16（today-able，工具齊全）
- **Scope**:
  - 用 `scripts/obj_matrix_cap.py`（已有 PASS≥0.8/DEGRADED≥0.6/FAIL gate + 混淆收集 + CSV）跑現役 n@640：`cup/bottle/phone/chair × 0.7/1.0/1.5m`=12 cell，window≥6s（避 object cooldown 5s）。
  - 隔離跨流污染（obj_matrix_cap 只訂 object topic，天然隔離 gesture）。
  - 量 cup recall（success_rate proxy）+ avg_confidence + misclass（混淆共現）+ verdict，把「感覺」換成數據以決定換不換模型。
  - FPS/RAM/溫度另用 tegrastats 並排記（obj_matrix 不收）。
- **Forbidden scope**:
  - 不換模型（YOLO26s 上機矩陣是另一張 P2 issue）。
  - 不改 conf threshold（非 runtime param，改要 kill 重啟）。
  - 不引 Supervision 到 Jetson（offline-only，另一張 P2）。
- **Evidence**:
  - Live HITL：S3 cup↔phone 混淆（acceptance §4：0.7m phone 4 次/bottle 2 次）。
  - `scripts/obj_matrix_cap.py:99-187` / `benchmarks/core/object_matrix.py:28-110`
- **Acceptance criteria**:
  - 產出 `artifacts/object_matrix/baseline.csv`（12 cell）。
  - cup recall@各距離 + 混淆數據可餵 P0-1/P2-1 決策。
- **Tests**:
  - 無 code（用既有工具）；驗證為 CSV 產出且 cell 完整。
- **HITL required**: yes（需 Jetson live /event/object_detected + 實體物品）
- **Rollback**: N/A（純量測，read-only）。
- **Suggested owner/lane**: Roy HITL（Jetson 跑矩陣）；nav/object lane 整理數據。

---

## [P1-11] PawAI CLI face enroll gap

- **Title**: CLI face enroll gap：_clean_face_name 與 delete 不對稱 + 無 sim 驗證閉環 + ghost dir 重訓前沉默
- **Priority**: P1
- **Deadline**: 6/16（P0-B/P0-A 列入 checklist，實作需 Roy 授權）
- **Scope**:
  - 記錄 gap（本輪 read-only，不改 code）：
    - (a) `face enroll --person-name` 未過 `_clean_face_name`（delete 有，不對稱）。
    - (b) 無任何 face 子命令驗 sim≥0.7（`face test` 跑的是 pytest 非 sim 量測）。
    - (c) `train_model` 無條件把所有子目錄訓成身份，enroll/rebuild 重訓前不掃 ghost dir（只 `face list` 警告）。
  - 把 face-enroll-proposal.md 的 P0-A（ghost 警告 30min）+ P0-B（enroll 套 _clean_face_name 10min）列入 MacBook checklist 的「demo 前 face_db 衛生」段。
  - 決策給 Roy：P0-B（補不對稱注入面，極低風險）是否 6/18 前做；P1-A face verify（sim 閉環 2-3hr）延後 post-6/18。
- **Forbidden scope**:
  - 不改 face_identity_node runtime。
  - 不重做 .npz purge（T5-1 已完成測試不可動）。
  - 不引 Typer/Rich；不讓 enroll/rebuild 阻擋 ghost dir（只警告，保 byte-identical）。
  - 本輪不寫 code（需 Roy 授權後另開）。
- **Evidence**:
  - `tools/pawai_cli/pawai_cli/main.py:2025`（enroll 無 clean）/ `:1982`（_clean_face_name）/ `:1995`（delete 有）
  - `docs/pawai_cli/2026-06-14-face-enroll-cli-proposal.md:58`
- **Acceptance criteria**:
  - checklist 寫明 face SOP 現況（list 看 ghost → 手動移出 → enroll → rebuild → 重啟 → 手動 echo sim）。
  - Roy 決策 P0-A/P0-B 是否 6/18 前做。
- **Tests**:
  - 若 Roy 授權 P0-B：enroll 套 _clean_face_name 後加對應 test；既有 4 條 .npz purge 守門測試不可動。
- **HITL required**: yes（決策 + 若實作需驗）
- **Rollback**: 純研究無 code；若實作 P0-B 為小 PR 可 revert。
- **Suggested owner/lane**: pawai-cli lane（記錄 + checklist）；Roy（決策授權）。

---

## [P1-12] full rehearsal checklist

- **Title**: 6/17 回穩日五幕全流程彩排 checklist（S1-S5 + Act1 fallback + 主控分工）
- **Priority**: P1
- **Deadline**: 6/17
- **Scope**:
  - 產出單頁彩排 checklist 涵蓋：
    - 啟動：`pawai demo start`（單一 driver，起前 pkill 殘留）+ `tmux ls` + `ros2 node list` 數 process（不只信 CLI 成功訊息，6/4 CRLF 假成功教訓）。
    - 暖機：15 句 canned 各發一次 /tts 進 cache（禁 mid-session 重啟 tts_node）。
    - S2：Roy 從框外走入觸發進場 greet（event-only，離框 ~5s 重現）。
    - S3：擺 cup（whitelist cup-only 或 priority param），pose 當加分不卡；換 take 前發 /brain/reset_context。
    - S4：peace→OK→wiggle（e-stop 在手 + Roy 授權）；其他手勢無動作。
    - S5：Studio 文字觸發「後空翻」→ 秒回拒絕 + Studio 紅字證據。
    - Act1：依 P0-5 ladder（預設 B 遙控+Foxglove；A 需 e-stop；C 影片）。
    - 主控分工：MacBook 按 Studio 隱藏五幕鈕（FLOOR）+ 一人 SSH 在 Jetson 待命 param set backup + Trace-Watcher/計時/canned 觸發人。
    - 跑 demo-preflight `--full`。
- **Forbidden scope**:
  - 不開 auto-advance 預設。
  - 不演任何未授權 Go2 motion。
- **Evidence**:
  - 整合所有 lane 的 6/18 SOP；Live HITL 五幕結果為基準。
  - `docs/runbook/2026-06-18-operator-runbook.md`
- **Acceptance criteria**:
  - checklist 涵蓋五幕 + Act1 + 啟動驗證 + 主控分工 + preflight。
  - 6/17 跑一次完整 dry-run，逐項打勾。
- **Tests**:
  - `demo-preflight --full` 通過。
- **HITL required**: yes（全流程彩排需 Jetson + Go2 + Roy + 操作員）
- **Rollback**: 各幕都有 fallback（見各 issue）。
- **Suggested owner/lane**: Roy HITL（主持彩排）；各 lane 提供各幕 SOP。

---

# P2

## [P2-1] YOLO26s 換模研究（6/18 前不換）

- **Title**: YOLO26s 換模研究：4 顆 ONNX 已 export 未上 Jetson，6/18 前大概率不換（B-4 預設不換）
- **Priority**: P2
- **Deadline**: post-6/18
- **Scope**:
  - 記錄已查證：`yolo26s_640/yolo26n_960/yolo26s_960/yolo26n-pose_640` ONNX 早於 6/10 export 完、shape 全相容 `(1,300,6)`，但未 rsync 上 Jetson、TRT 未預燒。
  - 結論：6/18 前不換（S3 真兇是 brain 不是模型；換模 hard-to-reverse、需 TRT 預燒 + RAM 重量 + Roy 點頭 + rollback 驗證）。
  - 若 Roy 要數據：rsync 4 顆 ONNX（additive 5min）→ 前夜 TRT 預燒（不開 demo stack）→ 上機矩陣量 recall/混淆/Hz/RAM；`env OBJECT_MODEL=...` 一行切換（launch 已支援）。
  - 換模 gate：T2 同時滿足 cup@1.5m≥80% + 混淆較 n 明確下降 + ≥3Hz + RAM 餘≥0.8GB + 溫度<75°C + Roy 點頭 + rollback 驗證，落地時機 post-6/18 + 補 ADR。
- **Forbidden scope**:
  - 6/18 前不 model runtime switch（forbidden）。
  - 換 960 模型必 `OBJECT_INPUT_SIZE=960` 同步（fixed-shape）；960 配 640x480 相機=插值自欺。
- **Evidence**:
  - `.tmp/yolo_export/out/yolo26s_640.onnx`（38MB）/ `export.log`
  - `object_perception/launch/object_perception.launch.py:26-39`
- **Acceptance criteria**:
  - 研究結論記錄（6/18 前不換 + gate 條件 + 切換指令）。
- **Tests**:
  - 若 Roy 要量：上機矩陣（屬 P1-10 工具）+ ORT CPU sanity。
- **HITL required**: yes（若要上機量需 Jetson + Roy 在場）
- **Rollback**: `env OBJECT_MODEL` 一行切回 n@640。
- **Suggested owner/lane**: Roy（決策）；object/nav lane（若要量）。

---

## [P2-2] Supervision offline confusion matrix benchmark

- **Title**: Supervision offline confusion matrix：WSL throwaway venv 對 demo 錄影/JSONL 跑（永不進 Jetson runtime）
- **Priority**: P2
- **Deadline**: post-6/18（若 Roy 給素材路徑可 today-able）
- **Scope**:
  - 用 `uv venv .tmp/sv_venv && uv pip install supervision`（禁裝 Jetson）對 demo 錄影 MP4 + `/event/object_detected` JSONL 跑 `supervision_evidence_spike.py` 產 annotated MP4 + filtered JSONL；再用 `sv.metrics ConfusionMatrix(cup/phone/bottle)` 出真 per-frame 混淆矩陣餵 P0-1/P2-1 決策。
  - 產物（MP4/JSONL/CSV）不進 git；decision_id join 經 custom_data 回拋 Lane 2。
- **Forbidden scope**:
  - 永不把 supervision pip install 上 Jetson（硬依賴完整 opencv-python，違反 ≥0.8GB 紀律）。
  - 不做 runtime tiling/SAHI（已裁出局，過不了 ≥3Hz 門檻）。
- **Evidence**:
  - `benchmarks/scripts/supervision_evidence_spike.py:103-125`
  - `docs/perception/research/2026-06-11-objdet-upgrade-synthesis-result.md:45`
- **Acceptance criteria**:
  - 產出 cup/phone/bottle 真混淆矩陣（offline，WSL）。
- **Tests**:
  - 無 runtime；spike 腳本跑通。
- **HITL required**: no（WSL offline；唯一需 Roy 指認錄影/JSONL 素材路徑）
- **Rollback**: N/A（throwaway venv，不進 runtime）。
- **Suggested owner/lane**: Codex/Carl（WSL offline benchmark）；Roy 指認素材。

---

## [P2-3] S3 dedup 換 take SOP

- **Title**: S3 換 take SOP：producer 5s class_cooldown + brain 60s OBJECT_REMARK_DEDUP 疊加 → 每次擺 cup 前發 /brain/reset_context
- **Priority**: P2
- **Deadline**: 6/17（納入彩排 SOP）
- **Scope**:
  - 確認 `OBJECT_REMARK_DEDUP_S=60.0`（per-class）+ producer `class_cooldown_sec=5.0` 疊加 → cup 講一次後 60s 內被 suppress，換 take <60s 沉默被誤判成 bug。
  - SOP（零 code）：換 take 前 `ros2 topic pub --once /brain/reset_context std_msgs/Empty`（已有清 `_object_remark_seen` 邏輯）。
  - P2 可選：`OBJECT_REMARK_DEDUP_S` param 化（預設 60=byte-identical），demo profile 調短 15-20s。
- **Forbidden scope**:
  - 本輪不改 dedup 預設值。
- **Evidence**:
  - `interaction_executive/interaction_executive/brain_node.py:78`（dedup）/ `:2528`（reset 清 seen）
  - `object_perception/config/object_perception.yaml:15`（5s cooldown）
- **Acceptance criteria**:
  - 彩排 SOP 納入「換 take 前發 reset_context」。
- **Tests**:
  - 若 param 化：dedup param 單測。
- **HITL required**: no（SOP 為主；param 化若做需驗）
- **Rollback**: dedup param 預設 60 = byte-identical。
- **Suggested owner/lane**: brain-studio-lane（SOP + 可選 param 化）。

---

## [P2-4] PawAI CLI PowerShell native blocker list

- **Title**: PowerShell native blocker list：明確列為不支援（exit 10）、不繞過、導向 wsl --install
- **Priority**: P2
- **Deadline**: post-6/18（隊友卡 Windows 才急用）
- **Scope**:
  - 產出 blocker list（docs，不改 code）：
    1. exit 10 確定發生（`platform.py:40-45` windows_native，reason 已點名 PowerShell/CMD/Git Bash）。
    2. 根因不只一個閘門：無本機 bash 跑 demo .sh、~/.ssh/config 語意、rsync Windows 語意、repo .sh。
    3. 正解 = `wsl --install -d Ubuntu` 後在 WSL2 跑（repo clone 到 `~/` 不要 /mnt/c）或用 MacBook。
    4. 6/18 前不解 PowerShell native（forbidden：不做 full CLI v2/Typer 重寫）。
  - 可選 post-6/18 P2 修：H3 false-block（malformed /proc/version 含 microsoft 但無 'wsl2' 字面誤判 wsl1）改 default 視為 wsl2，加 test。
- **Forbidden scope**:
  - 不為 PowerShell 把 `shell.stream` bash 呼叫改 cross-platform subprocess。
  - 不做 full CLI v2/Typer 重寫。
- **Evidence**:
  - `tools/pawai_cli/pawai_cli/platform.py:40/44/111`
  - `tools/pawai_cli/pawai_cli/shell.py:43`（無 bash → 127）
  - `docs/pawai_cli/README.md:68`
- **Acceptance criteria**:
  - blocker list docs 列全根因 + 一步到位 `wsl --install -d Ubuntu` 指引。
- **Tests**:
  - 若修 H3：test_platform.py 對應 case。
- **HITL required**: no（docs；H3 修為純編輯 + 單測）
- **Rollback**: 純文件；H3 修為小 PR 可 revert。
- **Suggested owner/lane**: pawai-cli lane。

---

## [P2-5] post-6/18 single Go2 driver 架構重構

- **Title**: post-6/18 Single Go2 Driver refactor：LT-0 profiling gate → LT-1 修 T0 URDF → LT-2 superset launch → LT-3~LT-6
- **Priority**: P2
- **Deadline**: post-6/18（全待 LT-0 profiling 過 + Roy 授權 + e-stop + 真機 motion HITL）
- **Scope**:
  - 記錄治本架構（背景研究，零 runtime 變更）：
    - 雙 driver 衝突是真實架構斷層：Go2 對單一 ROBOT_IP 只接受一條 WebRTC peer，兩份 robot.launch.py + nav2_amcl 裸 driver = 多個 RTCPeerConnection 搶同一台 Go2 → ICE FROZEN→FAILED + topic 撞名。
    - LT-0：corun Config A profiling（brain 全感知 + 完整 nav 8GB）是 gate；FAIL 則退分時。
    - LT-1（P0）：從 single-mode URDF 移除 map→odom/odom→base_link fixed joint（T0 dual-authority，與 AMCL/driver 動態 TF 衝突），單檔一鍵 revert。
    - LT-2：single-driver superset launch（nav2:=true mux:=true teleop:=false），nav lane 不再自起 driver。
    - LT-3：nav2_amcl 改走 robot.launch.py + 同一 twist_mux，controller remap /cmd_vel_nav。
    - LT-4：修 enable_lidar arg leak（full_demo 傳 enable_lidar:=false 但 launch 沒宣告 → 被丟棄，driver 維持 True 仍 decode LiDAR）。
    - LT-5/LT-6：共享 brake 決策層（brain SafetyLayer 訂 reactive_stop status）+ actuation 層（driver interlock 同擋 cmd_vel Move + webrtc Move 1008），皆 default-off gated。
  - 6/18 前最小整合：文件禁令（dual-driver 寫進 lock collision）+ 靜態 no-motion 驗證 + raw LiDAR 證據窗（需先過 corun Config B profiling）。
- **Forbidden scope**:
  - 6/18 前不合併兩 launcher driver/mux、不讓 nav2_amcl 走 mux、不 always-on reactive_stop 疊進 demo、不任何 goto/DriveOnHeading/cmd_vel live motion 驗證。
  - 全部需真機 motion HITL，6/18 前不做。
- **Evidence**:
  - `go2_robot_sdk/.../webrtc/go2_connection.py:72/107`（單一 peer/channel）
  - `go2_robot_sdk/urdf/go2.urdf:49-50/71-72`（T0 fixed joint）
  - `go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py:132`（enable_lidar default True）
  - `docs/archive/navigation-legacy/plans/2026-06-14-unified-demo-stack-single-go2-driver-plan.md`
- **Acceptance criteria**:
  - 架構計畫文件完整（LT-0~LT-6 標 PLANNED + 順序依賴 + gate 條件）。
  - 6/18 前只落 ST-1/ST-2/ST-3/ST-5（文件 + no-motion 驗證 + 證據窗）。
- **Tests**:
  - LT-1 後 `echo /tf_static` 不含 map→odom/odom→base_link；M1 走直 n=3（需 e-stop）。
- **HITL required**: yes（全部 post-6/18 真機 motion HITL）
- **Rollback**: 每項 default-off / 單檔一鍵 revert / env 切換。
- **Suggested owner/lane**: nav-avoidance-lane（post-6/18）；Roy 授權 + e-stop。

---

## [P2-6] reactive_stop path-corridor / footprint-aware 升級

- **Title**: reactive_stop path-corridor / footprint-aware 升級（post-6/18 opt-in param，預設仍 cone）
- **Priority**: P2
- **Deadline**: post-6/18（~7/2，需卡尺實測機身）
- **Scope**:
  - 記錄：reactive_stop body-forward 錐不對齊斜走路徑、不考慮機身寬度（footprint 0.6×0.3 短於真實 0.7×0.31、機鼻 ~0.4-0.5m）→ 走歪時 off-axis 障礙進 danger 前機身角已可能接觸。
  - 升級：path-corridor（沿速度方向矩形含機身寬）+ footprint-aware，opt-in param 預設仍 cone（byte-identical）。
  - 6/18 不靠「走歪 + reactive 兜底」——Act1 走 standalone 純停障（直線前進或不前進，不走 goto 斜方向）。
  - Nav2 Collision Monitor polygon footprint 需卡尺實測機身。
- **Forbidden scope**:
  - 6/18 前不做（Act1 不靠 reactive 兜底走歪）。
  - 不改 cone 預設行為。
- **Evidence**:
  - `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py:5-51`
  - `go2_robot_sdk/config/nav2_params.yaml:220-238`（footprint 0.6×0.3）
  - `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-motion-incident-root-cause-plan.md:274`
- **Acceptance criteria**:
  - 升級計畫記錄（opt-in param + 卡尺實測待辦）。
- **Tests**:
  - post-6/18：corridor 納機身投影後 off-axis 障礙進 danger 的單測。
- **HITL required**: yes（post-6/18 真機 + 卡尺）
- **Rollback**: opt-in param 預設 cone = byte-identical。
- **Suggested owner/lane**: nav-avoidance-lane（post-6/18）。

---

## 附錄：給 Roy 的關鍵 open decisions（審草案時一併拍板）

1. **S3 修法選哪個**：① 現場 `ros2 param set class_whitelist '[41,...]'`（零 code、最安全）vs ② brain `_on_object` 做 cup 優先排序（治本、需授權 + smoke 全綠）。Roy「cup 優先、bottle 也可」暗示 ②，但 ② 是 6/18 前 runtime code 改。
2. **cell_phone 處置**：完全移出白名單（保留 UI）還是可講但排最後？建議 phone 移出講話白名單。
3. **pose 當加分**：接受「有 cup 一律講 cup，sitting 只在偵測到時升級複合句」？複合句現硬鎖 name=='Roy'，是否泛化成任意 known person？
4. **Act1 6/18 採哪層**：建議預設 B（遙控+Foxglove），A 為 e-stop upside，C 影片保底。Roy 是否同意 A 不當預設主線？
5. **Act1 收工前 evidence pull**：今晚是否先 `pawai evidence pull` 保住 Act1 那發的 zone 時間線（否則 stack 重啟遺失）？
6. **S4「關 Studio 手勢按鈕」指哪個**：GestureToggle（ON/OFF）還是 SkillButtons（直觸 wiggle）？後者對 Go2 安全更關鍵。
7. **S4「只保留 peace」程度**：接受現行（thumbs_up_demo_ack + gesture_direct_disabled）還是要硬性白名單（新增 gesture_allowlist code，需授權）？
8. **S5 觸發方式**：6/18 主線走 Studio 文字（建議）還是語音現場喊？是否維持「後空翻/翻跟斗」不換詞？
9. **DEMO_CANNED_TABLE 15 句**：6/15 簽核（含 S2 三層、S4 wiggle/fallback 句、S5 拒絕句）。
10. **auto-advance**：6/18 是否任何一幕開？建議只 S2 開（自動補進場 greet + max_wait rescue），其餘 manual floor。
11. **gateway auth**：6/18 凍結期維持 OFF（MacBook 直接可達）還是設 token？若設須同步前端帶 token。
12. **CLI face P0-A/P0-B**：6/18 前是否實作（需授權）？face verify（sim 閉環）確認延後 post-6/18。
13. **物體上機矩陣排程**：6/15-16 全天 / 半天精簡 / post-6/18？S3 不靠換模解決，換模上機可安心排 post-6/18。
