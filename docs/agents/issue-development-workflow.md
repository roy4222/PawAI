# Issue Development Workflow

> **Scope**：把 GitHub issue 轉成 `/goal` 固定執行規格（7 段）+ scope guard + PR template 對應。
> **Status**：active / agent-config（開發流程護欄）。
> **Owner lane**：agents。
> **Related**：issue 操作見 [`issue-tracker.md`](issue-tracker.md)；triage label 見 [`triage-labels.md`](triage-labels.md)；HITL 取證見 [`hitl-verification-protocol.md`](hitl-verification-protocol.md)；evidence 背書原則見 north-star [`../mission/2026-06-18-demo-north-star.md`](../mission/2026-06-18-demo-north-star.md) §9。
> **What this file is NOT**：不是能力真相、不是 CI 自動 reject 規則。

每個 `/goal` 開工前，先把 GitHub issue 轉成固定執行規格，清楚說明本次只做什麼、不准碰什麼、需要哪些驗證與產物。搭配 `.github/pull_request_template.md`，讓多張 issue 的 agent 開發品質一致、evidence 可稽核（North Star §9：每個判斷都要 evidence 背書）。

## `/goal` spec template

每個 `/goal` 開工時必含這 7 段：

```md
Branch: codex/issue-X-short-name
Scope: 只做 #X，不碰 #Y/#Z
Hardware: none / Jetson / Go2 motion
Required tests:
Required artifact:
Required evidence:
Out of scope:
```

## 各段說明

- **Branch**：`codex/issue-X-short-name`，`X` 是 issue number，short name 用精簡英文描述。
- **Scope**：明確寫「只做 #X，不碰 #Y/#Z」。有相鄰 issue 時逐一列出，避免把未排進本 issue 的工作一起做掉。
- **Hardware**：三選一 `none` / `Jetson` / `Go2 motion`。需要真機或 HITL 驗證時要寫清楚（對應 PR template 的 **Hardware needed** 欄）。
- **Required tests**：列出必跑指令與預期輸出。純文件可寫 `N/A 純文件`。
- **Required artifact**：完成後必須產出的檔案、文件、截圖或報告。
- **Required evidence**：PR 內要附的證據（screenshot / log / snapshot / `pawai readiness` 輸出連結）。
- **Out of scope**：**直接吃 issue 的 Out-of-scope 欄**，作為本次 `/goal` 的「不准改」清單。

## Scope guard（怎麼把 Out-of-scope 帶進每個 PR）

1. 開工時把 issue 的 Out-of-scope 原樣抄進 `/goal` 規格。
2. 實作時把 Out-of-scope 當禁止清單；若非碰不可，**停下**拆成另一個 issue 或回報 scope 衝突，不要順手做。
3. 開 PR 時把同一份 Out-of-scope 填進 `.github/pull_request_template.md` 的 **Out of scope** 欄。

## 與 PR template 的對應

`.github/pull_request_template.md` 五欄（Linked issue / Test command + output / Hardware needed / Evidence / Out of scope）逐一對回本文件的 issue scope、required tests、hardware、required evidence 與 scope guard——reviewer 看一份 PR 即可稽核完整。

> Out of scope（本流程文件本身）：不做 CI 自動 reject 空欄（屬 #78 的 Fast Gate gate enhancement）；不改既有 `.github/ISSUE_TEMPLATE/`。
