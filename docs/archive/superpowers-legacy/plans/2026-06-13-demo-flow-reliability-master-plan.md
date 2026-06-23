# PawAI Demo Flow Reliability Sprint — Master Plan（6/18 五幕流程穩定化）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫群：PawAI Demo Flow Reliability Sprint（Cloud A）｜本份：**Master Plan（總綱 + 決策表）**
> 硬底線：**6/18 期末發表**。本計畫群目標**不是 v2 北極星**，而是把 6/18 demo 五幕流程「**變穩、照順序、可操作、出錯有 trace/rollback**」，讓**禮拜一前可以照順序跑完**。

> **本計畫群五份**（本份為總綱，其餘四份為子計畫）：
> 1. **master**（本份）：總綱、能力分級、跨計畫執行序、決策表。
> 2. [conductor](2026-06-13-demo-phase-conductor-plan.md)：五幕 `demo_phase` 指揮（詞彙/切換清理/控制面）。
> 3. [online/offline fallback](2026-06-13-online-offline-fallback-plan.md)：語音/LLM/TTS 網路降級韌性 + 五幕 canned phrase。
> 4. [s1 low-risk navigation](2026-06-13-s1-low-risk-navigation-plan.md)：第一幕移動段低風險主線 + 三層 fallback。
> 5. [operator runbook](2026-06-13-demo-operator-runbook-plan.md)：現場逐幕操作手冊規劃 + 平台支援度。

> **既有真相來源（不重寫、只引用）**：[nav-capability-ladder](../navigation/2026-06-13-nav-capability-ladder.md)、[nav-618-claim-wording](../navigation/2026-06-13-nav-618-claim-wording.md)、[roy-hitl-queue](../runbook/2026-06-13-roy-hitl-queue.md)、[post-refactor-acceptance-report](../runbook/2026-06-13-post-refactor-acceptance-report.md)、[Lane 1 ISM](2026-06-13-lane1-brain-ism-staged-enable-plan.md)、[Lane 3 CLI](2026-06-13-lane3-cli-v2-completion-plan.md)、[Lane 6 nav](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)。

---

## 1. Goal

讓一名操作員能在 6/18 之前、照固定順序穩定跑完五幕 demo，且**全程不 overclaim**：

1. **demo 五幕照順序**：s1_nav → s2_greet → s3_pose_object → s4_gesture → s5_safety。
2. **每幕只觸發該幕功能**：用既有 `demo_phase` gate 自發社交（greet/object/gesture），安全鏈/明確指令不受影響。
3. **online / offline 兩套路徑**：網路差時不卡 LLM/TTS timeout，秒回保底台詞。
4. **S1 移動段低風險**：短距/operator-assisted/遇障安全停，**不押 live SLAM / autonomous approach Roy**；最壞退影片。
5. **Studio / CLI 可操作**：切幕、看 phase、看 trace、切 online/offline。
6. **出錯有 trace / rollback**：每幕、每步都能往「現行已驗行為」退，不引入新行為。

**誠實底線（貫穿五份）**：AFK 完成的只能說「code merged + 單測綠」（needs-HITL）；**只有 Roy 在場真機 HITL 過的才算 proven**。能力一律分 **proven / needs-HITL / research-only** 三級，對外 nav claim 全部走 [claim-wording](../navigation/2026-06-13-nav-618-claim-wording.md) S1–S8 / F1–F10。

---

## 2. Current state（2026-06-13）

### 2.1 完成度（handoff EOD 數字）
- ① 軟體面 AFK ~**95%**（8 PR #167-#175 merged、~955 tests、全行為變更 flag 預設 off）。
- ② Pre-6/18 整體（軟體+HITL）~**63%**。
- ③ v2 北極星 ~**33%**。
- 剩餘 ~37% **幾乎全是 Roy 在場 HITL**（nav motion、L4 上機矩陣日、L5 enforcement flip）。

### 2.2 即時硬體狀態（開工/收工第一件事）
- Jetson 上 **nav stack 還在跑**（tmux `nav-cap-demo`，9 windows）。
- **剛發生 Go2 撞擊**：`goto_relative 0.3m` 第一發走歪撞牆、Roy e-stop。**第一件事 = 確認 Go2 停穩 + `pawai demo stop` 清場**。
- D435 **Right MIPI error / Hardware Error**（nav 不需 D435；face/vision 受影響 → brain demo 前可能重插 D435 USB）。
- **nav stack 與 brain demo stack 8GB 互斥**（不能同跑）→ S1 是獨立鏡頭。

