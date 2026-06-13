# PawAI v2 Aggressive Pre-6/18 — Master Plan

> **日期**：2026-06-13（六）　**狀態**：PLANNED — 待 Roy 審核，審核通過前不實作
> **性質**：v2 套件的**策略修訂層**。承接 [`2026-06-11-pawai-system-refactor-v2-master.md`](2026-06-11-pawai-system-refactor-v2-master.md)（北極星、依賴閘門 G1-G8、決策登記簿 A-1~A-14 持續有效），把「6/18 前保守 freeze」改為「6/18 前 aggressive refactor + 每刀 checkpoint/tests/rollback」。
> **統領六份 lane plan**：
> [Lane 1 Brain ISM Staged Enable](2026-06-13-lane1-brain-ism-staged-enable-plan.md) ·
> [Lane 2 Studio Evidence Center v2](2026-06-13-lane2-studio-evidence-center-v2-plan.md) ·
> [Lane 3 CLI v2 完整化](2026-06-13-lane3-cli-v2-completion-plan.md) ·
> [Lane 4 Vision Benchmark / Model A-B](2026-06-13-lane4-vision-benchmark-model-ab-plan.md) ·
> [Lane 5 Robot Control / Security Hardening](2026-06-13-lane5-robot-control-security-hardening-plan.md) ·
> [Lane 6 Navigation / Obstacle Avoidance v2](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)

## 命名消歧（全套件適用，繼承 v2 master）

| 名稱 | 指什麼 |
|---|---|
| **系統重構 Phase 1-5** | v2 套件大階段（Phase 1 + Phase 2 pre-6/18 已完成） |
| **Lane 1-6** | 本 aggressive 套件的六條並行工作線（本文件 §3）；Lane 5 = 控制面**安全**（誰能命令）、Lane 6 = 導航**能力**（nav 能做什麼），兩者明確分界 |
| **ISM Phase 0-3 / staged enable 2a-2g** | `interaction_state.py` 的實作階段（ISM plan §5-§8）；Lane 1 = 把 **2a-2d** 提前到 pre-6/18 |
| **安全 hardening P0-P3** | hardening plan 的修補優先級標籤 |

內文一律寫全名，禁止裸寫「Phase N」。

---

## 1. North Star

### 北極星（不變，引用 v2 master）

> **把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台。**
> Perception Nodes → Perception Router → ISM → Policy + Safety Layer → Skill Executor → Trace + Evidence；三支撐 = PawAI CLI v2 / PawAI Studio v2 / pawai_contracts。

### 策略修訂：為什麼現在可以 aggressive

| 舊風險模型（6/11 凍結表） | 新風險模型（6/13 起） |
|---|---|
| demo 還沒錄完 → 任何行為變更都可能毀掉唯一交付 | **demo 影片已全部錄完**（S1-S5，tag `demo-2026-06-snapshot`）→ 最壞情況 = 發表日放影片，交付保底 |
| 6/18 前 = 只准 additive-only 預設關 | 6/18 前 = **可做 flag-gated 行為變更**，條件：每刀有 checkpoint、tests、rollback、HITL 驗證 |
| ISM staged enable 全部 post-6/18（G5 後） | ISM staged enable **2a-2d 提前**；2e/2f/2g 仍 post-6/18 |
| 控制面 hardening 全段 post-6/18 | **機制先行**（env/param-gated 預設關 = byte-identical）提前；enforcement flip 仍逐項 Roy 決策 |

### 6/18 前要衝到的狀態（目標圖像）

1. **Brain**：ISM 2a-2d 接管（demo_phase / confirm 非黑洞 / executing watchdog / speaking chokepoint），`ism_enabled` 一鍵可退 legacy——發表時可以講「狀態機已部分上線、黑洞與卡死有 watchdog 自癒」且有 trace 證據。
2. **Studio**：Evidence Center 能回答「為什麼沒反應」——session list + decision timeline + suppressed 原因（中文）+ 報告匯出。
3. **CLI**：`pawai smoke vision|object|nav-static|full` + `pawai face delete` + status 顯示 brain runtime 狀態（shadow 是否開著）。
4. **Vision**：W1-W5 離線 spike 全跑完、有數據；上機矩陣日視 Roy 排程（可 post-6/18）；**runtime 模型/參數 6/18 前不換**。
5. **Robot Control**：`/webrtc_req` whitelist 機制入庫（預設關）、gateway token wiring 完成（flip 只剩翻 env）、route_id 消毒與 CLI 注入修補完成；最危險的 enforcement（DDS、mux、foxglove）逐項待 Roy 決策或 post-6/18。
6. **Navigation**：capability ladder + proven table 成文；poses/routes 恢復且有備份迴路；短距 0.3/0.5/1.0m 有 n=3 可靠性數據；拒絕有可讀理由；短 route demo（= 固定路線巡邏 prototype v0）有證據或誠實標未排到；fusion / patrol v1 / approach person 三條研究 spec 落檔（**不寫 code**）。
7. **不變的底線**：demo snapshot forbidden claims 持續有效；main 永遠可部署；**6/17（三）= 回穩日硬 checkpoint**（見 §5）。

