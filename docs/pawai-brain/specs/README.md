# PawAI Brain Specs Index

> **Scope**：Brain / Studio / 互動主線的「設計規格」層（怎麼設計、怎麼量）。本資料夾不是能力 grade 的真相源。
> **Status**：active index ｜ **Owner lane**：pawai-brain ｜ **Created**：2026-06-05
> **Source-of-truth priority（本層在全 repo 階層中的位置）**：
> - 能力「是否 pass / 可否進 Brain 主線」的最終事實 → [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/)（trusted snapshot `78fbf36`, readiness=`not_ready`）。
> - 「能不能講、屬哪個分級」的對照表 → [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md)（canonical claim matrix，**勿在本層重複整份散文，一律連結**）。
> - 本資料夾管的是「**怎麼量、怎麼設計**」（measurement / design truth），grade 結果不在這裡定。
> **Maintained child files**：見下表。**Archived-legacy boundary**：標 `legacy` 者為 5 月 sprint 期設計，保留作歷史，**不再更新、不得當 6/18 真相**；要查 6/18 怎麼量請看 current 那一份。
> **What this index is NOT**：不是 plan（實作步驟在 [`../plans/README.md`](../plans/README.md)）、不是 research（模型候選/調查在 [`../research/README.md`](../research/README.md)）、不是 contract（ROS2 schema 在 [`../../contracts/interaction_contract.md`](../../contracts/interaction_contract.md)）。

---

## current（6/18 量測真相）

| 檔案 | 角色 | 狀態 |
|---|---|---|
| [`2026-06-18-capability-baseline-spec.md`](2026-06-18-capability-baseline-spec.md) | **15 capability「怎麼量、怎樣算 pass」的唯一真相源（measurement truth）** | current（門檻 provisional until baseline）|

> 注意：baseline-spec 定義量測協定，但**能力 grade 結果以 baseline-evidence snapshot 為準**（見上方權威鏈）。spec 內的門檻在跑完 baseline 前都是 provisional。

## current（設計規格，仍引用中）

| 檔案 | 角色 |
|---|---|
| [`2026-04-27-pawai-brain-skill-first-design.md`](2026-04-27-pawai-brain-skill-first-design.md) | Brain Skill-First MVS 系統設計（current）|
| [`2026-04-27-pawclaw-embodied-brain-evolution.md`](2026-04-27-pawclaw-embodied-brain-evolution.md) | Embodied Brain 演進設計 Phase A→B（與 MVS 並存）|
| [`2026-05-06-conversation-engine-langgraph-design.md`](2026-05-06-conversation-engine-langgraph-design.md) | Conversation Engine × LangGraph shadow 設計 |
| [`2026-05-07-capability-aware-self-demonstration-design.md`](2026-05-07-capability-aware-self-demonstration-design.md) | Capability-Aware 自我展示設計 |
| [`2026-05-14-spec-a-demo-mainline-stop-bleed.md`](2026-05-14-spec-a-demo-mainline-stop-bleed.md) | Demo 主線止血設計 freeze |

## legacy（5 月 sprint 期，歷史，不當 6/18 真相）

| 檔案 | 角色 | 為何 legacy |
|---|---|---|
| [`2026-05-01-pawai-11day-sprint-design.md`](2026-05-01-pawai-11day-sprint-design.md) | 5/12 學校 demo 11 天作戰地圖 | sprint 已過，定位已被 6/18 north-star 取代 |
| [`2026-05-04-llm-eval-result.md`](2026-05-04-llm-eval-result.md) | 5/4 LLM eval 結果 | 結果快照，模型主線已多次更新 |
| [`2026-05-04-phase-b-implementation-notes.md`](2026-05-04-phase-b-implementation-notes.md) | Phase B working notes | 配套 5/01 sprint，已過 |
| [`2026-05-05-jetson-smoke-result.md`](2026-05-05-jetson-smoke-result.md) | 5/4 Jetson smoke 結果 | 一次性結果快照 |
| [`2026-05-05-tts-rewrite-result.md`](2026-05-05-tts-rewrite-result.md) | TTS provider 換血結果 | 一次性結果快照 |
| [`2026-05-09-interaction-quality-improvements-design.md`](2026-05-09-interaction-quality-improvements-design.md) | 互動品質改善設計 | 5/9 sprint 期 |
| [`2026-05-10-demo-quality-roadmap-index.md`](2026-05-10-demo-quality-roadmap-index.md) | 6-spec roadmap index | 檔內自述 superseded by Demo Readiness Master Plan |
| [`2026-05-10-llm-naturalness-a-plus-design.md`](2026-05-10-llm-naturalness-a-plus-design.md) | LLM 自然度 A+ 設計（draft）| sprint 期 draft |
| [`2026-05-10-spec2-gesture-interaction-design.md`](2026-05-10-spec2-gesture-interaction-design.md) | 手勢互動設計（draft）| sprint 期；gesture claim 以 claim matrix 為準（`gesture.wave` 現 fail）|
| [`2026-05-10-spec3-pose-interaction-design.md`](2026-05-10-spec3-pose-interaction-design.md) | 姿勢互動設計（draft）| sprint 期；pose 為 Studio-only/insufficient（見 claim matrix）|
| [`2026-05-10-spec4-object-perception-design.md`](2026-05-10-spec4-object-perception-design.md) | 物體感知升級設計（draft）| sprint 期；object 僅 `object.cup` 窄版（見 claim matrix）|
| [`2026-05-10-spec5-navigation-roadmap.md`](2026-05-10-spec5-navigation-roadmap.md) | 導航 roadmap（draft）| sprint 期；nav 為 insufficient_data，不主張動態避障/自走 |
| [`2026-05-10-spec6-studio-ux-polish.md`](2026-05-10-spec6-studio-ux-polish.md) | Studio UX polish（draft）| sprint 期 |
| [`2026-05-07-pawai-demo-test-checklist-v2.md`](2026-05-07-pawai-demo-test-checklist-v2.md) | 5/13–18 demo 測試 checklist | sprint 期測試清單 |
| [`2026-05-07-pawai-demo-test-fail-map.md`](2026-05-07-pawai-demo-test-fail-map.md) | 5/7 night fail-map | sprint 期快照 |
| [`2026-05-07-pawai-demo-test-plan.md`](2026-05-07-pawai-demo-test-plan.md) | demo 驗收測試計畫 v1 | sprint 期 |

> legacy 區的能力 claim（gesture/pose/object/nav）一律以 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md) 與 baseline-evidence 為準，不得用這些 5 月 draft 的措辭當 6/18 主張。
