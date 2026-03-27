# project-onboard Skill 設計規格

**建立日期**：2026-03-15
**狀態**：Draft
**目標**：讓任何 AI 在新 session 中能快速上手 PawAI 專案

---

## 1. 問題與動機

每次開新 AI 對話（Claude Code、Gemini CLI、Codex、ChatGPT），AI 都缺乏專案上下文。目前 repo 中可能存在的平台入口檔（如 `CLAUDE.md`、`AGENTS.md`、`GEMINI.md`）提供了基礎慣例，但缺少：

- 功能模組分流導覽（不知道該先讀哪份文件）
- 當前進度快照（不知道專案做到哪了）
- 已知陷阱彙整（會重複踩坑）

結果是：每次新 session 都要花大量 token 讓 AI 重新探索，或人類手動交代背景。

## 2. 使用場景與優先序

優先序：A → C → B（依效益排列，非字母順序）

| 優先 | 場景 | 描述 |
|:----:|------|------|
| 1st | 新 AI session 上手 | 每次開新對話，AI 觸發 skill 後快速建立專案認知 |
| 2nd | 跨 AI 平台通用 | 非 Claude Code 的 AI 透過 `PROJECT_MAP.md` 依序閱讀 |
| 3rd | 新人類成員 onboarding | 新組員透過 AI 導覽理解專案（附帶收益） |

## 3. 設計決策

### 3.1 Router 而非 Dump

Skill 不把整個專案灌入 context，而是：
1. 先載入總覽（~100 行），建立架構認知
2. 根據任務路由到對應功能區塊
3. 功能區塊指向權威文件，不重寫權威文件

這樣 token 成本最低，且不會因為過多無關資訊鈍化 AI。

### 3.2 三層 Progressive Disclosure

