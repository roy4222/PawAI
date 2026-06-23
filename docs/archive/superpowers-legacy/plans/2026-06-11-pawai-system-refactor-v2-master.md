# PawAI System Refactor v2 — Master Plan

> **日期**：2026-06-11
> **Status**：PLANNED
> **性質**：v2 總計畫（master）。承接並延伸 [`2026-06-10-post-demo-refactor-master-plan.md`](2026-06-10-post-demo-refactor-master-plan.md)——該文件仍是**系統重構 Phase 1 的權威歷史紀錄與原則來源**（重構原則 §3、D1-D6 拍板 §4、ISM 設計約束 §7 持續有效）；本文件接手「系統 Phase 1 之後」的總路線，統領四份 phase plan（見 §Scope）。
> **上游**：[audit 主報告](../specs/2026-06-10-pawai-architecture-audit.md)、[Foundation Closure Report](../../runbook/2026-06-11-refactor-foundation-closure-report.md)、[demo snapshot](../../pawai-demo/2026-06-10-demo-snapshot.md)、[`references/project-status.md`](../../../references/project-status.md) 6/11 段。

---

> **⚠️ 命名消歧（全套件適用）**
>
> | 名稱 | 指什麼 | 範圍 |
> |---|---|---|
> | **系統重構 Phase 1-5** | 本 v2 套件的大階段（Phase 1 已完成；Phase 2-5 = 本文件統領的四份 phase plan） | 全系統 |
> | **ISM Phase 0-3** | `interaction_state.py` 狀態機自己的實作階段（0 純模組 / 1 shadow / 2 逐 gate family / 3 權威化），定義在 [ISM plan](2026-06-11-plan-ism-interaction-state-machine.md) | Brain 內 |
> | **安全 hardening P0-P3** | security hardening plan 的優先級標籤（如 hardening P0-2 = foxglove clientPublish） | 安全項 |
> | **Phase 2B** | 系統 Phase 2 的落盤/匯出子段（trace JSONL 落盤 + export endpoint） | 系統 Phase 2 內 |
>
> 內文引用一律寫全名（「ISM Phase 1 shadow」「hardening P0-2」「系統 Phase 3」），**禁止裸寫 Phase N**。

---

## Goal

### 北極星（一句話）

> **把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台。**

### 最終架構

```
Perception Nodes（face / vision(gesture+pose) / object / speech / nav state）
        │  各自的原始 topic 事件
        ▼
Perception Router ──── 標準化事件（PerceptionEvent，唯一解析點）
        ▼
Interaction State Machine（ISM）──── 狀態裁決（candidate → decision，8 態 + watchdog）
        ▼
Policy + Safety Layer ──── 優先序鐵律：safety > explicit command > confirm > 自發社交
        ▼
Skill Executor（interaction_executive 唯一 actuator 出口；SkillContract / banned_api）
        ▼
Trace + Evidence（/brain/trace → gateway JSONL 落盤 → Studio / CLI 呈現與匯出）

三個支撐系統：
  PawAI CLI v2      ── deploy / demo start / smoke / face / evidence / status
  PawAI Studio v2   ── 操作台 + 證據中心
  pawai_contracts   ── skills / events / trace / policy / zh 表的共用真相（ROS-free）
```

### 七個子系統理想狀態

**1. Brain v2**
事件 → Router → ISM → Policy → Executor → Trace 單向流。感知只產生 candidate、永不直接改狀態；安全最高優先、可從任何狀態搶入 `SAFETY_HOLD`；confirm 在飛時其他事件 queue-or-suppress-with-trace、不黑洞不卡死；TTS 在講時社交候選讓路、不被搶話；每個 suppressed 決策有 gate + reason；每個 active interaction 有 watchdog、不永久卡（吸收 6/9 stranger plan 卡死全系統教訓）；不信任 wire 自稱 `source`——進 `EXECUTING` 只有受信任通道的 explicit command 或已解析的 confirm OK。

