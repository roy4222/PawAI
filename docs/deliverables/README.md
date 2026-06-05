# Deliverables — 學期繳交素材

> 區別於 `archive/`：這裡的內容是**主動交付給老師 / 學校**的成品，不是內部歷史。

> **文件治理（governance header）**
> - **Scope**：對外交付成品（thesis / 報告 / 系統限制與可行性分析，`.md` + `.docx` + `.pdf`）。
> - **Status**：active / thesis 交付層。內容是**面向老師的敘事成品**，不是能力真相層。
> - **Source-of-truth priority**：任何能力宣稱（face / object / voice / gesture / pose / nav / Brain）以 [`../README.md` §衝突仲裁](../README.md#衝突仲裁誰是真相來源) 的 EVIDENCE_AUTHORITY 為準 — 實測 [`../runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/) ＞ 6/05 convergence audit ＞ capability-baseline-spec ＞ north-star。交付文稿不得 over-claim（face 只認熟人、object 只 cup 近距、voice.stop / gesture.wave 現為 fail、pose 是 Studio-only、nav 為 insufficient_data 非動態避障/自走、Brain 只宣稱 deterministic safety/allowlist）。
> - **Routing**：本資料夾在 [`docs/README.md`](../README.md) 主線列為「Deliverables（學期繳交素材）」。對外**寫作 / 報告心態 / 禁說清單**指南在 [`../pawai-demo/`](../pawai-demo/)；6/18 戰略邊界與禁說清單權威在 [`../mission/2026-06-18-demo-north-star.md`](../mission/2026-06-18-demo-north-star.md)。
> - **What this is NOT**：不是內部設計真相（見 `pawai-brain/` / `navigation/`）、不是 capability scoreboard。docx/pdf 是 render 產物，`.md` 為原始檔。

---

## 內容

| 路徑 | 內容 |
|------|------|
| [thesis/](thesis/) | 論文 / 報告 / 系統限制與可行性分析（`.md` + `.docx` + `.pdf`） |

---

## 重要日期（硬底線）

- **2026/4/13**：文件繳交（週日初版、週一繳交）— 已過
- **2026/5/12**：學校 demo
- **2026 五月底**：展示 / 驗收

---

## 文件規則

- `.md` 為原始檔，`.docx` / `.pdf` 為老師收到的格式
- 大檔（> 5 MB）目前仍在 git，未啟用 git-lfs（5/14 後評估）
- `__pycache__/` 已加入 `.gitignore`，不應再進 git
