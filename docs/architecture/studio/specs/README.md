# PawAI Studio — Specs Index

**English** | [中文](./README.zh.md)

> **Governance header**
> - **Scope**: Index of the PawAI Studio `specs/` directory — marks each spec as **current (still the design source of truth) / legacy (partially superseded) / superseded (already replaced)**, so readers don't mistake the old architecture for the current state.
> - **Status**: active / index.
> - **Owner lane**: brain-studio-lane.
> - **Source-of-truth priority**: The Studio module design source of truth lives in each spec; but **whether the architecture reflects the implementation** is determined by [`../README.md`](../README.md) (the current Studio source of truth) + the gateway code (`pawai-studio/gateway/studio_gateway.py`). **Whether a capability passes** always falls back to [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/README.md) ＞ `convergence audit` ＞ [`capability-baseline-spec`](../../specs/2026-06-18-capability-baseline-spec.md). Capability claim boundaries are bound to [`capability-claim-matrix`](../../../mission/2026-06-18-capability-claim-matrix.md). The ROS2 schema source of truth lives in [`docs/contracts/interaction_contract.md`](../../../contracts/interaction_contract.md).
> - **What this index is NOT**: It is not capability-pass proof, not a ROS2 contract, and not an implementation plan (plans live in `../plans/`).

## Specs List (current / legacy / superseded)

| spec | Topic | Status | Notes |
|------|------|------|------|
| [`2026-05-04-studio-chat-first-redesign-design.md`](2026-05-04-studio-chat-first-redesign-design.md) | chat-first main-screen redesign v2.1 | **current (design of record)** | Landed on 5/4 (see the README status card); the "awaiting approval" note in the spec body reflects its state at writing time — the implementation is complete. |
| [`2026-05-04-design-tokens.md`](2026-05-04-design-tokens.md) | chat-first design tokens (dark only) | **current** | Corresponds to `frontend/lib/design-tokens.ts` + `globals.css`. |
| [`2026-05-04-studio-redesign-feedback.md`](2026-05-04-studio-redesign-feedback.md) | UI/UX review feedback (a11y / touch / animation) | **current (review record)** | Step 10 review output; for follow-up items see the README "Next steps" phase C. |
| [`ui-orchestration.md`](ui-orchestration.md) | UI orchestration design principles (ChatGPT↔Foxglove dual mode) | **current (principle layer, v1.1)** | The concept still holds; for the concrete panel structure, defer to the README chat-first section. |
| [`event-schema.md`](event-schema.md) | Gateway ↔ Frontend JSON event / state / command schema (v1.0) | **legacy (partially aligned)** | The concept is correct; but the actual WS event fields defer to the current gateway + [`interaction_contract.md`](../../../contracts/interaction_contract.md) v2.5 (including later-added fields such as conversation_trace / capability / tts source). |
| [`brain-adapter.md`](brain-adapter.md) | LLM unified interface (Brain Adapter, v1.0) | **legacy (partially superseded)** | The principle "LLM proposes suggestions → Executive decides → Runtime executes" still holds; but the actual fallback chain defers to the README "Chat closed loop" + the five-tier fallback in `llm_bridge_node._try_openrouter_chain`. |
| [`system-architecture.md`](system-architecture.md) | System architecture (fast/slow dual system + Gateway topology, v1.0) | **🔴 LEGACY / partially superseded** | **The RTX 8000 + Redis Event Bus + ros2_bridge→Redis topology was never landed.** The current Gateway runs on **Jetson** (FastAPI+rclpy direct connection, port **8080**), with no Redis. It conflicts with the current gateway README, so **always defer to [`../README.md`](../README.md) + the gateway code**. A banner has been added at the top of the file. |

## One-line current vs legacy criteria

- **Architecture / deployment / port / endpoints**: defer to [`../README.md`](../README.md) + `pawai-studio/gateway/studio_gateway.py` (current). The RTX8000/Redis in `system-architecture.md` was an early proposal that was never landed.
- **JSON schema fields**: defer to [`interaction_contract.md`](../../../contracts/interaction_contract.md) v2.5 (ROS2 layer) + the current gateway (WS layer); `event-schema.md` is a v1.0 conceptual draft.
- **Whether a capability passes / chip color**: defer to [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/README.md) as the single trusted data source — **a Studio display does not equal a capability pass** (see the README "Studio claim boundaries").