| 層級 | 載入時機 | 內容 | 大小限制 |
|:----:|---------|------|---------|
| Layer 1 | 永遠在 context | name + description | ~100 words |
| Layer 2 | skill 觸發時 | SKILL.md body（總覽 + 路由） | < 500 行 |
| Layer 3 | 按需讀取 | references/*.md（功能區塊） | 不限 |

### 3.3 穩定 vs 易變內容分離

| 類別 | 檔案 | 更新頻率 |
|------|------|---------|
| 穩定骨架 | SKILL.md | 極少（架構變動才更新） |
| 穩定知識 | references/{speech,face,...}.md | 低（功能設計變動才更新） |
| 易變進度 | references/project-status.md | 高（每次開發後可更新） |

### 3.4 Reference = 導覽，不是第二份真相

`references/*.md` 的角色是：
- 告訴 AI 這個模組是什麼、核心檔案在哪、已知陷阱有哪些
- **指向**權威文件（`docs/語音功能/README.md` 等），不複製其內容
- 如果 reference 和權威文件衝突，以權威文件為準

### 3.5 與 CLAUDE.md / AGENTS.md 的分工

| 檔案 | 職責 | 不做的事 |
|------|------|---------|
| CLAUDE.md / AGENTS.md | 開發慣例、build 指令、coding conventions | 不做功能分流、不追蹤進度 |
| SKILL.md | 專案全貌、功能路由、架構骨架 | 不重複 build 指令、不放易變進度 |
| references/*.md | 功能區塊導覽、已知陷阱 | 不重寫權威文件內容 |
| project-status.md | 當前進度、下一步 | 不放穩定知識 |

如果兩者有重疊（如「已知陷阱」），CLAUDE.md 放跨模組通用的，references 放模組特定的。衝突時以 CLAUDE.md 為準。

### 3.6 觸發控制

觸發條件：
- 使用者明確說 "onboard"、"上手"、"了解專案" 等
- 任務涉及兩個以上模組的交互
- AI 從 CLAUDE.md / AGENTS.md 找不到相關模組資訊

不觸發條件：
- 任務已明確限定在單一檔案且不需要專案上下文
- 純 build / lint / format 等工具類操作（CLAUDE.md 已覆蓋）

## 4. 檔案結構

```
.claude/skills/project-onboard/
├── SKILL.md                         ← Layer 2: 總覽 + 路由
├── references/
│   ├── project-status.md            ← 易變：當前進度快照
│   ├── speech.md                    ← 語音模組導覽
│   ├── face.md                      ← 人臉辨識導覽
│   ├── llm-brain.md                 ← AI 大腦 + Gateway 導覽
│   ├── studio.md                    ← PawAI Studio 前端導覽
│   ├── validation.md                ← 測試 / 驗收工具導覽
│   └── environment.md               ← Jetson / 部署 / 環境導覽

PROJECT_MAP.md                       ← repo 根目錄，跨平台入口
```

## 5. SKILL.md 規格

### 5.1 Frontmatter

```yaml
name: project-onboard
description: >
  PawAI 專案快速上手 — 讓任何 AI 在新 session 中立即理解專案全貌、
  當前進度、功能架構與開發慣例。每次開新對話、接手不熟悉的模組、
  或需要理解專案上下文時都應觸發。觸發詞包括但不限於：
  "onboard"、"上手"、"了解專案"、"project context"、"/onboard"、
  "這個專案是做什麼的"、"幫我看一下專案"、"我是新來的"、
  "給我專案背景"。即使使用者只是問了一個看起來簡單的功能問題，
  如果你對專案缺乏上下文，也應該先觸發這個 skill 建立基礎認知。
```

### 5.2 Body 內容區塊

1. **專案定位**（~5 行）：一句話定位 + 硬底線
2. **三層架構速記**（~10 行）：Layer 1/2/3 角色
3. **硬體拓撲**（~8 行）：Jetson / Go2 / RTX 8000 / D435 / 麥克風
4. **當前進度指標**：指向 `references/project-status.md`
5. **功能路由表**（~15 行）：關鍵字 → reference 檔案的對應表
6. **權威文件索引**（~10 行）：各領域 single source of truth
7. **開發慣例速記**（~15 行）：跨模組通用的踩坑規則
8. **非 Claude Code 指引**（~5 行）：指向 `PROJECT_MAP.md`
9. **觸發邊界**（~3 行）：什麼時候不需要觸發

預估總長：~80-100 行，遠低於 500 行上限。

## 6. Reference 檔案模板

每個 `references/*.md` 統一使用以下結構。注意：reference 的角色是**導覽與摘要**，
詳細內容應指向權威文件，不要在這裡重寫。

```markdown
# [模組名稱]

> 最後更新：YYYY-MM-DD

## 這個模組是什麼
一段話描述模組在系統中的角色和定位。

## 權威文件
指向 docs/ 下的真相來源，不重寫其內容。
- docs/XXX/README.md — 說明
- docs/architecture/contracts/interaction_contract.md §X — 相關介面

## 核心程式檔案
| 檔案 | 用途 |
|------|------|
| path/to/file.py | 一句話說明 |

## 目前狀態
[DONE] / [WIP] / [PAUSED] — 一句話說明

## 已知陷阱
- 陷阱描述 + 為什麼會踩到 + 怎麼避

## 開發入口
你最可能需要做的事，以及從哪個檔案開始。

## 驗收方式
怎麼確認這個模組正常運作。
```

## 7. PROJECT_MAP.md 規格

放在 repo 根目錄，內容極簡，跨平台通用：

```markdown
# PawAI Project Map

給任何 AI 的快速入口。依序閱讀：

1. 本檔案（你正在讀）
2. 平台入口檔（如果存在，擇一讀取）：
   - Claude Code → CLAUDE.md
   - Codex / OpenCode → AGENTS.md
   - Gemini CLI → GEMINI.md
   - 如果以上都不存在，跳過此步，直接往下
3. .claude/skills/project-onboard/SKILL.md — 專案總覽與功能路由
   （如果 .claude/ 目錄不存在，改讀 docs/mission/README.md 作為總覽）
4. .claude/skills/project-onboard/references/project-status.md — 當前進度
5. 根據你的任務，讀對應的 references/*.md（見 SKILL.md 路由表）

如果你只有 5 分鐘，至少讀完 1-4。
```

## 8. 最小可行版本（MVP）

先落這 5 個檔案：

| 檔案 | 理由 |
|------|------|
| SKILL.md | 核心，沒它 skill 不存在 |
| references/project-status.md | 易變進度，每個 session 都要讀 |
| references/speech.md | 目前最活躍的開發模組 |
| references/environment.md | 環境問題是最常見的阻礙 |
| PROJECT_MAP.md | 跨平台入口 |

其餘 references（face、llm-brain、studio、validation）後續補齊。

## 9. 維護規則

- `project-status.md`：每次重大開發進展後更新
- `references/*.md`：對應模組設計變動時更新，每個檔案頂部有「最後更新」日期
- `SKILL.md`：僅在架構層級變動時更新
- 如果 reference 內容和權威文件（docs/）衝突，以權威文件為準並修正 reference

## 10. Git 追蹤與跨平台可發現性

`.claude/skills/project-onboard/` 必須 commit 進 repo，這樣任何平台的 AI 都能**讀取**這些檔案。

但 commit 進 repo 不等於其他平台會自動發現或觸發這個 skill。
`.claude/skills/` 是 Claude Code 的 runtime 註冊點，其他平台（Codex、Gemini CLI）
需要透過 `PROJECT_MAP.md` 的指引手動導向這些檔案，或依各平台機制做額外設定
（如 symlink、平台專屬 config 等）。

確認事項：
- `.gitignore` 沒有排除 `.claude/skills/`
- `PROJECT_MAP.md` 也必須 commit
- `PROJECT_MAP.md` 是非 Claude 平台的唯一入口，必須自足（不假設 skill 機制存在）

## 11. 降級策略

| 狀況 | 處理方式 |
|------|---------|
| AI 路由到錯誤 reference | reference 開頭有模組定位描述，AI 讀到後應能自行修正 |
| 權威文件已移動/刪除 | AI 用 Glob 搜尋相近檔名，並在 reference 中標記需更新 |
| project-status.md 過期（>2 週未更新） | AI 應改用 `git log --oneline -20` + `git status --short` 判斷近期活動與未提交進度 |
| .claude/ 目錄不存在（非 Claude 平台） | AI 依 PROJECT_MAP.md 指引，直接讀 docs/ 下的權威文件 |
