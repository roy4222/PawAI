# Capability Baseline & Scoreboard — GitHub Issues 草稿（2026-06-02）

> **draft-only**：本文件為草稿，review 通過才轉 GitHub Issue，現階段不開 issue、不建分支、不動 code。

## 14-child 總表

| # | Title | Type | 6/18? | Blocked by |
|---|---|---|:---:|---|
| #1 | `scoreboard_schema.py`：14 欄 `CapabilityResult` + `CAPABILITY_META`(15 能力含 dependency_role) + `current_run_meta`(雙-sha + layer0→run_trusted) | AFK | ✅ | none |
| #2 | `grader.py`：四段 grade 純函式 (`pass/degraded/fail/insufficient_data`) + `brain_allowed(grade, claim_level)` derive | AFK | ✅ | none |
| #3 | `scoreboard.py` aggregator + `build_scoreboard.py` CLI（Task 3b）：JSONL→snapshot / zero-sample 也列全 15 能力(F1) / preflight fail→全 insufficient_data(F2) / 預設 `--out artifacts/baseline/baseline_snapshot.json` | AFK | ✅ | #1, #2 |
| #4 | `demo.yaml` Layer-0 Preflight gate：填 demo.yaml 的 Layer-0 checks（現為 `checks: []`；以 smoke.yaml 現有 9 checks 為候選來源挑適用 subset + 補 Layer-0 專屬項，不綁固定數字）→ top-level fail-closed gate，產 `preflight_result.json` | HITL | ✅ | none |
| #5 | `perception_baseline_observer.py`：gesture / object（event-only）round 比對邏輯 + 薄 ROS node wrapper | AFK | ✅ | none |
| #6 | `face_baseline_observer.py`：吃 `/state/perception/face` 連續流（recall / unknown-false-accept / wrong-person） | AFK | ✅ | none |
| #7 | voice baseline run：`speech_test_observer`→record(A2) + voice.stop 拆「停」專項(FN=0) + **mic_stop endpoint** | HITL | ✅ | #1, #2, #3, #4 |
| #8 | face baseline run：registered/stranger × 1m/2m，量 recall / false-accept / wrong-person | HITL | ✅ | #1, #2, #3, #4, #6 |
| #9 | gesture (`gesture.wave`) + object (`object.cup`) baseline run：wave recall/idle 誤觸硬 gate + cup recall/idle false-positive | HITL | ✅ | #1, #2, #3, #4, #5 |
| #10 | pose (`pose.basic`) baseline run（studio_only 薄測）；`pose.fall` 不測（future） | HITL | **optional / P2** | #1, #2, #3, #4, #5 |
| #11 | nav baseline run：safe_stop / no_auto_resume (insufficient_data) + short_move (dry-run) + dynamic_avoidance (future) | HITL | ✅ | #1, #2, #3, #4 |
| #12 | `studio.evidence`：provenance label (live/mock/frozen/missing) + Brain trace display + read-only frozen scoreboard chip (`GET /api/scoreboard`) | AFK | ✅ | none |
| #13 | `cli.readiness`：`pawai readiness` / `--json` fail-closed 真值表（sha mismatch 硬擋 / 缺檔→not_ready）+ freeze mechanism | AFK + 1 HITL smoke | ✅ | 實作:#3；freeze:#4+#7/#8/#9/#11；optional:#10 |
| #14 | Brain capability health gate（v0.2）：`compute_effective_status` 加 grade 分支 + IE 第二道 gate + allowlist single source | AFK | **v0.2（不擋 6/18）** | #2, #3, #4 |

> **編號對齊說明**：drafter 內部表的舊編號（observer #4/#6、voice #7、nav 拆 #8/#9/#11 等）已重排為下方連續 #1..#14。Blocked-by 一律指本表編號。

---

## Tracking Issue：Capability Baseline & Scoreboard

**目標（一句）**：量化 15 個 capability（pass / degraded / fail / insufficient_data），產生 frozen snapshot，供 **CLI readiness 與 Studio evidence** 決定 demo 主線；**runtime gate 接入另在 #14 v0.2，不在 6/18 範圍**。讓「沒 baseline 證據的能力不准進 6/18 demo」。

**真相源**：
- Master Plan `docs/archive/pawai-brain-legacy/plans/2026-05-31-capability-baseline-scoreboard-plan.md`（架構 / 三軸 / canonical 15 能力表 / 設計段 C-D）
- Spec `docs/architecture/specs/2026-06-18-capability-baseline-spec.md`（門檻數字）
- Implementation `docs/archive/pawai-brain-legacy/plans/2026-06-01-scoreboard-implementation-plan.md`（6 deliverable TDD）
- Runbook `docs/runbook/2026-06-18-baseline-runbook.md`（上機流程）

**v0.1 成功定義**：不是「Brain 已自動 gate 所有能力」，而是「已有可信 baseline 數據，可決定哪些能力允許進 demo 主線」（Master Plan:22）。

### 依賴關係

- **核心鏈（6/18 主線）**：#1（schema）→ #2（grader）→ #3（aggregator / build_scoreboard）→ 餵所有量測 issue（#7 #8 #9 #11 #12 #13）。
- **observer**：#5（gesture/object）+ #6（face state 流）+ #7（voice）+ #11（nav safety）→ append 同一 `baseline_result.jsonl` → #3 產 `baseline_snapshot.json`。
- **preflight gate**：#4（demo.yaml）是 top-level fail-closed gate（`run_trusted`），#3 / #13 / #14 都依賴它的可信判定。
- **nav 跑序鐵律**：#11 內 short_move 依賴同 issue 的 safe_stop + no_auto_resume 先 pass（或人工 override）才放行真實 motion；未達前只 dry-run（Spec §6c:248-249、Runbook:22-24）。
- **brain.trace 拆兩處**：#12 負責 6/18「trace 看得到、非 mock、有 reason」；#14 負責 v0.2「grade 真的接進 runtime gate」。**#14 不重寫 trace 展示。**
- **post-baseline**：#14 依賴 #2 + #3 + #4（grade / snapshot / run_trusted 都要先有），是 v0.2 deliverable，**不擋 6/18**；6/18 `brain.skill_gate` 維持 insufficient_data 為 acceptable。

### overclaim 防線（鎖定）

- `brain.skill_gate`：grade 接進 gate 前一律 `insufficient_data`，**不可寫「6/18 要做到 gate enforce」**（Spec §7a:288/294）。
- `nav.safe_stop / nav.no_auto_resume / nav.short_move`：baseline pass 前一律 `insufficient_data`，不可寫 pass（Spec §6:202、§6a:219、§6c:249）。
- `nav.short_move`：safety 未 pass 前只 dry-run（Spec §6c:248、Runbook:24）。
- `studio.evidence`：Studio 是 evidence 不是 authority，不可宣稱「IE 第二道 gate 已吃 scoreboard / runtime 全層已 enforce」（Spec §8:350，該 enforcement = #14 v0.2 待補）。

---

## Issue #1：Scoreboard schema — `CapabilityResult` + `CAPABILITY_META` + `current_run_meta`

- **Title**：Scoreboard schema：14-field `CapabilityResult` record + 15-capability `CAPABILITY_META` + dual-sha `current_run_meta`
- **Type**：AFK（純 Python dataclass + dict + pytest，dev 機可跑、無 ROS 依賴；IMPL Task 1 全程在 `benchmarks/` dev-machine TDD，IMPL:21-303）
- **Blocked by**：none（IMPL 建議實作序第一個，IMPL:13）

**What to build**
`benchmarks/core/scoreboard_schema.py`：(1) `CapabilityResult` dataclass，`to_record()` 吐一筆 JSONL record 並打上 `SCHEMA_VERSION`；(2) `CAPABILITY_META` dict — 15 個 canonical capability，每個帶 4 個靜態屬性 `depth / claim_level / risk_role / dependency_role`；(3) `current_run_meta()` — run-level metadata，含 version_snapshot 雙 sha（WSL commit + Jetson install sha）+ Layer-0 preflight → `run_trusted`。

**Acceptance criteria**
- `CapabilityResult.to_record()` 帶 `schema_version == SCHEMA_VERSION`（`SCHEMA_VERSION = "scoreboard-0.1"`），核心欄位齊（`capability_id / scenario_id / run_id / timestamp / git_commit / expected_label / predicted_label / pass_fail / confidence / distance_m / latency_ms`），預設值 `false_trigger is False`、`distance_source == "manual_declared"`、`failure_reason == ""`（IMPL:36-56, :167, :192-221）。
- record 為 14 欄資料 + 識別欄（dataclass 欄位列 IMPL:194-216：識別 5 + 判定 / 觀測欄 + 資源欄 cpu/gpu/ram 可為 None + failure_reason）。
- `CAPABILITY_META` 含全 15 canonical capability，鍵與 MASTER canonical 表逐列一致（MASTER:63-78：face.recognition / voice.command / voice.stop / gesture.wave / object.cup / nav.safe_stop / nav.no_auto_resume / nav.short_move / nav.dynamic_avoidance / pose.basic / pose.fall / brain.skill_gate / brain.trace / studio.evidence / cli.readiness）。
- 每能力 `claim_level ∈ {mainline, studio_only, future, not_claimed}`、`risk_role ∈ {safety_critical, safety_support, actuation, convenience, evidence_only}`、`depth ∈ {deep, thin, future}`、`dependency_role ∈ {trigger, content, safety_guard, actuation, evidence}`（IMPL:59-78；列舉值真相源 IMPL `CAPABILITY_META`:173-189）。
- nav 已拆單一能力：`nav.safe_stop` 與 `nav.short_move` 各自存在，**無** `"nav.short_move + nav.safe_stop"` 複合鍵（IMPL:71-74；MASTER:40）。
- `dependency_role` 與 `risk_role` 正交且對齊 SPEC 逐功能：`nav.safe_stop.dependency_role == "safety_guard"`（SPEC:211）、`gesture.wave.dependency_role == "trigger"`（SPEC:171）、`face.recognition.dependency_role == "content"`（SPEC:37）；voice.command/voice.stop = trigger（SPEC:74, :91）、object.cup = content（SPEC:190）、nav.no_auto_resume = safety_guard（SPEC:211 / MASTER:70）、brain.skill_gate = safety_guard（SPEC:296）、brain.trace/studio.evidence/cli.readiness = evidence（SPEC:314, :341, :369）、pose.basic = content / pose.fall = evidence（SPEC:137, :152）。
- `current_run_meta()` 帶 `run_id`（uuid 非空）+ `jetson_install_sha`（來自 manifest `git_sha_full`）+ `jetson_deploy_ts`（manifest `when`）+ `demo_profile_env` + `version_mismatch`（IMPL:81-94）。
- 無 manifest → `jetson_install_sha is None`、`version_mismatch is True`、`manifest_exists is False`（fail-closed：無法確認 Jetson 跑哪版，IMPL:96-101；MASTER:39, :116）。
- manifest `when` age > `stale_after_h`（預設 6h）→ `version_stale is True`；未逾期 → False（IMPL:103-116；MASTER:31, :101）。
- 帶 `wsl_dirty / branch / manifest_exists`；manifest `dirty:True` → `jetson_dirty is True`（IMPL:119-122）。
- Layer-0 preflight：`status ∈ {pass, pass_with_warnings}` → `layer0_preflight_status` 對應 + `run_trusted is True`；`status == fail` 或未跑（缺）→ `layer0_preflight_status` 為 `fail`/`unknown` 且 `run_trusted is False`（fail-closed，IMPL:125-141；MASTER Layer-0 段:89）。

**Files / modules likely touched**
- NEW `benchmarks/core/scoreboard_schema.py`（IMPL Task 1，code:152-291）
- NEW `benchmarks/test/test_scoreboard_schema.py`（IMPL:30-142；repo 測試目錄 `benchmarks/test/` 已確認 IMPL:15）

**Test / verification**
`python -m pytest benchmarks/test/test_scoreboard_schema.py -q`（先 red：`ModuleNotFoundError`，後全綠 — IMPL:144-147, :293-296）。涵蓋 8 個測試：to_record / CAPABILITY_META enum + nav 拆分 + dependency_role 正交 / dual-sha + run_id / no-manifest fail-closed / stale-by-age / dirty+branch / preflight pass→trusted / preflight fail→untrusted。`_git` 在非 git 環境須降級 `"unknown"` 不爆（MASTER:235）。

**Output artifact**
`benchmarks/core/scoreboard_schema.py`（提供 `CapabilityResult / SCHEMA_VERSION / CAPABILITY_META / current_run_meta`，給 #2 grader 的 claim_level、#3 aggregator 的 `to_snapshot` 遍歷 import）。一筆 `to_record()` = 一行 baseline JSONL；`current_run_meta()` = snapshot 的 run-level header。