**2. Studio v2**
操作台 + 證據中心合一：decision timeline（每事件 decision_id 串鏈）、「為什麼沒反應」一鍵回答、感知 evidence（debug image / 事件流）、nav / safety / health 即時面板、session 報告匯出、annotated clip 產出；operator mode 與 presentation mode 分離；**不是任意瀏覽器都能控 Go2**（gateway 授權後才有控制權）。（落點：suppressed-reason 呈現第一刀＝系統 Phase 2 first slice；decision timeline 完整版、session 報告匯出、annotated clip＝**系統 Phase 2 的 2B post-6/18 段**——各自獨立 task/PR，以 T2B-1 落盤 + T2B-2 export 為基座，annotated clip 消費系統 Phase 3 W4 產物。）

**3. CLI v2**
`doctor` / `status` / `demo` / `smoke brain|vision|object|nav|full` / `face list|enroll|delete|rebuild|test` / `evidence pull` / `deploy` 全套；錯誤訊息清楚可照做；Win / Mac / WSL 三平台可安裝；**不假成功**（healthcheck hard-gate、起 demo 後驗 process 數）、**不洗 `.env`**（audited rsync + exclude 契約）。

**4. Perception v2**
每個模型有 recall / precision / FPS / latency / RAM / GPU / 溫度功耗的 benchmark 數據；YOLO26n / YOLO26s / high-res / seg / pose 候選全部有數據再決策（不憑感覺換模型）；Supervision 只做 offline evidence（EVIDENCE only，不進 runtime）；固定測試矩陣（距離 × 物件 × 光照）可重跑；色彩判斷與 open-vocab 能力有明確邊界宣告。

**5. Robot Control v2**
gateway 預設 localhost bind + 強制 token；foxglove clientPublish 降權；DDS 面收斂；`/webrtc_req` whitelist；nav action 授權；cmd_vel 來源鏈路清楚（twist_mux 優先序有文件有測試）；**所有能讓 Go2 動的入口都有 owner 和 guard**。

**6. Navigation v2**
capability ladder 分級：`wired_only` / `hardware_proven` / `demo_ready` / `research_prototype`，每級宣稱對應 HITL 證據；短距移動、正前 safe-stop、stop-resume 各有實機證據與限制條款；D435+LiDAR fusion 是研究線（research_prototype），不亂 claim。

**7. Evidence / Trace 系統**
每個能力可回答七問：誰發的（source + decision_id）／為何接受／為何 suppressed／哪個 gate 擋的／當時系統看到什麼（感知快照）／Go2 有沒有真的動（actuator 回報）／是否 hardware proven（HITL 紀錄）。單一真相 = pawai_contracts trace schema + gateway JSONL（D5：Brain 只發射、Studio 只落盤呈現、CLI 只讀取匯出）。

### 六條最終成功標準

1. **可部署**：deploy / demo start / status 可信、不假成功。
2. **可觀測**：出問題先看 trace / evidence，不用猜。
3. **可擴展**：新增感知或 skill 不用到處改 callback。
4. **可驗證**：每能力有 CI / smoke / HITL / evidence 至少一層覆蓋。
5. **安全**：未授權者不能讓 Go2 動；危險動作多層防護。
6. **可交接**：隊友照 CLI / Studio / runbook 即可操作。

（逐條可驗收化見 §Done criteria。）

---

## Scope

本文件管的是**系統 Phase 2-5 的總路線、依賴閘門、治理與凍結約束**。可執行細節在四份 phase plan；本文件不含實作步驟。

### 系統 Phase 1 完成清單（已封閉的基線，證據齊）