**誠實的完成定義（先說清楚）**：目標是 6/18 前完成 PawAI v2 第一輪 aggressive upgrade，把 Brain / Studio / CLI / Vision / Security / Navigation 推到**目前時間內可達的最高版本**——不是「全部完成」。其中**導航避障是高風險項，必須用 capability ladder 管理，不承諾一次變成完整自主巡邏**；reactive_stop 是 safe-stop（停下等待）不是繞障，這個區別寫進所有對外措辭。

### 不變的紀律（每刀必備）

- 每刀小 PR、CI 綠、紅綠驗證才 merge；行為變更一律 flag-gated 且**預設 = 現行為**；翻 default 是獨立 PR。
- 觀測類與政策類永不同 PR；搬家與行為變更分開 PR。
- 失敗就 rollback（flag-off 或 revert），不硬留、不帶病前進。
- 硬體能力宣稱必過 HITL gate。

---

## 2. Current State（2026-06-13 早，全部有真機證據）

**系統 Phase 1 Foundation：已完成、地基封閉**（closure smoke 9/9，[`closure report`](../../runbook/2026-06-11-refactor-foundation-closure-report.md)）：CI guardrails（PR #143-#149）、CLI audited deploy + healthcheck hard-gate（#151/#155/#156）、pawai_contracts 單源（#152）、perception_router 預設 True（#153）、`/brain/trace` + decision_id（#154）、S0-1/S0-2 安全機制層（#157/#158）、ISM Phase 0 純模組（#159）。

**系統 Phase 2 pre-6/18：已完成、真機驗收 Roy 10 步全綠**（[`checkpoint report`](../../runbook/2026-06-12-phase2-pre618-checkpoint.md) §8）：

| 資產 | 現狀 |
|---|---|
| ISM shadow（#160） | `ism_shadow_enabled` runtime 可切；6 個接點（emit propose / suppressed evaluate / skill_result / confirm / TTS edge+watchdog tick / operator reset）；11 條 parity + 6/9 黑洞重演測試；**soak 已開**（⚠ demo 重啟歸 False）；已收到 legacy/ISM 分歧樣本（legacy `attention_engaged` 擋、ISM accept） |
| Evidence first slice（#161） | gateway `trace_store.py`（JSONL 落盤 + 20MB rotation + 留 20 sessions + kill-switch）；`GET /api/trace/export`（redacted 預設 / full 無 auth 403 / since 過濾）；前端 Suppressed viewer（cap 50 + shadow badge）；A-4 PII / A-11 export auth 已 RESOLVED 落地 |
| CLI 第二刀（#162） | `pawai smoke brain`（5/5 真機綠）、`pawai evidence pull`、structured errors、conftest 網路封鎖（173 tests ~0.7s） |
| 真機修掉 4 bug（#163-#166） | smoke SSH env / 凍結檔 ASR glob（stt 長期死因）/ tts pub race / **deploy `--delete` 轟 runtime/**（excludes 已補） |
| 測試基數 | contracts 11 / IE 320 / gateway 93 / CLI 173 / 前端 vitest 16 + tsc 乾淨 |

**`ism_enabled` 不存在**（staged enable 零開工，by design）；19 個 `_suppressed` 早退零刪除；nav `named_poses`/`routes` 已被歷次 deploy 清掉待 Roy 重錄。

---

## 3. Remaining Lanes（六條，可並行）

