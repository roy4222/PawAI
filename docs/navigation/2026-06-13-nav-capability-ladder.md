# Navigation Capability Ladder + Proven Table（2026-06-13）

> **日期**：2026-06-13　**狀態**：DOC — Lane 6 T6-1（純文件，無實作碼）
> **上游**：[Lane 6 plan §2 evidence table](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)、[aggressive master §1 北極星](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)
> **這份是什麼**：把 Lane 6 plan §2 的 evidence table 擴寫成**正式能力階梯**——每個 nav 能力一節，含證據文件路徑、current label、升級條件（對應 §8 HITL matrix 的 N 項）、6/18 可否講。
> **這份不是什麼**：① 不是「現在能跑什麼」的 runtime 真相（runtime 行為以 code / topic schema 為準）；② 不是對外 claim 措辭（→ [`2026-06-13-nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md)）；③ 不是操作手冊（最安全 operator 流程 = [`docs/runbook/2026-06-18-hitl-oneshot-runbook.md`](../runbook/2026-06-18-hitl-oneshot-runbook.md) nav DRY-RUN 段 + [`docs/runbook/2026-06-13-roy-hitl-queue.md`](../runbook/2026-06-13-roy-hitl-queue.md) nav 場測段）。
> **權威關係**：本表的 current label **只能透過 §8 HITL matrix 結果升級**；任何升級都要回填本檔 + claim wording。與 6/4 trusted snapshot（[`baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/)）的關係見 §5。

---

## 1. 四級階梯定義（標籤詞彙）

Lane 6 T6-1 定義四個**階梯級別**，作為「這個能力成熟到哪」的粗粒度框架；每個能力另有一個**細粒度 current label**（沿用 Lane 6 §2 與 [capability-baseline-spec](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md) 的詞彙），兩者對應關係見每節。

| 階梯級別 | 定義 | 升級進入的條件 | 6/18 對外措辭 |
|---|---|---|---|
| **`wired_only`** | code / topic / action chain 接好，dry-run 證明鏈路通，但**從未有真實 motion 證據**或資料已遺失 | 任一次 HITL 真機 motion 證據 → `hardware_proven` | 只能講「鏈路已接、fail-closed 正確」，**不可講能力本身可用** |
| **`hardware_proven`** | 至少一次真機 HITL 證明該能力**做到過**，但樣本不足（n<3）或有明確限制（margin 薄 / 需操作員 / 窄場限定） | n=3 重複過 + 限制可接受 → `demo_ready` | 可講「做到過（單點/窄版）」，必須**連帶講出限制與樣本數** |
| **`demo_ready`** | n=3 重複可靠 + 6/18 場地（客廳 indoor_tight）可現場展示 + 有現場中止手段 | — | 可現場 live 展示；仍綁安全前提（e-stop ready） |
| **`research_prototype`** | 只有設計 spec、無任何實作碼 / 無可展示物 | 實作 + HITL（post-6/18） | 只能講「研究路線已有 spec、屬 research prototype」，**絕不可講已具備** |

**鐵則**：① 不把 `insufficient_data` / 資料遺失洗成更高級別；② 單情境最多講 CLAIM_WITH_CAVEAT（沿用 [convergence audit §B 硬規則](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md)）；③ 任何 motion 能力的升級都必須有 §8 對應 N 項 PASS 才能改 label。

---

## 2. Proven Table 總覽（升級的唯一依據）

> current label 直接繼承 Lane 6 plan §2；本檔在每節展開證據路徑與升級路徑。**任何一格沒有「日期 + 文件路徑級證據」就不准比現在更高的 label。**

