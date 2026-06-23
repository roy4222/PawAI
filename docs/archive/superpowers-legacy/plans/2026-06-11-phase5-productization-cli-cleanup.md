# 系統 Phase 5：Productization / CLI Cleanup（5A CLI v2 完整化 + 5B Dead Code 歸檔 + 5C Contracts/Studio 收尾 + 5D Docs/治理）

> **日期**：2026-06-11　**狀態**：PLANNED
> **上游文件**：
> - v2 Master plan：[`2026-06-11-pawai-system-refactor-v2-master.md`](2026-06-11-pawai-system-refactor-v2-master.md)（閘門 G7、里程碑 M8/M9、附錄 A 決策登記簿 A-5/A-6/A-7/A-8）
> - Plan B（CLI v2 第一刀）：[`2026-06-10-plan-b-cli-v2-first-slice.md`](2026-06-10-plan-b-cli-v2-first-slice.md)——其 Forbidden scope 明文「不做 Typer/Rich 遷移（第 2 刀）」，本 phase 即解除該保留
> - Plan C（pawai_contracts 抽取）：[`2026-06-10-plan-c-pawai-contracts-extraction.md`](2026-06-10-plan-c-pawai-contracts-extraction.md)——其 shim docstring 明文「Remove this shim only after a dedicated migration PR rewrites all imports (post-ISM)」，本 phase 即該 migration PR
> - Plan D（Router Phase 0）：[`2026-06-10-plan-d-brain-router-phase0.md`](2026-06-10-plan-d-brain-router-phase0.md)——`PerceptionEvent` 明文「等第二個消費者再升格進 pawai_contracts」，ISM/Trace 落地後條件成立
> - ISM plan：[`2026-06-11-plan-ism-interaction-state-machine.md`](2026-06-11-plan-ism-interaction-state-machine.md)（ISM Phase 3 權威化 = 本 phase 拆 shim/刪 legacy 的硬前置）
> - Findings 真相源：[audit 主報告](../specs/2026-06-10-pawai-architecture-audit.md) + [findings ledger](../specs/2026-06-10-pawai-architecture-findings-ledger.md)（本文引用之 BRAIN-x / CLI-x / STUDIO-x / DEVOPS-x / FACE-5 / VISION-4 / OBJECT-1/9 逐條有證據）

## 命名消歧（必讀）

本套件有三套互不相干的編號，內文一律寫全名、禁止裸寫「Phase N」：

| 編號系統 | 指什麼 | 範圍 |
|---|---|---|
| **系統重構 Phase 1-5** | 本 v2 套件的大階段（本文件＝系統 Phase 5，最後一棒） | CI → Core Brain/Ops → Vision → Nav/安全 → 收口 |
| **ISM Phase 0-3** | `interaction_state.py` 狀態機自己的實作階段（[ISM plan](2026-06-11-plan-ism-interaction-state-machine.md)）；「ISM Phase 3 權威化」是本 phase 拆 shim 的閘門 G7 | Brain 內 |
| **安全 hardening P0-P3** | hardening plan 的修補優先級標籤（如「hardening P0-1」= gateway secure-default） | 安全項 |

> **北極星（一句引用，全文見 master plan）**：把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台——三個支撐系統＝PawAI CLI v2 / PawAI Studio v2 / pawai_contracts。系統 Phase 5 對應六條成功標準中的 **1 可部署、3 可擴展、6 可交接**，並把「dead code 零殘留」做成可 grep 驗證的事實。

---

## Goal

把工具和架構變成**可以長期交給別人用的系統**。系統 Phase 2-4 完成了內臟（ISM）、證據（Trace/Evidence）、控制面（hardening）與感知數據（benchmark verdict）；系統 Phase 5 收口四件事：

1. **5A CLI v2 完整化與 productization**：Typer/Rich 完整遷移、smoke family 補完（vision/object/nav/full）、face_db 生命週期整個收進 CLI、pipx 雙模式安裝、三平台安裝穩定化、error registry 全命令覆蓋、lane scripts 升格出 `.claude/skills/`。
2. **5B Dead code / 歸檔**：Executive v0 殘骸、object 死路徑、ISM Phase 3 權威化後的 legacy gate 死碼、demo-only hacks——一套件一 PR、每刀附 zero-consumer grep 證據。
3. **5C contracts / Studio 收尾**：IE compat shim 移除、`PerceptionEvent` 升格進 pawai_contracts、zh 表 Studio TS 拷貝 JSON artifact 化、LLM allowlist 政策完全單源進 `SkillContract`、Studio v2 完整版（mock parity / 假開關 / 真值回讀 / map meta / operator mode）。
4. **5D docs / 治理**：runbook 整理、HITL evidence governance（單一 schema + 單一 landing dir）、文件漂移批、dependency cleanup、PROJECT_MAP/onboard 資料同步。

