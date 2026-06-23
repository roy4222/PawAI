# PawAI Brain × Studio — Architecture Documentation Index

**English** | [中文](./README.zh.md)

> **Scope**: The entry point for the **architectural source of truth** of PawAI's interaction mainline — a layered index of the architecture documents for Brain / Executive / Studio / perception data flow (which one is the current overview, which one is the 5/11 freeze-snapshot, which one is historical/outdated).
> **Status**: active (architecture index). This file is **not** the source of truth for capability claims, nor does it duplicate any capability tiering.
> **Owner lane**: brain-studio (paired with `docs/architecture/README.md` and each module's `CLAUDE.md`).
> **Source-of-truth priority** (high → low): code / topic schema ＞ `docs/runbook/baseline-evidence/2026-06-04-hitl/` (the latest and only trusted snapshot, SHA `78fbf36`, readiness=`not_ready`) ＞ `docs/mission/2026-06-18-capability-claim-matrix.md` (canonical Capability Claim Matrix) ＞ `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B (basis for claim adjudication) ＞ `docs/architecture/specs/2026-06-18-capability-baseline-spec.md` (thresholds / how to measure) ＞ `docs/mission/2026-06-18-demo-north-star.md` (strategic boundaries) ＞ this directory (architecture) ＞ `docs/contracts/interaction_contract.md` (topic/action schema, v2.5 frozen).
> **Maintained child files**: `overview.md` (current architecture overview), `designs/clean-architecture.md`, `designs/data-flow.md` (both partially outdated, see table below).
> **Archived / historical boundary**: `0511/**` is the **5/11 freeze-snapshot** (retained for reference, **not maintained in parallel**); anything about "what can run right now" must defer to the canonical claim matrix, not to the 0511 snapshot or the older diagrams in designs.
> **This README is not**: the source of truth for capability claims (→ canonical claim matrix), the threshold definitions (→ `specs/2026-06-18-capability-baseline-spec.md`), or the interface contract (→ `docs/contracts/interaction_contract.md`).

---

## Architecture Documentation Guide

| Document | Status | Contents |
|---|---|---|
| [`overview.md`](overview.md) | active (architecture source of truth); capability claims/timeline superseded | An integrated overview of Brain (decision engine) × Studio (operation & observation interface): goals, system architecture, data flow, module responsibilities, degradation chains, deployment topology. The **6/05 note at the top** explains which capability claims have been superseded by the 6/04 baseline + 6/05 audit. |
| [`designs/clean-architecture.md`](designs/clean-architecture.md) | ⚠️ partially outdated | The four-layer Clean Architecture principles (3/08). The principles are still worth referencing, but the implementation status differs from the document's description (only `go2_robot_sdk` is fully implemented, as noted in the banner at the top). |
| [`designs/data-flow.md`](designs/data-flow.md) | ⚠️ outdated (structural divergence) | Early (3/13) data-flow and interaction-flow diagrams. The banner at the top flags the known divergences; **defer to `docs/contracts/interaction_contract.md`**. |

---

## 5/11 freeze-snapshot (`0511/`, historical reference, not maintained in parallel)

> `0511/` is the **frozen architecture snapshot of each lane as of 5/11** (runtime flow / graph node map / persona-capability-memory / debug runbook, etc., split per lane). It is a photograph of the architecture during that demo sprint, **retained for reference**: it is useful for understanding "what a given chain looked like as of 5/11", but it **must not be used as the basis for "what can run right now / whether a capability passes"**. Capability tiering always defers to the canonical claim matrix.

| lane | snapshot entry |
|---|---|
| Brain | `0511/brain.md` → `0511/brain/` (runtime-flow / graph-node-map / persona-capability-memory / debug-runbook) |
| Face | `0511/face.md` → `0511/face/` |
| Gesture | `0511/gesture.md` → `0511/gesture/` |
| Pose | `0511/pose.md` → `0511/pose/` |
| Object | `0511/object.md` → `0511/object/` |
| Nav | `0511/nav.md` → `0511/nav/` |
| Speech | `0511/speech.md` → `0511/speech/` |
| Studio | `0511/studio.md` → `0511/studio/` |

---

## Whether a capability passes / what can be claimed (not duplicated here, linked to canonical)

- **canonical Capability Claim Matrix**: `docs/mission/2026-06-18-capability-claim-matrix.md` (adjudication source: 6/05 audit §B, baseline `docs/runbook/baseline-evidence/2026-06-04-hitl/`).
- **Capability thresholds / how to measure** (provisional until baseline): `docs/architecture/specs/2026-06-18-capability-baseline-spec.md`.
- **Strategic boundaries / do-not-say list**: `docs/mission/2026-06-18-demo-north-star.md`.
- **Interface contract** (topic / action / service schema, v2.5 frozen): `docs/contracts/interaction_contract.md`.
