# ADR-0005: Evidence-First Claim Policy（先量化後宣稱）

- **Date**: 2026-06-05
- **Status**: accepted

## Context

2026-05 三場驗收 + 6/05 教授會議反覆出現同一個失分模式：文件 / 簡報宣稱了未經實測的能力，被追問時拿不出證據，反而傷可信度。具體：

- demo 敘事預設「功能寫了就算有」，把「機制存在」當成「e2e 驗證過」。
- 能力被當二元（有 / 沒有），但實際上分級（pass / degraded / fail / insufficient_data）才反映真相。
- 6/04 HITL baseline 跑出 `readiness=not_ready`（`voice.stop` / `gesture.wave` fail、nav / brain 未量），若沒有政策強制「未 pass 不宣稱」，敘事很容易滑回 overclaim。

老師的核心方法論訊號：**不要用桌機 GPU 標準評估，先量化能力，再決定講什麼 / 換不換模型**。沒有明文政策，這個原則會在簡報固化期被「想多講一點」的壓力侵蝕。

替代方案考量過：(a) 靠 demo 排練 ad-hoc 約束（5/22 已證會滑回）；(b) 永久禁止任何未 production 的 claim（太嚴，degraded 能力的合法顯示也被砍）；(c) 明文化分級 + 證據綁定政策。本 ADR 取 (c)。

## Decision

PawAI 對外 / 文件 claim 一律遵守 **evidence-first** 政策：

1. **能力分四級**，每級對應可做的事：
   - **pass** → 可進 Brain 主線（可控制機器人）、可口頭宣稱。
   - **degraded** → 可在 Studio 顯示、可語音說明，但**不可控制機器人**、不作為可靠性宣稱。
   - **fail** → 不宣稱、不觸發。
   - **insufficient_data** → 不放行高風險動作（motion / nav），不宣稱已具備。

2. **claim 必須綁證據**：任何能力 claim 的最終事實依據是 [`docs/runbook/baseline-evidence/`](../runbook/baseline-evidence/) 的當前 trusted snapshot（grade + honesty caveats），不是任何敘事文件。能不能講連 [canonical claim matrix](../mission/2026-06-18-capability-claim-matrix.md)。

3. **三條禁止句式**（硬性）：
   - 不得把 `insufficient_data` 寫成 pass。
   - 不得把「機制存在」寫成「e2e 已驗證」。
   - 不得把「模型研究 / 候選」預設變成「已實作 backlog」。

4. **窄版邊界必須隨 claim 同行**：pass 的能力若只在窄條件成立（如 `object.cup` 僅 ~1m 近距 cup-only、`face.recognition` 僅已註冊熟人），claim 必須帶 caveat，不得放大為通用能力。

5. **scoreboard 的誠實本身是可信度**：被問「可靠嗎」一律指向 scoreboard——「這項 pass 所以在用、這項 degraded 所以只顯示、這項 fail 所以不宣稱」。

## Consequences

**正面**：

- overclaim 風險系統性下降；被追問時有 Studio evidence / baseline snapshot 背書。
- 與 ADR-0004 #1 銜接：baseline-evidence 是 claim 真相的單一物理錨點。
- degraded 能力仍有合法用途（Studio 顯示），不被一刀切。
- 對齊老師「先量化後宣稱」方法論，scoreboard 變成敘事資產而非弱點。

**負面**：

- 簡報能講的能力比「功能清單」少，旁白要主動 frame「我們選擇誠實揭露」。
- 每個 claim 都要回查 snapshot，撰寫成本上升。
- baseline 未跑完前，許多能力卡在 insufficient_data，敘事掛點受限（需靠價值 / 角色語言補）。

## Related

- claim 真相源 canonical：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md)（8 欄位能力卡 + grade 速查）
- 當前 trusted snapshot：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（grade + honesty caveats）
- 量測協定（怎麼量）：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md)
- 真相層級：ADR-0004（本政策的 #1 即該層級的 empirical layer）
- 6/18 demo 具體禁說清單：ADR-0006
- 未來若引入新的證據 freeze 流程，開 ADR-000X 補充本政策的取證細節