| Lane | 一句話 | 風險 | 對 6/18 價值 | plan |
|---|---|---|---|---|
| **1 Brain ISM Staged Enable** | ISM 從 shadow 接管 2a demo_phase / 2b confirm 非黑洞 / 2c executing watchdog / 2d speaking chokepoint；2e/2f/2g 留 post-6/18 | 中（flag-gated 行為變更） | 高：解搶話/黑洞/卡死，發表可講「狀態機上線」 | [lane1](2026-06-13-lane1-brain-ism-staged-enable-plan.md) |
| **2 Studio Evidence Center v2** | session list + decision timeline + suppressed 中文原因 + session report 匯出 | 低（additive） | 高：發表展示「為什麼沒反應」可被看見 | [lane2](2026-06-13-lane2-studio-evidence-center-v2-plan.md) |
| **3 CLI v2 完整化** | smoke vision/object/nav-static/full、face delete、status 補 brain 狀態 | 最低（零 runtime 行為） | 高：上機人為錯誤防線 + 發表日 shadow 開關可見 | [lane3](2026-06-13-lane3-cli-v2-completion-plan.md) |
| **4 Vision Benchmark / Model A-B** | W1-W5 WSL spike 全開跑；上機矩陣日 Roy 排程；runtime 換模 6/18 前禁 | spike 零風險；上機日中風險（須還原） | 中：數據在手，發表講能力邊界有依據 | [lane4](2026-06-13-lane4-vision-benchmark-model-ab-plan.md) |
| **5 Robot Control / Security Hardening** | **誰能命令**：機制先行（webrtc whitelist / gateway token wiring / 消毒 / pickle→npz）；enforcement flip 逐項 Roy 決策；DDS/mux post-6/18 | 機制低；enforcement 高 | 中：控制面收斂開始，不破 demo | [lane5](2026-06-13-lane5-robot-control-security-hardening-plan.md) |
| **6 Navigation / Obstacle Avoidance v2** | **nav 能做什麼**：capability ladder + poses/routes 恢復 + 短距 n=3 重驗 + rejection reason + 短 route demo（巡邏 prototype v0）+ fusion/patrol/approach spec（不寫 code） | 軟體低；HITL 中（全 motion、有中止手段） | 高：nav 是大功能——恢復能力、講清楚邊界、demo 段有三層 fallback | [lane6](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) |

不做：Website / Presentation Integration lane（明確排除）；簡報製作不在本套件。

---

## 4. Execution Strategy

- **分工**：Fable 審 plan、拆 task、審 Codex 結果；**Codex 實作**（一次一 task、每 task 一 commit、TDD 紅綠）；Roy 拍板決策 + HITL 驗收。
- **流程**：Roy 審本套 plan → 通過後 Fable 依 lane plan 的 task list 逐刀叫 Codex → 每 PR：CI 綠 + 紅綠驗證 + Fable review（Linus 風格）→ admin rebase merge → 該驗真機的排進 HITL session。
- **每刀 PR 小而可退**：單 PR 單主題；行為變更必帶 flag（預設 = 現行為）；revert 任一 PR 不需連動其他 PR。
- **每刀都有測試**：新行為先紅後綠；既有測試（IE 320 / gateway 93 / CLI 173 / contracts 11）一條不刪、斷言不弱化。
- **失敗就 rollback**：HITL 驗不過 → flag-off（runtime param / env，秒級）；結構性失敗 → revert PR；main 紅燈 = 停新刀先修復。

---

## 5. Weekend Execution Queue（6/13 六 → 6/18 四）

### 分類總表（**執行授權邊界**：Roy 不在場時只准做第一列；第二列需 Roy 授權 deploy 時段；第三列 Roy 不在**一律不做**）

| 類型 | 可做 | **不可宣稱** |
|---|---|---|
| **AFK pure software（WSL）** | Lane 3 全部 P0/P1；Lane 2 全部 P0/P1；Lane 1 各 stage TDD 實作 + parity 測試（flag 預設 off）；Lane 4 W1-W5 harness/spike（W2 需 Roy 素材）；Lane 5 機制層（whitelist 機制 / token wiring / 消毒 / CLI-01 / pickle→npz——**全部 default-off**）；Lane 6 純軟體面（ladder/claim 文件、reason 分流、covariance probe、orphan 修、resume_policy 防呆、三條 spec、evidence pull 納 nav runtime）；全部文件/docs | **不可說 HITL 通過**、不可說「功能完成」——只能說「code merged + 單測綠，待真機驗證」 |
| **Jetson-only（不需 Go2 motion）** | deploy / colcon build / trace 觀測 / smoke（static）/ Lane 2 瀏覽器驗證 / Lane 5 auth-on 走查、face npz 重訓 / Lane 1 感知流 smoke | **不可說 Go2 motion 安全**——Jetson 綠 ≠ 機器人行為驗證 |
| **Go2 HITL（Roy 在場才做）** | Lane 1 2b/2c（wiggle、卡死重演）；Lane 4 上機矩陣日；Lane 5 whitelist-on 動作回歸；Lane 6 HITL matrix N1-N8（nav / safe-stop / patrol / stop-resume——與 brain lane 8GB 互斥，需專屬時段） | **Roy 不在不可做、不可預跑、不可「先試一下」**；做完才能把 proven table 對應格升級 |

