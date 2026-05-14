---
name: update-docs
description: 每日開發後同步文件。當使用者說「更新文件」、「同步文件」、「整理今天進度到文件」、「根據今天開發更新 docs」、「幫我把今天改動寫進文件」時觸發。這個 skill 會檢查當天 git 變更，判斷哪些文件需要同步，按治理規則更新對應的真相來源文件。只要使用者提到更新文件、同步 docs、或把開發進度寫進文件，就應該使用這個 skill。
---

# 更新文件

每日開發完成後，根據程式碼變更同步對應的文件。

**核心原則**：不是「全部更新一輪」，而是「只更新真正被今天開發影響的真相來源」。

---

## 流程

### Step 1：檢查今天改了什麼

執行以下命令掌握變更範圍：

```bash
# 今天的 commit
git log --since="00:00" --oneline

# 如果沒有今天的 commit，看 staged + unstaged 變更
git diff --name-only
git diff --name-only --cached

# 完整差異（理解改動內容）
git diff
git diff --cached
```

如果使用者指定了時間範圍（例如「更新這週的」），用 `--since` 調整。

### Step 2：判斷影響層級

把變更分成 4 個層級，從窄到寬：

**模組層**（最常見）
- 改了某個 ROS2 package 的程式碼
- 對應更新該模組的 README

**契約層**
- 改了 topic 名稱、message schema、參數、QoS
- 對應更新 `docs/contracts/interaction_contract.md`
- 必要時更新 `docs/archive/2026-05-docs-reorg/architecture-misc/data_flow.md`

**Studio 層**
- 改了 Gateway、event schema、brain adapter、面板行為
- 對應更新 `docs/pawai-brain/studio/` 下的相關文件

**Sprint 層**（Sprint 期間每日必做）
- 今天的開發對應 sprint-b-prime.md 的哪個 Day
- 把完成的 checklist item 打勾（`- [ ]` → `- [x]`）
- 補上實測數據或驗收結果
- 同步更新 `references/project-status.md` 的模組狀態表和當日進度段落

**專案層**（最少動）
- P0/P1/P2 調整、分工變更、demo 策略變更
- 才更新 `docs/mission/README.md` 或 `docs/mission/handoff_316.md`

### Step 3：產生更新提案

列出建議同步的文件清單，格式如下：

```
今天建議同步 N 份文件：

1. `docs/pawai-brain/speech/README.md`
   - 補充新的啟動腳本
   - 更新 fallback 行為

2. `docs/contracts/interaction_contract.md`
   - 更新 /event/... schema 欄位
```

### Step 4：決定自動 or 提案模式

**直接更新**（小改模式）：
- 只影響 1-3 份文件
- 不碰 `mission/README.md`
- 不碰 `interaction_contract.md`（凍結中）
- 不碰 docs 結構與治理規則

**先提案再改**（大改模式）：
- 會改 `mission/README.md`
- 會改 `interaction_contract.md`
- 會改 `pawai-brain/studio/specs/event-schema.md`
- 會改 docs 結構、導航、archive
- 會跨 3 份以上主幹文件

大改模式時，先輸出提案等使用者確認，確認後才動手。

### Step 5：執行更新

更新時遵守以下規則：
- **不要重寫整份文件** — 只改受影響的段落
- 保留既有真相來源的責任邊界
- 用 Edit 工具做精準替換，不用 Write 整份覆蓋

### Step 6：輸出結果摘要

固定格式回報：

```
已更新：
- docs/pawai-brain/speech/README.md — 補充 energy VAD 參數說明
- docs/archive/2026-05-docs-reorg/architecture-misc/data_flow.md — 更新 banner 偏差描述

未更新：
- docs/mission/README.md（本次變更不影響專案方向）

需要你確認：
- interaction_contract.md 的 /state/interaction/speech schema 是否要加 vad_state 欄位

已 commit：<hash> <subject>
```

如果是 opt-out 情況，把最後一行換成 `未 commit（原因：...）`。

### Commit 規則

**預設：自動 commit**

執行完 Step 5 的文件編輯後，如果有任何變更（`git status` 非空），**自動**執行 commit：

1. `git add` 只加入本次實際修改/新增的文件（包含 docs 相關目錄、對應的 README、新加入版控的 script/config）
   - **不要**用 `git add -A` 或 `git add .`，避免誤入敏感檔案
   - 如果這次順手新增了 `.gitignore`、`scripts/README.md` 這類相關支援檔，也一併加入（它們是 docs 更新的一部分）
2. 寫 commit message，格式：
   ```
   docs: [一句話摘要本次同步的主題]

   - 檔案 1：改了什麼
   - 檔案 2：改了什麼
   ...

   Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
   ```
3. 用 HEREDOC 方式執行 `git commit -m`（避免引號/換行問題）
4. commit 完執行 `git status` + `git log --oneline -3` 驗證
5. **不要自動 push**，只 commit