### 2.3 五幕能力快照（code 現實 + HITL 證據）
- **demo_phase 機制已存在**（`interaction_state.py:33` `PHASE_ALLOWED_KINDS`、`brain_node.py:496/333` `demo_phase`/`_phase_allows`），只 gate 三種自發社交 kind（greet/object/gesture）；安全鏈/明確指令/Studio skill_request 不受 phase 影響（priority safety > explicit > phase）。**詞彙是 `all/s2_face/s3_object/s4_gesture/quiet`**，五幕詞彙是其改名+擴充（conductor 計畫）。
- 既有 CLI：`demo start|stop`、`smoke brain|vision|object|nav --static|full`、`face list|enroll|rebuild|test`、`evidence pull`、`status`、`health`、`doctor`（Lane 3 已 merged）。
- TTS chain `openrouter_gemini(Despina) → edge_tts → piper`（`tts_node.py:1119-1133`）；LLM `gpt-5.4-mini → gemini-3-flash → rule:chat_fallback say_canned`。

---

## 3. Problems / gaps（跨計畫，子計畫各有細列）

| # | Gap | 歸屬子計畫 |
|---|-----|-----------|
| M1 | nav motion **今天 FAILED**（0.3m 撞牆，根因 AMCL initialpose 朝向 + 跑 open_space ±30°） | [s1-nav](2026-06-13-s1-low-risk-navigation-plan.md) |
| M2 | phase 詞彙與五幕不對齊（無 s1_nav/s5_safety、s2_face≠s2_greet）；切 phase 不清 pending_confirm/active_plan/cooldown | [conductor](2026-06-13-demo-phase-conductor-plan.md) |
| M3 | 網路差會卡 LLM/TTS timeout（`openrouter_gemini_timeout_s` 兩處不一致 60s vs 6s、`llm_timeout=15s`）；無 runtime offline 開關 | [fallback](2026-06-13-online-offline-fallback-plan.md) |
| M4 | face re-enroll 脆（B4 npz bug、幽靈目錄、demo start 重訓）；confirm 目標路徑(thumbs_up→OK→wiggle) 未驗（只驗過 peace→OK→WeGo） | [runbook §8.6](2026-06-13-demo-operator-runbook-plan.md) |
| M5 | `pawai demo phase` / `demo mode` / `status` brain 區塊 / `face delete`(B4 修) 未實作 | [Lane 3](2026-06-13-lane3-cli-v2-completion-plan.md) + conductor/fallback |
| M6 | 8GB 互斥 → S1（nav）與 S2-S5（brain）必須分段交接 stack | [runbook §8.0](2026-06-13-demo-operator-runbook-plan.md) |

---

## 4. Scope

五份計畫合起來涵蓋：phase 指揮（conductor）+ 網路韌性（fallback）+ 第一幕移動低風險（s1-nav）+ 現場操作手冊（runbook）+ 本份總綱治理。**全部「只規劃、不實作 code」**；實作工項交棒既有 lane（conductor 詞彙/清理 → IE；CLI → Lane 3；nav → Lane 6）。

---

## 5. Forbidden scope（計畫群共同，五份一致）

- ❌ 不換模型當主線（LLM/TTS/ASR/vision 模型維持現役）。
- ❌ 不做完整 benchmark dashboard。
- ❌ 不做 live SLAM 主線。
- ❌ 不做 autonomous approach Roy 主線。
- ❌ 不大改 Studio UI（只加唯讀 chip / 指示燈）。
- ❌ 不完整重寫 CLI（只加 additive subcommand）。
- ❌ 不進 Phase 3/4/5 遠期大功能（ISM 2e/2f/2g、source-trust enforcement、CLI 產品化、模型 A/B 全跑）。
- ❌ nav：F1–F10 禁講（自由巡邏/動態繞障/D435 已融合/auto-resume/即時恢復…，見 [claim-wording §4](../navigation/2026-06-13-nav-618-claim-wording.md)）。
- ❌ 不對移動中 Go2 送 Damp(1001)。

---

## 6. Tasks（跨計畫 roll-up；逐項細節見各子計畫）

> 標記：`[SW]`=pure software（WSL）｜`[J]`=Jetson needed（無 Go2 motion）｜`[G]`=Go2 motion needed。能力分級見 §9。

