# Architecture Decision Records (ADR)

> **Scope**：PawAI 的持久架構決策（durable decisions）。一次一決策、可被未來提案 supersede。
> **Status**: active / canonical durable-decision layer
> **Owner lane**: cross-cutting（不綁單一模組）
> **Source-of-truth priority**：ADR 是 [真相層級](0004-docs-source-of-truth-hierarchy.md) 的 **#8**（持久決策）。能力是否 pass 一律高於 ADR、回 **#1** [`baseline-evidence`](../runbook/baseline-evidence/2026-06-04-hitl/)；能不能講連 [canonical claim matrix](../mission/2026-06-18-capability-claim-matrix.md)。ADR 記**決策**，不記能力 grade、不記 transient todo。
> **Maintained child files**：`0001`–`0007` + 本 README index。
> **Archived / legacy boundary**：被 supersede 的 ADR 在 Status 標 `superseded by ADR-XXXX`，不刪；被新文件 amend 的在頂部加 Amendment blockquote（見 0001 / 0002）。
> **What this README is NOT**：不是長版設計規格（那是 `docs/architecture/specs/` 等模組 spec），不是能力真相源（那是 baseline-evidence + claim matrix）。

每個架構決策一份 markdown。檔名格式 `NNNN-kebab-case-title.md`（e.g. `0004-docs-source-of-truth-hierarchy.md`）。

## ADR 索引

| ADR | 決策 | Status |
|---|---|---|
| [0001](0001-pawai-2026-06-poc-non-contact-positioning.md) | 2026-06 POC 採非接觸式定位（紅線） | accepted · 2026-06-05 amended |
| [0002](0002-pawai-platform-and-demo-scenario-two-layer-narrative.md) | 平台身份 + demo 場景雙層敘事 | accepted · 2026-06-05 amended |
| [0003](0003-2026-05-demo-studio-ptt-over-wake-word-vad.md) | demo 階段以 Studio PTT 取代 wake word / VAD | accepted |
| [0004](0004-docs-source-of-truth-hierarchy.md) | 文件真相來源 10 層 hierarchy + 衝突仲裁 | accepted |
| [0005](0005-evidence-first-claim-policy.md) | Evidence-first claim policy（分級 + 證據綁定 + 禁止句式） | accepted |
| [0006](0006-618-demo-claim-policy.md) | 6/18 demo claim policy（窄版 pass + 禁說清單 + fail-closed） | accepted |
| [0007](0007-wsl-source-of-truth-vs-jetson-runtime.md) | WSL=source-of-truth / Jetson=runtime（SHA-match 取證鐵律） | accepted |

## 與長版 spec 的分工
- **`docs/architecture/specs/`、`docs/architecture/navigation/specs/`、`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/`（歷史）**：歷史設計規格、Spike 計畫、北極星文件 — 通常含「為什麼這樣設計、後續細節怎麼跑」的長篇規格
- **`docs/adr/`**（本資料夾）：精煉的「我們決定 X、因為 Y、後果 Z」記錄 — 一次一個決策、可被未來提案 supersede

新決策從這裡開始；spec 是 ADR 的長版背景。

## 模板
```markdown
# ADR-NNNN: <decision title>

- **Date**: YYYY-MM-DD
- **Status**: proposed | accepted | superseded by ADR-XXXX
- **Context**: 為何需要這個決策？前提是什麼？
- **Decision**: 我們決定怎麼做。
- **Consequences**: 接受後會發生什麼（正反面）？
```
