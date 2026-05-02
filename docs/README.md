# PawAI 文件入口

**專案**：老人與狗 (Elder and Dog) / PawAI
**5/12 學校 Demo 倒數中** — 主線文件均在以下 7 條路線下。

> **30 秒原則**：找不到資訊 30 秒之內 → 走 `pawai-brain/` 或 `navigation/`，再不行去 `archive/`。

---

## 主線文件 (active)

| # | 路線 | 入口 | 內容 |
|:-:|------|------|------|
| 1 | **Brain** | [pawai-brain/README.md](pawai-brain/README.md) | 互動主線：感知 / 語音 / Studio / Brain 決策層 |
| 2 | **Navigation** | [navigation/README.md](navigation/README.md) | 移動主線：LiDAR / Nav2 / AMCL / D435 depth / 避障 |
| 3 | **Contracts** | [contracts/README.md](contracts/README.md) | 跨主線 ROS2 介面契約 + 設計總則 |
| 4 | **Runbook** | [runbook/README.md](runbook/README.md) | Demo 救火 SOP（Jetson / Network / GPU server / Go2 操作） |
| 5 | **Mission** | [mission/README.md](mission/README.md) | 專案定位 / Demo 劇本 / 八大功能 SoT |
| 6 | **Deliverables** | [deliverables/](deliverables/) | 學期繳交素材（thesis） |

## 歷史

| # | 路線 | 入口 | 內容 |
|:-:|------|------|------|
| 7 | **Archive** | [archive/](archive/) | 5/02 reorg 前歷史 + 2026-02-11 restructure |

---

## 衝突仲裁（誰是真相來源）

- **程式碼** → 永遠是最終真相
- **介面契約**（ROS2 topic / action / service schema）→ [contracts/interaction_contract.md](contracts/interaction_contract.md)
- **Brain 決策邏輯 / 感知模組設計** → `pawai-brain/{specs,plans,perception/*,speech,studio}/`
- **導航避障設計與實作** → `navigation/{plans,research,setup}/`
- **專案方向 / Demo 劇本 / 八大功能** → `mission/README.md`
- **環境建置與救火 SOP** → `runbook/`
- **Claude Code 工作規則** → 模組 `CLAUDE.md`（散在各主線資料夾）

---

## 文件治理

- **不主動重寫沒碰到的文件** — 改了程式碼才同步對應 `README.md`
- **新增 / 移除 ROS2 topic** → 同步 `contracts/interaction_contract.md`
- **每日收工** → 更新 `references/project-status.md`（在 repo 根目錄 `references/`，不在 `docs/`）
- **命名約定**：`YYYY-MM-DD-description.md`（plan / spec / research）

詳見本檔 commit 紀錄與 [`archive/2026-05-docs-reorg/README.md`](archive/2026-05-docs-reorg/README.md)（本次重組來源）。

---

*Last reorg: 2026-05-02（推翻 5/13 pre-demo policy 提前執行；18 top-level → 7 active + archive）*
