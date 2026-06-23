# PawAI Brain

**English** | [中文](./README.zh.md)

> **Scope**: The **architectural source-of-truth layer** for "how the PawAI interaction mainline understands, decides, speaks, and presents" — Brain decision-making / Studio / speech / perception(face,gesture,pose,object) / architecture / specs / plans.
> **Status**: active (architectural source-of-truth layer). This file is **NOT** the source-of-truth for "current capability claims" — whether any brain / perception capability passes / may enter the Brain mainline is always governed by the canonical claim matrix (see the "Brain capability claims" section below).
> **Owner lane**: brain-studio (used together with each module's `CLAUDE.md` / `perception/*` working rules).
> **Source-of-truth priority** (high→low): code / topic schema ＞ `docs/runbook/baseline-evidence/2026-06-04-hitl/` (measured, the latest and only trusted snapshot, SHA `78fbf36`, readiness=`not_ready`) ＞ `docs/mission/2026-06-18-capability-claim-matrix.md` (canonical Capability Claim Matrix) ＞ `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B (basis for claim adjudication) ＞ `docs/architecture/specs/2026-06-18-capability-baseline-spec.md` (thresholds / how to measure, provisional until baseline) ＞ `docs/mission/2026-06-18-demo-north-star.md` (strategic boundaries / forbidden-claims list) ＞ this file (architecture) ＞ `docs/contracts/interaction_contract.md` (topic/action schema, v2.5 frozen).
> **Maintained child files**: `architecture/README.md` (architecture index), `architecture/overview.md` (Brain × Studio integration overview), `specs/`, `plans/`, `speech/README.md`, `studio/README.md`, `perception/{face,gesture,pose,object}/` (each with its own `CLAUDE.md`).
> **Archived / historical boundary**: `architecture/0511/**` is the **5/11 freeze-snapshot** (kept for reference, not re-maintained); `docs/archive/2026-05-docs-reorg/superpowers-legacy/` is entirely frozen; `research/*.md` is always **research-not-truth** (sole exception: the 6/05 convergence audit, which was specifically promoted to evidence-hierarchy #2).
> **This README is NOT**: the source-of-truth for capability claims (→ canonical claim matrix), the threshold definition (→ `specs/2026-06-18-capability-baseline-spec.md`), an operations manual (→ `docs/runbook/`), or the product script (→ `docs/mission/README.md`).

---

## In one sentence

**PawAI Brain is the decision layer that turns multimodal perception (face / speech / gesture / pose / object) into a SkillPlan; the LLM only offers suggestions, only the Executive executes, and every physical action passes through the Safety Gate.**

---

## Brain capability claims (references canonical, do not duplicate the whole thing here)

> **Authority**: `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B Capability Claim Matrix (brain rows), benchmarked against `docs/runbook/baseline-evidence/2026-06-04-hitl/` (the latest and only trusted snapshot). The below is only an entry-point summary — details are not duplicated here.

- **Current Claim**: The Brain safety-layer refusal mechanism **exists and passes unit tests** (`safety_gate.py` hard-short-circuits "stop / emergency" to bypass the LLM; the skill allowlist blocks unauthorized skills).
- **Claim Level**: safety-layer mechanism = **CLAIM_WITH_CAVEAT (limited to mechanism-exists + unit-test level)**; anti-hallucination = **DO_NOT_CLAIM**; `brain.skill_gate` / `brain.trace` = **insufficient_data** (n=0, `brain_allowed=false`).
- **Evidence-Provenance**: `docs/runbook/baseline-evidence/2026-06-04-hitl/` + code (`pawai_brain/personas/v1/`, `world_state_builder.py`).
- **Pass / Degraded / Fail / Insufficient**: safety layer = mechanism exists (no e2e N-times interception measurement done); anti-hallucination = **fail** (6/4 operator observed fabricated rain / seeing a cup / pose); skill_gate / trace = **insufficient_data**.
- **Fallback / safety rules**: deterministic safety hard rule + banned_api gate + LLM `selected_skill` diagnostic-only; LLM down → say_canned; Brain down → when the single exit breaks, it really breaks.
- **Non-Claims (forbidden)**: must not claim "Brain never hallucinates / only speaks of real sensing / passed the anti-hallucination test / persona naturalness is verified", must not present `brain.skill_gate` as pass, must not stage network weather "it's raining outside" as real perception. May claim deterministic safety / allowlist; do not claim a "non-hallucinating autonomous agent".
- **Model Candidates**: see `docs/archive/pawai-brain-legacy/research/2026-06-02-model-candidate-registry.md` (research-not-truth; tiered BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH, not presumed to be an implementation backlog).
- **Next Retest**: safety-layer e2e N≥10 dangerous / unauthorized commands 100% intercepted + still effective after long idle + negative case; anti-hallucination requires implementing a grounding verifier + removing the hallucination few-shot + disabling the `_get_weather()` injection. Tiering of each perception capability (face / object.cup / voice / gesture / pose) always follows the canonical claim matrix.

---

## Architecture mainline (whether a capability passes always returns to the canonical claim matrix)

> The following is Brain's **architectural composition** (mechanism existence), **NOT** a capability-pass claim. Whether "this demo segment can be presented, and which layer it belongs to" always returns to the canonical claim matrix + North Star §5 forbidden-claims list. Starting from the 6/05 professor meeting we adopt **scoreboard-first**: first quantify capabilities (pass / degraded / fail / insufficient gate Brain), then decide whether to swap models, and do not presume model research to be an implementation backlog.

- **Skill Registry** — 27-entry SkillContract (Active / Hidden / Disabled / Retired + per-entry demo metadata); the OK three-layer secondary-confirmation principle. The mechanism exists; whether a capability goes on stage follows the claim matrix.
- **Three-layer decision-making** — Safety (deterministic hard rule + banned_api gate) → Policy (rule router + arbitration) → Expression (reply / tone / Studio bubble). Safety layer = CLAIM_WITH_CAVEAT (mechanism exists + unit test); anti-hallucination = DO_NOT_CLAIM.
- **LLM / TTS provider chain** — cloud mainline → fallback → local → RuleBrain / Piper (the specific providers are governed by the code + `speech/README.md`). Model tiering BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH, see `research/2026-06-02-model-candidate-registry.md` (research-not-truth).
- **Conversation Engine** — `pawai_brain` LangGraph stateful graph, `conversation_engine` / `conversation_shadow_engine` feature flag; the legacy `llm_bridge_node` can still be switched back to (see `architecture/overview.md` §3.5).
- **Studio Brain Skill Console** — Brain Status Strip + Trace Drawer + Skill Buttons. Studio evidence display / provenance has value, but it **does not equal a capability pass** (unless bound to trusted baseline data). `studio.evidence` was insufficient_data on 6/04.

---

## Documentation navigation

> Entry-point navigation. Capability tiering returns to the canonical claim matrix; thresholds return to the 6/18 capability-baseline-spec.

| File / path | Content |
|---|---|
| **Entry page (this file)** | `docs/architecture/README.md` |
| **Architecture index** | `docs/architecture/brain/README.md` |
| **Architecture overview** (Brain × Studio integration) | `docs/architecture/brain/overview.md` |
| **canonical Capability Claim Matrix** (source-of-truth for capability tiering) | `docs/mission/2026-06-18-capability-claim-matrix.md` (adjudication source: 6/05 audit §B) |
| **Capability thresholds / how to measure** (provisional until baseline) | `docs/architecture/specs/2026-06-18-capability-baseline-spec.md` |
| **Strategic boundaries / forbidden-claims list** | `docs/mission/2026-06-18-demo-north-star.md` |
| **Latest measured trusted snapshot** (final fact for capability pass/fail) | `docs/runbook/baseline-evidence/2026-06-04-hitl/` |
| **Phase A Brain MVS spec** | `docs/architecture/specs/2026-04-27-pawai-brain-skill-first-design.md` |
| **PawClaw evolution spec** | `docs/architecture/specs/2026-04-27-pawclaw-embodied-brain-evolution.md` |
| **Interface contract** (v2.5 frozen) | `docs/contracts/interaction_contract.md` |
| **PawAI Studio design** | `docs/architecture/studio/README.md` |

---

## Legacy / Archive

Older research, historical decisions, and each module's README still remain in their original locations:
- `docs/archive/pawai-brain-legacy/architecture-0511/` — **5/11 freeze-snapshot** (each lane's 5/11 frozen snapshot, kept for reference, not re-maintained; only noted in `architecture/README.md` as a freeze-snapshot)
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/` — design spec history (4/10 guardian dog / 4/11 home interaction / 4/27 brain MVS / pawclaw evolution / 5/01 sprint), all frozen
- `docs/architecture/speech/` `docs/architecture/perception/face/` `docs/architecture/perception/gesture/` `docs/architecture/perception/pose/` `docs/architecture/perception/object/` — authoritative documents for each perception module (each with its own `CLAUDE.md` working rules)
- `docs/architecture/studio/` — existing Studio design

This folder maintains the **architectural source-of-truth** for the interaction mainline; older documents are kept as history and for reference, not re-maintained. Whether a capability passes always returns to the canonical claim matrix and is not duplicated in full within narrative documents.