| 項 | 內容 | 證據 |
|---|---|---|
| Demo snapshot freeze | demo 凍結文件 + 回滾點 | tag `demo-2026-06-snapshot`；baseline tag `post-demo-refactor-baseline-2026-06-10` = `b1f0bc4` |
| Architecture audit | 全 repo 盤點 | 99 findings、98 成立（findings ledger 逐條查證） |
| Security audit | S0 安全研究三件套 docs | 已 commit（hardening plan 的上游） |
| Perception 研究 | 7 線研究定案（supervision / PINTO / object 升級等） | `objdet-upgrade-synthesis-result` 等，verdict = BLOCKED_BY_HARDWARE_TEST |
| Plan A CI guardrails | fast-gate 多 invocation + container + hook | PR #143-#149 |
| Plan B CLI v2 第一刀 | audited deploy + healthcheck hard-gate | PR #151 |
| Plan C pawai_contracts | skill_contract / zh / llm_policy / trace_schema 抽取 | PR #152 |
| Plan D Brain Router Phase 0 | perception_router 雙路徑（預設 True） | PR #153 |
| Plan E Brain Trace v1 | `/brain/trace` + decision_id + suppressed trace | PR #154 |
| B-E 上機 smoke | 4/4 通過 | 6/11 晚實機 |
| Gap 1 / Gap 2 | deploy 依賴閉包 / healthcheck pane+grace | PR #155 / #156 |
| S0-1 freeze-safe | CI/hook hardening（secret guard + permissions） | PR #157 |
| S0-2 freeze-safe | gateway access-control 機制層（env-gated **預設關** = byte-identical） | PR #158 |
| ISM 詳細 plan | 施工圖（遵 master plan §7 八條約束） | commit `5e5795a` |
| ISM Phase 0 | `interaction_state.py` 純模組、33 測試、**未接 runtime** | PR #159 |
| Foundation Closure Smoke | 真機 9/9 → **地基封閉** | [`docs/runbook/2026-06-11-refactor-foundation-closure-report.md`](../../runbook/2026-06-11-refactor-foundation-closure-report.md) |

### 系統 Phase 2-5 一頁式摘要

#### 系統 Phase 2 — Core Brain / Ops Refactor
→ [`2026-06-11-phase2-core-brain-ops-refactor.md`](2026-06-11-phase2-core-brain-ops-refactor.md)

把 Brain 的隱式仲裁換成顯式 ISM，並讓「為什麼沒反應」變成可看的證據。三條線：① **ISM 接入**——按 [ISM plan](2026-06-11-plan-ism-interaction-state-machine.md) 走 ISM Phase 1 shadow（餵真實事件、發 STATE_TRANSITION trace、與 legacy 裁決並排比對、**不改行為**）→ ISM Phase 2 逐 gate family flag-gated 切換 → ISM Phase 3 權威化；② **Studio Evidence Center**——decision timeline、suppressed 原因呈現、session 報告，吃 Plan E trace + gateway JSONL；③ **CLI smoke / evidence 第一刀**——`pawai smoke brain` 與 `evidence pull` 最小可用。**6/18 前只做 ISM Phase 1 shadow + evidence + 零 runtime 行為的 CLI 工具（`pawai smoke brain` / `evidence pull`）（additive-only、預設關）；一切 staged enable（`ism_enabled` 翻 default、gate family 切換）全部 6/18 後**。trace PII 邊界（hardening P3-1）需在 Phase 2B（落盤/匯出）動工前由 Roy 拍板。

#### 系統 Phase 3 — Vision Evidence + Model Benchmark
→ [`2026-06-11-phase3-vision-evidence-model-benchmark.md`](2026-06-11-phase3-vision-evidence-model-benchmark.md)

用數據決定感知模型去留，不再憑印象。節奏：**先一週 WSL offline spike**（Supervision offline evidence pipeline、Roy 提供的 object JSONL + demo 錄影做離線重放與標注、固定測試矩陣定稿）→ **再一個上機矩陣日**（Jetson 實測 A conf0.35→0.30 / B s@640 / C n@960+720p / D s@960 / E YOLOE vocab38 條件項 + Lab-LUT 色彩，量 recall/FPS/溫度功耗）。產出 = 每候選一行數據 + KEEP/SWITCH verdict；verdict GO 後進入階段 3-4 runtime 落地——換模/換參 PR + contract v2.5→v2.6 一次合併 bump + 色彩方案 A node（全屬行為變更，整段 post-6/18）。**blocked on Roy：object JSONL + demo 錄影素材交付**；WSL offline 部分與系統 Phase 2 檔案面不重疊、素材到位即可並行。

#### 系統 Phase 4 — Robot Control / Nav Hardening
→ [`2026-06-11-phase4-robot-control-nav-hardening.md`](2026-06-11-phase4-robot-control-nav-hardening.md)