**Opt-out 條件**（遇到以下情況**不要** commit，只改檔）：
- 使用者明確說「不要 commit」「先別 commit」「只改檔」「no commit」「--no-commit」
- 變更中包含**任何** `mission/` 或 `interaction_contract.md` 的修改（大改模式下使用者必須先審過再 commit）
- `git status` 顯示的變更檔案中有 `.env`、`credentials*`、`*.key`、`*.pem` 等疑似機密檔（這時候要警告使用者、不 commit）
- `pre-commit` hook 安裝時失敗 → 報告錯誤，不要用 `--no-verify`

**輸出格式**：commit 完成後，在 Step 6 的輸出摘要最後加一段：
```
已 commit：<hash> <subject>
```

或（opt-out 時）：
```
未 commit（原因：...）
```

---

## 程式碼 → 文件對照表

這是預設的映射關係，skill 應據此判斷該更新哪些文件：

| 程式碼變更 | 對應文件 |
|-----------|---------|
| `speech_processor/`、語音相關腳本 | `docs/pawai-brain/speech/README.md` |
| `face_perception/`、`scripts/face_*` | `docs/pawai-brain/perception/face/README.md` |
| 手勢/姿勢相關程式、`gesture_*`、`pose_*`、DWPose、RTMPose | `docs/pawai-brain/perception/gesture/README.md`、`docs/pawai-brain/perception/pose/README.md` |
| `go2_robot_sdk/` | `docs/contracts/interaction_contract.md`（如涉及 topic/command） |
| `go2_interfaces/msg/`、`go2_interfaces/srv/` | `docs/contracts/interaction_contract.md` |
| `interaction_executive/` | `docs/contracts/interaction_contract.md`、`docs/pawai-brain/studio/specs/brain-adapter.md` |
| `face_dashboard_fastapi/`、`face_dashboard_nextjs/` | `docs/pawai-brain/studio/` 相關文件 |
| `scripts/start_*.sh` | 對應模組的 README + `CLAUDE.md` 常用指令區 |
| `go2_robot_sdk/config/` | `CLAUDE.md` 配置檔區塊 |
| `go2_robot_sdk/launch/` | `CLAUDE.md` 啟動指令區塊 |
| 專案級策略、分工、demo 變更 | `docs/mission/README.md`、`docs/mission/handoff_316.md` |
| 任何功能性程式碼變更 | `references/project-status.md`（模組狀態表 + 當日進度段落） |
| Sprint 期間的交付物完成 | `docs/mission/sprint-b-prime.md`（對應 Day 的 checklist 打勾 + 驗收結果） |

如果變更涉及新的 ROS2 node，除了模組 README，也要檢查 `CLAUDE.md` 的「常見開發情境 → 新增 ROS2 節點」是否需要更新範例。

---

## 文件治理規則（內建）

更新文件時必須遵守的責任邊界：

> `mission` 定方向，`contracts` 定 ROS2 介面契約，`pawai-brain` 定 Brain/感知/語音/Studio，`navigation` 定移動，`runbook` 定操作，程式碼庫定現況，`CLAUDE.md` 不定規格。

### 衝突仲裁

| 問題類型 | 以誰為準 |
|---------|---------|
| 專案方向、P0/P1/P2、分工、Demo | `mission/` |
| ROS2 介面、schema、QoS、跨模組契約 | `contracts/` |
| Studio / Gateway / Brain / Frontend | `pawai-brain/studio/`、`pawai-brain/` |
| 模組內部設計 | 各模組 README |
| 安裝、部署、操作步驟 | `runbook/` |
| `CLAUDE.md` vs `runbook/` 衝突 | 以 `runbook/` 為準 |
| `CLAUDE.md` vs `contracts/` 衝突 | 以 `contracts/` 為準 |

### CLAUDE.md 特殊規則

`CLAUDE.md` 是操作速查卡，不是規格文件：
- **可以放**：建構指令、除錯指令、已知陷阱摘要（附引用連結）、常見情境
- **不可以放**：完整 schema 表、完整節點清單、完整 api_id 表
- 新增內容時，摘要寫在 `CLAUDE.md`，完整規格寫在對應的主幹文件

---

## 永遠要做

- 先看 code 變更，再決定改哪份文件
- 優先維護真相來源（不是每份提到的文件都要改，而是改「定義那件事」的文件）
- 改完後給簡短摘要
- 發現主幹文件彼此矛盾時，主動指出

## 永遠不要做

- 不要為了「看起來完整」而補沒有根據的規格
- 不要每天都改 `mission/README.md`（除非專案方向真的變了）
- 不要每天都寫 `CHANGELOG.md`（只有結構級變更才記）
- 不要把 `archive/` 當現行依據
- 不要讓 `CLAUDE.md` 再長出完整規格表
- 不要把模組細節塞進 `mission/`
- 不要把跨模組契約塞進模組 README
