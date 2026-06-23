# Architecture Decision Records (ADR)

**English** | [中文](./README.zh.md)

> **Scope**: PawAI's durable architecture decisions. One decision at a time; can be superseded by future proposals.
> **Status**: active / canonical durable-decision layer
> **Owner lane**: cross-cutting (not bound to a single module)
> **Source-of-truth priority**: ADR is **#8** of the [source-of-truth hierarchy](0004-docs-source-of-truth-hierarchy.md) (durable decisions). Whether a capability passes always ranks above ADR, falling back to **#1** [`baseline-evidence`](../runbook/baseline-evidence/2026-06-04-hitl/); whether something can be claimed defers to the [canonical claim matrix](../mission/2026-06-18-capability-claim-matrix.md). ADRs record **decisions**, not capability grades, and not transient todos.
> **Maintained child files**: `0001`–`0007` + this README index.
> **Archived / legacy boundary**: superseded ADRs are marked in their Status as `superseded by ADR-XXXX` and are not deleted; those amended by a newer document get an Amendment blockquote added at the top (see 0001 / 0002).
> **What this README is NOT**: not a long-form design spec (those live in module specs such as `docs/architecture/specs/`), and not a capability source-of-truth (that is baseline-evidence + claim matrix).

One markdown file per architecture decision. Filename format `NNNN-kebab-case-title.md` (e.g. `0004-docs-source-of-truth-hierarchy.md`).

## ADR Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-pawai-2026-06-poc-non-contact-positioning.md) | 2026-06 POC adopts non-contact positioning (red line) | accepted · 2026-06-05 amended |
| [0002](0002-pawai-platform-and-demo-scenario-two-layer-narrative.md) | Platform identity + demo scenario two-layer narrative | accepted · 2026-06-05 amended |
| [0003](0003-2026-05-demo-studio-ptt-over-wake-word-vad.md) | During the demo phase, replace wake word / VAD with Studio PTT | accepted |
| [0004](0004-docs-source-of-truth-hierarchy.md) | Docs source-of-truth 10-layer hierarchy + conflict arbitration | accepted |
| [0005](0005-evidence-first-claim-policy.md) | Evidence-first claim policy (grading + evidence binding + forbidden phrasing) | accepted |
| [0006](0006-618-demo-claim-policy.md) | 6/18 demo claim policy (narrow pass + do-not-say list + fail-closed) | accepted |
| [0007](0007-wsl-source-of-truth-vs-jetson-runtime.md) | WSL=source-of-truth / Jetson=runtime (SHA-match evidence iron rule) | accepted |

## Division of labor with long-form specs
- **`docs/architecture/specs/`, `docs/architecture/navigation/specs/`, `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/` (historical)**: historical design specs, Spike plans, North Star documents — usually contain long-form specs covering "why it is designed this way, and how the follow-up details play out"
- **`docs/adr/`** (this folder): distilled "we decided X, because Y, with consequence Z" records — one decision at a time, can be superseded by future proposals

New decisions start here; specs are the long-form background for ADRs.

## Template
```markdown
# ADR-NNNN: <decision title>

- **Date**: YYYY-MM-DD
- **Status**: proposed | accepted | superseded by ADR-XXXX
- **Context**: 為何需要這個決策？前提是什麼？
- **Decision**: 我們決定怎麼做。
- **Consequences**: 接受後會發生什麼（正反面）？
```