**Roy 時段預算（稀缺資源，先講清楚）**：固定兩個晚間 HITL（#1、#2，各 ~2h，demo lane）＋**兩個可選大時段**——Lane 4 上機矩陣日（B-3，半天～全天）與 Lane 6 nav 場測（B-9，~半天）。四天內兩個大時段都排會非常硬；**建議至多選一個排 6/15-16、另一個 post-6/18**（nav 場測對 6/18 的直接價值較高：poses 不重錄則 route/goto_named 全空轉、nav 段只能走影片 fallback）。

### 日程（建議，Roy 可改）

| 日 | AFK（Codex 串行，Fable review） | Roy（晚間 HITL / 決策） |
|---|---|---|
| **6/13 六** | Roy 審 plan → 通過後開工：Lane 3 T3-1/2/3（smoke scripts+wiring）、Lane 2 T2-1/2（session API + export 補強）、Lane 5 T5S-2/T5S-4（消毒類 bugfix）、Lane 4 W1（ONNX export+sanity）、Lane 6 T6-1/T6-10（ladder + claim 文件） | 審 plan（/grill-me 可選）；拍板 B-1（staged enable 授權）+ B-9 初步意向（nav 場測排不排）；指認 Lane 4 素材位置（B-8） |
| **6/14 日** | Lane 1 stage 2a + 2b TDD；Lane 2 T2-3/4（timeline + zh 化）；Lane 4 W3/W4/W5；Lane 5 T5S-1（whitelist 機制）/T5S-3（token wiring）；Lane 6 T6-5/T6-6（rejection reason + orphan 修） | W2 拍照素材（半小時）；**HITL #1（~2h）**：deploy → Lane 1 2a/2b 真機 smoke → Lane 3 smoke 真機 → Lane 2 瀏覽器走查 → evidence pull |
| **6/15 一** | Lane 1 stage 2c + 2d TDD；Lane 2 T2-5（report）；Lane 4 W2（vocab replay）；Lane 6 T6-2①②/T6-7①；修前日 HITL 發現 | 拍板 B-3 / B-9 終版（兩大時段至多選一提前）、B-5/B-6（foxglove / auth flip）；**HITL #2**：Lane 1 2c/2d 真機 + Lane 5 auth-on 走查 |
| **6/16 二** | 收尾修補；Lane 1 soak 分歧報告（吃 Lane 2 T2-5）；Lane 4 或 Lane 6 場測資料整理；Lane 6 T6-8 研究 spec | **可選大時段**（B-3 矩陣日 或 B-9 nav 場測 N1-N8，二選一）；或 HITL #3 補驗 |
| **6/17 三** | **回穩日（硬 checkpoint）**：不開新刀。全 flag 設為「發表日狀態」並寫入 checklist；`pawai smoke full` + demo 全流程 smoke；tag `pre-618-checkpoint` | 彩排一輪；逐項確認發表日 flag 狀態（shadow on、ism stages 視驗證結果、auth 視 B-6）；未過驗證的刀 flag-off 或 revert |
| **6/18 四** | — | 期末發表（影片 fallback 在手；shadow soak 開著） |

**回穩日鐵則**：6/17 18:00 起 main 凍結至發表結束；任何 stage 在 6/17 尚未通過 HITL → 該 flag 維持 False 進發表（shadow 照常收數據），不硬上。

---

## 6. Priority Order（先做對 6/18 最有幫助、最不容易炸的）

1. **Lane 3 CLI**（零 runtime 行為、即時減少上機人為錯誤、發表日工具）
2. **Lane 2 Evidence**（additive、發表展示素材、同時是 Lane 1 soak 分析的工具）
3. **Lane 1 ISM 2a→2b→2c→2d**（價值最高的行為變更，嚴格按序、一 stage 一驗）
4. **Lane 6 純軟體面 + 文件**（ladder / claim / rejection reason / orphan 修——低風險高解釋價值；其 HITL matrix 依 B-9 時段）
5. **Lane 4 WSL spikes**（零風險、平行跑；上機日與 runtime 落地獨立決策）
6. **Lane 5 機制層**（預設關 = byte-identical；enforcement flip 最後、逐項 Roy 決策，**DDS / mux / driver cmd_vel 收斂整段 post-6/18**）