| ID | Task | 子計畫 | 類型 | 分級 |
|----|------|--------|:----:|------|
| **C1** | `PHASE_ALLOWED_KINDS` 擴 5 幕 + alias（s2_face=s2_greet…） | conductor T-C1 | `[SW]` | needs-HITL |
| **C2** | 切 phase 清理 helper `_apply_phase_transition`（重用 reset_context 語義） | conductor T-C2 | `[SW]` | needs-HITL |
| **C3** | `pawai demo phase <phase>` 介面契約（實作歸 Lane 3） | conductor T-C3 | `[SW]` | needs-HITL |
| **C4** | `/state/brain` 帶 `demo_phase` + Studio 唯讀 chip | conductor T-C4 | `[SW]` | needs-HITL |
| **F1** | 統一/收緊 `openrouter_gemini_timeout_s`（60s→6s 消地雷） | fallback T-FB-1 | `[SW]` | needs-HITL |
| **F2** | 收緊 `llm_timeout` + 釐清 demo 主線吃哪條 timeout | fallback T-FB-2 | `[SW]` | needs-HITL |
| **F3** | 五幕 canned phrase 表（phase→台詞）+ WAV pre-render | fallback T-FB-3 | `[SW]`+`[J]` | needs-HITL |
| **F4** | runtime offline mode 開關（`demo mode offline`，param 短路 cloud） | fallback T-FB-5 | `[SW]` | needs-HITL |
| **N1** | s1_nav 主線參數鎖定 indoor_tight ±18° 低速 0.2（kill 重啟帶參） | s1-nav T-S1-1 | `[J]` | proven(C6) |
| **N2** | initialpose 朝向校正 SOP（LiDAR 紅點對齊牆）+ goto 前朝向 sanity | s1-nav T-S1-3/4 | `[SW]`寫+`[G]`驗 | needs-HITL(C7) |
| **N3** | 短距重驗 0.3m × n=3 全 reached 0 撞（**s1_nav live 唯一閘門**） | s1-nav H3 | `[G]` | needs-HITL(今日 FAILED) |
| **B4** | `pawai face delete`/`rebuild` 補刪 `model_sface.npz`（修 B4 bug） | Lane 3 T3-5 | `[SW]`+`[J]` | needs-HITL |
| **S** | `pawai status` brain runtime 區塊（顯示 ism/demo_phase/gesture/stranger） | Lane 3 T3-6 | `[SW]`+`[J]` | needs-HITL |
| **R** | operator runbook 五幕骨幹 + 平台表 + 三洞段 + dry-run | runbook T-RB-* | `[SW]`(+HITL驗) | needs-HITL |

---

## 7. Pure software tasks（可 WSL AFK，不需硬體）

C1、C2、C3、C4、F1、F2、F4、B4(刪 npz 邏輯)、S(解析)、R(全文件)、N2(SOP/sanity 提示撰寫) 的 code/文件部分皆 `[SW]`，可在 6/18 前先合 + 單測綠（標 needs-HITL）。全部具 **byte-identical 退路**（`demo_phase=all` + `ism_enabled` off + offline mode off + 不切 phase = 現行為）。

---

## 8. Jetson / Go2 HITL tasks（需 Roy 在場）

> **共通前置**：先確認 Go2 停穩 + `pawai demo stop` 清場；nav 與 brain stack 8GB 互斥不同跑；Go2 motion 項一律 e-stop 就位。對應 [roy-hitl-queue](../runbook/2026-06-13-roy-hitl-queue.md)。

| HITL | 內容 | 類型 | 對映 |
|------|------|:----:|------|
| **H-conductor** | 五幕詞彙逐幕驗 + 切換清理（s4 confirm 切 s5 不黑洞）+ confirm 觸發手勢差異 | `[J]`+`[G]`(confirm) | conductor H-C1~H-C4 |
| **H-nav（高風險）** | indoor_tight 護欄(N8) → initialpose 朝向校正(N2) → **0.3m n=3 重驗(N3)** | `[G]` | s1-nav H1/H2/H3、HITL queue C 段 |
| **H-face** | face_db 衛生 + re-enroll + sim≥0.7 重驗 | `[J]` | runbook §8.6.1 |
| **H-offline** | runtime offline mode 切換 + 五幕 canned/WAV 播放 | `[J]` | fallback H |
| **H-fullrun** | 五幕照順序跑一遍、每幕只觸發該幕功能 + dry-run runbook | `[J]`+`[G]` | runbook T-RB-9 / E 回穩日 |

