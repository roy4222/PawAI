# Advanced Navigation Capability Plan（進階導航能力升級層，Cloud B）

> **日期**：2026-06-13　**狀態**：PLANNED（待 Roy 審核，審核前不實作、不改 runtime、不改 demo flow、不碰既有檔案）
> **計畫群**：PawAI Advanced Capability Upgrade（Cloud B）｜本份：Advanced **Navigation** Capability Plan
> **上游連結**：
> - [Nav Capability Ladder C1-C12（黃金來源）](../../navigation/2026-06-13-nav-capability-ladder.md)
> - [Nav 6/18 Claim Wording S1-S8 / F1-F10（對外措辭真相層）](../../navigation/2026-06-13-nav-618-claim-wording.md)
> - [Lane 6 plan（既有排程 aggressive refactor，本份不重抄）](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)
> - [Track B HITL Results（6/8 居家窄場實機）](../../navigation/research/2026-06-08-trackB-hitl-results.md)
> - [D435+LiDAR Fusion spec](../../navigation/research/2026-06-13-spec-d435-lidar-fusion.md)、[Patrol v1 spec](../../navigation/research/2026-06-13-spec-patrol-v1.md)、[Approach Person spec](../../navigation/research/2026-06-13-spec-approach-person.md)
> - [Post-Refactor Acceptance Report（附錄 HITL #2 Task3：goto 0.3m 走歪撞牆＝NOT_DEMO_READY）](../../runbook/2026-06-13-post-refactor-acceptance-report.md)
> - [aggressive master §1 北極星](2026-06-13-aggressive-pre618-master-plan.md)、[demo north-star §7](../../mission/2026-06-18-demo-north-star.md)

> **這份是什麼**：在既有 Lane 6（已排程 refactor）之上的「**進階／選配導航能力**」分析層——把 nav 從「短距能走 + 安全停（單次證據）」往「fusion-assisted safe-stop / patrol prototype / approach person / initialpose 朝向校正 SOP / 不掃圖直走可行性」推進的**評估與排程**。每個能力強制分級 proven / needs_hitl / research_only / do_not_claim_by_618，並逐項對齊 ladder C 編號與 current label。
>
> **這份不是什麼**：
> - **不是 demo flow 可靠度層**——phase conductor / 五幕指揮 / online-offline fallback / s1_nav 鏡頭編排 / operator runbook 全歸 **Cloud A**（[demo phase conductor plan](2026-06-13-demo-phase-conductor-plan.md)）。本份凡涉及「demo 當天怎麼演 nav 那一幕」一律標「**歸 Cloud A，本計畫不重複**」。
> - **不是 Lane 6 重抄**——Lane 6 = 已排程的 T6-1~T6-10（ladder 落檔、poses 重錄、rejection reason、orphan 根治、三 spec 落檔、claim wording）。本份引用 Lane 6 用連結，**不複製其內文**；本份的價值是「在 Lane 6 跑完後、如果時間足夠，還能往上測什麼」+「6/13 撞牆事件後的 initialpose 校正前置」。
> - **不是 runtime 真相**——能力是否能跑以 code / topic schema / `pawai smoke nav --static` 為準；本份是成熟度敘事 + 升級路徑。
> - **不改 covariance 門檻、不改 reactive_stop 4-mode 本體、不開 auto-resume、不做動態繞障**——這些是 Lane 6 §5 Forbidden scope，本份完全繼承。

---

## §0 TL;DR 總表

> 分級詞彙：`proven`（HITL 至少一次真機證據；對齊 ladder `hardware_proven`）／`needs_hitl`（鏈路在、需真機重驗才能升級或宣稱）／`research_only`（只有 spec、無實作碼）／`do_not_claim_by_618`（6/18 對外一律不宣稱）。
> P0=高價值+低風險+6/18 前可做（多為純軟體文件/評估/SOP）；P1=中價值或需 Jetson/HITL；P2=research only / post-6/18 / 高風險先落 spec。

| # | Sub-capability | ladder | 分級 | P | task_type | before_monday | enter_6/18_runtime |
|---|---|---|---|---|---|---|---|
| A1 | short goto 0.3/0.5/1.0m（短距可靠性 n=3） | C1/C2/C3 | needs_hitl | P1 | go2_motion_needed | maybe | maybe |
| A2 | safe-stop margin（正前停障，margin 薄只停不轉） | C4 | proven | P0 | mixed | yes | yes |
| A3 | stop-resume / operator-confirm（禁 auto-resume lunge） | C5 | needs_hitl | P1 | mixed | maybe | maybe |
| A4 | named poses / routes 恢復（資料遺失需重錄） | C10 | needs_hitl | P0 | go2_motion_needed | maybe | maybe |
| A5 | route patrol prototype（固定 route 單圈→v1） | C9 | research_only | P1 | go2_motion_needed | maybe | no |
| A6 | approach Roy / person（spec only，F6 禁講） | C12 | research_only | P2 | pure_software | no | no |
| A7 | D435+LiDAR fusion → costmap（目前只 depth_clear gate） | C12 | research_only | P2 | pure_software | no | no |
| A8 | local costmap / DWB tuning / true dynamic detour | C11 | do_not_claim_by_618 | P2 | pure_software | no | no |
| A9 | 不掃圖直走（straight forward + reactive_stop safety + Studio evidence + remote fallback） | C4+C1 | needs_hitl | P1 | mixed | maybe | maybe |
| A10 | AMCL initialpose 朝向校正 SOP（6/13 撞牆根因，motion 重驗前置） | C7 | needs_hitl | P0 | mixed | yes | yes ※ |

> **※ A10 的 `enter=yes` 精確意義**：指「初始定位重設＝所有 motion 的必走前置操作儀式」，**不是**宣稱「朝向校正已可靠收斂」——A10 仍 `needs_hitl`、ladder C7 仍 `HARDWARE_PROVEN_LOW_SAMPLE`，對外**不可講「可靠收斂」**（[ladder C7](../../navigation/2026-06-13-nav-capability-ladder.md)）。

**一句總結**：6/13 HITL #2 Task3「第一發 goto 0.3m 走歪撞牆」把 nav motion 全段壓回 `NOT_DEMO_READY`（[acceptance §附錄 Task3](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）——**A10（initialpose 朝向校正 SOP）是所有 motion 能力的硬前置**，必須先做。純軟體面（A10 SOP 文件、A2 safe-stop 量化評估、A9 不掃圖直走的可行性與證據呈現設計）週末可做（P0）；所有真機 motion 屬 Go2 HITL，需 e-stop + 淨空 + Roy 在場，且 nav stack 與 brain demo **8GB 互斥**（獨立時段）。research-only 三條（A6/A7/A8）pre-6/18 只引用既有 spec、不開工。

---

## §1 範圍與邊界

### 1.1 與 Cloud A（demo flow reliability）的分界

| 主題 | 歸屬 | 說明 |
|---|---|---|
| nav 那一幕（s1_nav）怎麼演、phase 切換、清場 | **Cloud A** | [demo phase conductor plan](2026-06-13-demo-phase-conductor-plan.md)：`s1_nav` 幕詞彙、切 phase 清 pending/active/cooldown、`pawai demo phase` wrapper |
| nav 段 online/offline canned phrase 與 timeout | **Cloud A** | demo flow reliability 的 fallback 三層演出層 |
| nav 段操作員逐幕指令、發表日用哪層 fallback | **Cloud A**（B-10 決策） | operator runbook；本份只提供「能力是否驗過」的輸入 |
| **nav 能力本身能做什麼**（短距可靠性、safe-stop margin、stop-resume、poses/routes、patrol、fusion、approach、initialpose 校正） | **本計畫（Cloud B）** | 對齊 ladder C1-C12 |
| nav 對外措辭 | **claim wording（已鎖）** | 本份不重寫 S1-S8 / F1-F10，只引用 |

> **鐵則**：凡是「demo 當天 nav 那段的可靠度/演出/fallback 切換」一律歸 Cloud A，本份不重複。本份只回答「這個 nav 能力升到哪了、要怎麼往上測、6/18 能不能講」。

### 1.2 與既有 Lane 6 的分界

Lane 6（T6-1~T6-10）是**已排程**的 aggressive refactor：ladder 落檔、poses 重錄 SOP、rejection reason、covariance probe、orphan 根治、stop-resume 防呆、三條研究 spec 落檔、claim wording。**本份不重抄這些**——本份是「Lane 6 之上的進階能力評估 + 6/13 撞牆後的 motion 前置」：

- **A10（initialpose 朝向校正 SOP）= Lane 6 之外的新前置**：6/13 HITL #2 Task3 才暴露的根因（朝向不準致 goto 走歪撞牆），Lane 6 §8 HITL matrix 的「開場儀式：goto 0.3m 暖身」**默認 initialpose 已準**——這個假設 6/13 被推翻，A10 補上這個缺口。
- **A1/A2/A3/A4/A5（HITL 重驗）= 引用 Lane 6 §8 的 N1-N8**，本份不重定義 N 項，只標「若時間足夠才測、測完回填 ladder」。
- **A6/A7/A8（research）= 引用 Lane 6 T6-8 三 spec**，本份不重寫 spec 內文，只做「6/18 前可否動」的排程判斷。

### 1.3 安全鐵則繼承（全份生效）

- 移動中禁 `Damp`（api_id=1001，5/2 摔狗）；移動中急停唯一手段＝`emergency_stop.py engage`（mux pri 255）+ `StopMove`（api_id=1003，topic `rt/api/sport/request`）。
- teleop 嚴格 kill；`test_mux_priority.py` 不可在 full stack 跑。
- **nav stack 與 brain demo stack 8GB 互斥**——nav 段是獨立鏡頭、獨立時段（[claim wording §5](../../navigation/2026-06-13-nav-618-claim-wording.md)）。
- 任何 motion HITL：`emergency_stop.py` 終端就位才開始（abort criteria 條 6）；非預期加速/方向 → 立即 abort。
- **不碰 covariance 閘門檻值（0.3/0.5 hardcoded）、不開 auto-resume、不做動態繞障**（Lane 6 §5 Forbidden 1/2/3/5 繼承）。

---

## §2 逐能力 13 點分析

> 每節 13 點：1 demo benefit / 2 baseline / 3 candidate options / 4 required data / 5 pure software / 6 Jetson / 7 Go2 HITL / 8 metrics / 9 pass-fail threshold / 10 risk / 11 rollback / 12 before Monday? / 13 enter 6/18 runtime?

---

### A1 — short goto 0.3 / 0.5 / 1.0m（短距可靠性 n=3）

> **ladder**：C1（0.3m）`HARDWARE_PROVEN_LOW_SAMPLE` / C2（0.5m）`NEEDS_RETEST` / C3（1.0m）`NOT_DEMO_READY`。**分級：needs_hitl。**

1. **Desired demo benefit**：把「操作員下令、室內已知地圖、短距自主走（0.3-0.5m）」從「做到過單次」升到「**n=3 可靠**」，S1 句才能加「可靠」二字（[claim wording S1](../../navigation/2026-06-13-nav-618-claim-wording.md)）。1.0m 若能進 green 連走，是具身導航最強的一張牌。
2. **Current baseline**：C1 6/7 首發 `success=reached actual=0.270m`、6/8 trackB `actual=0.270m`，**單次、無重複性數據**（[trackB §1](../../navigation/research/2026-06-08-trackB-hitl-results.md)）。短距是 discrete-step（0.3m→0.27m、0.5m→0.27m，~3.45s reached，一步幅就達標）。**⚠️ 6/13 HITL #2 Task3：第一發 goto 0.3m 走歪撞牆＝NOT_DEMO_READY**（[acceptance 附錄 Task3](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）——所以 C1 的 `hardware_proven` 與 6/13 撞牆並存的解讀是：**「能往前走」proven，「往對的方向走」尚未 proven**（取決於 initialpose 朝向＝A10）。C3 從未成功（AMCL 黃帶 cov 0.45 卡死、yellow gate 只准 ≤0.5m，[ladder C3](../../navigation/2026-06-13-nav-capability-ladder.md)）。
3. **Candidate options**：(a) 先做 A10 朝向校正再 n=3（**建議起點**）；(b) 切 indoor_tight ±18° + 低速 ≤0.2 降低撞側邊家具風險；(c) 1.0m 先走 covariance SOP（[N2](../../navigation/2026-06-13-nav-capability-ladder.md)）進 green 再發。**不改 covariance 門檻值**（Lane 6 §5 禁）。
4. **Required data**：每發記 `covariance` / `actual_distance` / 朝向誤差 / 結果（reached/abort/撞）；0.3m × n=3、0.5m × n=3、1.0m × n=3（1.0m 需先 N2 進 green）。錄 `/cmd_vel_nav` angular.z + `/amcl_pose` yaw 供歪斜根因鎖定（H1 步態 60% / H2 DWB 30% / H3 TF 10%，[ladder §4](../../navigation/2026-06-13-nav-capability-ladder.md)）。
5. **Pure software tasks**：無新 code（Lane 6 已含 covariance probe T6-5②）；本份只產「短距 n=3 記錄表模板」+ 把 A10 朝向校正列為 N3 前置（文件層）。
6. **Jetson tasks**：deploy nav stack（與 brain demo 互斥，需切 stack）；`pawai smoke nav --static` 8/8 PASS 為前置（[acceptance Task3 已證可 8/8](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。
7. **Go2 HITL tasks**：[Lane 6 §8 N3](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（0.3/0.5/1.0m × n=3），**前置改為 N2（covariance SOP）+ A10（朝向校正）**；e-stop 全程；abort criteria 全生效（尤其條 1 非預期方向、條 5 機鼻 <0.3m 仍動）。
8. **Metrics**：reached 成功率（n=3）、actual vs target 誤差、朝向偏移角、撞擊次數（必須 0）。
9. **Pass/fail threshold**：0.3m × 3 全 reached + 0 撞 + 朝向偏移可接受 → C1 升 `demo_ready` 候選；0.5m × 3 全 reached + 0 撞 → C2 升 `demo_ready` 候選（[Lane 6 T6-4](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。**任一撞牆 = 該距離 FAIL，當日不再試**（abort 條 1/5）。1.0m 需 N2 進 green 才測，否則直接 N/A。
10. **Risk**：高——6/13 已撞一次牆；朝向不準是系統性問題（非單次運氣），未解 A10 前重測仍會撞。
11. **Rollback**：HITL 現場可中止（emergency_stop engage / `pawai demo stop` 路由 nav cleanup）；任一距離 FAIL 不連坐其他距離（ladder §6 維護規則）；proven table 照實標、claim wording 對應降級（S1 退保守版去掉「可靠」）。
12. **Before Monday? maybe**——純軟體面（記錄表模板）yes；真機 n=3 **必須先 A10 朝向校正過**才有意義，否則重蹈 6/13 撞牆。建議：A10 SOP 先做（週末純軟體），n=3 排在 A10 驗過之後的 motion 時段。
13. **Enter 6/18 runtime? maybe**——僅在 A10 過 + n=3 全 reached 0 撞後，0.3-0.5m 進 live 短距 fallback ①層（[claim wording §5](../../navigation/2026-06-13-nav-618-claim-wording.md)）；否則退 fallback ②遙控輔助或③純影片。**1.0m no**（F8 禁講 1.0m+ 乾淨連續導航）。

---

### A2 — safe-stop margin（正前停障，margin 薄、只停不轉）

> **ladder**：C4 `HARDWARE_PROVEN_WITH_LIMIT`。**分級：proven。**

1. **Desired demo benefit**：「正前方障礙物會安全停下、不碰撞——偵測到障礙會停下等待，不會繞行」（[claim wording S2](../../navigation/2026-06-13-nav-618-claim-wording.md)）。這是 nav 段**最站得住**的能力，也是「機器狗非噱頭」的具身安全證明。
2. **Current baseline**：trackB §1 NAV-2 接近牆 1.03m → reactive_stop danger → nav_paused → Go2 停、**0 撞 0 暴衝（多次）**；6/9 §1.5 goto 0.5m → danger 停 @0.78m 0 撞 0 暴衝（[ladder C4](../../navigation/2026-06-13-nav-capability-ladder.md)）。**限制**：① stop-based 不繞行（`angular.z=0`）；② margin 薄（機鼻 ~0.4m）；③ 側向 ±18-30° 不覆蓋（窄錐換來的）。
3. **Candidate options**：(a) 維持現狀只做「量化 margin 評估」（**建議**，純軟體＋既有數據）；(b) indoor_tight ±18° + danger 1.0 + 低速 ≤0.2 重跑一輪確認 margin（[Lane 6 N8](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。**不改 reactive_stop 4-mode 本體、不放寬 danger 門檻**。
4. **Required data**：danger 觸發距離（LiDAR 視距）、機鼻到障礙實測距離、停下後 0 暴衝確認、側向覆蓋角缺口。LiDAR 安在 base_link+0.175m、Go2 機鼻在 base_link+~0.40m（[navigation CLAUDE.md](../../navigation/CLAUDE.md)）——margin = LiDAR 視距 − 0.225m − 反應距離。
5. **Pure software tasks**：把既有 trackB/6/9 數據整理成「safe-stop margin 量化表」（danger 距離 vs 機鼻 buffer vs 速度 vs 反應時間），標清「margin 薄、不繞、側向不覆蓋」三限制——供 claim wording S2 與 §3 標準說法佐證。**無新 code。**
6. **Jetson tasks**：nav stack deploy（互斥）；reactive_stop active 確認（[acceptance Task3 已證 active](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。
7. **Go2 HITL tasks**：[Lane 6 N8](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（indoor_tight danger 停 / clear 放行 / 無誤擋各一輪）；abort 條 2（該觸發沒觸發 → abort 全部後續 motion）。
8. **Metrics**：danger 觸發距離、停下後 0 撞 0 暴衝率、誤擋率（clear 區誤報 danger）、機鼻最終 buffer。
9. **Pass/fail threshold**：indoor_tight 下「danger 該停都停 + clear 該放都放 + 機鼻 buffer >0.3m + 0 撞 0 暴衝」→ 維持 C4 `HARDWARE_PROVEN_WITH_LIMIT`（已 proven，N8 是再確認非升級）。**任一該停沒停 = abort**。
10. **Risk**：低——已多次 proven；唯一風險是 margin 薄（機鼻 ~0.4m），demo 時障礙不能放太近（trackB §6：sweet spot 1.0-1.5m）。
11. **Rollback**：reactive_stop 是現行為，不改本體無回退需求；若 N8 某輪誤擋 → 收窄錐角（已是 indoor_tight ±18°）或標 FAIL 不連坐。
12. **Before Monday? yes**——純軟體 margin 量化表週末可完成；真機 N8 可併入任何 motion 時段（短，~15min）。
13. **Enter 6/18 runtime? yes**——safe-stop 是 nav 段核心可講能力（S2），fallback ①②層都用得到；**必須配 §3 標準說法明講「safe-stop 不是繞障」**，不講側向覆蓋。

---

### A3 — stop-resume / operator-confirm resume（禁 auto-resume lunge）

> **ladder**：C5 `NEEDS_FIX_OR_OPERATOR_CONFIRM`。**分級：needs_hitl。**

1. **Desired demo benefit**：「停下後由操作員確認再續走」（[claim wording S3](../../navigation/2026-06-13-nav-618-claim-wording.md)）——展示「安全停 → 人在迴路確認 → 續走」的可控性，是 safe-stop 的自然延伸。
2. **Current baseline**：auto-resume 會動，但以 Go2 MIN_X ~0.5 m/s **lunge、短 goal 貼牆 0.21m**（機鼻幾乎貼牆）→ **tight space 禁 demo auto-resume**（[ladder C5](../../navigation/2026-06-13-nav-capability-ladder.md)、6/9 §275）。operator-confirm 流程 gateway 已實作（6/10 S1）**未完整驗**。
3. **Candidate options**：(a) operator-confirm only（**建議**，安全）；(b) Lane 6 T6-7 加 `resume_policy` param 防呆（`operator_confirm` 預設 / `auto` 僅大場地，tight×auto 單測被拒）。**不開 auto-resume**（Lane 6 §5 Forbidden 3，A-9 終局 post-6/18）。
4. **Required data**：operator-confirm 一輪流程（danger 停 → Studio 按「繼續」→ 續走）；lunge 數據（速度、貼牆距離）供 A-9 終局決策一頁。
5. **Pure software tasks**：[Lane 6 T6-7①](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) `resume_policy` param 防呆 + 單測（tight×auto 被拒）——**本份不重做**，只標「歸 Lane 6」。本份新增：A-9 終局決策材料一頁（lunge 數據 + 兩案利弊）——但這偏 research，列 P2 附帶。
6. **Jetson tasks**：nav stack + gateway paused_confirm 流程 deploy。
7. **Go2 HITL tasks**：[Lane 6 N6](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（route/goto 中置障 → danger 停 → Studio 按「繼續」→ 續走）；abort 條 4（lunge 重現 → abort，當日退 operator-confirm only）。
8. **Metrics**：operator-confirm 流程成功率（停→確認→續走無誤）、auto-resume lunge 速度/貼牆距離（記錄供決策，不啟用）。
9. **Pass/fail threshold**：operator-confirm 一輪「停 → 按繼續 → 續走 0 撞」→ C5 可講 S3（needs_hitl→proven 候選）。**auto-resume lunge 重現 = abort**，不升級。
10. **Risk**：中——operator-confirm 依賴 gateway paused_confirm 流程未完整驗；auto-resume 若被誤觸發會 lunge（高風險，靠 param 防呆 + 台詞退路）。
11. **Rollback**：`resume_policy` param 預設=現行為（Lane 6 §10）；HITL FAIL → 退「操作員確認/遙控輔助」台詞（[6/9 HITL ④](2026-06-09-nav-vision-hitl-execution.md)）。
12. **Before Monday? maybe**——param 防呆是 Lane 6 純軟體（AFK 可做）；operator-confirm HITL 需真機，排 motion 時段。
13. **Enter 6/18 runtime? maybe**——operator-confirm 過 N6 才講 S3；**auto-resume 永遠 no**（F4/F5 禁講）。tight space demo 禁 auto-resume。

---

### A4 — named poses / routes 恢復（資料遺失需重錄）

> **ladder**：C10 `NOT_DEMO_READY`（N1 恢復後 `NEEDS_RETEST`）。**分級：needs_hitl。**

1. **Desired demo benefit**：恢復 `goto_named` / `run_route` 能力（目前空轉）——是 A5 patrol prototype 的硬前置；恢復後可講「具名點位/固定路線」（需 N1 過）。
2. **Current baseline**：code 在（`nav_action_server_node.py` / `GotoNamed.action` / `RunRoute.action`），但 **poses/routes 被歷次 deploy `--delete` 清掉**（#166 已修 excludes、`runtime/` 不再被刪，但**資料已失**，[ladder C10](../../navigation/2026-06-13-nav-capability-ladder.md)）→ 全部空轉。
3. **Candidate options**：(a) 重錄 2-3 named poses + 1 條短 route（**建議**，[Lane 6 N1](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）；(b) `evidence pull` 納入 `runtime/nav_capability/{named_poses,routes}` 作異地備份（Lane 6 T6-2②，**B2 bug 6/13 已修**：缺失目錄優雅跳過，[acceptance §hotfix](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。
4. **Required data**：客廳 2-3 個 named poses（`/log_pose` 記錄）+ 1 條短 route（poses 序列）+ `evidence pull` 驗備份拉得回。
5. **Pure software tasks**：[Lane 6 T6-2①②](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（重錄 SOP 文件 + CLI evidence pull include）——**歸 Lane 6，本份不重做**。本份只標「A5/A6 的硬前置」。
6. **Jetson tasks**：nav stack deploy；`/log_pose` action 可用確認。
7. **Go2 HITL tasks**：[Lane 6 N1](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（`/log_pose` × 2-3 點 + 組 1 條短 route + `evidence pull` 驗備份，~20min）；需 Go2 移動到各點位記錄。
8. **Metrics**：poses 記錄成功數、route 組裝成功、evidence pull 備份完整性（rsync 拉回行數）。
9. **Pass/fail threshold**：2-3 poses 記錄 + 1 route 組成 + evidence pull 拉得回 → C10 升 `NEEDS_RETEST`（可進 A5 N5）。
10. **Risk**：低——純資料記錄，無高速 motion（移動到點位是低速）；唯一風險是再被 deploy `--delete`（#166 已修 + evidence pull 備份雙保險）。
11. **Rollback**：poses/routes 是 runtime 資料非 code，錄壞重錄即可（Lane 6 §10）；evidence pull 備份讓「再被清掉」變可還原事件。
12. **Before Monday? maybe**——SOP 文件 yes（Lane 6 已含）；重錄 HITL 需真機，排 motion 時段（A5/A6 的前置）。
13. **Enter 6/18 runtime? maybe**——恢復後 `NEEDS_RETEST`，需 N5 跑通才講 patrol；單純 goto_named「需更大空間才有意義」（[trackB §6](../../navigation/research/2026-06-08-trackB-hitl-results.md)），居家窄場一圈就到頭。

---

### A5 — route patrol prototype（固定 route 單圈 → v1）

> **ladder**：C9 `PROTOTYPE`。**分級：research_only**（v0 單圈需 HITL 才有展示物；v1 多圈/排程是 spec）。

1. **Desired demo benefit**：「固定路線單圈巡邏 prototype（操作員監督）」（[claim wording S7，需 N5 過](../../navigation/2026-06-13-nav-618-claim-wording.md)）——守護 30% 範疇的具身展示。
2. **Current baseline**：`run_route` action 存在（`route_runner_node.py` / `RunRoute.action`）；6/9 Phase 1.5 設計 reactive patrol v0；**routes 資料已遺失、從未跑過完整單圈**（[ladder C9](../../navigation/2026-06-13-nav-capability-ladder.md)）。v1（多圈/排程/暫停恢復）只有 [patrol v1 spec](../../navigation/research/2026-06-13-spec-patrol-v1.md)、零實作碼。
3. **Candidate options**：(a) v0 單圈先跑（[Lane 6 N5](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)，indoor_tight 護航 + 操作員監督 + emergency_stop 待命，**建議起點**）；(b) v1 多圈/排程**需大場地、post-6/18**（patrol v1 spec §2 明標居家客廳淨空 ~1.1-1.5m 一圈就到頭）。
4. **Required data**：N5 run_route 單圈跑通 + Studio 三層同框錄證據；硬閘 = N1（routes 恢復＝A4）+ N7（orphan 根治，route 是多 goal、orphan 會放大，[patrol v1 spec §0](../../navigation/research/2026-06-13-spec-patrol-v1.md)）。
5. **Pure software tasks**：[Lane 6 T6-8②](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) patrol v1 spec 落檔——**已完成（6/13 spec 已在）**，本份不重寫。
6. **Jetson tasks**：nav stack + route_runner + reactive_stop indoor_tight profile deploy。
7. **Go2 HITL tasks**：[Lane 6 N5](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（run_route 單圈，~30min，stretch 項）；依賴 N1（A4）+ N7（orphan）；每圈 covariance 重檢（N2）。abort criteria 全生效。
8. **Metrics**：單圈完成率、每段 reached、0 撞 0 暴衝、Studio 三層同框證據完整性。
9. **Pass/fail threshold**：run_route 單圈跑通（所有段 reached + 0 撞 + 操作員監督）→ C9 有展示物，6/18 可講 S7。**未跑通 → 退影片 fallback，不講 S7。**
10. **Risk**：高——依賴 A4（poses 恢復）+ N7（orphan 根治）+ A10（朝向校正，否則每段都可能走歪）；居家窄場連續多 goal 風險疊加；是 Lane 6 §8 標的 stretch 項（時間不夠先砍）。
11. **Rollback**：HITL FAIL → C9 維持 `PROTOTYPE`（無展示物），claim wording S7 整句不講、走影片 fallback；patrol v1 多圈本來就 post-6/18。
12. **Before Monday? maybe**——v0 單圈 HITL 若 A4+N7+A10 都過且時間足夠才測（低機率）；v1 多圈 no（需大場地）。
13. **Enter 6/18 runtime? no**——僅在 N5 跑通才講 S7 prototype；v1 多圈/排程 post-6/18。**「自由巡邏」永遠 F1 禁講**，patrol 是固定預錄 route。

---

### A6 — approach Roy / person（spec only，F6 禁講）

> **ladder**：C12 `DO_NOT_CLAIM`（spec only）。**分級：research_only。**

1. **Desired demo benefit**：（未來）「看到/聽到人 → 走到人身邊安全距離停下」——把感知（face/depth）與移動（nav）第一次接起來。**6/18 不是 benefit、是 forbidden**。
2. **Current baseline**：**零連接**——只有 2D RPLIDAR 進導航迴路，RGB/物體/人臉/語音與 nav goal 零連接（[trackB §2](../../navigation/research/2026-06-08-trackB-hitl-results.md)）。approach 的「人在哪→算 goal→走過去」整條鏈不存在（[approach spec §0](../../navigation/research/2026-06-13-spec-approach-person.md)）。
3. **Candidate options**：只有一條——[approach spec](../../navigation/research/2026-06-13-spec-approach-person.md) 四層開發（L1 目標偵測 / L2 像素→地圖座標 / L3 規劃走過去 / L4 接近 safe-stop），~4-5 天，**明確超出 6/18**。
4. **Required data**：無（pre-6/18 不開工）；spec 的三硬閘＝短距 n=3（N3／A1）+ fusion B1/B2 解（A7）+ face/depth→map 座標鏈設計過審。
5. **Pure software tasks**：[Lane 6 T6-8③](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) approach spec 落檔——**已完成（6/13 spec 已在）**，本份不重寫。
6. **Jetson tasks**：無（pre-6/18）。
7. **Go2 HITL tasks**：無（pre-6/18）。
8. **Metrics**：無（spec only）；post-6/18 L1+L2 = 偵測到人 + 算出穩定 map 座標（Go2 不動，n≥3 不同位置）。
9. **Pass/fail threshold**：spec 過 Roy 審 + 三硬閘全達 → 可開工（仍 research_prototype，post-6/18）。
10. **Risk**：—（pre-6/18 不動，無執行風險）；最大風險是**對外誤講**（F6「聽懂過來就走到 Roy 身邊」是明文 forbidden）。
11. **Rollback**：—（無 code 可回退）；若被追問，固定用「研究路線有 spec、感知與移動還沒接起來、不在這次展示範圍」（[claim wording §7](../../navigation/2026-06-13-nav-618-claim-wording.md)）。
12. **Before Monday? no**——spec 已落檔，pre-6/18 不開工（Lane 6 §5 Forbidden 1）。
13. **Enter 6/18 runtime? no**——C12 `DO_NOT_CLAIM`；最多講 S8「研究路線已有 spec、屬 research prototype」，**F6 絕不可講已具備**。

---

### A7 — D435 + LiDAR fusion → costmap（目前只 depth_clear gate）

> **ladder**：C12 `DO_NOT_CLAIM`（spec only）。**分級：research_only。**

1. **Desired demo benefit**：（未來）用 D435 depth 補 2D RPLIDAR 盲區（矮障礙/掃描平面外）→ **safe-stop 更準/更早**。**fusion = 讓 safe-stop 更可靠，不是動態繞障**（[fusion spec §1](../../navigation/research/2026-06-13-spec-d435-lidar-fusion.md)）。**6/18 不是 benefit、是 forbidden**。
2. **Current baseline**：現在**只有** `depth_clear` fail-closed gate（`/capability/depth_clear`，IE SafetyLayer 消費，擋 MOTION skill）——**D435 沒有融入 Nav2 costmap**（[trackB §2](../../navigation/research/2026-06-08-trackB-hitl-results.md)、F3 forbidden）。5/3 fusion L3 FAIL，根因＝B1 max_speed 不 enforce + B2 AMCL plateau。
3. **Candidate options**：[fusion spec §2](../../navigation/research/2026-06-13-spec-d435-lidar-fusion.md) 兩路線——路線 A（costmap obstacle layer，真 3D，CPU/RAM 高、Jetson 8GB 緊）vs 路線 B（depth→`/scan_d435` light 版，CPU 低、工具鏈已驗，**建議起點 spike**）。**6/9 Roy 給的進度序**：D435 shadow test（不動狗）→ 接 local costmap → 靜態障礙更準停 → reactive patrol。
4. **Required data**：無（pre-6/18 不開工）；硬閘＝B1 max_speed enforce + B2 AMCL plateau 解（兩者任一未解，fusion 不開工，[fusion spec §0 硬閘](../../navigation/research/2026-06-13-spec-d435-lidar-fusion.md)）。
5. **Pure software tasks**：[Lane 6 T6-8①](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) fusion spec 落檔——**已完成（6/13 spec 已在）**，本份不重寫。
6. **Jetson tasks**：無（pre-6/18）；post-6/18 需先量 RAM（路線 A 風險高、8GB 互斥）。
7. **Go2 HITL tasks**：無（pre-6/18）；post-6/18 shadow test 階段 **Go2 不動**（只錄 `/scan_d435_shadow` vs `/scan_rplidar`）。
8. **Metrics**：無（spec only）；post-6/18 shadow = D435 補到 RPLIDAR 漏的障礙、無大量幽靈點；costmap 接入 = 停障點比純 RPLIDAR 更準/更早（量化，n≥3）。
9. **Pass/fail threshold**：spec 過審 + B1/B2 解 → 可開工（post-6/18）。
10. **Risk**：—（pre-6/18 不動）；post-6/18 最大風險＝路線 A 的 8GB RAM + D435 幽靈障礙永久停車（需 clearing + DenoiseLayer + 一鍵關）。對外風險＝F3「D435 已融合進 costmap」是 forbidden。
11. **Rollback**：—（無 code）；fusion 開後 D435 source 必須可一鍵關（env/param），出問題退純 RPLIDAR（[fusion spec §3](../../navigation/research/2026-06-13-spec-d435-lidar-fusion.md)）。
12. **Before Monday? no**——spec 已落檔，B1/B2 未解前不開工（[fusion spec §0 硬閘](../../navigation/research/2026-06-13-spec-d435-lidar-fusion.md)）。
13. **Enter 6/18 runtime? no**——C12 `DO_NOT_CLAIM`；最多講 S8「有 spec、是研究」，**F3 絕不可講已融合進 costmap**。

---

### A8 — local costmap / DWB tuning / true dynamic detour

> **ladder**：C11 `DO_NOT_CLAIM`。**分級：do_not_claim_by_618**（最強禁制——永遠 forbidden claim）。

1. **Desired demo benefit**：（未來、超出 6/18）真正的動態繞障——遇障自動轉向繞過。**6/18 永遠 forbidden**。
2. **Current baseline**：**不存在**——reactive_stop `angular.z=0` 只停不轉；硬轉曾摔狗（5/2，[trackB §7](../../navigation/research/2026-06-08-trackB-hitl-results.md)、Lane 6 §2）。DWB 不會自動繞行（當前 yaml 是保守安全停 profile，[navigation CLAUDE.md 5/3 教訓](../../navigation/CLAUDE.md)）。
3. **Candidate options**：(a) **不做**（Lane 6 §5 Forbidden 1/2 明禁，**建議**）；(b) post-demo（~7/2）Nav2 Collision Monitor polygon footprint（取代錐角，從根解 off-path 側前誤擋，[trackB §6 backlog 4](../../navigation/research/2026-06-08-trackB-hitl-results.md)）——這是「更好的停障」不是「繞障」。**繞障本身不在任何 6/18 範圍。**
4. **Required data**：無（不做）。
5. **Pure software tasks**：無（本份僅標「永遠 forbidden、不在 6/18 範圍」）。
6. **Jetson tasks**：無。
7. **Go2 HITL tasks**：無。
8. **Metrics**：無。
9. **Pass/fail threshold**：N/A——明確不做。
10. **Risk**：對外誤講風險最高——F1/F2「自由巡邏/動態繞障/自動繞開」是誠信破口；硬轉摔狗是實機教訓。
11. **Rollback**：N/A。
12. **Before Monday? no**——明確不做（Lane 6 §5 Forbidden）。
13. **Enter 6/18 runtime? no**——C11 `DO_NOT_CLAIM`，F2 永遠禁講。被追問繞障固定用 [claim wording §3 標準說法](../../navigation/2026-06-13-nav-618-claim-wording.md)：「reactive_stop 只停不轉是刻意的安全選擇」。

---

### A9 — 不掃圖直走（straight forward + reactive_stop safety + Studio evidence + remote fallback）

> **ladder**：對應 C4（safe-stop）+ C1（短距前進）。**分級：needs_hitl。**（Roy 特別要求分析）

1. **Desired demo benefit**：Roy 的需求——**不依賴 AMCL/map，直接讓 Go2 直線前進**，由 reactive_stop 兜底安全，Studio 顯示即時 LiDAR/感知作為證據，失敗時遙控接管。好處：**繞過 6/13 撞牆根因（AMCL initialpose 朝向不準）**——不用 map 就沒有「朝地圖歪方向走」的問題。
2. **Current baseline**：goto_relative 走 AMCL+Nav2+costmap 鏈，6/13 因 initialpose 朝向不準走歪撞牆（[acceptance Task3](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。reactive_stop 是獨立鏈路（LiDAR → danger → `/cmd_vel_obstacle`=0 → mux pri 200），**不依賴 AMCL**（[navigation CLAUDE.md reactive 段](../../navigation/CLAUDE.md)）。**直走的 cmd_vel 來源目前是 teleop / 手動 publish**——非 nav_action_server goal。
3. **Candidate options**：(a) teleop 低速直走 + reactive_stop progressive mode 兜底（**最簡、建議評估**，無新 nav goal）；(b) 短 open-loop 前進指令（固定時長低速 Move）+ reactive_stop；(c) 維持 goto_relative 但先 A10 校正朝向（落回 A1）。**⚠️ 誠實前提**：reactive_stop 是 **safe-stop 不是繞障**——直走遇障**只會停、不會繞**（[claim wording §3](../../navigation/2026-06-13-nav-618-claim-wording.md)）；且 6/13 證實「走歪」即使不用 map 也可能來自步態 yaw drift（H1 ~60%，[ladder §4](../../navigation/2026-06-13-nav-capability-ladder.md)）——**不掃圖直走仍需精準初始朝向，否則走歪**。
4. **Required data**：直走鏈路的 cmd_vel 來源確認（teleop vs open-loop）；reactive_stop progressive mode 在直走場景的 danger 觸發確認；Studio 是否能即時顯示 `/scan_rplidar` 點雲 + reactive zone 狀態作為「邊緣端即時感知」證據（[claim wording §5 fallback ②](../../navigation/2026-06-13-nav-618-claim-wording.md)）；遙控接管路徑（teleop kill→手動）。
5. **Pure software tasks**：**本份核心純軟體產出**——「不掃圖直走」的可行性與安全前提評估 + 證據呈現設計文件：① 直走 cmd_vel 來源與 reactive_stop 兜底的鏈路圖；② 安全前提清單（必綁低速 ≤0.2、indoor_tight ±18° 錐、e-stop 待命、初始朝向 sanity）；③ Studio evidence 呈現方案（LiDAR 點雲 + zone 狀態，**引用 Lane 2 Evidence 既有管道，不擴張 UI**）；④ 遙控 fallback SOP。**無新 nav code**（直走若走 teleop 是現有路徑）。
6. **Jetson tasks**：nav stack（或最小 reactive_stop + sllidar + driver）deploy；Foxglove/Studio LiDAR 點雲可視化確認。
7. **Go2 HITL tasks**：低速直走一段（≤0.2 m/s）+ 前方放障礙驗 reactive_stop 停 + Studio 同框錄證據；e-stop 全程；abort 條 1（非預期方向）、條 2（該停沒停）、條 5（機鼻 <0.3m 仍動）。**與 A1 共用 motion 時段。**
8. **Metrics**：直走偏移角（無 map 下靠步態，記錄）、reactive_stop 停障成功率、Studio 證據完整性、遙控接管反應時間。
9. **Pass/fail threshold**：低速直走 + 前方障礙 reactive_stop 停 + 0 撞 + Studio 同框證據 → 可作 fallback ②層演出（遙控輔助 + Studio 證據）。**偏移角過大撞側邊家具 = FAIL**（同 6/13 根因，需 A10）。
10. **Risk**：中高——**最大誤解風險**：把「直走 + safe-stop」包裝成「自主導航/避障」（F2/F7 禁）；且直走仍可能走歪（步態 yaw drift），不掃圖不等於不會撞。
11. **Rollback**：teleop 直走是現有路徑，停止＝鬆開按鍵 / emergency_stop engage；無 code 改動無回退；FAIL → 退純遙控 + Studio 證據（fallback ②）或純影片（③）。
12. **Before Monday? maybe**——可行性評估文件 yes（純軟體，週末可做，**P0 級價值**：直接回應 Roy 需求 + 給 6/13 撞牆一條繞過路徑）；真機直走 HITL 排 motion 時段。
13. **Enter 6/18 runtime? maybe**——可作 fallback ②層的演出方式（遙控輔助 + Studio 即時感知證據），但**對外措辭嚴格**：講「操作員下令前進 + 遇障安全停 + Studio 顯示即時感知」（S2 + 「Studio 顯示即時感知環境非寫死」），**禁講「自主直線導航/避障」**（safe-stop≠繞障，F2/F7）。

---

### A10 — AMCL initialpose 朝向校正 SOP（6/13 撞牆根因，motion 重驗前置）

> **ladder**：C7（AMCL initialpose 重定位）`HARDWARE_PROVEN_LOW_SAMPLE`。**分級：needs_hitl。**（6/13 撞牆事件的直接修法）

1. **Desired demo benefit**：**所有 motion 能力的硬前置**——6/13 第一發 goto 0.3m 走歪撞牆，根因＝AMCL initialpose **朝向(orientation)不準**致「前方 0.3m」算在地圖歪方向（[acceptance 附錄 Task3 根因](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。校正朝向 = 讓 A1/A4/A5/A9 的 motion 不再走歪。
2. **Current baseline**：`/api/nav/initialpose` 實測 amcl_pose 跳到設定點（[ladder C7](../../navigation/2026-06-13-nav-capability-ladder.md)、6/10 S1）；但 **朝向設定靠 Foxglove 目視、無物理錨定 SOP**——6/13 設的朝向不準。位置面有 C7，**朝向校正面是缺口**。covariance 收斂另有缺口（C7：黃帶等多久無決策表，走 N2 SOP）。
3. **Candidate options**：(a) **物理錨定法**（navigation CLAUDE.md 黃金標準）——用 `lidar_front_sector.py` / `scan_health_check.py`：Go2 正前方已知距離放物體或對齊牆面，看 LiDAR 紅點落在哪個 angle bin，反推真實朝向再設 initialpose（**建議**）；(b) goto 前加「朝向 sanity」檢查或先小角度自轉對齊（[acceptance Task3 後續修法③](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）；(c) 切 indoor_tight ±18° + 低速降低走歪撞牆後果。**不掃圖直走（A9）是另一條繞過路徑**。
4. **Required data**：物理錨定的朝向設定步驟（LiDAR 紅點對齊牆面/已知物體 → angle bin → yaw）；設準後 goto 0.3m 朝向偏移角（vs 6/13 撞牆）；covariance 收斂時間（走 N2 probe）。
5. **Pure software tasks**：**本份核心 P0 產出**——「AMCL initialpose 朝向校正 SOP」文件：① 物理錨定步驟（引用 `lidar_front_sector.py` ±15/20/30° 扇區 + `scan_health_check.py` 物理錨定，**不重寫工具**）；② goto 前朝向 sanity checklist（initialpose 後先驗 `tf2_echo map base_link` yaw 對得上現場再發 goal）；③ 「不要用 Foxglove 目視猜 yaw」硬規則成文（navigation CLAUDE.md 4/29 教訓：視覺差異不能當判讀依據）。**無新 code**（工具已存在）。
6. **Jetson tasks**：nav stack + AMCL deploy；`lidar_front_sector.py` / `scan_health_check.py` 可跑確認；`tf2_echo map base_link` 對齊現場。
7. **Go2 HITL tasks**：物理錨定校正一輪（Go2 正前方對齊牆面 → LiDAR angle bin 驗 → 設 initialpose → `tf2_echo` 驗 yaw）→ goto 0.3m 一發暖身（朝向 sanity 過才發）；abort 條 1/3（cov 黃帶 >0.3 不送 >0.5m）/條 5。**這是 A1 n=3 與 A4/A5/A9 的開場儀式。**
8. **Metrics**：校正後 goto 0.3m 朝向偏移角（目標：明顯小於 6/13 撞牆的斜邊偏移）、撞擊次數（必須 0）、covariance 收斂時間。
9. **Pass/fail threshold**：物理錨定設準 initialpose → goto 0.3m 朝向偏移可接受 + 0 撞 → C7 可作 motion 前置（A1 才能往 demo_ready 走）。**仍撞 = 朝向校正法 FAIL，當日所有 motion 項 abort**（不能在 NOT_DEMO_READY 上疊測）。
10. **Risk**：中——物理錨定法已是 navigation 黃金標準（4/29 驗過視覺猜法全錯），但朝向校正 + goto 仍是真機 motion，6/13 已撞一次；步態 yaw drift（H1）即使朝向設準仍可能微歪。
11. **Rollback**：SOP 是文件無 code 回退；HITL FAIL → motion 全段標 NOT_DEMO_READY、nav 退 fallback ②③（遙控/影片）；對外不可講「自主短距移動」直到校正 + n 次無撞重驗（[acceptance Task3 誠實結論](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。
12. **Before Monday? yes**——SOP 文件純軟體、週末可做，且**是所有 motion HITL 的前置**（不先做這個，A1 重測必再撞）；真機校正排 motion 時段最前。
13. **Enter 6/18 runtime? yes**——initialpose 校正是 nav motion demo 的**必走前置儀式**（哪怕只演 safe-stop 也要定位準）；可作為「定位重設」操作展示（S 級操作），但**不講「可靠收斂」**（收斂時間不確定，[ladder C7](../../navigation/2026-06-13-nav-capability-ladder.md)）。

---

## §3 任務清單（task_type + tests + HITL checklist + rollback）

> task_type：[pure software] / [Jetson needed] / [Go2 motion needed]。凡引用 Lane 6 既有 N 項/T 項一律標「歸 Lane 6，本份不重做」。

### T-NAV-1：AMCL initialpose 朝向校正 SOP 文件（A10）

- **task_type**：[pure software]
- **內容**：產出 `docs/navigation/` 朝向校正 SOP（物理錨定步驟 + goto 前 yaw sanity checklist + 「不目視猜 yaw」硬規則）。引用 `lidar_front_sector.py` / `scan_health_check.py`，不重寫工具。
- **tests**：文件 review（Roy 過目）；checklist 可逐條執行（dry-run 走查每條指令存在：`tf2_echo map base_link`、`lidar_front_sector.py` --help）。
- **HITL checklist**：N/A（純文件）；真機校正在 T-NAV-7。
- **rollback**：文件，無 code；不合用即廢棄。

### T-NAV-2：safe-stop margin 量化表（A2）

- **task_type**：[pure software]
- **內容**：整理 trackB/6/9 既有數據成 margin 量化表（danger 距離 vs 機鼻 buffer vs 速度 vs 反應時間 + 三限制標註），供 claim wording S2 佐證。
- **tests**：數字逐項對得上來源文件（trackB §1、6/9 §1.5、navigation CLAUDE.md 機身幾何）。
- **HITL checklist**：N/A（純文件，N8 再確認在 T-NAV-7）。
- **rollback**：文件，無 code。

### T-NAV-3：「不掃圖直走」可行性與證據呈現評估（A9）

- **task_type**：[pure software]
- **內容**：直走鏈路圖 + 安全前提清單 + Studio evidence 呈現方案（引用 Lane 2 既有管道）+ 遙控 fallback SOP。**明標 safe-stop≠繞障、直走仍需精準朝向**。
- **tests**：鏈路圖與 reactive_stop progressive mode 行為對得上（navigation CLAUDE.md 4-mode 表）；安全前提清單與 abort criteria 一致。
- **HITL checklist**：N/A（純文件，真機直走在 T-NAV-8）。
- **rollback**：文件，無 code；teleop 直走是現有路徑無 code 改動。

### T-NAV-4：引用 Lane 6 純軟體項（不重做，標歸屬）

- **task_type**：[pure software]
- **內容**：本份**不實作** Lane 6 T6-2①②（poses SOP/CLI）、T6-5（rejection reason/probe）、T6-6（orphan）、T6-7①（resume_policy）——僅在本份標明「這些是 A3/A4/A5 的前置，歸 Lane 6」。
- **tests**：N/A（無新 code，引用對照）。
- **rollback**：N/A。

### T-NAV-5：approach / fusion / patrol-v1 spec 引用（A5/A6/A7，不重寫）

- **task_type**：[pure software]
- **內容**：三 spec 6/13 已落檔（Lane 6 T6-8①②③）；本份只做「6/18 前可否動」排程判斷（全 no，pre-6/18 不開工），不重寫 spec 內文。
- **tests**：N/A（引用）。
- **rollback**：N/A。

### T-NAV-6（HITL）：initialpose 物理錨定校正（A10 真機）

- **task_type**：[Go2 motion needed]（含低速 motion：goto 0.3m 暖身）
- **內容**：Go2 正前方對齊牆面/已知物體 → LiDAR angle bin 驗 → 設 initialpose → `tf2_echo map base_link` 驗 yaw → goto 0.3m 暖身。**所有後續 motion 項的開場儀式。**
- **tests**：`pawai smoke nav --static` 8/8 PASS（前置）；`tf2_echo` yaw 對得上現場；goto 0.3m 朝向偏移可接受 + 0 撞。
- **HITL checklist**：① e-stop 終端就位（口頭確認）② 場地淨空 ③ profile = indoor_tight ±18° + 低速 ≤0.2 ④ cov 不在紅區才發 goal ⑤ 非預期方向/該停沒停/機鼻 <0.3m 仍動 → abort。
- **rollback**：emergency_stop engage / `pawai demo stop` 路由 nav cleanup；FAIL → motion 全段 NOT_DEMO_READY、退 fallback ②③。

### T-NAV-7（HITL）：safe-stop N8 + 短距 n=3（A2 + A1，依賴 T-NAV-6）

- **task_type**：[Go2 motion needed]
- **內容**：[Lane 6 N8](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（danger 停/clear 放/無誤擋各一輪）+ [N3](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（0.3/0.5/1.0m × n=3，1.0m 先 N2 進 green）。每發記 cov/actual/朝向/結果。
- **tests**：N8 該停都停 + clear 放行 + 0 撞；N3 0.3/0.5m × 3 全 reached 0 撞 → 升 demo_ready 候選。
- **HITL checklist**：同 T-NAV-6 ①-⑤ + abort 條 1（非預期方向）、條 5（機鼻 <0.3m）逐發確認。
- **rollback**：任一距離/輪 FAIL 不連坐（ladder §6）；FAIL → proven table 照實標、claim wording 對應降級。

### T-NAV-8（HITL）：不掃圖直走 + Studio 證據（A9 真機，依賴 T-NAV-6）

- **task_type**：[Go2 motion needed]
- **內容**：低速 ≤0.2 直走一段 + 前方放障礙驗 reactive_stop 停 + Studio LiDAR 點雲 + zone 狀態同框錄證據 + 遙控接管演練。
- **tests**：直走偏移角記錄；reactive_stop 停障 0 撞；Studio 證據完整；遙控接管可行。
- **HITL checklist**：同 T-NAV-6 ①-⑤；**特別確認直走 cmd_vel 來源（teleop）+ reactive_stop progressive mode active + teleop 可即時 kill**。
- **rollback**：鬆開按鍵 / emergency_stop engage；FAIL → 退純遙控 + Studio 證據（fallback ②）。

### T-NAV-9（HITL，stretch）：poses 重錄 + run_route 單圈（A4 + A5，依賴 T-NAV-6 + Lane 6 N1/N7）

- **task_type**：[Go2 motion needed]
- **內容**：[Lane 6 N1](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（poses/routes 重錄 + evidence pull）+ [N5](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)（run_route 單圈，操作員監督 + Studio 三層同框）。**stretch——時間不夠先砍**（Lane 6 §8）。
- **tests**：poses 記錄成功 + route 組成 + evidence pull 拉得回；單圈跑通所有段 reached + 0 撞 → C9 有展示物（可講 S7）。
- **HITL checklist**：同 T-NAV-6 ①-⑤ + 依賴 N7 orphan 根治（否則中斷留 orphan 卡死 route）+ 每圈 cov 重檢。
- **rollback**：FAIL → C9 維持 PROTOTYPE、S7 不講、走影片 fallback。

---

## §4 三桶分類（Pure software / Jetson / Go2 HITL）

### 桶 1：Pure software（WSL，AFK，週末可做）

| Task | 對應能力 | 價值 |
|---|---|---|
| T-NAV-1 initialpose 朝向校正 SOP | A10 | **P0——所有 motion 前置；6/13 撞牆直接修法** |
| T-NAV-2 safe-stop margin 量化表 | A2 | P0——claim wording S2 佐證 |
| T-NAV-3 不掃圖直走可行性 + 證據呈現 | A9 | **P0——直接回應 Roy 需求 + 6/13 繞過路徑** |
| T-NAV-4 引用 Lane 6 純軟體項（標歸屬，不重做） | A3/A4/A5 | 邊界釐清 |
| T-NAV-5 三 spec 引用（不重寫） | A5/A6/A7 | 邊界釐清 |

### 桶 2：Jetson needed（deploy + 軟體驗證，不一定動狗）

- nav stack deploy（與 brain demo **8GB 互斥**，需切 stack）——T-NAV-6~9 的前置。
- `pawai smoke nav --static` 8/8（[acceptance Task3 已證可過](../../runbook/2026-06-13-post-refactor-acceptance-report.md)）。
- `lidar_front_sector.py` / `scan_health_check.py` / `tf2_echo map base_link` 可跑確認（A10/A9 工具）。
- reactive_stop active + indoor_tight profile 確認。

### 桶 3：Go2 motion needed（HITL，需 e-stop + 淨空 + Roy 在場）

| Task | 能力 | 估時 | 依賴 |
|---|---|---|---|
| T-NAV-6 initialpose 校正 + goto 0.3m 暖身 | A10 | ~20min | smoke nav static 8/8 |
| T-NAV-7 safe-stop N8 + 短距 n=3 | A2/A1 | ~45min | T-NAV-6 |
| T-NAV-8 不掃圖直走 + Studio 證據 | A9 | ~20min | T-NAV-6 |
| T-NAV-9（stretch）poses 重錄 + run_route 單圈 | A4/A5 | ~50min | T-NAV-6 + Lane6 N1/N7 |

> 全程 e-stop（emergency_stop.py engage 終端就位）；abort criteria（[Lane 6 §8](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）逐條生效；nav stack 與 brain demo 8GB 互斥（獨立時段，B-9）。**A6/A7/A8 無 HITL（pre-6/18 不開工 / 永遠不做）。**

---

## §5 Metrics / Pass-fail threshold 總表

| 能力 | Metric | Pass threshold | Fail 處置 |
|---|---|---|---|
| A1 短距 0.3/0.5m | reached 率(n=3)、actual 誤差、朝向偏移、撞擊數 | 0.3/0.5m × 3 全 reached + 0 撞 → demo_ready 候選 | 任一撞 = 該距離 FAIL，當日不再試，退保守措辭 |
| A1 短距 1.0m | 同上 + cov 收斂 | 需 N2 進 green 才測，全 reached 0 撞 | 黃帶卡死 = N/A，**F8 禁講 1.0m** |
| A2 safe-stop | danger 距離、0 撞 0 暴衝率、誤擋率、機鼻 buffer | danger 該停都停 + clear 放行 + buffer >0.3m + 0 撞 | 該停沒停 = abort 全部後續 motion |
| A3 stop-resume | operator-confirm 成功率、lunge 數據 | 停→確認→續走 0 撞 → 可講 S3 | lunge 重現 = abort，退 operator-confirm only；**auto-resume 永不啟用** |
| A4 poses/routes | 記錄數、route 組裝、備份完整性 | 2-3 poses + 1 route + evidence pull 拉得回 → NEEDS_RETEST | — |
| A5 patrol v0 | 單圈完成率、各段 reached、0 撞 | 單圈跑通 + 操作員監督 → C9 有展示物（S7） | 未跑通 = PROTOTYPE，S7 不講，走影片 |
| A6 approach | —（spec only） | spec 過審 + 三硬閘 → 可開工(post-6/18) | **F6 禁講已具備** |
| A7 fusion | —（spec only） | spec 過審 + B1/B2 解 → 可開工(post-6/18) | **F3 禁講已融合 costmap** |
| A8 detour | —（不做） | N/A | **F1/F2 永遠禁講** |
| A9 不掃圖直走 | 偏移角、停障率、Studio 證據、遙控反應 | 低速直走 + reactive 停 + 0 撞 + Studio 同框 → fallback ② | 偏移撞家具 = FAIL（同 6/13 根因，需 A10）；**禁講「自主直線避障」** |
| A10 initialpose 朝向 | 校正後 goto 0.3m 偏移角、撞擊數、cov 收斂時間 | 設準 → goto 0.3m 偏移可接受 + 0 撞 → motion 前置成立 | 仍撞 = 校正法 FAIL，當日所有 motion abort |

---

## §6 Rollback 總表

| 層級 | Rollback 手段 |
|---|---|
| **純軟體文件**（T-NAV-1/2/3/4/5） | 文件無 code，不合用即廢棄；零 runtime 影響 |
| **HITL motion**（T-NAV-6~9） | 現場 `emergency_stop.py engage`（mux pri 255 + StopMove）/ `pawai demo stop` 路由 nav cleanup；任一項 FAIL 不連坐（ladder §6） |
| **資料項**（poses/routes，A4/A5） | runtime 資料非 code，錄壞重錄；`evidence pull` 異地備份（B2 bug 6/13 已修，缺失目錄優雅跳過） |
| **claim 降級** | 任一能力 HITL FAIL → proven table 照實標、[claim wording](../../navigation/2026-06-13-nav-618-claim-wording.md) 對應降級（S1 去「可靠」、S7 整句不講、退 fallback ②③） |
| **demo fallback 不受影響** | S1 nav 鏡影片已錄（demo snapshot tag）；nav 段三層 fallback 任一層都能交付（**不存在 nav 整段開天窗**） |
| **research（A6/A7/A8）** | pre-6/18 無 code，無回退；fusion/approach 開後 D435 source 必須可一鍵關 |

---

## §7 決策表（before_monday + enter_6/18_runtime + 理由）

| 能力 | before_monday | enter_6/18_runtime | 理由 |
|---|---|---|---|
| **A10 initialpose 朝向 SOP** | **yes** | **yes ※** | 純軟體 SOP 週末可做，且是**所有 motion 的硬前置**——不先做，A1 重測必再撞（6/13 已撞）。校正是 demo 必走儀式。**※ enter=yes＝定位重設操作儀式必走，非宣稱朝向校正已可靠收斂（C7 仍 LOW_SAMPLE，不講可靠收斂）** |
| **A2 safe-stop margin** | **yes** | **yes** | 已 proven（C4）；margin 量化表純軟體；safe-stop 是 nav 段核心可講能力（S2），配 §3 標準說法 |
| **A9 不掃圖直走** | **maybe** | **maybe** | 可行性評估文件 yes（P0，回應 Roy + 繞過 6/13 撞牆）；真機直走需 motion 時段；可作 fallback ②演出但**禁講自主避障** |
| **A1 短距 n=3** | **maybe** | **maybe** | 純軟體記錄表 yes；真機 n=3 **必須先 A10**否則重蹈撞牆；過後 0.3-0.5m 進 fallback ①，1.0m 不進 |
| **A4 poses/routes** | **maybe** | **maybe** | SOP 歸 Lane 6（AFK 可做）；重錄 HITL 需真機；恢復後 NEEDS_RETEST，goto_named 需大空間才有意義 |
| **A3 stop-resume** | **maybe** | **maybe** | param 防呆歸 Lane 6（AFK）；operator-confirm HITL 需真機；過 N6 才講 S3，**auto-resume 永不** |
| **A5 patrol v0** | **maybe** | **no** | spec 已落檔；v0 單圈是 stretch HITL（依賴 A4+N7+A10，低機率排上）；僅 N5 跑通才講 S7 |
| **A6 approach** | **no** | **no** | C12 spec only；pre-6/18 不開工；**F6 禁講** |
| **A7 fusion** | **no** | **no** | C12 spec only；B1/B2 未解不開工；**F3 禁講** |
| **A8 dynamic detour** | **no** | **no** | C11 DO_NOT_CLAIM；Lane 6 §5 明禁；硬轉摔狗；**F1/F2 永遠禁講** |

---

## §8 需 Roy 拍板的 open decisions

1. **A10 vs A9 路線選擇（最關鍵）**：6/13 撞牆後，nav motion demo 要走 **(A10) 修好 AMCL initialpose 朝向校正再 goto**，還是 **(A9) 乾脆不掃圖、teleop 低速直走 + reactive_stop 兜底 + Studio 證據**？兩者不互斥（A9 仍需精準初始朝向），但決定 6/18 nav 那一幕的主演出形態。建議：兩條都先做純軟體評估（週末），motion 時段先驗 A10（成立則 A1 可往 demo_ready），A9 作平行 fallback ②保底。

2. **motion HITL 時段（B-9）是否排得進 6/18 前**：所有 motion 項（T-NAV-6~9）需 nav stack（與 brain demo 8GB 互斥）+ e-stop + 淨空 + Roy 在場半天。6/13 撞牆後若朝向校正仍不穩，nav 是否乾脆全走 fallback ③純影片（S1 已錄）？這是 B-10 fallback 層決策的輸入。

3. **A1 1.0m 是否值得排**：1.0m 需 N2 covariance SOP 進 green 才測，居家窄場大概率排不上，且 **F8 明禁講 1.0m+**——是否直接放棄 1.0m、只追 0.3-0.5m 的 n=3？建議放棄 1.0m（投報比低）。

4. **A9「不掃圖直走」的對外措辭**：若 demo 演直走 + safe-stop，措辭要嚴守「操作員下令前進 + 遇障安全停 + Studio 即時感知證據」，**絕不能讓觀眾以為是「自主導航/避障」**。Roy 是否接受這個「誠實但較弱」的演出？（vs 走 A10 goto 顯得更「自主」但 6/13 撞過牆、風險高）。

5. **A5 patrol v0 是否值得佔 motion 時段**：N5 是 stretch（依賴 A4 poses 重錄 + N7 orphan 根治 + A10 朝向，三重前置），跑通才有 S7。半天時段若 A10+A1+A2 已吃滿，patrol v0 是否直接砍到 post-6/18？建議砍（除非 A10 異常順利且時間有餘）。

6. **A3 auto-resume 終局（A-9）材料**：是否要本份順帶整理 lunge 數據 + 兩案利弊一頁供 post-6/18 決策？（偏 research，列 P2 附帶，非 6/18 必要）。

7. **research 三條（A6/A7/A8）pre-6/18 完全不碰確認**：本份判斷全 no（spec 已落檔、開工前置未達）。Roy 確認 6/18 前 nav 不投任何 research 開發資源、只引用 spec？