吸收 security hardening plan 的**控制面項**：gateway secure-default flip（bind 127.0.0.1 + 強制 token + 前端/probe token wiring）、foxglove clientPublish 降權（hardening P0-2，Roy 決策——會碰 nav initialpose 工作流）、DDS 收斂、`/webrtc_req` whitelist、nav action 授權、cmd_vel 來源治理；加上 **nav capability ladder** 正式化（wired_only / hardware_proven / demo_ready / research_prototype，逐級綁 HITL 證據；含 S1 簿記、stop-resume 終局、orphan-goal client fix）。**全段 post-6/18**（碰凍結腳本與 demo 工作流）+ **重 HITL**（每項控制面變更需實機回歸 session 證明 Studio/nav/demo 流程不破）。

#### 系統 Phase 5 — Productization / CLI Cleanup
→ [`2026-06-11-phase5-productization-cli-cleanup.md`](2026-06-11-phase5-productization-cli-cleanup.md)

收尾與產品化：CLI v2 完整化（Typer 全命令、error registry、Win/Mac/WSL packaging）、Studio v2 完整版收尾（mock parity / Plan A-B 假開關 / gesture_enabled 真值回讀 / map meta / operator-presentation mode＝phase 5 plan T5C-5；**decision timeline 完整版、session 報告匯出、annotated clip 的落點在系統 Phase 2 的 2B post-6/18 段，非本 phase**，annotated clip 消費系統 Phase 3 W4 evidence 產物）、dead code 歸檔批次（一套件一 PR + zero-consumer grep 證據）、docs 收斂、HITL 證據治理（`docs/hitl/` 與 raw artifacts 粒度）、shim 拆除與 legacy 刪除。**拆 shim / 刪 legacy 的硬前置 = ISM Phase 3 權威化完成**（ISM Phase 3 只翻 default + 停用 legacy 裁決路徑、不刪碼；19 個 `_suppressed` 死碼刪除統一在本 phase 執行）。

### 依賴閘門圖

```
系統 Phase 1（已完成；地基封閉 2026-06-11 真機 9/9）
   │
   ├──────────────────────────► 系統 Phase 2（Core Brain/Ops）
   │                              ├─ 現在可動：ISM Phase 1 shadow + Evidence（additive-only、預設關）
   │                              │    └─ gate：trace PII 邊界（hardening P3-1，A-4）+ export auth 形態（A-11）Roy 雙拍板 → Phase 2B 落盤/匯出
   │                              └─ 6/18 後：ISM Phase 2 gate family 切換 → ISM Phase 3 權威化
   │
   ├──[gate：Roy 素材（object JSONL + demo 錄影）]──► 系統 Phase 3（Vision Evidence + Benchmark）
   │                              ├─ WSL offline spike：與系統 Phase 2 檔案面不重疊 → 可並行
   │                              └─ [gate：Jetson 上機日排程 + HITL] ──► 上機矩陣日 → 模型 verdict
   │
   └──[gate：6/18 解凍 + Roy 決策批次 + 實機回歸 session]──► 系統 Phase 4（Robot Control / Nav Hardening）
                                  │
                                  ▼
[gate：ISM Phase 3 權威化完成] ──► 系統 Phase 5（Productization：拆 shim / 刪 legacy / packaging）
（系統 Phase 5 的非 shim 部分——CLI packaging、docs、dead code——可在系統 Phase 4 期間穿插）
```

### 閘門表

| 閘門 | 解鎖對象 | 條件 | 負責 |
|---|---|---|---|
| G1 地基封閉 | 系統 Phase 2 pre-6/18 部分 | ✅ 已達成（closure smoke 9/9） | — |
| G2 trace PII 邊界 | Phase 2B（trace 落盤/匯出擴張） | Roy 拍板 hardening P3-1（A-4）+ export auth 形態（A-11）雙拍板 | Roy 決策 |
| G3 Roy 素材 | 系統 Phase 3 WSL offline spike | object JSONL + demo 錄影交付 | Roy |
| G4 上機矩陣日 | 系統 Phase 3 上機部分 | Jetson 排程 + Roy HITL 在場 | Roy HITL |
| G5 6/18 解凍 | ISM staged enable、系統 Phase 4 全段 | 6/18 期末發表結束 + 凍結解除宣告 | Roy 決策 |
| G6 系統 Phase 4 決策批次 | 系統 Phase 4 各控制面項 | foxglove / gateway flip / stop-resume 等逐條拍板（見附錄 A） | Roy 決策 |
| G7 ISM Phase 3 權威化 | 系統 Phase 5 拆 shim / 刪 legacy | `ism_enabled` 翻 default + legacy 裁決路徑停用（flag-off 保留、**不刪碼**——19 個 `_suppressed` 死碼刪除統一歸系統 Phase 5 T5B-3）+ 回歸全綠 | Codex + Fable + Roy HITL |

