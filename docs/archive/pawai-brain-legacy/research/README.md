# PawAI Brain Research Index

> **Scope**：Brain / 感知 / 語音主線的「研究」層 — 模型候選調查、選型路徑、收斂審計。
> **Status**：active index ｜ **Owner lane**：pawai-brain ｜ **Created**：2026-06-05
> **核心紀律：research-not-truth**。本資料夾的檔案是**調查與候選**，**不是**能力 pass/fail 真相、不是實作 backlog、不是 Brain 主線契約。
> **唯一例外**：[`2026-06-05-618-demo-convergence-audit-and-model-tournament.md`](2026-06-05-618-demo-convergence-audit-and-model-tournament.md) 經指定為證據權威鏈 #2（read-only audit），可用於裁定 claim-scope / 換不換模型 / docs-drift，但**本身仍不覆寫 baseline-evidence 數據或 contracts**。
> **Source-of-truth priority（最新優先）**：
> 1. 實測證據（最終事實）：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/)（`78fbf36`, readiness=`not_ready`）。
> 2. 收斂審計（本層的 6/05 audit）。
> 3. 量測協定：[`../specs/2026-06-18-capability-baseline-spec.md`](../specs/2026-06-18-capability-baseline-spec.md)。
> 4. 戰略邊界 / 能不能講：[`docs/mission/2026-06-18-demo-north-star.md`](../../mission/2026-06-18-demo-north-star.md) v2 + canonical claim matrix。
> **能力 claim 一律連結 → [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md)，勿在本層重複整份散文。**
> **What this index is NOT**：不是 spec（[`../specs/README.md`](../specs/README.md)）、不是 plan（[`../plans/README.md`](../plans/README.md)）。

---

## 模型研究分層（tier 語意）

研究檔頂部都有 tier banner，意義如下（**不要把任何 tier 預設變成實作 backlog**）：

| Tier | 意思 | 6/18 效果 |
|---|---|---|
| `BASELINE_NOW` | 影響 6/18 主線故事、必須量測 | 只在 scoreboard grade=`pass` 時才可進 Brain 主線 |
| `STUDIO_ONLY_NOW` | 現在值得當 evidence 顯示，但**不得**驅動 Brain 決策 / 移動 / nav | Studio overlay / event-only |
| `SPIKE_AFTER_FAIL` | 只在主 baseline 路徑 fail/卡住時才測 | time-boxed fallback spike，非平行承諾 |
| `FUTURE_RESEARCH` | 有趣但出 6/18 範圍 | 6/18 不花 baseline 時間 |

## 檔案

| 檔案 | 性質 | 主要 tier | 摘要 |
|---|---|---|---|
| [`2026-06-05-618-demo-convergence-audit-and-model-tournament.md`](2026-06-05-618-demo-convergence-audit-and-model-tournament.md) | **read-only audit（證據鏈 #2）** | — | 6/04 snapshot + 6/05 會議基準的 claim-scope / 換不換 / docs-drift 裁定；錦標賽結論：六能力全 `KEEP_CURRENT`（不換模型）|
| [`2026-06-02-model-candidate-registry.md`](2026-06-02-model-candidate-registry.md) | research registry（候選註冊，非承諾）| 混合 `BASELINE_NOW` / `STUDIO_ONLY_NOW` / `SPIKE_AFTER_FAIL` / `FUTURE_RESEARCH` | 各能力模型候選 + tier + gate rule，明確非 6/18 promise list |
| [`2026-06-03-asr-llm-tts-selection-path.md`](2026-06-03-asr-llm-tts-selection-path.md) | research（選型路徑整理）| `BASELINE_NOW`（語音三段主線）| ASR/LLM/TTS 採用路徑 + 淘汰原因；現役主線見 `speech/README.md`，**這份不換現役 pass 模型** |
| [`2026-06-04-pinto-jetson-deployable-models.md`](2026-06-04-pinto-jetson-deployable-models.md) | research（Jetson 可部署清單）| `FUTURE_RESEARCH`（除已實機 5 個錨點外）| PINTO zoo → Orin Nano 8GB 兩道門檻判定；僅 5 個已實機為地面真值，其餘推定 |
| [`2026-06-04-pinto-model-zoo-full-analysis.md`](2026-06-04-pinto-model-zoo-full-analysis.md) | research（全 zoo 解析）| `FUTURE_RESEARCH` | 19 類 × 482 模型 × Jetson 部署判定；四級標記（可/很可能/風險/不可），非 backlog |

> 模型錦標賽結論（6/05 audit §G）：**六條能力全部「不換」**（`KEEP_CURRENT`）。6/18 demo claim 沒有任何一條依賴換模型。錢花在上機補量測，不要花在換模型。
