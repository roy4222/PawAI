# Capability Baseline & Scoreboard — Implementation Plan

> **文件修訂 v0.2.3（2026-06-01，drift 清掃）**。清掉 v0.2.2 fold 後的殘留矛盾：開頭 Architecture / scope / File Structure 標題 / Self-Review / Handoff 全部從「4 件」統一成「6 deliverable（核心 4 + Task 3b build_scoreboard + Task 4b face observer）」；runbook step3 face 改走 `face_baseline_observer`（勿用 event observer）；canonical 表 face observer 欄改 Task 4b。**`to_snapshot` 預設 fail-closed**：`run_trusted = bool(run_meta.get("run_trusted", False))`（caller 漏帶 → 視為不可信，杜 fail-open），3 個 trusted-case test 補 `run_trusted=True` + 新增 `test_missing_run_trusted_defaults_failclosed`；全部 dry-run 5 test 綠。
> **文件修訂 v0.2.2（2026-06-01，code-review fold）**。在 v0.2.1 上 fold 進 Roy code review 的 5 finding 修法（全部 dry-run 驗證綠）：F1 snapshot 永遠列 15 能力（未測=insufficient_data）、F2 Layer-0 preflight fail→`run_trusted=False`→`to_snapshot` 覆寫全 grade、F3 face 拆獨立 `face_baseline_observer`（state 流）、F4 demo.yaml canonical=`.claude/`（git-tracked；Roy 建議的 `.agents/` 方向被 `.gitignore:84` 反駁）、F5 dependency_role 入 snapshot；+ completeness critic 的 A2（voice record 轉換）/A4（build_scoreboard 簽名）。
> **文件修訂 v0.2.1（2026-06-01，BLOCKING fold）**。在 v0.2 上 fold 進 4 個 BLOCKING 決定 + 1 個結構發現（見下「2026-06-01 fold」段）。
> **文件修訂 v0.2（2026-05-31，recon-grounded）**。本版把 6 路 file:line 級調查 + grill 收斂的決策 fold 進來。
> **交付的 scope = v0.1（"Baseline-First"，= 選項 B）**：量測框架 6 個 deliverable（核心 4 + build_scoreboard + face observer）+ Layer-0 Preflight gate + 設計/runbook。**不**做 Brain runtime gate / Studio UI / 換模型（v0.2 / v0.3）。
> **性質**：這是「**讓 baseline 可以被量出來的工程計劃**」，不是 baseline 結果報告。今天的實機只證明「感知 lane 可起、資源健康、topic 會發」，**不能**宣稱任何能力 pass/fail。

> **For agentic workers:** 工具中立——用 TDD；可選擇每個 task 派 fresh subagent/worker 實作、task 間 review。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先跑出可信的能力 baseline 數據（pass / degraded / fail / insufficient_data），用來決定哪些能力允許進 6/18 demo 主線——不在這一版把 Brain 自動 gate、Studio UI、CLI JSON、ROS health publisher 全做完。

**Architecture:** v0.1 = **6 個 deliverable**（核心 4 件：schema / grader / 聚合器 / gesture-object observer；＋ Task 3b `build_scoreboard` CLI；＋ Task 4b `face_baseline_observer`）+ Layer-0 Preflight（填既有 `jetson-verify` 的 `demo.yaml` profile）+ 設計/runbook 文件。資料來源分四路：**voice 用現成 `speech_test_observer`**（→ A2 轉 record）；**gesture/object 用 `perception_baseline_observer`（event-only）**；**face 用 `face_baseline_observer`（吃 `/state/perception/face` 連續流，F3）**；**nav.short_move 用 `/event/nav/mission`（partial）、nav.safe_stop/no_auto_resume 標 insufficient 等 BD-7/BD-8**。硬體資源 reuse `benchmarks/core/monitor.py JetsonMonitor`，門檻 check reuse `benchmarks/core/criteria.py GateEvaluator`，per-run schema reuse `benchmarks/core/reporter.py build_result` 範式（**JSONL，非 SQLite**）。聚合件 dev 機可跑、無 ROS 依賴、走 TDD；observer 的純比對邏輯 TDD，ROS node wrapper 在 Jetson 跑。

**Tech Stack:** Python 3 + dataclasses + pytest（純函式）；既有 `benchmarks/`（reporter / monitor / criteria）；`speech_test_observer.py` 的 PASS/MARGINAL/FAIL grading 範式；`jetson-verify` YAML-driven check runner（preflight）。

---

## v0.1 成功定義（最重要，整份 plan 的北極星）

> **v0.1 的成功定義不是「Brain 已經會自動 gate 所有能力」，而是「我們已經有可信 baseline 數據，可以決定哪些能力允許進 demo 主線」。**