**終局判準（可交接）**：隊友不問 Roy，照 CLI/Studio/runbook 能獨立完成 deploy → demo start → smoke → evidence pull 全流程。

---

## Scope

| 主線 | 內容 | 主要檔案面 |
|---|---|---|
| 5A | Typer/Rich 完整遷移（含 demo_start C901 解除）、`pawai smoke vision\|object\|nav\|full`、`pawai face delete` + face_db 生命週期、pipx 雙模式（CLI-9）、Win/Mac/WSL 安裝、error registry、#150 conftest 正式修、lane scripts 升格（DEVOPS-10）+ preflight 統一（DEVOPS-5）+ session manifest（CLI-6）+ readiness package 化（CLI-7） | `tools/pawai_cli/`、`tools/sync/`、`scripts/lanes/`（新）、`.claude/skills/{brain-studio,nav-avoidance}-lane/`、`.claude/skills/jetson-verify/`、`scripts/hooks/git-pre-commit.sh`、`.claude/skills/ros2-test-suite/` |
| 5B | state_machine.py + test（BRAIN-6）、`.claude/rules/interaction-executive.md` 改寫、`_route_object`/`OBJECT_TTS_MAP` + coco_detector 殘渣（OBJECT-9）、env_builder/context_builder、ISM Phase 3 後的 19 個 `_suppressed` 早退死碼、`demo_video_cup_compound`（OBJECT-1） | `interaction_executive/`、`pawai_brain/pawai_brain/nodes/`、`.claude/rules/`、`scripts/archive/`（新） |
| 5C | IE shim 移除 migration PR（Plan C 遺留）、PerceptionEvent 升格（Plan D 遺留）、zh 表 JSON artifact、LLM 政策進 SkillContract（BRAIN-4 終局）、mock_server route-parity pytest（STUDIO-4）、Plan A/B 開關（STUDIO-5）、gesture_enabled 真值回讀（STUDIO-8）、map meta API（STUDIO-6）、operator/presentation mode（A-7） | `pawai_contracts/`、`interaction_executive/`、`pawai_brain/`、`pawai-studio/{gateway,backend,frontend}/` |
| 5D | `docs/runbook/` 整理、HITL evidence record schema + landing dir（DEVOPS-7、A-6）、文件漂移批（FACE-5 / VISION-4 / DEVOPS-9）、dependency 盤點（setuptools<70 等約束文件化）、PROJECT_MAP / project-onboard references 同步 | `docs/runbook/`、`docs/hitl/`（A-6 拍板後）、`docs/architecture/perception/{face,gesture,pose}/`、`docs/contracts/`、`scripts/ci/check_topic_contracts.py`（docstring）、`references/`、`.claude/skills/project-onboard/references/` |

**排程彈性（master plan 明文）**：本 phase 的**非 shim 部分**（CLI packaging、docs、dead code 中不依賴 ISM 的批次）可在系統 Phase 4 期間穿插；**拆 shim / 刪 legacy gate 死碼**硬等 G7（ISM Phase 3 權威化）。

---

## Forbidden scope