| # | 能力 | 階梯級別 | Current label | 主證據 | 升級 HITL 項 |
|---|---|---|---|---|---|
| C1 | 0.3m short goto | hardware_proven | `HARDWARE_PROVEN_LOW_SAMPLE` | [trackB §1](research/2026-06-08-trackB-hitl-results.md) | N3 |
| C2 | 0.5m short goto | wired_only→hardware_proven | `NEEDS_RETEST` | [6/9 HITL §1.4-1.5](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) | N3 |
| C3 | 1.0m goto | wired_only | `NOT_DEMO_READY` | [fusion spec §AMCL gate](specs/2026-05-03-d435-rplidar-fusion-detour.md) ※ | N2→N3 |
| C4 | safe stop（正前停障） | hardware_proven | `HARDWARE_PROVEN_WITH_LIMIT` | [trackB §1 / 6/9 §1.5](research/2026-06-08-trackB-hitl-results.md) | N8（+N3 護航） |
| C5 | stop-resume | wired_only | `NEEDS_FIX_OR_OPERATOR_CONFIRM` | [6/9 §1.6](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) | N6 |
| C6 | indoor_tight profile（±18° 誤擋修正） | hardware_proven | `HARDWARE_PROVEN_WITH_LIMIT` | [trackB §4 / 6/9 §1.3](research/2026-06-08-trackB-hitl-results.md) | N8 |
| C7 | AMCL initialpose 重定位 | hardware_proven | `HARDWARE_PROVEN_LOW_SAMPLE` | [6/10 S1 區段](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) | N2 |
| C8 | orphan goal 自癒 | hardware_proven（client 側 wired_only） | `HARDWARE_PROVEN_WITH_LIMIT` | [trackB §5-6 / 6/9 §orphan](research/2026-06-08-trackB-hitl-results.md) | N7 |
| C9 | patrol（固定 route 單圈） | research_prototype | `PROTOTYPE` | [6/9 Phase 1.5](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) | N1→N5 |
| C10 | goto_named / run_route | wired_only | `NOT_DEMO_READY` | code 在、資料遺失（[master §2](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)） | N1 |
| C11 | free roam / dynamic detour | — | `DO_NOT_CLAIM` | [trackB §7](research/2026-06-08-trackB-hitl-results.md) | 無（不在 6/18 範圍） |
| C12 | D435+LiDAR fusion / approach person | research_prototype | `DO_NOT_CLAIM`（spec only） | 本 lane T6-8 三 spec | 無（post-6/18） |

※ C3 主證據是「**為什麼到不了**」的證據（AMCL yellow gate 卡死），非「做到過」的證據——這正是它停在 `wired_only` 的理由。

---

## 3. 逐能力階梯（每節：證據 / current label / 升級條件 / 6/18 可否講）

### C1 — 0.3m short goto

- **階梯級別**：`hardware_proven`（current label `HARDWARE_PROVEN_LOW_SAMPLE`）。
- **證據**：[`research/2026-06-08-trackB-hitl-results.md`](research/2026-06-08-trackB-hitl-results.md) §1：6/7 首發 goto 0.3m → `success=reached, actual=0.270m`，無 no_progress abort，Roy 目視 Go2 真的往前走（NAV-1 / F7 RESOLVED）。特性是 discrete-step：0.3m→0.27m，~3.45s `reached`（Go2 sport-mode 一步幅後 goal close）。
- **為何不更高**：只有單次成功，無重複性數據（n<3）。
- **升級條件**：§8 **N3** 短距可靠性——0.3m × n=3 全 `reached`，每發記 covariance/actual_distance → 升 `demo_ready` 候選。
- **6/18 可否講**：✅ 可講「室內已知地圖、操作員下令的短距自主移動」，**但須標單點/窄版**；n=3 過後才可加「可靠」。

### C2 — 0.5m short goto

- **階梯級別**：`wired_only`→候選 `hardware_proven`（current label `NEEDS_RETEST`）。
- **證據**：[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) §1.4-1.5：indoor_tight 走過一次（safe-stop 場景中），樣本不足；trackB §1 另記 0.5m→0.27m discrete-step（一步幅內就達標）。
- **為何不更高**：只在 safe-stop 護航下走過、未獨立重驗。
- **升級條件**：§8 **N3**——0.5m × n=3，三連過 = `demo_ready` 候選（Lane 6 §6 T6-4）。
- **6/18 可否講**：⚠️ 與 C1 合併講「0.3-0.5m 短距」；0.5m 在 N3 過之前**不單獨宣稱可靠**，且**禁講「乾淨 0.5m+ 連續導航」**（trackB §7 forbidden）。