---

## Forbidden scope

1. **不做一次性大爆炸重寫**（master plan §1 禁令延續）——一層一層換，不拆承重牆；`interaction_executive_node` 唯一 actuator 出口、SafetyLayer、SkillContract、PendingConfirm、StopMove 路由、twist_mux 優先序**不推倒**。
2. **凍結期（至 6/18）不碰 demo 參數**：`executive.yaml`、`scripts/start_full_demo_tmux.sh`、`.claude/skills/`，除 Roy 明示授權。
3. **跨 phase 混線**：系統 Phase 2 期間不做 Vision benchmark 上機（那是系統 Phase 3 上機日）、不做 Nav/控制面 hardening（那是系統 Phase 4）；單一 PR 不橫跨兩個 phase 的 scope。
4. **不繞過 HITL gate 宣稱能力**：任何硬體能力宣稱必過 HITL；demo snapshot 的 forbidden claims 對所有對外材料持續有效。
5. 本 master 文件本身不產生任何 code 變更；它只統領 phase plan。

---

## Inputs / prerequisite docs

| 文件 | 角色 |
|---|---|
| [`2026-06-10-post-demo-refactor-master-plan.md`](2026-06-10-post-demo-refactor-master-plan.md) | 系統 Phase 1 權威紀錄；重構原則 §3 / 拍板 D1-D6 §4 / ISM 約束 §7 的來源 |
| [`docs/runbook/2026-06-11-refactor-foundation-closure-report.md`](../../runbook/2026-06-11-refactor-foundation-closure-report.md) | 地基封閉證據（真機 9/9） |
| [`docs/pawai-demo/2026-06-10-demo-snapshot.md`](../../pawai-demo/2026-06-10-demo-snapshot.md) | demo 回滾點 + forbidden claims 真相源 |
| [`references/project-status.md`](../../../references/project-status.md) | 每日系統狀態（6/10-6/11 段 = 系統 Phase 1 經過） |
| [`2026-06-11-plan-ism-interaction-state-machine.md`](2026-06-11-plan-ism-interaction-state-machine.md) | ISM Phase 0-3 施工圖（系統 Phase 2 的核心子計畫） |
| [`docs/superpowers/specs/2026-06-10-pawai-architecture-audit.md`](../specs/2026-06-10-pawai-architecture-audit.md) | 99 findings audit 主報告 |
| [`docs/security/2026-06-11-pawai-hardening-plan.md`](../../security/2026-06-11-pawai-hardening-plan.md) | hardening P0-P3 標籤定義 + 系統 Phase 4 控制面項來源 |
| 四份 phase plan（本文件 §Scope 連結） | 系統 Phase 2-5 可執行細節 |

---

## Tasks

### 執行模式（全 phase 繼承）

- **Fable** 寫 spec / plan + review；**Codex** 串行實作（一次一 plan、每 task 一 commit）；**Roy** HITL 驗收 + 決策拍板。
- 每 plan 一 PR（或依 phase plan 內切分）；CI 紅綠驗證（先證明會抓、再證明過）；merge 一律 admin rebase。
- main 永遠可部署；搬家與行為變更分開 PR；trace / 觀測 additive-only；觀測類與政策類永不同 PR。
- HITL 是真實驗收——測試綠 ≠ 真機可用。

### 治理任務清單