1. **不在 G7 之前動 shim / legacy 裁決路徑**：`interaction_executive/skill_contract.py` shim、19 個 `_suppressed` 早退、任何 `ism_enabled` fallback 路徑——ISM Phase 3 權威化（`ism_enabled` default 翻轉 + 回歸全綠）完成前一行不刪。
2. **不重寫任何承重邏輯**：lock.py 語意（`-y` ≠ `--force`、lane、stale threshold、flock+exit-17）只准 port 不准改——唯一允許的 lock 模組變更是刪除 deprecated `Lock.transition_to`/`Lock.release`（CLI-10 建議原文）。SafetyLayer / twist_mux / StopMove 路由不在本 phase 範圍（系統 Phase 4 已收口）。
3. **dead code 刪除不夾帶行為變更**：每刀 PR 只能是「刪除/搬家 + 必要的 import/docs 修正」；發現順手想修的 bug 一律另開 PR。
4. **Typer 遷移不改命令語意**：錯誤訊息字串可換載體（Rich），但 exit code、flag 語意、IP 解析優先序、CRLF 防線、platform exit 10 等 5/14 硬化不變量（CLI-10 清單）一條不准退化。
5. **Studio 假開關處置不得「先留著」**：STUDIO-5 的 `_PLAN_MODE` 二選一（接線或移除），不准第三選項繼續掛無消費者的 UI 承諾。
6. **觀測類與政策類永不同 PR**（治理原則繼承）；歸檔（git mv）與刪除（git rm）也分開 PR，rollback 域不同。
7. **不做新功能**：本 phase 是收口，不新增感知能力、不新增 nav 能力、不動模型（系統 Phase 3 verdict 為準）。
8. **Studio v2 的三件延後能力不在本 phase**：decision timeline 完整版、session 報告匯出、annotated evidence clip（消費系統 Phase 3 W4 產物）——落點＝**系統 Phase 2 的 2B post-6/18 段**（master plan Phase 5 摘要與系統 Phase 2 plan 同口徑），T5C-5 不重複認領。

---

## Inputs / prerequisite docs

| 前置 | 狀態 | 用途 |
|---|---|---|
| **G7：ISM Phase 3 權威化完成**（`ism_enabled` default 翻轉 PR + 73 條 brain_rules + 612+ 測試綠 + legacy 裁決路徑**停用**證據——停用＝flag-off 保留不刪碼，刪碼是本 phase T5B-3 的事） | OPEN（系統 Phase 2 產出） | 5B 的 `_suppressed` 死碼刀 + 5C 的 shim 移除刀的硬閘門 |
| 系統 Phase 3 數據落地（採集腳本 + 矩陣 + verdict） | OPEN | T5A-2 的 `pawai smoke vision\|object` 是對 Phase 3 採集腳本的包裝——沒有素材就沒有 smoke 可包 |
| 系統 Phase 4 控制面收斂（nav 回歸清單 + capability ladder） | OPEN | T5A-2 的 `pawai smoke nav` 包裝 Phase 4 回歸清單；T5C-5 operator mode 沿用 Phase 4 的 token enforcement |
| **A-5：dead-code 歸檔原則 Roy 拍板**（建議案：scripts → `scripts/archive/`、套件內模組直接 git 刪除、一套件一 PR 附 zero-consumer grep 證據；不放 `docs/archive/`） | OPEN（Roy 決策） | 5B 全線的執行依據 |
| **A-6：HITL 證據治理粒度**（`docs/hitl/` 新樹 + raw artifacts 進 git 的大小門檻） | OPEN（Roy 決策） | T5D-2 landing dir 選址 |
| **A-7：Studio operator enforcement 強度**（token / 第二 port / 信任內網） | OPEN（Roy 決策） | T5C-5 operator/presentation mode 實作形態 |
| **A-8：Ollama 本地 LLM 層去留**（主線收編 / 留 legacy / 放棄離線智能） | OPEN（Roy 決策） | 決定 llm_bridge legacy 退役是否納入 5B dead-code 批次（master 附錄 A 指派給系統 Phase 5） |
| lane scripts 永久位置（audit Open Question 11：CLI package data vs `scripts/lanes/`；建議補登 master 附錄 A） | OPEN（Roy 決策） | T5A-7 搬家目的地 |
| Plan B 執行結果（PR #151；CLI 測試 144→152；follow-up：#150、demo_start C901） | merged | T5A-1/T5A-6 的基線與回歸網 |
| Plan C 執行結果（PR #152；612 全綠；shim 在位） | merged | T5C-1 的搬遷基線 |
| 系統 Phase 2 的 `pawai smoke brain` + `pawai evidence pull`（T2C-1/T2C-2） | OPEN（系統 Phase 2 產出） | T5A-2 smoke family 的 pattern 先例；T5D-2 evidence 鏈下游 |
| CLI-10 不變量清單（5/14 硬化，ledger 逐處 code-verified） | 已 commit | T5A-1 的回歸契約來源 |

---

## Tasks

### 執行紀律（治理原則，繼承 master plan，全 task 適用）

main 永遠可部署；每刀小 PR + CI 綠 + 紅綠驗證才 merge；搬家與行為變更分開 PR；trace/觀測 additive-only；觀測類與政策類永不同 PR；Codex 串行實作 + Fable spec/review；硬體能力宣稱必過 HITL gate；demo snapshot 的 forbidden claims 對所有對外材料持續有效。

