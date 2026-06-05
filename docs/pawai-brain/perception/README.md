# 多模態感知（Perception）— 模組索引

> **Scope**：PawAI 互動主線的四條感知能力（face / gesture / object / pose）模組設計真相**入口**｜**Status**: active / canonical index (module layer)
> **Owner lane**: pawai-brain / perception
> **能力 claim 真相源（canonical）**：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md) — 任何「能不能講、屬哪層」一律以此頁為準，本索引**不重複整份散文**。
> **能力 grade 證據（最終事實）**：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/)（SHA `78fbf36`, run_trusted=true, readiness=`not_ready`）— grade + honesty caveats 凌駕一切敘事。
> **量測協定（怎麼量）**：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../specs/2026-06-18-capability-baseline-spec.md)。
> **這頁不是什麼**：不是能力 pass/fail 的裁定（看 baseline-evidence）；不是量測協定（看 spec）；不放程式細節（看各模組 README）。各模組 README 是該模組的設計真相；`research/` 子樹一律 research-only / 非真相。

---

## 四能力速查（grade 以 6/04 trusted baseline 為準）

| 能力 | 6/04 grade | claim level | 模組 README | 一句話邊界 |
|---|---|---|---|---|
| `face.recognition` | 🟢 pass（窄版） | CLAIM_WITH_CAVEAT | [face/](./face/README.md) | 僅**已註冊熟人** + 空景 idle；**不講**陌生人拒絕 / 守護 / 「不會認錯」 |
| `object.cup` | 🟢 pass（窄版近距 ~1m） | CLAIM_WITH_CAVEAT | [object/](./object/README.md) | 僅 **~1m cup-only**；**不講**通用 / 80 類 / 尋物 / VLM / 可靠顏色 / 2m 穩 |
| `gesture.wave` | 🔴 **fail** | DO_NOT_CLAIM | [gesture/](./gesture/README.md) | camera 動態 wave **fail**；靜態手勢是 fallback/demo-only（非 wave 能力） |
| `pose.basic` / `pose.fall` | ⚪ insufficient_data | DO_NOT_CLAIM | [pose/](./pose/README.md) | basic = **Studio-only**；跌倒是 **future、非緊急**（`enable_fallen:=false`） |

> **完整 8 欄位能力卡**（Current Claim / Claim Level / Evidence-Provenance / Pass-Degraded-Fail-Insufficient / Fallback / Non-Claims / Model Candidates / Next Retest）見 [claim matrix §1](../../mission/2026-06-18-capability-claim-matrix.md#1-8-欄位能力卡每能力-canonical)；各模組 README 頂部亦有對應能力卡速查表（連回 matrix）。

---

## 用詞紀律（一行版，細節回 [North Star §2/§5](../../mission/2026-06-18-demo-north-star.md) + claim matrix §3）

- 一律「守望 / 提醒 / 回報 / 非接觸 / 可解釋互動」；**禁用**守護 / guardian / 陌生人警報 / 保護長者 / 照護安全 / 防跌倒。
- 窄版 pass 不擴張：face = 僅 Roy / 空景、object.cup = ~1m cup-only。
- fail 誠實揭露：gesture.wave camera 動態不演。
- insufficient_data 只顯示不宣稱：pose Studio-only。
- 模型研究分層：BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH — 研究**不**預設變實作 backlog（claim matrix §2）。

---

## 模組結構

每個能力資料夾固定四件：

| 檔案 | 角色 |
|---|---|
| `README.md` | 模組設計真相（含能力卡速查 + governance header） |
| `CLAUDE.md` | Claude Code 模組工作規則（不能做 / 改前先看 / 陷阱 / 驗證指令） |
| `AGENT.md` | topic 介面契約（輸出/輸入 schema + 接手清單） |
| `research/` | **research-only / 非真相**：選型調查、benchmark、PR extraction plan（不得覆寫 baseline-evidence 或 contracts） |

> ROS2 topic schema 的權威是 [`docs/contracts/interaction_contract.md`](../../contracts/interaction_contract.md)（各 AGENT.md 為摘要鏡像）。