### C3 — 1.0m goto

- **階梯級別**：`wired_only`（current label `NOT_DEMO_READY`）。
- **證據**：[`navigation/specs/2026-05-03-d435-rplidar-fusion-detour.md`](specs/2026-05-03-d435-rplidar-fusion-detour.md) §「AMCL cov 又卡 YELLOW」：Goal >0.5m 被 `nav_action_server` YELLOW gate 拒（covariance ≤0.30 才允許 >0.5m goal）；[`research/2026-05-01-amcl-180-degree-diagnosis.md`](research/2026-05-01-amcl-180-degree-diagnosis.md) 記 AMCL 靜止不收斂根因。6/10 S1：covariance 0.45 黃帶抖、nav 閘 yellow 只准 ≤0.5m → 被拒且 Studio 靜默回 idle（[master §2](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)）。
- **為何不更高**：**從未成功**——黃帶卡死、無 covariance 收斂 SOP。
- **升級條件**：§8 **N2**（covariance SOP：probe 收斂曲線 + 黃帶決策表，設準 initialpose 等收斂進 green）→ **N3**（1.0m × n=3，每發先用 N2 SOP 進 green 再發）。⚠️ 不放寬 covariance 門檻值（0.3/0.5 hardcoded，Lane 6 §5 禁止）——靠診斷 SOP + 設準 pose 解。
- **6/18 可否講**：❌ **不可講 1.0m 自主移動**，除非 N2+N3 都過並回填本表；在那之前 1.0m 不進 demo 主線。

### C4 — safe stop（正前停障）

- **階梯級別**：`hardware_proven`（current label `HARDWARE_PROVEN_WITH_LIMIT`）。
- **證據**：[`research/2026-06-08-trackB-hitl-results.md`](research/2026-06-08-trackB-hitl-results.md) §1 NAV-2：接近牆 1.03m → reactive_stop danger → nav_paused → Go2 停、0 撞 0 暴衝（多次）；[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) §1.5：goto 0.5m → danger 停 @0.78m、0 撞 0 暴衝。
- **限制（label 帶 WITH_LIMIT 的原因）**：① **stop-based 不繞行**（reactive_stop `angular.z=0` 只停不轉）；② margin 薄（機鼻 ~0.4m）；③ 側向 ±18-30° 不覆蓋（窄錐換來的）。
- **升級條件**：§8 **N8**（indoor_tight danger 停 / clear 放行 / 無誤擋各一輪重跑），由 **N3** 短距護航。**注意**：safe-stop 永遠不會升成「繞障」——繞障是 C11，明確 `DO_NOT_CLAIM`。
- **6/18 可否講**：✅ 可講「正前方障礙物安全停下、不碰撞」，**必須明講是 safe-stop 不是繞障**（標準說法見 claim wording §3）。

### C5 — stop-resume

- **階梯級別**：`wired_only`（current label `NEEDS_FIX_OR_OPERATOR_CONFIRM`）。
- **證據**：[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) §1.6 + §275：auto-resume 會動，但以 Go2 MIN_X ~0.5 m/s lunge、短 goal 貼牆 0.21m（機鼻幾乎貼牆）→ **tight space 禁 demo auto-resume**；operator-confirm 流程 gateway 已實作（6/10 S1）未完整驗。
- **為何不更高**：auto-resume 不安全（lunge）；operator-confirm 流程只在 gateway，台詞退路有但**無 param 防呆**。
- **升級條件**：§8 **N6**（route/goto 中置障 → danger 停 → Studio 按「繼續」→ 續走）驗 operator-confirm 一輪；Lane 6 T6-7 加 `resume_policy` param 防呆（`operator_confirm` 預設 / `auto` 僅大場地，tight×auto 單測被拒）。auto-resume 終局（A-9）post-6/18。
- **6/18 可否講**：✅ 可講「停下後由操作員確認再續走」（operator-confirm）；❌ **禁講** auto-resume / 「障礙移開後會自己繼續」「停了不會再走」（[6/9 §1.6 Acceptance](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)：實際會 auto-resume 但不安全）。