### 5A：CLI v2 完整化與 productization

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T5A-1** | **Typer/Rich 完整遷移**（解除 Plan B Forbidden scope 的二刀保留）。照 audit §10 三段式（audit 原文稱 Phase A/B/C，本文件改稱**遷移段 A/B/C** 以免與系統 Phase / ISM Phase 編號混淆）：遷移段 A 新命令以 Typer sub-app 掛進 Click root → 遷移段 B 無 lock 語意的 leaf group 逐一搬 → 遷移段 C lock-bearing 命令最後；全程 `PAWAI_CLI_V1=1` 可切回。連帶解 `demo_start` C901 複雜度（Plan B follow-up 明文留給本刀）：拆 option 解析 / lock 流程 / healthcheck gate 為獨立函式 | Fable 撰寫遷移 spec → Codex 實作（每段一 PR） | 152+ 既有測試一條不刪全綠；**CLI-10 的 5/14 硬化不變量清單 port 成回歸契約**（-y≠--force、lane 路由、platform exit 10、CRLF 防線、IP 解析優先序、lock owner-aware transition 各至少一條測試斷言）；flake8 C901 對 demo_start 不再豁免 |
| **T5A-2** | **smoke family 補完**：`pawai smoke vision\|object\|nav\|full`。vision/object = 包裝系統 Phase 3 產出的採集腳本（含 CLAUDE.md 已知的 topic 隔離坑：object 用 `--gesture-topic /__no_gesture__`、gesture 反之）；nav = 包裝系統 Phase 4 的 nav 回歸清單；`full` = 串多 lane 依序執行、彙總各 lane rc 為單一 exit code + 摘要表 | Codex 實作（仿系統 Phase 2 T2C-1 的 `_SMOKE_SCRIPTS` pattern） | mock 測試（argv/env 斷言、rc 彙總邏輯）+ **真機各跑一次綠**（見 Jetson 章節）；`smoke full` 對「一 lane 失敗」回非零 |
| **T5A-3** | **`pawai face delete`** 補完（list/enroll/rebuild/test 已有）+ **face_db 生命週期整個收進 CLI**（audit §11 Face row）：ghost-dir 黑名單（`_backup*`/`old*` 幽靈身份防呆——`train_model` 把所有子目錄當人名的已知坑）、刪人 → 刪 pkl → 提示重訓的完整 SOP、db 健康檢查（孤兒目錄 / 空目錄 / 過期 enrollment 警示） | Codex 實作 | 單測（temp face_db fixture：含 `_backup` 目錄時 enroll/rebuild 必須警示或拒絕）+ Jetson 真 face_db 實測一輪 delete→rebuild→重訓 |
| **T5A-4** | **pipx 雙模式**（CLI-9）：命令分 **repo-independent**（doctor/status/net/lock ops——純 SSH）vs **repo-dependent**（deploy/demo/docs/smoke）；後者在無 repo checkout 時給明確錯誤「requires repo checkout, set PAWAI_REPO_ROOT」而非 crash；operator 模式 = pipx 安裝 + 白名單命令 | Fable 撰寫命令分類 spec（含每命令歸類表）→ Codex 實作 | pipx 安裝後 repo-independent 命令可用；repo-dependent 命令缺 repo 的錯誤訊息測試；`shell.repo_root()` 的 `PAWAI_REPO_ROOT` override 路徑有測試 |
| **T5A-5** | **Windows / Mac / WSL 安裝穩定化**：PEP 660 editable install 問題的正式解（packaging metadata 修正，非 wrapper 繞道；troubleshooting A2）；**user-install PATH 指引正式化 + console entry point 安裝驗證**（與 troubleshooting A1 對齊——`~/.local/bin/pawai` 是 pip user-install 自動生成的 entry point，repo 內無手寫 wrapper 可退役） | Codex 實作 | 三平台安裝驗證（見 Jetson/平台章節）；`pawai --version` + `pawai doctor` 三平台可跑 |
| **T5A-6** | **error registry / structured errors 全命令覆蓋**：PawaiError registry（stable id + next_steps 至少一條可複製指令）+ `pawai errors --markdown` 生成 usage-guide §7、測試鎖防文件漂移（audit §10 原案）。同 PR 群組內：**#150 conftest 隔離正式修**（`PAWAI_REPO_ROOT` 指 `tmp_path`、全 mock `shell.stream`/`run_remote`，杜絕 `.env.local` 污染的 300s 假掛）+ **ros2-test-suite skill 補回 pawai_cli** + **pre-commit hook 加回 pawai_cli scope** | Codex 實作 | 每命令至少一條錯誤路徑測試斷言 error id + next_steps；CLI 套件本機 <10s 全綠；pre-commit 紅綠驗證（故意弄壞一條 CLI 測試 → commit 被擋） |
| **T5A-7** | **lane scripts 升格**（DEVOPS-10，「skills 變薄」指標）：`.claude/skills/*/scripts/{start,preflight,healthcheck,cleanup}.sh` 搬到 `scripts/lanes/` 或 CLI package data（依 Roy 拍板，audit Open Question 11），skills 縮成薄指標；**preflight 四套並存統一**成 jetson-verify YAML 引擎（DEVOPS-5：doctor → profile → lane → post-start healthcheck 四層同一 substrate；順手處決 demo-preflight skill 指向不存在腳本的壞 runbook）；**lane session manifest**：lane scripts 產出 tmux session/pane manifest、CLI 讀 manifest 而非硬編 pane 名（CLI-6，`pawai logs` 同時區分 pane-not-found vs pane-empty）；**readiness 共用 package 化**（CLI-7：`benchmarks.core.readiness` 的 sys.path hack 改為可安裝共用套件或 vendor，pipx 模式才能用） | Roy 決策（位置）→ Codex 實作（搬家 PR 與行為 PR 分開） | 搬家 PR 零行為 diff（`pawai demo start` 全流程 byte-identical 輸出）；manifest 測試（pane 改名 → `pawai logs` 報 pane-not-found 而非 `(no output)`）；preflight 統一後 jetson-verify 3 個測試檔進 CI |

