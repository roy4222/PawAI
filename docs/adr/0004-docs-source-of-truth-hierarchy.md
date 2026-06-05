# ADR-0004: 文件真相來源層級（source-of-truth hierarchy）

- **Date**: 2026-06-05
- **Status**: accepted

## Context

2026-06 docs 重構暴露一個反覆出現的摩擦：同一個能力 / 同一條 claim 散落在多份文件，當它們互相矛盾時，沒有明文的仲裁規則決定誰是最終真相。具體症狀：

- `research/` 子樹（含 `pawai-brain/research`、`navigation/research`）長期被當成真相引用，但它本質是「研究、未驗證」。
- `archive/` 內的歷史 spec 仍被新文件連結為現行設計。
- mission 敘事文件（demo-flow-plan / final-presentation-outline）引用 6/03 的 face=fail，而 6/04 HITL snapshot 已是更新的 trusted 證據。
- 多 agent / 接手者每次都得重新辯論「這份算不算數」。

沒有一份 canonical 仲裁表，docs drift 會無限累積；任何「能力是否 pass」的問題都可能拿到三個不同答案。

替代方案考量過：(a) 每份文件自己宣告自己是真相（現況，會撞）；(b) 把所有真相塞進單一巨型文件（不可維護、會變 god-doc）；(c) 明文化「由高到低」的分層仲裁鏈，每層職責單一、衝突時逐層往上問。本 ADR 取 (c)。

## Decision

採用 **10 層 source-of-truth hierarchy**，衝突時由高到低仲裁（**最新證據優先**）：

| # | 層 | 真相範圍 |
|---|---|---|
| 0 | 程式碼 / runtime topic schema | 永遠是最終真相 |
| 1 | 實測證據（empirical） | `docs/runbook/baseline-evidence/` 的當前 trusted snapshot — 能力 pass/fail 的最終事實 |
| 2 | 收斂審計（read-only audit） | `docs/pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` — 經指定升格為 #2，但不覆寫 baseline 數據 |
| 3 | 能力規格（how to measure） | `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md` — 怎麼量、怎樣算 pass |
| 4 | 戰略邊界（what to claim） | `docs/mission/2026-06-18-demo-north-star.md` v2 — 能不能講、屬哪層 |
| 5 | 介面契約 | `docs/contracts/interaction_contract.md`（ROS2 topic/action/service/message schema） |
| 6 | 模組設計真相 | `docs/pawai-brain/{specs,plans,perception,speech,studio}/` 與 `docs/navigation/{plans,research,setup,specs}/` |
| 7 | 產品方向 / Demo 劇本 / 八大功能 | `docs/mission/README.md` |
| 8 | 持久決策 | `docs/adr/`（ADR，可被新提案 supersede） |
| 9 | 環境建置與救火 SOP | `docs/runbook/` |
| 10 | 頂層分流 / 仲裁入口 | `docs/README.md`（7-route taxonomy + 衝突仲裁表） |

**關鍵原則**：

- **實測 > 審計 > 規格 > 敘事**。能力是否 pass，一律回 #1 baseline-evidence，不被任何敘事文件覆寫。
- `research/`（含 lane research）一律 **research-not-truth**，不得覆寫 baseline-evidence 或 contracts——唯一例外是 6/05 convergence audit 被明確指定為 #2。
- `archive/` 全 **frozen**，不得被當作現行設計引用。
- 「最新證據優先」：當兩份 empirical snapshot 衝突，最新 trusted 取代舊的（6/03 first-trusted 已被 6/04 取代，僅作歷史）。

## Consequences

**正面**：

- 任何 claim 衝突有明確仲裁路徑，多 agent / 接手者不必每次重辯。
- 把「研究」與「真相」明確分層，杜絕 research 文件被誤當權威。
- 與 ADR-0005（evidence-first claim policy）銜接：#1 baseline-evidence 是 claim 真相的物理錨點。

**負面**：

- 層級維護成本：新增頂層資料夾（如 `adr/`、`agents/`、`pawai_cli/`）需同步收進 `docs/README.md` 仲裁表，否則 off-route。
- 「最新證據優先」要求每次 freeze 都標清 trusted 邊界，否則舊 snapshot 可能被誤用。
- 10 層對非工程接手者偏重；需 `docs/README.md` 的 route map 做為輕量入口。

## Related

- 證據權威鏈 canonical：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md) §證據權威鏈
- 當前 trusted snapshot：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)
- 頂層分流入口：[`docs/README.md`](../README.md)
- ADR-0005（evidence-first claim policy）細化 #1 如何驅動 claim
- 未來若新增 / 重排層級，開 ADR-000X supersede 本表對應列即可