不要在 v0.1 同時做量測框架 + runtime gate + UI + CLI + adapter，否則沒有一個會完成。

## 2026-06-01 fold（4 BLOCKING + 1 結構發現，workflow file:line 接地）

1. **skill alias 校正（A 級，會讓 v0.2 runtime 接錯）**：設計段 C 的 7 個 demo skill 名，subagent 雙輪核對 `skill_contract.py`（29 條真實 `SKILL_REGISTRY`）→ 4 個名錯已更正（`sit_down→sit_along`、`approach_short→nav_demo_point`（1.2m 非 0.3/0.5）、`refuse_unsafe→request_backflip`、`answer_fixed_command`→無單一 skill，demo alias →〔chat_reply｜say_canned〕）。
2. **+`dependency_role`（第 5 靜態屬性，design-only）**：CAPABILITY_META + canonical 表加；15 能力各標 `trigger/content/safety_guard/actuation/evidence`。語意=「fail 時依賴它的 skill 怎麼降級」，與 `risk_role` 正交。v0.1 不被 grader 消費。
3. **Brain fail-closed 落點校正（結構發現，推翻 v0.2 草稿）**：`compute_effective_status()`（effective_status.py:26）**已是 runtime 純函式、已吃 `demo_status_baseline`、已輸出 8 態**。v0.2 不造新機制，只**擴既有函式加 grade 分支**。並鎖「四欄不混、不雙真相源」紀律（見設計段 D）。
4. **version_snapshot 補 stale 判（洞④）**：`current_run_meta()` 加 `wsl_dirty/branch/jetson_dirty/manifest_exists/version_stale`（manifest age>6h）。
5. **demo.yaml（洞③ Layer-0）無爭議**：smoke.yaml 現有 9 check（非 plan 原寫 7），搬+補 3，issue #5 獨立做。

## v0.1 → v0.2 改了什麼（recon + grill 收斂）

1. **+Task 4 `perception_baseline_observer`**：recon 證實 face/gesture/object 的 topic 全是 event JSON，**沒有任何 accuracy/false_trigger/latency 是 topic 自帶**，且現有 `verification_observer.py` **只計數、無判定層**。所以「schema/grader/aggregator 做完，第一張 scoreboard 仍只評得到 voice」——必須補 perception observer，視覺三能力才量得到（選項 B）。**（v0.2.2 校正：face 後來證實必須走 `/state/perception/face` 連續流，已拆出獨立 `face_baseline_observer`＝Task 4b；本 Task 4 收斂為 gesture/object event-only。）**
2. **Layer-0 Preflight 從能力降為 top-level gate**：`layer0.preflight=fail → 本次 run 不可信 → 全 capability 維持 insufficient_data，不產 pass/fail`。落地 = 填 `jetson-verify` 既有但 stub 的 `demo.yaml`（不自寫 runner）。
3. **+`claim_level` / `risk_role`（capability 靜態屬性）**：`status(grade)` 是量出來的；`claim_level`/`risk_role` 是作者預先標的。Brain 主線放行 = `grade==pass AND claim_level==mainline`（`claim_level` 只能更嚴、不能放寬）。
4. **+`version_snapshot`（雙 sha）**：Jetson **無 `.git`**，版本靠 `.pawai-last-deploy` manifest（`pawai jetson deploy` 寫）+ WSL commit；baseline runner 在 dev、能力在 Jetson 量 → 必須同記 `wsl_commit` 與 `jetson_install_sha`，mismatch fail-closed。
5. **canonical capability 表正規化**：拆掉 `nav.short_move + nav.safe_stop` 複合列；每列單一能力 + 上述屬性。
6. **recon Known Findings fold 進來（候選，非 pre-baseline fix）**：object whitelist / gesture score-floor / nav 0.85 motion-unverified / studio live / cli CI / wave 雙回應 / doc drift——一律「**baseline fail 後才開修**」。

## Scope（scope 階段 v0.1 / v0.2 / v0.3 邊界）

**v0.1（本 plan，要做）**：6 個 deliverable — 核心 4 件（`scoreboard_schema` / `grader` / 聚合器 `scoreboard` / `perception_baseline_observer` gesture+object）＋ Task 3b `build_scoreboard` CLI ＋ Task 4b `face_baseline_observer`（state 流）；+ Layer-0 Preflight（填 `demo.yaml`）+ canonical capability 表 + `gesture.wave` 事件層協定 + 手寫 dependency map + Brain fail-closed 規則**設計**（不接 runtime）+ 上機 runbook + Known Findings 清單。

**v0.2（不在本 plan）**：`effective_status.py` 補 `capability_health` 分支並接 runtime、`pawai scoreboard --json`、Studio health chip（degraded 第 4 態 / `ScoreChip`）、trace drawer fail reason、perception health publisher、nav / object adapters。