### C6 — indoor_tight profile（±18° 誤擋修正）

- **階梯級別**：`hardware_proven`（current label `HARDWARE_PROVEN_WITH_LIMIT`）。
- **證據**：[`research/2026-06-08-trackB-hitl-results.md`](research/2026-06-08-trackB-hitl-results.md) §4：±30° 寬錐把右前角家具（0.84m）算進前方危險 → nav_paused 鎖死；收窄 ±15° + danger 1.0 + 低速 0.2 → obstacle 1.16-2.12m、zone slow/clear、nav_paused false。[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) §1.3：front 0.97→1.22m、zone danger→slow（±18° 實證）。
- **限制**：窄錐**必綁低速 ≤0.2 m/s**（側向覆蓋變少靠低速補反應時間）；`front_arc_deg`/`danger_distance_m` 只在 `__init__` 讀，`ros2 param set` 改無效 → **必須 kill 重啟帶參數**。
- **升級條件**：§8 **N8**；profile 驗收矩陣文件化見 Lane 6 T6-9。一鍵 profile 已在 [`scripts/start_nav_capability_demo_tmux.sh`](../../scripts/start_nav_capability_demo_tmux.sh)（`REACTIVE_PROFILE=open_space|indoor_tight`）。
- **6/18 可否講**：✅ 可講「居家窄場用收窄安全錐避免誤擋」（trackB §7 能講項）；現場標準診斷工具 = [`scripts/lidar_front_sector.py`](../../scripts/lidar_front_sector.py)。

### C7 — AMCL initialpose 重定位

- **階梯級別**：`hardware_proven`（current label `HARDWARE_PROVEN_LOW_SAMPLE`）。
- **證據**：6/10 S1 段（[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)）：`/api/nav/initialpose` 實測 amcl_pose 跳到設定點；Studio nav panel 有 initialpose 按鈕。
- **為何不更高**：跳點可行但 **covariance 收斂無 SOP**（黃帶要等多久 / 該推 / 該重設沒有決策表）。
- **升級條件**：§8 **N2** covariance SOP（probe 腳本量靜置 vs 0.3m warmup 兩模式收斂曲線 → 填黃帶決策表，Lane 6 T6-5②③）。
- **6/18 可否講**：⚠️ 可作為「定位重設」操作展示；但不講「可靠收斂」——收斂時間不確定（[fusion spec §238](specs/2026-05-03-d435-rplidar-fusion-detour.md)：60-90s 偶爾過）。

### C8 — orphan goal 自癒

- **階梯級別**：`hardware_proven`（client 側 `wired_only`，current label `HARDWARE_PROVEN_WITH_LIMIT`）。
- **證據**：[`research/2026-06-08-trackB-hitl-results.md`](research/2026-06-08-trackB-hitl-results.md) §5-6：被擋 goto 撐 278s 無 abort、client 被殺後 server 端 goal 仍 active → 後續全被 `rejecting goto_* — another goto still active` 擋；[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) §orphan：`no_progress_timeout`(~10s) + `goto_max_duration_s=120` backstop 可自癒、不需重啟。
- **限制**：server 側自癒成立（~10s），但 **client cancel 仍沒送出**（rclpy SIGINT 先關 context → RCLError，非 KeyboardInterrupt）；`send_relative_goal.py` 另有 double-shutdown bug（trackB §6 backlog 1）。
- **升級條件**：§8 **N7**（goto 中 Ctrl-C → cancel 送達 → 立刻可接下一筆）；Lane 6 T6-6 client 根治（`rclpy.init(signal_handler_options=NO)` + 自管 SIGINT）。
- **6/18 可否講**：✅ 可講「client/SSH 掛掉約 10 秒內自動恢復、不需重啟」；❌ **不可講「即時恢復」**（[6/9 §36](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)）。

