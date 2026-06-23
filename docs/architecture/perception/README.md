# Multimodal Perception — Module Index

**English** | [中文](./README.zh.md)

> **Scope**: The **entry point** for the design-truth of the four perception capabilities (face / gesture / object / pose) on the PawAI interaction mainline｜**Status**: active / canonical index (module layer)
> **Owner lane**: pawai-brain / perception
> **Canonical source for capability claims**: [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md) — any question of "can we say it, which layer it belongs to" defers to that page; this index does **not** duplicate the whole prose.
> **Capability grade evidence (final fact)**: [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) (SHA `78fbf36`, run_trusted=true, readiness=`not_ready`) — grade + honesty caveats override any narrative.
> **Measurement protocol (how it's measured)**: [`docs/architecture/specs/2026-06-18-capability-baseline-spec.md`](../specs/2026-06-18-capability-baseline-spec.md).
> **What this page is not**: not the adjudication of capability pass/fail (see baseline-evidence); not the measurement protocol (see spec); does not hold code details (see each module's README). Each module README is the design truth for that module; the `research/` subtree is uniformly research-only / non-truth.

---

## Four-Capability Quick Reference (grade per the 6/04 trusted baseline)

| Capability | 6/04 grade | claim level | Module README | One-line boundary |
|---|---|---|---|---|
| `face.recognition` | 🟢 pass (narrow) | CLAIM_WITH_CAVEAT | [face/](./face/README.md) | Only **enrolled acquaintances** + empty-scene idle; **do not claim** stranger rejection / guarding / "never misrecognizes" |
| `object.cup` | 🟢 pass (narrow, close range ~1m) | CLAIM_WITH_CAVEAT | [object/](./object/README.md) | Only **~1m cup-only**; **do not claim** general-purpose / 80 classes / object finding / VLM / reliable color / 2m stable |
| `gesture.wave` | 🔴 **fail** | DO_NOT_CLAIM | [gesture/](./gesture/README.md) | camera dynamic wave **fail**; static gestures are fallback/demo-only (not a wave capability) |
| `pose.basic` / `pose.fall` | ⚪ insufficient_data | DO_NOT_CLAIM | [pose/](./pose/README.md) | basic = **Studio-only**; falls are **future, non-emergency** (`enable_fallen:=false`) |

> **Full 8-field capability card** (Current Claim / Claim Level / Evidence-Provenance / Pass-Degraded-Fail-Insufficient / Fallback / Non-Claims / Model Candidates / Next Retest) see [claim matrix §1](../../mission/2026-06-18-capability-claim-matrix.md#1-8-欄位能力卡每能力-canonical); each module README also has a corresponding capability-card quick-reference table at the top (linking back to the matrix).

---

## Terminology Discipline (one-line version; details back in [North Star §2/§5](../../mission/2026-06-18-demo-north-star.md) + claim matrix §3)

- Always "watch over / remind / report / non-contact / explainable interaction"; **forbidden**: guarding / guardian / stranger alert / protecting the elderly / care safety / fall prevention.
- Narrow-version pass does not expand: face = only Roy / empty scene, object.cup = ~1m cup-only.
- Honestly disclose fail: gesture.wave camera dynamic is not performed.
- insufficient_data only displays, does not claim: pose Studio-only.
- Model research tiers: BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH — research does **not** by default turn into an implementation backlog (claim matrix §2).

---

## Module Structure

Each capability folder has a fixed set of four files:

| File | Role |
|---|---|
| `README.md` | Module design truth (incl. capability-card quick reference + governance header) |
| `CLAUDE.md` | Claude Code module working rules (what not to do / read before changing / pitfalls / verification commands) |
| `AGENT.md` | topic interface contract (output/input schema + handoff checklist) |
| `research/` | **research-only / non-truth**: selection surveys, benchmarks, PR extraction plans (must not override baseline-evidence or contracts) |

> The authority for ROS2 topic schemas is [`docs/contracts/interaction_contract.md`](../../contracts/interaction_contract.md) (each AGENT.md is a summary mirror).