**v0.3（不在本 plan）**：data-driven 修復——見最後「Known Findings」段（gesture confidence floor、WHC A/B、object whitelist、YOLO26s A/B、nav F7、TTS fallback）。

**對齊已鎖決策**：provisional(≥1 樣本，標黃) vs confirmed(≥3 樣本，可標綠)；as-is baseline **必走 demo entrypoint**（裸 `ros2 run` 會拿到錯的 mic_gain / gesture backend / whisper device）；demo skill **手寫 dependency map**；`distance_m` 對 gesture/pose 為人工宣告（`distance_source="manual_declared"`）；demo-day health 用 snapshot（凍結）。

---

## Canonical Capability Table（v0.1 鎖定，15 能力 + 1 前置 gate）

> `layer0.preflight` **不是能力**，是前置 gate（見下節）。`risk_role ∈ {safety_critical, safety_support, actuation, convenience, evidence_only}`。`claim_level ∈ {mainline, studio_only, future, not_claimed}`。`default_status` 在跑 baseline 前一律 `insufficient_data`（除 cli 已有 dev 證據）。`observer_status` = 能不能**現在**產出可評分記錄。
>
> **`dependency_role`（2026-06-01 新增第 5 靜態屬性，design-only，v0.1 不被 grader 消費）** ∈ `{trigger, content, safety_guard, actuation, evidence}`：它與 `risk_role` 正交，回答的是「**這能力 fail 時，依賴它的 demo skill 怎麼降級**」——
> `trigger` fail → 不觸發該 skill（連表情都不做）；`content` fail → skill 仍觸發但內容降級（如 face fail→不叫名字只說「有人來了」）；`safety_guard` fail → 禁 motion；`actuation` fail → 禁該動作；`evidence` fail → 只影響 Studio 顯示，不擋 skill。供設計段 C dependency map 與 v0.2 chain-gating 用（值見 Task 1 `CAPABILITY_META`）。

| # | capability_id | depth | claim_level | risk_role | dependency_role | observer_status（誰產記錄）| Brain surface（pass 時）| fallback（not-pass）|
|---|---|---|---|---|---|---|---|---|
| 1 | `face.recognition` | deep | mainline | evidence_only | **content** | ❌ 新 `face_baseline_observer`（Task 4b，state 流）| 問候/識別(speech)，無 motion | 泛稱「有人來了」/ studio |
| 2 | `voice.command` | deep | mainline | convenience | **trigger** | ✅ `speech_test_observer` 現成 | intent→允許 skill + tts | RuleBrain/請重說；degraded 不 motion |
| 3 | `voice.stop` | deep | mainline | convenience（operator_abort）| **trigger** | 🟡 命中率現成；停車反應時間要新 observer | 觸發 stop_move（便利）| **不影響安全**（reactive_stop 獨立）|
| 4 | `gesture.wave` | deep | mainline | convenience（emote）| **trigger** | ❌ 新 observer（confidence hardcode 1.0 無鑑別力）| wave→emote(api 1016)/招手 | studio_only 顯示，不觸發 |
| 5 | `object.cup` | deep | mainline | evidence_only | **content** | ❌ 新 observer（無人訂 `/event/object_detected`）| remark(tts) | studio 顯示/不口頭 |
| 6 | `nav.safe_stop` | deep | mainline | **safety_critical** | **safety_guard** | ❌ recorder `_cb_reactive_status` no-op（BD-7）| 啟用 motion 護欄（#8 前置）| **FAIL→禁所有 motion/nav** |
| 7 | `nav.no_auto_resume` | deep | mainline | **safety_critical** | **safety_guard** | ❌ **BD-8 行為重設計（非只接 recorder）**：現行 `reactive_stop_node.py:307` 離開 danger 自動 `/nav/resume`＝auto-resume，與語意相反 | #8 前置 | **FAIL→禁所有 motion/nav** |
| 8 | `nav.short_move` | deep | mainline | **actuation** | **actuation** | 🟡 `/event/nav/mission` 有 outcome；runs 表 persist 待 BD-7 | 走 0.3/0.5m（需 #6+#7 pass）| F7 未定位前→insufficient |
| 9 | `nav.dynamic_avoidance` | future | future | actuation | **actuation** | —（架構 stop-only，不繞障）| none | 灰/未主張（非 fail）|
| 10 | `pose.basic` | thin | studio_only | evidence_only | **content** | ❌ 新 observer | studio 顯示 +「我在幹嘛」語境，無 motion | studio-only |
| 11 | `pose.fall` | future | future（debug_only）| evidence_only | **evidence** | ❌ 新 observer | none | studio 紅 alert，不 TTS/不停車 |
| 12 | `brain.skill_gate` | deep | mainline | **safety_critical** | **safety_guard** | 🟡 340 offline tests（historical_evidence）；on-device harness 要新 | gate：放行/擋 skill | **FAIL→Brain 全面 fail-closed** |
| 13 | `brain.trace` | deep | mainline | evidence_only | **evidence** | 🟡 `ros2 topic echo /brain/conversation_trace` 可量；completeness scorer 要新 | studio trace drawer | trace 節點少（RuleBrain 只 1 條）|
| 14 | `studio.evidence` | deep | mainline | evidence_only | **evidence** | ❌ 要 Jetson live smoke（live path 零自動覆蓋）| n/a（顯示層）| 主張轉弱 / 部分 mock |
| 15 | `cli.readiness` | thin | not_claimed | safety_support | **evidence** | ✅ 139 tests（dev 跑，未進 CI；1 紅燈）| none | 手動 ops |

