# PawAI Studio — Specs Index

> **Governance header**
> - **Scope**：PawAI Studio `specs/` 目錄索引 — 標明每份 spec 是 **current（仍是設計真相）/ legacy（部分 superseded）/ superseded（已被取代）**，避免讀者誤把舊架構當現況。
> - **Status**：active / index。
> - **Owner lane**：brain-studio-lane。
> - **Source-of-truth priority**：Studio 模組設計真相在各 spec；但**架構是否反映實作**以 [`../README.md`](../README.md)（current Studio 真相）+ gateway 程式碼（`pawai-studio/gateway/studio_gateway.py`）為準。**能力是否 pass** 一律回 [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/README.md) ＞ [`convergence audit`](../../research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md) ＞ [`capability-baseline-spec`](../../specs/2026-06-18-capability-baseline-spec.md)。能力 claim 邊界綁 [`capability-claim-matrix`](../../../mission/2026-06-18-capability-claim-matrix.md)。ROS2 schema 真相在 [`docs/contracts/interaction_contract.md`](../../../contracts/interaction_contract.md)。
> - **What this index is NOT**：不是能力 pass 證明、不是 ROS2 contract、不是實作計畫（plans 在 `../plans/`）。

## Specs 清單（current / legacy / superseded）

| spec | 主題 | 狀態 | 備註 |
|------|------|------|------|
| [`2026-05-04-studio-chat-first-redesign-design.md`](2026-05-04-studio-chat-first-redesign-design.md) | chat-first 主畫面重設計 v2.1 | **current（設計 of record）** | 5/4 已落地（見 README 狀態卡）；spec 內文標「awaiting approval」是撰寫當下狀態，實作已完成。 |
| [`2026-05-04-design-tokens.md`](2026-05-04-design-tokens.md) | chat-first design tokens（dark only） | **current** | 對應 `frontend/lib/design-tokens.ts` + `globals.css`。 |
| [`2026-05-04-studio-redesign-feedback.md`](2026-05-04-studio-redesign-feedback.md) | UI/UX review feedback（a11y / touch / animation） | **current（review 紀錄）** | Step 10 review output；follow-up 項見 README「下一步」phase C。 |
| [`ui-orchestration.md`](ui-orchestration.md) | UI orchestration 設計原則（ChatGPT↔Foxglove 雙模） | **current（原則層，v1.1）** | 概念仍成立；具體 panel 結構以 README chat-first 章節為準。 |
| [`event-schema.md`](event-schema.md) | Gateway ↔ Frontend JSON event / state / command schema（v1.0） | **legacy（部分對齊）** | 概念正確；但實際 WS event 欄位以 current gateway + [`interaction_contract.md`](../../../contracts/interaction_contract.md) v2.5 為準（含 conversation_trace / capability / tts source 等後加欄位）。 |
| [`brain-adapter.md`](brain-adapter.md) | LLM 統一介面（Brain Adapter，v1.0） | **legacy（部分 superseded）** | 「LLM 提建議 → Executive 決策 → Runtime 執行」原則仍成立；但實際 fallback chain 以 README「Chat 閉環」+ `llm_bridge_node._try_openrouter_chain` 五級 fallback 為準。 |
| [`system-architecture.md`](system-architecture.md) | 系統架構（快/慢雙系統 + Gateway 拓撲，v1.0） | **🔴 LEGACY / 部分 superseded** | **RTX 8000 + Redis Event Bus + ros2_bridge→Redis 拓撲未落地**。現行 Gateway 跑 **Jetson**（FastAPI+rclpy 直連，port **8080**），無 Redis。與 current gateway README 衝突，**一律以 [`../README.md`](../README.md) + gateway 程式碼為準**。檔頂已加 banner。 |

## current vs legacy 一句話判準

- **架構 / 部署 / port / 端點**：以 [`../README.md`](../README.md) + `pawai-studio/gateway/studio_gateway.py` 為準（current）。`system-architecture.md` 的 RTX8000/Redis 是早期提案，未落地。
- **JSON schema 欄位**：以 [`interaction_contract.md`](../../../contracts/interaction_contract.md) v2.5（ROS2 層）+ current gateway（WS 層）為準；`event-schema.md` 是 v1.0 概念草案。
- **能力是否 pass / chip 顏色**：以 [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/README.md) 為唯一 trusted 數據源，**Studio 顯示不等於能力 pass**（見 README「Studio claim 邊界」）。
