# Advanced Robot Control / Security Hardening 計畫（誰能命令機器人 — enforcement flip 決策層）

> **日期**：2026-06-13　**狀態**：PLANNED（待 Roy 審核，審核前不實作、不改 runtime、不碰任何既有檔案）
> **角色**：Cloud B「Advanced Capability Upgrade」之一。本份只寫計畫；唯一 Write 目標 = 本檔案。
>
> **上游連結（權威，本份引用不複製內文）**：
> - 修法權威：[`docs/security/2026-06-11-pawai-hardening-plan.md`](../../security/2026-06-11-pawai-hardening-plan.md)（P0-1 / P0-2 / P1-1~4 / P2-1~4 / P3-x）
> - Findings 真相源：[`docs/security/2026-06-11-pawai-security-findings-ledger.md`](../../security/2026-06-11-pawai-security-findings-ledger.md)（94 筆，7 critical）
> - DDS 範本：[`docs/security/2026-06-13-cyclonedds-hardening-template.md`](../../security/2026-06-13-cyclonedds-hardening-template.md)
> - 機制層 lane（**不重抄**，本份做其上的 enforcement flip 決策層）：[`docs/superpowers/plans/2026-06-13-lane5-robot-control-security-hardening-plan.md`](2026-06-13-lane5-robot-control-security-hardening-plan.md)
> - 系統 Phase 4（post-6/18 全段）：[`docs/superpowers/plans/2026-06-11-phase4-robot-control-nav-hardening.md`](2026-06-11-phase4-robot-control-nav-hardening.md)
> - 驗收基線：[`docs/runbook/2026-06-13-post-refactor-acceptance-report.md`](../../runbook/2026-06-13-post-refactor-acceptance-report.md) §6（default-off byte-identical、auth-on 401/403 機制已驗）
> - Nav capability ladder（C1-C12，本份 nav 相關全對齊）：[`docs/navigation/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)
> - master 決策登記簿 B-4 / B-5 / B-6：[`docs/superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md`](2026-06-13-aggressive-pre618-master-plan.md)

---

## 這份是什麼

**這份是「enforcement flip 的決策與風險分析層」。** Lane 5（機制先行版）已把多數安全項做成 **env/param-gated、預設關 = byte-identical** 的機制（auth.py PR #158、`/webrtc_req` filter、route_id 消毒、security_smoke.sh 等）。本份**不重做機制**，而是回答每一項機制「**6/18 前該不該翻成 enforced？翻了會不會破 demo？翻的證據門檻是什麼？rollback 是什麼？**」——並把進階/選配的控制權收斂（forbidden API driver block 的 whitelist 模式、emergency stop policy、DDS isolation 評估）逐項分級 proven / needs_hitl / research_only / do_not_claim_by_618。

## 這份不是什麼

- **不是 Cloud A 的 demo flow 可靠度計畫**：phase conductor / offline fallback / demo 可靠度歸 Cloud A，本份不重複（凡屬該範疇逐項標「歸 Cloud A，本計畫不重複」）。
- **不是 Lane 5 機制層的重抄**：Lane 5 §6 的 T5S-1~T5S-9 機制實作是權威，本份**引用其 task 編號**做決策，不複製其內文。
- **不是 nav 能力面計畫**：poses/routes 重錄、短距可靠性、stop-resume、fusion/patrol/approach 等能力歸 Lane 6 / ladder。本份在 nav 上**只碰授權與消毒**（誰能命令 nav），能力 claim 一律對齊 ladder C1-C12 與其「6/18 可否講」欄。
- **不是攻擊程式碼**：全為防禦性設計建議，未實作、未測試。

---

## §0 TL;DR 總表

| # | sub-capability | 分級 | 優先 | task_type | before_monday | 進 6/18 runtime | 對應 finding / hardening |
|---|---|---|:---:|---|:---:|:---:|---|
| 1 | gateway auth secure-default（token/Origin/CORS flip，B-6） | needs_hitl | P1 | mixed | maybe | maybe | EXP-01/GW-01/GW-04 · P0-1 · Lane5 T5S-3/T5S-8 |
| 2 | Foxglove clientPublish 降權（B-5；斷 nav initialpose） | needs_hitl | P1 | mixed | no | maybe | EXP-02 · P0-2 · Lane5 T5S-7 |
| 3 | /webrtc_req whitelist enforcement flip | needs_hitl | P1 | jetson_needed | no | no | MOT-01/MOT-08 · P1-2 · Lane5 T5S-1 |
| 4 | forbidden API driver-level block（blacklist 模式） | proven | P0 | pure_software | yes | maybe | MOT-01 · P1-2 · Lane5 T5S-1 |
| 5 | nav action auth（interface 級授權，post-6/18） | research_only | P2 | go2_motion_needed | no | no | MOT-05 · P1-3① · Phase4 T4A-5① |
| 6 | DDS domain isolation / SROS2 feasibility | research_only | P2 | jetson_needed | no | no | EXP-03/LLM-10/GAP3-03 · P1-1 · T4A-3 |
| 7 | cmd_vel / mux ownership boundary（post-6/18） | research_only | P2 | go2_motion_needed | no | no | MOT-02/03/10 · P1-4 · T4A-6 |
| 8 | route_id sanitize（注入防護，純軟體） | proven | P0 | pure_software | yes | yes | MOT-04 · P1-3② · Lane5 T5S-2 |
| 9 | security smoke 擴充（security_smoke.sh） | proven | P0 | pure_software | yes | n/a（測試工具） | 滲透清單自動化 · Lane5 T5S-6 |
| 10 | emergency stop / hold brake policy | needs_hitl | P1 | go2_motion_needed | no | maybe | MOT-10/GAP3-01 · P3-4 · T4A-7 |

> **分級語意**：`proven` = 純軟體已可機制驗證、邏輯封閉、6/18 前可安全完成且不破 demo；`needs_hitl` = 翻成 enforced 前必須 Roy 在場真機回歸（Jetson/Go2）；`research_only` = post-6/18、只落 spec / 評估報告；`do_not_claim_by_618` = 6/18 對外不得宣稱已具備（本份無此級獨立項，但「未授權者已不能讓 Go2 動」為對外 forbidden claim，見 §1）。
> **`proven` 的精準邊界**：指「**機制/消毒邏輯**已可在 WSL 純軟體證明封閉」，**不等於** enforcement 已在發表日打開。第 4/8/9 項即使 proven，是否翻 enforced 仍受 §7 決策表約束。

---

## §1 範圍與邊界

### 與 Cloud A 的分界

| 主題 | 歸屬 | 本份是否碰 |
|---|---|---|
| phase conductor / demo 段落編排 | Cloud A | 否（歸 Cloud A，本計畫不重複） |
| offline fallback（LLM/TTS/ASR 斷線降級） | Cloud A | 否（歸 Cloud A，本計畫不重複） |
| demo 可靠度 smoke（`pawai smoke brain/full`、healthcheck）| Cloud A | 否——但 §9 security_smoke 是**安全滲透**驗證，與 demo smoke 正交、不重疊 |
| 「誰能命令機器人」的授權 / 消毒 / 控制權邊界 | **本份** | 是 |
| enforcement flip 決策（B-5/B-6 風險與門檻） | **本份** | 是 |

### 與 Lane 5 機制層的分界

Lane 5 = **機制入庫（預設關 = byte-identical）+ 紅綠單測**。本份 = **flip 決策 + 風險 + HITL 門檻 + rollback 總表**。對應關係：

- Lane5 T5S-1（webrtc filter 機制）→ 本份 §2.3（whitelist flip 決策）+ §2.4（blacklist 模式，可 proven）。
- Lane5 T5S-2（route_id 消毒）→ 本份 §2.8（純軟體 proven，可進 runtime）。
- Lane5 T5S-3/T5S-8（gateway token wiring + auth flip 彩排）→ 本份 §2.1（B-6 flip 決策）。
- Lane5 T5S-6（security_smoke.sh）→ 本份 §2.9（擴充與覆蓋率）。
- Lane5 T5S-7（foxglove 降權）→ 本份 §2.2（B-5 決策，斷 initialpose 權衡）。
- Lane5 T5S-9（cyclonedds.xml 範本）→ 本份 §2.6（DDS isolation 評估，全 post-6/18）。

### 與 Lane 6 / ladder 的分界

本份在 nav 上**只碰授權（nav action auth §2.5）與消毒（route_id §2.8）**。任何 nav **能力**宣稱一律引用 ladder：短距 goto = C1/C2/C3、safe-stop = C4、stop-resume = C5、indoor_tight = C6、initialpose = C7、orphan = C8、patrol = C9、goto_named/run_route = C10、free roam/dynamic detour = C11（`DO_NOT_CLAIM`）、fusion/approach = C12（`DO_NOT_CLAIM`）。**安全停 ≠ 繞障**（ladder C4 註：safe-stop 永不升成繞障，繞障是 C11 `DO_NOT_CLAIM`）。**單次成功 ≠ 可靠**（ladder N3 要求 n=3）。

### 對外 forbidden claim（本份產生的安全 claim 紀律）

- ❌ **不可講「未授權者已不能讓 Go2 動」**：DDS 面（R2）未收斂，5 條未認證→motion 路徑只封了機制、不全是 enforcement（Lane 5 §13 已明訂）。**誠實版**：「控制面 hardening 機制已入庫、注入點已修、enforcement 分階段上線中」。
- ❌ 不可把 §2.4 blacklist 模式講成「已完整防護危險動作」——它只在 driver 層拒 3 條 BANNED（1030/1031/1301），DDS 直發其他 api_id 仍可達（whitelist 才更全，但 whitelist 屬 needs_hitl）。
- ✅ 可講：「driver 層已有 forbidden-api block 機制、gateway 已有認證機制（401/403 已驗）、route_id 注入點已消毒、安全滲透有自動化 smoke」。

---

## §2 逐能力 13 點分析

### 2.1　gateway auth secure-default（token / Origin / CORS；flip 時點 B-6）

> 分級 **needs_hitl** · 優先 **P1** · task_type **mixed** · before_monday **maybe** · 進 runtime **maybe**

1. **Desired demo benefit**：發表日可現場展示「未授權請求被 401/403 擋下」這一刀，把「誰能命令機器人」從口頭講成可演示的事實；同時關掉「瀏覽器/LAN → 機器人移動」最高投報率缺口（EXP-01/GW-01）。
2. **Current baseline**：機制層 `auth.py`（PR #158）**已 ship 且預設關**，真機雙模式驗過——驗收報告 §6「default-off Studio 可用；auth-on enforcement 401/403 機制驗證」。但 ledger 確認 production gateway `__main__` 仍綁 `host="0.0.0.0", port=8080`（GW-01 行 1333）、CORS `allow_origins=["*"]`（行 876，註解自承「Demo internal network — acceptable risk」）、WS 無 Origin 檢查（GW-04 行 1209）。**前端 13 HTTP + 4 WS、CLI probe、healthcheck 尚未會帶 token**（Lane5 §2 實證）→ 直接 flip 即斷 Studio/demo。
3. **Candidate options**：(a) **發表日維持 default-off**（demo 行為與已錄影片一致，最安全）；(b) **發表日 auth-on**（需 T5S-3 wiring 完成 + T5S-8 彩排全綠 + B-6 點頭）；(c) **混合**：對外網段走 SSH tunnel / 反向代理，gateway 仍綁 loopback（hardening P0-1 修法①）。
4. **Required data**：token 發放流程（Roy 決策，A-3）、前端 token 來源（`NEXT_PUBLIC_GATEWAY_TOKEN` env / localStorage，Lane5 T5S-3）、CLI probe token（`GATEWAY_TOKEN` env）、CORS 白名單 IP（隊員筆電 / `localhost:3000`）。
5. **Pure software tasks**：前端 fetch/WS 統一加 `Authorization: Bearer`（無 token 時 header **完全不帶**＝現行為，Lane5 T5S-3）；CLI probe / healthcheck 支援帶 token；CORS 改白名單、WS 加 Origin 檢查（GW-04）——**全部在 default-off 下 byte-identical**。**機制本體不重寫**（auth.py 已在）。
6. **Jetson tasks**：T5S-8 auth-on 彩排——Jetson 開 auth-on（env）→ 跑 Studio 全流程（按鈕 / push-to-talk / video / nav panel / Evidence 頁）+ `pawai status` / smoke + security smoke。
7. **Go2 HITL tasks**：低度（auth 不直接動 motion；Studio nav panel 若觸發 GotoRelative 需 Go2 連線確認不誤殺）。
8. **Metrics**：auth-on 模式下 Studio 全流程操作成功率（目標 100%）；無 token 對狀態變更端點 → 401（已驗）；偽 Origin WS → 拒（GW-04）；`redact=0` 無 token → 403（A-11，驗收報告已 🟢）。
9. **Pass/fail threshold**：**PASS = auth-on 彩排 demo 全流程零中斷 + security_smoke 三項 HTTP 斷言全綠（MOT-01+GW-02 401 / 偽 Origin 非 101 / trace export 403）**。任一紅 → 發表日 default-off。
10. **Risk**：token wiring 漏一個端點 → 該端點 401 → demo 中該功能死（如 push-to-talk）。CORS 白名單漏隊員 IP → 前端 fetch 被擋。**flip 後若無一鍵退路 → demo 當天崩**。
11. **Rollback**：auth 全程 env-gated，翻回 default-off 一個 env（S0-2 已驗 byte-identical）。發表日預設姿態 = **off**，除非 B-6 點頭。
12. **Before Monday？ maybe**：純軟體 wiring（T5S-3）可 AFK 在週末前完成（屬 proven 子工作）；但 **flip 決策（B-6）不在週末做**——master 排在 6/15-16，且需 T5S-8 彩排（HITL #2，6/15 晚）。故「wiring maybe、flip no」。
13. **進 6/18 runtime？ maybe**：master B-6 預設「wiring 完成 + HITL 全綠才考慮 on；否則 default-off 進發表」。符合 master B-4「6/18 前換 runtime 的預設答案是不換」精神——auth 是**新增 enforced 行為**，需證據門檻。

---

### 2.2　Foxglove clientPublish 降權（B-5；會斷 nav initialpose 工作流）

> 分級 **needs_hitl** · 優先 **P1** · task_type **mixed** · before_monday **no** · 進 runtime **maybe**

1. **Desired demo benefit**：封掉 EXP-02（critical）——瀏覽器未認證即可 advertise/publish `/cmd_vel` 直接驅動 Go2。降權後 Foxglove 仍可看 topic/影像但不能 publish。
2. **Current baseline**：ledger EXP-02 確認 foxglove_bridge 預設 `address=0.0.0.0` + `capabilities` 含 `clientPublish`，啟動行在**凍結腳本** `start_full_demo_tmux.sh:274`，另涉 8 處 `start_*.sh`（hardening P0-2 列 6 處 + Phase4 T4A-2 補 2 deprecated）。兩 fix 已備：`-p capabilities:='["connectionGraph"]'`（唯讀）或 `-p address:=127.0.0.1`（僅本機）。
3. **Candidate options**：(a) **降權**（B-5 通過，發表不開 Foxglove）；(b) **post-6/18**（發表仍需 Foxglove 設 initialpose）；(c) **先遷工作流再降權**（Phase4 T4A-2 兩 PR：initialpose 遷 Studio `/api/nav/initialpose` → 再降權）。
4. **Required data**：發表日是否需要現場 Foxglove（Roy 決策 B-5）；nav initialpose 是否已能在 Studio nav control 完成（gateway `/api/nav/initialpose` **已存在**，Phase4 Inputs 表確認）。
5. **Pure software tasks**：腳本 foxglove 行加 capabilities 參數（**碰凍結腳本** `start_full_demo_tmux.sh:274`，逐改知情程序，單獨 PR）。
6. **Jetson tasks**：降權後驗證——Foxglove 仍可看 topic/影像、瀏覽器 client 無法 advertise/publish `/cmd_vel`。
7. **Go2 HITL tasks**：若 initialpose 遷 Studio → 需 nav stack 在跑驗 AMCL 收到 pose（`Setting pose` log + `map→odom` TF）。
8. **Metrics**：降權後 Foxglove publish `/cmd_vel` → 拒；可視化（topic/image panel）仍正常；若遷工作流 → Studio 設 initialpose 後 AMCL covariance 收斂（對齊 ladder **C7** initialpose `hardware_proven`）。
9. **Pass/fail threshold**：**PASS = EXP-02 封閉（client publish 被拒）+ demo smoke 全綠 + （若需 initialpose）Studio 設 pose 實機驗證過**。
10. **Risk**：**已知衝突點**——降權會斷「nav `/initialpose`-via-Foxglove」工作流（Phase4 T4A-2 卡點）。nav lane 場測仍靠 Foxglove 設 `/initialpose`（CLAUDE.md nav demo 流程）。若未先遷工作流就降權 → nav 定位流程斷。
11. **Rollback**：拿掉 capabilities 參數一行即回原行為（PR revert）。
12. **Before Monday？ no**：碰凍結腳本（逐改知情程序）+ 需 B-5 決策（master 排 6/15）+ 需確認 initialpose 替代路徑。週末不動凍結面。
13. **進 6/18 runtime？ maybe**：master B-5「若發表不開 Foxglove → 降權；否則 post-6/18」。**關鍵相依**：發表若用 Studio nav panel 設 initialpose 且已實機驗 → 可降權；否則保留 Foxglove publish 能力到 post-6/18。

---

### 2.3　/webrtc_req whitelist enforcement flip

> 分級 **needs_hitl** · 優先 **P1** · task_type **jetson_needed** · before_monday **no** · 進 runtime **no**

1. **Desired demo benefit**：whitelist 模式比 blacklist 更全——明列 demo+nav 所需 api_id（sport 基本動作 + Megaphone 4001-4004），其餘**全拒**。封 MOT-01（同 LAN 注入翻滾/跳躍/倒立）最徹底。
2. **Current baseline**：ledger MOT-01（critical，行 113）確認 `handle_webrtc_request` **零過濾直接轉發**；BANNED_API_IDS（1030/1031/1301）只在 IE SafetyLayer 層、driver 端不複查（ledger LEG/GEN-09 補強）。Lane5 T5S-1 機制：`webrtc_api_filter_mode` param——`off`（預設 byte-identical）/ `blacklist` / `whitelist`，**StopMove 1003 永遠放行**，rate limit param（預設 0 不限）。
3. **Candidate options**：(a) **off**（發表預設，byte-identical）；(b) **blacklist**（拒 3 條 BANNED，行為 = 現狀 + 拒 3 條，風險最低 → 見 §2.4，可 proven）；(c) **whitelist**（最全但誤殺風險高，需完整動作回歸）。
4. **Required data**：demo+nav 實際用到的完整 api_id 清單（sit 1009 / stand 1004 / hello 1016 / stretch 1017 / wiggle_hip 1020 / balance_stand 1002 / Megaphone 4001-4004 / StopMove 1003 …）——**需 Roy 指認 / 從 demo 動作序列實測**，漏一個即誤殺。
5. **Pure software tasks**：filter 機制與 11 條權威測試擴充（Lane5 T5S-1，`test_robot_control_service.py` 既有一條不改）——off byte-identical / blacklist 拒 3 條 / whitelist 內放行外拒絕 / StopMove 永放行 / rate limit 不擋 1 Hz StopMove dedupe。
6. **Jetson tasks**：whitelist-on 動作回歸——param 切 `whitelist` → demo 動作全流程（wiggle/hello/sit/TTS Megaphone/nav 若在）不誤殺。
7. **Go2 HITL tasks**：**需 Go2 連線（WebRTC 不可斷）**——driver 是最後實體出口，每改必驗 Go2 全動作序列。
8. **Metrics**：whitelist 內 api_id 放行率 100%（零誤殺）；whitelist 外（如 backflip 1301）拒絕 + log；StopMove 1003 永放行；rate limit 不擋 1 Hz StopMove dedupe（CLAUDE.md 記 reactive_stop 10Hz spam 曾撐爆 DataChannel 86KB+）。
9. **Pass/fail threshold**：**PASS = demo 動作 n 次全流程零誤殺 + banned api_id 拒絕 log 出現 + StopMove 永放行斷言過**。任一誤殺 → 切回 blacklist 或 off。
10. **Risk**：whitelist 漏 api_id → demo 動作被 driver 拒 → 該動作死。rate limit 設太嚴 → 撐爆問題復發或 StopMove 被擋（安全反效果）。
11. **Rollback**：param 切回 `off` = 秒級 byte-identical；whitelist 誤殺 = 切 `blacklist`（行為 = 現狀 + 拒 3 條）。
12. **Before Monday？ no**：whitelist-on 需 Jetson + Go2 完整動作回歸（HITL），週末非 HITL 時段。機制單測本身屬 Lane5 純軟體（可週末），但 flip 不行。
13. **進 6/18 runtime？ no**：whitelist 誤殺風險對發表太高（漏一個 api_id = 一個動作死），且 master B-4「不換」精神。**發表日 webrtc filter 維持 off**（驗收報告 §6 已記 off byte-identical）；blacklist 模式（§2.4）才是 maybe。

---

### 2.4　forbidden API driver-level block（blacklist 模式）

> 分級 **proven** · 優先 **P0** · task_type **pure_software** · before_monday **yes** · 進 runtime **maybe**

1. **Desired demo benefit**：在 driver 層加最後一道——即使 SafetyLayer 被繞過（DDS 直發 `/brain/proposal` 偽造 priority_class，LLM-01）或直發 `/webrtc_req`（MOT-01），driver 仍拒 3 條 BANNED（1030/1031/1301 翻滾/跳/倒立）。縱深防禦最便宜的一刀。
2. **Current baseline**：BANNED_API_IDS（`speech_processor/llm_contract.py`，3 條）目前只在 `interaction_executive/safety_layer.py` 引用、**driver 端零複查**（ledger MOT-01 / LEG / GEN-09 三處互相補強：「go2_driver 端不複查；任何直接 pub /webrtc_req 的人也不受這些 gate 約束」）。
3. **Candidate options**：(a) **blacklist 模式**（driver 拒 3 條 BANNED，從 pawai_contracts 讀，不重抄）；(b) whitelist（§2.3，更全但需 HITL）。本節聚焦 blacklist。
4. **Required data**：BANNED_API_IDS 權威值（1030/1031/1301）**從 pawai_contracts 讀取**（Lane5 紀律：不 hardcode）。
5. **Pure software tasks**：Lane5 T5S-1 的 blacklist 分支實作 + 單測（拒 3 條、其餘放行、StopMove 1003 永放行、off parity 不變）。**純 WSL，可 AFK**。
6. **Jetson tasks**：blacklist-on 不誤殺驗證可併入 §2.3 的動作回歸（blacklist 比 whitelist 風險低——只多拒 3 條本就不該出現在 demo 的危險動作）。
7. **Go2 HITL tasks**：低度——blacklist 只拒 3 條翻滾類，demo 動作序列本就不含，理論上零誤殺；但仍建議一輪 Go2 動作回歸確認。
8. **Metrics**：3 條 BANNED 拒絕率 100% + log；demo 全動作（不含翻滾類）放行率 100%；off parity byte-identical（紅綠測試）。
9. **Pass/fail threshold**：**PASS = blacklist 單測全綠（拒 3 條 / 放行其餘 / StopMove 永放行 / off byte-identical）**。HITL 端 = demo 動作零誤殺。
10. **Risk**：低。唯一風險 = 若 BANNED 清單未來新增某個 demo 用得到的 api_id（目前不會，1030/1031/1301 都是危險動作）。
11. **Rollback**：param 切回 `off`（byte-identical）；blacklist 本身行為 = 現狀 + 拒 3 條，revert 即回。
12. **Before Monday？ yes**：純軟體機制 + 單測（Lane5 T5S-1 的 blacklist 子集），WSL 可完成。**flip 到 enforced 仍需 §7 決策**。
13. **進 6/18 runtime？ maybe**：blacklist 是**低風險、高敘事價值**的縱深防禦（可講「driver 層已擋危險 api_id」）。若 §2.3 動作回歸時 blacklist-on 零誤殺 + Roy 點頭 → maybe 進發表（比 whitelist 安全得多）。否則維持 off + 講「機制已入庫」。

---

### 2.5　nav action auth（nav action interface 級授權，post-6/18）

> 分級 **research_only** · 優先 **P2** · task_type **go2_motion_needed** · before_monday **no** · 進 runtime **no**

1. **Desired demo benefit**：封 MOT-05（critical，critic 升級）——同 LAN 主機可 `ros2 action send_goal /nav/goto_relative` 命令機器人導航到任意座標，零認證。
2. **Current baseline**：ledger MOT-05（行 118）確認 4 個 nav action server（`/nav/goto_*`、`/nav/run_route`、`/log_pose`）**零認證**（`_accept_goal` 只擋並行）。Phase4 §Problems 明指「ROS2 action 模型下沒有便宜解（goal 無 caller identity；加 token 欄位 = 改 `.action` interface = 全鏈 rebuild）」。
3. **Candidate options**：(a) demo lock owner / token 檢查；(b) 限定只接受 Brain Executive 轉發、禁外部直呼 action；(c) `.action` interface 加 token 欄位（全鏈 rebuild，post-6/18）。**全屬 interface 級改動**。
4. **Required data**：nav action 授權模型（Roy 決策）；caller identity 在 ROS2 action 下如何取得（無便宜解，需設計）。
5. **Pure software tasks**：spec 撰寫（授權模型評估）——本份只落 spec，不寫 code。
6. **Jetson tasks**：post-6/18（Phase4 T4A-5①）。
7. **Go2 HITL tasks**：post-6/18——nav action 授權動到「Go2 會不會動」本體，需 motion 回歸。
8. **Metrics**：未授權 `action send_goal` → reject（post-6/18 驗）；合法 goto/run_route 流程不破。
9. **Pass/fail threshold**：post-6/18 定義（Phase4 T4A-5）。本份 = spec 含授權模型 + HITL 升級條件。
10. **Risk**：改 `.action` interface = 全鏈 rebuild = 高破壞性，發表前嚴禁（Lane5 §5 Forbidden 3、Phase4 Forbidden）。
11. **Rollback**：N/A（不實作）。
12. **Before Monday？ no**：interface 級、需全鏈 rebuild + motion 回歸，5 天內不該碰（Lane5 §3 明訂）。
13. **進 6/18 runtime？ no**：post-6/18（Phase4 T4A-5①）。**注意**：`route_id` 消毒（§2.8）是 MOT-05 鄰項 MOT-04 的**獨立 bugfix**，可先做、與本節 auth 分開。nav 能力 claim 對齊 ladder——C10 goto_named/run_route 目前 `wired_only` `NOT_DEMO_READY`（資料遺失），**N1 未做前不可講**。

---

### 2.6　DDS domain isolation / SROS2 feasibility（post-6/18 評估）

> 分級 **research_only** · 優先 **P2** · task_type **jetson_needed** · before_monday **no** · 進 runtime **no**

1. **Desired demo benefit**：根治 R2（DDS 信任邊界與 LAN 重合）——LLM-10 確認全 `/brain/*` `/event/*` 在無 SROS2 下對同 DDS domain 零認證，是 5 條未認證→motion 路徑的共同前提。SROS2（enclave + DDS-Security）是**唯一真正關掉 R2 的方法**（hardening P1-1）。
2. **Current baseline**：`cyclonedds-template.xml` 範本**已入庫不接線**（範本文件確認：「this commit does not set CYCLONEDDS_URI, does not change ROS_DOMAIN_ID」）；範本含 `NetworkInterface name="eth0" multicast="false"`、`AllowMulticast=false`、`Peers` 白名單（占位 `192.168.123.161` / `192.168.123.x`，需替換）。`ROS_DOMAIN_ID` 仍預設（`config/school_demo.env:37`）。
3. **Candidate options**：(a) **interface 限定 + AllowMulticast=false + Peers 白名單**（範本路線，降低 discovery/暴露面，但**不認證 participant**）；(b) **ROS_DOMAIN_ID 改非預設值**（避開 domain 0 掃描）；(c) **SROS2**（enclave + DDS-Security 認證加密，唯一真正解，但最重）。
4. **Required data**：真實 Jetson-to-Go2 ethernet interface 名（替換 `eth0` 占位，需 Roy 指認）；可信 DDS participant 清單（Jetson + 刻意加入的 dev 機）；SROS2 對 Jetson Humble 的相容性與延遲影響（**待量測**）。
5. **Pure software tasks**：cyclonedds.xml 範本完善（占位替換的接線文件）+ SROS2 評估報告——**入庫不接線**（Lane5 T5S-9）。
6. **Jetson tasks**：post-6/18（Phase4 T4A-3）——接線後需 Go2↔Jetson 全鏈路回歸（WebRTC 不可斷、5 感知 + brain + nav topic 全通）。
7. **Go2 HITL tasks**：post-6/18——DDS 收斂直接動 Go2 通訊鏈，每改必驗全鏈路。
8. **Metrics**：第二台同 LAN 主機（未列 Peers）`ros2 topic list` 看不到 / pub 不進 bus；Go2↔Jetson 全鏈路零中斷。
9. **Pass/fail threshold**：post-6/18（Phase4 T4A-3）。本份 = 範本 + SROS2 評估報告（不強制落地）。
10. **Risk**：**最危險**——動 Go2↔Jetson 通訊鏈，配置錯一格 WebRTC 斷 / 5 感知失聯。Lane5 §5 Forbidden 1、Phase4 Forbidden 1 明訂 post-6/18。
11. **Rollback**：範本不接線時零風險（純檔案）；接線後回退 = `unset CYCLONEDDS_URI` + `ROS_DOMAIN_ID` 改回（舊值記在 `school_demo.env` 註解）。
12. **Before Monday？ no**：接線需專屬實機回歸 session（Phase4 T4A-3），週末不碰通訊鏈。範本完善（純檔案）屬 Lane5 T5S-9 餘力項。
13. **進 6/18 runtime？ no**：post-6/18（Lane5 §5 Forbidden 1）。**對外 forbidden claim**：不可講「DDS 已隔離 / 未授權 peer 已進不了 bus」——範本未接線。

---

### 2.7　cmd_vel / mux ownership boundary（控制權邊界收斂，post-6/18）

> 分級 **research_only** · 優先 **P2** · task_type **go2_motion_needed** · before_monday **no** · 進 runtime **no**

1. **Desired demo benefit**：封 MOT-02（critical，driver 直訂裸 `/cmd_vel` 繞 twist_mux + reactive_stop）+ MOT-03（emergency lane 不驗速度值）+ MOT-10（`/lock/emergency` 無認證）。把「誰能驅動底盤」收斂到 mux 輸出專屬 topic。
2. **Current baseline**：ledger MOT-02（critical，行 305）確認 driver 直訂裸 `/cmd_vel`（繞 twist_mux priority 255/200/100/10）；MOT-03（high）emergency lane 不驗速度；MOT-10（low）`/lock/emergency` 任意主機可 engage（DoS）/release。hardening P1-4 **明標「需 nav lane 實機回歸」**。
3. **Candidate options**：(a) driver 改訂 mux 輸出專屬 topic（裸 `/cmd_vel` 不直連 driver）；(b) emergency lane 加速度 clamp；(c) `/lock/emergency` 來源治理。
4. **Required data**：mux 拓撲變更對 reactive_stop 4-mode 狀態機 / nav 既有行為的影響（需隔離 mux 環境先驗）。
5. **Pure software tasks**：spec + 隔離 mux 環境單測（**`test_mux_priority.py` 不可在 full stack 跑**——CLAUDE.md 鐵則：FakePublisher 是真實 publisher 會讓 Go2 衝出，4/26 撞過）。
6. **Jetson tasks**：post-6/18（Phase4 T4A-6）。
7. **Go2 HITL tasks**：post-6/18——**必排完整 nav lane 回歸**（danger 停 → clear 放行 → goto → emergency engage/release 全鏈不變）；動到「Go2 會不會停」本體。
8. **Metrics**：裸 `/cmd_vel` 直發不被 driver 收 / emergency 超速值被 clamp；nav lane 全鏈不變。
9. **Pass/fail threshold**：post-6/18（Phase4 T4A-6）。隔離 mux 先驗 priority 行為，再實機回歸。
10. **Risk**：**最高**——動 reactive_stop / nav 安全鏈本體。CLAUDE.md 記 cmd_vel=0 不停車（Go2 MIN_X 0.50）+ StopMove 路由（`test_robot_control_service.py` 11 條權威）。改錯 = Go2 停不下來。
11. **Rollback**：mux 拓撲變更前 tag；實機回歸不過即 revert，不帶病前進。
12. **Before Monday？ no**：動安全鏈本體，需完整 nav lane HITL（Lane5 §5 Forbidden 2、Phase4 Forbidden 3）。
13. **進 6/18 runtime？ no**：post-6/18（hardening P1-4 明標需 nav lane 回歸）。

---

### 2.8　route_id sanitize（注入防護，純軟體）

> 分級 **proven** · 優先 **P0** · task_type **pure_software** · before_monday **yes** · 進 runtime **yes**

1. **Desired demo benefit**：封 MOT-04（medium，路徑穿越）——同 LAN 主機可用 `route_id: "../../..."` 寫/讀 routes_dir 外 JSON，覆寫 named_poses（竄改座標 → goto_named 導向危險點，連動 MOT-06）。**純軟體、零誤殺、可直接進 runtime**。
2. **Current baseline**：ledger MOT-04（行 101-104）確認 `path = os.path.join(routes_dir, f"{goal.route_id}.json")` **無 sanitize**；`route_runner _load_route`（行 216 同樣 join）讀路徑亦可穿越。route_validator 只驗 JSON schema、不檢檔名。
3. **Candidate options**：白名單字元 `[A-Za-z0-9_-]` + 拒 `/`/`..`/絕對路徑 + 寫/讀前 `os.path.realpath` 驗最終路徑仍在 routes_dir/named_poses 內（`os.path.commonpath` 比對）。**白名單而非黑名單**（Lane5 Fable checklist）。
4. **Required data**：合法 route_id/name 字元集（`[A-Za-z0-9_-]`，與既有 `sample` 等 route_id 相容——需確認既有資料無特殊字元）。
5. **Pure software tasks**：Lane5 T5S-2 消毒實作 + 單測（惡意 route_id 全拒含 URL-encoded 變體、合法全過）。**純 WSL，可 AFK**。
6. **Jetson tasks**：無（合法輸入零行為差 = bugfix，非行為變更）。
7. **Go2 HITL tasks**：無。
8. **Metrics**：惡意 route_id（`../evil`、絕對路徑、URL-encoded）拒絕率 100%；合法 route_id（`sample` 等）通過率 100%。
9. **Pass/fail threshold**：**PASS = 消毒單測全綠（惡意全拒 / 合法全過）**。security_smoke MOT-04 項：`route_id: '../evil'` → 拒（腳本已含此手動 HITL 項）。
10. **Risk**：極低。唯一風險 = 既有 route_id 含被白名單拒的字元（需事前 grep 既有資料確認；目前命名如 `sample`/`alpha` 皆 ASCII 安全）。
11. **Rollback**：bugfix 類，revert 即回（但不應需要——合法輸入無行為差）。
12. **Before Monday？ yes**：純軟體 bugfix，無誤殺風險，WSL 可完成。
13. **進 6/18 runtime？ yes**：bugfix 非行為變更，合法輸入 byte-identical，**直接修掉沒有不修的理由**（Lane5 把它列 P0 bugfix 先行）。是少數可確定進 runtime 的項。nav 能力 claim 不受影響（C10 goto_named 仍 `wired_only`）。

---

### 2.9　security smoke（security_smoke.sh 擴充）

> 分級 **proven** · 優先 **P0** · task_type **pure_software** · before_monday **yes** · 進 runtime **n/a（測試工具，不進 runtime）**

1. **Desired demo benefit**：把「擋得住」從散文（Phase4 Tests §3 人工滲透清單）變成**可重跑腳本**——每項對應一個 finding 編號（可追溯）。發表敘事「安全有自動化驗證」。
2. **Current baseline**：`scripts/security_smoke.sh` **已存在**（Lane5 T5S-6）——3 項 HTTP 斷言（MOT-01+GW-02 無 token POST `/api/skill_request` → 401；GW-06/07/EXP-04 偽 Origin WS → 非 101；A-11 `redact=0` 無 token → 403）+ 2 項手動 ROS2 HITL（MOT-01 banned api_id 1030 → driver 拒 log；MOT-04 `route_id '../evil'` → 拒）。`set -u`，CI 不跑（需活 gateway），`bash -n` 進 pre-commit。
3. **Candidate options**：擴充覆蓋率——可補的 finding：GW-04 WS Origin（已含偽 Origin 項）、CORS 白名單驗證、whitelist-on banned 其他 api_id（1031/1301）、`/api/nav/initialpose` / `/api/nav/start` 無 token → 401（EXP-01 nav 端點）、`/api/gesture_enabled` 無 token → 401（GAP1-02 toggle DoS）。
4. **Required data**：auth-on gateway 啟動方式（腳本 header 已記：`GATEWAY_AUTH_TOKEN` + `GATEWAY_ALLOWED_ORIGINS` + `GATEWAY_HOST/PORT`）。
5. **Pure software tasks**：擴充 curl 斷言（nav 端點 401、gesture toggle 401、CORS 偽 Origin fetch）+ 每項標 finding 編號 + 可選 wiring `pawai smoke security`（Lane5 P2）。**純 WSL（腳本語法）+ HITL（真機跑）**。
6. **Jetson tasks**：真機至少跑一輪（HITL #2，配合 auth-on 彩排 §2.1）。
7. **Go2 HITL tasks**：無（只讀驗證，不發 motion；MOT-01 banned api_id 是 driver log 驗證，不真的動 Go2——但需確認 banned 確實被拒而非執行）。
8. **Metrics**：HTTP 斷言全綠（FAILURES=0 → exit 0）；每項對應 finding 編號可追溯。
9. **Pass/fail threshold**：**PASS = `security_smoke.sh` exit 0（所有 HTTP-checkable 斷言過）+ 手動 HITL 項在 Jetson 跑過一輪有紀錄**。
10. **Risk**：極低（只讀 curl，不改 source/config/topic）。誤判風險 = gateway 未起時 curl timeout（腳本 `--max-time 5` 已防）。
11. **Rollback**：N/A（測試工具，不進 runtime）。新增斷言 revert 即回。
12. **Before Monday？ yes**：純腳本擴充，WSL 可寫；`bash -n` 驗語法。真機跑配合 HITL #2。
13. **進 6/18 runtime？ n/a**：測試工具不進 runtime。但**是 enforcement flip 的驗收前提**——T5S-8 彩排、§2.1 auth flip、§2.4 blacklist flip 的「擋得住」面都靠它。

---

### 2.10　emergency stop / hold brake policy（緊急停止策略）

> 分級 **needs_hitl** · 優先 **P1** · task_type **go2_motion_needed** · before_monday **no** · 進 runtime **maybe**

1. **Desired demo benefit**：確保發表現場有**唯一、可靠、可信來源**的移動中急停；同時修文件債（GAP3-01：`safety_only=true` 會 promote 成 `hold_brake` 永久煞車鎖死 nav，CLAUDE.md 過時宣稱與實際腳本 `mode:=progressive` 矛盾）。
2. **Current baseline**：`nav_capability/scripts/emergency_stop.py` **已存在**（普通 ROS2 Bool publisher，無認證——ledger MOT-10）。CLAUDE.md / nav 安全鐵則：「移動中禁 Damp、`emergency_stop.py engage` 為唯一移動中急停、teleop 嚴格 kill」（Phase4 §Jetson requirement）。twist_mux `/lock/emergency` priority 255、timeout 0.0（ledger MOT-10）。reactive_stop 4-mode 狀態機（`docs/navigation/CLAUDE.md` 載 27 cases，CLAUDE.md 仍記舊數 17，T4A-7 文件債）。
3. **Candidate options**：(a) **文件債修正**（emergency stop SOP 寫清、reactive_stop 4-mode 與文件對齊，hardening P3-4，**doc 可凍結期先做**）；(b) `/lock/emergency` 來源治理（latched + 受信任節點，MOT-10，**post-6/18**——動安全鏈）；(c) demo-preflight 加「遮 LiDAR 驗 `/cmd_vel_obstacle` 發 0」檢項（碰 `.claude/skills/`，凍結面，排 G5 後）。
4. **Required data**：發表日 emergency stop 操作 SOP（誰按、按什麼、Go2 連線 vs Damp 的界線）——對齊 nav lane 既有鐵則。
5. **Pure software tasks**：**文件債修正**（CLAUDE.md / `docs/navigation/CLAUDE.md` reactive_stop 4-mode 與實作逐字對照、emergency stop SOP）——doc 不碰凍結三檔可先做。
6. **Jetson tasks**：preflight 新檢項真機跑一次（排 G5 後，碰 demo-preflight skill）。
7. **Go2 HITL tasks**：發表彩排確認 `emergency_stop.py engage` 移動中可靠停 Go2（nav lane 既有鐵則，需 motion）；對齊 ladder **C4** safe-stop（`hardware_proven` `HARDWARE_PROVEN_WITH_LIMIT`）——**注意 emergency stop（操作員主動急停）≠ reactive safe-stop（自動停障）≠ 繞障（C11 `DO_NOT_CLAIM`）**。
8. **Metrics**：`emergency_stop.py engage` 移動中 Go2 停（撞 0、暴衝 0，對齊 trackB §1 證據）；文件與 `reactive_stop_node.py` 4-mode 零矛盾；`/lock/emergency` 來源治理 = post-6/18。
9. **Pass/fail threshold**：**文件 PASS = 與 4-mode 實作逐字對照無矛盾**；**HITL PASS = 移動中 engage 可靠停（發表彩排一輪）**。`/lock/emergency` 認證 = post-6/18 不在本份門檻。
10. **Risk**：文件債低風險（純 doc）。`/lock/emergency` 治理動安全鏈（高風險，post-6/18）。**已知坑**：`safety_only=true` 誤設 → `hold_brake` 永久煞車鎖死 nav（GAP3-01），demo 前須確認未誤設。
11. **Rollback**：文件 revert 即回；preflight 檢項 revert 即回；`/lock/emergency` 治理（post-6/18）獨立 PR revert。
12. **Before Monday？ no（HITL/preflight）/ doc 部分 maybe**：文件債修正（doc）可凍結期先做（不碰凍結三檔）；preflight 檢項碰 `.claude/skills/`（凍結面）排 G5 後；`/lock/emergency` 治理 post-6/18。整體標 no（主體需 HITL/凍結解除）。
13. **進 6/18 runtime？ maybe**：emergency_stop.py **已是 runtime 既有**（發表必用，nav lane 鐵則）——本節不新增 enforced 行為到 runtime，只確認可靠 + 修文件債。`/lock/emergency` 認證收斂進 runtime = post-6/18（no）。故「現役急停 maybe 確認、認證收斂 no」。

---

## §3 任務清單（task_type + tests + HITL checklist + rollback）

> 凡與 Lane 5 機制重疊者，本份**不重做實作**，只列「flip 決策 / 驗收 / rollback」任務。Lane5 task 編號為機制權威。

| Task | sub-cap | task_type | 內容（決策/驗收層，非重做機制） | tests / 驗證指令 | HITL checklist | rollback |
|---|---|---|---|---|---|---|
| **AS-1** | §2.8 route_id | pure_software | 確認 Lane5 T5S-2 消毒覆蓋 read+write 兩路徑（log_pose `_append_waypoint` 行 101 / route_runner `_load_route` 行 216）；grep 既有 route_id/name 確認無被白名單拒字元 | `cd nav_capability && python3 -m pytest test/ -q`（消毒單測）；`grep -rE '"route_id"|"name"' runtime/nav_capability/` | 無（純軟體） | revert PR（合法輸入零行為差） |
| **AS-2** | §2.4 blacklist | pure_software | 確認 Lane5 T5S-1 blacklist 分支從 pawai_contracts 讀 BANNED（1030/1031/1301）、StopMove 1003 永放行、off byte-identical | `python3 -m pytest go2_robot_sdk/test/test_robot_control_service.py -q`（11 條既有零改 + 新增 filter 條目） | blacklist-on 一輪 Go2 動作回歸（零誤殺，併入 §2.3 回歸） | param 切 `off`（byte-identical） |
| **AS-3** | §2.9 smoke | pure_software | 擴充 `security_smoke.sh`：nav 端點（`/api/nav/start`、`/api/nav/initialpose`）無 token → 401；`/api/gesture_enabled` 無 token → 401；每項標 finding | `bash -n scripts/security_smoke.sh`；真機 `HOST=127.0.0.1 PORT=8080 GATEWAY_AUTH_TOKEN=... scripts/security_smoke.sh` | 真機跑一輪 exit 0（HITL #2） | 新斷言 revert 即回 |
| **AS-4** | §2.1 auth flip | mixed | T5S-8 auth-on 彩排決策驗收（Studio 全流程 + CLI probe + smoke 全綠 → B-6 可選 on）；本份只定門檻與紀錄，不翻 | T5S-3 wiring 單測（無 token header 不帶=現行為）；彩排 = security_smoke + Studio 全流程 | HITL #2（6/15 晚）：Studio 按鈕/push-to-talk/video/nav panel/Evidence 全綠 | env 翻回 default-off（S0-2 已驗 byte-identical） |
| **AS-5** | §2.2 foxglove | mixed | B-5 決策驗收：若發表不開 Foxglove 且 initialpose 可走 Studio → 降權（單獨 PR，碰凍結腳本逐改知情）；否則 post-6/18 | 降權後：Foxglove 看 topic/image OK、publish `/cmd_vel` 拒；遷工作流：Studio 設 pose → AMCL `Setting pose` log | HITL：降權後驗證 + （若遷）initialpose 實機（對齊 ladder C7） | 拿掉 capabilities 參數一行（PR revert） |
| **AS-6** | §2.3 whitelist | jetson_needed | whitelist-on 動作回歸決策（誤殺風險評估，發表預設 off）；本份定門檻不翻 | whitelist 單測（內放行/外拒/StopMove 永放行/rate limit 不擋 1Hz dedupe） | HITL：demo 動作全流程零誤殺 + banned 拒 log | param 切 `off` 或 `blacklist` |
| **AS-7** | §2.10 emergency | go2_motion_needed | 文件債修正（CLAUDE.md / `docs/navigation/CLAUDE.md` reactive_stop 4-mode 對齊、emergency SOP）— **doc 可凍結期先做**；preflight 檢項排 G5 後 | 文件與 `reactive_stop_node.py` 4-mode 逐字對照；`docs/navigation/CLAUDE.md` 27 cases 對齊（修舊數 17） | 發表彩排：移動中 `emergency_stop.py engage` 可靠停（撞 0） | 文件 revert |
| **AS-8** | §2.5/2.6/2.7 | research_only | 三 spec 落地（nav action auth 模型 / DDS isolation + SROS2 評估 / cmd_vel-mux 收斂）——**全 post-6/18，本份只確認 spec 在 Phase4 有歸屬、不寫 code** | spec review（含根因前置 + HITL 升級條件） | 無（不實作） | N/A |

---

## §4 Pure software vs Jetson vs Go2 HITL 三桶分類

### 桶 1：Pure software（WSL，可 AFK，before_monday 可做）

- **§2.8 route_id sanitize**（AS-1）— proven，bugfix，可進 runtime。
- **§2.4 blacklist 機制**（AS-2 軟體部分）— proven，單測封閉。
- **§2.9 security_smoke 擴充**（AS-3 腳本部分）— proven，`bash -n` 驗。
- **§2.1 gateway token wiring**（AS-4 前端/CLI 軟體部分，T5S-3）— 機制可週末，**flip 不可**。
- **§2.10 文件債修正**（AS-7 doc 部分）— 不碰凍結三檔可先做。
- **§2.5/2.6/2.7 spec 草擬**（AS-8）— research_only，純文件。

### 桶 2：Jetson needed（無 Go2 motion，需真機環境）

- **§2.1 auth-on 彩排**（AS-4，T5S-8）— Studio 全流程 + smoke（HITL #2）。
- **§2.9 security_smoke 真機跑**（AS-3）— 需活 gateway。
- **§2.2 foxglove 降權驗證**（AS-5）— Foxglove 仍可看、不可 publish。
- **§2.6 DDS 接線回歸**（AS-8）— post-6/18，Go2↔Jetson 全鏈路（含 Go2，列此因主體是 Jetson 配置）。

### 桶 3：Go2 motion needed（需 Go2 連線 + 動作回歸，Roy 在場）

- **§2.3 whitelist-on 動作回歸**（AS-6）— WebRTC 不可斷，全動作序列零誤殺。
- **§2.4 blacklist-on 確認**（AS-2 HITL）— 一輪動作回歸（低風險）。
- **§2.5 nav action auth**（AS-8）— post-6/18，motion 回歸。
- **§2.7 cmd_vel/mux 收斂**（AS-8）— post-6/18，**必排完整 nav lane 回歸**。
- **§2.10 emergency stop 彩排**（AS-7 HITL）— 移動中 engage 可靠停。
- **§2.2 initialpose 遷移實機**（AS-5，若降權前置）— nav stack 在跑（對齊 ladder C7）。

---

## §5 Metrics / Pass-fail threshold 總表

| sub-cap | metric | PASS threshold | FAIL → 動作 |
|---|---|---|---|
| §2.1 auth flip | Studio 全流程操作 + 401/403 | 彩排零中斷 + smoke 3 項 HTTP 綠 | 發表 default-off |
| §2.2 foxglove | publish `/cmd_vel` 拒 + 可視化正常 | EXP-02 封閉 + demo smoke 綠 + （若需）Studio initialpose 過 | post-6/18 保留 Foxglove |
| §2.3 whitelist | demo 動作放行 + banned 拒 | 動作零誤殺 + banned 拒 log + StopMove 永放行 | 切 blacklist 或 off |
| §2.4 blacklist | 3 條 BANNED 拒 + 其餘放行 | 單測全綠 + off byte-identical + HITL 零誤殺 | param 切 off |
| §2.5 nav auth | 未授權 send_goal 拒 | post-6/18 定義 | post-6/18 |
| §2.6 DDS | 未列 Peers 主機進不了 bus + 全鏈不斷 | post-6/18 定義 | post-6/18 |
| §2.7 cmd_vel/mux | 裸 cmd_vel 不收 + nav 鏈不變 | post-6/18 定義（隔離 mux 先驗） | post-6/18 |
| §2.8 route_id | 惡意拒 / 合法過 | 單測全綠（含 URL-encoded） | revert |
| §2.9 smoke | HTTP 斷言 + finding 可追溯 | `security_smoke.sh` exit 0 + 真機一輪 | 修斷言 |
| §2.10 emergency | 移動中 engage 可靠停 + 文件對齊 | 撞 0 + 4-mode 文件零矛盾 | 文件 revert / 確認未誤設 safety_only |

> **nav 能力 metric 對齊 ladder**（本份不重定義，引用）：safe-stop = C4 `HARDWARE_PROVEN_WITH_LIMIT`（danger 停 0 撞 0 暴衝，trackB §1）；短距 = C1 0.3m `reached actual=0.270m` / C2 0.5m `NEEDS_RETEST`（n=3 未過不單獨宣稱）；initialpose = C7 `HARDWARE_PROVEN_LOW_SAMPLE`。

---

## §6 Rollback 總表

| sub-cap | rollback 機制 | 退回後狀態 | 退回成本 |
|---|---|---|---|
| §2.1 auth flip | env-gated（S0-2 auth.py 開關） | default-off = byte-identical（已驗） | 秒級（一個 env） |
| §2.2 foxglove | 拿掉 `capabilities`/`address` 參數一行 | 原 foxglove 行為（可 publish） | PR revert（一行） |
| §2.3 whitelist | param 切 `off`/`blacklist` | off=byte-identical / blacklist=現狀+拒3條 | 秒級（param） |
| §2.4 blacklist | param 切 `off` | byte-identical | 秒級（param） |
| §2.5 nav auth | 不實作（spec only） | N/A | N/A |
| §2.6 DDS | `unset CYCLONEDDS_URI` + ROS_DOMAIN_ID 改回 | 原 DDS 行為（舊值記 school_demo.env 註解） | unset env（post-6/18） |
| §2.7 cmd_vel/mux | 拓撲變更前 tag + PR revert | 原 mux 行為 | tag revert（post-6/18） |
| §2.8 route_id | PR revert | 原行為（但合法輸入無差） | revert（應不需要） |
| §2.9 smoke | 新斷言 revert | 原 3 項斷言 | revert |
| §2.10 emergency | 文件 revert / 確認 safety_only 未誤設 | 原文件 / 現役急停 | revert |
| **全域** | tag `post-demo-refactor-baseline-2026-06-10`（`b1f0bc4`）+ `demo-2026-06-snapshot` | baseline | git checkout |

> **發表日預設姿態**：所有 enforcement flip 維持 **off**，除非對應 HITL 全綠 + Roy 點頭（B-5/B-6）。唯一可確定進 runtime 的 enforced 變更 = §2.8 route_id（bugfix，byte-identical）。

---

## §7 決策表（before_monday + enter_6/18_runtime + 理由）

| sub-cap | 分級 | before_monday | enter 6/18 runtime | 理由 |
|---|---|:---:|:---:|---|
| §2.1 gateway auth flip | needs_hitl | maybe | maybe | wiring 可週末（proven 子工作）；flip 需 B-6（6/15-16）+ T5S-8 彩排全綠；master B-4「不換」精神 |
| §2.2 foxglove 降權 | needs_hitl | no | maybe | 碰凍結腳本 + 需 B-5（6/15）+ initialpose 替代驗證；發表不開 Foxglove 才降權 |
| §2.3 webrtc whitelist | needs_hitl | no | no | whitelist 誤殺風險高（漏 api_id=動作死），需完整 Go2 動作回歸；發表維持 off |
| §2.4 forbidden blacklist | proven | yes | maybe | 機制純軟體可週末；低風險縱深防禦，HITL 零誤殺 + Roy 點頭可 maybe 進發表 |
| §2.5 nav action auth | research_only | no | no | interface 級 = 全鏈 rebuild，post-6/18（Phase4 T4A-5①） |
| §2.6 DDS isolation | research_only | no | no | 動 Go2 通訊鏈最危險，post-6/18（Phase4 T4A-3）；範本入庫不接線 |
| §2.7 cmd_vel/mux | research_only | no | no | 動 nav 安全鏈本體，需完整 nav lane 回歸，post-6/18（Phase4 T4A-6） |
| §2.8 route_id sanitize | proven | yes | yes | 純軟體 bugfix，合法輸入 byte-identical，無不修理由 |
| §2.9 security smoke | proven | yes | n/a | 測試工具不進 runtime；是 flip 驗收前提 |
| §2.10 emergency policy | needs_hitl | no | maybe | doc 可週末（不碰凍結三檔）；現役急停 maybe 確認；`/lock/emergency` 認證 post-6/18 |

---

## §8 需 Roy 拍板的 open decisions

1. **B-6（gateway auth flip）**：發表日 auth-on 還是 default-off？前置 = T5S-3 wiring 完成 + T5S-8 彩排（HITL #2）全綠。**本份建議**：彩排全綠才 on，否則 default-off 進發表（master 預設）。需 Roy 定 token 發放流程（A-3）。
2. **B-5（foxglove 降權）**：發表日是否需要現場 Foxglove？若不需 + initialpose 已能走 Studio nav panel（`/api/nav/initialpose` 已存在，需實機驗 AMCL 收 pose）→ 降權；否則 post-6/18。**本份標已知衝突點**：降權斷 nav initialpose-via-Foxglove 工作流。
3. **§2.4 blacklist 是否進發表 runtime**：低風險縱深防禦（driver 拒 3 條 BANNED）。HITL 動作回歸零誤殺後，Roy 是否點頭翻 enforced（blacklist 模式）？對外可講「driver 層已擋危險 api_id」。**vs** 維持 off + 講「機制已入庫」。
4. **webrtc filter 完整 api_id 清單**：whitelist 模式需 demo+nav 用到的完整 api_id（sit/stand/hello/stretch/wiggle_hip/balance_stand/Megaphone 4001-4004/StopMove 1003…）。**需 Roy 指認 / 從動作序列實測**——漏一個即誤殺。即使不翻 whitelist，blacklist 也需確認 3 條 BANNED 不在 demo 動作中（已知不在）。
5. **DDS 真實 interface 名 + Peers 白名單**：`cyclonedds-template.xml` 占位 `eth0` / `192.168.123.161` / `192.168.123.x` 需替換為真實 Jetson-to-Go2 interface 與可信 participant 清單（post-6/18 接線前）。**需 Roy 指認**。
6. **emergency stop 文件債修正範圍**：CLAUDE.md「`safety_only=true` 必須用於 mux 模式」過時宣稱（與腳本 `mode:=progressive` 矛盾、會 promote `hold_brake` 鎖死 nav）。doc 修正可凍結期先做——Roy 是否授權現在改 CLAUDE.md / `docs/navigation/CLAUDE.md`（含 reactive_stop 27 cases 對齊舊數 17）？
7. **post-6/18 三 research spec 排期**：nav action auth（§2.5）、DDS/SROS2（§2.6）、cmd_vel-mux（§2.7）全在 Phase4 有歸屬。本份確認不偷跨進發表前——Roy 確認排期（master G5 解凍後）。

> 本計畫所有「修法」均為設計建議，未實作、未測試（READ-ONLY 審計基礎，且本份只寫計畫）。實作時走既有 TDD + 實機回歸流程，enforcement flip 嚴格依 Lane5 六步硬順序（機制 → 測試 → dry-run → CLI smoke → Jetson smoke → secure-default flip），每步逐項 Roy 拍板，凍結期不翻任何 enforcement。