> **claim_level / risk_role 放哪層（我編碼的微決策，Roy review 可否決）**：兩者是 capability **靜態屬性**（存 `CAPABILITY_META`，見 Task 1），**不進每筆 `CapabilityResult` record**；聚合器在 snapshot 把它們附到每個 capability，並 derive `brain_allowed = (grade=="pass" and claim_level=="mainline")`。

### `brain.skill_gate` 的 historical_evidence（非本輪 status）
`default_status=insufficient_data`；`historical_evidence="340 offline tests pass (pawai_brain/test/, mock LLM)"`。本輪 on-device baseline 跑過 safety-block scenario 才可變 pass。

---

## Layer-0 Preflight（top-level gate，不是 capability）

> `layer0_preflight=fail → 本次 baseline run 不可信 → 全 capability 維持 insufficient_data，不產 pass/fail`。只有 `pass / pass_with_warnings` 才開始量能力。
> **落地不自寫 runner**：`jetson-verify` 的 `demo.yaml` profile 目前是 stub（`checks: []` → `verify.py` `sys.exit(2)`）。把 `smoke.yaml` 已驗證的 check 搬過去 + 補 3 個。8 項裡 5 項現成。

| check | pass | degraded | fail | hard-blocker? | 現成來源 |
|---|---|---|---|---|---|
| `jetson.ssh_reachable` | 可達 | — | 不可達 | **YES（全域）** | ✅ `main.py:348` doctor SSH echo / `shell.ssh_args` |
| `go2.ethernet_ping` | 0% loss & <5ms | jitter/間歇 | loss/不可達 | **YES（nav/motion + megaphone-voice）；純 vision 否** | ✅ `network.py:64` `jetson_ping_go2` |
| `ros.runtime_started` | 該 lane expected node set 全 alive | 部分 | 0 nodes | **YES（冷機不能量）** | 🟡 補：`smoke.yaml` ros2.daemon/topic_count + node-count gate |
| `demo.entrypoint_started` | 走 demo script（gateway 8080 / tmux `demo:` session）| bare `ros2 run` | 沒起 | **YES（Q3 鐵律）** | ✅ `network.py:290` gateway_8080 / `status.py:47` has_demo |
| `go2.driver_alive` | webrtc subscriber ≥1 | webrtc degraded | 無 driver | **capability-conditional**（motion/Go2-TTS 要；純 vision 否）| 🟡 補：`smoke.yaml module.go2.webrtc_subscriber`（語意正向）|
| `topic_contract_ok` | 0 FAIL,0 WARN | 0 FAIL, WARN 落在受測能力 path | 任一 FAIL on-path | **conditional** | ✅ `pawai contract check --jetson` |
| `resource_idle_snapshot` | RAM headroom ≥0.8GB & temp<70°C | 0.5–0.8GB / 70–80°C | <0.5GB / >80°C / throttle | **fail 才 block** | ✅ `smoke.yaml` system.memory/disk/gpu_temp + JetsonMonitor |
| `version_snapshot` | 記到 `{wsl_commit, wsl_dirty, branch, jetson_install_sha, deploy_ts, sync_method, manifest_exists, version_mismatch, version_stale, run_id, demo_profile_env}` | `wsl_dirty` / `version_stale`（manifest age>6h，標註）| 取不到版本（無 manifest→`version_mismatch=True`）| **fail 才 block；mismatch/stale 標註不 block** | 🟡 補：讀 `.pawai-last-deploy`（`status.py:11`）；`version_stale` 由 manifest `when` age 判（`current_run_meta(stale_after_h=6)`）|