| # | Task | 載體 | 驗證方式 |
|---|---|---|---|
| M1 | 四份 phase plan 成文 + 與本 master 摘要一致性檢查 | Fable 撰寫 spec | 每份含十固定章節 + 消歧框；Goal/Scope 與本文件 §Scope 摘要逐字級一致 |
| M2 | 系統 Phase 2 pre-6/18 部分開工（ISM Phase 1 shadow + Evidence 第一刀） | Codex 實作（依 phase 2 plan） | CI 綠 + shadow 預設關 byte-identical + Jetson shadow soak |
| M3 | G2 trace PII 邊界拍板（Phase 2B 前置） | Roy 決策 | 決策記入附錄 A + phase 2 plan 更新 |
| M4 | G3 素材交付（object JSONL + demo 錄影）→ 系統 Phase 3 WSL spike 開工 | Roy（素材）→ Codex 實作 | 素材清單核對 + offline pipeline 可重放 |
| M5 | G4 上機矩陣日排程 + 執行 | Roy HITL | 矩陣 CSV + 溫度功耗紀錄 + verdict 文件 |
| M6 | G5/G6：6/18 解凍宣告 + 系統 Phase 4 決策批次（附錄 A 逐條） | Roy 決策 | 決策登記簿逐條標 RESOLVED + phase 4 plan 解鎖 |
| M7 | 系統 Phase 4 開工（控制面 hardening + nav ladder） | Codex 實作 + Roy HITL | 每項變更附實機回歸 session 紀錄 |
| M8 | G7：ISM Phase 3 權威化 → 系統 Phase 5 拆 shim 解鎖 | Codex 實作 + Fable review + Roy HITL | `ism_enabled` default 翻轉 PR + 回歸全綠 + legacy 停用證據（刪碼歸系統 Phase 5 T5B-3） |
| M9 | 系統 Phase 5 收尾（packaging / dead code / docs / HITL 治理） | Codex 實作 + Fable review | 跨平台安裝驗證 + zero-consumer grep + runbook 隊友走查 |
| M10 | 決策登記簿維護（附錄 A），每次拍板回寫 | Fable 撰寫 | 登記簿無 stale OPEN 項超過對應 gate 時點 |

---

## Tests / verification

各 phase 的 exit gate 彙總（細節在各 phase plan 的 Tests 章節）：

| Phase | Exit gate |
|---|---|
| 系統 Phase 2 | ① ISM Phase 1 shadow 比對數據落地（shadow vs legacy 裁決差異報告）；② Studio Evidence Center 能回答「為什麼沒反應」（suppressed gate+reason 可視）；③ `pawai smoke brain` / `evidence pull` 可用；④ post-6/18 staged enable 後：`test_brain_rules` 73 條 + 6/9 場景重演（ALERT 卡住 → cup/greet 被 queue/suppressed-with-trace 而非黑洞）全綠 + Jetson soak 無回歸 |
| 系統 Phase 3 | ① 固定測試矩陣 A-D + Lab-LUT 必備 recall/FPS/RAM/溫度功耗數據，E 為 W2 過門檻之條件項（NO_GO 時以 W2 replay 數據結案）；② KEEP/SWITCH verdict 文件化且引用數據；③ 不留「未測但已宣稱」項；④ verdict GO 的線完成階段 3-4 runtime 落地（換模 PR + contract v2.6 bump，post-6/18；NO_GO 線不進 contract） |
| 系統 Phase 4 | ① 所有能讓 Go2 動的入口列表化且各有 owner+guard；② gateway secure-default ON 後 Studio / probe / demo 流程實機全綠；③ nav capability ladder 每級綁 HITL 證據文件；④ 每項控制面變更附實機回歸 session |
| 系統 Phase 5 | ① shim 移除後全 repo zero-import 殘留（grep 證據）；② CLI Win/Mac/WSL 安裝驗證；③ runbook 隊友走查通過（不需口頭支援）；④ dead code 歸檔 PR 全帶 zero-consumer 證據 |

通用：每 PR CI 綠 + 紅綠驗證；行為變更 PR 附 before/after 證據；硬體宣稱附 HITL 紀錄。

---

## Jetson / Go2 requirement