### C9 — patrol（固定 route 單圈）

- **階梯級別**：`research_prototype`→候選展示（current label `PROTOTYPE`）。
- **證據**：`run_route` action 存在（[`nav_capability/nav_capability/route_runner_node.py`](../../nav_capability/nav_capability/route_runner_node.py)、[`go2_interfaces/action/RunRoute.action`](../../go2_interfaces/action/RunRoute.action)）；[`2026-06-09-nav-vision-hitl-execution.md`](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) Phase 1.5 設計 reactive patrol v0；**routes 資料已遺失、從未跑過完整單圈**。
- **為何不更高**：無資料、無單圈證據。
- **升級條件**：§8 **N1**（poses/routes 重錄）→ **N5**（run_route 單圈，indoor_tight 護航 + 操作員監督 + emergency_stop 待命，錄 Studio 三層同框）。N5 跑通 = 「固定路線單圈巡邏 prototype（操作員監督）」有證據，可講可展示（Lane 6 §13）。
- **6/18 可否講**：⚠️ **僅在 N5 跑通後**才可講「固定路線單圈巡邏 prototype（操作員監督）」，與「自由巡邏」嚴格區分；N5 未跑 → 退影片 fallback。

### C10 — goto_named / run_route

- **階梯級別**：`wired_only`（current label `NOT_DEMO_READY`，N1 恢復後 `NEEDS_RETEST`）。
- **證據**：code 在（[`nav_capability/nav_capability/nav_action_server_node.py`](../../nav_capability/nav_capability/nav_action_server_node.py)、[`go2_interfaces/action/GotoNamed.action`](../../go2_interfaces/action/GotoNamed.action) / [`RunRoute.action`](../../go2_interfaces/action/RunRoute.action)）；**poses/routes 被歷次 deploy `--delete` 清掉**（#166 已修 excludes、`runtime/` 不再被刪，但資料已失，[master §2](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)）→ 目前全部空轉。
- **為何不更高**：資料遺失 → 能力空轉。這是 Lane 6 的第一刀（T6-2）。
- **升級條件**：§8 **N1**（`/log_pose` × 2-3 點 + 組 1 條短 route + `evidence pull` 驗備份）→ 恢復後 `NEEDS_RETEST`。備份迴路：`pawai evidence pull` 納入 `runtime/nav_capability/{named_poses,routes}`（拉回即異地備份，Lane 6 T6-2②）。
- **6/18 可否講**：❌ N1 未做前**不可講** goto_named / run_route；goto_named 真正有意義需更大空間（學校場地，trackB §6）。

### C11 — free roam / dynamic detour（自由巡邏 / 動態繞障）

- **階梯級別**：— （current label `DO_NOT_CLAIM`）。
- **證據**：不存在——reactive_stop `angular.z=0` 只停不轉；硬轉曾摔狗（5/2，[trackB §7](research/2026-06-08-trackB-hitl-results.md) + Lane 6 §2）。
- **升級條件**：**無**——不在 6/18 範圍；Lane 6 §5 Forbidden scope 1/2 明禁（不做動態繞障、reactive_stop 維持 stop-based）。
- **6/18 可否講**：❌ **永遠 forbidden claim**：自由巡邏、動態繞障/繞行（[north-star §7](../mission/2026-06-18-demo-north-star.md) + [convergence audit §B nav 行](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md)）。

### C12 — D435+LiDAR fusion / approach person

