# Navigation

**English** | [中文](./README.zh.md)

> **Scope**: The **architectural source-of-truth layer** for PawAI mobility (localization / mapping / obstacle avoidance / short-distance movement) — "how the stack is assembled, which action path is real, and which are historical/research."
> **Status**: active (architectural source-of-truth layer). This file **no longer** serves as the source-of-truth for "current capability claims" — whether any nav capability passes / whether real motion is allowed is governed solely by the nav row of the canonical claim matrix in §"nav capability claim".
> **Owner lane**: nav (paired with the module working rules in `docs/architecture/navigation/CLAUDE.md`).
> **Source-of-truth priority** (high→low): code / topic schema ＞ `docs/runbook/baseline-evidence/2026-06-04-hitl/` (measured, nav all `insufficient_data`) ＞ `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §4 (convergence audit: nav downgraded to Studio-display-only, zero real-robot self-driving) ＞ `docs/mission/2026-06-18-demo-north-star.md` §7 (strategic boundary) ＞ this file (architecture) ＞ `docs/contracts/interaction_contract.md` (nav topic/action schema).
> **Maintained child files**: `CLAUDE.md` (working rules), `legacy-readme-from-導航避障.md` (existing authoritative README), `2026-05-11-architecture-deep-audit-and-fix-roadmap.md` (4-mode reactive stop / B-burndown architectural truth).
> **Archived / historical boundary**: `plans/*.md` (5/1–5/4 sprint plans), `research/*.md`, and `legacy-archive/` are all **historical / research-only** — not maintained in duplicate and must not be used as the basis for "what can run right now."
> **This README is NOT**: the source-of-truth for capability claims (→ canonical claim matrix), an operations manual (→ runbook, safest = `docs/runbook/2026-06-18-hitl-oneshot-runbook.md`), or the threshold definition (→ `docs/architecture/specs/2026-06-18-capability-baseline-spec.md`).

---

## nav capability claim (references the canonical; do not duplicate the whole thing here)

> **Authoritative**: the nav row of §B Capability Claim Matrix + §4 in `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`, with `docs/runbook/baseline-evidence/2026-06-04-hitl/` as the baseline. Below is just an entry-point summary.

- **Current Claim**: the four nav capabilities (`nav.short_move` / `nav.safe_stop` / `nav.no_auto_resume` / `nav.dynamic_avoidance`) are all **`insufficient_data`** in the 6/4 trusted snapshot.
- **Pass / Degraded / Fail / Insufficient**: **Insufficient_data** (no trusted motion record).
- **Real action path**: manual short-distance goto goes through `/nav/goto_relative` (action), triggered by `scripts/send_relative_goal.py`; the observed value is the action Result that script prints (`success` / `message` / `actual_distance`). **The `/event/nav/mission` topic does not exist in any source** — do not echo it (it will hang forever); see the doc-bug note in `docs/runbook/2026-06-18-baseline-runbook.md`.
- **Fallback / safety rule**: nav is always **dry-run / fail-closed**, unless there is an explicit override **and** the safety gate (`nav.safe_stop` + `nav.no_auto_resume`) passes. A dry-run only proves fail-closed + that the action chain is connected (AMCL not localized → `amcl_lost` abort, Go2 never moves) — it is **not real movement, not dynamic avoidance / self-driving**.
- **Non-Claims (must not say)**: must not claim 6/18 dynamic avoidance / autonomous detour / self-driving; nav defaults to Studio / Foxglove display only with zero real-robot self-driving (North Star §7 + convergence audit §4).
- **Next Retest**: real motion can only be discussed after the HITL on-robot localization F7 (no publisher on `/cmd_vel_nav` after goal accept) + the recorder/behavior redesign of the two safety items. The safest operator runbook = `docs/runbook/2026-06-18-hitl-oneshot-runbook.md` (nav = pure DRY-RUN section).

---

## In one sentence (architectural source-of-truth layer, not a current capability claim)

**Navigation is PawAI's mobility capability — RPLIDAR-A2M12 provides 2D `/scan` + SLAM (offline mapping) + AMCL (runtime localization) + Nav2 (planning), and D435 depth provides the close-range safety gate; two Capability Bools (`/capability/nav_ready` + `/capability/depth_clear`) feed the Pre-action Validate of the Brain Executive.**

---

> **The following 5/2–5/12 sprint sections are historical sprint records (kept for reference).** Language such as "dynamic avoidance / detour / Wow" therein refers to 5/12 sprint goals, which **have been downgraded by the 6/5 convergence audit §4 + North Star §7 to Studio display only, with zero real-robot self-driving**. Current nav capability is governed solely by the "nav capability claim" (canonical claim matrix) above; do not treat these sprint sections as "what can run right now."

## 5/2 progress update (historical)

Phase A Step 1+2+3 complete (commit `a3bdd2e`): BUG #2 fixed (`nav_action_server` subscribes to `/state/nav/paused` + 10s pose-progress timeout, K1 3/3 + K-pause passed on real robot), `/capability/depth_clear` fail-closed shipped, `/capability/nav_ready` v0.5 basic shipped.
Phase A Step 4 (Executive wiring) completed the same day: WorldState subscribes to all three capabilities (fail-closed) + SafetyLayer adds the three gates nav_paused / NAV / MOTION (27 cases pass + 92/92 regression).
**day 2 to-do**: wire up launch / Brain rules / Studio LED / upgrade `nav_ready` to lifecycle+TF+costmap.

## 5/4 Scope Freeze and Bug Diagnosis

The 5/3 nighttime teardown confirmed that the root cause of the repeated detour failures is two chained bugs, **B1** (`nav_action_server` does not enforce max_speed, a 0.5m goal travels 1.04m) + **B2** (AMCL `update_min_d=0.10` does not converge while stationary) — **not a DWB design problem, not the venue, not the sensor**.

See `plans/2026-05-04-demo-scope-freeze.md` for details — including strategic framing, the complete bug backlog (B1-B5), environment pitfalls (E1-E10), operational lessons (O1-O4), physical limits (P1-P4), acceptance V1-V9, and defense framing.

Phase 2 code changes will be split into independent small PRs (PR 1-7), **outside this scope freeze**.

## Current mainline (5/12 sprint week)

- **Mapping layer**: cartographer (offline, already produced `home_living_room_v8.pbstream + .yaml`; slam_toolbox is permanently abandoned on this hardware)
- **Localization layer**: AMCL (loads an existing map, K1 baseline 5/5 PASS @ 5/1)
- **Planning layer**: Nav2 BT navigator + DWB controller (`min_vel_x ≥ 0.45` corresponding to the Go2 sport mode 0.50 m/s threshold)
- **Dynamic obstacle avoidance**: `reactive_stop_node` (D435+LiDAR dual source, Phase 4 v0) + `/state/nav/paused` global pause state (added in Phase A)
- **Capability Gate** (added in Phase A):
  - `/capability/nav_ready` — Nav2 active + AMCL covariance < 0.20 + local costmap healthy
  - `/capability/depth_clear` — D435 ROI within 1m ahead / obstacle < 0.4m
- **nav_capability platform layer**: `goto_relative` action (Phase A fixed BUG #2) + `run_route` + `log_pose`

---

## 5/12 Demo must-dos (5 lifelines)

> See `plans/2026-05-04-demo-scope-freeze.md` for the Scope Freeze

1. **`nav_demo_point` 5/5 PASS** — corresponds to Storyboard Scene 2 ★Wow A
   *Condition*: B1 (`nav_action_server` max_speed enforce) + B2 (AMCL plateau) fixed
2. **D435 + LiDAR dual-source reactive stop** — forced stop when obstacle < 0.6m
3. **Pause-Resume or safe abort** — resume when obstacle cleared / abort after 10s of no progress
4. **`/capability/nav_ready` upgrade** (lifecycle + TF + scan freshness, three items; **do only these three, add no more**)
5. **30-minute continuous power test with 0 outages** (2464 buck-boost constant-voltage constant-current module acceptance)

### Wow bonus (do only if conditions are met)

- `approach_person` 1 PASS — corresponds to Scene 7 ★★Wow C (can be cut)
- **Detour profile** — ★ Wow, **condition: after B1+B2 are fixed**; on failure fall back to stop+resume
- Studio / Foxglove display `nav_ready` level + reasons

---

## Document map

| File / path | Content |
|---|---|
| **Entry page (this file)** | `docs/architecture/navigation/README.md` |
| **Phase A Implementation Plan** (5/2-5/3 attack) | `docs/archive/navigation-legacy/plans/2026-05-01-phase-a-nav-attack.md` |
| **Sprint design mainline** (includes §5 D435+RPLIDAR integration / §6 two-layer Capability Gate / §7 Phase A) | `docs/architecture/specs/2026-05-01-pawai-11day-sprint-design.md` |
| **Existing design specs** | `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`<br/>`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-26-nav-capability-s2-design.md` |
| **Interface contract** (nav-related topics + actions) | `docs/contracts/interaction_contract.md` |
| **Safest operator runbook** (nav = pure DRY-RUN section, fail-closed) | `docs/runbook/2026-06-18-hitl-oneshot-runbook.md` |
| **Baseline measurement runbook** (includes the `/event/nav/mission` doc-bug note) | `docs/runbook/2026-06-18-baseline-runbook.md` |
| **Capability claim canonical matrix** (nav row) | `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B/§4 |
| **Existing authoritative Nav README** (historical) | `docs/architecture/navigation/legacy-readme-from-導航避障.md` |
| **Nav CLAUDE.md** (module working rules) | `docs/architecture/navigation/CLAUDE.md` |

---

## 5/2 external Stack research (8 docs) — research-only

> **Everything under `docs/archive/navigation-legacy/research/*` is research-not-truth**: it is absorption analysis / daily probing records, **does not override baseline-evidence or contracts**, and must not be taken as the basis for "implemented / verified." The model/stack research tiers = BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH — do not let them become an implementation backlog by default.

Conducted an absorbability analysis of 8 open-source projects (Odin / OM1 / NavDP / visualnav-transformer / amigo_ros2 / DimOS + 1 paper).
**Overall synthesis and priority**: `research/2026-05-02-research-synthesis.md` — lists 4 items immediately absorbable in Phase A (A1-A4), 7 P2 items after 5/12, 6 P3 items after June, and the things explicitly not done.

## Legacy / Archive (historical)

Historical records / research / daily logs prior to 5/1 remain in place:
- `docs/archive/navigation-legacy/research/` — 4/27-5/1 LiDAR mount yaw / AMCL 180° / K1 baseline / Phase 4-7 critical bugs
- `docs/archive/navigation-legacy/research/lidar-dev/` — 4/27 lidar dev roadmap
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-{24,26}-*.md` — Phase 1-4 design

This folder **only** maintains the 5/12 Demo sprint period + later mainline versions; old documents are kept for history and reference, not maintained in duplicate.

---

## Known pitfalls (summary; full list in `docs/architecture/navigation/CLAUDE.md`)

- **Go2 sport mode `cmd_vel` threshold MIN_X = 0.50 m/s** — DWB `min_vel_x` must be ≥ 0.45, otherwise Go2 refuses to lift its legs
- **slam_toolbox is permanently abandoned on ARM64 + Humble + RPLIDAR** (Mapper FATAL ERROR known bug)
- **Do not `ros2 topic pub --once /goal_pose`** — the bt_navigator subscriber is BEST_EFFORT; use `-r 2 --times 5` instead
- **D435 RGB-D topic uses a double namespace** `/camera/camera/aligned_depth_to_color/image_raw`
- **XL4015 power instability** — since 4/27, 8+ Jetson outages while Go2 is running; the biggest Demo risk, awaiting the KREE DL241910