### 5B：Dead code / 歸檔

> **前置：A-5 Roy 拍板歸檔原則**。建議案：loose scripts → `scripts/archive/`（git mv 保史）；套件內模組 → 直接 git 刪除（git history 即歸檔）；**一套件一 PR**，PR body 附 zero-consumer grep 證據（`grep -rn "<symbol>" --include="*.py" | grep -v test` 空輸出截圖/貼文）。

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T5B-1** | **Executive v0 殘骸**（BRAIN-6）：刪 `interaction_executive/interaction_executive/state_machine.py`（303 LOC，生產零引用）+ `test/test_state_machine.py`（343 LOC，測死碼）；**同批改寫 `.claude/rules/interaction-executive.md`**——它仍寫「現況：空殼」+ superseded 的 v0 IDLE→GREETING 設計，主動誤導 agents 中，改寫為真實的 brain_node/IE-node 分工 + ISM 現況 | Codex 實作 | zero-consumer grep（唯一 import 在其自身測試）；IE 套件測試全綠（刪 343 LOC 死測試後基數下修屬預期，PR body 註明）；rules 檔改寫經 Fable review |
| **T5B-2** | **object 死路徑**（OBJECT-9）：刪 `_route_object` + `OBJECT_TTS_MAP`（state_machine.py 內，T5B-1 同檔順刪）+ 清 coco_detector `__pycache__` 殘渣（untracked，零風險）；**env_builder/context_builder**（pawai_brain/nodes/，自 pawai_brain 自身歷史階段編號 Phase A.6 起棄用——非本套件系統 Phase / ISM Phase——graph.py 不 import）grep 確認 test-only 後一併移除 | Codex 實作 | 各 symbol zero-consumer grep；pawai_brain 348+ 測試綠；`docs/architecture/perception/object/README.md` 的「棄用路徑」段同步刪除 |
| **T5B-3** | **ISM Phase 3 權威化後的 legacy gate 死碼**：ISM plan §2.3 盤點的 19 個分散 `_suppressed` 早退（demo_phase/dedup/llm_allowlist/capability_health/skill_cooldown/gesture_enabled/pending_confirm/active_plan/conversation_gate/stranger_alert_enabled/greet 三閘/attention_engaged/tts_playing/object_remark_dedup）在 ISM policy 表權威化後成為重複判斷——用 refactor-cleaner 掃出實際死分支逐一移除。**硬依賴 G7（系統 Phase 2 的 ISM Phase 3 完成＝翻 default + legacy 路徑停用、不刪碼），在那之前本 task 不開工；19 個早退死碼的刪除歸屬單源在本 task（ISM plan / 系統 Phase 2 plan / master G7 同口徑）** | Codex 實作（G7 後）+ Fable review | 每刀：73 條 brain_rules + ISM 全測 + 612+ 測試綠；shadow parity 測試證明移除前後裁決 byte-identical；6/9 場景重演測試保留為永久回歸網 |
| **T5B-4** | **demo-only hacks 清理**：`demo_video_cup_compound` 整段移除（OBJECT-1 查證改判後的修法——該路徑 dead-by-flag；以 **symbol 錨定**刪除：`demo_video_cup_compound` flag（現行 main 宣告/讀取於 `brain_node.py:385`/`:423`）+「我看到 Roy 坐著拿著杯子」字面量所在的複合句區塊（現行 main `:1551` 起）+ 30s/10s/60s 魔術數字整段刪，通用 object_remark 路徑已涵蓋。**ledger OBJECT-1 的 `:1390-1420` 為 6/10 audit baseline（tag `demo-2026-06-snapshot`）行號、已漂移，執行時一律以 grep 為準**）；其餘 `demo_video_*` flags 逐一 grep 消費者後同批處置 | Codex 實作 | flag 預設 false + executive.yaml false 雙證據（已成立）；刪除後 brain 測試綠；trace 對照（移除前後對 cup 事件的裁決一致） |

