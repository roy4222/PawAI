# HITL 驗證協定

> **Scope**：Issue #86 的 HITL 驗證分級、逐能力硬體對照、Go2 motion sign-off 與 artifact layout / schema。
> **Status**：active / agent-config（取證流程，非能力真相）。
> **Owner lane**：agents。
> **Source-of-truth priority**：本檔定義**怎麼取證 / 怎麼簽核**，**不裁定**能力是否 pass。量測結果的最終事實依據是 [`../runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（trusted snapshot）；路徑 / readiness fail-closed 規則引用 [`../architecture/specs/2026-06-18-capability-baseline-spec.md`](../architecture/specs/2026-06-18-capability-baseline-spec.md) §9。
> **詞彙**：trusted snapshot / readiness / HITL / fail-closed 等共用定義見 [`domain.md`](domain.md) §Glossary。
> **What this file is NOT**：不是能力 grade、不是 CI gate（不做 T3/T4 自動 gate）、不是 dashboard。

本文件定義 Issue #86 的 HITL 驗證與 artifact 版本化規則。範圍只含文件與 JSON Schema，不改 runtime code、不做 T3/T4 自動 CI gate、不做 artifact dashboard / web UI。

## 外部邊界

- #73 `demo.yaml`：Layer-0 preflight checks 的內容與 runner 由 #73 定義；本文件只消費其輸出 `artifacts/baseline/preflight_result.json`。
- #87 freeze：frozen demo snapshot、readiness freeze 流程與 demo 當天讀取策略由 #87 定義；本文件只要求 sign-off 與 snapshot 綁定 commit。
- SPEC §9：路徑與 readiness fail-closed 規則引用 `docs/architecture/specs/2026-06-18-capability-baseline-spec.md:380` 到 `:420`，不在此重寫。

## 驗證分級

| 分級 | 何時需要 | 最小產物 |
|---|---|---|
| Jetson smoke | 涉及 Jetson runtime、ROS2 topic、D435、camera、mic、baseline observer、preflight 輸出或 Jetson 上的 `build_scoreboard` 產物 | `preflight_result.json`、`baseline_result.jsonl`、`baseline_snapshot.json`、logs 或 screenshots |
| Go2 motion | 測試會送出或驗證 Go2 實體移動、停止、禁自動恢復、避障或任何 actuation 行為 | Jetson smoke 產物 + `motion_sign_offs.jsonl` + video evidence sha |

不涉及硬體的純文件、schema、fixture 或 dry-run 驗證不需要 Jetson smoke。voice / face / gesture / object 的感知測試需要 Jetson smoke；只有當結果直接驅動 Go2 移動時，才升級成 Go2 motion。

## 逐能力硬體對照

| capability_id | 必要硬體 | 驗證分級 | Go2 motion sign-off |
|---|---|---|---|
| `face.recognition` | Jetson + D435 | Jetson smoke | 否 |
| `voice.command` | Jetson + mic | Jetson smoke | 否 |
| `voice.stop` | Jetson + mic | Jetson smoke；若用於實體停車 trial，跟隨 `nav.safe_stop` | 視 nav trial 而定 |
| `gesture.wave` | Jetson + camera | Jetson smoke | 否 |
| `object.cup` | Jetson + camera | Jetson smoke | 否 |
| `nav.safe_stop` | Go2 + 安全場地 | Go2 motion | 是 |
| `nav.no_auto_resume` | Go2 + 安全場地 | Go2 motion | 是 |
| `nav.short_move` | Go2 + 安全場地 | Go2 motion | 是 |
| `nav.dynamic_avoidance` | Go2 + 安全場地 | Go2 motion；future 能力若測才簽 | 是 |
| `pose.basic` | Jetson + camera | Jetson smoke | 否 |
| `pose.fall` | Jetson + camera | Jetson smoke；future 能力若測才產 evidence | 否 |
| `brain.skill_gate` | Jetson + baseline snapshot / replay evidence | Jetson smoke 或 dry-run，依輸入來源 | 若 gate 放行 motion，簽在對應 nav trial |
| `brain.trace` | Jetson / Studio evidence | Jetson smoke 或 dry-run，依輸入來源 | 否 |
| `studio.evidence` | Studio + baseline snapshot | dry-run 或 Jetson smoke，依 snapshot 來源 | 否 |
| `cli.readiness` | WSL + Jetson artifact 讀取 | Jetson smoke | 否 |

## Go2 Motion Sign-Off

`artifacts/baseline/motion_sign_offs.jsonl` 是 append-only JSONL。每一行代表一個 Go2 實體 motion trial 的人工安全簽核，必須符合 `.claude/schemas/motion_sign_off.schema.json`。

簽核規則：

- 誰簽：現場 operator 簽，`operator` 必須是可追溯的人名或帳號。
- 何時簽：每次 Go2 motion trial 結束後、確認安全檢查通過與 video evidence 已保存後簽；失敗或不安全 trial 不拿來當 baseline pass evidence。
- 簽在哪個 commit：`commit_sha` 必須是該 trial 實際部署在 Jetson / Go2 上的 commit。若 commit 變更，舊 sign-off 不得沿用。
- 如何留痕：只 append 新行，不編輯、不刪除舊行；重新測試用新的 `trial_id` 與新的 sign-off 行。
- 必要欄位：`operator`、`timestamp`、`trial_id`、`commit_sha`、`safety_checks_passed`、`video_sha`。

sample 不放在 `artifacts/`，因為 `artifacts/` 被 `.gitignore` 忽略；git-tracked sample 位於 `docs/agents/samples/motion_sign_offs.sample.jsonl`。

## Artifact Layout

`artifacts/baseline/` 是 Jetson / WSL 量測產物目錄，不進 git。Issue #86 只定義 layout 與 schema；實際產出由各 baseline run、#73 preflight、#87 freeze 消費。

| 路徑 | 內容 | schema |
|---|---|---|
| `artifacts/baseline/preflight_result.json` | #73 `demo.yaml` preflight 結果；至少含 `status` | `.claude/schemas/preflight_result.schema.json` |
| `artifacts/baseline/baseline_result.jsonl` | 各能力 scenario-run 原始 JSONL | 由現有 benchmark record schema / observer 定義，本 issue 不新增 |
| `artifacts/baseline/baseline_snapshot.json` | `benchmarks.core.scoreboard.to_snapshot()` 聚合結果；`run_meta` 欄位攤平成 top-level | `.claude/schemas/baseline_snapshot.schema.json` |
| `artifacts/baseline/motion_sign_offs.jsonl` | Go2 motion HITL 簽核 append-only JSONL | `.claude/schemas/motion_sign_off.schema.json` |
| `artifacts/baseline/logs/` | preflight、observer、scoreboard、Jetson smoke logs | N/A |
| `artifacts/baseline/screenshots/` | Studio / Foxglove / terminal evidence 截圖 | N/A |

`baseline_snapshot.json` 的版本綁定使用現有程式輸出的 `wsl_commit`、`jetson_install_sha`、`version_mismatch`、`version_stale`、`run_trusted`、`layer0_preflight_status`。dry-run 可額外帶 `git_commit`，但正式 readiness evidence 應以 `current_run_meta()` 產出的欄位為準。
