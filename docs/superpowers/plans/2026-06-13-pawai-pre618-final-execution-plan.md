# PawAI Pre-6/18 Final Execution Plan（總綱 / MASTER）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 角色分工（全計畫群鐵律）：**Cloud / Fable = planner + reviewer（讀 source、設計、切 task packet、定 tests/rollback/stop-conditions、對抗式查 overclaim/demo-break/safety、整合，不寫 runtime code）；Codex = builder（依 packet 實作、寫測試、跑測試、小 commit/PR、回報 diff+test-result+risk，不擴 scope、不改 runtime-claim，未經 Roy 明確授權＋e-stop 不發任何 Go2 motion）。**
> 本檔 = 六份子計畫的整合總綱，**§2 supersede 所有 source / digest 草稿**，子計畫之 task 不重複、只引用 id。

---

## 1. Executive Summary（一句話）

**6/18 交付 = 一場「連續五幕 live 居家互動 demo」（s1_nav → s2_greet → s3_pose_object → s4_gesture → s5_safety），用穩定化（FLOOR）保證每幕都出得了聲、不開天窗，用 ENHANCEMENT（auto-advance，預設 OFF、逐幕）讓它「看起來自動」；不是把所有研究端到端展全，也不是預錄影片當主體——影片只是四階 rollback 的最後一階。**

