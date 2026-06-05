# PawAI 文件入口

**專案**：老人與狗 (Elder and Dog) / PawAI
**定位**：居家四足具身互動機器人（互動 70% / 守護 30%）。主線文件在以下路線下。

> **30 秒原則**：找不到資訊 30 秒之內 → 走 `pawai-brain/` 或 `navigation/`，再不行去 `archive/`。
>
> **Demo claim 真相**：任何「某能力是否 pass / 能不能講」一律以 §衝突仲裁 的 EVIDENCE_AUTHORITY 順序裁定，不以任何敘事文件為準。

---

## 主線文件 (active)

| # | 路線 | 入口 | 內容 |
|:-:|------|------|------|
| 1 | **Brain** | [pawai-brain/README.md](pawai-brain/README.md) | 互動主線：感知 / 語音 / Studio / Brain 決策層 |
| 2 | **Navigation** | [navigation/README.md](navigation/README.md) | 移動主線：LiDAR / Nav2 / AMCL / D435 depth / 避障 |
| 3 | **Contracts** | [contracts/README.md](contracts/README.md) | 跨主線 ROS2 介面契約 + 設計總則 |
| 4 | **Runbook** | [runbook/README.md](runbook/README.md) | Demo 救火 SOP（Jetson / Network / GPU server / Go2 操作） |
| 5 | **Mission** | [mission/README.md](mission/README.md) | 專案定位 / Demo 劇本 / 八大功能 SoT；6/18 戰略邊界 north-star v2（禁說清單） |
| 6 | **Deliverables** | [deliverables/](deliverables/) | 學期繳交素材（thesis） |

## 支援性資料夾（active，非主線真相層）

> 工具手冊 / 流程設定 / 製作指南 / 持久決策 / 研究。**不是能力或產品真相**——能力 pass/fail 一律回 baseline-evidence（見 §衝突仲裁）。

| 資料夾 | 入口 | 角色 |
|--------|------|------|
| **ADR** | [adr/](adr/) | 持久架構決策（一次一決策、可被 supersede）。ADR-0001/0002 待 north-star v2 正式 amend |
| **Agents** | [agents/](agents/) | AI agent / skill 運作設定（domain / issue-tracker / triage / HITL 取證流程）。流程設定，非產品真相 |
| **PawAI CLI** | [pawai_cli/README.md](pawai_cli/README.md) | 五人共用 Jetson 單一入口 CLI 手冊（搭配 runbook 使用） |
| **PawAI Demo** | [pawai-demo/](pawai-demo/) | Demo 製作 / 簡報 / 影片 / 報告撰寫指南（製作流程，非能力真相） |
| **Research** | [research/](research/) | 通用研究（非 lane 綁定）。research-not-truth，不覆寫 baseline-evidence / contracts |
| **Superpowers** | [superpowers/](superpowers/) | 長版 spec / plan 背景（CLI / nav / object 等）。spec=背景，決策精煉版見 adr/ |

## 歷史

| # | 路線 | 入口 | 內容 |
|:-:|------|------|------|
| 7 | **Archive** | [archive/](archive/) | 5/02 reorg 前歷史 + 2026-02-11 restructure |

---

## 衝突仲裁（誰是真相來源）

衝突時由高到低仲裁；**最新實測證據優先**。能力是否 pass、能不能進 Brain 主線、6/18 能不能講，一律回此順序。

| # | 層級 | 真相來源 |
|:-:|------|---------|
| 0 | **程式碼 / runtime topic schema** | 永遠是最終真相 |
| 1 | **實測證據（empirical, TOP）** | [runbook/baseline-evidence/2026-06-04-hitl/](runbook/baseline-evidence/2026-06-04-hitl/) — 當前唯一 trusted snapshot（SHA 78fbf36, readiness=not_ready）。其 README 的 capability grades + honesty caveats 是能力 pass/degraded/fail/insufficient 的最終事實。READ-ONLY 證據資料。`2026-06-03-first-trusted-face/` 已被取代，僅作歷史 |
| 2 | **收斂審計（read-only）** | [pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md](pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md) — 6/18 claim-scope / 換不換模型 / docs-drift 裁定的權威。本身是 research，不覆寫 baseline 數據 |
| 3 | **能力規格（how to measure）** | [pawai-brain/specs/2026-06-18-capability-baseline-spec.md](pawai-brain/specs/2026-06-18-capability-baseline-spec.md) — 15 capability 怎麼量、怎樣算 pass 的唯一真相源（門檻 provisional）。grade 結果以 #1 為準 |
| 4 | **戰略邊界（what to claim）** | [mission/2026-06-18-demo-north-star.md](mission/2026-06-18-demo-north-star.md) v2 — 6/18 定位、禁說清單、scoreboard-first、scope 分層。amend ADR-0001/0002。能力是否 pass 仍回 #1 |
| 5 | **介面契約** | [contracts/interaction_contract.md](contracts/interaction_contract.md)（ROS2 topic / action / service / message schema，v2.5 凍結） |
| 6 | **模組設計真相** | `pawai-brain/{specs,plans,perception/*,speech,studio}/`、`navigation/{plans,research,setup,specs}/`（各帶模組 `CLAUDE.md`） |
| 7 | **產品方向 / Demo 劇本 / 八大功能** | [mission/README.md](mission/README.md) |
| 8 | **持久決策** | [adr/](adr/)（ADR，可被新提案 supersede） |
| 9 | **環境建置與救火 SOP** | [runbook/](runbook/) |

**EVIDENCE_AUTHORITY（最新優先）**：`runbook/baseline-evidence/2026-06-04-hitl/` ＞ 6/05 convergence audit ＞ 2026-06-18-capability-baseline-spec ＞ 2026-06-18-demo-north-star。6/03 first-trusted 為歷史。

**canonical claim matrix**：每能力的 Current Claim / Claim Level / Evidence-Provenance / Pass-Degraded-Fail-Insufficient / Fallback / Non-Claims / Model Candidates / Next Retest 以上述 #1–#4 為準，**不在各檔重複整份散文**——一律連結回 baseline-evidence README + convergence audit。

**關鍵原則**：實測 ＞ 審計 ＞ 規格 ＞ 敘事。`research/`、`pawai-brain/research/`、`navigation/research/` 一律 research-not-truth（除 6/05 convergence audit 經指定升格為 #2）；`archive/` 全 frozen。

---

## 文件治理

- **不主動重寫沒碰到的文件** — 改了程式碼才同步對應 `README.md`
- **新增 / 移除 ROS2 topic** → 同步 `contracts/interaction_contract.md`
- **每日收工** → 更新 `references/project-status.md`（在 repo 根目錄 `references/`，不在 `docs/`）
- **命名約定**：`YYYY-MM-DD-description.md`（plan / spec / research）

詳見本檔 commit 紀錄與 [`archive/2026-05-docs-reorg/README.md`](archive/2026-05-docs-reorg/README.md)（本次重組來源）。

---

*Last reorg: 2026-05-02（推翻 5/13 pre-demo policy 提前執行；18 top-level → 7 active + archive）*
