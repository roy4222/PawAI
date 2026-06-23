# Contracts — Cross-Lane ROS2 Interface Contract

**English** | [中文](./README.zh.md)

> **Governance**
> - **Scope**: ROS2 topic / action / service / message schema + design principles jointly observed by the Brain lane (pawai-brain/) and the Navigation lane (navigation/).
> - **Status**: active / source-of-truth (conflict arbitration #5). `interaction_contract.md` v2.5 frozen.
> - **Owner lane**: shared across lanes; adding/removing a topic is PR-reviewed here first, then each module follows up.
> - **Source-of-truth priority**: code / runtime topic schema ＞ this contract. Whether a capability passes is **not decided here** — refer to EVIDENCE_AUTHORITY in [`../README.md` §Conflict Arbitration](../README.md) (baseline-evidence is authoritative).
> - **Maintained child files**: `interaction_contract.md`.
> - **Archived-legacy boundary**: the original design-principles manuscript lives in `archive/2026-05-docs-reorg/architecture-misc/` (frozen, reference only).
> - **What this README is NOT**: not a capability grade, not the truth of demo claims, not module implementation status; it only defines the interface schema and the naming / QoS principles.
>
> For any change to a perception module or control logic, **change the contract first, then change the code**.

---

## Documents

| File | Content |
|------|------|
| [interaction_contract.md](interaction_contract.md) | Full ROS2 topic / action / message schema (v2.5 frozen, 5/12 demo mainline) |

---

## Design Principles (extracted from archive/2026-05-docs-reorg/architecture-misc/CLAUDE.md+AGENT.md)

### Topic Forms: Event vs State

| Type | Purpose | QoS | Naming Prefix |
|------|------|-----|---------|
| **Event** | One-shot trigger signal (Intent recognized / Gesture detected / Goal reached) | RELIABLE, KEEP_LAST(10) | `/event/...` |
| **State** | Continuous state snapshot (Face perception state 10Hz / Pose state) | BEST_EFFORT, KEEP_LAST(1) | `/state/...` |
| **Capability** | Capability gate Bool (used by Brain Executive for pre-action validate) | RELIABLE, TRANSIENT_LOCAL (latched) | `/capability/...` |
| **Cmd** | Action command (Go2 driver / Nav outlet) | RELIABLE, KEEP_LAST(10) | `/cmd_vel`, `/webrtc_req` |

### Latched Topic (TRANSIENT_LOCAL)

- Slow rate, last value is the truth → latched (e.g. `/capability/nav_ready`, `/state/perception/face`)
- High rate, only valid at the moment → not latched (e.g. `/scan`, camera image)

### Correlation ID

- Correlate events across nodes (speech → Brain → action) → the same `correlation_id`
- Format: UUID4 string
- Speech intent → Brain skill plan → Go2 cmd carries the same id throughout the chain

### Single-Outlet Principle for Actions

- All physical actions (Go2 movement, speech playback, head) have their **sole outlet in the Layer 3 Brain Executive**
- Perception modules only publish event/state and **do not publish cmd directly**
- The Safety Gate is inside the Executive (Pre-action Validate + Reactive Stop)

---

## Modification Flow

1. Edit `interaction_contract.md` — schema, QoS, field definitions
2. PR passes the contract review
3. Each module's implementation follows up
4. CI `pre-commit topic contract check` prevents implementation drift

> **Pre-commit hook**: `scripts/hooks/git-pre-commit.sh` runs the contract check, validating automatically on commit.