**Out of scope**
- 不接 Brain runtime / 不消費 `dependency_role` 做 gate — v0.1 `dependency_role` 是 design-only static 屬性（IMPL:172 末句「v0.1 不被 grader 消費」；MASTER:60）。
- 不做 grade 計算（屬 #2）、不做聚合 / snapshot（屬 #3）。
- 資源欄 `cpu_pct/gpu_pct/ram_mb` v0.1 可留 None，JetsonMonitor 整合屬 runbook 手動填、不在本 issue（IMPL:212；MASTER:239）。
- 不把 `claim_level/risk_role/dependency_role` 寫進每筆 record（是 CAPABILITY_META 靜態屬性，aggregator 才附到 snapshot — MASTER:80）。

---

## Issue #2：Grader — four-tier grade pure function + `brain_allowed` gate derive

- **Title**：Grader：`pass / degraded / fail / insufficient_data` four-tier pure function + `brain_allowed = (pass AND mainline)`
- **Type**：AFK（純函式、無 ROS、dev 機 TDD；IMPL Task 2:307-453）
- **Blocked by**：none（grader 不 import schema；但 #3 aggregator import 它，故 #3 blocked by #2）

**What to build**
`benchmarks/core/grader.py`：(1) `Criterion` dataclass（`metric / pass_min / degraded_min / higher_is_better`）；(2) `grade_one()` 單 metric → pass/degraded/fail；(3) `grade_capability()` 結合「門檻 band」與「樣本充足度」吐四段 grade；(4) `brain_allowed(grade, claim_level)` 純 derive。

**Acceptance criteria**
- 暴露 4 個 grade 常數 `GRADE_PASS="pass" / GRADE_DEGRADED="degraded" / GRADE_FAIL="fail" / GRADE_INSUFFICIENT="insufficient_data"`（IMPL:389-392）。
- `sample_count <= 0` → `insufficient_data`（IMPL:328-329, :424-425）。
- `criteria` 為空 → `insufficient_data`（fail-closed，防 fail-open；缺判據絕不可 pass — IMPL:332-334, :426-427；SPEC 對齊 fail-closed 結構鎖:26）。
- 所有 metric 達 pass band 但 `sample_count < confirm_min`（預設 3）→ `degraded`（provisional / 標黃 — IMPL:337-338, :433-434；MASTER provisional≥1 標黃 vs confirmed≥3:51）。
- 所有 metric 達 pass band 且 `sample_count >= confirm_min` → `pass`（IMPL:341-342, :435）。
- 任一 metric fail → `fail`（fail-closed：fail 蓋過一切 — IMPL:345-347, :429-430）。
- `higher_is_better=False` 的 lower-is-better band 正確（誤觸率 / latency：≤pass_min→pass、≤degraded_min→degraded、否則 fail — IMPL:350-352, :413-418）；對齊 SPEC 不對稱門檻語意（face `unknown_false_accept_rate` ≤3%/3-10%/>10% SPEC:41, :52；gesture idle 誤觸硬 gate SPEC:175；object idle false-positive SPEC:194）。
- degraded band 蓋過 unconfirmed：metric 落在 degraded band 即使樣本足 → `degraded`（IMPL:355-356, :431-432）。
- `grade_one(None, crit)` → `fail`（None 視為保守 fail — IMPL:404-405）。
- `brain_allowed(grade, claim_level)` 僅 `grade == pass AND claim_level == "mainline"` 為 True；`pass + future`、`pass + studio_only`、`degraded + mainline`、`fail + mainline`、`insufficient_data + mainline` 全 False（claim_level 只能更嚴、不放寬 — IMPL:359-366, :438-440；SayCan affordance-gating 語意 SPEC:286；MASTER:38, :198-199）。

**Files / modules likely touched**
- NEW `benchmarks/core/grader.py`（IMPL Task 2 code:377-440）
- NEW `benchmarks/test/test_grader.py`（IMPL:318-367）
- 範式對齊（讀，不改）：`speech_processor/speech_processor/speech_test_observer.py` 的 `_compute_grade`（PASS/MARGINAL/FAIL，IMPL:380-382）

**Test / verification**
`python -m pytest benchmarks/test/test_grader.py -q`（先 red `ModuleNotFoundError`、後 8 測試全綠 — IMPL:369-372, :443-446）：zero-sample / empty-criteria / pass-but-unconfirmed→degraded / pass-confirmed→pass / any-fail→fail / lower-is-better band / degraded-dominates-unconfirmed / brain_allowed only-pass-and-mainline。

**Output artifact**
`benchmarks/core/grader.py`（提供 `Criterion / grade_capability / brain_allowed / GRADE_* 常數`，給 #3 aggregator import — IMPL:617）。

**Out of scope**
- 不定義各能力的門檻數字 — pass_min/degraded_min 一律由 Capability Baseline Spec 取（provisional until baseline；IMPL:17「門檻數字不在本檔」；SPEC:22, :26 真相源）。執行預設門檻 `DEFAULT_CRITERIA` 屬 #3 的 build_scoreboard，不在本 issue。
- 不讀 JSONL、不分組、不算 success_rate/percentile（屬 #3 aggregator）。
- 不接 Brain runtime gate — `brain_allowed` v0.1 只是 derive 函式，`compute_effective_status()` 接 grade 是 v0.2（MASTER 設計段 D:165-200；SPEC §7a:284, :303 brain.skill_gate grade 未接前一律 insufficient_data，不可寫「6/18 gate enforce」）。

---

## Issue #3：Scoreboard aggregator + `build_scoreboard` CLI

- **Title**：Scoreboard aggregator (`scoreboard.py` + Task 3b `build_scoreboard.py` CLI)：JSONL → 15-capability snapshot, scenario-kind aware, fail-closed
- **Type**：AFK（純 Python 聚合 + argparse CLI，dev 機 TDD（`tmp_path` fixture），無 ROS；IMPL Task 3:457-768 + Task 3b:772-922）
- **Blocked by**：#1（import `CAPABILITY_META` / `current_run_meta`，IMPL:618, :848）、#2（import `grade_capability / brain_allowed / Criterion / GRADE_INSUFFICIENT`，IMPL:617, :846）

**What to build**
(1) `benchmarks/core/scoreboard.py`：`aggregate()` 讀 record list → 按 `(capability_id, scenario_kind)` 分離算指標 → `CapabilityScore`；`to_snapshot()` 遍歷 `CAPABILITY_META` 全 15 鍵附 claim_level/risk_role/depth/dependency_role + derive brain_allowed；`load_results` / `write_snapshot`。(2) `benchmarks/core/build_scoreboard.py`（Task 3b 薄殼）：runbook step4 唯一 CLI，`baseline_result.jsonl` + `--manifest` + `--preflight` → `current_run_meta` → `aggregate` → `write_snapshot`，含 `DEFAULT_CRITERIA`。

**Acceptance criteria**

*aggregator（`scoreboard.py`）*
- `aggregate()` 算 `sample_count / success_rate / false_trigger_rate / latency_p50 / latency_p90 / confirmed`，false_trigger 強制 fail（IMPL:485-499）。
- **scenario_kind 分離**（Roy lock + SPEC face 不對稱量法）：按 `scenario_kind` 分組吐 `positive_count / idle_count / registered_recall（positive round pass 率）/ unknown_false_accept_rate（idle round false_trigger 率）/ wrong_person_count（positive round 卻 false_trigger）`，known/unknown 不混算稀釋（IMPL:502-527, :631-637, :683-706；SPEC face Criterion 映射:47-55、object 計算規則:193-194）。
- **(LOCK 1) JSONL → snapshot**：`build_scoreboard` 讀 `baseline_result.jsonl` → `aggregate` → `write_snapshot` 產 JSON（IMPL:802-807；RUNBOOK step4:27）。
- **(LOCK 2) zero-sample 也列出全 15 能力**：`to_snapshot` 遍歷 `CAPABILITY_META` 全鍵（非 scores），未測能力補 `grade="insufficient_data" / sample_count=0 / success_rate=None（非 0.0）/ brain_allowed=False`，且仍帶靜態屬性（`dependency_role` 等）；snapshot 永遠 15 列（IMPL F1:555-568, :710-721, :726-728, :735-739）。
- snapshot 每能力附 `claim_level / risk_role / depth / dependency_role` + derived `brain_allowed`；`gesture.wave → brain_allowed True`(pass+mainline)、`nav.dynamic_avoidance` 即使量到 pass 因 claim_level=future → `brain_allowed False`（IMPL:529-552, :744-748）。
- **(LOCK 3) preflight fail → 全 insufficient_data**：`run_meta.run_trusted == False`（含 caller 漏帶 → 預設 fail-closed）→ 覆寫全 15 能力 `grade="insufficient_data"` + `brain_allowed=False` + `failure_reason="layer0_preflight={status}"`，但保留 raw metrics 可 debug（IMPL F2:571-593, :731-743；MASTER Layer-0:89, :182；RUNBOOK:37）。

*build_scoreboard CLI（Task 3b）*
- **(LOCK 4) 預設 `--out artifacts/baseline/baseline_snapshot.json`**（IMPL:881, :898；SPEC §9 working snapshot 路徑:415；RUNBOOK:27, :35）。
- `--preflight` pass → `run_trusted True`、snapshot 15 列、已測能力維持原 grade（IMPL:795-807）。
- `--preflight` 缺 / 非 pass → `run_trusted False` → 全 grade insufficient_data（fail-closed，對齊 to_snapshot F2 — IMPL:810-820；SPEC §9 fail-closed 規則:392-401；RUNBOOK「必須帶 `--preflight`」:27）。
- `DEFAULT_CRITERIA` 用 SPEC provisional 門檻：face（registered_recall 0.80/0.60、unknown_false_accept_rate 0.03/0.10、wrong_person_count 0/0 — SPEC:48-53）、voice.command（success_rate 0.80/0.70 — SPEC:78）、gesture.wave（success_rate 0.90/0.80 — SPEC:175）、object.cup（SPEC:194）；門檻真相源在 Spec、CLI 只是執行預設（IMPL:850-868）。
- CLI 可由 `python -m benchmarks.core.build_scoreboard RESULT.jsonl [--manifest] [--preflight] [--criteria] [--out]` 跑（IMPL:834-836, :892-905）。

