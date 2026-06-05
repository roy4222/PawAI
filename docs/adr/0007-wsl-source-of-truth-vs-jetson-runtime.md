# ADR-0007: WSL 為 source-of-truth、Jetson 為 runtime（SHA-match 取證鐵律）

- **Date**: 2026-06-05
- **Status**: accepted

## Context

PawAI 是雙平台架構：

- **WSL / 開發機（DESKTOP）**：git source-of-truth、程式碼編輯、文件、scoreboard 構建。
- **Jetson Orin Nano**：ROS2 runtime、模型推理、Go2 連線——能力 baseline 的**原始證據**在這裡產生。

6/04 HITL baseline 取證流程暴露一個可信度關鍵：scoreboard 的 trusted 與否，取決於「**評分用的程式碼版本是否等於 Jetson 上實際跑的版本**」。若 WSL 上 `build_scoreboard` 用的 checkout 與 Jetson deploy manifest 的 SHA 不一致，grade 就不可信（可能用新 code 評舊 runtime 的行為）。

6/04 snapshot 實證了這條鏈：

- Jetson deploy manifest：`git_sha=78fbf36`（`jetson-deploy` 寫入 `.pawai-last-deploy`）。
- WSL scoreboard：`wsl_commit=78fbf36`，**built at checkout `78fbf36` 以對齊 Jetson deploy manifest**。
- snapshot 計算出 `version_mismatch=false` → `run_trusted=true`。

若沒有把這條「WSL 評分必須對齊 Jetson runtime SHA」鐵律凍結成持久決策，未來取證很容易在 WSL 上用 dirty / 不同 SHA 跑出「看起來 pass」但不可信的 scoreboard，重蹈 overclaim。

替代方案考量過：(a) 直接在 Jetson 上算 scoreboard（Jetson 資源吃緊、且 WSL 才有 git source-of-truth）；(b) 不檢查 SHA，靠人記得對齊（會漏）；(c) 明文化 WSL=source-of-truth / Jetson=runtime + 自動 SHA-match gate 驅動 `run_trusted`。本 ADR 取 (c)。

## Decision

凍結雙平台的真相分工與取證鐵律：

1. **WSL = source-of-truth**：git tracked tree、scoreboard 構建、`pawai readiness` 判定都在 WSL。`build_scoreboard --preflight` **必須 built at 與 Jetson deploy manifest 相同的 checkout SHA**。

2. **Jetson = runtime / 證據產地**：raw baseline 記錄（`capture_baseline_round.py`、voice `run_speech_test.sh`）在 Jetson + Go2 實機產生；deploy 由 `jetson-deploy`（rsync + colcon build）寫入 manifest（`.pawai-last-deploy`，含 `git_sha`）。

3. **SHA-match gate 驅動 `run_trusted`**：snapshot 比對 `wsl_commit` vs `jetson_install_sha`：
   - `version_mismatch=false` 且 layer0 preflight pass → `run_trusted=true`。
   - SHA 不一致 → snapshot 不 trusted，grade 不得引用為 claim 真相。
   - WSL 經 SSH 讀 Jetson 路徑（沿用 `status.py` 讀 `{jetson_repo}/.pawai-last-deploy`）取得 manifest SHA。

4. **provenance 必須隨 snapshot 同存**：每次 freeze 附 `wsl_commit` / `jetson_install_sha` / `dirty` 狀態。`dirty=true` 若僅來自 untracked 檔（slide PDF / `.tmp/`），需在 evidence README 明示「非 tracked-code 變更」；reproducibility 較弱時，**下次 freeze 應附 `git status --short` 或從乾淨 checkout 重跑**。

5. **rsync 只搬源碼、不 rebuild `install/`**：感覺新 code / 參數沒生效時跑 `colcon build`，不要只 `sync once`——否則 Jetson runtime 與 manifest SHA 名義一致但行為不一致。

## Consequences

**正面**：

- scoreboard trusted 與否變成可機器驗證的 SHA-match，而非人工記憶。
- WSL（git 真相）與 Jetson（runtime 真相）職責不再混淆，取證鏈可 audit。
- 與 ADR-0005 銜接：baseline-evidence 之所以能當 claim 真相 #1 層，正因為 `run_trusted=true` 的 SHA-match 保證。

**負面**：

- 每次 baseline 前要先 deploy + 對齊 SHA，流程多一步；忘了 build 會得到名義一致但行為不一致的 runtime。
- `dirty=true`（即使只是 untracked slide）會讓 reproducibility 標記變弱，需額外註記，增加 freeze 紀律負擔。
- WSL 經 SSH 讀 Jetson manifest 依賴網路 / Tailscale 可達；離線時無法判定 trusted。

## Related

- 6/04 trusted snapshot（實證本鐵律）：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（README provenance note + `baseline_snapshot.json` 的 `version_mismatch` / `run_trusted` + `jetson_manifest.json` 的 `git_sha`）
- readiness 路徑覆寫（`PAWAI_SCOREBOARD_PATH`、SSH 讀 Jetson）：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md) §8
- 真相層級（本 ADR 鞏固 #1 empirical layer 的可信前提）：ADR-0004
- claim 政策（本鐵律是其證據可信的物理基礎）：ADR-0005 / ADR-0006
- 未來若改用乾淨 CI freeze 流程，開 ADR-000X supersede 本 ADR 的 dirty 處理段