- **階梯級別**：`research_prototype`（current label `DO_NOT_CLAIM`，spec only）。
- **證據**：現在**只有** `depth_clear` fail-closed gate（`/capability/depth_clear`，IE SafetyLayer 消費，擋 MOTION skill）——**D435 沒有融入 Nav2 costmap**；fusion 歷史見 [`navigation/specs/2026-05-03-d435-rplidar-fusion-detour.md`](specs/2026-05-03-d435-rplidar-fusion-detour.md)（5/3 詳測，根因 = `nav_action_server` max_speed 不 enforce + AMCL plateau）；approach 未開發。
- **升級條件**：本 lane **T6-8 三條研究 spec**（[fusion](research/2026-06-13-spec-d435-lidar-fusion.md) / [patrol v1](research/2026-06-13-spec-patrol-v1.md) / [approach person](research/2026-06-13-spec-approach-person.md)）落檔可審 → 實作 + HITL（post-6/18）。spec 未過 Roy 審不開工。
- **6/18 可否講**：⚠️ 最多講「D435+LiDAR 融合 / 自主找人：研究路線已有 spec，屬 research prototype」；❌ **不可講** D435 已融合進 costmap、已具備自主找人。

---

## 4. OPEN 項與待補書記

> 沿用 Lane 6 §2 / §3 的誠實盤點；以下是 label 旁帶星號或尚未閉合的書記項。

| 書記 | 內容 | 狀態 |
|---|---|---|
| **A-1（S1 簿記）** | 6/9 鎖過一版 nav 台詞，之後 S1 錄成的**方式待補記**；poses 隨後遺失 → 6/18 版台詞需重鎖（Lane 6 §3 問題 7） | OPEN（claim wording 鎖定時補） |
| **歪斜診斷** | 0.3/0.5m discrete-step 有微幅歪斜，根因排序 H1 步態 yaw drift（~60%）＞H2 DWB 短距修正不足（~30%）＞H3 LiDAR TF（~10%），因 orphaned-goal 未錄到完整波形（[trackB §3](research/2026-06-08-trackB-hitl-results.md)） | OPEN（需較大空間 goto_named >1m 錄 angular.z + yaw） |
| **C3 covariance 收斂** | 黃帶等待時間不確定（60-90s 偶爾過），無決策表 | 待 N2 SOP 閉合 |

---

## 5. 與 6/4 trusted snapshot 的關係（不矛盾聲明）

[`baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/) 的 nav 四能力（`nav.short_move` / `nav.safe_stop` / `nav.no_auto_resume` / `nav.dynamic_avoidance`）在 6/4 trusted snapshot 全 **`insufficient_data`**（n=0，dry-run 在 AMCL gate `amcl_lost` abort、Go2 零 motion，[convergence audit §B nav 行](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md)）。

**本 ladder 與 6/4 snapshot 不矛盾**：6/4 snapshot 是「在 fresh stack 自動採集流程下、無 trusted motion record」的正確 fail-closed 結論；本 ladder 記的 C1/C4 等 `hardware_proven` 是 **6/7-6/10 後續 HITL 的人工觀測證據**（trackB / 6/9 HITL log），尚未回灌進 scoreboard 的自動 trusted 流程。兩者的橋接 = §8 HITL matrix（N3 短距、N8 safe-stop）跑出可溯源數字後回填 scoreboard——在那之前，**對外 claim 一律取兩者中較保守者**，且 nav 在 scoreboard 層維持 `insufficient_data`。

---

## 6. 維護規則

1. **label 升級**：只能透過 §8 HITL matrix 對應 N 項 PASS；每次升級回填本檔 §2/§3 + [claim wording](2026-06-13-nav-618-claim-wording.md) 對應句。
2. **label 降級**：任一 HITL 項 FAIL → 對應格照實標、claim wording 對應降級（FAIL 不連坐其他格，Lane 6 §10）。
3. **資料項**（poses/routes）：是 runtime 資料非 code，錄壞重錄即可；`evidence pull` 備份讓「再被清掉」變成可還原事件。
4. **本檔不是 runtime 真相**：能力是否能跑以 code / topic schema / `pawai smoke nav --static` 為準；本檔是「成熟度敘事 + 升級路徑」。
