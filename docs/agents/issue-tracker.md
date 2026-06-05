# Issue tracker: GitHub

> **Scope**：本檔定義 issue / PRD 在何處、用什麼工具操作。
> **Status**：active / agent-config（流程設定）。**Verified 2026-06-05** — repo = `roy4222/PawAI`，`gh` CLI 可用。
> **Owner lane**：agents。
> **Related**：triage 角色 → label 對照見 [`triage-labels.md`](triage-labels.md)；`/goal` → issue 開工規格見 [`issue-development-workflow.md`](issue-development-workflow.md)。
> **What this file is NOT**：不是能力真相、不是 triage label 清單。

Issues and PRDs for this repo live as GitHub issues (`github.com/roy4222/PawAI`). Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` — `gh` does this automatically when run inside a clone.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