### 5C：contracts / Studio 收尾

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T5C-1** | **IE compat shim 移除**（Plan C 明文遺留）：專門 migration PR——全 repo `from interaction_executive.skill_contract import` 改寫為 `from pawai_contracts.skill_contract import`，然後刪 shim 檔。**硬依賴 G7**（ISM Phase 3 權威化後 legacy 路徑不再 import 它才安全） | Codex 實作（G7 後） | import 全改 + shim 刪除後 **全 repo zero-import grep**（`grep -rn "interaction_executive.skill_contract"` 空）+ 612+ 測試綠 + colcon 三套件可建 |
| **T5C-2** | **PerceptionEvent 升格進 pawai_contracts**（Plan D 明文「等第二個消費者——Trace/ISM——出現再升格」；ISM 接入後條件成立）：git mv + 原地 shim → 消費端改 import → 拆 shim（同 Plan C2 紀律，兩段 PR） | Codex 實作 | router 既有測試零修改全綠（搬家段）；contracts purity gate（不 import rclpy）涵蓋新模組 |
| **T5C-3** | **zh 表 Studio TS 拷貝 JSON artifact 化**：`pawai_contracts/zh_tables.py` 生成 JSON artifact，Studio frontend build 時消費 JSON 而非手抄 TS dict——**取代 Plan C3 的 parity test 拷貝制**（parity test 退役為 artifact freshness check） | Codex 實作 | artifact 生成腳本測試；前端 build 綠；故意改 zh_tables 一鍵後 artifact stale check 紅（紅綠驗證） |
| **T5C-4** | **LLM allowlist 政策完全單源進 SkillContract 欄位**（BRAIN-4 終局，audit §8 原案）：`llm_policy.py` 的 allowlist + execute-mode map 收編為 `SkillContract` 上的欄位（registry 既有 `requires_confirmation`/`demo_status_baseline` 已編碼近似資訊），`llm_policy.py` 變 derived view 或退役 | Fable 撰寫欄位設計 spec → Codex 實作 | Plan C4 的三條 llm_policy 測試升級為 registry 欄位斷言；`test_allowlist_single_source_of_truth` 持續綠；skill 定義值零變動（凍結 hash 斷言） |
| **T5C-5** | **Studio v2 完整版**：① mock_server **route-parity pytest**（STUDIO-4：diff gateway vs mock 的 FastAPI app.routes，漂移 fail CI）+ 補 `/api/reset`、`/api/nav/*` stub；② **Plan A/B 假開關**（STUDIO-5）接線（publish `/brain/plan_mode` 給 brain 消費，仿 gesture_enabled）**或移除 UI**——二選一，Roy 拍板；③ **gesture_enabled 真值回讀**（STUDIO-8）：brain_node 把 gesture_enabled 發進 `/state/pawai_brain`，gateway/UI 讀真值、退役 session cache；④ **map meta API 化**（STUDIO-6）：gateway `/api/map_meta` 從 Nav2 同一份 map.yaml 解析 origin/res/dimensions，前端 fetch、刪三處手動同步；⑤ **operator/presentation mode**：依 A-7 拍板的 enforcement 強度落地（沿用系統 Phase 4 的 gateway token 機制）。**明示不在本項**：decision timeline 完整版 / session 報告匯出 / annotated clip 落點＝系統 Phase 2 的 2B post-6/18 段（見 Forbidden scope 8） | Roy 決策（②⑤）→ Codex 實作（每項獨立 PR） | route-parity pytest 紅綠驗證（故意在 gateway 加 route → mock 缺 → CI 紅）；gateway 64+ 測試綠；③ 的 desync 場景測試（ros2 param set 後 Studio 顯示跟上）；④ 換地圖只改 map.yaml 一處 |

