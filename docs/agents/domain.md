# Domain Docs

> **Scope**：本檔有兩個職責 — (1)「engineering skills 怎麼消費 repo 的 domain 文件（CONTEXT / ADR）」的流程規則；(2)「PawAI shared language glossary」（§Glossary）—— agents / 文件對 trusted snapshot、readiness、narrow pass、insufficient_data 等詞的**共用定義**。
> **Status**：active / agent-config（流程設定 + 共用語彙），**不是**產品或能力真相。
> **Owner lane**：agents（AI agent / skill 運作設定）。
> **Source-of-truth priority**：本檔**不裁定**任何能力是否 pass。能力 grade 的最終事實依據是 `docs/runbook/baseline-evidence/2026-06-04-hitl/`（trusted snapshot, SHA `78fbf36`, readiness=`not_ready`）＞ 收斂審計 ＞ capability spec ＞ north-star v2 ＞ claim matrix。glossary 的每個詞錨到此權威鏈，不複製其數據。
> **Maintained child files（docs/agents/）**：`issue-tracker.md`、`triage-labels.md`、`hitl-verification-protocol.md`、`issue-development-workflow.md`、`samples/`。
> **Archived / legacy boundary**：本檔無歷史前身；`docs/archive/**` 全 frozen，不在此引用為現行真相。
> **What this README is NOT**：不是能力真相源、不是量測協定、不是 demo 劇本、不是 ADR。能力「能不能講」回 [`../mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md)；「怎麼量」回 [`../architecture/specs/2026-06-18-capability-baseline-spec.md`](../architecture/specs/2026-06-18-capability-baseline-spec.md)。

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo (most repos):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context repo (presence of `CONTEXT-MAP.md` at the root):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_

---

## Glossary — PawAI shared language

> **目的**：讓所有 agent / 文件對「能力可信度」用詞**一致**，避免 overclaim。**每個詞錨到 canonical 權威鏈，不在此複製數據或整份散文**。
> **權威鏈（最新優先，衝突時由高到低仲裁）**：
> 0. 程式碼 / runtime topic schema（最終真相）
> 1. **實測證據**：[`../runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（trusted snapshot, SHA `78fbf36`, `run_trusted=true`, readiness=`not_ready`）—— grade + honesty caveats 凌駕一切敘事。
> 2. **收斂審計（read-only）**：[`../archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`](../archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md)
> 3. **能力規格（怎麼量）**：[`../architecture/specs/2026-06-18-capability-baseline-spec.md`](../architecture/specs/2026-06-18-capability-baseline-spec.md)
> 4. **戰略邊界（能不能講）**：[`../mission/2026-06-18-demo-north-star.md`](../mission/2026-06-18-demo-north-star.md) v2
> 5. **canonical claim matrix（每能力對照）**：[`../mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md)
>
> `2026-06-03-first-trusted-face/` 已被 6/04 取代，僅作歷史。`research/`、lane research 一律 research-not-truth（除 6/05 convergence audit 被指定為權威鏈 #2）；`archive/**` 全 frozen。

| 詞 | 定義 | 錨點 |
|---|---|---|
| **trusted snapshot** | 由 `build_scoreboard` 在與 Jetson deploy manifest **相同 commit** 的 checkout 上產出、且 `run_trusted=true` / `version_mismatch=false` 的 baseline 量測快照。目前唯一 trusted = `2026-06-04-hitl/`（SHA `78fbf36`）。**不是** trusted 的不得用來宣稱能力 pass。 | 權威鏈 #1 |
| **readiness** | `pawai readiness` 對「demo 整體可否放行」的 fail-closed 判定（`ready` / `not_ready`）。6/04 為 `not_ready` —— 這是**正確**結果（多數能力非 pass），**不是** bug，也**不只因 face**。readiness 看的是 trusted snapshot + preflight，不看敘事。 | 權威鏈 #1（`readiness_output.json`） |
| **narrow pass（窄版 pass）** | 某能力在**明確受限條件**下 🟢 pass，但邊界外未驗證。例：`face.recognition` 僅單一註冊者 Roy / 單光照；`object.cup` 僅 ~1m 近距 cup-only。講 narrow pass **必須**同時講邊界。**不得**升級為「已可靠 / 通用 / 已穩定」。 | claim matrix §1 + baseline README caveats |
| **claim-with-caveat** | claim level：可在 demo / 簡報講，但**必帶 caveat**（邊界 + Non-Claims）。對應 narrow pass 能力（face / object.cup / voice.command）與「限機制」的 brain safety 拒絕。**caveat 不是可選項**。 | claim matrix §0 速查表 |
| **insufficient_data** | 該能力本輪 **n=0 / 無 observer / 未量**，grade 既非 pass 也非 fail。**禁止寫成 pass**，也禁止寫成「做不到」。所有 nav.* / pose.* / brain.* / studio.evidence / cli.readiness 目前皆 insufficient_data。高風險動作（motion / nav）一律不放行。 | baseline README + north-star §9 |
| **fail-closed** | 系統 / gate 在「能力非 pass」或「資訊不足」時**預設拒絕放行高風險動作**，而非樂觀放行。readiness `not_ready`、Brain capability health gate（預設關閉、未接 runtime）、nav dry-run 在 AMCL gate abort（actual_distance=0.0）都是 fail-closed 證據。 | north-star §9 + baseline README §nav caveat |
| **demo-safe claim** | 6/18 現場 / 簡報**可以講**的話：只用 trusted snapshot 標 pass（或明確人工安全 override）的能力進 Brain 主線；degraded / fail / insufficient 只在 Studio **顯示**不觸發不宣稱。判斷某句能不能講一律回 claim matrix。 | north-star §4 / §5 + claim matrix |
| **forbidden overclaim** | 證據不支持、**禁止出現在任何文件 / 旁白**的宣稱。硬清單：陌生人拒絕 / 守護 / guardian / 陌生人警報；通用物體偵測 / 尋物 / VLM；`voice.stop` 當 safety-stop；`gesture.wave` pass；動態避障 / 自走 / 跟隨；跌倒偵測可靠；「Brain 不會幻覺 / 已過反幻覺測試」；mic_stop latency。 | north-star §5 + claim matrix「Non-Claims」 |
| **brain_allowed** | 某能力**是否可進 Brain 主線去控制機器人**的布林前提。`brain_allowed=true` 僅當該能力在 trusted snapshot 標 **pass**。degraded / fail / insufficient → `brain_allowed=false`（只顯示、不控制）。這是 scoreboard-first 的執行語意。 | north-star §9（pass=可進主線） |
| **capability gate** | 依能力分級放行 / 攔截動作的 gate。**注意**：Brain 的 capability health gate **目前預設關閉、未接 runtime motion 觸發**（#85 v0.2 設計落點）—— 在它真正接上前，**不得宣稱「capability health gate 已存在 / 已生效」**。「必留底線」是範圍優先級，不是 runtime 攔截。 | north-star §7 / §9 |
| **HITL**（human-in-the-loop） | 量測 / motion trial 由**現場 operator**（Roy 在 Go2+Jetson 旁）親自跑與簽核。Go2 motion 必須有 `motion_sign_offs.jsonl` append-only 簽核 + video evidence sha。驗證分級與逐能力硬體對照見 [`hitl-verification-protocol.md`](hitl-verification-protocol.md)。 | hitl-verification-protocol.md |
| **Studio evidence** | Studio / Foxglove 把「感知 event → Brain decision → gate → skill result」逐步顯示的證據載體。**有價值（provenance / 可解釋）但不等於能力 pass** —— `studio.evidence` 本身目前 insufficient_data，除非綁 trusted baseline 資料，否則不單獨宣稱 pass。 | claim matrix（studio.evidence 卡）+ north-star §4 |
| **Jetson runtime** | Jetson Orin Nano 上的 ROS2 / 模型推理 / Go2 連線實際執行環境。感知（face/pose/gesture/object）+ 安全層 + reactive_stop 都在此 edge 端跑（Edge AI framing）。Jetson repo 路徑 `~/elder_and_dog`，source 用 `setup.zsh`。 | north-star §10 |
| **WSL source of truth** | `build_scoreboard` 的權威執行環境是 **WSL**（不在 Jetson 上算分），且必須在與 Jetson deploy 相同 commit 的 checkout build，否則 `version_mismatch` → snapshot 不 trusted。「WSL 是 scoreboard 真相」指此聚合算分的版本綁定來源。 | baseline README §Method + hitl-protocol §Artifact |
| **research-only** | 標記某文件 / 模型調查為**研究、非實作 backlog、非能力真相**。模型研究分層：`BASELINE_NOW` / `STUDIO_ONLY_NOW` / `SPIKE_AFTER_FAIL` / `FUTURE_RESEARCH`。`research/`、lane research 一律 research-not-truth；**不得覆寫 baseline-evidence 或 contracts**（唯一例外：6/05 convergence audit 經指定升格為權威鏈 #2）。 | claim matrix「Model Candidates」+ convergence audit |
| **archived-superseded** | 被新證據 / 新文件取代、保留作歷史、**不刪除**的舊檔。標記方式：頂部 blockquote banner 標 `historical / superseded by <new>`。例：`2026-06-03-first-trusted-face/`（被 6/04 取代）、`docs/archive/**`（全 frozen）。archived 內容不得引用為現行真相。 | 權威鏈說明 + docs/README 仲裁表 |

> **使用規則**：agent 輸出（issue title / 旁白 / refactor 提案 / 測試名）命名能力可信度時，**用上表的詞**，不要漂移到同義詞（如把 narrow pass 講成「已穩定」、把 insufficient_data 講成「做不到」）。某句能不能講有疑慮 → 回 claim matrix 對照表，不要自行 brainstorm。