| Phase | Jetson | Go2 | 說明 |
|---|---|---|---|
| 系統 Phase 2 | **需要**（shadow soak + smoke 要真實事件流） | 低度（多數驗證不需 motion；staged enable 後的回歸 smoke 需 Go2 在場） | shadow 觀測必須吃真感知事件，WSL 單測不夠 |
| 系統 Phase 3 | WSL offline spike 不需；**上機矩陣日需要**（D435 + 溫度功耗量測） | **需要**（D435 機上視角 + 家用場地擺位；motion 不需） | 一個專屬上機日，Roy HITL 在場 |
| 系統 Phase 4 | **全段需要** | **全段需要** | 控制面 + nav 全是實機回歸；HITL 最重的 phase |
| 系統 Phase 5 | 部分（smoke 驗收、runbook 走查需 Jetson） | 低度（演示性驗收） | packaging 驗證在 Win/Mac/WSL 三平台 |

---

## Done criteria

六條成功標準逐條可驗收化：

1. **可部署**：`pawai jetson deploy` 前後 `.env` md5 不變；`pawai demo start` healthcheck hard-gate（無假成功，process 數可驗）；`pawai demo stop` 後殘留 demo 進程 = 0；`pawai status` 反映真實 lock/driver/網路。（closure smoke 九項常態化為可重跑 smoke。）
2. **可觀測**：任一「PawAI 沒反應」場景，操作者可在 Studio Evidence Center 或 CLI trace 內指出 decision_id + gate + reason，**不需讀 code 或猜**；每個 suppressed 有 trace。
3. **可擴展**：新增一個感知事件或 skill 的 diff 只動 router 表 + policy 表 + pawai_contracts，不觸碰 brain_node callback 堆；以一次實際新增驗證。
4. **可驗證**：capability claim matrix 每能力標注 CI / smoke / HITL / evidence 至少一層的具體 artifact 路徑；無 evidence 的能力標 insufficient_data，不對外宣稱。
5. **安全**：gateway 預設 localhost+token、`/webrtc_req` whitelist、nav action 授權、foxglove 降權落地後——未授權者從任何入口都不能讓 Go2 動（入口清單逐項實測）；危險動作有 banned_api + SafetyLayer + confirm 多層防護且各有測試。
6. **可交接**：隊友（非 Roy）照 runbook 完成 deploy → demo start → smoke → evidence pull 全流程，過程零口頭支援；走查紀錄入 docs。

全部六條達成 + 四個 phase exit gate 全過 = v2 套件完成。

---

## Rollback / fallback

- **全域回滾點**：tag `post-demo-refactor-baseline-2026-06-10`（= `b1f0bc4`）；demo 行為回滾點 tag `demo-2026-06-snapshot` + snapshot 文件。
- **Per-phase 紀律**：每刀小 PR、可單 PR revert；行為變更一律 flag-gated（`ism_enabled`、`ism_shadow_enabled`、gateway env-gated access control、`perception_router_enabled` 等）且**預設 = 現行為**，翻 default 是獨立 PR。
- **ISM 接入 fallback**：`ism_enabled=false` 隨時退回 v1 legacy 裁決（ISM plan §9 風險與 rollback）；shadow 模式本身零行為影響。
- **系統 Phase 4 控制面 fallback**：gateway secure flip 為 env 開關，翻 default 前保留 default-off 一鍵退回；foxglove 變更附原 launch 設定回復步驟。
- **系統 Phase 5 拆 shim**：刪除前 tag；git history 即歸檔，單 PR revert 可復原。
- main 出現紅燈 = 停止新刀、先修復或 revert，不疊加。

---

## 6/18 freeze constraint

全域凍結表（至 2026-06-18 期末發表結束；解凍 = G5）：

| 項 | 凍結狀態 | 解凍條件 |
|---|---|---|
| `executive.yaml` | **禁改**（除 Roy 明示授權） | 6/18 後 + 測試 |
| `scripts/start_full_demo_tmux.sh` | **禁改**（除 Roy 明示授權） | 6/18 後 + 測試 |
| `.claude/skills/` | **禁改**（除 Roy 明示授權） | 6/18 後 |
| gateway secure-default flip（bind+token 強制 + 前端/probe wiring） | 機制已入庫（PR #158）但**預設關**；凍結期不翻 | 6/18 後 + Roy 拍板時點（附錄 A-3） |
| foxglove clientPublish 降權（hardening P0-2） | **凍結**（會斷 nav initialpose 工作流 + 碰凍結腳本） | 6/18 後 + Roy 決策（附錄 A-2） |
| `ism_enabled` 預設 | **保持 false**；凍結期只允許 shadow（`ism_shadow_enabled`，additive-only） | ISM Phase 2 staged enable 全在 6/18 後 |
| demo snapshot forbidden claims | **持續有效**，對所有對外材料（簡報/影片/docs） | 個別 claim 取得新 HITL 證據後逐條解除 |