### 5D：docs / 治理

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T5D-1** | **docs/runbook 整理**：合併重複 runbook、過期段落標註 superseded、入口從 `docs/runbook/README.md` 一條路走通 deploy→demo→smoke→evidence | Fable 撰寫 | runbook 隊友走查（見 Done criteria③） |
| **T5D-2** | **HITL evidence governance**（DEVOPS-7）：定義**單一 HITL evidence record schema**——日期 / stack(profile) / params / 結果 enum（PASS/DEGRADED/FAIL，沿用 audit §13 的 `PASS_HW_PROVEN\|PASS_SENSING_ONLY\|DEGRADED\|FAIL\|NOT_RUN`）/ raw-log 指標——+ **單一 landing dir**（`docs/hitl/` 或 `benchmarks/results`，依 A-6 拍板）+ 打通 **evidence_pull → scoreboard 鏈**（Jetson `test_results/<topic>/<ts>/` 約定 → `pawai evidence pull` → `benchmarks/results/raw\|summary` → build_scoreboard → readiness fail-closed） | Roy 決策（A-6）→ Fable 撰寫 schema → Codex 實作（鏈路腳本） | schema 有 pytest 驗證器；既有四處散裝 HITL 紀錄至少一份轉錄為首例；scoreboard 從新 landing dir 可重建 |
| **T5D-3** | **文件漂移批**：FACE-5 四重漂移（CLAUDE.md 凍結閾值 0.35/0.25 vs yaml 0.40/0.22、AGENT.md `identity` vs wire `stable_name`、rate 宣稱 10/8/6.6Hz 三說、phantom `identity_unknown` 事件）；VISION-4 誤導保護條款（兩處「不要移除 GESTURE_COMPAT_MAP（fist→ok）」vs code 2026-05-05 已清空且明文禁止、contract §4.3 fist 映射假話、fallen 0.4 vs 0.45）；DEVOPS-9（contract checker docstring 假稱 report-only 實則 ghost-topic blocking + pre-commit 丟棄 stderr） | Codex 實作（純文件 + docstring + hook 一行） | 逐條對照 ledger 證據行號修正；pre-commit 紅綠驗證（contract 違規時 stderr 可見） |
| **T5D-4** | **package/dependency cleanup**：已知約束文件化（Jetson `setuptools<70`、aiortc 1.9.0 pin load-bearing、onnxruntime-gpu wheel 來源等收進單一 dependencies 文件）；各套件 requirements / package.xml 盤點（漏列、多列、版本飄移） | Codex 實作 + Fable review | colcon 全套件可建；`pawai doctor` 加 dependency 檢查項（可選）；文件單一入口 |
| **T5D-5** | **PROJECT_MAP / onboard 資料同步**：`.claude/skills/project-onboard/references/project-status.md` 與 root `references/project-status.md` 的漂移問題收斂為單源（指標或生成）；PROJECT_MAP 反映 v2 終局架構（Router→ISM→Policy→Executor→Trace + 三支撐） | Fable 撰寫 | 兩份 project-status 無內容分叉（單源 + grep 驗證）；新 session onboard 走查可達 v2 架構認知 |

---

## Tests / verification

- **dead code（5B 全線）**：每刀附 **zero-consumer grep 證據**（PR body 必含 grep 指令 + 空輸出）+ 對應套件全套測試綠；刪測試檔導致基數下修須在 PR body 註明前後數字。
- **shim 移除（T5C-1/T5C-2）**：專門 migration PR；import 全改 + **612+ 測試綠** + 全 repo zero-import grep + colcon 可建（contracts → IE → pawai_brain 依序）。
- **CLI 遷移（T5A-1）**：**152+ 既有測試全保留**（一條不刪、斷言不弱化）+ **CLI-10 的 5/14 硬化不變量清單 port 成回歸契約**（test_lock / test_platform / test_cli 隨命令一起搬）；`PAWAI_CLI_V1=1` 降級路徑每段遷移 PR 驗一次。
- **smoke family（T5A-2）**：mock 層（argv/env/rc 彙總）+ 真機層（每 lane 至少一次綠 run，紀錄寫 HITL evidence record）。
- **Studio（T5C-5）**：route-parity pytest 進 CI 且紅綠驗證；gateway / frontend 既有測試零退化。
- **CI 全程**：fast-gate 全 invocation 綠是每 PR 的地板；新增測試一律先紅後綠（治理原則）。