**lane-aware expected node set**（`ros.runtime_started` 判定依此；node 真名，非檔名）：
```text
vision-baseline : realsense + face_identity_node + vision_perception_node + object_perception_node
voice-baseline  : stt_intent_node + tts_node + conversation_graph_node ﹝interaction_executive_node/llm_bridge 視 engine﹞
                  ﹝VAD 是 stt_intent_node 內建 energy VAD，無獨立 vad_node——勿要求﹞
                  ﹝go2_driver 只在 megaphone TTS 才需﹞
nav-baseline    : sllidar_node + go2_driver_node + twist_mux + reactive_stop_node
                  + nav_action_server_node + state_broadcaster_node + capability_publisher_node + depth_safety_node
                  + Nav2 core(controller/planner/bt/behavior/smoother/velocity_smoother/waypoint_follower) + amcl + map_server
```

**`topic_contract_ok` 的 2 WARN 裁定（今日實機）**：`/state/executive/brain`(planned/未實作) + `/executive/status`(legacy，被 `/state/pawai_brain` 取代) 都是 off-path 孤兒 → **pass_with_warnings = GO**，WARN 進 Known Findings（contract 清理），不阻 baseline。

**`version_snapshot` 雙-sha fail-closed**：`wsl_commit`(dev `git rev-parse`) 與 `jetson_install_sha`(`.pawai-last-deploy.git_sha_full`) **mismatch → 警告**（範本 `status.py:286-296`）。裸 `~/sync once` 不更新 manifest → 標 stale，由 manifest `when` age 判。

---

## 四文件結構（2026-06-01 拆檔）

本 plan 已從 1375 行單檔拆成 4 份，本檔降級為**總控 / 架構決策 / index**：

| 文件 | 路徑 | 放什麼 |
|---|---|---|
| **Master Plan（本檔）** | `docs/pawai-brain/plans/2026-05-31-capability-baseline-scoreboard-plan.md` | goal / scope / 6 deliverable / Layer-0 Preflight / 15 能力 canonical 表 / 三軸定義 / dependency map / fail-closed 設計 / Known Findings / issue 入口 |
| **Capability Baseline Spec** | `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md` | 15 能力逐功能 9+1 問（門檻數字的**唯一真相源**）|
| **Scoreboard Implementation Plan** | `docs/pawai-brain/plans/2026-06-01-scoreboard-implementation-plan.md` | 6 deliverable 的 TDD skeleton（test→impl→commit）|
| **Baseline Runbook** | `docs/runbook/2026-06-18-baseline-runbook.md` | 上機跑 baseline / JSONL / snapshot freeze / demo 當天用 |

> **drift 防線**：門檻數字只在 Spec、code 結構只在 Implementation、上機步驟只在 Runbook。本檔不重複這三者，只放架構決策與 index。

### 6 deliverable（實作見 Implementation Plan）

| File | 責任 |
|---|---|
| `benchmarks/core/scoreboard_schema.py` | `CapabilityResult` + `CAPABILITY_META`(含 dependency_role) + `current_run_meta()`(雙-sha + layer0→run_trusted) |
| `benchmarks/core/grader.py` | 四段 grade + `brain_allowed` |
| `benchmarks/core/scoreboard.py` | 聚合器：snapshot 遍歷全 15 能力(F1) + preflight-fail 覆寫(F2) + dependency_role(F5) |
| `benchmarks/core/perception_baseline_observer.py` | gesture/object（event-only）|
| `benchmarks/core/face_baseline_observer.py` | face（`/state/perception/face` 連續流，F3）|
| `benchmarks/core/build_scoreboard.py` | CLI thin wrapper（runbook 用）|
| `.claude/skills/jetson-verify/profiles/demo.yaml` | Layer-0 Preflight 8 check（canonical=`.claude/`，git-tracked；`.agents/` 是未追蹤舊鏡像）|

## 設計段 C：手寫 demo skill → capability dependency map（非 TDD code，供 v0.2 fail-closed 用）

> demo skill 手寫 dependency map（不用 executor 種類自動粗推）。**安全依賴明確標 safety_critical**。
> **2026-06-01 校正（subagent file:line 雙輪核對）**：skill name **一律用 `interaction_executive/interaction_executive/skill_contract.py` 的真實 `SKILL_REGISTRY` name**（29 條），不得自創。原 v0.2 草稿 4 個名錯已更正；非單一 skill 的 demo 段落明標「〔demo 段 alias〕」。`demo_status_baseline`（skill_contract.py:77-80，5 值 enum）是 skill 層既有的靜態 demo gate，與此 capability dependency map **分屬兩層、不可雙真相源**（見設計段 D）。