兩個 Roy 大時段（Lane 4 矩陣日、Lane 6 nav 場測）獨立於上述排序，由 B-3 / B-9 決定；HITL 風險最高的是 Lane 6 N5/N6（route 單圈、stop-resume）與 Lane 5 whitelist-on 動作回歸，全部有現場中止手段。

依賴：Lane 1 的 soak 分歧報告吃 Lane 2 T2-5；Lane 3 smoke vision/object 吃 Lane 4 的口徑（`capture_baseline_round.py` 既有）；Lane 3 T3-3（smoke nav --static）是 Lane 6 場測的開場儀式；Lane 5 T5S-3 是 B-6 flip 的前置；Lane 6 與 Lane 5 在 nav 上嚴格分界（能力 vs 授權）。其餘檔案面互不重疊、可並行。

---

## 7. Global Rollback Plan

| 層級 | 回滾手段 | 時效 |
|---|---|---|
| Lane 1 | `ros2 param set /brain_node ism_enabled false`（master kill，全 stage 一鍵回 legacy）；單 stage：`ism_stage_2x false` | 秒級 runtime |
| Lane 2 | `PAWAI_TRACE_STORE_ENABLED=0`（落盤退回純 bridge）；新 endpoint / 前端頁各自獨立 revert | env / PR revert |
| Lane 3 | 全部新增命令，獨立 revert，不碰既有 deploy/demo/health 路徑 | PR revert |
| Lane 4 | 全程離線 additive 無需 rollback；上機日結束**必須還原 demo 現役配置**（n@640 / conf 0.35 / 640x480）+ demo smoke；TRT cache 分目錄保證現役 engine 不被覆蓋 | 當日還原 SOP |
| Lane 5 | 每項 env/param-gated 預設關（off = byte-identical 已驗模式）；enforcement flip 後出問題 = 翻回 env；whitelist 誤殺 = param 切 blacklist-only fallback | env / param 秒級 |
| Lane 6 | 軟體項（reason 分流 message-only / orphan 修 / resume_policy 預設=現行為）單 PR revert；HITL 項全部現場可中止（emergency_stop.py engage / demo stop nav cleanup），FAIL 不連坐、proven table 照實標；poses/routes 是 runtime 資料，錄壞重錄、evidence pull 即異地備份 | PR revert / 現場中止 |
| **demo fallback** | 已錄影片（S1-S5）+ tag `demo-2026-06-snapshot` = 發表保底，**任何 lane 都不得使其失效**；發表日 demo 腳本以 6/17 回穩日驗過的 flag 組合為準 | 永備 |
| **main 壞掉** | 停新刀 → revert 到最近綠 commit；最壞退 tag `post-demo-refactor-baseline-2026-06-10`（=`b1f0bc4`）或 6/17 的 `pre-618-checkpoint` | tag |

---

## 8. Global Done Criteria

**Aggressive 第一輪完成（6/17 回穩日判定）**：
1. Lane 3：smoke family + face delete + status 補強 merged、真機綠。
2. Lane 2：session list / timeline / suppressed zh / report 可在瀏覽器走通，回答「為什麼沒反應」不用讀 code。
3. Lane 1：2a/2b merged 且 HITL 過（最低標）；2c/2d merged 且 HITL 過（達標）；任何未過項 flag-off 不影響發表。
4. Lane 4：W1-W5 各有產物與 gate 判定；上機矩陣若跑了則數據歸檔 + Jetson 已還原。
5. Lane 5：機制層 merged（預設關全 byte-identical）；消毒類 bugfix merged；enforcement 狀態 = Roy 決策的明確結果（做了/不做/post-6/18），無懸空。
6. Lane 6：ladder + proven table + claim wording 成文；rejection reason / orphan 修 merged；poses/routes 恢復且有備份迴路（或誠實標未排到 HITL）；三條研究 spec 落檔。
7. `pre-618-checkpoint` tag 打好，demo 全流程 smoke 綠，發表日 flag checklist 成文。

**6/18 前可用的定義**：上述 1/2/7 必達；3 至少 2a/2b；6 的文件面（ladder/claim/spec）必達、HITL 面依 B-9；4/5 盡力。