## Jetson / Go2 requirement

| 項 | Jetson | Go2 |
|---|---|---|
| smoke family 真機驗證（T5A-2）、face_db 實測（T5A-3）、lane scripts 搬家後 `pawai demo start` 全流程、runbook 走查 | **需要** | 低度（演示性驗收；smoke nav 需 Go2 在場跑 Phase 4 回歸清單） |
| 安裝驗證（T5A-4/T5A-5） | 不需要 | 不需要（**Win / Mac / WSL 三平台**各驗一次） |
| 5B / 5C / 5D 其餘全部 | 不需要（WSL 即可） | 不需要 |

本 phase 整體是五個系統 phase 中 Go2 需求最低的；唯一硬 HITL 是 smoke family 的真機綠 run 與搬家後的 demo start 等價驗證。

## Done criteria

（對齊 master plan 系統 Phase 5 驗收行 + 北極星成功標準 1/3/6）

1. **可交接**：隊友不問 Roy，照 CLI/Studio/runbook 能獨立完成 **deploy → demo start → smoke → evidence pull** 全流程（runbook 走查通過，不需口頭支援）。
2. **pipx 可裝**：operator 模式 pipx 安裝後白名單命令可用；repo-dependent 命令缺 repo 給明確錯誤；Win/Mac/WSL 三平台安裝驗證通過。
3. **dead code 零殘留**：5B 清單全數處置完畢；shim 移除後全 repo zero-import grep 乾淨；每刀 PR 帶 zero-consumer 證據。
4. **HITL 證據有 schema 有 landing dir**：evidence record schema 定稿 + 單一 landing dir 啟用 + evidence_pull→scoreboard 鏈至少跑通一輪真實數據。
5. **單源收斂完成**：zh 表（JSON artifact）、LLM 政策（SkillContract 欄位）、map meta（gateway API）、gesture_enabled（brain 真值）、preflight（jetson-verify 引擎）、session 命名（lane manifest）各只剩一個真相源。
6. **skills 變薄**：`.claude/skills/` 內不再有 load-bearing 生產腳本（DEVOPS-10 關閉），skills 只剩薄指標與 agent 知識。

## Rollback / fallback

- **歸檔不刪史**：scripts 用 `git mv` 進 `scripts/archive/`；套件內模組走 git 刪除（git history 即歸檔）；**刪除前打 tag**（master plan 紀律）。
- **每刀單 PR revert**：5B/5C 每個刪除/搬家都是獨立 PR，revert 即完整復原；shim 移除 PR revert 會還原 shim（Plan C 已驗證此性質）。
- **CLI 遷移降級**：`PAWAI_CLI_V1=1` 全程保留到遷移段 C（T5A-1）完成 + 一個穩定週期後才拆。
- **lane scripts 搬家**：搬家 PR 零行為 diff 是驗收條件，出問題 revert 後 `.claude/skills/` 路徑原樣可用。
- **smoke family**：新命令 additive，失敗不影響既有 `pawai demo` / `health` 路徑。

## 6/18 freeze constraint

本 phase 排在全套件最後，開工時 **6/18 凍結早已解除**（G5 已過、系統 Phase 2-4 已消化各自的解凍項），無凍結檔案衝突。但兩條紀律持續有效：

1. **main 永遠可部署**：收口期最容易鬆懈，每刀 PR 的 CI 綠 + 真機等價驗證標準不降。
2. **`.claude/skills/` 大搬家需 Roy 全程知情**：lane scripts 升格（T5A-7）動的是團隊每天在用的 `pawai demo start` 路徑——搬家時點、目的地（A 開放決策）、與切換窗口由 Roy 簽核，且搬家後第一次 demo start 必須 Roy 在場驗證。

另：demo snapshot 的 forbidden claims 清單在本 phase 仍對所有對外材料有效——productization 不等於能力宣稱升級，capability ladder（系統 Phase 4 產出）是唯一的宣稱依據。
