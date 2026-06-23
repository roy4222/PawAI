# PawAI Documentation Entry Point

**English** | [中文](./README.zh.md)

**Project**: Elder and Dog / PawAI
**Positioning**: A home quadruped embodied interaction robot (70% interaction / 30% guardianship). The mainline documentation lives under the lanes below.

> **30-second rule**: If you cannot find the information within 30 seconds → go to `architecture/` (including `architecture/navigation/`); if that still fails, check whether the `archive/` at the repo root retains the retired code.
>
> **Demo claim truth**: Any question of "whether a capability passes / whether it can be claimed" is always adjudicated by the EVIDENCE_AUTHORITY order in §Conflict Arbitration, not by any narrative document.

---

## Mainline Documents (active)

| # | Lane | Entry | Contents |
|:-:|------|------|------|
| 1 | **Brain** | [architecture/README.md](architecture/README.md) | Interaction mainline: perception / speech / Studio / Brain decision layer |
| 2 | **Navigation** | [architecture/navigation/README.md](architecture/navigation/README.md) | Mobility mainline: LiDAR / Nav2 / AMCL / D435 depth / obstacle avoidance |
| 3 | **Contracts** | [contracts/README.md](contracts/README.md) | Cross-lane ROS2 interface contract + design principles |
| 4 | **Runbook** | [runbook/README.md](runbook/README.md) | Demo firefighting SOP (Jetson / Network / GPU server / Go2 operations) |
| 5 | **Mission** | [mission/README.md](mission/README.md) | Project positioning / Demo script / eight-feature SoT; 6/18 strategic boundary north-star v2 (do-not-say list) |
| 6 | **Deliverables** | [deliverables/](deliverables/) | Semester submission materials (thesis) |

## Supporting Folders (active, not the mainline truth layer)

> Tool manuals / process configuration / production guides / persistent decisions / research. **Not capability or product truth** — capability pass/fail always defers to baseline-evidence (see §Conflict Arbitration).

| Folder | Entry | Role |
|--------|------|------|
| **ADR** | [adr/](adr/) | Persistent architecture decisions (one decision at a time, can be superseded). ADR-0001/0002 pending formal amendment by north-star v2 |
| **Agents** | [agents/](agents/) | AI agent / skill operation configuration (domain / issue-tracker / triage / HITL evidence-gathering process). Process configuration, not product truth |
| **PawAI CLI** | [pawai_cli/README.md](pawai_cli/README.md) | Single-entry CLI manual for the five-person shared Jetson (used together with the runbook) |
| **PawAI Demo** | [pawai-demo/](pawai-demo/) | Demo production / slides / video / report writing guide (production process, not capability truth) |
| **Research** | [research/](research/) | General research (not lane-bound). research-not-truth, does not override baseline-evidence / contracts |

## History

| # | Lane | Entry | Contents |
|:-:|------|------|------|
| 7 | **Archive** | [archive/](archive/) | Retired packages and scripts (excluding internal historical documents) |

---

## Conflict Arbitration (who is the source of truth)

In a conflict, arbitrate from high to low; **the latest empirical evidence takes priority**. Whether a capability passes, whether it can enter the Brain mainline, and whether it can be claimed on 6/18 all defer to this order.

| # | Tier | Source of Truth |
|:-:|------|---------|
| 0 | **Code / runtime topic schema** | Always the final truth |
| 1 | **Empirical evidence (empirical, TOP)** | [runbook/baseline-evidence/2026-06-04-hitl/](runbook/baseline-evidence/2026-06-04-hitl/) — the only currently trusted snapshot (SHA 78fbf36, readiness=not_ready). The capability grades + honesty caveats in its README are the final fact for capability pass/degraded/fail/insufficient. READ-ONLY evidence data. `2026-06-03-first-trusted-face/` has been superseded and is kept only as history |
| 2 | **Convergence audit (read-only)** | (6/05 convergence audit — removed from the public version, see internal history) — the authority for adjudicating 6/18 claim-scope / whether to swap models / docs-drift. It is itself research and does not override baseline data |
| 3 | **Capability spec (how to measure)** | [architecture/specs/2026-06-18-capability-baseline-spec.md](architecture/specs/2026-06-18-capability-baseline-spec.md) — the sole source of truth for how the 15 capabilities are measured and what counts as a pass (thresholds provisional). Grade results defer to #1 |
| 4 | **Strategic boundary (what to claim)** | [mission/2026-06-18-demo-north-star.md](mission/2026-06-18-demo-north-star.md) v2 — 6/18 positioning, do-not-say list, scoreboard-first, scope tiering. Amends ADR-0001/0002. Whether a capability passes still defers to #1 |
| 5 | **Interface contract** | [contracts/interaction_contract.md](contracts/interaction_contract.md) (ROS2 topic / action / service / message schema, v2.5 frozen) |
| 6 | **Module design truth** | `architecture/{brain,perception/*,speech,studio,specs}/`, `architecture/navigation/{setup,specs}/` (each carrying a module `CLAUDE.md`; internal historical documents are not included in the public version) |
| 7 | **Product direction / Demo script / eight features** | [mission/README.md](mission/README.md) |
| 8 | **Persistent decisions** | [adr/](adr/) (ADR, can be superseded by a new proposal) |
| 9 | **Environment setup and firefighting SOP** | [runbook/](runbook/) |

**EVIDENCE_AUTHORITY (latest first)**: `runbook/baseline-evidence/2026-06-04-hitl/` ＞ 6/05 convergence audit ＞ 2026-06-18-capability-baseline-spec ＞ 2026-06-18-demo-north-star. 6/03 first-trusted is history.

**canonical claim matrix**: Each capability's Current Claim / Claim Level / Evidence-Provenance / Pass-Degraded-Fail-Insufficient / Fallback / Non-Claims / Model Candidates / Next Retest defers to #1–#4 above, and **is not duplicated as full prose in each file** — always link back to the baseline-evidence README + convergence audit.

**Key principle**: Empirical ＞ audit ＞ spec ＞ narrative. `research/` is always research-not-truth (except the 6/05 convergence audit, which is designated and promoted to #2); retired code lives in the repo-root `archive/` and is not part of the current truth.

---

## Documentation Governance

- **Do not proactively rewrite documents you have not touched** — only sync the corresponding `README.md` after changing the code
- **Adding / removing a ROS2 topic** → sync `contracts/interaction_contract.md`
- **End of each workday** → update `references/project-status.md` (under the repo-root `references/`, not under `docs/`)
- **Naming convention**: `YYYY-MM-DD-description.md` (plan / spec / research)

See this file's commit history for details.

---

*Last reorg: 2026-05-02 (overturned the 5/13 pre-demo policy and executed it early; 18 top-level → 7 active + archive)*
