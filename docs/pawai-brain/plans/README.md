# PawAI Brain Plans Index

> **Scope**：Brain / Studio / 感知主線的「實作計畫」層 — TDD 步驟、workorder、roadmap、checklist。
> **Status**：active index ｜ **Owner lane**：pawai-brain ｜ **Created**：2026-06-05
> **Source-of-truth priority**：plan 是「怎麼做」，**不是**能力 grade 真相。能力是否 pass / 可否進 Brain 主線 → [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/)。能不能講 / 屬哪分級 → [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md)（canonical，**勿在本層重複整份散文**）。
> **Maintained child files**：見下表。**Archived-legacy / historical boundary**：標 `historical` 者為 5 月 sprint 期計畫，已被 6/18 scoreboard-first 路線取代，**保留作歷史、不再執行**（檔頂有 blockquote banner）。
> **What this index is NOT**：不是 spec（設計在 [`../specs/README.md`](../specs/README.md)）、不是 research（[`../research/README.md`](../research/README.md)）、不是 contract（[`../../contracts/interaction_contract.md`](../../contracts/interaction_contract.md)）。

---

## current（6/18 scoreboard-first 主線）

| 檔案 | 角色 |
|---|---|
| [`2026-05-31-capability-baseline-scoreboard-plan.md`](2026-05-31-capability-baseline-scoreboard-plan.md) | Capability Baseline & Scoreboard 實作計畫（v0.2.3）|
| [`2026-06-01-scoreboard-implementation-plan.md`](2026-06-01-scoreboard-implementation-plan.md) | Scoreboard TDD 實作計畫（核心 deliverable 已 merged，HITL baseline run 待跑）|
| [`2026-06-04-codex-workorders.md`](2026-06-04-codex-workorders.md) | 6/04 route-paving workorder（source-verified 行號）|
| [`2026-06-04-system-improvement-roadmap.md`](2026-06-04-system-improvement-roadmap.md) | 系統改善 roadmap（26 blocker，4 個 6/18 blocker：cli .env CRLF / gesture backend default / nav observer / nav F7）|
| [`2026-06-02-baseline-issues-draft.md`](2026-06-02-baseline-issues-draft.md) | baseline GitHub issues 草稿（draft-only，已轉 issue 後保留參考）|
| [`2026-04-28-pawclaw-master-integration.md`](2026-04-28-pawclaw-master-integration.md) | Master Integration Plan（檔內自述 single source of integration truth）|

## historical（5 月 sprint 期，已被 6/18 路線取代，不再執行）

| 檔案 | 角色 | 為何 historical |
|---|---|---|
| [`2026-04-27-pawai-brain-skill-first.md`](2026-04-27-pawai-brain-skill-first.md) | Brain Skill-First MVS 實作計畫 | 4 月 sprint 實作計畫，主線已演進 |
| [`2026-05-06-conversation-engine-phase-0-5.md`](2026-05-06-conversation-engine-phase-0-5.md) | Conversation Engine Phase 0.5 | 5 月 sprint 期 |
| [`2026-05-07-capability-aware-self-demonstration.md`](2026-05-07-capability-aware-self-demonstration.md) | Capability-Aware 自我展示實作 | 5 月 sprint 期 |
| [`2026-05-07-pawai-demo-test-execution.md`](2026-05-07-pawai-demo-test-execution.md) | 5/7 night fail-map 執行計畫 | 一次性 sprint 執行 |
| [`2026-05-09-master-execution-roadmap.md`](2026-05-09-master-execution-roadmap.md) | 5/9 互動品質 master roadmap | sprint 期 roadmap，已被 6/18 取代 |
| [`2026-05-09-wave0-p11-observability-foundation.md`](2026-05-09-wave0-p11-observability-foundation.md) | Wave 0 + P1-1 觀測底座 | sprint 期 |
| [`2026-05-10-brain-minimum-checklist.md`](2026-05-10-brain-minimum-checklist.md) | 5/12 freeze Brain minimum checklist | 對應 5/12 demo |
| [`2026-05-10-demo-readiness-master-plan.md`](2026-05-10-demo-readiness-master-plan.md) | 5/11→5/18 demo readiness master plan | 對應 5 月 demo 視窗 |
| [`2026-05-10-spec1-llm-naturalness-plan.md`](2026-05-10-spec1-llm-naturalness-plan.md) | LLM 自然度 plan | 檔內已自述 SUPERSEDED |
| [`2026-05-10-spec2-gesture-static-plan.md`](2026-05-10-spec2-gesture-static-plan.md) | 靜態手勢 plan | sprint 期；gesture claim 以 claim matrix 為準 |
| [`2026-05-10-spec5-nav-fieldtest-checklist.md`](2026-05-10-spec5-nav-fieldtest-checklist.md) | 5/13–16 nav 場測 checklist | nav 已降級純 Studio 顯示零實機自走（見 claim matrix / north-star §7）|
| [`2026-05-10-spec6-scroll-verification-checklist.md`](2026-05-10-spec6-scroll-verification-checklist.md) | Studio scroll 驗證 checklist | 檔內已自述 COMPLETED |
| [`2026-05-11-asr-tw-and-context-reset.md`](2026-05-11-asr-tw-and-context-reset.md) | ASR 繁中 + context reset skeleton | sprint 期 branch 計畫 |
| [`2026-05-11-elevenlabs-spike-and-dual-route.md`](2026-05-11-elevenlabs-spike-and-dual-route.md) | ElevenLabs spike + dual route skeleton | ElevenLabs 已淘汰（3/26 確認）|
| [`2026-05-11-nav-root-cause-burndown.md`](2026-05-11-nav-root-cause-burndown.md) | Nav root-cause burndown（5/11–12 排除法）| 5 月 nav burndown；nav 能力 claim 以 baseline-evidence insufficient_data 為準 |
| [`2026-05-11-persona-openclaw-lite.md`](2026-05-11-persona-openclaw-lite.md) | Persona OpenClaw-lite 實作 | sprint 期 branch |
| [`2026-05-12-attention-policy.md`](2026-05-12-attention-policy.md) | Attention policy skeleton | sprint 期 branch |
| [`2026-05-12-free-conversation-audio-readiness.md`](2026-05-12-free-conversation-audio-readiness.md) | 自由對話音訊 readiness | 5/12 移交前 |
| [`2026-05-12-mac-school-network-readiness.md`](2026-05-12-mac-school-network-readiness.md) | Mac × 學校網路 readiness | 5/12 移交前 |
| [`2026-05-12-runtime-fallback-readiness.md`](2026-05-12-runtime-fallback-readiness.md) | Runtime fallback readiness | 5/12 移交前 |
| [`2026-05-14-spec-a-demo-mainline-stop-bleed.md`](2026-05-14-spec-a-demo-mainline-stop-bleed.md) | Demo 主線止血實作計畫 | 5/14 sprint 止血 |

> historical 區的能力 claim（gesture/pose/object/nav/voice）一律以 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md) 與 baseline-evidence 為準，不得用這些 sprint plan 措辭當 6/18 主張。