凍結期可動的 = additive-only、預設關、byte-identical 驗證可證明零行為變更的工作（系統 Phase 2 pre-6/18 部分、系統 Phase 3 WSL offline 部分、所有 docs/plan）。

---

## 附錄 A：Roy 決策登記簿

| # | 決策項 | 影響 phase | 狀態 |
|---|---|---|---|
| A-1 | S1 錄製方式簿記（最後用 0.5m / initialpose / 遙控輔助哪個錄成）→ 決定 nav ladder 上 operator-confirm 迴圈標 `hardware_proven` 還是 `wired_only` | 系統 Phase 4 | OPEN |
| A-2 | foxglove clientPublish 降權（hardening P0-2；會斷 nav initialpose 工作流） | 系統 Phase 4 | OPEN |
| A-3 | gateway secure-default flip 時點（機制已備，何時翻 + token 發放流程） | 系統 Phase 4 | OPEN |
| A-4 | trace PII 邊界（hardening P3-1；**Phase 2B 動工前要決**） | 系統 Phase 2 | **RESOLVED**（2026-06-12 AFK 指令）：保守預設——safe summary 可顯示、name/transcript/image path/full text 預設 private；磁碟全量僅本機、離機路徑一律 redact。落地 `trace_store.redact_trace_event()`；記錄見 phase 2 plan 附錄 |

| A-5 | dead-code 歸檔原則（scripts → `scripts/archive/`；套件內模組 → git 刪除；不放 `docs/archive/`） | 系統 Phase 5 | OPEN |
| A-6 | HITL 證據治理粒度（`docs/hitl/` 新樹 + raw artifacts 進 git 的大小門檻） | 系統 Phase 3 / 5 | OPEN |
| A-7 | Studio operator enforcement 強度（token / 第二 port / 信任內網） | 系統 Phase 2（Evidence Center）/ 4 | OPEN |
| A-8 | Ollama 本地 LLM 層去留（主線收編 / 留 legacy / 放棄離線智能） | 系統 Phase 5 | OPEN |
| A-9 | stop-resume 終局（operator-confirm 永久化 vs `resume_policy=auto` 留大場地）+ 安全層投資方向（自製 reactive_stop 強化 vs nav2_collision_monitor） | 系統 Phase 4 | OPEN |
| A-10 | object A/B + pose observer 第一場 HITL session 排期 | 系統 Phase 3 | OPEN |
| A-11 | export endpoint auth 形態（POST vs GET＋例外 token-gate；phase 2 T2B-0②，**T2B-1 落盤動工前要決**，pre-6/18 時效） | 系統 Phase 2 | **RESOLVED**（2026-06-12 AFK 指令）：GET＋例外 token-gate——auth-on 時 GET export 也要 token（401）；full export 在 token 系統關閉時一律 403。落地 `auth.export_access()`；記錄見 phase 2 plan 附錄 |
| A-12 | lane scripts 永久位置（audit Open Question 11：CLI package data vs `scripts/lanes/`；phase 5 T5A-7 搬家目的地） | 系統 Phase 5 | OPEN |
| A-13 | Studio Plan A/B 假開關處置（phase 5 T5C-5②：接線 publish `/brain/plan_mode` 或移除 UI，二選一） | 系統 Phase 5 | OPEN |
| A-14 | 矩陣勝者採用 + E 存廢 + 色彩 GO/NO_GO verdict 採用（phase 3 V4-1，依階段 3-3 數據） | 系統 Phase 3 | OPEN |

每次拍板：本表標 RESOLVED + 一行結論 + 回寫對應 phase plan。