**Files / modules likely touched**
- NEW `benchmarks/core/scoreboard.py`（IMPL Task 3 code:604-755）
- NEW `benchmarks/test/test_scoreboard.py`（IMPL:468-594）
- NEW `benchmarks/core/build_scoreboard.py`（IMPL Task 3b code:831-909）
- NEW `benchmarks/test/test_build_scoreboard.py`（IMPL:784-820）
- import 依賴：`benchmarks/core/scoreboard_schema.py`(#1)、`benchmarks/core/grader.py`(#2)

**Test / verification**
`python -m pytest benchmarks/test/test_scoreboard.py benchmarks/test/test_build_scoreboard.py -q`（先 red、後全綠 — IMPL:596-599, :758-761, :823-825, :912-915）。scoreboard.py 涵蓋 11 測試：success_rate+grade / false_trigger→fail / recall-vs-false-accept 分離 / wrong_person on positive / claim_level+brain_allowed / future-not-allowed / always-15 / missing-run_trusted-failclosed / preflight-fail-all-insufficient。build_scoreboard 涵蓋 2 測試（`tmp_path`）：preflight pass→snapshot(15 列)、missing preflight→failclosed。

**Output artifact**
`benchmarks/core/scoreboard.py`（`aggregate / to_snapshot / write_snapshot / load_results`）+ `benchmarks/core/build_scoreboard.py`（CLI + `DEFAULT_CRITERIA`）。執行產出 = `artifacts/baseline/baseline_snapshot.json`（15 能力 grade + brain_allowed + 靜態屬性 + run_meta header；給 §8 `/api/scoreboard`、§9 `pawai readiness` 唯讀 — SPEC:415-421）。

**Out of scope**
- 不接 Brain runtime / 不接 `effective_status.py` — aggregator 只產 snapshot 供人判讀，capability_health 接 runtime gate 是 v0.2（IMPL:463 末句「不接 Brain runtime（v0.2）」；MASTER 設計段 D:165-200、scope:47）。
- 不寫 `pawai readiness` 子命令 / freeze 機制 / `PAWAI_SCOREBOARD_PATH` env / `/api/scoreboard` endpoint（屬 #13 cli.readiness 與 #12 studio.evidence；SPEC §9:425、§8:357）。
- 不產 ROS observer 記錄（gesture/object → #5 perception observer；face → #6 face observer；IMPL Task 4:926、Task 4b）。
- overclaim 防線：nav.safe_stop / nav.no_auto_resume / nav.short_move 在 baseline pass 前由 aggregator 吐 insufficient_data（recorder BD-7 no-op、BD-8 行為衝突、3 blocker），不可在 snapshot 顯示為 pass（SPEC:212, :219, :234, :249；MASTER:69-71, :213）；brain.skill_gate 在 grade 接進 gate 前一律 insufficient_data，不寫「6/18 gate enforce」（SPEC:288, :294；MASTER:83）。

---

## Issue #4：Layer-0 Preflight gate — 填 `demo.yaml` profile，fail-closed → all insufficient_data，產 `preflight_result.json`

- **Title**：Layer-0 Preflight gate（填 `jetson-verify` demo.yaml profile，fail-closed → 全能力 insufficient_data，產 preflight_result.json）
- **Type**：HITL — preflight 的本質是上機驗 demo stack / Jetson / Go2 是否就緒（`jetson.ssh_reachable` / `go2.ethernet_ping` / `ros.runtime_started` / `demo.entrypoint_started` 全要真實 Jetson + demo session 才能判，MASTER:92-101）。profile 是 YAML，但驗收要在 Jetson 上跑出 pass / fail 結果。
- **Blocked by**：none（profile 與 manifest 讀取自成一體；snapshot 端的 fail-closed 消費在 #1/#3 已實作，本 issue 只負責「產出 preflight_result + 餵 build_scoreboard」）

**What to build**
把 `jetson-verify` 目前 stub 的 `demo.yaml` profile（`checks: []` → `verify.py sys.exit(2)`，MASTER:90）填成 Layer-0 Preflight checks（對齊 MASTER:92-101 表）：**以 `smoke.yaml` 現有 9 checks 為候選來源挑適用 subset + 補 Layer-0 專屬項**（node-count gate / go2 webrtc subscriber / version_snapshot 讀 `.pawai-last-deploy`），**不以固定數字綁死**；跑完輸出 `artifacts/baseline/preflight_result.json`（至少含 `{"status": ...}`），作為 RUNBOOK step 0 的前置 gate。

**Acceptance criteria**
- profile canonical 路徑 = `.claude/skills/jetson-verify/profiles/demo.yaml`（git-tracked；`.agents/` 是未追蹤舊鏡像，F4，MASTER:143）。
- 8 項 check 對齊 MASTER:92-101 表：`jetson.ssh_reachable`(hard-blocker 全域) / `go2.ethernet_ping` / `ros.runtime_started`(lane-aware node set，MASTER:103-112) / `demo.entrypoint_started`(走 demo script，非裸 `ros2 run`，Q3 鐵律 RUNBOOK:8) / `go2.driver_alive`(capability-conditional) / `topic_contract_ok` / `resource_idle_snapshot`(RAM headroom ≥0.8GB & temp<70°C) / `version_snapshot`（MASTER:101）。
- 三級判定：全 hard-blocker pass → `status="pass"`；off-path WARN（如 `/state/executive/brain` planned、`/executive/status` legacy）→ `status="pass_with_warnings"` = GO（MASTER:114）；任一 hard-blocker fail → `status="fail"`。
- **fail-closed 串接（核心）**：preflight fail / 缺結果 → `run_trusted=False` → snapshot 全 15 能力 grade 覆寫 `insufficient_data`（MASTER:89, RUNBOOK:14, RUNBOOK:27, RUNBOOK:37）。此行為由 `current_run_meta(layer0_preflight=...)`（IMPL:271-272, :287-288）+ `to_snapshot` F2（IMPL:740-743）消費，本 issue 只需保證輸出的 `preflight_result.json` 能被 `build_scoreboard --preflight` 正確讀成 `run_trusted`（IMPL:818-820 `test_build_scoreboard_missing_preflight_is_failclosed`）。
- `version_snapshot` 讀 `.pawai-last-deploy`（`status.py:11`）：無 manifest → `version_mismatch=True`（fail 才 block）；manifest age>6h → `version_stale=True`（標註不 block，MASTER:101, IMPL:103-116）。

**Files / modules likely touched**
- `.claude/skills/jetson-verify/profiles/demo.yaml` — 目前 stub（`checks: []`），填 8 check（MASTER:143 canonical 路徑；MASTER:90 現況 stub）。
- `.claude/skills/jetson-verify/profiles/smoke.yaml` — 候選來源（現有 **9 checks**，挑 demo preflight 適用 subset 參考；MASTER:32, :90）。**讀取 / 參考，不改**。
- `verify.py`（jetson-verify runner）— 需確認能輸出結果 dict 落地成 `artifacts/baseline/preflight_result.json`；若 runner 無寫檔能力則 NEW 薄 wrapper（預定 `benchmarks/scripts/run_preflight.py`，呼叫 verify runner → dump json）。
- 消費端（**不在本 issue 改，僅對齊**）：`benchmarks/core/scoreboard_schema.py` `current_run_meta`（IMPL:247-290）、`benchmarks/core/build_scoreboard.py`（IMPL:878-889）。

**Test / verification**
- Jetson smoke：起 demo entrypoint（`start_full_demo_tmux.sh` / lane 腳本）→ 跑 demo.yaml → 確認 `preflight_result.json` 產出且 `status` 正確。
- 反向驗證（fail-closed）：故意不起 demo session / 斷 Go2 ethernet → preflight `status="fail"` → `build_scoreboard --preflight <fail>.json` → snapshot 全 15 能力 `insufficient_data`（對齊 IMPL:580-593 `test_layer0_preflight_fail_forces_all_insufficient`，但以真實 preflight 輸出驅動）。
- 缺檔驗證：`build_scoreboard` 不帶 `--preflight` → `run_trusted=False` → 全 insufficient（IMPL:810-820 已有單測，本 issue 確認真實 `preflight_result.json` 路徑被 RUNBOOK step4 `--preflight artifacts/baseline/preflight_result.json` 帶上，RUNBOOK:27）。

**Output artifact**
`artifacts/baseline/preflight_result.json`（含 `status` ∈ {pass, pass_with_warnings, fail} + `version_snapshot` 欄位）；填好的 `.claude/skills/jetson-verify/profiles/demo.yaml`。

**Out of scope**
- **不自寫 check runner** — 複用 `jetson-verify` YAML-driven runner（MASTER:37, :90）。
- 不接 Brain runtime gate、不做 Studio health panel、不換模型（v0.2/v0.3，MASTER:47-49）。
- Known Findings 的 contract 2 WARN 清理、cli CI 缺口、demo-preflight skill 指向不存在的 `scripts/preflight.py` 等一律「baseline fail 後才開修」，不在本 issue 修（MASTER:215-217）。
- 不在本 issue 改 snapshot fail-closed 邏輯本身（已由 #1/#3 的 `current_run_meta` + `to_snapshot` F2 實作）。

---

## Issue #5：Perception baseline observer — `gesture.wave` / `object.cup`，event-only，scenario_kind 分流

- **Title**：Perception baseline observer（`perception_baseline_observer.py`，gesture/object event-only，每 round 標 scenario_kind）
- **Type**：AFK（純比對邏輯 `evaluate_round` / `count_false_triggers` dev 機 TDD，無 ROS 依賴，IMPL:933, :1004）。注意：ROS node wrapper 真正上機量測屬 RUNBOOK step 3，但 wrapper 本身保持薄、不在 CI（IMPL:1086-1093）；本 issue 的可驗收 deliverable = 純函式 + 單測。
- **Blocked by**：none（純函式產 record dict，aggregator/schema 端 key 已由 #1/#2/#3 定義；本 issue 只需對齊欄位）

**What to build**
新 `benchmarks/core/perception_baseline_observer.py`：純比對邏輯把 operator 宣告的 `RoundMeta`（capability/scenario/expected_label/distance/window_start）與該 round 觀測到的 `(label, confidence, ts)` 比對，產一筆 CapabilityResult-shaped dict；idle round（expected ∈ {none,idle,""}）任何觀測 = false_trigger，positive round 命中 expected → pass(latency=首中相對 window_start)、否則 miss(fail，非 false_trigger)。**只負責 gesture / object（event-only）；face 不在此**（F3，face 走 #6，IMPL:934-935）。

**Acceptance criteria**
- `evaluate_round` 五種行為正確（IMPL:946-997 六個單測）：idle 無觀測 → pass/non-FT；idle 有觀測 → fail/FT；positive 命中 → pass + latency_ms（`(ts-window_start)*1000`）+ distance_m；positive 無觀測 → miss(fail, 非 FT)；positive 認錯類別（如 cup round 看到 bottle）→ miss(fail, 非 FT，SPEC §5:193「wrong class → 傷 cup_recall 不算 false-positive」）。
- 每筆 record 帶 `scenario_kind`（idle / positive，IMPL:1070），供 aggregator 分離算 recall vs false-accept（不混算，IMPL:660-661, MASTER §F2）。
- `count_false_triggers` 數 idle round 誤觸數（IMPL:989-996）。
- record 欄位為 `CapabilityResult` 子集且與 aggregator 讀的 key 對齊：`capability_id/scenario_id/scenario_kind/expected_label/predicted_label/pass_fail/false_trigger/confidence/latency_ms/distance_m/distance_source`（IMPL:1066-1079）。
- `distance_source` 對 gesture/object = `"manual_declared"`（人工宣告，非 D435 深度，MASTER:51, SPEC §1:40 對照 face 才是 d435_depth）。
- 對齊 SPEC 門檻語意（門檻數字在 spec / DEFAULT_CRITERIA，本 observer 只產 raw record）：gesture idle false_trigger 是硬 gate（SPEC §4:175 ≤1/10min=pass）；object idle round = 1 個 60s 窗生一筆 record，`false_trigger`=窗內有無誤報 cup（SPEC §5:194）。

**Files / modules likely touched**
- `benchmarks/core/perception_baseline_observer.py` — **NEW**（IMPL:929，預定路徑已定）。
- `benchmarks/test/test_perception_baseline_observer.py` — **NEW**（IMPL:930, :940-997 測試已寫好可照抄）。
- ROS node wrapper（**保持薄、不在 CI、Jetson 跑**）：訂 `/event/gesture_detected` + `/event/object_detected`，正規化 `/event/gesture_detected → (gesture, confidence, stamp)`、`/event/object_detected → 每 objects[]: (class_name, confidence, stamp)`（IMPL:935, :1086-1093）。event schema 接地：`object_perception_node.py:365,416`（SPEC §5:198）、wave confidence hardcode 1.0（`vision_perception_node.py:414`，SPEC §4:172）。

**Test / verification**
- dev 機 pytest：`python -m pytest benchmarks/test/test_perception_baseline_observer.py -q` → 6 測試全綠（IMPL:1098-1099），再 `python -m pytest benchmarks/test -q` 全綠（IMPL:1103）。
- 上機（RUNBOOK step 3，HITL，非本 issue 的 CI 驗收）：起感知 lane demo entrypoint，**object 必須先起 `object_perception`**（現無 consumer 訂 `/event/object_detected`，SPEC §5:191, RUNBOOK:20）、**gesture 必走 recognizer backend**（demo 真實 backend，非壓測 mediapipe，SPEC §4:172, RUNBOOK:20），operator 宣告 round_meta + 人工 ground-truth → JSONL。

**Output artifact**
`benchmarks/core/perception_baseline_observer.py`；逐 round append 進共用 `baseline_result.jsonl`（face/gesture/object/voice/nav 共用同檔，RUNBOOK:34）。

**Out of scope**
- **不跑 face**（event-only 量不出 unknown-false-accept / 多臉 / 距離，face 拆 #6 `face_baseline_observer` 吃 state 流，F3，IMPL:934, SPEC §1:38）。
- 不改任何感知 node、不修辨識、不接 Brain（IMPL:933）。
- 不主張 static gesture（ok/thumbs/palm 全不主張，只 wave；SPEC §4:168）、不主張 object.bottle/wallet/key/`object.general`/VLM（全 future，SPEC §5:187）。
- 不改 object whitelist、不修 gesture score-floor、不調 WaveDetector 超參 — 這些是「baseline fail 後才開修」的 Known Findings（MASTER:210-211, SPEC §4:177, §5:196）。
- ROS node wrapper 不進 CI、不做厚邏輯（保持薄，IMPL:1086, MASTER:233）。

---

## Issue #6：Face baseline observer — `/state/perception/face` 連續流，unknown-false-accept aware

- **Title**：Face baseline observer（`face_baseline_observer.py`，吃 `/state/perception/face` 連續狀態流，量得出 unknown-false-accept）
- **Type**：AFK（純邏輯 `evaluate_face_round` dev 機 TDD，無 ROS 依賴，IMPL:1205）。ROS node wrapper 上機量測屬 RUNBOOK step 3、保持薄不在 CI（IMPL:1296-1302）；本 issue 可驗收 deliverable = 純函式 + 單測。
- **Blocked by**：none（與 #5 並行；獨立檔，aggregator/schema key 已由 #1/#3 定義）

**What to build**
新 `benchmarks/core/face_baseline_observer.py`：純邏輯把 `FaceRoundMeta`（expected=註冊者名 / "unknown"(idle) / distance / window）與 window 內累積的 `FaceStateSnapshot(ts, tracks)`（每 tick 全 tracks）比對，產一筆 CapabilityResult-shaped dict。**face 必須吃 `/state/perception/face` 連續流，不可用 #5 的 event observer** — 因 `/event/face_identity` 只在 stable transition 發、**從不發 unknown**（`face_identity_node.py:561`），event-only 量不出 unknown-false-accept / 多臉 / 距離分桶（F3，IMPL:1119, SPEC §1:38, :59）。

**Acceptance criteria**
- `evaluate_face_round` 五種行為正確（IMPL:1134-1189 五個單測）：idle round 出現被穩定辨識成註冊者的 track → fail/FT（誤把陌生人叫成註冊者）；idle 全 unknown track → pass/non-FT；positive 命中 expected 名 → pass + confidence(=track sim) + distance(=track 真實深度) + `distance_source="d435_depth"`；positive 只 unknown/無 track → miss(fail，非 FT)；positive 卻穩定辨識成別的註冊者 → fail/FT（認錯人，比漏認嚴重，SPEC §1:52 硬規則）。
- 每筆 record 帶 `scenario_kind`（idle=expected ∈ {unknown,none,idle,""} / positive，IMPL:1283），供 aggregator 算 `registered_recall`(positive pass 率) / `unknown_false_accept_rate`(idle FT 率) / `wrong_person_count`(positive 卻 FT)（SPEC §1:55, IMPL:688-690）。
- `distance_source` = `"d435_depth"` when track 帶真實深度（face state 帶 D435 深度，≠ gesture/object 的人工宣告，IMPL:1167, :1291-1292, SPEC §1:40）。
- record 欄位與 aggregator/schema key 對齊：`capability_id/scenario_id/scenario_kind/expected_label/predicted_label/pass_fail/false_trigger/confidence/latency_ms/distance_m/distance_source`（IMPL:1279-1293）。
- 對齊 SPEC 門檻（門檻數字在 spec / DEFAULT_CRITERIA，本 observer 只產 raw record）：`registered_recall` ≥80%/60-80%/<60%、`unknown_false_accept_rate` ≤3%/3-10%/>10%、`wrong_person_count`≥1 且小樣本 → 不得 pass（SPEC §1:41, :50-53）。

**Files / modules likely touched**
- `benchmarks/core/face_baseline_observer.py` — **NEW**（IMPL:1116，預定路徑已定）。
- `benchmarks/test/test_face_baseline_observer.py` — **NEW**（IMPL:1117, :1124-1189 測試已寫好可照抄）。
- ROS node wrapper（**保持薄、不在 CI、Jetson 跑**）：訂 `/state/perception/face`（連續 ~20Hz），parse JSON → `FaceStateSnapshot(ts, tracks)`，依 round window 累積 → `evaluate_face_round`（IMPL:1296-1302）。state schema 接地：`face_identity_node.py:634-641`（含 track_id/stable_name/sim/distance_m/bbox/mode/face_count，SPEC §1:59）。

**Test / verification**
- dev 機 pytest：`python -m pytest benchmarks/test/test_face_baseline_observer.py -q` → 5 測試全綠（IMPL:1307-1308）。
- 上機（RUNBOOK step 3，HITL，非本 issue 的 CI 驗收）：跑 `face_baseline_observer` 吃 `/state/perception/face`，operator 宣告 `FaceRoundMeta`（expected 註冊者名 / "unknown"(idle) / distance / window，每 round 標 scenario_kind）→ JSONL。scenario 距離 1m/2m（3m optional、drop 0.5m）、註冊者 1-2 人 + 陌生人 2-3 人（SPEC §1:39, RUNBOOK:21）。**勿用 `perception_baseline_observer` 跑 face**（RUNBOOK:21）。

**Output artifact**
`benchmarks/core/face_baseline_observer.py`；逐 round append 進共用 `baseline_result.jsonl`（與 gesture/object 同一檔，IMPL:1301, RUNBOOK:34）。

**Out of scope**
- 不改 `face_identity_node`、不修辨識、不接 Brain（IMPL:1302）。
- 不調 `sim_threshold`(現 0.40)、不重 enroll face_db、不換 YuNet/SFace — 這些是「`unknown_false_accept_rate` fail 才考慮」的 v0.3 修法，不在本 issue（SPEC §1:43, MASTER:206-208）。
- 不主張守護 / 陌生人警報（North Star §5 禁止；陌生人=泛稱不點名不警報，SPEC §1:45）。
- 不做 Studio evidence chip 展示（屬 #12 studio.evidence，SPEC §1:57）。
- ROS node wrapper 不進 CI、保持薄（IMPL:1296, MASTER:233）。

---

## Issue #7：Voice baseline run — voice.command + voice.stop + mic_stop endpoint（HITL）

- **Title**：Voice baseline run — voice.command + voice.stop on Jetson, with mic_stop manual-boundary endpoint
- **Type**：HITL（上機跑 baseline 需人在 Jetson 對麥克風講固定指令 /「停」並錄 round；mic_stop endpoint 的 code 部分為 AFK 前置，但量測本身 HITL）
- **Blocked by**：#1 schema、#2 grader、#3 build_scoreboard（aggregator 薄殼）、#4 preflight（run_trusted）— baseline JSONL→**可信** snapshot 需這四者就位才能判讀 trusted grade；mic_stop endpoint code 本身無 issue 依賴

**What to build**
1. 接 `mic_stop` 訊號流（demo-blocking 前置）：Studio `use-audio-recorder.ts` stopRecording → WebSocket `mic_stop` event → 發 `/event/mic_boundary`；`stt_intent_node` 訂閱後立即 finalize + 解 echo gate（SPEC §2:108）。
2. 把現成 `speech_test_observer` 的 CSV 結果轉成 baseline record（A2：補 `capability_id=voice.command` / `voice.stop`）寫進共用 `baseline_result.jsonl`。
3. 上機走 demo entrypoint 跑 voice.command（6-8 固定指令各 ≥3 輪）+ voice.stop（「停」專項 N 輪含噪音）。

**Acceptance criteria**
- voice.command：fixed `accuracy ≥80% pass / 70-80% degraded / <70% fail`（SPEC:78；對齊 `speech_test_observer.py:247` `fixed_accuracy_ge_80pct`）；`e2e_median ≤3.5s`（SPEC:78；`speech_test_observer.py:248`）；`play_ok ≥80%`（SPEC:78；`speech_test_observer.py:250`）；**TTS TTFA p90 ≤2s / 2-4s degraded / >4s fail**（SPEC:78）。ASR/intent/TTS 為 sub-metric，任一 fail 則 row fail（SPEC:77）。
- voice.stop：**FN（漏聽）硬性 = 0**，任一漏聽 = fail，不平均（SPEC:95）。含噪音段（SPEC:93）。
- mic_stop endpoint：baseline 走 **manual mic boundary**（`energy_vad.enabled=False`），latency **雙記錄** — 新 `e2e_latency_ms` 從 `mic_stop_ts` 起算、舊 `speech_start_ts` 欄位保留改名對照，報告標「metric v2（mic_stop 起算）」（SPEC:108-109；RUNBOOK:19）。echo gate 在 manual mic_stop 時立即解（SPEC:110）。
- 沒接 mic_stop 訊號流就量不到 manual mic boundary，latency 仍是 VAD 舊世界 → 此項為 demo-blocking 前置，必須先驗 `/event/mic_boundary` 通（SPEC:108；RUNBOOK:19）。
- aggregator 預設門檻一致：`voice.command` criteria = `Criterion("success_rate", 0.80, 0.70, higher_is_better=True)`（IMPL:857-859）。
- 每 round 走 demo entrypoint，不裸 `ros2 run`（拿錯 mic_gain/whisper device）（RUNBOOK 鐵律:8）。

**Files / modules likely touched**
- `pawai-studio/frontend/hooks/use-audio-recorder.ts`（existing；加 stopRecording → WS `mic_stop` event，SPEC:108）
- `speech_processor/speech_processor/stt_intent_node.py`（existing；訂閱 `/event/mic_boundary` → finalize + 解 echo gate，~10-15 行 SPEC:108）
- `speech_processor/speech_processor/speech_test_observer.py`（existing；A2 record 轉換，現 PASS_CRITERIA:246-250 + CSV_FIELDS:238-242 在，但**無 `capability_id`/`to_record`/jsonl 輸出** → 需補）
- `benchmarks/core/scoreboard_schema.py`（NEW，Task 1；record schema voice 用）
- Studio gateway WS handler（existing path；`mic_stop` event 路由，SPEC:108）
- `scripts/run_speech_test.sh`（existing；baseline orchestration 入口，RUNBOOK:19）
- baseline JSONL：`baseline_result.jsonl`（NEW；voice/face/gesture/object/nav 共用，RUNBOOK:34）
- code 接地：`safety_gate.py:11` `SAFETY_KEYWORDS=("停","stop","暫停","煞車","緊急")` → `:23` `stop_move`（現成 fast path 雛形，SPEC:100）；`intent_classifier.py:16` SUPPORTED_INTENTS（SPEC:82）

**Test / verification**
- mic_stop 訊號流：`ros2 topic echo /event/mic_boundary`（按 Studio stop 後應收到 event）；確認 `stt_intent_node` 立即 finalize（不等 VAD timeout）。
- baseline 量測：`bash scripts/run_speech_test.sh --skip-driver --skip-build` → `speech_test_observer` CSV → A2 轉 JSONL（每筆帶 `capability_id`）。
- snapshot 判讀：`build_scoreboard.py baseline_result.jsonl --preflight ...` → voice.command/voice.stop grade（IMPL Task 3b:878-889）。
- voice.stop FN 驗證：N 輪「停」全命中（grep JSONL `voice.stop` 無 miss round）。
- pytest（mic_stop finalize 邏輯若拆純函式可加單測）。

**Output artifact**
- `/event/mic_boundary` topic（新訊號流）
- `speech_test_*.csv`（observer 原輸出，含 `mic_stop_ts` + 舊 `speech_start_ts` 雙欄位）
- `baseline_result.jsonl` 中 `capability_id=voice.command` / `voice.stop` 的 round records
- snapshot 內 voice.command + voice.stop 的 grade + brain_allowed

**Out of scope**
- **fast_router / System1-System2 fast path 不做**（另線 Voice Latency Improvement，go/no-go = baseline fail，SPEC:112-115）。
- Piper fast TTS cache / canned first-feedback / LLM-VLM slow path orchestration（另線，SPEC:114）。
- diffusion action model = 明確 future（SPEC:116）。
- voice.stop **不主張為安全機制**，是互動便利（operator_abort）；motion 安全由 reactive_stop + 物理 e-stop 保證，**不在任何 skill 安全依賴鏈**（SPEC:88,99-100；MASTER:66）。
- 換 ElevenLabs（TTS）只在 TTFA fail >4s **且** edge_tts fallback 也 fail 才談，本 issue 不評估換模型（SPEC:80）。
- 報告不可寫「快了 2 秒」— metric v2 是量法變非系統變快（SPEC:109）。

---

## Issue #8：Face baseline run — registered/stranger × 1m/2m（HITL）

- **Title**：Face baseline run — registered vs stranger at 1m/2m, measure recall / false-accept / wrong-person on Jetson
- **Type**：HITL（需人在 Jetson 前以註冊者 / 陌生人在 1m/2m 站位走 round，operator 宣告 FaceRoundMeta）
- **Blocked by**：#6（`face_baseline_observer` Task 4b，吃 `/state/perception/face` 連續流；目前 `benchmarks/core/face_baseline_observer.py` 不存在 = NEW）；判讀可信 snapshot 另需 #1 schema、#2 grader、#3 build_scoreboard、#4 preflight（run_trusted）

**What to build**
上機跑 face baseline：註冊者 1-2 人 + 陌生人 2-3 人 × 距離 1m / 2m，用 `face_baseline_observer`（Task 4b）吃 `/state/perception/face` 連續流，operator 每 round 宣告 `FaceRoundMeta`（expected 註冊者名 / "unknown"(idle) / distance / window）並標 `scenario_kind`（positive / idle），逐 round append `baseline_result.jsonl`。

**Acceptance criteria**
- 量三個指標：`registered_recall` ≥80% pass / 60-80% degraded / <60% fail；`unknown_false_accept_rate` ≤3% pass / 3-10% degraded / >10% fail（SPEC:41，**不對稱門檻**）。
- **硬規則：`wrong_person_count` ≥1（小樣本）→ 不得 pass，只能 degraded/fail**（SPEC:41,52）；認錯人 / 把陌生人叫成註冊者皆計 false_accept（SPEC:41）。criteria 對齊 `Criterion("wrong_person_count", pass_min=0, degraded_min=0, higher_is_better=False)`（SPEC:52；IMPL build_scoreboard:855）。
- 每 round 須標 `scenario_kind`（positive=已知人出場 / idle=只陌生人或無人）（SPEC:55；observer record key `scenario_kind` IMPL:1283）。
- 距離分桶 1m / 2m（3m optional stress、drop 0.5m）；多人同框只驗「會不會把 unknown 叫成註冊者」（SPEC:39）。
- 必走 `face_baseline_observer`（state 流），**勿用 `perception_baseline_observer`**（event-only 量不出 unknown-false-accept，因 `/event/face_identity` 從不發 unknown）（SPEC:38,59；RUNBOOK:21；IMPL:1119）。
- aggregate 分組 by (capability_id, scenario_kind)：`registered_recall`=positive round pass 率、`unknown_false_accept_rate`=idle round false_trigger 率、`wrong_person_count`=positive round 卻 false_trigger（認錯人）次數（SPEC:55）。
- 必走 demo entrypoint（感知 lane 腳本），不裸 `ros2 run`（RUNBOOK 鐵律:8,21）。

**Files / modules likely touched**
- `benchmarks/core/face_baseline_observer.py`（NEW，Task 4b；`FaceStateSnapshot` / `FaceRoundMeta` / `evaluate_face_round` + ROS node wrapper 訂 `/state/perception/face`，IMPL:1200-1302）— **由 #6 交付**，本 issue 是上機 run
- `benchmarks/test/test_face_baseline_observer.py`（NEW；5 測試，IMPL:1124-1190）
- `benchmarks/core/scoreboard_schema.py`（NEW，Task 1；`to_record` + `CAPABILITY_META` face 屬性）
- `baseline_result.jsonl`（face round 與 gesture/object 同檔，RUNBOOK:34；IMPL:1301）
- code 接地（不改 node）：`face_identity_node.py:634-641` 每 tick 發全 tracks（track_id/stable_name/sim/distance_m/bbox/mode/face_count）；`:561` `/event/face_identity` 只在 stable transition 發、**從不發 unknown**（SPEC:59）；`face_perception/config/face_perception.yaml:23` `sim_threshold_upper:0.40` / `:24` lower:0.22 / `:17` stable_hits:2 / `:30` max_faces:5（SPEC:59）

**Test / verification**
- 先 `python -m pytest benchmarks/test/test_face_baseline_observer.py -q`（5 綠，#6 交付物，IMPL:1307）。
- 上機：起感知 lane → `face_baseline_observer` 訂 `/state/perception/face`（~20Hz，RUNBOOK:17 實機 19.97Hz）→ operator 逐 round 宣告 FaceRoundMeta → JSONL append。
- 判讀：`build_scoreboard.py baseline_result.jsonl --preflight artifacts/baseline/preflight_result.json` → face.recognition grade（缺 `--preflight` → 全 insufficient_data，RUNBOOK:27）。
- 驗 wrong-person 硬規則：JSONL 中任一 positive round `false_trigger=True`（認錯人）→ snapshot grade 必非 pass。

**Output artifact**
- `baseline_result.jsonl` 中 `capability_id=face.recognition` 的 round records（含 `scenario_kind` / `predicted_label` / `false_trigger` / `confidence` / `distance_m` / `distance_source=d435_depth`，IMPL:1283-1292）
- snapshot 內 face.recognition grade + brain_allowed + `registered_recall` / `unknown_false_accept_rate` / `wrong_person_count`

**Out of scope**
- **不主張守護 / 陌生人警報**：North Star §5 禁；`stranger_alert` 已 5/27 改 silent（`text=""`）→ 陌生人=泛稱不點名、不警報（SPEC:45）。
- **不觸發 motion**：face risk_role=evidence_only / dependency_role=content，fail→不叫名仍可互動，degraded/fail 都不觸發 motion（SPEC:42；MASTER:64）。
- 棄 TAR@FAR（小樣本不可理解），改 recall/false-accept/wrong-person（SPEC:40）。
- 換 YuNet/SFace 只在 `unknown_false_accept_rate` fail（>10%）才考慮，**且先試零成本手段**（調高 `sim_threshold` / 重 enroll face_db）；recall fail 單獨不換（SPEC:43）。本 issue 不換模型。
- `time_to_stable_ms` 為觀測欄、**非 gating criterion**（SPEC:55）。
- 不改 `face_identity_node`、不接 Brain（IMPL:1302）。

---

## Issue #9：Gesture (`gesture.wave`) + Object (`object.cup`) baseline run（HITL）

- **Title**：Gesture (`gesture.wave`) + Object (`object.cup`) baseline run — wave recall/idle 誤觸硬 gate + cup recall/idle false-positive
- **Type**：HITL（必須在 Jetson 上機、真人比手勢 + 拿 demo 杯子，operator 宣告 round_meta + 人工 ground-truth；無法 AFK）
- **Blocked by**：#5（`perception_baseline_observer`，Task 4 event-only 純比對邏輯；SPEC §4 observer:172、§5 observer:191；IMPL Task 4:926-997）；判讀可信 snapshot 另需 #1 schema、#2 grader、#3 build_scoreboard、#4 preflight（run_trusted）

**What to build**
跑 `gesture.wave` 與 `object.cup` 兩個 mainline 視覺能力的 as-is baseline：起感知 lane（demo entrypoint，**gesture 必走 `recognizer` backend、object 必須真起 `object_perception`**），operator 逐 round 宣告 `scenario_kind`（positive / idle）+ 人工確認命中，透過 `perception_baseline_observer` 產 JSONL 餵 aggregator。不改模型、不修辨識、不接 Brain。

**Acceptance criteria**
- gesture round 涵蓋：real wave 1m/2m 各 ≥10 次（positive）+ person-present idle 60s×10=10min（idle，人在框內手自然放鬆，**非 idle-EMPTY**）+ natural hand motion；對齊 SPEC:174。
- gesture grade 門檻對齊 SPEC:175：recall ≥90%/80-90%/<80%；**idle 誤觸是硬 gate（權重 > recall）：≤1/10min=pass / 1-3=degraded / >3=fail，不管 recall**。
- gesture 必走 demo recognizer backend + 人工 ground-truth，**不可用壓測 mediapipe backend 的 idle 結果當 baseline**（wave confidence hardcode 1.0 無鑑別力，SPEC:172、:179；RUNBOOK:20）。
- object round 涵蓋：cup 放桌上 1m/2m 各 ≥5 次含背景干擾（positive）+ 空場景 / 無 cup 連續 60s 量 false-positive（idle）；**不測地上 / 人手拿**；對齊 SPEC:192。
- object 計算規則對齊 SPEC:193-194：positive round cup detected=pass、no detection=miss、wrong class=傷 `cup_recall` 不算 false-positive；idle no-cup round 任何 cup 事件=false_positive；1 idle round=1 個 60s 窗，單窗 0=pass/1=degraded/>1=fail。
- object grade 門檻對齊 SPEC:194：cup recall ≥80%/60-80%/<60%；`unknown_false_accept_rate`=誤觸窗數 / 總窗數。
- 每 round JSONL record 帶 `scenario_kind`（positive/idle）供 aggregator 分組（IMPL aggregate by (capability_id, scenario_kind):664-707）。

**Files / modules likely touched**
- `benchmarks/core/perception_baseline_observer.py`（#5 產出，本 issue 使用其 ROS node wrapper 餵 `evaluate_round`；IMPL:1004-1022）
- gesture lane 啟動：`scripts/start_stress_test_tmux.sh` / `vision_perception` launch，**改 `gesture_backend:=recognizer`**（demo backend，非壓測 mediapipe）— RUNBOOK:20
- object lane 啟動：`object_perception` launch，whitelist `[41,999]`（cup-only，SPEC code 接地:198 `object_perception.yaml:20`）
- 訂閱 `/event/gesture_detected`、`/event/object_detected`（IMPL observation 正規化規則:935）
- append 共用 `baseline_result.jsonl`（RUNBOOK:34）

**Test / verification**
- 前置（dev 機）：#5 的 `python -m pytest benchmarks/test/test_perception_baseline_observer.py -q` 全綠（idle/positive/miss/wrong-label/count_false_triggers，IMPL:946-996）。
- Jetson smoke：`ros2 topic hz /perception/object/debug_image`（~6-8 Hz）+ `ros2 topic echo /event/object_detected --once` 確認 cup 事件會發；gesture 確認 recognizer backend 真實揮手會發 `/event/gesture_detected`。
- 上機跑序遵 RUNBOOK step 3 gesture/object（required baseline step，demo entrypoint，operator 宣告 round_meta + 人工確認 → JSONL；RUNBOOK:20）。

**Output artifact**
- 逐 round append `baseline_result.jsonl`（含 `gesture.wave` / `object.cup` records，帶 `scenario_kind`）
- 餵 `build_scoreboard.py` 後 snapshot 中 `gesture.wave` / `object.cup` 兩能力的 grade + recall + idle false-trigger rate（非 insufficient_data）

**Out of scope**
- static gesture（ok/thumbs/palm）全不主張、不測（SPEC:168）。
- object：bottle/wallet/key/denture/`object.general`/VLM 場景描述、顏色辨識全 future、不測（SPEC:184、:196；無 color detection code）。
- 不測 object 地上 / 人手拿（SPEC:192）。
- 不改模型、不調超參、不換 backend score-floor、不動 whitelist — baseline fail 後才開修，屬 v0.3（MASTER Known Findings:210-211；SPEC 修法順序:177、:196）。
- 不接 Brain runtime gate（v0.2）。

---

## Issue #10：Pose (`pose.basic`) baseline run（optional / P2，非 6/18 blocker）

- **Title**：Pose (`pose.basic`) baseline run（studio_only 薄測，optional/P2）— `pose.fall` 不測（future）
- **Type**：HITL（需真人在 Jetson 前擺姿勢、operator 宣告 + 人工確認；但 **optional/P2，非 6/18 blocker**）
- **Blocked by**：#5（`perception_baseline_observer`，Task 4 event-only；IMPL:926-997）；判讀可信 snapshot 另需 #1 schema、#2 grader、#3 build_scoreboard、#4 preflight（同 #9）

> **非 6/18 blocker**：`pose.basic` claim_level=`studio_only`、6/18 不進 Brain 主線（SPEC:134）；canonical 結構鎖定 #10 = optional/P2。可在 6/18 主線跑完後補。

**What to build**
跑 `pose.basic`（standing/sitting/crouching/bending 單幀 2D 幾何分類）的薄 baseline：起感知 lane（demo entrypoint），operator 擺各姿勢，`perception_baseline_observer` 量各姿勢 recall，**只 observe 不觸發 motion、不進 Brain**。`pose.fall` 本輪明確不測。

**Acceptance criteria**
- 場景對齊 SPEC:139：standing/sitting（+crouching/bending）各 ≥3 次 recall，只 observe 不觸發 motion。
- grade 用寬門檻（studio_only）對齊 SPEC:141：recall ≥70% 可顯 / <70% 連 studio 也不信；akimbo/knee_kneel 不穩、不主張。
- `pose.fall` **不產任何 baseline record**，snapshot 維持 `insufficient_data`（SPEC:156 標 insufficient_data；:154 幻覺未解不測）。
- record 帶 `scenario_kind`（pose recall 為 positive）；JSONL append 共用 `baseline_result.jsonl`。
- 明確標註本 issue 為 optional/P2，pose.basic fail **只降級為 unknown / 不顯示姿勢**，不觸發換模型工作（SPEC:143）。

**Files / modules likely touched**
- `benchmarks/core/perception_baseline_observer.py`（#5 產出；event-only，訂 `/event/pose_detected`）
- pose lane 啟動：`vision_perception` launch（`pose_backend:=mediapipe`，demo entrypoint，RUNBOOK 鐵律:8）
- append 共用 `baseline_result.jsonl`

**Test / verification**
- 前置（dev 機）：#5 `python -m pytest benchmarks/test/test_perception_baseline_observer.py -q` 全綠。
- Jetson smoke：`ros2 topic echo /event/pose_detected` 確認 sitting/standing 真人可觸發。
- 上機走 demo entrypoint（非裸 `ros2 run`，RUNBOOK:8）。

**Output artifact**
- `baseline_result.jsonl` 中 `pose.basic` records（各姿勢 recall）；snapshot 中 `pose.basic` grade（studio_only 寬門檻）、`pose.fall` 維持 `insufficient_data`。

**Out of scope**
- `pose.fall` 不測、不評（SPEC:149 claim_level=future；:154 不測；:156 insufficient_data；North Star §5 禁說跌倒可靠）。fallen TTS 永靜音、不停車、不進 Brain（SPEC:157）。
- akimbo/knee_kneel 不主張、不測（SPEC:141）。
- pose 不進 Brain 決策、不觸發 motion（SPEC:142）。
- 不換模型（6/18 前不換；recall fail 只降為 unknown，不觸發 RTMPose/PINTO 升級 — 避免 P2 功能偷偷變 P0，SPEC:143）。
- 非 6/18 blocker，不可因此卡主線 baseline。

---

## Issue #11：Nav baseline — safe_stop / no_auto_resume (insufficient_data) + short_move (dry-run) + dynamic_avoidance (future)（HITL，安全先於移動）

- **Title**：Nav baseline run — safe_stop/no_auto_resume insufficient_data（等 BD-7/BD-8）+ short_move dry-run（safety pass 前不放行 motion）+ dynamic_avoidance future
- **Type**：HITL（需在 Jetson + Go2 上機；safety 兩項待行為重設計，short_move 僅 dry-run / action-path check，**不讓 Go2 實際走**）
- **Blocked by**：#1 schema、#2 grader、#3 build_scoreboard、#4 preflight（判讀可信 snapshot 需這四者）；外部依賴 nav recorder BD-7/BD-8（行為重設計，非本 issue）。本輪三能力**不需** #5 perception observer（safe_stop/no_auto_resume 走 reactive_stop recorder、short_move 走 `/event/nav/mission` action-path；屬 nav workstream）

> **安全先於移動寫死**：`nav.safe_stop` + `nav.no_auto_resume` **pass（或明確人工安全 override）前，不允許跑 motion**，順序不可顛倒（RUNBOOK 跑序鐵律:22；SPEC §6 紀律:202）。

**What to build**
本輪 nav baseline 在「安全先於移動」鐵律下執行：(a) `nav.safe_stop` / `nav.no_auto_resume` 本輪標 `insufficient_data`（recorder BD-7 未接 + no_auto_resume 行為衝突待 BD-8 重設計）；(b) `nav.short_move` 在 safety 兩項未 pass 前**只做 dry-run / action-path check**（手動發 `/nav/goto_relative` 驗 action server 鏈路通、量 `/event/nav/mission`，不讓 Go2 實際走）；(c) `nav.dynamic_avoidance` future、不主張、標 insufficient_data。

**Acceptance criteria**
- `nav.safe_stop`：本輪標 `insufficient_data`，**不可寫 pass** — recorder `_cb_reactive_status` no-op（BD-7 未接，SPEC:212、:219）。硬 fail 結構先鎖：`collision_count` 任一次=fail、`stop_margin_m` pass 需 ≥0.10m（SPEC:215，數字 calibrate-from-run-1）。
- `nav.no_auto_resume`：本輪標 `insufficient_data` + 標明「**行為待重定義（BD-8）**」 — 現行 `reactive_stop_node.py:307 _maybe_call_nav_pause` 是 auto-resume，與語意相反（SPEC:234；RUNBOOK:23「還需 BD-8 行為重設計，非只接 recorder」）。正確行為先鎖：stop 後不自動 resume 原 goal，須 operator/Brain 發新命令才動（SPEC:232）。
- `nav.short_move`：safety 兩項 pass 前**只 dry-run**，手動發 goto_relative 驗 action server 鏈路通 + 量 `/event/nav/mission`（outcome_code/actual_distance），**不讓 Go2 實際走**（RUNBOOK:24；SPEC:248 需 safe_stop+no_auto_resume 先 pass）。本輪 short_move 標 `insufficient_data`，記錄 3 blocker（IE:278 dispatch stub / F7 未定位 / 0.85 profile 無實機 motion 證據，SPEC:249）。
- `nav.dynamic_avoidance`：不主張、標 `insufficient_data`（非 fail；架構 stop-only 不繞障，SPEC:256-259）。
- 跑序遵 RUNBOOK step 3 nav 鐵律：safety pass / 人工 override 前不跑 motion，順序不可顛倒（RUNBOOK:22-24）。
- D435 fusion shadow test 屬 spike、不主張：若跑，**必須 `target_frame:=base_link` 且先驗 TF**、height filter 0.05-0.50、同錄 `/scan_rplidar`、**不可沿用舊 detour script**，且**不可先宣稱 fusion 已可靠**（SPEC §6e:267、:273）。

**Files / modules likely touched**
- `scripts/start_nav_capability_demo_tmux.sh`（demo entrypoint，nav lane；short_move action-path）
- 手動發 action：`ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative`（dry-run 驗鏈路）
- 訂閱 `/event/nav/mission`（outcome_code/actual_distance；SPEC:244）
- recorder `recorder_node` `_cb_reactive_status` / `_cb_depth_safety`（BD-7 待接；MASTER Known Findings:213）— 本輪不在此 issue 修，僅標 insufficient_data 依據
- `reactive_stop_node.py:307`（no_auto_resume 行為衝突點，BD-8 重設計依據，**本輪不改**，SPEC:234）
- D435 shadow（若跑 spike）：`pointcloud_to_laserscan` → `/scan_d435_shadow`，`target_frame:=base_link`（SPEC:267）
- append 共用 `baseline_result.jsonl`

**Test / verification**
- short_move dry-run：手動發 goto_relative，確認 action server 接 goal + 發 `/event/nav/mission`，**Go2 不動**（safety 未 pass）。
- 跑前確認 RUNBOOK step 3 nav 鐵律順序（RUNBOOK:22）+ CLAUDE.md 已知陷阱（reactive_stop `safety_only=true` mux 模式、cmd_vel=0 不停車 StopMove 路徑）。
- snapshot 驗：`nav.safe_stop` / `nav.no_auto_resume` / `nav.short_move` / `nav.dynamic_avoidance` 四能力 grade 皆 `insufficient_data`（aggregator 對 0 樣本 / 未接 observer 的 fail-closed 行為，IMPL:555-565）。

**Output artifact**
- `baseline_result.jsonl`：short_move dry-run 的 action-path check 記錄（如有 `/event/nav/mission` outcome）。
- snapshot 中 nav 四能力 grade = `insufficient_data` + reason（safe_stop=BD-7 未接 / no_auto_resume=BD-8 行為待重定義 / short_move=3 blocker / dynamic_avoidance=future）。
- 若跑 D435 shadow spike：`/scan_d435_shadow` + `/scan_rplidar` 同錄 bag（「RPLIDAR 漏掉而 D435 補到的比例」記錄，不主張）。

**Out of scope**
- **不寫 `safe_stop 已完成` / `no_auto_resume pass`**（SPEC:219；MASTER:70）。
- safety 兩項 pass / 人工 override 前**不跑真實 0.3/0.5m motion**（SPEC:248；RUNBOOK:24）。
- `nav.dynamic_avoidance` 不主張、不測 — ComposableNode + velocity_smoother 是 Phase 11+ future（SPEC:260）。
- 本輪不修 recorder BD-7、不做 no_auto_resume BD-8 行為重設計、不定位 F7 — 屬獨立 nav workstream，非 capability spec grill 範圍（SPEC:275；MASTER:213）。
- D435 fusion 不主張為可靠、不接 safe_stop / Nav2 obstacle layer（spike 過了才升級，SPEC:267、:273）；不復活舊 detour script。
- Go2 內建 LiDAR / `range_obstacle[4]` / onboard avoidance（api 1004）皆 spike/future、不進 6/18 主宣稱（SPEC §6e:264-271）。

---

## Issue #12：Studio evidence — provenance label + Brain trace display + frozen scoreboard chip

- **Title**：Studio evidence：provenance label (live/mock/frozen/missing) + Brain trace display + read-only frozen scoreboard chip
- **Type**：AFK（純前端 / gateway code，本機可開發；可用 `backend/mock_server.py` + 一份 fixture snapshot 在 dev 機完成。Jetson live smoke 在上機輪驗收，不阻 AFK 開發）
- **Blocked by**：none（read-only 讀 frozen snapshot；snapshot 產出鏈在 #3 build_scoreboard / #13 freeze，但本 issue 可先用 `pawai_brain/test/fixtures/baseline_snapshot.example.json` 做 chip 開發，git-tracked 穩定樣本，SPEC §9:417；不擋 6/18）

**What to build**
1. 在既有 Studio dashboard 加「誠實層」provenance 標籤 `live/mock/frozen/missing`，**mock server 跑時 UI 必須明顯標 `mock`、不得偽裝 live**，並修預設 `start.sh` 跑 mock 卻看不出來的問題（SPEC §8:334, :358）。
2. 確認 Brain trace drawer 渲染真實 `/brain/conversation_trace`（非 mock），可看出 stage/status/reason 與四態（proposed/blocked/needs_confirm/rejected_not_allowed）（SPEC §8:343-345 c、§7b:318 d）。
3. 新增 `GET /api/scoreboard` 唯讀 endpoint + 前端 chip：讀 frozen `baseline_snapshot.json`（path 由 `PAWAI_SCOREBOARD_PATH` 控制），顯 `capability_id/grade/reason/last_tested_at`（SPEC §8:345 (4), :352；owner = Studio gateway/frontend team，§9:421）。

**Acceptance criteria**（對齊 SPEC §8:345 的 pass 5 條 + degraded/fail）
- [ ] 前端對每個資料來源明確標 `live / mock / frozen / missing` 四態之一（SPEC §8:345 (1)）。
- [ ] 跑 mock server（`backend/mock_server.py`，port 8080）時 UI 明顯顯 `mock`，**不得偽裝成 live**；mock 與 live envelope 一字不差是已知坑，標籤必須來自連線後端身分而非 envelope 內容（SPEC §8:345 (2), :356）。
- [ ] 預設 `start.sh`（現 `start.sh:44-46` 預設 mock，port 8080）不再讓 demo 畫面看似真資料 —— 或顯著標 mock、或 demo 切 `start-live.sh --live`（SPEC §8:358）。
- [ ] `/brain/conversation_trace` 在 trace drawer 顯 stage / status / detail(reason)；proposed / blocked / needs_confirm / rejected_not_allowed 四態可辨（SPEC §8:345 (3)、§7b:318；trace 已在 gateway forward，`studio_gateway.py:81`）。
- [ ] frozen scoreboard chip 顯 `capability_id / grade / reason(failure_reason) / last_tested_at` 四欄齊全（SPEC §8:345 (4)）。
- [ ] `blocked / insufficient_data` 必帶 reason，不准只顯 `fail`；斷某來源顯 `missing` 非空白（SPEC §8:343 (e), :345 (5)）。
- [ ] chip 只讀 frozen snapshot，欄位語意對齊 snapshot 結構（`capabilities[id].grade / failure_reason`，IMPL `to_snapshot`:744-748；`brain_allowed` derive:748）。
- [ ] **overclaim 防線**：UI 不得宣稱「IE 第二道 gate 已吃 scoreboard / runtime 全層 enforce」；gate blocked 顯示只反映 pawai_brain 那層，IE scoreboard-aware enforcement 標 v0.2 待補（SPEC §8:350）。

**Files / modules likely touched**
- `pawai-studio/gateway/studio_gateway.py`（NEW endpoint `GET /api/scoreboard`；現 `/api/capability` 在 `studio_gateway.py:268, 538-541` 只回 Nav/Depth Bool tri-state，**非** baseline grade → 需新 endpoint，SPEC §8:357；trace forward 已存在 `:81`）
- `pawai-studio/frontend/components/`（NEW/修改 provenance badge + scoreboard chip 元件；面板已齊 face/gesture/pose/object/speech/chat/navigation/live，SPEC §8:355）
- `pawai-studio/frontend/.../contracts/types.ts`（現 `source` 欄位是感知模態非資料真偽，`types.ts:25,59,95,118,155` → NEW provenance 欄位，SPEC §8:356）
- `pawai-studio/frontend/.../use-websocket.ts`（連同一 `/ws/events`，分不出 gateway vs mock → NEW 後端身分標記，SPEC §8:356）
- `pawai-studio/start.sh`（line 44-46 預設 mock；NEW 標 mock 或調整預設）
- `pawai-studio/backend/mock_server.py`（envelope 與 live 一字不差，NEW mock 身分標記，SPEC §8:356）
- fixture（讀）：`pawai_brain/test/fixtures/baseline_snapshot.example.json`（NEW，git-tracked，SPEC §9:417）

**Test / verification**（對齊 SPEC §8:342-343 scenario）
- gateway live smoke：起 live gateway → 驗 UI 標 `live`；起 mock server → 驗 UI 標 `mock`（不偽裝）。
- replay 一段對話 → 驗 trace drawer 顯 stage/status/reason（§7b code path 由 scenario replay 獨立驗，trace 是否真實顯示在此驗）。
- 載入一份 `baseline_snapshot.json`（fixture）→ 驗 chip 顯 capability/grade/reason/timestamp 四欄；斷某來源 → 驗顯 `missing`。
- `/api/*` check：`curl GET /api/scoreboard` 回 frozen snapshot 內容；`PAWAI_SCOREBOARD_PATH` 切換不同檔可生效。
- frontend source-label smoke（跑 live 看 `live` / 跑 mock 看 `mock`）+ screenshot（SPEC §8:342）。

**Output artifact**
- `GET /api/scoreboard` JSON 回應（讀 frozen `baseline_snapshot.json`）
- 前端 provenance badge + scoreboard chip（截圖證據）
- trace drawer 渲染 `/brain/conversation_trace` 的畫面

**Out of scope**（SPEC §8:338, :350, :352 scope guard）
- **不接 runtime gate**：chip 只讀 frozen snapshot，不接 Brain runtime / IE enforcement（v0.2，SPEC §8:350；§7b/#14 才負責「grade 真的接進 runtime gate」）。
- **不 live recompute**：不在 demo 中即時重算 grade（避免 grade 抖動，SPEC §8:352, §9:421）。
- **不做 health monitor / full observability dashboard**：超出唯讀 chip 範圍的 Studio health panel / runtime monitor 仍砍（SPEC §8:338, :352；MASTER:231 例外限「唯讀、不 live recompute、不接 runtime gate、只讀 frozen snapshot」）。
- **不重寫 trace 展示給 v0.2**：本 issue 只做 6/18「trace 看得到、非 mock、有 reason」展示面；scoreboard grade 接進 runtime gate 是 #14（不在此重做）。
- chip owner = Studio team，snapshot 的「產出 + freeze」是 #13/#3，不在本 issue 做。

---

## Issue #13：CLI readiness + freeze mechanism

- **Title**：CLI readiness + freeze mechanism — `pawai readiness`（demo readiness authority, fail-closed --json truth table）+ freeze mechanism（凍結 demo snapshot 到 artifacts/baseline/frozen/）
- **Type**：AFK 為主（`pawai readiness` 子命令 + 真值表 pytest 純 code，本機可寫）；**含 1 次 HITL Jetson smoke**（真 snapshot 上機跑 `pawai readiness` + `--json` 格式驗證，SPEC §9:370-371）。建議拆：AFK 寫命令 + 真值表先綠，Jetson smoke 上機輪補。
- **Blocked by**：**implementation（`pawai readiness` 命令 + freeze mechanism + 真值表）blocked by #3**（build_scoreboard.py 產 `baseline_snapshot.json`，IMPL Task 3b:772-922）── 可先用 fixture / 合成 snapshot 寫，不必等真 baseline run。**但 actual demo freeze blocked by #4（preflight→run_trusted）+ completed required baseline runs #7 / #8 / #9 / #11** ── **#10 pose 為 optional/P2，缺它應讓 `pose.basic`/`pose.fall` 維持 insufficient_data、不擋 freeze**（可有就收）。required baseline 沒跑完，frozen 的只會是空殼 / 全 insufficient_data，不是可信 demo snapshot。

**What to build**
1. 新 `pawai readiness` / `pawai readiness --json` 子命令，**與 `doctor` 分開**（doctor 可呼叫顯摘要，但不塞進 doctor 主邏輯）：以 frozen baseline snapshot + deploy manifest（`.pawai-last-deploy`）+ preflight metadata 做 **fail-closed** demo readiness 判定（SPEC §9:362, :366, :377）。
2. freeze demo snapshot 機制：把 working `artifacts/baseline/baseline_snapshot.json` 凍進 `artifacts/baseline/frozen/2026-06-18/baseline_snapshot.json`（SPEC §9:416；RUNBOOK:36 demo 當天用 frozen）。

**Acceptance criteria**（對齊 SPEC §9:373 capability grade 定義 + :391-403 fail-closed 表）
- [ ] fail-closed 真值表全綠：snapshot 缺檔 / schema invalid / `run_trusted == false` / `layer0_preflight` fail / `snapshot.git_sha != deploy sha`（sha mismatch）/ capability list 不全 / mainline 能力缺 grade-reason → verdict `not_ready`；全通過 → `ready`（SPEC §9:371, :391-401）。
- [ ] sha mismatch 是硬 stale 訊號（snapshot.git_sha != 當前 deploy sha → `not_ready`，:397, :403）；snapshot age **只警告不擋** verdict：`>3 days → warning`、`>7 days → strong warning`（SPEC §9:386, :403）。
- [ ] `fail_open_count = 0`（無「該 not_ready 卻 ready」）；scoreboard 評的是 readiness **機制本身**正確性（capability grade），非單次 runtime verdict（SPEC §9:372-373 (a)/(b) 兩層別混）。
- [ ] `--json` 輸出格式正確（真值表 verdict + 各 check 結果）；readiness 機制本身壞 → 對自己也 fail-closed（當 not_ready），任何不確定 = not_ready（SPEC §9:374, :391）。
- [ ] override 軟可硬不可、且留痕：`--accept-warnings`/`--force-ready` 只能 override 軟條件（age warning / missing optional notes / preflight `pass_with_warnings`）；硬條件（snapshot missing / schema invalid / run_trusted=False / layer0_preflight fail / **sha mismatch** / capability list 不全）**不可** override；override 蓋進輸出 `{override, operator, reason, timestamp}`（SPEC §9:406-409）。
- [ ] checks 涵蓋最小檢查表 8 項：snapshot 存在 / schema version / run_trusted / layer0_preflight pass|pass_with_warnings / sha 對 deploy manifest / age advisory / 15 capability 全列 / mainline 能力皆有 grade+reason（SPEC §9:380-389）。
- [ ] snapshot path 用 env `PAWAI_SCOREBOARD_PATH` 可覆寫（預設 working 路徑 `artifacts/baseline/baseline_snapshot.json`）；WSL 跑 readiness 經 SSH 讀 Jetson 路徑（沿用 `status.py:88 cat {jetson_repo}/.pawai-last-deploy`，SPEC §9:419）。
- [ ] **概念不混**：deploy manifest `stale_after_h=6h`（檢查部署記錄新舊，IMPL `current_run_meta`:251）與 snapshot age 3d/7d advisory（檢查 baseline snapshot 新舊）是不同概念，各自為政（SPEC §9:404）。
- [ ] freeze 後 `artifacts/baseline/frozen/2026-06-18/baseline_snapshot.json` 即 §8 `/api/scoreboard` 唯讀的那份（demo 當天用 frozen 不重算，SPEC §9:421, §8:352）。
- [ ] **overclaim 防線**：readiness 是 demo readiness authority，但 Brain v0.1 不即時消費它（v0.2 才接 runtime gate，SPEC §9:362）；不可寫成「readiness 已接進 Brain gate」。

**Files / modules likely touched**
- `pawai_cli/.../readiness.py`（NEW 子命令 — recon 確認 greenfield，SPEC §9:425）
- `pawai_cli/.../main.py`（NEW 註冊 click 命令；現 doctor/status 命令齊 `main.py:95` 構造 `.pawai-last-deploy`、`main.py:643` 寫 Jetson、`main.py:348` SSH echo，SPEC §9:424）
- `pawai_cli/.../status.py`（reuse 讀 manifest `status.py:11/12/88`、sha mismatch 範本 `status.py:286-296`，MASTER:116）
- test：`pawai_cli/test/test_readiness.py`（NEW 真值表 pytest，SPEC §9:370）
- fixture：`pawai_brain/test/fixtures/baseline_snapshot.example.json`（NEW git-tracked 穩定樣本，SPEC §9:417）
- snapshot 路徑（讀/freeze）：`artifacts/baseline/baseline_snapshot.json`（working，`.gitignore` 加 `artifacts/`）→ `artifacts/baseline/frozen/2026-06-18/baseline_snapshot.json`（frozen，SPEC §9:415-416）
- env：`PAWAI_SCOREBOARD_PATH`（NEW，SPEC §9:419, :421）
- 依賴產出：`benchmarks/core/build_scoreboard.py`（#3 / IMPL Task 3b，`--out` 預設 `artifacts/baseline/baseline_snapshot.json` IMPL:881；freeze 凍它的產物）

**Test / verification**（對齊 SPEC §9:370-371 observer）
- pytest 真值表窮舉（fail-open 是失敗模式，採樣測不到）：snapshot 缺檔 / schema 錯 / run_trusted=False / preflight fail / sha mismatch / capability list 不全 / age 過舊 / 全通過 → 預期 verdict（SPEC §9:371）。
- 失敗模式 = 「該說不可信卻說 ready」(fail-open)，真值表覆蓋數 ÷ 應覆蓋數 + `fail_open_count` 為 metric（SPEC §9:372）。
- 1 次 Jetson smoke（HITL）：真 snapshot → `pawai readiness` 跑得出 + `--json` 格式正確（SPEC §9:371）。
- override 留痕驗證：軟條件 `--accept-warnings` 可過且輸出含 override 區塊；硬條件（如 sha mismatch）即使加 `--force-ready` 仍 `not_ready`（SPEC §9:408-409）。
- grep / fixture：用 `baseline_snapshot.example.json` 跑全真值表分支。

**Output artifact**
- `pawai readiness` 終端輸出（verdict `ready / not_ready` + 各 check）
- `pawai readiness --json`（機器可讀真值表 + override 留痕欄位）
- freeze command / readiness output（本 issue 交付的是 freeze command/mechanism + readiness verdict）；actual `artifacts/baseline/frozen/2026-06-18/baseline_snapshot.json` 在 #4 + required baseline runs #7/#8/#9/#11 跑完後才產得出（#10 pose optional；非本 issue 完成即有）

**Out of scope**（SPEC §9 + MASTER scope guard，防 scope creep）
- **不塞進 doctor**：readiness 與 doctor 分開 —— doctor = 系統現在能不能跑（環境/網路/lock/driver）；readiness = baseline snapshot 可不可信，兩者不混（SPEC §9:362, :377）。
- **不接 Brain runtime gate**：Brain v0.1 不即時消費 readiness；runtime gate enforce 是 v0.2（SPEC §9:362；overclaim 防線：grade 接進 `compute_effective_status` 是 #14 / MASTER 設計段 D，不在此做）。
- **不設武斷 TTL 硬擋**：age 只 advisory（3d/7d warning），硬 stale 只認 sha mismatch（SPEC §9:403）。
- **不重算 grade**：readiness 只讀 frozen snapshot 判可信度，不重跑 aggregator / 不改 grade（grade 計算是 #2/#3 grader+build_scoreboard）。
- override 不萬能：硬條件不可 override（SPEC §9:408）。
- `/api/scoreboard` endpoint 本體 owner = Studio team（#12），本 issue 只負責產 + freeze 它讀的那份 snapshot（SPEC §9:421）。

---

## Issue #14：Brain capability health gate（v0.2，grade 接進 runtime gate）

- **Title**：Brain capability health gate — `compute_effective_status` 加 grade 分支 + IE 第二道 gate + allowlist single source（v0.2）
- **Type**：AFK（純 code：擴 `compute_effective_status` 純函式 + IE executor gate + pytest 真值表，dev 機可跑、無 ROS / Jetson 依賴）
- **Blocked by**：#2（grader：`brain_allowed(grade, claim_level)`）、#3（aggregator/build_scoreboard：產 `baseline_snapshot.json` 含每能力 `grade` / `claim_level` / `dependency_role` / `brain_allowed`）、#4（demo.yaml preflight：`run_trusted` fail-closed → snapshot grade 來源可信）。**不 block 6/18**（post-baseline，明確標 v0.2）

**What to build**
把 baseline scoreboard 的 `grade` / `claim_level` / `dependency_role` 接進 PawAI Brain 的 runtime gate —— 在 `compute_effective_status()` 既有 first-match 鏈插一個 grade 分支（SayCan affordance-gating），再於 IE executor 補第二道 gate（`brain_node.py:505` 吃 grade），並把 allowlist 收斂成 single source of truth（`skill_policy_gate.py:18` 與 `brain_node.py:574` 收斂），全部用 pytest 真值表覆蓋。snapshot grade 為唯一 capability-health 來源（demo-day 用 frozen），不重算。

**Acceptance criteria**（對齊 SPEC §7a row 10 / MASTER 設計段 D）
- [ ] grade 分支插在 SPEC 指定位置：`disabled / studio_only / explain_only / demo_guide / static_enabled / enabled_when / cooldown` 判定**之後**、physical-block（`tts_playing / obstacle / nav_safe`）判定**之前**（SPEC §7a:303；MASTER:184；現有鏈見 `effective_status.py:38-70`）。
- [ ] 分支邏輯逐條對齊 MASTER 偽碼（MASTER:187-199）：依賴 grade==fail 時 `trigger→disabled` / `safety_guard→blocked(禁 motion/nav)` / `actuation→blocked(禁該動作)` / `content→放行內容降級` / `evidence→放行`；grade∈{degraded,insufficient_data} 時 `safety_guard|actuation→blocked` / `trigger→disabled` / `content|evidence→放行(only say/表情/顯示，不 motion)`。
- [ ] **不覆蓋 skill-level hard disable**：`disabled / studio_only / explain_only` 是 skill 層硬約束，capability grade 不得翻案（SPEC:303「不可覆蓋 skill-level hard disable」、MASTER:198-199）。需有 test 證明「skill baseline=disabled + capability grade=pass → 仍 disabled」。
- [ ] `brain_allowed = (grade==pass AND claim_level==mainline)`：`claim_level∈{future,studio_only,not_claimed}` 即使 grade==pass 也不進 mainline（MASTER:199、grader `brain_allowed` 簽名 IMPL:438-440）。
- [ ] reason 帶 baseline provenance（`{cap} FAIL/未達 pass，...` 形式，MASTER:189-197）；blocked / disabled 必帶 reason（SPEC §8:345 對 reason 的要求一致）。
- [ ] IE 第二道 gate：`brain_node.py:505` executor 在 dispatch 前查 effective_status / grade（SPEC §8:350 點名 P1-1「`brain_node.py:505-533` executor 不查 grade/effective_status」尚未修，此 issue 修它）。
- [ ] allowlist single source of truth：`skill_policy_gate.py:18` 與 `brain_node.py:574` 兩處 allowlist 收斂為一份（避免兩層各標各的 drift，對齊 MASTER 設計段 D「四欄不雙真相源」:171-180）。
- [ ] `brain.skill_gate` 真值表 pass 條件全部成立（SPEC §7a:301）：(a) `unsafe_allowed_count=0`；(b) grade≠pass 的依賴 skill 全被擋；(c) future/not_claimed 永不進 mainline；(d) insufficient_data 對 motion/nav 必 fail-closed。窮舉 (claim_level × grade × dependency_role/risk_role) 組合（SPEC §7a:299）。
- [ ] fail-closed 預設：缺 grade / snapshot 不可信（`run_trusted=False`）→ 全當 insufficient_data → 擋（SPEC §7a:302）。

**Files / modules likely touched**
- `pawai_brain/pawai_brain/capability/effective_status.py:26`（`compute_effective_status` 加 grade 分支；現 first-match 鏈:38-70，無 grade 分支 — SPEC §7a:284 確認）
- `pawai_brain/pawai_brain/capability/effective_status.py`（`WorldFlags` 或新 `CapabilityHealth` 入參加 `capability_grade / brain_allowed / failure_reason` — MASTER 設計段 D:167-169）
- `pawai_brain/pawai_brain/brain_node.py:505`（executor 第二道 gate，吃 grade；P1-1 SPEC §8:350）
- `pawai_brain/pawai_brain/brain_node.py:574`（allowlist 收斂端）
- `interaction_executive/interaction_executive/skill_policy_gate.py:18`（allowlist single source；`normalize_proposal_v2` 分流見 :88 — SPEC §7b code 接地:325）
- NEW：`pawai_brain/test/test_capability_health_gate.py`（grade 分支真值表，預定路徑）
- 讀（不改）：`benchmarks/core/grader.py`（`brain_allowed`）、`benchmarks/core/scoreboard_schema.py`（`CAPABILITY_META` dependency_role）、`artifacts/baseline/baseline_snapshot.json`（frozen grade 來源，SPEC §9:415）

**Test / verification**
- `python -m pytest pawai_brain/test/test_capability_health_gate.py -q`：grade 分支真值表（SayCan affordance-gating，非上機採樣 — SPEC §7a:298「pytest 真值表，非上機採樣」）。
- 回歸：現有 340 offline tests（Skill Policy Gate 層，SPEC §7a:283）插分支後須仍全綠（grade 分支不得破壞既有 8 態 first-match）。
- 真值表須覆蓋角落 case：`grade=insufficient_data + risk_role=safety_critical` → fail-closed（SPEC §7a:298 指出採樣永遠測不到此角落）。
- allowlist 收斂後：兩處引用同一份的 grep / import 檢查。

**Output artifact**
改寫的 `effective_status.py`（含 grade 分支）+ `brain_node.py`（IE 第二道 gate）+ 收斂後 single-source allowlist + `test_capability_health_gate.py`（真值表全綠）。`brain.skill_gate` 真值表覆蓋報告（covered ÷ should-cover，SPEC §7a:300）。

**Out of scope**
- **6/18 不要求接完**：`brain.skill_gate` 維持 `insufficient_data` 是 acceptable 的 6/18 狀態（SPEC §7a:288「grade 沒接進 gate 之前一律 insufficient_data」、:294「grade 未接進 gate 前 = insufficient_data，不可寫 pass」）。本 issue 是 v0.2 deliverable，**不擋 6/18**。
- **不重寫 trace 展示**：`brain.trace` 的 6/18「trace 看得到 / 非 mock / 有 reason」由 #12 Studio evidence 負責；本 issue 只做 grade-consuming gate，不碰 trace drawer / Studio 顯示（SPEC §7b:322 §7b/§8 邊界）。
- 不改 `demo_status_baseline`（skill 層）/ `claim_level`（capability 層）的標註；本 issue 只**合成**四欄判定，不新增真相源（MASTER 設計段 D:171-180「不可雙真相源」）。
- 不造平行 gate：擴既有 `compute_effective_status`，不另寫平行 capability_health gate（MASTER:169「不另造平行 gate」）。
- 不接 fast_router 繞 gate：fast path 不得繞過 capability_health gate / nav safety（SPEC §7:329 硬邊界）。
- snapshot demo-day 用 frozen、不即時重算（MASTER:202、RUNBOOK:36）。

---

# Dev Workflow Meta Issues（獨立 tracking，**非 baseline 完成條件**）

> **兩層 tracking（Roy 鎖定）**：`Capability Baseline & Scoreboard` tracking 只掛 #1-#14；這 3 個 meta issue 屬另一條 tracking `Development Workflow Hardening`（或同 milestone），**不放進「完成 baseline」的 checklist** ── 它們是讓未來 `/goal → branch → PR → CI → review → merge` 跑得穩的流程護欄，不是 demo 功能。
> **關鍵紀律**：meta issue **不得 block #1-#3 core**（baseline core 可先跑）。

## Tracking Issue（第二條）：Development Workflow Hardening

**目標（一句）**：補齊 PR template / CI fast-gate / HITL 驗證協定三道流程護欄，讓 17 個 issue 的 agent 開發品質一致、evidence 可稽核。掛 Meta-A / Meta-B / Meta-C。**與 baseline 完成度脫鉤**。

| # | Title | Type | 6/18? | Blocked by |
|---|---|---|:---:|---|
| Meta-A | Add PR template + issue execution checklist | AFK | 先做（最高優先，低成本） | none |
| Meta-B | Expand Fast Gate CI（Phase 1 純 Python → Phase 2 ROS Tier-2） | AFK | Phase 1 先做（與 #1-#3 平行，**不 block 它們**） | none |
| Meta-C | Jetson/Go2 HITL verification protocol + artifact versioning | AFK（doc/schema）+ HITL（上機） | #7-#11 baseline run **之前**完成 | 與 #4 demo.yaml 部分重疊（見下） |

**建立 / 執行順序（Roy 鎖定）**：
```text
1. Meta-A 先做（PR template）
2. #1 #2 #3 baseline core 開始（meta 不擋）
3. Meta-B Phase 1 與 #1-#3 平行
4. #5 #6 #7-#11 跟上
5. Meta-C 在 #7-#11 之前完成
6. #12 #13 收 evidence / freeze
7. #14 留 v0.2
```

---

## Issue Meta-A：Add PR template + issue execution checklist

- **Title**：Add `.github/pull_request_template.md`（linked issue / test / hardware / evidence / out-of-scope 五欄）
- **Type**：AFK（純文件，無 code）
- **Blocked by**：none。**最高優先**（其餘 PR 要靠它才一致）
- **What to build**：兩部分 ──
  - **(a) PR template** `.github/pull_request_template.md`，強迫每個 PR 填：(1) linked issue #；(2) test command + 輸出；(3) hardware needed = `none / Jetson / Go2`；(4) evidence（screenshot / log / snapshot / readiness output 連結）；(5) out of scope（本 PR 不碰什麼）。
  - **(b) issue execution checklist /「`/goal` 執行規格」模板**（讓 agent 穩定開工，存進 workflow doc `docs/agents/issue-development-workflow.md` 供 `/goal` 套用）：每個 `/goal` 須含 `Branch: codex/issue-X-short-name` / `Scope: 只做 #X，不碰 #Y/#Z` / `Hardware: none / Jetson / Go2 motion` / `Required tests:` / `Required artifact:` / `Required evidence:` / `Out of scope:` ── 直接吃 issue 的 Out-of-scope 欄當「不准改」清單。
- **Acceptance criteria**：PR template 在 GitHub PR 編輯器正確 render；5 欄齊；hardware 欄是 `none/Jetson/Go2` 三選；reviewer 能一眼看出要不要 HITL 驗證。
- **Files / modules likely touched**：Create `.github/pull_request_template.md`（現只有 `.github/ISSUE_TEMPLATE/your-question.md`，無 PR template ── 已驗）。
- **Test / verification**：開一個 test/draft PR，確認 5 欄出現在編輯器。
- **Output artifact**：`.github/pull_request_template.md`。
- **Out of scope**：CI 自動 reject 空欄（未來 Meta-B 的 gate enhancement）；**非 baseline 完成條件**。

## Issue Meta-B：Expand Fast Gate CI（Phase 1 純 Python → Phase 2 ROS Tier-2）

- **Title**：擴充既有 `ros_build.yaml` Fast Gate ── 加新 package 純 Python tests + flake8 只擋新 code
- **Type**：AFK（CI 設定）
- **Blocked by**：none。**Phase 1 與 #1-#3 平行，不得 block #1-#3**
- **What to build**：
  - **Phase 1（6/18 先做）**：把 `benchmarks/core`（含 **scoreboard schema / grader / aggregator** test）、`tools/pawai_cli`(5 test，含 **readiness CLI** test)、`pawai_brain`(18 test)、`pawai_nav_metrics`(1 test) 的**純 Python test** 加進**既有** Fast Gate pytest 清單（`ros_build.yaml:31-55`，**不是從零搭 CI** ── Fast Gate job 已存在 :14）；flake8 **只對新 code blocking**（`git diff` filter，新增檔才 `--exit-1`；至少針對 `benchmarks/core/*` / `tools/pawai_cli/*` / `pawai_brain/*`），legacy 維持 `--exit-zero`（:30）；`studio-ci.yml` backend 加 `pytest test_mock_text_input.py`。
  - **Phase 2（sprint B，後做）**：Tier-2 colcon（:110）加 `interaction_executive`(9 ROS test) / `pawai_brain` / `nav_capability`(1 integration)。
- **Acceptance criteria**：Phase 1 ── 新增 ~32 純 Python test 在 Fast Gate <1-2 min 全綠；flake8 只擋新 code lint、不動 legacy；CI green。**不一次把所有 ROS package 丟進去（會因 heavy deps 爆）**。
- **Files / modules likely touched**：Modify `.github/workflows/ros_build.yaml`（Fast Gate pytest list ~:31-55、flake8 ~:27-30、Tier-2 ~:110）、`.github/workflows/studio-ci.yml`（backend pytest）。
- **Test / verification**：push 含新 test 的 branch → Fast Gate ~1 min 跑得到並 green；故意加一個 lint-fail 的新檔 → flake8 擋；改 legacy 檔 lint → 不擋。
- **Output artifact**：CI workflow logs（Fast Gate test 數從 15 → ~47 全綠）+ coverage report。
- **Out of scope**：Phase 2 ROS Tier-2 / heavy deps（go2_robot_sdk needs nav2/PCL）；benchmarks model-load test（需 model cache）；T3/T4 硬體 CI；**非 baseline 完成條件**。

## Issue Meta-C：Jetson/Go2 HITL verification protocol + artifact versioning

- **Title**：定義 HITL 驗證協定 + artifact 版本化（`artifacts/baseline/` schema + motion sign-off）
- **Type**：AFK（doc / schema）+ HITL（上機驗）
- **Blocked by**：與 **#4 demo.yaml 部分重疊**（#4 填 demo.yaml 的 preflight checks + run_trusted；本 issue **不重填 demo.yaml**，只定**協定 + artifact schema + sign-off**，引用 #4）。應在 **#7-#11 baseline run 之前**完成（baseline 要照這個 artifact 規範產出）。
- **What to build**：(1) HITL 驗證協定文件（`docs/agents/hitl-verification-protocol.md`）：何時需 Jetson smoke / 何時需 Go2 motion，含**逐能力硬體對照**（voice→Jetson+mic、face→D435、gesture/object→camera、nav→Go2+安全場地）；(2) artifact schema：`artifacts/baseline/{preflight_result.json, baseline_result.jsonl, baseline_snapshot.json, logs/, screenshots/}`（對齊 SPEC §9 路徑表）；(3) **Go2 motion sign-off 機制**：`artifacts/baseline/motion_sign_offs.jsonl`（append-only，每筆含 **operator / timestamp / trial_id / commit_sha / safety_checks_passed / video_sha**）── 回答你說的「誰簽、何時簽、在哪個 commit 簽」；(4) snapshot 帶 `git_sha + deploy_version`（接 #1 `current_run_meta` / #13 freeze）。
- **Acceptance criteria**：協定 doc 存在且涵蓋 Jetson/Go2 觸發條件；artifact schema 定義清楚；`motion_sign_offs.jsonl` 為 append-only 且必含 commit_sha；與 #4 demo.yaml + #13 freeze 對齊不重複。
- **Files / modules likely touched**：Create `docs/agents/hitl-verification-protocol.md`、`.claude/schemas/{preflight_result,baseline_snapshot,motion_sign_off}.schema.json`（NEW）；引用（不重寫）#4 `demo.yaml`、#13 freeze、SPEC §9 路徑表。
- **Test / verification**：dry-run 產一份 sample `preflight_result.json` + `baseline_snapshot.json`；手動 append 一筆 `motion_sign_off` → 驗 schema + commit_sha 欄位在。
- **Output artifact**：HITL 協定 doc + 3 個 schema + sample `motion_sign_offs.jsonl`。
- **Out of scope**：T3/T4 自動 CI gate（6/18 用手動 checklist，不做 Actions blocker）；artifact dashboard / web UI（post-demo）；demo.yaml 的 check 內容（屬 #4）；**非 baseline 完成條件**。