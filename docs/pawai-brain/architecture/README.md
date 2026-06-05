# PawAI Brain × Studio — 架構文件索引

> **Scope**：PawAI 互動主線的**架構真相**入口 — 把 Brain / Executive / Studio / 感知資料流的架構文件分層索引（哪份是當前總覽、哪份是 5/11 freeze-snapshot、哪份是 historical/outdated）。
> **Status**：active（架構索引）。本檔**不是**能力 claim 真相，也不重複任何能力分級。
> **Owner lane**：brain-studio（搭配 `docs/pawai-brain/README.md` 與各模組 `CLAUDE.md`）。
> **Source-of-truth 優先序**（高→低）：程式碼 / topic schema ＞ `docs/runbook/baseline-evidence/2026-06-04-hitl/`（最新唯一 trusted snapshot，SHA `78fbf36`，readiness=`not_ready`）＞ `docs/mission/2026-06-18-capability-claim-matrix.md`（canonical Capability Claim Matrix）＞ `docs/pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B（claim 判決依據）＞ `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`（門檻 / 怎麼量）＞ `docs/mission/2026-06-18-demo-north-star.md`（戰略邊界）＞ 本目錄（架構）＞ `docs/contracts/interaction_contract.md`（topic/action schema, v2.5 凍結）。
> **Maintained child files**：`overview.md`（當前架構總覽）、`designs/clean-architecture.md`、`designs/data-flow.md`（兩份均部分過時，見下表）。
> **Archived / historical 邊界**：`0511/**` 為 **5/11 freeze-snapshot**（保留作引用，**不重複維護**）；任何「現在能跑什麼」一律以 canonical claim matrix 為準，不以 0511 快照或 designs 舊圖為準。
> **本 README 不是**：能力 claim 真相（→ canonical claim matrix）、門檻定義（→ `specs/2026-06-18-capability-baseline-spec.md`）、介面契約（→ `docs/contracts/interaction_contract.md`）。

---

## 架構文件導覽

| 文件 | 狀態 | 內容 |
|---|---|---|
| [`overview.md`](overview.md) | active（架構真相）；能力宣稱/時程 superseded | Brain（決策引擎）× Studio（操作觀測介面）整合總覽：目標、系統架構、資料流、模組職責、降級鏈、部署拓樸。**頂部 6/05 註記**說明哪些能力宣稱已被 6/04 baseline + 6/05 audit 取代。 |
| [`designs/clean-architecture.md`](designs/clean-architecture.md) | ⚠️ 部分過時 | Clean Architecture 四層分層原則（3/08）。原則可參考，但落地狀況與文件描述有差距（只有 `go2_robot_sdk` 完整落地，頂部 banner 已標）。 |
| [`designs/data-flow.md`](designs/data-flow.md) | ⚠️ outdated（結構性差異） | 早期（3/13）資料流與互動流程圖。頂部 banner 已標已知偏差，**以 `docs/contracts/interaction_contract.md` 為準**。 |

---

## 5/11 freeze-snapshot（`0511/`，historical 參考，不重複維護）

> `0511/` 是 **5/11 各 lane 的凍結架構快照**（runtime flow / graph node map / persona-capability-memory / debug runbook 等，按 lane 拆檔）。它是當時 demo 衝刺期的架構照片，**保留作引用**：理解某條鏈路「5/11 時長怎樣」很有用，但**不得當作「現在能跑什麼 / 能力是否 pass」的依據**。能力分級一律回 canonical claim matrix。

| lane | snapshot 入口 |
|---|---|
| Brain | `0511/brain.md` → `0511/brain/`（runtime-flow / graph-node-map / persona-capability-memory / debug-runbook） |
| Face | `0511/face.md` → `0511/face/` |
| Gesture | `0511/gesture.md` → `0511/gesture/` |
| Pose | `0511/pose.md` → `0511/pose/` |
| Object | `0511/object.md` → `0511/object/` |
| Nav | `0511/nav.md` → `0511/nav/` |
| Speech | `0511/speech.md` → `0511/speech/` |
| Studio | `0511/studio.md` → `0511/studio/` |

---

## 能力是否 pass / 哪段能講（不在本目錄重複，連結 canonical）

- **canonical Capability Claim Matrix**：`docs/mission/2026-06-18-capability-claim-matrix.md`（判決來源 6/05 audit §B，基準 `docs/runbook/baseline-evidence/2026-06-04-hitl/`）。
- **能力門檻 / 怎麼量**（provisional until baseline）：`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`。
- **戰略邊界 / 禁說清單**：`docs/mission/2026-06-18-demo-north-star.md`。
- **介面契約**（topic / action / service schema, v2.5 凍結）：`docs/contracts/interaction_contract.md`。
