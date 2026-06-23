# ADR-0006: 6/18 Demo Claim Policy（窄版 pass + 禁說清單 + fail-closed）

- **Date**: 2026-06-05
- **Status**: accepted

## Context

6/18 是現場驗收（非剪輯影片）。6/04 HITL baseline（SHA `78fbf36`、`run_trusted=true`、`readiness=not_ready`）+ 6/05 收斂審計 + 6/05 教授會議共同界定了「這場能誠實宣稱什麼」。若不把這條邊界凍結成持久決策，簡報固化期的「想多講」壓力會把 demo 推回 overclaim，重演 5 月三場 review 的失分。

本 ADR 把 North Star v2 的禁說清單 + scoreboard-first + fail-closed 收斂成一條可被接手者一眼讀懂的 demo 政策。它是 ADR-0005（evidence-first）在 6/18 這個具體場景的落地。

替代方案考量過：(a) 把禁說清單只留在 North Star 散文（接手者容易漏看）；(b) 等 baseline 全跑完再定 claim（時程不允許）；(c) 用 6/04 trusted snapshot 鎖窄版 claim + 明文禁說 + fail-closed runtime。本 ADR 取 (c)。

## Decision

6/18 demo / 簡報 / 對外材料的 claim 邊界，以 [`docs/mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md) 為 canonical，本 ADR 凍結其持久骨幹：

### A. 窄版 pass（只有這三條能進 Brain 主線並口頭宣稱，且必帶窄版邊界）

| 能力 | 6/04 grade | 窄版邊界（caveat 必同行） |
|---|---|---|
| `face.recognition` | 🟢 pass | **只認已註冊熟人**；不講陌生人拒絕 / 守護 / 不會認錯 |
| `object.cup` | 🟢 pass | **只 cup-only、~1m 近距**；不講通用偵測 / 尋物 / VLM / 可靠顏色 |
| `voice.command` | 🟢 pass | **只固定指令集意圖分類**；非自由語音理解 |

### B. 禁說清單（6/18 一律不宣稱）

- `voice.stop` 現為 **fail** → 不可當 safety stop；mic_stop / observer 接上量測前不講 safety-stop / latency。
- `gesture.wave` 現為 **fail** → camera 動態 wave 不演；static gesture 僅 fallback / demo-only（除非重 baseline）。
- `pose.basic` / `pose.fall` **insufficient_data** → Studio-only；跌倒是 future、非緊急行為。
- `nav.*` 全 **insufficient_data** → dry-run 只證 fail-closed / action chain 已接線，**非真實移動 / 動態避障 / 自走**。不宣稱完整自主導航、自動找人、動態繞障、跟隨、巡邏整個機構。
- **brain 反幻覺 fail** → 不講「不會幻覺 / 已通過反幻覺測試」；LLM 持人格曾杜撰未感知世界狀態。
- 不講：完整長照照護可靠、導盲犬能力、通用物體辨識、守護 / 陌生人警報 / 主動保護、LLM 自然度 = 機器人可靠性。

### C. 可宣稱的機制（限機制、非 e2e pass）

- `brain.skill_gate` / `brain.trace`：可 demo **deterministic safety / allowlist 拒絕 + trace**（rule-based、fail-closed、91 unit test 全綠）；不講「非幻覺自主 agent」、不講 e2e 已實機跑通。
- `studio.evidence`：evidence 顯示 / provenance 有價值，但**不等於能力 pass**（除非綁 trusted baseline 資料）。

### D. Fail-closed 鐵律（runtime）

- Brain 對 `degraded` / `fail` / `insufficient_data` 能力**不得觸發 motion / nav 類動作**。
- 此 capability health gate **6/18 預設關閉（fail-closed）、不接 runtime motion 觸發**；在它真正接上前，不得宣稱「capability health gate 已存在 / 已生效」。
- nav 任何 claim 在 nav baseline run 標 pass（或明確人工安全 override）前一律 `insufficient_data`、**只在 Studio 顯示、不口頭宣稱**。

### E. 模型研究分層（不預設變 backlog）

模型候選一律標分層：`BASELINE_NOW` / `STUDIO_ONLY_NOW` / `SPIKE_AFTER_FAIL` / `FUTURE_RESEARCH`。6/05 收斂審計結論：**六條能力全 KEEP_CURRENT，6/18 不換任何模型**——錢花在上機補量測，不花在換模型。

## Consequences

**正面**：

- 接手者 / 多 agent 一眼讀懂 6/18 能講什麼、不能講什麼，不必逐份比對散文。
- 窄版 pass + 禁說清單 + fail-closed 三件套讓 demo 無 overclaim 包袱，scoreboard 誠實成可信度。
- 與 6/04 trusted snapshot 物理綁定，claim 可被 audit。

**負面**：

- 能上台講的能力少（只三條窄版 pass），第⑤⑦步等靠 Studio 顯示 / 語音說明，旁白負擔重。
- 窄版邊界 caveat 必同行，敘事節奏變慢。
- baseline 重跑後若某能力翻盤（如 gesture / voice.stop 修好），需回頭 amend 本 ADR 對應列。

## Related

- claim 真相源 canonical：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../mission/2026-06-18-capability-claim-matrix.md)
- 戰略邊界：[`docs/mission/2026-06-18-demo-north-star.md`](../mission/2026-06-18-demo-north-star.md) v2 §5 禁說 / §7 nav 鐵律 / §9 scoreboard-first
- 證據：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（grade + honesty caveats）
- 收斂審計：[`docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`](../archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md) §2 / §G
- 上層政策：ADR-0005（evidence-first）；定位邊界：ADR-0001 / ADR-0002（被 North Star v2 amend，見各 ADR amendment note）
- 互動入口：ADR-0003（Studio PTT）
- 未來能力翻盤後 amend：開 ADR-000X supersede 本 ADR A / B 表對應列