| demo 段（alias）| 真實 skill（skill_contract.py）| 依賴 capability（全 pass 才允許進主線）|
|---|---|---|
| 熟人問候 | `greet_known_person`（:349, emote 1016）| face.recognition + voice.command(TTS) |
| 回應固定指令〔alias〕| `chat_reply`（:199）or `say_canned`（:211）| voice.command |
| 揮手回應 | `wave_hello`（:247, emote 1016）| gesture.wave |
| 物件提醒 | `object_remark`（:432）| object.cup + voice.command(TTS) |
| 坐下陪伴 | `sit_along`（:263, StandDown 1005）| voice.command |
| 短距移動 | `nav_demo_point`（:450, goto_relative **1.2m**, requires_confirmation, baseline=`explain_only`）| nav.short_move + **nav.safe_stop + nav.no_auto_resume（safety_critical，硬性前置）** |
| 拒絕危險動作 | `request_backflip`（:405, 觸發→IE `validate()` 發現 backflip→1301 BANNED→必 reject）| brain.skill_gate（deterministic，恆可用）|

> **修正紀錄**：`sit_down`→`sit_along`、`approach_short`→`nav_demo_point`（注意是 1.2m 非 0.3/0.5m）、`refuse_unsafe`→`request_backflip`、`answer_fixed_command`→無單一 skill（demo alias →〔chat_reply｜say_canned〕，依 intent 決定）。`greet_known_person`/`wave_hello`/`object_remark` 三者本就正確。
> **`voice.stop` 不在任何 skill 的安全依賴鏈**：它是 operator_abort/convenience，motion 安全一律由 `nav.safe_stop / nav.no_auto_resume / reactive_stop / 物理 e-stop` 保證，與「狗有沒有聽到『停』」無關。

---

## 設計段 D：Brain fail-closed 規則設計（v0.1 只設計，不接 runtime）

> **2026-06-01 結構校正（subagent file:line 證實，推翻 v0.2 草稿假設）**：Brain fail-closed **不是要新造機制**。`pawai_brain/pawai_brain/capability/effective_status.py:26 compute_effective_status(skill, world)` **已是 runtime 純函式、已在跑**，已透過 `registry.py:72 baseline=contract.demo_status_baseline` 消費 skill 層 demo gate，已輸出 **8 態**（`disabled / studio_only / explain_only / cooldown / defer / blocked / needs_confirm / available`）。它真正缺的不是「health 維度不存在」，而是 **input 沒有 scoreboard 的 `grade` / `brain_allowed`**（現 `WorldFlags` 只有 `tts_playing/obstacle/nav_safe`）。
>
> **v0.1 = 只寫規格（本段）；v0.2 = 擴既有函式**：在 `WorldFlags`（或新 `CapabilityHealth` 參數）加 `capability_grade / brain_allowed / failure_reason`，**在既有 first-match 鏈插一個 grade 分支**，並補單測。**不另造平行 gate**（否則與既有 8 態邏輯衝突）。

**四欄四問——不可混、不可雙真相源**（這是本段最重要的紀律）：

| 欄位 | 在哪層 | 回答什麼 |
|---|---|---|
| `demo_status_baseline` | skill 層（skill_contract.py:77）| 這 **skill** demo 本來能不能執行？|
| `claim_level` | capability 層（CAPABILITY_META）| 這 **能力** 6/18 是否主張？|
| `grade` | baseline snapshot | 這 **能力** 量起來是否可靠？|
| `dependency_role` | capability 層（CAPABILITY_META）| 它 fail 時依賴它的 skill 怎麼 **降級**？|

> v0.2 runtime gate 必須**把四者合成**判 skill 最終狀態，不可各自獨立、不可讓 capability 層的 `claim_level` 與 skill 層的 `demo_status_baseline` 各標各的而 drift。Baseline scoreboard 只**提供能力健康資料**，skill 最終狀態仍由擴充後的 `compute_effective_status()` 決定。

**前置（Layer-0）**：`layer0_preflight != pass/pass_with_warnings → 全 capability grade = insufficient_data`，以下規則不啟動。

**v0.2 要插入的 grade 分支規格**（first-match-wins，查依賴 capability 的 `grade`（snapshot）+ `dependency_role`（CAPABILITY_META）；接在既有 disabled / studio_only / explain_only / demo_guide / static_enabled / enabled_when / cooldown 判定**之後**、physical-block（tts_playing / obstacle / nav_safe）判定**之前**；對齊 Spec §7a row 10 完整序列）：

```
對每個 demo skill，取其依賴 capability（設計段 C map）的 grade + dependency_role：
- 任一依賴 grade == "fail":
    - dependency_role == "trigger"      → ("disabled",  f"{cap} FAIL，trigger 不觸發該 skill")
    - dependency_role == "safety_guard" → ("blocked",   f"{cap} FAIL，禁所有 motion/nav")
    - dependency_role == "actuation"    → ("blocked",   f"{cap} FAIL，禁該動作")
    - dependency_role == "content"      → 放行但內容降級（face→不叫名字；object→不口頭，只 studio）
    - dependency_role == "evidence"     → 放行（只影響 studio 顯示）
- 任一依賴 grade in ("degraded","insufficient_data"):
    - dependency_role in ("safety_guard","actuation") → ("blocked", f"{cap} 未達 pass，不准 motion/nav")
    - dependency_role == "trigger"                    → ("disabled", f"{cap} 未達 pass，不觸發")
    - dependency_role in ("content","evidence")       → 放行（只允許 say/表情/顯示，不 motion）
- 所有依賴 brain_allowed == True（grade==pass AND claim_level==mainline）→ 落回既有 8 態流程
注：claim_level != mainline 的 capability（future/studio_only/not_claimed）即使 grade==pass 也不進主線（brain_allowed=False）。
```