---

## 9. Tests（含能力分級總表）

### 9.1 全 demo 能力分級（誠實，對外 claim 依此）

| 幕 | 能力 | 分級 | 證據 / 條件 |
|----|------|------|------------|
| — | demo_phase gate（3 kind 抑制） | **proven** | 6/10 demo 用 `demo_phase s3_object` 錄影 |
| — | 五幕詞彙 + 切換清理 + CLI + chip | needs-HITL | conductor 新 code，待 H-conductor |
| **S1** | 0.3-0.5m short goto | **needs-HITL（今日 FAILED）** | 今天 0.3m 撞牆；C1 low-sample / C2 needs-retest；**N3 n=3 過才可 live** |
| S1 | safe-stop（正前停障，不繞行） | **proven** | trackB §1 NAV-2 / 6/9 §1.5（C4 with-limit） |
| S1 | indoor_tight ±18° profile | **proven** | trackB §4 / 6/9 §1.3（C6 with-limit，綁低速 ≤0.2） |
| S1 | 1.0m+ goto / 動態繞障 / approach person | **research-only / DO_NOT_CLAIM** | C3 wired_only、C11/C12 |
| **S2** | 具名問候（known face + sitting + cooldown） | **proven 一次（脆）** | HITL#2 sim 0.87 / 6/8 0.73-0.81；needs-HITL 重驗（B4/幽靈目錄/重訓） |
| **S3** | pose=sitting + cup remark | needs-HITL | cup 0.7/1.0/1.5m recall 高（vision HITL proven）；sitting 兩類中等信心 |
| S3 | cup↔bottle↔phone 類別混淆改善 | **research-only** | 換模目標、不在 6/18 主線（B-4 預設不換） |
| **S4** | confirm flow（OK 二確 + wiggle） | **proven 一次** | HITL#2 peace→OK→WeGo；**目標 thumbs_up→OK→wiggle 未驗（needs-HITL）** |
| S4 | gesture min_conf 0.7 + 3-vote 防誤觸 | **proven** | spam 已明顯改善（vision HITL） |
| **S5** | backflip 安全拒絕（SafetyLayer reject） | **proven 端到端** | 6/10 S5 已驗 |
| — | online ASR/LLM/cloud TTS + 自動 fallback chain | **proven** | 5/12 night offline chain 實機驗 / 3/17 斷 tunnel 5/5 |
| — | env-offline（LLM_ENDPOINT 假 port + piper） | **proven** | 5/12 |
| — | runtime offline mode + WAV pre-render | needs-HITL | fallback 新 code |

### 9.2 測試手段
- 單測（WSL）：conductor phase 表/清理、fallback timeout/canned、CLI mock（Lane 3 conftest 網路封鎖）。
- 回歸護欄：`demo_phase=all` + `ism_enabled` off + offline off → 既有 ~955 tests 全綠（byte-identical）。
- smoke：`pawai smoke full`（6/17 回穩日主工具）、`smoke nav --static`（零 motion）。
- trace：`pawai evidence pull` grep phase suppress reason。
- HITL：§8 各項，全需 Roy 在場。

---

## 10. Rollback（全域，往現行已驗行為退）

| 層 | 觸發 | 動作 |
|----|------|------|
| 全域退保守 | 任一幕失控 | `demo_phase all` + `ism_enabled false`（byte-identical） |
| TTS 退本地 | cloud timeout | `TTS_PROVIDER=piper` / `demo mode offline`(PLANNED) / canned |
| 手勢退 | 誤觸 | `gesture_enabled false`（cancel in-flight confirm） |
| stranger 退 | 全系統卡 | `stranger_alert_enabled false`（6/9 真兇，demo 預設關） |
| 換幕殘留退 | confirm/plan 污染 | `/brain/reset_context`（Empty） |
| nav 退影片 | S1 撞/n=3 未過 | e-stop → `pawai demo stop` → S1 純影片 fallback |
| face 退 generic | sim<0.7 | S2 不秀具名、generic greet / 還原 backup |
| 整 stack 退 | 環境異常 | `pawai demo stop --force` + 逐一 `pkill -9` + clean script |

> 每個子計畫各 Task 另有逐項 rollback。三層 nav fallback（live → 遙控+Studio 證據 → 影片）保證 **nav 段不開天窗**。

