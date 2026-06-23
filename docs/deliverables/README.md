# Deliverables — Semester Submission Materials

**English** | [中文](./README.zh.md)

> Distinct from `archive/`: the content here consists of finished works **actively delivered to teachers / the school**, not internal history.

> **Documentation governance (governance header)**
> - **Scope**: External deliverables (thesis / reports / system-limitation and feasibility analysis, `.md` + `.docx` + `.pdf`).
> - **Status**: active / thesis delivery layer. The content is a **narrative deliverable aimed at teachers**, not the capability source-of-truth layer.
> - **Source-of-truth priority**: Any capability claim (face / object / voice / gesture / pose / nav / Brain) is governed by the EVIDENCE_AUTHORITY in [`../README.md` §Conflict Arbitration](../README.md#衝突仲裁誰是真相來源) — measured [`../runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/) ＞ 6/05 convergence audit ＞ capability-baseline-spec ＞ north-star. Delivered documents must not over-claim (face only recognizes acquaintances; object only cup at close range; voice.stop / gesture.wave currently fail; pose is Studio-only; nav is insufficient_data, not dynamic obstacle avoidance / autonomous navigation; Brain only claims deterministic safety/allowlist).
> - **Routing**: In the [`docs/README.md`](../README.md) main line, this folder is listed as "Deliverables (semester submission materials)". The guide for external-facing **writing / reporting mindset / forbidden-claims list** is in [`../pawai-demo/`](../pawai-demo/); the authority for the 6/18 strategic boundary and forbidden-claims list is in [`../mission/2026-06-18-demo-north-star.md`](../mission/2026-06-18-demo-north-star.md).
> - **What this is NOT**: Not the internal design source-of-truth (see `pawai-brain/` / `navigation/`), not the capability scoreboard. docx/pdf are rendered artifacts; `.md` is the source file.

---

## Contents

| Path | Content |
|------|------|
| [thesis/](thesis/) | Thesis / report / system-limitation and feasibility analysis (`.md` + `.docx` + `.pdf`) |

---

## Key Dates (Hard Deadlines)

- **2026/4/13**: Document submission (initial version on Sunday, submit on Monday) — passed
- **2026/5/12**: School demo
- **End of May 2026**: Demonstration / acceptance

---

## Document Rules

- `.md` is the source file; `.docx` / `.pdf` are the formats the teacher receives
- Large files (> 5 MB) are currently still in git; git-lfs is not yet enabled (to be evaluated after 5/14)
- `__pycache__/` has been added to `.gitignore` and should no longer enter git
