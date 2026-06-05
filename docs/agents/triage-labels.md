# Triage Labels

> **Scope**：Matt Pocock triage skills 講的 5 個 canonical 角色，對應到 `roy4222/PawAI` 實際 GitHub label 字串。
> **Status**：active / agent-config（流程設定）。**Verified 2026-06-05** against `gh label list`。
> **Owner lane**：agents。
> **What this file is NOT**：不是能力真相、不是 ADR。能力是否 pass 回 [`../mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md)。

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker (`roy4222/PawAI`).

> ⚠️ **Reality check（2026-06-05）**：`roy4222/PawAI` **只實作了 3 個** Matt Pocock 角色 label（`ready-for-agent` / `ready-for-human` / `wontfix`）。`needs-triage` 與 `needs-info` **目前不存在於 tracker**——之前此表把它們列成「已存在、同名」是 stale。下表「Label in our tracker」欄如實標示哪些已建、哪些未建。

| Label in mattpocock/skills | Label in our tracker          | Status         | Meaning                                  |
| -------------------------- | ----------------------------- | -------------- | ---------------------------------------- |
| `needs-triage`             | （未建 — 預設無 label = 待 triage）| ⚠️ not created | Maintainer needs to evaluate this issue  |
| `needs-info`               | （未建）                        | ⚠️ not created | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`             | ✅ exists       | 可由 agent 獨立執行（AFK-ready）            |
| `ready-for-human`          | `ready-for-human`             | ✅ exists       | 需人在 Jetson/Go2 上機操作 (HITL)          |
| `wontfix`                  | `wontfix`                     | ✅ exists       | This will not be worked on               |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from the **Status: exists** rows. For `needs-triage` / `needs-info`：要嘛先 `gh label create` 建好，要嘛在 issue body 用純文字標註狀態——**不要假設 label 已存在**。

## PawAI 專案附加 label（非 Matt Pocock 角色）

這些是 PawAI 自有的分類 / 範圍 label，與 triage 角色正交（可同時掛）：

| Label                | Meaning                                  |
| -------------------- | ---------------------------------------- |
| `capability-baseline`| 6/18 capability baseline & scoreboard    |
| `dev-workflow`       | 開發流程護欄 (CI / template / HITL)        |
| `nav_capability`     | nav stack / 移動能力範圍                    |
| `P0`                 | 6/18 必留底線優先級（範圍優先，非 runtime 攔截）|
| `code-review` / `code-quality` / `security` | 程式碼審查 / 品質 / 安全範圍 |

> 維護：label set 變動時，跑 `gh label list --json name,description` 對照本表更新；不要讓本表再次漂移成「宣稱存在但實際沒建」。