---

## 11. Done criteria

1. ☐ 五幕可照順序跑完（`pawai demo phase` 或 `ros2 param set demo_phase` 切幕），**每幕只觸發該幕功能**（trace 證明）。
2. ☐ online/offline 兩套路徑都能交付五幕；網路差時不卡 timeout（秒回 canned）。
3. ☐ S1 三層 fallback 鎖定：**H-nav（N3 0.3m n=3 無撞）過 → live；否則退影片**，claim 退保守。
4. ☐ 三洞 runbook 段完成：face 重驗 SOP（B4 workaround）、confirm 目標 vs 驗過差異、nav HITL + e-stop。
5. ☐ Studio/CLI 可切幕、看 phase、看 trace、切 mode（落地的標 needs-HITL、未落地的標 PLANNED + workaround）。
6. ☐ 回歸：`demo_phase=all`+`ism off`+offline off → ~955 tests 全綠（byte-identical）。
7. ☐ 6/17 回穩日 `pawai smoke full` 全綠 + 五幕彩排一輪 + tag。
8. ☐ 對外 claim 全部過 [claim-wording](../navigation/2026-06-13-nav-618-claim-wording.md)，無 F1–F10 越界。

---

## 12. Execution order（跨五計畫）

**Step 0（即刻，硬體安全）**：確認 Go2 停穩 + `pawai demo stop` 清 nav stack（撞擊後清場）。

**Phase A — 純軟體 AFK（6/13–6/15，可 WSL 並行）**
1. conductor C1（phase 表+alias）→ C2（切換清理）→ C4（brain_state 欄位）。
2. fallback F1/F2（timeout 收緊）→ F3（canned 表+WAV）→ F4（runtime offline mode）。
3. Lane 3 B4（face npz 修）+ S（status brain 區塊）+ C3（demo phase CLI 契約實作）。
4. s1-nav N2(SOP/sanity 撰寫) + runbook R（全文件骨幹）。
→ 全程 byte-identical 退路 + 單測綠，標 needs-HITL。

**Phase B — HITL（依 [roy-hitl-queue](../runbook/2026-06-13-roy-hitl-queue.md) 時段，Roy 在場）**
5. **demo lane**：H-conductor（五幕詞彙/清理/confirm 差異）+ H-face（face_db 衛生）+ H-offline（offline mode + canned）+ smoke family。
6. **nav lane（獨立時段，先 `pawai demo stop`）**：H-nav 三步 — indoor_tight 護欄 → initialpose 朝向校正 → **0.3m n=3 重驗（撞牆根因最終裁決）**。

**Phase C — 6/17 回穩日（硬 checkpoint，不開新刀）**
7. 全 flag 設發表日狀態 + `pawai smoke full` 全綠 + 五幕彩排 + tag `pre-618-checkpoint`；未過 HITL 的刀 flag-off。

**6/17 18:00 起 main 凍結至發表結束。**

---

## 13. 6/18 presentation impact

- **正面**：五幕可照順序、不串台、出錯有 rollback、網路差有 offline 保底、nav 三層 fallback 不開天窗。S5 安全拒絕（proven）穩收尾，把「具身機器人懂安全邊界」講足；「能力階梯 + 誠實」當敘事主軸（呼應撞牆風險）。
- **誠實風險（必須對外照講）**：
  - **S1 nav 今天剛撞牆** → n=3 未過前禁講「自主短距移動/可靠導航」，最壞退純影片。
  - **confirm 目標路徑未驗** → 現場先試 thumbs_up→OK→wiggle、失敗退已驗的 peace→OK→WeGo；對外只講「比 OK 確認後執行」。
  - **face proven 僅一次且脆** → 發表日早上重驗，不行退 generic greet。
- **不可講**：「五幕指揮全自動」「狀態機全面接管」（ISM 2e/2f 未做）；nav F1–F10 全部封口。
- **最壞保底**：全 flag 退（`demo_phase=all`+`ism off`+offline off）= 6/10/6/12 已驗過的現行為 + demo snapshot 影片。

---

## 14. 決策表（禮拜一前必做 / 時間夠才做 / 不做）

> 三桶分類。「禮拜一前必做」= 不做則五幕跑不順或會 overclaim/翻車；「時間夠才做」= 加分但非必要；「不做」= 明確排除（forbidden 或 post-6/18）。

### 🔴 禮拜一前必做（P0 — 不做則 demo 不穩 / 會 overclaim）