demo-day health 來源 = **baseline snapshot（凍結）**，不在 demo 中即時重算（避免 grade 抖動讓 Brain 行為跳變）。

---

## Known Findings（recon 抓到的 root-cause / 風險；**候選，baseline fail 後才開修，非 pre-baseline fix**）

> 紀律：主張能力 as-is baseline，這些不混進 P0 baseline。只有「決定主張該能力 **且** baseline fail」才開修（多屬 v0.3）。

- **object 多類**：`object_perception.yaml:20 class_whitelist=[41,999]` 鎖 cup-only（commit b81cfdd，從未改回）。**但 `object.cup` 本身對齊 6/18 主張、不算壞**；只有要主張 `object.bottle/general` 時才改 yaml 一行 [0,16,39,41,56,60]（注意保留 ≥2 int 避 BYTE_ARRAY 坑）。
- **gesture 靜態誤觸**：MediaPipe Recognizer 無 `score_threshold`（預設 -1=停用）→ 靜態手勢無 confidence floor。**但 6/18 只主張 `gesture.wave`（走 WaveDetector，不同路徑）**；score-floor 修的是靜態手勢（非主張）。
- **nav 0.85 profile motion-UNVERIFIED**：唯一 logged motion 用已否決的 0.75/1.20；sensor-inventory 的「gate-c PASS」已校正為 unbacked（見該 doc + project-status §5/27 校正）。baseline 前不可當 pass。
- **nav recorder BD-7 + no_auto_resume 行為衝突 BD-8**：`recorder_node` 的 `_cb_reactive_status`/`_cb_depth_safety` no-op → `safe_stop` 量不出（BD-7 接 recorder 即可）。**但 `no_auto_resume` 更嚴重——不只量測缺口，是行為定義衝突**：`reactive_stop_node.py:307 _maybe_call_nav_pause` 離開 danger 自動發 `/nav/resume`（=auto-resume），與「停了不自動衝、須等新命令」語意相反；hold_brake mode 又故意不 resume（:33-34），行為不統一。**BD-8 需行為重設計，不是接 recorder 就能過**（獨立 nav workstream）。
- **studio live path 零自動覆蓋**：所有 studio commit 都是 layout/CORS fix，無一次乾淨 Jetson e2e 紀錄 → `studio.evidence` 必須補一條 live smoke。
- **cli CI 缺口**：139 tests 不在 CI（`.github/workflows` 0 引用）+ 1 常態紅燈（`test_health_brain_passes_jetson_host_env` 測試隔離 bug）+ `demo-preflight` skill 指向不存在的 `scripts/preflight.py`。
- **wave 雙回應（風險非 confirmed bug）**：`event_action_bridge` 也訂 `/event/gesture_detected`，但 `start_full_demo_tmux.sh:99` 會 `pkill event_action_bridge` → 預設不雙發。**preflight 檢查 `event_action_bridge` 不在主線**即可。
- **doc drift**：contract 2 WARN（`/state/executive/brain` planned、`/executive/status` legacy）；測試數膨脹（brain 文件 ~30 實際 340、studio 221 實際 59、object 37 實際 34+1紅）；studio port 8001 vs 8080；brain mode 7 vs 8。場上 debug 會被誤導，列入清理候選。

---

## North Star 對齊（不在本 plan 改 North Star，只記錄）

`docs/mission/2026-06-18-demo-north-star.md §7` 的 `nav.short_move + nav.safe_stop` 複合寫法，與本 plan 拆成 `nav.safe_stop` / `nav.no_auto_resume` / `nav.short_move` 三能力一致（North Star 是 scope 優先級層、本 plan 是量測層，不衝突）。North Star §7 的 F7 前置 caveat 仍有效。**North Star 正文待 ADR amend 時一併同步**，本 plan 不 silent conflict。

---

## Self-Review

