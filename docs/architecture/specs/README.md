# PawAI Brain Specs Index

**English** | [中文](./README.zh.md)

> **Scope**: The "design spec" layer of the Brain / Studio / interaction mainline (how it is designed, how it is measured). This folder is NOT the source of truth for capability grades.
> **Status**: active index ｜ **Owner lane**: pawai-brain ｜ **Created**: 2026-06-05
> **Source-of-truth priority (where this layer sits in the whole-repo hierarchy)**:
> - The final fact on whether a capability "passes / may enter the Brain mainline" → [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) (trusted snapshot `78fbf36`, readiness=`not_ready`).
> - The lookup table for "may we claim it, which grade does it belong to" → [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md) (canonical claim matrix; **do not duplicate the whole prose in this layer — always link**).
> - What this folder governs is "**how to measure, how to design**" (measurement / design truth); grade results are not decided here.
> **Maintained child files**: see the table below. **Archived-legacy boundary**: anything tagged `legacy` is a design from the May sprint, kept as history, **no longer updated and must not be treated as 6/18 truth**; to find out how 6/18 is measured, see the current one.
> **What this index is NOT**: not a plan (implementation steps are in `../plans/README.md`), not research (model candidates/investigation are in `../research/README.md`), not a contract (the ROS2 schema is in [`../../contracts/interaction_contract.md`](../../contracts/interaction_contract.md)).

---

## current (6/18 measurement truth)

| File | Role | Status |
|---|---|---|
| [`2026-06-18-capability-baseline-spec.md`](2026-06-18-capability-baseline-spec.md) | **The single source of truth (measurement truth) for "how the 15 capabilities are measured, what counts as pass"** | current (thresholds provisional until baseline) |

> Note: the baseline-spec defines the measurement protocol, but **capability grade results are governed by the baseline-evidence snapshot** (see the authority chain above). The thresholds in the spec are provisional until the baseline has been run.

## current (design specs, still referenced)

| File | Role |
|---|---|
| [`2026-04-27-pawai-brain-skill-first-design.md`](2026-04-27-pawai-brain-skill-first-design.md) | Brain Skill-First MVS system design (current) |
| [`2026-04-27-pawclaw-embodied-brain-evolution.md`](2026-04-27-pawclaw-embodied-brain-evolution.md) | Embodied Brain evolution design Phase A→B (coexists with MVS) |
| [`2026-05-06-conversation-engine-langgraph-design.md`](2026-05-06-conversation-engine-langgraph-design.md) | Conversation Engine × LangGraph shadow design |
| [`2026-05-07-capability-aware-self-demonstration-design.md`](2026-05-07-capability-aware-self-demonstration-design.md) | Capability-Aware self-demonstration design |
| [`2026-05-14-spec-a-demo-mainline-stop-bleed.md`](2026-05-14-spec-a-demo-mainline-stop-bleed.md) | Demo mainline stop-bleed design freeze |

## legacy (May sprint period, history, not 6/18 truth)

| File | Role | Why legacy |
|---|---|---|
| [`2026-05-01-pawai-11day-sprint-design.md`](2026-05-01-pawai-11day-sprint-design.md) | 5/12 school demo 11-day battle map | the sprint has passed; the positioning has been superseded by the 6/18 north-star |
| [`2026-05-04-llm-eval-result.md`](2026-05-04-llm-eval-result.md) | 5/4 LLM eval result | a result snapshot; the model mainline has been updated several times |
| [`2026-05-04-phase-b-implementation-notes.md`](2026-05-04-phase-b-implementation-notes.md) | Phase B working notes | paired with the 5/01 sprint, now passed |
| [`2026-05-05-jetson-smoke-result.md`](2026-05-05-jetson-smoke-result.md) | 5/4 Jetson smoke result | a one-off result snapshot |
| [`2026-05-05-tts-rewrite-result.md`](2026-05-05-tts-rewrite-result.md) | TTS provider overhaul result | a one-off result snapshot |
| [`2026-05-09-interaction-quality-improvements-design.md`](2026-05-09-interaction-quality-improvements-design.md) | Interaction quality improvement design | 5/9 sprint period |
| [`2026-05-10-demo-quality-roadmap-index.md`](2026-05-10-demo-quality-roadmap-index.md) | 6-spec roadmap index | self-described as superseded by the Demo Readiness Master Plan |
| [`2026-05-10-llm-naturalness-a-plus-design.md`](2026-05-10-llm-naturalness-a-plus-design.md) | LLM naturalness A+ design (draft) | sprint-period draft |
| [`2026-05-10-spec2-gesture-interaction-design.md`](2026-05-10-spec2-gesture-interaction-design.md) | Gesture interaction design (draft) | sprint period; gesture claims are governed by the claim matrix (`gesture.wave` currently fail) |
| [`2026-05-10-spec3-pose-interaction-design.md`](2026-05-10-spec3-pose-interaction-design.md) | Pose interaction design (draft) | sprint period; pose is Studio-only/insufficient (see claim matrix) |
| [`2026-05-10-spec4-object-perception-design.md`](2026-05-10-spec4-object-perception-design.md) | Object perception upgrade design (draft) | sprint period; object is only the narrow `object.cup` version (see claim matrix) |
| [`2026-05-10-spec5-navigation-roadmap.md`](2026-05-10-spec5-navigation-roadmap.md) | Navigation roadmap (draft) | sprint period; nav is insufficient_data, does not claim dynamic obstacle avoidance/autonomous driving |
| [`2026-05-10-spec6-studio-ux-polish.md`](2026-05-10-spec6-studio-ux-polish.md) | Studio UX polish (draft) | sprint period |
| [`2026-05-07-pawai-demo-test-checklist-v2.md`](2026-05-07-pawai-demo-test-checklist-v2.md) | 5/13–18 demo test checklist | sprint-period test checklist |
| [`2026-05-07-pawai-demo-test-fail-map.md`](2026-05-07-pawai-demo-test-fail-map.md) | 5/7 night fail-map | sprint-period snapshot |
| [`2026-05-07-pawai-demo-test-plan.md`](2026-05-07-pawai-demo-test-plan.md) | demo acceptance test plan v1 | sprint period |

> Capability claims in the legacy section (gesture/pose/object/nav) are always governed by the [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md) and the baseline-evidence; the wording of these May drafts must not be used as 6/18 claims.