> 全計畫群是「**live 五幕可靠性工程**」，不是「all-research 展示」。誠實底線：AFK 完成只能說「code merged + 單測綠（needs-HITL）」；只有 Roy 在場真機 HITL 過才算 `proven`。對外 nav claim 一律綁 [`nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md) S1-S8 / F1-F10。

---

## 2. 六份子計畫索引（本總綱 supersede 全部 source docs）

| Plan ID | 標題 | 負責問題 | 檔案 |
|---|---|---|---|
| **plan1** | Runtime Layout / Co-run Profiling | **Q2** S1 runtime layout 決策閘（NO-MOTION 三配置量測） | [`2026-06-13-plan1-runtime-layout-corun-profiling.md`](2026-06-13-plan1-runtime-layout-corun-profiling.md) |
| **plan2** | Demo Conductor / Auto-Advance / Manual Floor | **Q3/Q6** 場景指揮（FLOOR 詞彙/清理/控制 + ENHANCEMENT auto-advance） | [`2026-06-13-plan2-demo-conductor-auto-advance.md`](2026-06-13-plan2-demo-conductor-auto-advance.md) |
| **plan3** | Online / Offline / LLM-Hybrid Speech | **Q5** 三層語音（非阻塞）+ offline fallback + canned 表 | [`2026-06-13-plan3-online-offline-llm-hybrid-speech.md`](2026-06-13-plan3-online-offline-llm-hybrid-speech.md) |
| **plan4** | Operator Controls / Studio / Runbook | **Q3/Q6** 控制面（Studio hidden 五幕鈕 + offline toggle）+ 操作員 runbook | [`2026-06-13-plan4-operator-controls-studio-runbook.md`](2026-06-13-plan4-operator-controls-studio-runbook.md) |
| **plan5** | Post-Refactor HITL Closure / Rehearsal | **Q6** HITL 收束 + 6/17 彩排總閘 + 唯一 runtime bugfix（S8）+ P1 offline 證據 | [`2026-06-13-plan5-post-refactor-hitl-rehearsal.md`](2026-06-13-plan5-post-refactor-hitl-rehearsal.md) |
| **plan6** | Navigation Safety / S1 Fallback | **Q1/Q2** S1 幕 nav 行為 + 三層 fallback + 撞牆根因 no-motion 診斷 | [`2026-06-13-plan6-navigation-safety-s1-fallback.md`](2026-06-13-plan6-navigation-safety-s1-fallback.md) |

---

## 3. 鎖定決策（Q1–Q6，全計畫群共用憲法）

### Q1 — 交付形式：**live 連續五幕**
6/18 = live 連續五幕（s1_nav → s2_greet → s3_pose_object → s4_gesture → s5_safety）。**預錄影片是 LAST-RESORT fallback，不是交付主體**。保留 live 順序流框架；不講「全自動 live demo」。

### Q2 — S1 runtime layout：**不預設換不換 stack，由 plan1 NO-MOTION profiling 閘決定**
plan1 量三配置（A brain-full / B brain+raw-LiDAR+Foxglove / C brain+full-nav-stack）的 RAM/CPU/GPU/溫度/延遲/topic-Hz，各 3–5 分鐘、**零 motion**。4-branch 決策樹（**每 branch 綁 plan1 §9.2 精確 metric 條件，權威定義在 plan1 §11.1**）：

```
C-CORESIDENT     ← C 配置全 metric=PASS（RAM used <5.5GB 且 headroom ≥0.8GB 且
                    溫度 <80°C 且每 watch topic Hz 在期望 ±20% 且無 node crash）
                  → S1 可免換 stack（仍不用 goto_relative；map/LiDAR/pose 當視覺證據）

B-RESIDENT-LIDAR ← C 任一 FAIL（RAM used >6.5GB 或 headroom <0.8GB 或溫度 >80°C 或
                    topic Hz 偏離 >40% 或 node crash），但 B 全 metric=PASS
                  → brain 常駐 + raw LiDAR/Foxglove + operator-assisted（不跑 nav2/amcl）

A-ONLY-VIDEO     ← B 也任一 FAIL，但 A（brain baseline）全 metric=PASS
                  → S1 live = 第三人稱 + Studio brain only；map/LiDAR 走影片/截圖

BRAIN-FIRST      ← A（brain baseline）本身任一 FAIL
                  → 先修 brain demo，nav 完全不談
```
**無論落哪 branch，S1 都不啟 `goto_relative` 當主線。**「配置 PASS」定義 = plan1 §9.2 全列 PASS 或最多 WARNING 且無 FAIL（任一 FAIL ⟹ 該配置 unstable）。

### Q3 — 控制面：**auto-advance 為主線視覺效果（看起來自動），但交付保證永遠是 manual FLOOR**
auto-advance / guard-based conductor = **MAIN LINE 視覺效果**（enable 時 demo 看起來自動、非手動遙控）。**但邏輯主線 ≠ 交付保證**：6/18 的**交付保證（P0 delivery）永遠是 manual 控制**——Studio 五幕 **HIDDEN 按鈕**（FLOOR，**任何情況不會被停用**）+ `ros2 param set /brain_node demo_phase`（last-resort backup）。換言之：auto-advance 是 per-phase enhancement flag（**預設 OFF**，6/17 彩排逐幕決定是否開），FLOOR manual 與 auto-advance **獨立存在、不互相依賴**——auto 關掉、Studio 掛掉、或 auto 失速時，manual FLOOR 仍 100% 可交付整場 demo。`pawai demo phase` CLI = **post-6/18**。**phase 切換必清** `pending_confirm` / `active_plan` / gesture cooldown，並 trace transition type。
> 一句話：**邏輯上 auto-advance 是主線（讓 demo 好看），交付上 manual FLOOR 是保證（讓 demo 一定出得來）。6/18 絕不押 auto-advance（見 Q6）。**

### Q4 — 失速行為：**C-prime = 快觸發 + canned rescue + skip/影片**，鐵律「never dead air」
每幕 `max_wait_s`：S1 10–20s（operator-arrived）/ S2 3–5s / S3 5–8s / S4 8–10s / S5 3–5s。觸發用「短但可信」信號（face known 0.5–1s → greet；cup/object 0.5–1s → remind；**pose = bonus 非硬依賴**；gesture **僅 S4** 一次高信心 → prompt；safety = keyword/text，**no LLM**）。逾時 → 播該幕 canned；canned/local-TTS 也失敗 → 操作員 hidden skip 或插影片。Trace：`real_trigger` / `timeout_canned_rescue` / `operator_skip` / `video_fallback`。

### Q5 — 語音：**C-plus = LLM-enabled 混合，非阻塞**
Layer1 快 intent/perception 觸發（不等 LLM）；Layer2 LLM 自然回覆（short deadline 內才用：demo beat 1.5–2s 沿用 `chat_wait_ms=1500`；Q&A 4–6s）；Layer3 rule canned fallback，觸發於**任一**：無偵測 / 低信心 / LLM timeout / TTS timeout / 網路斷 / operator fallback / 時間壓力。**Safety 永遠 rule-first，LLM 不能 override**；offline canned = 0s、safety = 0s。Q&A 保留完整 LLM 路徑。**五幕不可寫成純 canned；任一幕不可乾等 15s LLM timeout。**

### Q6 — 建構策略：**分層**
**FLOOR（P0，保證出貨、先做）** = demo_phase 五幕詞彙 + 切換清理 + canned/LLM-hybrid 語音 + Studio hidden 五幕鈕 + `ros2 param set` backup。**這一層獨立就是能跑的 live demo。**
**ENHANCEMENT（`auto_advance_enabled` 旗標，預設 OFF、PER-PHASE，疊在 FLOOR 上）** = auto-advance guards/triggers/timeouts/canned-rescue。**6/17 彩排逐幕決定要不要 enable auto；6/18 絕不押 auto-advance。**
**四階 rollback ladder**：auto-advance → Studio hidden buttons → `ros2 param set` → `demo_phase=all` + 影片。

---

## 4. 合併 P0 / P1 / P2 board（跨六份）

### 4.1 P0 — FLOOR（保證出貨、先做）

| # | Task | Plan | type | 摘要 |
|---|---|---|---|---|
| 1 | T2-1 `PHASE_ALLOWED_KINDS` 擴五幕 + `canonicalize_phase` alias | plan2 | pure_software | 五幕詞彙（alias s2_face/s3_object byte-identical） |
| 2 | T2-2 `_apply_phase_transition` 切換清理 helper + trace | plan2 | pure_software | 清 pending_confirm/active_plan/gesture cooldown |
| 3 | T2-3 `/brain/demo_phase` String subscriber（brain 側契約） | plan2 | pure_software | plan4 hidden 鈕接點；param/topic 共用 `_set_demo_phase` |
| 4 | T1 timeout `openrouter_gemini_timeout_s` 60→6 dataclass | plan3 | pure_software | 消 60s 地雷 |
| 5 | T2 `llm_timeout` 15→6 | plan3 | pure_software | demo 保險絲 |
| 6 | T3 五幕 3-tier canned phrase table | plan3 | pure_software | success/degraded/generic；**台詞 = plan3 §9.3 15 句，待 Roy 6/15 前最遲簽核鎖定（未簽=task blocked，Codex 不得自改措辭，先以 `LOCKED_CANNED` placeholder 實作 dict 結構）** |
| 7 | T4 `offline_mode` 新 param（預設 False=byte-identical） | plan3 | pure_software | LLM 路徑短路 cloud |
| 8 | T5 fallback 觸發擴充 slow/broken/unstable + phase-aware canned | plan3 | pure_software | `_on_chat_timeout` phase-aware |
| 9 | T6 WAV pre-render piper cache 暖機 SOP | plan3 | jetson | offline canned 0s |
| 10 | T8 byte-identical 迴歸測試套件 | plan3 | pure_software | ~955 不退 |
| 11 | P4-1 gateway `/api/demo_phase` publisher+route（reset-before-phase） | plan4 | pure_software | hidden 鈕後端 |
| 12 | P4-2 gateway `/api/offline_mode` publisher+route（預設 OFF） | plan4 | pure_software | offline 切換後端 |
| 13 | P4-3 frontend HIDDEN 五幕鈕 + offline toggle | plan4 | pure_software | 抄 gesture-toggle，掛 dev/hidden panel |
| 14 | P4-5 runbook 開場安全前置 | plan4 | docs | Go2 停穩/nav 清/D435/e-stop/.env CRLF/數 node |
| 15 | P4-6 runbook 五幕六欄 SOP | plan4 | docs | 逐字對 `PHASE_ALLOWED_KINDS` |
| 16 | P4-7 runbook 三洞段（face/confirm/nav）+ Gotcha | plan4 | docs | S2 greet 進場 + sitting bonus + .npz ls + nav FAILED |
| 17 | P4-8 runbook 操作員角色分工 | plan4 | docs | Driver/Trace-Watcher/S5-Trigger |
| 18 | P4-9 runbook CLI 清單 + ros2 param set backup + 平台表 | plan4 | docs | PLANNED CLI 標清楚 + .env CRLF 檢查 |
| 19 | P4-10 runbook 四階 rollback ladder + 誠實底線 + 8GB 交接 | plan4 | docs | — |
| 20 | P4-11 runbook dry-run review | plan4 | pure_software | 發表日前 48h |
| 21 | P4-12 HITL 五幕全流程 + 控制面真機驗 | plan4 | mixed（S1/S4 go2_motion） | needs-HITL→proven 唯一閘 |
| 22 | P4-13 8GB co-run stack 交接決策（消費 plan1） | plan4 | docs | **拆兩階消依賴環**：P4-13-**P0（template，6/14 寫）**＝交接決策樹骨架，S1 stack layout 欄填「TBD — pending plan1 profiling」；P4-13-**P1（fill，6/15 下午）**＝plan1 T5 決策樹輸出後回填實際 branch。P4-11 dry-run（6/16）用回填後的 runbook |
| 23 | T1 profiling harness + parser + 7 pytest + 程序文件骨幹 | plan1 | pure_software | AFK 可做 |
| 24 | T2 配置 A profiling run（brain-full baseline） | plan1 | jetson（no-motion） | branch 4 判讀 |
| 25 | T3 配置 B profiling run（brain+raw-LiDAR+Foxglove） | plan1 | jetson（no-motion） | branch 2 判讀 |
| 26 | T4 配置 C profiling run（brain+full-nav-stack 同跑） | plan1 | jetson（no-motion） | branch 1 判讀（壓力上限） |
| 27 | T5 4-branch 決策樹判讀 + S1 runtime layout 決策表 | plan1 | pure_software/docs | plan6/plan2/plan4 消費 |
| 28 | T5-1 CLI face delete/rebuild 補刪 .npz（B4 修法 spec→Lane3） | plan5 | pure_software | face re-enroll 乾淨 |
| 29 | T5-2 face_db 衛生 + 發表日 re-enroll sim≥0.7 | plan5 | jetson | S2 具名問候前置（先機上 ls） |
| 30 | T5-3 S8 route_id sanitize 驗證收尾（已實作，**勿誤寫成實作**） | plan5 | pure_software/jetson | byte-identical 確認 |
| 31 | T5-6 6/17 彩排總閘 逐幕 auto vs manual + 四級 ladder | plan5 | jetson | 控制面形態決策 |
| 32 | T5-7 五幕全流程彩排 + `pawai smoke full` 綠 + tag pre-618-checkpoint | plan5 | jetson | **6/17 執行的 go/no-go 硬閘**（彩排 6/17、結論決定 6/18 是否上台；main 6/17 18:00 凍結） |
| 33 | NS-0 收場安全（Go2 停穩 + demo stop + 清 nav stack） | plan6 | jetson | 8GB 釋放 |
| 34 | NS-D0 證據回收（evidence pull 當天 [PR1a] + reactive timeline） | plan6 | pure_software | 定量 R1/R2/R3 |
| 35 | NS-D1 T0 TF authority no-motion 診斷（echo /tf_static） | plan6 | jetson（no-motion） | 決定是否做 NS-T0 |
| 36 | NS-T0 gated T0 remediation（移除 go2.urdf map/odom fixed joint） | plan6 | pure_software→jetson | **僅 D1 confirm 才做，有 nav regression 風險** |
| 37 | NS-D2 no-motion 診斷集 D2-D5 SOP 化 | plan6 | jetson（no-motion） | AMCL yaw/yaw-blind/LiDAR 軸/reactive 側向/covariance |
| 38 | NS-5 initialpose yaw 校正 SOP + scan-overlay SOP | plan6 | pure_software/docs | S1 fallback② 操作依據 |
| 39 | NS-6 S1 三層 fallback 決策 + claim wording 鎖定（Roy D-1） | plan6 | pure_software/docs | 決定 S1 演什麼講什麼 |
| 40 | NS-V1 route_id sanitize 回歸覆蓋驗證（ownership plan5） | plan6 | pure_software | byte-identical |

### 4.2 P1 — ENHANCEMENT / UPSIDE（過了才升，6/18 不押）

| # | Task | Plan | type | 摘要 |
|---|---|---|---|---|
| 1 | T2-4 `auto_advance_enabled` per-phase 旗標 + gotcha #1（進幕 known-face greet） | plan2 | pure_software | 預設 OFF；s2 自動開口 |
| 2 | T2-5 gotcha #2（s2 sitting=false/s3 bonus）+ max_wait_s + timeout→canned-rescue + transition-type trace | plan2 | pure_software | never dead air |
| 3 | H-2A auto s2 entry-greet 真機驗 | plan2 | jetson（no-motion） | 前置 face sim≥0.7 |
| 4 | H-2B max_wait 逾時補 canned 真機驗 | plan2 | jetson（no-motion） | IRON RULE never dead air |
| 5 | H-2C s4 confirm 觸發手勢 + Go2 wiggle | plan2 | go2_motion | thumbs_up→OK→wiggle vs 已驗 peace→OK→WeGo |
| 6 | T6 brain cold-start 成本 + 8GB 交接時間 | plan1 | jetson（no-motion） | 現場交接旁白 |
| 7 | T7 `pawai demo mode online\|offline` CLI 契約（給 Lane 3） | plan3 | pure_software | 契約定義 |
| 8 | P4-4 Studio phase chip + offline 指示燈（唯讀） | plan4 | pure_software | 觀眾看「現在第幾幕」 |
| 9 | T5-4 confirm-wiggle HITL（目標 vs 已驗） | plan5 | go2_motion | 台詞不指定手勢 |
| 10 | T5-5 nav motion HITL gate H1→H2→H3（0.3m n=3 0撞） | plan5 | go2_motion | 前置 incident T0 排除 |
| 11 | NS-1 goto 前置 yaw/scan sanity 閘 + nav_ready 三拆 | plan6 | pure_software | additive；旗標關=byte-identical |
| 12 | NS-2 goto 限速/限距 watchdog（治 R2 超衝） | plan6 | pure_software | additive |
| 13 | NS-3 HITL 路徑 fail-closed 前置（zone≠danger + depth_clear） | plan6 | pure_software | additive |
| 14 | NS-4 covariance probe 腳本（含 c[35]）+ 黃帶決策表 | plan6 | pure_software | 量測工具 |
| 15 | NS-7 DriveOnHeading speed-port（speed≥0.45）live-motion option | plan6 | pure_software | wired_only，預設不接 demo |
| 16 | NS-H1 indoor_tight ±18° 安全錐驗證 | plan6 | go2_motion | upside |
| 17 | NS-H2 initialpose 朝向校正一輪（θ_error<5°） | plan6 | go2_motion | upside |
| 18 | NS-H3 短距 DriveOnHeading n=3 全達零撞零超衝 | plan6 | go2_motion | upside |
| 19 | T5-P1a object 杯/瓶/手機混淆 benchmark（supervision offline） | plan5 | pure_software | 證據，不 override demo |
| 20 | T5-P1b gesture 誤觸 ROC + pose sitting precision（offline） | plan5 | pure_software | 證據 |
| 21 | T5-P1c supervision 標註 MP4（offline 證據） | plan5 | pure_software | 證據 |

### 4.3 P2 — DO NOT DO（明確排除，post-6/18 或永不）

| Item | 來源 | 為何不做 |
|---|---|---|
| `pawai demo phase` / `pawai demo mode` CLI 實作 | plan4/plan3 | post-6/18（Q3）；6/18 用 Studio 鈕 + `ros2 param set` |
| live SLAM / autonomous approach Roy / 動態繞障 進 demo 主線 | plan6 | NOT_DEMO_READY；禁 F1–F10 |
| auto-resume（stop→resume 自動衝） | plan6/MEMORY | tight space lunge，禁 demo |
| D435+LiDAR costmap fusion（寫成已完成） | plan6 | 只有 depth_clear fail-closed gate；fusion=research-only |
| full gateway secure-default flip / SROS2 / DDS isolation / Foxglove clientPublish full-cut | plan4/plan6 | route_id sanitize（S8）是唯一 confirmed byte-identical runtime 變更 |
| 任何 plan 依賴 `goto_relative` | 全部 | R1 AMCL-yaw 注入 + R2 超衝 + T0 URDF 衝突 |
| LLM streaming | plan3 | 架構大改，deferred |
| 換主線模型（gpt-5.4-mini / Despina / sensevoice） | plan3 | 6/18 凍結 |
| gesture/pose 門檻改 runtime | plan5 | B-4 鐵律：6/18 前不換 params；ROC 只觀測 |
| fallen / 跌倒 / guardian / emergency-alert | 全部 | `enable_fallen:=false` 永久鎖 |
| 2m 物體 / 可靠顏色 / 19 色 claim | 全部 | overclaim 禁區 |
| 收緊 `phase_allows` unknown→quiet | plan2 | 會改 Lane 1 2a 同函式語義，破 byte-identical |
| P1 supervision/benchmark 上 Jetson runtime | plan5 | 雙 OpenCV 違反 ≥0.8GB 餘量；錄影絕不餵 LLM |

---

## 5. GLOBAL 執行順序（按實際工作流，非技術分類）

> 原則：純軟體 AFK 先行（不阻塞 HITL）→ 收場安全 → no-motion 量測/診斷 → no-motion HITL → motion HITL（Roy+e-stop）→ 6/17 彩排總閘 → 6/18 live。

```
═══ Phase A：純軟體 FLOOR（6/13–6/15，AFK，無硬體，Codex 並行）═══
  A1  plan1-T1   profiling harness + parser + 7 pytest + 程序文件骨幹
  A2  plan2-T2-1 PHASE_ALLOWED_KINDS 五幕 + canonicalize_phase     ← 前置：plan3/plan4/Lane1 都依賴正確詞彙
  A3  plan2-T2-2 _apply_phase_transition 清理 helper + trace
  A4  plan2-T2-3 /brain/demo_phase subscriber + _set_demo_phase    ← FLOOR 完成（已是能跑 live demo）
  A5  plan3-T1/T2 timeout 60→6 / 15→6  + plan3-T8 byte-identical 迴歸骨架
  A6  plan3-T3   五幕 canned table（台詞待 Roy 鎖定）
  A7  plan3-T4   offline_mode param  → plan3-T5 fallback 擴充 phase-aware
  A8  plan4-P4-1 gateway /api/demo_phase（reset-before-phase）     ← 依 A4 契約
  A9  plan4-P4-2 gateway /api/offline_mode                          ← 依 A7 契約
  A10 plan4-P4-3 frontend HIDDEN 五幕鈕 + offline toggle            ← 依 A8/A9 route
  A11 plan5-T5-1 CLI face delete/rebuild 補 .npz（spec→Lane3）
  A12 plan5-T5-3 S8 route_id sanitize 驗證收尾（勿實作）/ plan6-NS-V1 回歸覆蓋
  A13 plan6-NS-D0 evidence pull 定量 [PR1a]
  A14 plan6 軟體 upside（並行，旗標關=byte-identical）：NS-1 / NS-2 / NS-3 / NS-4 / NS-7
  A15 plan2 ENHANCEMENT：T2-4 / T2-5（auto-advance，預設 OFF）
  A16 plan5 P1 offline 證據（並行，WSL 隔離）：T5-P1a / T5-P1b / T5-P1c
  A17 文件：plan4-P4-5..P4-10（runbook 各段）/ plan6-NS-5 / NS-6（Roy D-1）/ NS-D2 SOP

═══ Phase B：收場安全 + no-motion 量測/診斷（Jetson，Roy 在場，零 motion）═══
  B0  plan6-NS-0 / plan1-J-0  收場：Go2 停穩 + pawai demo stop + pkill nav 殘留 + ros2 node list 乾淨
  B1  plan6-NS-D1 T0 TF authority 診斷（echo /tf_static）          ← 最先做的 Jetson 項
  B2  plan6-NS-T0 gated T0 remediation（僅 D1 confirm；改後 smoke 8/8 + tf2_echo 復驗）
  B3  plan6-NS-D2 no-motion 診斷集 D2-D5 SOP 化
  B4  plan1-T2 → T3 → T4  配置 A→B→C profiling（C 是壓力上限，OOM 立即清場）
  B5  plan1-T6 cold-start + 交接時間（順手量）
  B6  plan1-T5 4-branch 決策樹判讀 + S1 runtime layout 決策表       ← plan6/plan2/plan4 消費

═══ Phase C：no-motion HITL（Jetson，Roy 在場）═══
  C1  plan5-T5-2 face_db 衛生 + re-enroll sim≥0.7（先機上 ls 確認真檔名）
  C2  plan5-T5-3 MOT-04 route_id 機上手動驗
  C3  plan2-H-1A/H-1B/H-1C  FLOOR 五幕詞彙/切換清理/subscriber 真機驗
  C4  plan3-H1..H5  timeout/offline_mode/canned+WAV/byte-identical/env-offline 真機驗
  C5  plan2-H-2A/H-2B + plan4-P4-12（S2/S3/S5 段）ENHANCEMENT no-motion 驗

═══ Phase D：motion HITL（Roy 授權 + e-stop；T0 排除 + plan1 profiling 允許共存才開）═══
> **序列規則（LOCKED）**：D1→D2→D3（nav motion HITL，**serial、互為前置**，是 S1 live 能力的硬閘）**先做**；
> D4（confirm-wiggle，**無 nav 依賴**）為**獨立分支**，可在 nav 段之外另起 session。
> **若 D1-D4 同 session**：**nav 先（gate S1 能力）、confirm 後（gate S4 能力）**，不交錯（避免 Go2 motion context 混淆）。
> **D1-D3（nav）與 D4（confirm）皆須在 6/17 23:59 前 green** 才進各自幕的 6/18 live；任一未過 → 該幕退 fallback（S1 退遙控/影片、S4 退 peace→WeGo）。
  D1  plan6-NS-H1 indoor_tight ±18° 安全錐                          ← nav serial，前置 T0 排除
  D2  plan6-NS-H2 initialpose 朝向校正（θ_error<5°）                ← nav serial，依 D1
  D3  plan6-NS-H3 短距 DriveOnHeading n=3（0.3m 0撞0超衝）          ← nav serial，依 D2；全過才升 S1 fallback① live
  D4  plan2-H-2C / plan5-T5-4  confirm→Go2 wiggle（失敗退 peace→WeGo） ← 獨立分支，無 nav 依賴；gate S4

═══ Phase E：6/17 彩排總閘 ═══
  E1  plan5-T5-6 逐幕 auto_advance vs manual floor 決策 + 四級 ladder（auto/manual 都彩排）
  E2  plan5-T5-7 五幕全流程彩排 + pawai smoke full 綠 + tag pre-618-checkpoint
      → main 6/17 18:00 凍結（之後不進新 code）

═══ Phase F：6/18 live demo ═══
  F1  P4-5 開場安全前置（runbook §0）
  F2  五幕順序，每幕走 FLOOR 為底、彩排決定的幕開 auto upside
  F3  失速 → 四階 rollback ladder（never dead air）
```

> **硬時間閘（解 plan1↔plan4 runbook 循環依賴）**：
> - **6/15 EOD**：plan1 三配置 profiling CSV 定稿（若 profiling 滑期 → S1 直接採 plan1 §11.1 branch 3「A-ONLY-VIDEO」最保守路徑，**不阻塞 runbook**）。
> - **6/16 09:00**：plan1 T5 4-branch 決策樹 + S1 runtime layout 鎖定；之後 **不得再改 S1 runtime layout**。
> - **runbook 不卡 profiling**：P4-13 P0 template（6/14）先用「S1 stack layout: TBD pending plan1」placeholder 寫成；plan1 結果 6/15 下午回填 P4-13 P1；P4-11 dry-run（6/16，發表前 48h）用回填後 runbook。**P4-13 草稿後不得再改 S1 runtime layout（與上方 6/16 09:00 鎖定一致）。**
> - **跨 plan 端到端閘**：plan4-P4-1 gateway + plan2-T2-3 brain subscriber 必須在 **6/16 前**完成一次 end-to-end 聯測（H-1C），才進 6/17 彩排（T5-7）。

---

## 6. 跨計畫依賴圖（Cross-Plan Dependency Map）

### 6.1 主依賴鏈

```
                 ┌─────────────────────────────────────────────┐
                 │  plan1 NO-MOTION co-run profiling（4-branch）  │
                 └───────────────┬─────────────────────────────┘
        gates ↓ gates ↓                    ↓ gates
  ┌────────────────────┐ ┌──────────────────────┐ ┌────────────────────────┐
  │ plan6 NS-H1/H2/H3   │ │ plan2 s1_nav phase    │ │ plan4 P4-13 8GB stack   │
  │ nav stack 能否共存   │ │ S1 幕呈現(live/證據/   │ │ 交接決策樹               │
  │ → S1 fallback ①/②/③ │ │ 影片)                  │ │                          │
  └────────────────────┘ └──────────────────────┘ └────────────────────────┘

  plan2 /brain/demo_phase String subscriber 契約 ──published-by──► plan4 gateway /api/demo_phase
                                                                      ▲
                                                       Studio hidden 五幕鈕觸發

  plan3 五幕 canned table + offline_mode 契約 ──consumed-by──► plan2 timeout→canned-rescue（rescue 呼叫 canned 路徑）
                                              ──published-by──► plan4 gateway /api/offline_mode（offline toggle）

  plan2 _publish_brain_state 加 demo_phase/offline_mode 欄位 ──consumed-by──► plan4 P4-4 phase chip

  nav incident plan T0 排除 + D1-D5 綠 ──gates──► plan5 T5-5 / plan6 NS-H3 motion HITL

  plan5 T5-1 face delete .npz spec ──implemented-by──► Lane 3 CLI v2 T3-5
  plan5 owns S8 route_id sanitize（已實作）──verified-by──► plan6 NS-V1（回歸覆蓋）
```

### 6.2 四條關鍵依賴（明確落點）

1. **plan1 profiling 結果 gates plan6 nav stack + plan2 S1 phase**：plan1 §11.1 的 4-branch 決策樹 + S1 runtime layout 決策表，是 plan6 NS-H1/H2/H3「能不能起 nav stack 做 motion」與 plan2 `s1_nav` 幕「呈現 live nav / Studio 證據 / 影片」的硬前置。plan6/plan2 **不得在 plan1 決策落點前先寫死 S1 為 live nav**。
2. **plan2 brain `/brain/demo_phase` subscriber 被 plan4 Studio button 消費**：plan2-T2-3 定義 brain 側 `std_msgs/String` subscriber 契約；plan4-P4-1 gateway publisher 對該 topic 發布（每次**先發 reset_context 再發 phase**）。契約未合前 plan4 寫 mock-publisher 單測、不依賴 brain 在線。
3. **plan3 canned table 被 plan2 conductor rescue 消費**：plan2-T2-5 timeout→canned-rescue 觸發點**呼叫** plan3-T3 提供的 canned 路徑（`say_canned` / 該幕 phrase），plan2 **不自定義台詞文字 / 不改 timeout 數值**。
4. **plan3 offline_mode 被 plan4 offline toggle 消費**：plan4-P4-2 gateway `/api/offline_mode` 對 plan3-T4 定義的 brain `offline_mode` 契約發布；契約形態（param vs topic）未定前 plan4 標 TODO-依-plan3，但 route/cache/WS/test 結構先就緒。

### 6.3 共享狀態欄位（需協調補欄位）

- `_publish_brain_state`（`brain_node.py:2211`）**目前不含** `demo_phase` / `offline_mode` → plan4 P4-4 phase chip 的真相欄位需 **plan2 / plan3 補上**；欄位未到前 chip 顯示 `?`。

---

## 7. 可平行 vs 不可平行

### 7.1 可平行（Parallelizable）

- **plan1-T1（harness）** vs **plan2 FLOOR** vs **plan3 timeout/canned** vs **plan4 runbook 文件** vs **plan5 P1 offline 證據** vs **plan6 軟體 upside（NS-1/2/3/4/7）** — 不同檔案、不同 Codex worktree，可並行。
- **plan4 gateway（`studio_gateway.py`）** vs **plan4 frontend（`*.tsx`/`state-store.ts`）** — 不同檔，可並行（但 frontend 依 gateway route 形態，先定 route 再接）。
- **plan5 P1 三項（T5-P1a/b/c）** 彼此可並行（WSL 隔離 venv，純加法 offline）。
- **plan6 NS-D0（evidence pull，dev 機）** 與 Phase A 所有純軟體可並行。
- **plan6 NS-5 / NS-6 / NS-D2 文件** 與 nav 軟體 task 可並行。

### 7.2 不可平行（NOT-Parallelizable，必須 sequence）

- **plan2-T2-1（詞彙）→ T2-2（清理）→ T2-3（subscriber）→ T2-4/T2-5（auto）**：同檔 `brain_node.py` / `interaction_state.py` 線性疊加；T2-1 是 T2-3/T2-4 顯示/解析正確 phase 名的前置。
- **plan3 brain_node.py 三 task（T3 canned → T4 offline_mode → T5 fallback）**：同檔，且 T5 fallback 路徑依 T3 canned table 存在。
- **plan4 frontend 依 gateway route**：P4-1/P4-2（gateway）→ P4-3（frontend 鈕）→ P4-4（chip，且依 plan2/plan3 補 brain_state 欄位）。
- **plan6 nav 診斷鏈**：NS-D1（T0 診斷）**必須最先** → NS-T0（gated remediation，僅 D1 confirm）→ NS-D2/NS-5 SOP。
- **plan1 profiling**：J-0 清場 → A → B → C（C 依 A 已起）→ T5 判讀（依 A/B/C CSV）。
- **跨 plan**：plan1-T5 決策表 **先於** plan6 S1 形態定稿、plan2 S1 phase 呈現定稿、plan4 P4-13 交接決策。
- **motion HITL（Phase D）**：必在 NS-T0 排除 + NS-D2 綠 + plan1 profiling 允許共存之後。
- **6/17 彩排（plan5-T5-6/T5-7）**：所有 FLOOR merged + 相關 HITL 完成後。

---

## 8. 共享檔案衝突風險（shared-file conflict，需排序避免 merge conflict）

> **鐵律**：同檔多 plan 改 → 線性 sequence（不開並行 worktree 改同檔），每 task 一小 PR，前一個 merge 後再接下一個。

| 共享檔 | 觸碰的 plan / task | 排序與邊界 |
|---|---|---|
| **`interaction_executive/interaction_executive/brain_node.py`** | **plan2**（T2-2 helper / T2-3 subscriber+`_set_demo_phase` / T2-4 auto+entry-greet / T2-5 max_wait+rescue）、**plan3**（T3 canned table / T4 offline_mode param / T5 `_on_chat_timeout` phase-aware） | **最高衝突檔**。**鎖定 merge 順序（LOCKED，序列 merge、零並行同檔）**：**(1)** plan2-T2-1/T2-2/T2-3（phase 機制 base，`:311-321`+`:1745-1789`+`:2190-2209`）**先 commit/merge** → **(2)** plan3-T3/T4/T5（canned/offline/fallback，`:80`+`:496`+`:439`+`:1124-1145`，步驟 1 後**零重疊**）→ **(3)** plan2-T2-4/T2-5（auto ENHANCEMENT）。**Codex 序列執行：commit 1 先進、再接 commit 2（預期 0 衝突）、再接 commit 3。任一步偵測 conflict → 停、回報衝突 file:line、等 Cloud 核可，不自行 resolve。** 邊界：plan2 擁 phase 詞彙/清理/控制/auto；plan3 擁 canned/offline_mode/fallback-reason；**plan3 讀 `self.demo_phase` 不改 phase 機制**。 |
| **`interaction_executive/interaction_executive/interaction_state.py`** | **plan2**（T2-1 PHASE_ALLOWED_KINDS + canonicalize_phase） | 僅 plan2 改；Lane 1 ISM 2a 同表接管（policy），與 plan2 詞彙不衝突；**禁收緊 unknown→all**。 |
| **`pawai-studio/gateway/studio_gateway.py`** | **plan4**（P4-1 demo_phase / P4-2 offline_mode publisher+route） | 僅 plan4 改；P4-1 → P4-2 線性；沿用既有 `auth` 機制 env-gated 預設關（**不 flip secure-default**）。 |
| **`tools/pawai_cli/pawai_cli/main.py`** | **plan5**（T5-1 face delete/rebuild 補 .npz，純 string）、**plan4**（P4-9 只**文件化** CLI workaround，不改 code）、**Lane 3**（owns `demo phase`/`demo mode`/`status brain`/`face delete` 實作） | plan5-T5-1 = spec 來源（落 Lane 3 T3-5）；若 Lane 3 已排 T3-5，T5-1 退化為「review Lane 3 PR 是否同刪 .pkl+.npz」。plan4 只在 runbook 標 PLANNED，**不碰 main.py code**。**避免 plan5 與 Lane 3 同改 main.py：以 Lane 3 為實作 owner，plan5 提供 spec+測試契約。** |
| **`nav_capability/nav_capability/nav_action_server_node.py`** | **plan6**（NS-1 yaw 閘 / NS-2 watchdog / NS-3 fail-closed gate） | 僅 plan6 改；三 task 各自 additive 旗標、各自小 PR、線性 merge；**不改 covariance 門檻值**。 |
| **`nav_capability/test/test_route_validator.py`** | **plan5**（T5-3 驗證收尾 owns）、**plan6**（NS-V1 回歸覆蓋） | S8 prod code 已實作、**兩者皆勿改 prod**；plan5 owns 驗證、plan6 補 nav 路徑覆蓋測試；協調避免重複 case。 |
| **`go2_robot_sdk/urdf/go2.urdf` + `robot.launch.py`** | **plan6**（NS-T0 gated remediation） | 僅 plan6 改；**gated**（僅 NS-D1 confirm）；單檔 `git checkout` 可退；有 nav-stack regression 風險，改後必跑 smoke 8/8 + view_frames。 |
| **`docs/runbook/2026-06-18-operator-runbook.md`** | **plan4**（owns，P4-5..P4-13）；plan3/plan5/plan6 **回填段落**（WAV SOP / 三洞 HITL / nav fallback） | plan4 owns 檔；其他 plan 提供「段落內容」由 plan4 整合，**不各自建檔**。 |

---

## 9. 6/17 彩排總閘（Rehearsal Gate）

**閘主：plan5-T5-6 / T5-7。** 規則：

1. **逐幕決定 `auto_advance_enabled`（ENHANCEMENT，預設 OFF）vs manual floor（FLOOR）**：每幕**兩種都彩排到**——(a) auto-advance guard/trigger/timeout/canned-rescue；(b) manual floor（Studio hidden 鈕 / `ros2 param set demo_phase`）。
2. **per-phase max_wait floor（Q4）**：S1 10–20s / S2 3–5s / S3 5–8s / S4 8–10s / S5 3–5s；逾時必有 canned 補位（never dead air）。
3. **one-keystroke disable**：逐幕 flag 可即時關（`ros2 param set` 或 Studio）；關掉後 manual floor 仍 100% 可用。
4. **phase switch 清理驗**：切幕清 `pending_confirm` / `active_plan` / gesture cooldown + trace transition type（消費 plan2-T2-2）。
5. **硬閘（go/no-go）**：開場安全前置全過 + `pawai smoke full` **全綠** + 五幕順序不串台（trace 驗 suppress 集合對 `PHASE_ALLOWED_KINDS`）→ `git tag pre-618-checkpoint`；**main 6/17 18:00 凍結**。smoke full 紅 → 不打 tag、回滾上一綠 commit。
6. **逐幕能力分級**：S1 = FAILED→fallback（今天撞牆）/ S2/S3/S4 = needs-HITL / S5 = proven（6/10）/ S8 = 已實作 byte-identical。
7. **6/18 絕不押 auto-advance**（Q6）；任一幕 auto 不穩 → 該幕走 manual floor。

---

## 10. 6/18 live demo 最終路徑（Final Path）

### 10.1 FLOOR 保證（floor guaranteed）

每一幕的**最底保證** = FLOOR 全綠時即可交付的 live 五幕：
- demo_phase 五幕詞彙 + 切換清理（plan2 FLOOR）
- canned / LLM-hybrid 語音（plan3，Layer1 快觸發 + Layer3 canned，never dead air）
- Studio hidden 五幕鈕（plan4 FLOOR）操作員切幕
- `ros2 param set /brain_node demo_phase <phase>` backup
- 全域 byte-identical 退保守：`auto_advance_phases=[]` + `demo_phase=all` + `ism_enabled=false` + `offline_mode=false` = 6/10 已驗現行為（~955 綠）

### 10.2 Auto upside（彩排決定逐幕開）

6/17 彩排判定穩的幕，開 `auto_advance_enabled`（per-phase）→ demo 看起來自動（guard/trigger/timeout→canned-rescue）。**永不全押。**

### 10.3 各幕觸發信號 + max_wait + 語音層 + 能力分級

| 幕 | 觸發信號（短但可信） | max_wait_s | 語音（Q5） | 能力 | S1 特例 |
|---|---|---|---|---|---|
| **s1_nav** | operator-arrived | 10–20 | Layer3 canned「我正在移動到巡檢位置」/「我先在這裡待命」 | **FAILED**→fallback | 走 plan1 4-branch + plan6 三層 fallback |
| **s2_greet** | face known 0.5–1s（pose=bonus 非硬依賴） | 3–5 | Layer2 LLM ≤1.5–2s → Layer3 canned | needs-HITL | greet 進幕觸發 + sitting=false（gotcha #1/#2） |
| **s3_pose_object** | cup/object 0.5–1s | 5–8 | Layer2 → Layer3 | needs-HITL | sitting 移此當 bonus |
| **s4_gesture** | 一次高信心 gesture（**僅 S4**） | 8–10 | Layer2 → Layer3 | needs-HITL | confirm 台詞不指定手勢；Go2 wiggle 需 e-stop |
| **s5_safety** | keyword/text（**no LLM**） | 3–5 | **rule-first 0s**（拒絕語意） | **proven** | LLM 不可 override |

### 10.4 四階 rollback ladder（four-rung rollback，never dead air）

```
① auto-advance（guard/trigger/timeout→canned-rescue）        ← 看起來自動，彩排決定逐幕開
        ↓ auto 失速 > 該幕 max_wait_s（S1 10–20s/S2 3–5s/S3 5–8s/S4 8–10s/S5 3–5s）
② Studio hidden 五幕鈕（操作員手動切幕，先 reset 再切）        ← FLOOR
        ↓ 按鈕後無 200 OK 確認 > 3s（Studio 不通）
③ ros2 param set /brain_node demo_phase <phase>             ← backup
        ↓ param set 無 ack > 2s（runtime 失效）
④ demo_phase=all + 影片（純影片 + 遙控 + 保守旁白）           ← LAST-RESORT，非主體
```
> **IRON RULE — 每階邊界都有 canned 補位（never dead air）**：
> - **①→② 邊界**：auto-advance 的 timeout→canned-rescue 在 `max_wait_s` 到時**自動播該幕 canned**（rule-based 0s，plan2-T2-5）。
> - **②（manual FLOOR 也保證 never dead air）**：manual floor 模式下，**若操作員在該幕 `max_wait_s` 內未按鈕**，操作員的 **S5-Trigger / Trace-Watcher 須立即用 Studio `skill_request` 觸發該幕 canned**（或退 ③ `ros2 param set` 觸發），**不可乾等操作員**——manual-only 模式不得因「操作員沒按」而開天窗。runbook P4-6「失速處置」欄逐幕寫明此 canned 觸發動作。
> - **每階 timeout 值寫進 runbook P4-10**：auto stall > `max_wait_s` → ②；hidden 鈕無確認 > 3s → ③；param set 無 ack > 2s → ④。
- S1 退：遙控 + Foxglove 證據 → 影片（plan6 fallback ②/③）。
- TTS 退：`TTS_PROVIDER=piper` 重起 / offline mode / canned。
- 手勢退：`gesture_enabled false`。stranger 退：`stranger_alert_enabled false`。
- face 退：sim<0.7 → generic greet（不秀具名）。
- offline 退：啟動前 env override（proven）`LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_full_demo_tmux.sh`。
- 最終保底：`demo-2026-06-snapshot` 影片。

### 10.5 8GB 交接（觀眾感知）

S1（nav 段）與 S2–S5（brain 段）若需 stack 交接（依 plan1 profiling branch），約 1 分鐘空檔 → 操作員口頭過場 + Studio 前段 trace 證據填補，不讓觀眾以為當機。交接決策樹依 plan1 P0 no-motion profiling 結果（plan4-P4-13）。

---

## 11. 角色分工（Role-Split）

- **Cloud / Fable（planner + reviewer）**：讀 source、設計、切 task packet、定 tests/rollback/stop-conditions、對抗式驗 overclaim/demo-break/safety、指示修正、整合。**不改任何 runtime code。**
- **Codex（builder）**：依 packet 實作、寫測試、跑測試、小 commit/PR、回報 diff + test-result + risk。**不擴 scope、不改 runtime-claim，未經 Roy 授權 + e-stop 不發任何 Go2 motion。**
- **Roy（HITL authority + Go2 operator）**：所有 `go2_motion` task 的授權者 + e-stop 在手；台詞鎖定（canned 五句、S1 claim）；6/17 彩排逐幕 auto/manual 拍板；6/18 Driver（S1 開 Go2 / S4 confirm 手勢）。
- **操作員角色（6/18，plan4-P4-8）**：① Driver（Roy）② Trace-Watcher（盯 Studio chip + trace，按 hidden 鈕切幕/reset）③ S5-Trigger（用 Studio skill_request/文字觸發 SafetyLayer reject）。

---

## 12. 全域誠實 / 安全鐵律（所有 plan 繼承）

1. demo flow > advanced capability；nav safety > nav capability；honesty > appearance。
2. AFK 完成 = 「code merged + 單測綠（needs-HITL）」；只有 Roy 真機 HITL 過 = `proven`。
3. **唯一確認進 runtime 的 byte-identical 變更 = S8 route_id sanitize（已實作）**；其餘 enforcement 全 default-off。
4. 任何 plan **不依賴 `goto_relative`**（NOT_DEMO_READY）。
5. **不對移動中 Go2 送 Damp(1001)**；e-stop = `emergency_stop.py engage` + `StopMove(1003)`。
6. nav motion **T0 URDF authority 未排除前一律禁 motion**。
7. 不 claim：autonomous navigation / 全自動 live demo / fallen detection / 2m object / reliable color / 19 colors / 動態繞障 / auto-resume / D435 已融合進 costmap。
8. 每個 task **必有 tests + rollback**；無「順便清理/重構」。**rollback 的 `git revert <sha>` 是「乾淨 linear」前提**：若該 commit 後已有多個 PR 落地同檔導致 revert 衝突 → **不硬 revert**，改 **(a) runtime flag/param 退（旗標關=byte-identical，首選）或 (b) 手動 revert 受影響行（target 那幾行、保留後續 PR）或 (c) 退到該檔最近綠 tag 再 cherry-pick 後續**。任一 plan 的 §10 rollback 表的 `git revert` 條目都隱含此「衝突時降級為 flag-off / 手動 revert 行」規則。
9. 8GB 互斥：nav stack 與 brain demo stack 不同跑（除非 plan1 profiling C-CORESIDENT 證實可共存）。
10. P1 supervision/benchmark **永不上 Jetson runtime**；demo 錄影**絕不餵 LLM**。

---

## 13. Done Criteria（總綱層級）

- [ ] Phase A 純軟體 FLOOR 全 merged + 單測綠（plan2 FLOOR / plan3 P0 / plan4 gateway+frontend+runbook / plan1-T1 / plan5-T5-1/T5-3 / plan6 NS-V1+軟體 upside）。
- [ ] Phase B：plan6 NS-0/NS-D0/NS-D1（+ 視 confirm 做 NS-T0）+ plan1 三配置 profiling + T5 決策表落點。
- [ ] Phase C：face re-enroll sim≥0.7 + plan2 FLOOR HITL（H-1A/B/C）+ plan3 H1..H5 + ENHANCEMENT no-motion 驗。
- [ ] Phase D（upside）：motion HITL（NS-H1/H2/H3 + confirm-wiggle）視 T0 排除 + plan1 允許共存才開。
- [ ] Phase E：6/17 彩排逐幕 auto/manual + `pawai smoke full` 綠 + tag `pre-618-checkpoint` + main 18:00 凍結。
- [ ] Phase F：6/18 live 五幕，FLOOR 保底 + auto upside + 四階 rollback + 影片末路。
- [ ] 全程 byte-identical 退路成立：`auto_advance_phases=[]` + `demo_phase=all` + `ism_enabled=false` + `offline_mode=false` = ~955 綠。
- [ ] 對外 claim 全綁 `nav-618-claim-wording.md` S1-S8 / F1-F10；逐幕能力分級標明。