**1. Spec coverage**（6 deliverable）：scoreboard_schema → Task 1 ✓；grader(+brain_allowed) → Task 2 ✓；聚合器(+claim_level/risk_role/dependency_role snapshot + F1 全列 + F2 preflight 覆寫) → Task 3 ✓；gesture/object observer（event-only）→ Task 4 ✓；**face observer（state 流，F3）→ Task 4b ✓**；**`build_scoreboard` CLI（A4）→ Task 3b ✓**；Layer-0 Preflight gate → 專段 + `demo.yaml` ✓；canonical 15 能力表 ✓；gesture.wave 協定 → 設計段 B ✓；dependency map → 設計段 C ✓；Brain fail-closed（不接 runtime）→ 設計段 D ✓；上機 runbook（含 A2 voice 轉 record）→ 設計段 E ✓；Known Findings（候選非 pre-fix）✓。砍項（health publisher / Studio UI / full CLI json / nav recorder 深整合 / 換模型）全部不在本 plan ✓。

> **例外（2026-06-01，對齊 Spec §8 `studio.evidence`）**：「Studio UI 砍項」有一個有限例外 ── §8 允許**最小唯讀 scoreboard chip**，只讀 frozen `baseline_snapshot.json`（`GET /api/scoreboard`）；**不包含** live health monitor、即時重算、或 Brain runtime gate 接線。超出此範圍的 Studio health panel / runtime monitor 仍砍。

**2. Placeholder scan**：6 個 deliverable 的 test + 實作皆完整無 TBD；`perception_baseline_observer`/`face_baseline_observer` 的 ROS node wrapper 標「Jetson 跑、保持薄、不在 CI」（純邏輯已 TDD）；`build_scoreboard.py` 標 ≤30 行 CLI（runbook 工具，簽名見 File Structure 段 Task 3b）。

**3. Type consistency**：`CapabilityResult` 欄位 ↔ 聚合器讀的 key（capability_id/pass_fail/false_trigger/latency_ms）一致；`evaluate_round` 產的 dict 欄位 ↔ `CapabilityResult` 子集一致（capability_id/scenario_id/expected_label/predicted_label/pass_fail/false_trigger/confidence/latency_ms/distance_m/distance_source）；`CAPABILITY_META` 的 claim_level/risk_role/**dependency_role** enum ↔ test 斷言一致；`brain_allowed(grade, claim_level)` 簽名在 grader/scoreboard/test 一致；canonical capability_id 全文單一能力（無 `+` 複合）。**2026-06-01 dry-run 驗證**：Task 1 `CAPABILITY_META`（15 能力含 dependency_role）+ `current_run_meta()`（含 version_stale/wsl_dirty/branch/manifest_exists）抽出實跑，4 組新斷言全綠（15 caps / stale-fresh / no-manifest fail-closed / dirty）；`_git` 在非 repo 環境正確降級 "unknown"。

**3b. 四欄不雙真相源（2026-06-01）**：`demo_status_baseline`（skill 層 skill_contract.py:77）vs `claim_level`/`dependency_role`（capability 層 CAPABILITY_META）分屬兩層，v0.2 `compute_effective_status()` 合成判定、不各自獨立（設計段 D）。canonical capability ↔ 真實 skill name（設計段 C，錨 skill_contract.py）已對齊，無杜撰名。

**4. 風險旗標**：Step 0 先確認 `benchmarks/test/` 慣例；`object.cup` baseline 先確認 whitelist=[41] 現況（改 config 屬 v0.3）；`nav.safe_stop` 卡 recorder BD-7（標 insufficient）；**`nav.no_auto_resume` 卡 BD-8 行為重設計（現行 auto-resume 與語意相反，非只接 recorder）**；`nav.short_move` 卡 3 blocker（Brain dispatch IE:278 stub / F7 / 無實機 pass，未達前標 insufficient，且 safety 兩項 pass 前只 dry-run）；version_snapshot 無 manifest → version_mismatch=True（fail-closed）；資源欄位 v0.1 可為 None（JetsonMonitor 整合屬 runbook 手動填）；gesture baseline 必走 recognizer backend（非壓測腳本的 mediapipe）。

---

## Execution Handoff

Plan 完成，存於 `docs/pawai-brain/plans/2026-05-31-capability-baseline-scoreboard-plan.md`。執行方式**工具中立**：用 TDD；可選擇 **(a)** 每個 task 派 fresh subagent/worker、task 間 review，或 **(b)** 本 session 批次執行 + checkpoint review。

（6 個 deliverable：核心 4（schema/grader/scoreboard 聚合器 + gesture-object observer）+ Task 3b `build_scoreboard` CLI + Task 4b `face_baseline_observer`。聚合件純 Python、dev 機可跑、無 ROS 依賴；observer 純邏輯 TDD、ROS node wrapper Jetson 跑。`demo.yaml` preflight profile 是 YAML。設計段 A–E + Known Findings 是文件/runbook。**建議實作序**：Task 1 → 2 → 3（含 F1/F2/F5）→ 3b → 4（gesture/object）→ 4b（face）→ demo.yaml。）