| 項 | 為什麼必做 | 類型 | 子計畫 |
|----|-----------|:----:|--------|
| Step 0 清場（Go2 停穩 + `pawai demo stop`） | 撞擊後殘留 stack/active goal，brain 起不來 | `[J]`+`[G]` | runbook §8.0 |
| conductor C1+C2（五幕詞彙 + 切換清理） | 「每幕只觸發該幕功能」「換幕不污染」的核心 | `[SW]` | conductor |
| fallback F1+F2（timeout 收緊） | 網路差不卡 60s/15s timeout（demo 最常翻車點） | `[SW]` | fallback |
| fallback F3（五幕 canned + WAV pre-render） | 五幕 offline 保底台詞、秒回 | `[SW]`+`[J]` | fallback |
| runbook R（五幕骨幹 + 三洞段 + 平台表） | 操作員照順序跑完的依據；誠實分級 | `[SW]` | runbook |
| s1-nav N1+N2+N3（indoor_tight + 朝向校正 + **0.3m n=3 重驗**） | 撞牆根因；不過則 S1 退影片（仍要做到能決策退不退） | `[J]`+`[G]` | s1-nav |
| H-face（face_db 衛生 + re-enroll 重驗） | S2 具名問候脆、proven 僅一次 | `[J]` | runbook §8.6.1 |
| H-conductor confirm 差異重驗 | S4 目標路徑未驗，需確認哪條會動 Go2 | `[G]` | conductor H-C3 |
| Lane 3 B4（face npz 修）| delete/rebuild 不生效會讓 face 衛生 SOP 失效 | `[SW]` | Lane 3 T3-5 |
| 6/17 回穩日 `pawai smoke full` + 彩排 + tag | 發表日狀態鎖定、byte-identical 退路驗證 | `[J]` | 回穩日 |

### 🟡 時間夠才做（P1 — 加分，可 post-6/18）

| 項 | 加分點 | 類型 | 子計畫 |
|----|--------|:----:|--------|
| conductor C3（`pawai demo phase` CLI） | 切幕免記 `ros2 param set`；落地前用 param（可接受） | `[SW]` | conductor/Lane 3 |
| conductor C4 + Studio phase chip | 觀眾/操作員看得到「第幾幕」；落地前 `ros2 param get` | `[SW]` | conductor |
| fallback F4（runtime offline mode 開關） | 不重啟切 offline；落地前用 env override（proven 可接受） | `[SW]` | fallback |
| Lane 3 S（`pawai status` brain 區塊） | 一眼看 shadow/phase/flag；落地前逐項 `ros2 param get` | `[SW]`+`[J]` | Lane 3 |
| s1-nav H4（N6 stop-resume operator-confirm） | 解鎖 claim S3；非 S1 主線必要 | `[G]` | s1-nav |
| s1-nav H5（N5 patrol 單圈 prototype） | 解鎖 claim S7；routes 需先重錄(N1) | `[G]` | s1-nav |

### ⚫ 不做（明確排除 — forbidden / post-6/18）

| 項 | 為什麼不做 |
|----|-----------|
| 換 LLM/TTS/ASR/vision 模型當主線 | forbidden；6/18 前不換（B-4） |
| 完整 benchmark dashboard / vision 模型 A/B 矩陣日當主線 | forbidden；B-3 至多選一提前、否則 post-6/18 |
| live SLAM 主線 / autonomous approach Roy / 動態繞障 | forbidden；nav F1–F6 永久封口 |
| 1.0m+ 連續導航進 S1 主線 | C3 wired_only、AMCL 黃帶卡死，從未成功 |
| 大改 Studio UI / 完整重寫 CLI | forbidden；只加唯讀 chip + additive subcommand |
| ISM 2e/2f/2g（社交 candidate 化 / 優先序全接管 / utterance_id） | post-6/18（6/12 分歧樣本證明需 soak 收斂，Lane 1 forbidden） |
| source-trust enforcement / auth enforcement flip 進發表日 | post-6/18（B-2/B-6 視 HITL，預設 default-off） |

---

> **一句話總結**：六個 P0（清場、conductor 切幕+清理、timeout 收緊、五幕 canned、s1 nav 三步重驗、runbook + 回穩日）做完，五幕禮拜一前能照順序跑、網路差有保底、nav 不過退影片、對外不 overclaim。其餘是加分或明確不做。
