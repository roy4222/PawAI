# Runbook — Demo Firefighting SOP + Ops

**English** | [中文](./README.zh.md)

> **Scope**: On-site demo firefighting SOP + environment/ops + index of demo-safe startup scripts. Each file should let someone diagnose or fix a class of problems within 5 minutes.
> **Status**: active (ops source-of-truth layer).
> **Owner lane**: ops / runbook.
> **Source-of-truth priority**: This folder is the source of truth for **operational SOPs**, **not** for capability pass/fail. Whether a capability passes is always determined by `docs/runbook/baseline-evidence/2026-06-04-hitl/` (the latest and only trusted snapshot) + the canonical claim matrix (`docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`).
> **Maintained child files**: see the index below. `baseline-evidence/` is **read-only evidence data** (out of this README's maintenance scope, only referenced).
> **This README is NOT**: the source of truth for capability claims (→ baseline-evidence + canonical matrix), the source of truth for architecture (→ each lane README), or the source of truth for threshold definitions (→ `docs/architecture/specs/2026-06-18-capability-baseline-spec.md`).

---

## 6/18 baseline / HITL runbook (capability measurement)

| File | Scenario | When to open |
|------|------|---------|
| [2026-06-18-hitl-oneshot-runbook.md](2026-06-18-hitl-oneshot-runbook.md) | **Safest operator runbook** (run the baseline in one sitting; honest + safety guardrails, nav = pure DRY-RUN) | When Roy is back at Jetson+Go2 and wants to actually run the capability baseline |
| [2026-06-18-baseline-runbook.md](2026-06-18-baseline-runbook.md) | baseline measurement procedure (JSONL / snapshot / freeze; includes the `/event/nav/mission` doc-bug note) | When you need "how to measure, where to store, how to freeze" |
| `baseline-evidence/` (read-only evidence) | measured snapshot + raw jsonl + manifest + readiness | To check the final fact of capability pass/fail (`2026-06-04-hitl/` = the only currently trusted one; `2026-06-03-first-trusted-face/` has been superseded and is historical) |
| [2026-06-03-first-trusted-baseline-evidence.md](2026-06-03-first-trusted-baseline-evidence.md) | 🕰️ historical milestone (the first trusted measurement on 6/3, face=fail) | To reference the 6/3 milestone (**must not be treated as the current face status**) |

---

## Firefighting file index

| File | Scenario | When to open |
|------|------|---------|
| [jetson.md](jetson.md) | Jetson Orin Nano 8GB environment | ROS2 / CUDA / environment variable / package path issues |
| [network.md](network.md) | Network troubleshooting | Connection issues between Go2 / Jetson / GPU server / dev machine |
| [gpu-server.md](gpu-server.md) | RTX 8000 GPU server connection | Cloud LLM / ASR unreachable, SSH tunnel issues |
| [go2-operation.md](go2-operation.md) | Go2 basic motion operations | Action ID quick reference, WebRTC command format, emergency stop |
| [demo_script.md](demo_script.md) · [demo-fallback-script.md](demo-fallback-script.md) · [demo-30-case-checklist.md](demo-30-case-checklist.md) | Demo presentation script / fallback / checklist | Presentation flow and backup plan on demo day |

---

## Demo startup scripts (not part of the runbook, listed here for convenience)

```bash
# 主流程
bash scripts/start_llm_e2e_tmux.sh             # 語音 + LLM 主線
bash scripts/start_nav_capability_demo_tmux.sh # nav_capability 平台層 demo
bash scripts/start_face_identity_tmux.sh       # 人臉辨識
bash scripts/start_full_demo_tmux.sh           # 四功能整合（demo 主線）

# 環境清理
bash scripts/clean_full_demo.sh                # 清 demo 全環境
bash scripts/clean_speech_env.sh               # 只清語音
bash scripts/clean_face_env.sh --all           # 人臉
```

See [`/CLAUDE.md`](../../CLAUDE.md) §"Build and Run" for details.