**各 lane 的現實預期（不喊「全部完成」）**：Brain 完成到 staged enable 的一部分（2a-2d 子集）；Studio Evidence 完成一版可用；CLI 完成一大段；Vision 完成 benchmark 與決策（模型不一定變好——那是數據說了算）；Security 補強控制面（機制層為主）；**Navigation 把能力層級講清楚、恢復 route、做短距/stop-resume 驗證與固定路線巡邏 prototype，但不保證達到「自由巡邏 + 動態繞障」**——nav 永遠用 capability ladder 管理宣稱。

**必須留到後續（post-6/18）**：ISM 2e/2f/2g 與 Phase 3 權威化（G7）；Lane 4 runtime 換模 + contract v2.6；Lane 5 DDS 收斂 / twist_mux 收斂 / nav action interface 級授權 / gateway 簽章；Lane 6 fusion / patrol v1 / approach person 的**實作**（spec 先行）、auto-resume 終局（A-9）、covariance 閘門檻調整；Typer 遷移與 pipx（系統 Phase 5）；dead code 刪除（G7 後）。

---

## 附錄 A：凍結表修訂（aggressive 版）

| 項 | 6/11 凍結表 | 本套件修訂 |
|---|---|---|
| `executive.yaml` / `scripts/start_full_demo_tmux.sh` / `.claude/skills/` | 禁改 | **改為「逐改知情」**：仍以 runtime param / env 為優先手段；確需改檔（先例：#164 Roy 現場授權）必須單獨 PR + demo smoke 全綠 + Roy 點頭 |
| `ism_enabled` | 不存在 / 不翻 | **解凍**：Lane 1 引入，預設 False，staged enable 2a-2d 逐 stage 翻子開關 |
| gateway secure-default flip | 凍結 | 機制 wiring 提前（Lane 5 T5S-3）；**flip 時點 = Roy 決策 B-6** |
| foxglove clientPublish 降權 | 凍結（A-2） | **Roy 決策 B-5**（前置：Studio initialpose 流程已存在） |
| demo snapshot forbidden claims | 持續有效 | **不變**（對外宣稱仍以 HITL 證據為準） |
| 已錄 demo 影片 + `demo-2026-06-snapshot` tag | — | **新增凍結項**：發表 fallback，不可動 |

## 附錄 B：本輪需要 Roy 的新決策（B 系列，與 v2 master 附錄 A 並行）

| # | 決策 | 影響 | 建議 | 時點 |
|---|---|---|---|---|
| B-1 | 授權 ISM staged enable 2a-2d 提前到 pre-6/18（推翻 G5 限制） | Lane 1 全部 | 同意（本套件即為其執行方式） | 審 plan 時 |
| B-2 | source trust enforcement（Studio nav 按鈕會多一步 confirm）提前與否 | Lane 1 / 5 | **post-6/18**（等 gateway 簽章一起做，發表日操作流程不變） | 審 plan 時 |
| B-3 | Lane 4 上機矩陣日：6/15-16 排半天/全天，或 post-6/18 | Lane 4 / Roy 時間 | 視 Roy 體力；不排也不影響其他 lane | 6/15 前 |
| B-4 | 矩陣若有明確贏家，6/18 前允不允許 runtime 換參（如 conf 0.30） | Lane 4 / demo | **不換**（env 切換能力在手即可，發表用現役） | 矩陣日後 |
| B-5 | foxglove clientPublish 降權（demo lane 一行；發表是否需要現場 Foxglove） | Lane 5 / 凍結腳本 | 若發表不開 Foxglove → 降權；否則 post-6/18 | 6/15 |
| B-6 | gateway auth flip：發表日 auth-on 還是 default-off | Lane 5 | wiring 完成 + HITL 全綠才考慮 on；否則 default-off 進發表 | 6/15-16 |
| B-7 | `pawai demo start --with-shadow`（CLI 自動重開 shadow param）要不要做 | Lane 3 | 做（解決「demo 重啟 shadow 歸 False」的發表日坑） | 審 plan 時 |
| B-8 | Lane 4 素材指認：object JSONL 與 demo 錄影的實際路徑 | Lane 4 G3 | 一句話回覆位置即可 | 6/13-14 |
| B-9 | Lane 6 nav 場測時段（HITL matrix N1-N8，~半天）：6/15-16 排，或 post-6/18 | Lane 6 / Roy 時間 | **建議排**（poses 不重錄則 route/goto_named 全空轉、nav 段只能影片 fallback）；與 B-3 至多選一個提前 | 6/13-15 |
| B-10 | 6/18 發表 nav 段形態：live 短距/短 route，或遙控輔助+Studio 證據，或純影片 | 發表腳本 | 依 B-9 結果定（N3/N5 過了才考慮 live） | 6/17 回穩日 |
