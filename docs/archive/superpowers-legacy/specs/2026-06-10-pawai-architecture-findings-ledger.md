# PawAI Architecture Findings Ledger（2026-06-10 Phase 1 Audit）

> 本帳本是 `2026-06-10-pawai-architecture-audit.md` 主報告的完整 findings 附錄。
> 產出方式：10 個唯讀子系統 mapper 並行盤點 → 99 條 findings → 每條由獨立對抗性查證員
> 開證據檔逐條核實（98/99 supported；OBJECT-1 部分駁回，已於該條修正）。
> 基線：tag `demo-2026-06-snapshot`（commit `24280ef`）。S1 未錄、6/18 demo 前，
> 標記 MUST_PRESERVE_FOR_DEMO 的項目一律凍結。

## 統計

| 維度 | 分布（OBJECT-1 查證改判後） |
|---|---|
| demo_tag | SAFE_TO_REFACTOR_NOW 32 · POST_DEMO_ONLY 47 · MUST_PRESERVE_FOR_DEMO 13 · NEEDS_HITL 6 · NEEDS_RESEARCH 1 |
| severity | high 26 · medium 57 · low 16 |
| category | fragile_runtime 32 · observability 13 · duplication 11 · missing_tests 10 · dead_code 9 · ownership 8 · overclaim_risk 8 · demo_hack 6 · missing_hitl 2 |

**demo_tag 語意**：SAFE_TO_REFACTOR_NOW = 不影響 S1 補錄與 6/18 demo，現在就能動；
POST_DEMO_ONLY = 6/18 後才能動；MUST_PRESERVE_FOR_DEMO = demo 依賴，逐字凍結；
NEEDS_HITL = 需 Jetson+Go2 上機確認；NEEDS_RESEARCH = repo 內證據不足。

## BRAIN — PawAI Brain（interaction_executive + pawai_brain）

> 勘誤：mapper 報告 SKILL_REGISTRY 為 27 個 skill；實際以 `len(SKILL_REGISTRY)` 驗證為 **30**
> （含 6/10 新增的 move_forward 等，registry 計數測試斷言 30）。其餘 BRAIN 條目不受影響。

### BRAIN-1 — Enable-flag sprawl: ~14 demo gates accreted in brain_node, several mutating class-level gesture maps via instance shadowing

- **分級**：🔴 high · `demo_hack` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — _declare_params (brain_node.py:334-424) declares all ~14 cited gates and _apply_gesture_demo_modes (426-453) instance-shadows _GESTURE_DIRECT/_GESTURE_CONFIRM exactly as claimed; executive.yaml:13-43 holds the frozen 6/10 values, PRD line 7-8/35 calls the flags 症狀繃帶, and snapshot lines 71-84 list each as a demo-only hack.
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:334-424 (_declare_params: gesture_direct_disabled, peace_direct_stretch, thumbs_up_demo_ack, gesture_enabled, stranger_alert_enabled, peace_wego_confirm, demo_video_cup_compound, demo_video_silent_sit_along, greet_require_sitting, demo_phase, idle_*, capability_gate_enabled)
  - interaction_executive/interaction_executive/brain_node.py:426-453 (_apply_gesture_demo_modes mutates _GESTURE_DIRECT/_GESTURE_CONFIRM)
  - interaction_executive/config/executive.yaml:13-43 (frozen 6/10 demo values)
  - docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md:25-35 (PRD admits flags are symptom bandages)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:71-84 (each flag listed as demo-only hack)
- **建議**：Freeze executive.yaml exactly as committed until 6/18. Post-demo, execute PRD Phase 2: collapse all *_enabled/demo_* flags into one declarative policy table read by an InteractionStateMachine; keep per-flag v1 fallback as PRD requires.

### BRAIN-2 — TTS has no request_id/ack — SAY-step completion is a Bool guess with a premature-completion race

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — interaction_executive_node.py:244-253 completes a SAY step after the 0.4s settle whenever tts_playing is False — so synthesis latency >0.4s yields premature completion exactly as described; tts_node.py publishes only Bool /state/tts_playing (1172, 1395-1399) with no request_id/ack anywhere, and PRD row 31 plus executive.yaml:47-48 match.
- **證據**：
  - interaction_executive/interaction_executive/interaction_executive_node.py:244-253 (_active_step_done: after step_settle_s=0.4s, SAY done when `not tts_playing` or 6s timeout — if synthesis latency >0.4s, tts_playing is still False and the step completes before audio starts, letting the next plan's SAY interleave)
  - speech_processor/speech_processor/tts_node.py:1172,1395-1399 (only Bool /state/tts_playing, no id/ack)
  - docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md:31 (PRD row 「我有沒有講出去」靠 bool 猜 — verified accurate)
  - interaction_executive/config/executive.yaml:47-48 (step_settle_s 0.4, tts_idle_timeout_s 6.0)
- **建議**：PRD Phase 3: add request_id to the /tts envelope and a terminal ack topic from tts_node; IE waits on ack with the existing 6s timeout as backstop. Smallest fix; do not retune settle/timeout before demo — recorded takes depend on current timing.

### BRAIN-3 — Arbitration = one active_plan slot + not-active gates copy-pasted into every callback; the 6/9 stranger_alert blackout was patched by disabling the trigger, not the structure

- **分級**：🔴 high · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — _has_active_skill_or_sequence (551-563) is re-invoked in speech (616), gesture (869), face (1225-1227) and object (1383) callbacks; the 6/10 in-code review-blocker comment at 1557-1561 explicitly documents the blackout re-enactment risk, and stranger_alert sits behind a default-false flag (1198-1216, executive.yaml:28) confirmed as 真兇 in project-status.md:13 and PRD:27/34-35.
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:551-563 (_has_active_skill_or_sequence single gate)
  - brain_node.py:616,869,1225-1227,1383 (same gate repeated in speech/gesture/face/object callbacks)
  - brain_node.py:1553-1566 (6/10 review blocker: STEP_FAILED must clear active_plan or one NAV failure blacks out cup/greet/gesture/speech — re-enactment risk explicitly documented in-code)
  - brain_node.py:1198-1216 (stranger_alert branch now behind stranger_alert_enabled=false; executive.yaml:28)
  - references/project-status.md:13 (6/10: stranger_alert 真兇, gate 預設 false)
  - docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md:27,34-35 (root cause: all events contend for one active_plan, first-grab wins TTS)
- **建議**：PRD Phase 1: replace the active_plan dict + scattered gates with an explicit InteractionStateMachine owning a single arbitration point (safety > explicit input > social), with a watchdog on plan lifecycle. 258 IE tests are the regression net.

### BRAIN-4 — LLM skill gating split across two packages with a circular dependency: canonical allowlist in pawai_brain, mirror + execute-mode map only in brain_node

- **分級**：🟡 medium · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Canonical allowlist in skill_policy_gate.py:19-29 is mirrored in brain_node.py:783-793 with the execute/confirm/trace_only map (794-807) existing only there and unguarded by the AST parity test (test_skill_policy_gate.py:87-120, allowlist-only); two-way coupling confirmed — conversation_graph_node.py:458 imports interaction_executive.skill_contract (contradicting its own line-79 comment) while brain_node.py:503 lazy-imports pawai_brain.capability.health_loader, and proposals are gated twice (graph skill_gate + brain_node 703-735).
- **證據**：
  - pawai_brain/pawai_brain/nodes/skill_policy_gate.py:17-29 (canonical LLM_PROPOSABLE_SKILLS)
  - interaction_executive/interaction_executive/brain_node.py:783-807 (mirror set + LLM_PROPOSAL_EXECUTE execute/confirm/trace_only map that exists nowhere else)
  - pawai_brain/test/test_skill_policy_gate.py:88-119 (AST parity test enforces mirror equality — good but the execute-mode map is unguarded)
  - pawai_brain/pawai_brain/conversation_graph_node.py:458 (pawai_brain imports interaction_executive.skill_contract) vs brain_node.py:500-510 (brain_node lazy-imports pawai_brain.capability.health_loader) — two-way package coupling
  - brain_node.py:703-779 (proposal passes gates twice: skill_policy_gate v2 in graph, then allowlist+health+cooldown in brain_node)
- **建議**：Move allowlist + execute-mode policy into skill_contract (SkillContract already has demo_status_baseline/requires_confirmation fields that encode nearly the same info) so both packages read one source; break the import cycle by making pawai_brain depend on interaction_executive only.

### BRAIN-5 — zh translation/TTS-phrase tables triplicated (brain_node / conversation_graph_node / Studio frontend) with sync-by-comment, no parity test

- **分級**：🟡 medium · `duplication` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — All three copies verified: brain_node.py:37-58 (comment declares 3 intentional copies), conversation_graph_node.py:77-99 (comment says canonical is brain_node), and pawai-studio/frontend/components/object/object-config.ts (zh entries at lines 73/183); grep finds no parity test for the tables — only the allowlist has one.
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:37-66 (OBJECT_CLASS_ZH/OBJECT_COLOR_ZH + comment declaring 3 intentional copies)
  - pawai_brain/pawai_brain/conversation_graph_node.py:77-99 (duplicate tables, comment says canonical is brain_node)
  - pawai-studio/frontend/components/object/object-config.ts (third copy per brain_node.py:38-39 comment)
- **建議**：Add a pure-Python parity test (AST or import) asserting the two Python dicts are equal, mirroring test_allowlist_single_source_of_truth. Test-only change, zero runtime/demo impact; frontend copy can be covered by a generated JSON check post-demo.

### BRAIN-6 — Dead code: Executive v0 state_machine.py (303 LOC + 343 LOC test) unused in production; .claude/rules/interaction-executive.md still describes IE as an empty shell built on it; env_builder/context_builder not wired into graph

- **分級**：🟡 medium · `dead_code` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — state_machine.py is exactly 303 LOC and test_state_machine.py 343 LOC; repo-wide grep finds the only import in its own test (the event_action_bridge.py:22 mention is a docstring), .claude/rules/interaction-executive.md still says 「現況：空殼」 with the superseded v0 IDLE→GREETING design, and env_builder.py/context_builder.py exist in pawai_brain/nodes/ but are absent from graph.py:14-25 imports and referenced only in comments (conversation_graph_node.py:300 confirms Phase A.6 dropped env_builder).
- **證據**：
  - interaction_executive/interaction_executive/state_machine.py:1-30 (Executive v0, imported by no production module — grep over all packages finds only test_state_machine.py)
  - interaction_executive/test/test_state_machine.py (343 LOC testing dead code)
  - .claude/rules/interaction-executive.md (states 「現況: 空殼」 and documents the superseded v0 IDLE→GREETING→... design — actively misleads agents)
  - pawai_brain/pawai_brain/graph.py:14-25 (node imports exclude env_builder.py and context_builder.py)
  - pawai_brain/pawai_brain/conversation_graph_node.py:300 (comment: Phase A.6 dropped env_builder)
- **建議**：Delete state_machine.py + its test and rewrite .claude/rules/interaction-executive.md to describe the real brain_node/IE-node split; remove env_builder/context_builder after confirming test-only usage. WSL-only doc/dead-file change; no Jetson redeploy needed before demo.

### BRAIN-7 — One social utterance crosses up to 8 gate/dedup layers spread over 3 nodes, re-synchronized only by broadcast /brain/reset_context; object_remark still depends on the noisy ENGAGED attention gate that greet already abandoned

- **分級**：🟡 medium · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — All 8 cup-path layers verified with exact values (object_perception class_cooldown_sec 5.0 + reset handler, brain_node 1374/1381/1383-1388/1431-1435 with OBJECT_REMARK_DEDUP_S=60, skill_contract object_remark cooldown_s=5.0, attention_machine 1.6m/1.5s dwell), three independent /brain/reset_context handlers confirmed, and the VIS-4 comment (1230-1238) shows greet dropped the ENGAGED gate while _on_object kept it at 1381. Sole imprecision: snapshot:38 says 'near-range and controlled' rather than literally 0.7m — immaterial to the claim.
- **證據**：
  - Cup path: object_perception_node.py:163 (5s class cooldown) → brain_node.py:1374 (demo_phase) → 1381 (attention ENGAGED required: ≤1.6m + 1.5s dwell, attention_machine.py:33-36) → 1383-1388 (active-skill / pending-confirm / tts_playing) → 1431-1435 (60s OBJECT_REMARK_DEDUP_S) → skill_contract.py object_remark cooldown_s=5.0
  - Gesture path: vision min_conf 0.7 + min_votes (references/project-status.md:23) → brain_node.py:849-906 (gesture_enabled → phase → confirm-in-flight → active-skill → 1s dedup → 30s conversation gate + tts_playing) → 929-952 (per-skill cooldown + PendingConfirm 30s/0.5s/5s-live)
  - Reset coordination: brain_node.py:1574-1591 + conversation_graph_node.py:1038-1066 + object_perception_node.py:225,429-432 (three independent reset handlers)
  - Greet dropped its ENGAGED gate for D435 depth noise (brain_node.py:1230-1238 VIS-4 comment) but _on_object kept it — cup line silently requires user ≤1.6m for ≥1.5s; 6/10 cup take was recorded at 0.7m so this held (docs/pawai-demo/2026-06-10-demo-snapshot.md:38)
- **建議**：Do not touch any layer before 6/18 — recorded takes and the retake SOP (reset_context) depend on exact values. Post-demo: centralize dedup/cooldown in PRD layer ① router with one inspectable table, and decide explicitly whether object_remark keeps the ENGAGED dependency.

### BRAIN-8 — Observability gaps: gesture_enabled topic path leaves ros2 param get stale; goal rejections invisible to operator (S1 'no reaction'); brain decisions only inspectable via JSON blobs

- **分級**：🟡 medium · `observability` · **POST_DEMO_ONLY**
- **查證**：✅ supported — _set_gesture_enabled (brain_node.py:318-332) sets only self.gesture_enabled and never writes the declared parameter back; project-status.md:32/42 record the stale `ros2 param get` as known unfixed review finding #4, project-status.md:37 + snapshot:105 record Studio silently returning to idle on S1 goal rejection, and /state/pawai_brain JSON (1593-1627) plus throttled suppress logs (312-315) are the only decision surfaces as claimed.
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:318-332 (_set_gesture_enabled sets python attribute only; never writes back the declared ROS parameter)
  - references/project-status.md:32,42 (6/10 HITL: toggle works end-to-end but `ros2 param get` shows stale — known review finding #4, unfixed)
  - references/project-status.md:37 + docs/pawai-demo/2026-06-10-demo-snapshot.md:105 (Studio silently returns to idle on nav goal rejection — operator saw 'button does nothing' during the failed S1 attempt)
  - brain_node.py:1593-1627 (/state/pawai_brain JSON is the only decision-state surface; suppressed proposals appear only as throttled log lines, brain_node.py:312-315)
- **建議**：Post-demo: write param back via set_parameters in _set_gesture_enabled; add a rejection-reason broadcast (gateway/Studio) per snapshot open item 2; PRD layer ⑤ Trace should make every suppressed proposal a trace event, not a log line.

### BRAIN-9 — Strong unit net (606 pass) but zero cross-node integration coverage; NAV executor enabled-path and SAY-race never tested beyond units

- **分級**：🟡 medium · `missing_tests` · **NEEDS_HITL**
- **查證**：✅ supported — Verified: 258+348=606 tests collected; test_nav_executor.py has 13 tests all using FakeActionClient; test_mini_e2e.py (5 tests) explicitly runs 'without ROS spinning by directly invoking node callbacks' with monkeypatched _pub_tts.publish and no conversation_graph; executive.yaml:3 chat_wait_ms=20000 vs conversation_graph_node.py:573 openrouter_overall_budget_s=5.0 with no test crossing them; demo-snapshot.md:95 forbidden claim and nav_executor_enabled=false default both confirmed.
- **證據**：
  - 258 IE + 348 pawai_brain tests collected, 606 pass in 15.2s on WSL (pytest run 2026-06-10, this audit)
  - interaction_executive/test/test_nav_executor.py (13 tests, fail-closed chain + happy path with mocked action client only)
  - interaction_executive/test/test_mini_e2e.py (5 tests; brain→IE in-process, no tts_node, no conversation_graph)
  - No test exercises brain_node chat_buffer 20s wait (executive.yaml:3) against conversation_graph 5s overall budget (conversation_graph_node.py:573) as one pipeline; no test for the BRAIN-2 premature SAY completion
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:95 (move_forward 'not demo-ready before nav_executor_enabled=true has passed HITL' — that HITL has not happened)
- **建議**：Post-demo: one pytest-level integration harness spinning brain_node + IE-node + fake tts/graph in-process (rclpy single executor) covering chat timeout, SAY race, preemption. NAV enabled-path needs a dedicated Jetson+Go2 session before any move_forward claim.

### BRAIN-10 — Capability health gate exists but is dormant: capability_gate_enabled defaults false and demo config never enables it, so LLM proposals bypass the baseline 'only claim verified capability' defense

- **分級**：🟡 medium · `overclaim_risk` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: brain_node.py:378 declares capability_gate_enabled default False; executive.yaml and all demo scripts/launch files contain zero capability_gate_enabled hits (gate stays off in demo); _capability_health_block (lines 497-523) returns None immediately when gate off, and unmapped-motion fail-close only runs gate-on; demo-snapshot.md:86-97 Forbidden Claims list is doc-level only.
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:378 (declare_parameter capability_gate_enabled False)
  - interaction_executive/config/executive.yaml (no capability_gate_enabled key → default off in demo)
  - brain_node.py:497-523 (_capability_health_block returns None immediately when gate off; unmapped motion skills would fail-closed only if gate were on)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:86-97 (forbidden-claims list is currently enforced by docs + flag discipline, not by this runtime gate)
- **建議**：Leave off for 6/18 (turning it on changes which skills fire). Post-demo, wire the baseline snapshot path and default the gate on, making PRD §③ 'unverified capability shows but never claims' a runtime invariant instead of a documentation rule.

## STUDIO — PawAI Studio（gateway + frontend + backend mock）

### STUDIO-1 — nav_start has no FSM state guard: a /api/nav/start while running/paused_confirm drops the live goal_handle uncancelled

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: nav_start (gateway 524-545) sets state='running' with no state check; _nav_send_goto (502-522) overwrites goal_token and sets goal_handle=None without cancel_goal_async, making the old handle unreachable even for nav_stop; trackB HITL doc lines 44-53 document the single-goal server and 'rejecting goto_* — another goto still active' orphan behavior; nav-control.tsx:109 canStart is the only (UI-side) gate.
- **證據**：
  - pawai-studio/gateway/studio_gateway.py:524-545 (nav_start sets state='running' unconditionally, no check of current state)
  - pawai-studio/gateway/studio_gateway.py:502-522 (_nav_send_goto overwrites goal_token and sets goal_handle=None — old handle reference lost without cancel_goal_async)
  - docs/archive/navigation-legacy/research/2026-06-08-trackB-hitl-results.md (nav_action_server is single-goal; orphaned active goal rejects subsequent gotos)
  - pawai-studio/frontend/components/navigation/nav-control.tsx:109 (only the UI canStart gate prevents this; REST is open to a second window/curl)
- **建議**：Add a gateway-side guard: nav_start returns {ok:false, error:'busy'} unless state in {idle,done}; on legitimate restart, cancel the old handle first. Until 6/18, enforce single-Studio-window operator discipline for S1. Verify orphan consequence on Jetson (NEEDS_HITL for robot-side effect).

### STUDIO-2 — Goal rejection is silent in UI — gateway broadcasts reason='rejected' but NavControl only renders reason in the paused_confirm branch

- **分級**：🔴 high · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: gateway 622-631 broadcasts reason='rejected' with state=idle; use-event-stream.ts:154-168 stores reason into navControl; nav-control.tsx renders navControl.reason only at line 201 inside the isPausedConfirm block (grep confirms no other render site), so idle-state rejected/failed/send_error reasons are invisible; demo-snapshot.md Known Open Item #2 and the S1 row (goal rejected by AMCL covariance gate, nothing visible) both confirmed.
- **證據**：
  - pawai-studio/gateway/studio_gateway.py:622-631 (rejected goal → state=idle, _nav_broadcast_ctrl(reason='rejected') IS sent)
  - pawai-studio/frontend/hooks/use-event-stream.ts:154-168 (nav_control handler stores reason into navControl)
  - pawai-studio/frontend/components/navigation/nav-control.tsx:198-206 (reason paragraph gated on isPausedConfirm; idle renders only '待命' chip — rejection/failure/send_error reasons never shown)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md Known Open Items #2 + S1 row (AMCL covariance gate rejected /nav/goto_relative with nothing visible)
- **建議**：Frontend-only fix in nav-control.tsx: render navControl.reason whenever present (e.g. red chip for reason in {rejected,failed,send_error}). Display-only, no robot path touched, and it directly unblocks the S1 retry loop by showing WHY the goal was refused.

### STUDIO-3 — Blocking wait_for_server(2s) runs on the uvicorn event loop inside async /api/nav/start, freezing all WS broadcasts and endpoints

- **分級**：🟡 medium · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: line 529 calls synchronous self._nav_client.wait_for_server(timeout_sec=NAV_SERVER_WAIT_S) with NAV_SERVER_WAIT_S=2.0 (line 121); async post_nav_start (1146-1150) calls node.nav_start directly on the uvicorn loop; the speech path (1275-1279) contrasts correctly with asyncio.to_thread. The 2s stall only occurs when the server is down, which the finding itself acknowledges.
- **證據**：
  - pawai-studio/gateway/studio_gateway.py:529 (self._nav_client.wait_for_server(timeout_sec=2.0) — synchronous)
  - pawai-studio/gateway/studio_gateway.py:1146-1150 (async post_nav_start calls node.nav_start directly on the loop)
  - contrast: studio_gateway.py:1275-1279 (speech path correctly uses asyncio.to_thread for blocking work)
- **建議**：Wrap node.nav_start/nav_resume in asyncio.to_thread (they are thread-safe by design — _nav_lock). 2s stall per click only bites when the nav server is down, but during S1 that is exactly the failure window where the operator needs a live UI.

### STUDIO-4 — mock_server (backend/) is a live dev twin, not dead code, but has drifted: no /api/nav/* (5 endpoints), no /api/reset, no nav_control WS events

- **分級**：🟡 medium · `duplication` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: mock_server.py full route list (397-895) has no /api/nav/* and no /api/reset; nav_demo scenario (839-893) emits only pose/reactive_stop/paused and grep for nav_control|initialpose returns 0 hits; chat-panel.tsx:255 and use-websocket.ts:60 both POST /api/reset (404 against mock); start.sh boots 'uvicorn mock_server:app' as the default backend; nav-control.tsx:52 GETs /api/nav/control which 404s, leaving navControl null while buttons render.
- **證據**：
  - pawai-studio/backend/mock_server.py:397-895 (full route list — /api/nav/* and /api/reset absent)
  - pawai-studio/backend/mock_server.py:839-893 (nav_demo scenario emits only pose/reactive_stop/paused; grep 'nav_control|initialpose' = 0 hits)
  - pawai-studio/frontend/components/chat/chat-panel.tsx:255 + hooks/use-websocket.ts:60 (POST /api/reset → 404 against mock)
  - pawai-studio/start.sh (mock is the default local boot path); pawai-studio/frontend/components/navigation/nav-control.tsx:52 (GET /api/nav/control 404s → navControl stays null, buttons appear but every POST no-ops silently)
- **建議**：Mock-only change: add stub /api/reset + /api/nav/* and emit nav_control in nav_demo; longer term add a route-parity pytest that diffs FastAPI app.routes of gateway vs mock so drift fails CI. Zero demo-runtime impact.

### STUDIO-5 — Plan A/B toggle is a no-op control surface: _PLAN_MODE has zero consumers, yet UI promises '固定台詞 網斷時的演出腳本'

- **分級**：🟡 medium · `overclaim_risk` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: _PLAN_MODE (gateway 920-922) carries the comment 'brain_node reads via REST or future ROS topic' but repo-wide *.py grep for plan_mode hits only studio_gateway.py and mock_server.py — zero hits in interaction_executive/ or speech_processor/, so nothing behavioral consumes it; navigation-panel.tsx:53-86 shows the Plan A/B toggle promising '固定台詞 / 網斷時的演出腳本'.
- **證據**：
  - pawai-studio/gateway/studio_gateway.py:920-922 ('brain_node reads via REST or future ROS topic' — future never built), 1053-1064
  - repo-wide grep 'plan_mode' (py): only mock_server.py + studio_gateway.py; zero hits in interaction_executive/ or speech_processor/
  - pawai-studio/frontend/components/navigation/navigation-panel.tsx:53-86 (toggle UI with behavioral claims)
- **建議**：Either wire it (publish /brain/plan_mode Bool/String that brain_node consumes like gesture_enabled) or remove the UI; minimum pre-demo step is briefing the operator that the toggle does nothing, since pressing Plan B during a network outage gives false confidence. Removal touches demo UI → after 6/18.

### STUDIO-6 — Map metadata (v8 origin/res/205x98) and DEMO_GOAL hardcoded in frontend; three-place manual sync feeds real /initialpose for AMCL

- **分級**：🟡 medium · `demo_hack` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified: nav-map-canvas.tsx:20-39 hardcodes DEMO_MAP (v8 origin -2.41/-2.81, res 0.05), MAP_W/H 205x98, and DEMO_GOAL with '⚠️ NOT v7' and 'Calibrate to the venue' comments plus an explicit 'update all three' sync warning; lines 15-18 acknowledge the unbuilt /api/map_meta fast-follow; gateway publish_initialpose (470-490) turns clicked coords into a real /initialpose for AMCL, so wrong metadata corrupts localization.
- **證據**：
  - pawai-studio/frontend/components/navigation/nav-map-canvas.tsx:20-39 (DEMO_MAP + MAP_W/H + DEMO_GOAL with '⚠️ NOT v7' and 'Calibrate to the venue' comments)
  - nav-map-canvas.tsx:15-18 (acknowledges gateway /api/map_meta as the unbuilt fast-follow)
  - studio_gateway.py:470-490 (clicked coords become a real AMCL initialpose on the robot — wrong metadata = wrong localization)
- **建議**：Freeze exactly as-is for S1/6-18 (it matches the v8 map in use). Post-demo: gateway /api/map_meta serving origin/res/dimensions parsed from the same map.yaml Nav2 loads, frontend fetches it; goal becomes a gateway param. Eliminates the documented 3-file sync trap.

### STUDIO-7 — Frontend nav math and event routing have zero tests; worldToCanvas/canvasToWorld and yaw-sign logic are module-private and untestable as written

- **分級**：🟡 medium · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: only 2 vitest files in the frontend; worldToCanvas/canvasToWorld (nav-map-canvas.tsx:65-77) are non-exported; two independent yaw negation sites exist (93-94 screenAngle=-yaw, 240-243 atan2(-dy,dx)) and the click-derived yaw flows via /api/nav/initialpose to the gateway's real /initialpose publisher; use-event-stream.ts:128-170 nav/nav_control routing has no test.
- **證據**：
  - pawai-studio/frontend/stores/__tests__/ (only 2 vitest files in entire frontend: state-store.test.ts, reset-conversation.test.ts)
  - pawai-studio/frontend/components/navigation/nav-map-canvas.tsx:64-77 (transforms not exported), 93-95 + 240-244 (two independent y-flip/negation sites for yaw — a sign error here sends a wrong-heading initialpose to the real robot)
  - pawai-studio/frontend/hooks/use-event-stream.ts:128-170 (nav/nav_control routing untested)
- **建議**：Export the pure transforms + a yawFromClick helper, add vitest round-trip tests (world->px->world identity, known v8 corner points, yaw quadrant cases) and a use-event-stream nav_control reducer test. Pure additions, no behavior change.

### STUDIO-8 — GET /api/gesture_enabled returns a gateway-session cache, not brain truth; brain has dual entry (topic + ros2 param) so Studio toggle state can silently desync

- **分級**：🟡 medium · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified: _gesture_enabled_last session cache (studio_gateway.py:233-234, 783-785) and the GET endpoint docstring (1124-1127) explicitly admits it is not brain truth; brain_node has dual write entry (Bool topic sub 238-240 + param callback 254-261) and _publish_brain_state payload (1605-1624) does not include gesture_enabled, so desync is possible. Demo snapshot doc line 75 confirms the toggle's anti-pollution role.
- **證據**：
  - pawai-studio/gateway/studio_gateway.py:233-234,783-785 (_gesture_enabled_last cache, None until first Studio toggle), 1122-1131 (docstring admits 'gateway 端 cache，不是 brain 端真值')
  - interaction_executive/interaction_executive/brain_node.py:235-261,318-319 (two write paths: /brain/gesture_enabled Bool AND ros2 param set; brain does not publish its state back)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md ('gesture_enabled is an operator toggle to prevent gesture pollution' — segment correctness depends on the toggle being truthful)
- **建議**：For 6/18: operate the toggle ONLY through Studio (never ros2 param set mid-recording) and treat null as OFF, as documented. Post-demo: brain_node publishes gesture_enabled into /state/pawai_brain (it already publishes state) and gateway/UI read that instead of caching.

### STUDIO-9 — Brain decision trace evidence is ephemeral: 50-trace / 200-event in-memory ring buffers, no persistence, export, or session grouping — the core gap for Studio v2 'evidence center'

- **分級**：🟡 medium · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: in-memory ring buffers (conversationTraces 50 at state-store.ts:143-146, brainResults 200 at 139-141, MAX_EVENTS=200 at event-store.ts:6); studio_gateway.py has zero file writes so broadcast envelopes are never persisted; trace_shadow merges into the same store (use-event-stream.ts:84-88) distinguished only by the payload engine field; README 'Studio claim 邊界' + provenance badge table confirm the evidence-carrier framing.
- **證據**：
  - pawai-studio/frontend/stores/state-store.ts:143-146 (conversationTraces slice(0,50)), 139-141 (brainResults 200)
  - pawai-studio/frontend/stores/event-store.ts:6 (MAX_EVENTS=200, no persistence)
  - pawai-studio/gateway/studio_gateway.py (no disk logging of broadcast envelopes anywhere; /brain/conversation_trace_shadow merged into the same store, distinguishable only by payload.engine)
  - docs/pawai-brain/studio/README.md 'Studio claim 邊界' + provenance badge table (Studio is an evidence carrier; trusted evidence must come from baseline files — Studio currently cannot replay or export what it showed)
- **建議**：Smallest step: gateway appends every brain:* envelope to a session JSONL (runtime/studio_traces/YYYYMMDD-HHMM.jsonl) keyed by session_id; frontend gets a 'download trace' button. Additive, off the demo critical path, and turns recordings into citable evidence per the README's provenance rules.

### STUDIO-10 — Gateway intent path mislabels provider and duplicates speech-lane classification via sys.path hack

- **分級**：⚪ low · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: sys.path.insert into speech_processor at studio_gateway.py:58-60; provider hardcoded 'sensevoice_cloud' at 1303 even though ASR_URL is env-overridable via PAWAI_ASR_URL (69-72); 'text_input' provider on /ws/text (at 1235, finding cites 1237 — trivial offset); independent asr_client.py exists beside the speech lane.
- **證據**：
  - pawai-studio/gateway/studio_gateway.py:58-60 (sys.path.insert into speech_processor/speech_processor to import IntentClassifier)
  - studio_gateway.py:1303 (provider hardcoded 'sensevoice_cloud' even when PAWAI_ASR_URL points elsewhere), 1237 (provider 'text_input' on /ws/text)
  - pawai-studio/gateway/asr_client.py (independent ASR HTTP client beside the speech lane's provider chain)
- **建議**：Post-demo: derive provider from the actual ASR endpoint response/config, and package intent_classifier as a shared pure-Python module (or publish raw text to the speech lane) so there is one intent vocabulary. Pre-demo the dual path is load-bearing for laptop-mic Studio收音 — do not touch.

## CLI — PawAI CLI（tools/pawai_cli）

### CLI-1 — deploy prefers unaudited ~/sync over built-in safe rsync — deleted Jetson .env (HITL-confirmed 6/10)

- **分級**：🔴 high · `fragile_runtime` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: main.py:512-518 blindly prefers an executable ~/sync with no exclude contract while the .env/.ssh/node_modules excludes exist only in the fallback rsync (521-544); references/project-status.md 6/10 HITL confirms the .env deletion and the manual-rsync workaround; troubleshooting F3 documents precedence as a feature; usage-guide §2.5 overclaims; test_cli.py:785-821 patches Path.home so only the fallback path is tested and no test covers the precedence branch.
- **證據**：
  - tools/pawai_cli/pawai_cli/main.py:512-517 (sync_once = Path.home()/'sync'; if executable, used blindly with no exclude contract)
  - tools/pawai_cli/pawai_cli/main.py:521-544 (the safe exclude list — .env/.env.*/.env.local/.ssh/node_modules/build/install — exists ONLY in the fallback built-in rsync)
  - references/project-status.md:31 (6/10 HITL: 'CLI 的 ~/sync once 沒排除 .env/node_modules，會刪 → 繞過'，team now deploys via manual rsync)
  - docs/pawai_cli/troubleshooting.md:385-388 (F3 documents the precedence as a feature)
  - docs/pawai_cli/usage-guide.md §2.5 (claims '.env/.ssh 不會被推上 Jetson' — guarantee only holds on the fallback path)
  - tools/pawai_cli/tests/test_cli.py:785-821 (excludes tested only for built-in rsync; line 800 patches Path.home to bypass ~/sync — no test guards the precedence branch)
- **建議**：Invert precedence: built-in safe rsync is default; ~/sync only via explicit --sync-script flag, and refuse it unless it provably excludes .env*/node_modules (grep its content or wrap with --exclude args). Add a regression test for the precedence branch. Fix usage-guide §2.5 overclaim.

### CLI-2 — demo start can report fake success — lock transitions to running on start.sh rc alone; Jetson-side .env CRLF path unprotected

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: main.py:899-919 transitions the lock to running and prints '✓ Demo running' on start.sh rc==0 alone (_invoke_start_sh just streams, no remote tmux/process check); start_full_demo_tmux.sh:25-29 raw-sources $WORKDIR/.env with no CRLF normalization under set -euo pipefail; _load_env_file (main.py:24-46) CRLF/BOM defense covers only the local dotenv load; the fake-success incident is HITL-documented in CLAUDE.md (6/4).
- **證據**：
  - tools/pawai_cli/pawai_cli/main.py:899-919 (rc==0 → transition_if_owned('running') → '✓ Demo running'; no remote tmux/process verification)
  - scripts/start_full_demo_tmux.sh:21-38 (raw `source $WORKDIR/.env` on Jetson, no CRLF normalization)
  - tools/pawai_cli/pawai_cli/main.py:24-45 (_load_env_file CRLF+BOM defense covers only the LOCAL dotenv load, mirrors PR #67)
  - CLAUDE.md §Demo 啟動/.env 環境陷阱 (6/4 HITL: CRLF .env silently aborted start_full_demo_tmux.sh, tmux never spawned, `pawai demo start` still printed '✓ Demo running'; documented operator workaround = tmux ls + count processes)
- **建議**：After start.sh returns 0, SSH-verify the expected tmux session exists (demo / nav-cap-demo, names already in the lock at lock.py:33) before transitioning to running; on miss, fail loudly. Add CRLF normalization (sed -i 's/\r$//' or `set -a; source <(tr -d '\r' ...)`) to the Jetson-side .env source in start_full_demo_tmux.sh.

### CLI-3 — 144 CLI tests exist but run nowhere — not in CI Fast Gate, not in pre-commit

- **分級**：🟡 medium · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: ros_build.yaml Fast Gate pytest invocations cover speech_processor/vision_perception/benchmarks/pawai_brain only (pawai_cli appears solely in the new-file flake8 step), git-pre-commit.sh has no pawai_cli reference, and tools/pawai_cli/tests has exactly 6 files with 144 test functions (87+23+16+10+5+3) totaling 2151 LOC.
- **證據**：
  - .github/workflows/ros_build.yaml:44-91 (Fast Gate pytest list: speech_processor/vision_perception/benchmarks/pawai_brain only — no tools/pawai_cli)
  - scripts/hooks/git-pre-commit.sh (no pawai_cli/tools reference; grep empty)
  - tools/pawai_cli/tests/ (6 files, 144 test functions: test_cli 87, test_network 23, test_lock 16, test_platform 10, test_readiness 5, test_cache 3; ~2151 LOC)
- **建議**：Add a third pytest invocation `pytest tools/pawai_cli/tests` to ros_build.yaml Fast Gate (pure-Python, deps = click + python-dotenv only). One-line CI change; protects the 5/14-hardened lock/platform/IP behaviors v2 must not regress.

### CLI-4 — pawai demo school: hardcoded recruitment-demo content + direct robot actuation embedded in ops CLI (event passed 5/16)

- **分級**：🟡 medium · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: main.py:969-1064 contains SCHOOL_DEMO_ENDING_TEXT, FINGER_HEART_API_ID=1036, and an inline python -c rclpy publisher publishing /webrtc_req + /tts explicitly bypassing brain; docs/pawai_cli/README.md documents it as 5/16 school-demo tooling; the 6/10 demo snapshot scope is S1-S5 only with no school-demo mention; the DDS one-shot-pub race rationale is documented at main.py:995-1009 as the recommendation cites.
- **證據**：
  - tools/pawai_cli/pawai_cli/main.py:969-1064 (SCHOOL_DEMO_ENDING_TEXT literal, FINGER_HEART_API_ID=1036, ~50-line inline rclpy publisher composed as a python -c string publishing /webrtc_req + /tts, bypassing brain)
  - docs/pawai_cli/README.md:372-388 (documents it as 5/16 school-demo tooling; not part of the 6/18 S1-S5 flow per docs/pawai-demo/2026-06-10-demo-snapshot.md §Snapshot Scope)
- **建議**：Extract the wait-for-subscriber-then-publish rclpy pattern into a reusable scripts/ helper (it solves a real DDS one-shot-pub race, documented at main.py:995-1009), then delete the school-specific command and content from the CLI in v2.

### CLI-5 — Lane-blind cleanup: orphan-driver preflight and no-lock stop always run brain cleanup — nav-cap-demo session not in its kill list

- **分級**：🟡 medium · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: orphan preflight (main.py:830,844) and no-lock demo stop (main.py:933) unconditionally call _invoke_cleanup_sh (brain cleanup); cleanup.sh:46-49 kills only pawai_brain/studio_gw/demo/llm-e2e tmux sessions (nav-cap-demo absent); lane routing via _cleanup_for_lock (main.py:739-742) only runs when a lock exists; status.py:52-53 indeed has has_nav_capability for the proposed fix.
- **證據**：
  - tools/pawai_cli/pawai_cli/main.py:829-847 (orphan preflight calls _invoke_cleanup_sh() = brain cleanup, regardless of --nav lane being started)
  - tools/pawai_cli/pawai_cli/main.py:931-934 (demo stop with no lock present → brain cleanup only)
  - .claude/skills/brain-studio-lane/scripts/cleanup.sh:46-49 (kills pawai_brain/studio_gw/demo/llm-e2e tmux sessions only — nav-cap-demo absent)
  - tools/pawai_cli/pawai_cli/main.py:739-742 (_cleanup_for_lock routes correctly ONLY when a lock with lane exists)
- **建議**：When no lock exists, detect which sessions are alive (status.py:52-53 already has has_nav_capability) and route/run both cleanups, or prompt for lane. Smallest fix: orphan-preflight + no-lock stop also invoke nav cleanup when `tmux ls` shows nav-cap-demo.

### CLI-6 — modules.py duplicates tmux pane/session naming truth from lane scripts; pawai logs masks missing panes

- **分級**：🟡 medium · `duplication` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: modules.py:19-107 hardcodes pane targets (demo:face, demo:vision, nav-cap-demo:nav_action, pawai_brain:conv_graph), packages, and doc paths while start_full_demo_tmux.sh independently names windows (face/vision/object/asr/tts/llm/...) with no shared constant; main.py:1235-1237 appends '|| true' to tmux capture-pane and prints '(no output)' making a missing/renamed pane indistinguishable from an empty log.
- **證據**：
  - tools/pawai_cli/pawai_cli/modules.py:26-105 (hardcoded pane targets demo:face/demo:vision/nav-cap-demo:nav_action/pawai_brain:conv_graph + package lists + doc paths)
  - scripts/start_full_demo_tmux.sh and .claude/skills/*/scripts/start.sh own actual window naming — no shared constant
  - tools/pawai_cli/pawai_cli/main.py:1234-1237 (tmux capture-pane ... '|| true' → renamed/missing pane prints '(no output)', indistinguishable from an empty log)
- **建議**：Distinguish 'pane not found' from 'pane empty' in pawai logs (drop `|| true`, check tmux exit code, print actionable hint). Longer term: lane scripts emit a session manifest the CLI reads, killing the drift.

### CLI-7 — pawai readiness depends on a sys.path hack into repo-root benchmarks/ and is undocumented in the CLI manual

- **分級**：🟡 medium · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: readiness.py:105-108 does sys.path.insert(repo_root) then imports benchmarks.core.readiness (repo checkout required); readiness/freeze (readiness.py:69-91, writes artifacts/baseline/frozen/<date>/) is a registered CLI command (main.py:20,161) yet grep 'readiness' across docs/pawai_cli/*.md returns 0 hits and the README §3 command table (lines 124-137) omits it; PRD lines 87-102 confirm the pipx/standalone-install v2 goal.
- **證據**：
  - tools/pawai_cli/pawai_cli/readiness.py:101-108 (sys.path.insert(repo_root) then `from benchmarks.core.readiness import evaluate_readiness` — breaks if CLI is ever installed standalone/pipx, the explicit v2 goal per docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md §4)
  - docs/pawai_cli/README.md:124-137 (command table omits readiness entirely; grep 'readiness' across docs/pawai_cli/*.md = 0 hits)
  - tools/pawai_cli/pawai_cli/readiness.py:69-91 (readiness freeze writes artifacts/baseline/frozen/<date>/ — demo-evidence workflow living undocumented)
- **建議**：Document readiness/freeze in docs/pawai_cli/README.md §3 now (doc-only, safe). In v2, move evaluate_readiness into a shared installable package (or vendor it) so pipx install works without a repo checkout.

### CLI-8 — Demo-critical operational flows still live in loose scripts, not the CLI (object A/B, nav goto/smoke, under-load probe, preflight)

- **分級**：🟡 medium · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: PRD line 88 contains the quoted text; scripts/obj_matrix_cap.py, under_load_probe.sh, lidar_front_sector.py, send_relative_goal.py all exist and grep for them in tools/pawai_cli returns 0 hits; docs/pawai_cli/README.md:341-350 documents nav motion test as raw `ros2 action send_goal`; counter-evidence accurate (face list/enroll/rebuild/test at main.py:1315-1366, readiness group at readiness.py:22, doctor --deep at main.py:399-418).
- **證據**：
  - docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md:88 ('face enroll / object A/B / nav goto / smoke 散在各 script，沒收進 CLI')
  - scripts/obj_matrix_cap.py, scripts/under_load_probe.sh, scripts/lidar_front_sector.py, scripts/send_relative_goal.py (referenced in references/project-status.md:56) — none invoked from tools/pawai_cli (grep obj_matrix/under_load/lidar_front in pawai_cli/*.py = 0 hits)
  - docs/pawai_cli/README.md:341-350 (nav motion test documented as raw `ros2 action send_goal`, not a CLI command)
  - Counter-evidence of what IS in the CLI: face enroll/list/rebuild/test main.py:1310-1366; readiness readiness.py:22; doctor --deep main.py:399-418
- **建議**：Follow PRD §4/§5: add pawai object test / pawai nav goto / pawai smoke wrapping the existing scripts, but hardware-actuating commands must default-off with explicit confirm and reuse the NAV fail-closed envelope; each needs its own HITL gate before being claimed.

### CLI-9 — Installability: clone + venv + editable install only; pipx impossible today because runtime hard-depends on repo-relative files

- **分級**：⚪ low · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: README.md:21-45 documents clone+venv+editable install with Jetson intentionally not installed (line 45); pyproject.toml has only click+python-dotenv deps and a setuptools entry point; runtime hard-codes repo-relative paths (.claude/skills start/healthcheck/cleanup scripts at main.py:642/713-715/727, scripts/ci checker at main.py:1270, modules.py doc paths, benchmarks import at readiness.py:108, git-toplevel repo_root discovery at shell.py:48-55 which already honors a PAWAI_REPO_ROOT override); PRD line 87 acknowledges the clone+WSL requirement.
- **證據**：
  - docs/pawai_cli/README.md:21-45 (install = clone repo, python3 -m venv, uv pip install -e tools/pawai_cli; Jetson intentionally not installed)
  - tools/pawai_cli/pyproject.toml (no packaging beyond setuptools entry point; deps click+python-dotenv only)
  - Repo-coupled runtime paths: .claude/skills/*/scripts/start.sh (main.py:642,713-715,727), scripts/ci/check_topic_contracts.py (main.py:1271), docs paths in modules.py:24-105, benchmarks.core import (readiness.py:108), shell.repo_root() git-toplevel discovery (shell.py:48-55)
  - PRD acknowledges: docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md:86 ('老師/同學電腦要能裝（目前需 clone repo + WSL）')
- **建議**：For pipx v2: split commands into repo-independent (doctor/status/net/lock ops — pure SSH) vs repo-dependent (deploy/demo/docs), and make the latter fail with a clear 'requires repo checkout, set PAWAI_REPO_ROOT' instead of crashing on missing paths.

### CLI-10 — Inventory of 5/14-hardened invariants v2 must not regress (locations catalogued, all code-verified)

- **分級**：⚪ low · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Every catalogued location verified in code/docs: -y≠--force at main.py:603-608/834-839/865-867 and README table 537-545; lane selection 794-799, lock.py lane field line 34, cleanup routing 739-742, nav mode whitelist 745-769 rejecting detour/fallback/amcl/mapping; platform.py sys.exit(10) at 95-102 invoked from cli group 155-158 with macOS+Linux+WSL2 support (35-65) and /mnt/c|d rejection (79-92); CRLF defense main.py:24-45; IP resolution _build_demo_env 652-695 shared by demo start + health brain (719-721), documented README 310-317; lock hardening (transition_if_owned/release_if_owned 101-167, stale thresholds 20-21/170-182, flock+exit-17 53-84, deprecated transition_to/release 86-99/137-142); test_lock/test_platform/test_cli exist in tools/pawai_cli/tests/.
- **證據**：
  - -y ≠ --force: deploy main.py:601-608; demo start orphan path main.py:833-839; lock takeover main.py:864-867; doc table docs/pawai_cli/README.md:537-545
  - Lanes brain/nav_capability: lane selection main.py:794-799; lock field lock.py:34; cleanup routing main.py:739-742; nav mode whitelist rejecting detour/fallback/amcl/mapping main.py:745-769
  - Platform exit 10: platform.py:95-102 sys.exit(10), invoked on every command via cli group main.py:155-158. NOTE: supported = macOS + native Linux + WSL2 (platform.py:35-65), NOT WSL2-only; rejects windows_native, WSL1, and /mnt/c|d repo paths (platform.py:79-92)
  - CRLF defense: main.py:24-45 (_load_env_file BOM strip + CR collapse before dotenv; python-side mirror of PR #67's start.sh/healthcheck.sh protection)
  - IP resolution priority: main.py:652-695 (_build_demo_env: PAWAI_TRUST_ENV_IP=1 > live Tailscale peer detection overrides env with warning > keep env on detect-failure), shared by demo start + health brain (main.py:719-721); documented docs/pawai_cli/README.md:310-317
  - Lock hardening: owner-aware transition_if_owned/release_if_owned lock.py:101-167; stale thresholds starting>10min/running>4h lock.py:20-21,170-182; flock+exit-17 acquire protocol lock.py:53-84; deprecated unguarded transition_to/release still present as footguns lock.py:86-99,137-142
- **建議**：Freeze all listed behaviors until after 6/18. In v2, port them with their tests (test_lock.py/test_platform.py/test_cli.py) as the regression contract; delete deprecated Lock.transition_to/Lock.release as the only allowed lock-module change.

## FACE — Face perception

### FACE-1 — Brain consumes sparse /event/face_identity as a presence-state stream — stranger/attention semantics structurally broken, disabled not fixed

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: brain_node.py:219 subscribes only /event/face_identity (grep confirms no /state/perception/face sub); unknown accumulation at 1186-1218 only advances on a subsequent unknown event; face_identity_node.py emits events solely on transitions (track_started 296-298, track_lost 311-319, identity_stable/changed 559-575 gated on old!=new); face_visible latch at 1171-1175 matches the claim (identity defaults to truthy 'unknown', any non-track_lost event sets True, single track_lost clears, and grep shows no decay path — only set in _on_face, read in _tick_attention); 6/9 root-cause comment at brain_node.py:362-367 and references/project-status.md 6/10 §1 + demo snapshot confirm stranger_alert_enabled=false as the disable-not-fix.
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:219 (subscribes only /event/face_identity, never /state/perception/face)
  - interaction_executive/interaction_executive/brain_node.py:1186-1218 (unknown_face_first_seen accumulation only advances when ANOTHER unknown event arrives)
  - face_perception/face_perception/face_identity_node.py:296-298,311-319,559-575 (events fire only on track_started/track_lost/identity transitions — a steady unknown face with a stable track emits nothing after track_started)
  - interaction_executive/interaction_executive/brain_node.py:1171-1175 (face_visible latch: any event except track_lost sets visible=True; identity defaults to truthy 'unknown'; one track's track_lost clears visibility even if another known track is on-frame; if face node dies the latch never decays)
  - references/project-status.md 6/10 §1 + docs/pawai-demo/2026-06-10-demo-snapshot.md (stranger_alert_enabled=false was the one-line kill for the 6/9 'face hallucination locks brain, cup/greet go dark' bug)
  - brain_node.py:362-367 (comment documents the 6/9 root cause)
- **建議**：Post-demo: brain's presence/unknown logic should consume /state/perception/face (true 10Hz state) with time-windowed evaluation, or face node should emit explicit identity_unknown_stable events. Until 6/18, freeze stranger_alert_enabled=false exactly as-is.

### FACE-2 — face_db hygiene: ghost-identity training, max-over-samples matching makes backup dirs worse than 'centroid dilution', counts-only staleness check, *.png-only glob

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: list_face_images/compute_db_counts (face_identity_node.py:31-51) iterate all subdirs with no blacklist and glob *.png only (line 38); predict_name (393-408) takes MAX cosine over stored sample embeddings (centroid only as fallback), supporting the 'worse than centroid dilution' reading; retrain trigger (163-181) compares PNG counts only so same-count replacement keeps a stale pkl; face/README.md:87-90 manual-enroll flow gives no image-format note; research doc line 15 has the HITL numbers (Roy 舊圖 sim 0.2 → re-enroll 0.73-0.81) and §face_db衛生 (192-195) documents the ghost-identity defect; pawai face list/enroll/rebuild exist at main.py:1315-1355.
- **證據**：
  - face_perception/face_perception/face_identity_node.py:31-51 (list_face_images/compute_db_counts iterate ALL subdirs, no blacklist for _backup/.tmp/old)
  - face_perception/face_perception/face_identity_node.py:393-408 (predict_name uses MAX cosine over all stored sample embeddings, not centroid — a backup dir duplicating Roy's photos creates an equal-sim competing name → identity flapping; the 6/8 research doc's 'dilute centroid' wording understates this)
  - face_perception/face_perception/face_identity_node.py:163-181 (retrain trigger compares per-dir PNG counts only — replacing images with same count silently keeps stale pkl)
  - face_perception/face_perception/face_identity_node.py:38 (glob('*.png') only — README manual-enroll flow docs/pawai-brain/perception/face/README.md:87-90 says 'put 1-3 photos in folder' with no format note; .jpg silently ignored)
  - docs/archive/pawai-brain-legacy/research/2026-06-08-night-vision-brain-research.md:192-195 (documented defect + HITL: stale enrollment dropped Roy sim to ~0.2, re-enroll restored 0.73-0.81)
  - tools/pawai_cli/pawai_cli/main.py:1315-1355 (pawai face list/enroll/rebuild exist as the manual-SOP guard)
- **建議**：Smallest fix: dirname blacklist (skip names starting with . or _, plus 'old*') in list_face_images/compute_db_counts + accept jpg/jpeg + hash-based (not count-based) staleness. Demo period: rely on documented SOP (ls face_db, pawai face rebuild). Greet's single point of failure per research doc §1.18.

### FACE-3 — No camera liveness / frame-staleness guard: D435 death freezes last frame and node keeps publishing 'live' state with fresh wall-clock stamps

- **分級**：🟡 medium · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified in face_identity_node.py: cb_color (383-385) keeps only the latest frame with no receipt timestamp and self.color is never reset to None; tick (494-505) re-runs detection on the cached frame with no age check; state JSON uses stamp=time.time() at publish (633-641). Research doc 2026-06-08 §4 dataflow confirms D435 is the shared upstream for face/pose/object.
- **證據**：
  - face_perception/face_perception/face_identity_node.py:383-389 (cb_color stores latest frame, no receipt timestamp kept)
  - face_perception/face_perception/face_identity_node.py:494-505 (tick re-detects on cached frame indefinitely; no frame-age check, no None-reset)
  - face_perception/face_perception/face_identity_node.py:633-641 (stamp=time.time() at publish — downstream cannot distinguish frozen camera from live feed)
  - docs/archive/pawai-brain-legacy/research/2026-06-08-night-vision-brain-research.md:100-110 (D435 is shared upstream for face+pose+object — single sensor SPOF)
- **建議**：Record last-frame receipt time in cb_color; in tick, if age > ~1s skip detection and publish face_count with a stale/degraded flag (or stop publishing). Carry the image header stamp into JSON for true latency/liveness observability.

### FACE-4 — 604-line legacy duplicate scripts/face_identity_infer_cv.py publishes the SAME topics; contract doc still names it as the current publisher

- **分級**：🟡 medium · `duplication` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — scripts/face_identity_infer_cv.py is 604 lines and publishes the same 4 topics (/state/perception/face, /event/face_identity, debug/compare images); interaction_contract.md:108 still names the script as current publisher and §7.1 (~1104-1106) still says '4/13 後回收' though the package node exists; no launcher references the script (only a pkill in clean_face_env.sh), and demo scripts use ros2 launch face_perception.
- **證據**：
  - scripts/face_identity_infer_cv.py (604 lines, wc -l; publishes /state/perception/face:132 and /event/face_identity:135 — accidental double-publisher risk if run beside the node)
  - face_perception/face_perception/face_identity_node.py:4-5 ('Original script retained as fallback')
  - docs/contracts/interaction_contract.md:108 ('發布者：face_identity_node（現為 scripts/face_identity_infer_cv.py）' — stale, package node has been the publisher since 3/25) and :1105-1106 ('4/13 後回收為 ROS2 package' — already done)
  - no demo script references it: scripts/start_full_demo_tmux.sh:153-156 and scripts/start_face_identity_tmux.sh use ros2 launch face_perception
- **建議**：Move scripts/face_identity_infer_cv.py to scripts/archive/ and fix the two stale publisher references in interaction_contract.md. Zero demo-flow impact (verified: no launcher uses it).

### FACE-5 — Doc/contract drift: frozen thresholds in CLAUDE.md contradict shipped yaml; AGENT.md event schema uses 'identity' while wire format is 'stable_name'; rate claims inconsistent; state-JSON 'mode' field ignores real hold semantics

- **分級**：🟡 medium · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — All four drift items verified: face CLAUDE.md:8 freezes upper=0.35/lower=0.25 vs yaml:23-24 (0.40/0.22, 5/8 tuning); AGENT.md:16 event schema uses 'identity' while node publishes 'stable_name' (contract 379-397 correct); rate claims 10Hz (contract:63) vs 8Hz (conversation_graph_node.py:530, in pawai_brain not interaction_executive) vs ~6.6Hz (README:104) vs tick_period=0.05 default (node:89); 'mode' recomputed from name only at 583-587/626-631 discarding decide_stable_name's hold/stable return, and README:~75 documents a phantom identity_unknown event the node never emits.
- **證據**：
  - docs/pawai-brain/perception/face/CLAUDE.md ('不要改 hysteresis 閾值（upper=0.35, lower=0.25）') vs face_perception/config/face_perception.yaml:23-24 (sim_threshold_upper 0.40 / lower 0.22, 5/8 HITL tuning)
  - docs/pawai-brain/perception/face/AGENT.md event schema field 'identity' vs face_identity_node.py:471-485 (publishes 'stable_name'; docs/contracts/interaction_contract.md:379-397 is correct)
  - rate claims: interaction_contract.md:63 says 10Hz, conversation_graph_node.py:530 comment says 8Hz, README.md:103 says ~6.6Hz debug, code default tick_period=0.05 → 20Hz nominal (face_identity_node.py:89)
  - face_identity_node.py:583-587 and :626-631 ('mode' recomputed as stable/hold from name only, discarding the actual hold/stable mode returned by decide_stable_name:410-447)
  - docs/pawai-brain/perception/face/README.md:73-79 documents an 'identity_unknown' event type the node never emits (only track_started/identity_stable/identity_changed/track_lost)
- **建議**：Doc-only sync now: fix CLAUDE.md threshold rule, AGENT.md field name, README phantom 'identity_unknown' event, unify rate claim as 'per-tick, inference-bound (~5-8Hz measured)'. The mode-field code fix is POST_DEMO_ONLY.

### FACE-6 — Tests cover only 3 pure helpers; tracking lifecycle, hysteresis, train_model, predict_name untested; brain-side tests use doc-shaped payloads, never the real wire schema

- **分級**：🟡 medium · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — face_perception/test contains only test_utilities.py (87 lines, 13 tests: 5 cosine_similarity, 4 bbox_iou, 4 to_bbox); assign_tracks/decide_stable_name/train_model/predict_name have no tests. test_brain_rules.py lines 170/179/338/397 all feed {'identity':..., 'identity_stable'/'stable':...} doc-shaped payloads, never the node's real {'stable_name','event_type'} wire shape, which only works via brain_node.py's defensive or-chain (~1149-1159).
- **證據**：
  - face_perception/test/test_utilities.py (87 lines, 13 tests: cosine_similarity x5, bbox_iou x4, to_bbox x4 only)
  - untested demo-critical paths: assign_tracks event emission (face_identity_node.py:272-323), decide_stable_name hysteresis+grace (:410-447), train_model ghost-identity behavior (:337-379), predict_name (:393-408)
  - interaction_executive/test/test_brain_rules.py:170,179,338,397 feed _msg({'identity': 'alice', 'identity_stable': True}) — the AGENT.md shape, not the actual wire shape {'stable_name','event_type'} the face node publishes; the cross-node contract is exercised only by brain's defensive or-chain parsing (brain_node.py:1149-1159)
- **建議**：Add pure-Python tests for decide_stable_name, assign_tracks (mock _publish_face_event), and train_model with a tmp face_db containing a _backup ghost dir (locks in FACE-2 fix). Add one brain test using the real wire payload shape.

### FACE-7 — Startup fragility: blocking synchronous retrain in __init__, hard RuntimeError crash on empty/missing face_db, unvalidated pickle.load

- **分級**：🟡 medium · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: model load/retrain runs synchronously in __init__ (161-187, re-embedding every PNG before serving); train_model raises RuntimeError on empty db_dir (339-340) and on zero valid embeddings (375-378), killing the node at startup; pickle.load at 164-166 has no schema/version validation (only a 'counts' dict comparison).
- **證據**：
  - face_perception/face_perception/face_identity_node.py:161-187 (model load/retrain runs synchronously in __init__; retrain re-embeds every PNG before node serves anything)
  - face_identity_node.py:339-340,375-378 (train_model raises RuntimeError on empty db_dir or zero valid embeddings → node dies, face tmux pane dead at demo start)
  - face_identity_node.py:164-166 (pickle.load of model_sface.pkl with no schema/version validation — a corrupt/old pkl produces undefined behavior downstream)
- **建議**：Post-demo: degrade to detection-only mode (publish unknown identities) when face_db empty/corrupt instead of crashing; move training fully into enroll/rebuild tooling; add a pkl schema version key. Do not touch before 6/18 — current Jetson face_db is healthy and S2 is recorded.

### FACE-8 — Greet path is entry-event-only and currently held together by demo params; stranger_alert remains one runtime param away from re-enabling an unverified capability

- **分級**：⚪ low · `overclaim_risk` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified: identity_stable fires only on unknown→known per-track transition (558-575; research doc 2026-06-08 §6 confirms event-only design); greet gate at brain_node.py ~1235-1252 (stable + optional sitting window + per-person cooldown); runtime param callback (~255-270) can flip stranger_alert_enabled live; 2026-06-10-demo-snapshot.md lists stranger_alert_enabled=false and greet_require_sitting=false as demo controls and S2 as recorded; baseline-evidence README confirms 'real stranger rejection unverified' and face README Non-Claims exclude stranger claims.
- **證據**：
  - face_identity_node.py:558-575 (identity_stable fires only on unknown→known transition per track — re-greet requires leaving frame / track loss; documented in research doc 2026-06-08 §6 lines 179-182)
  - brain_node.py:1235-1252 (greet gate now: stable + optional sitting window + per-person greet_cooldown_s=20)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md (greet_require_sitting=false and stranger_alert_enabled=false are listed demo-only controls; S2 recorded with this set)
  - brain_node.py:255-265 (runtime param callback can flip stranger_alert_enabled live)
  - docs/runbook/baseline-evidence/2026-06-04-hitl/README.md:25 ('real stranger rejection unverified') + face README.md:22 Non-Claims
- **建議**：Freeze the current param set (stranger off, gesture off outside S4, greet sitting off) through 6/18; demo script must not flip stranger_alert_enabled and must not claim stranger detection — only the recorded greet class is verified.

### FACE-9 — Track churn (45 tracks/2min vs target ≤5) is the unresolved engine behind both stranger false-positives and greet re-fires; yaml tuning is mitigation, root cause is YuNet detection instability

- **分級**：🟡 medium · `fragile_runtime` · **NEEDS_HITL**
- **查證**：✅ supported — Verified: face README documents '45 tracks/2min, 目標 ≤5, 根因是 YuNet 偵測不穩定' (lines ~67 and ~116) plus 無人幻覺/低光/多人 known issues (~113-117); yaml:11-18 shows the mitigation stack with det_score_threshold 0.90→0.35 and min_face_area_ratio 0.02→0.001 vs code defaults (node:77,84); brain_node.py ~363-368 comment ties face hallucination → stranger_alert active-plan lockup (6/9 demo 全黑真兇). NEEDS_HITL recommendation is consistent with the 2026-06-04 baseline evidence.
- **證據**：
  - docs/pawai-brain/perception/face/README.md:67,116 (documented: '45 tracks/2min, 目標 ≤5, 根因是 YuNet 偵測不穩定')
  - face_perception/config/face_perception.yaml:11-18 (mitigation stack: det_score_threshold 0.35, min_face_area_ratio 0.001, track_iou_threshold 0.15, track_max_misses 20, stable_hits 2, unknown_grace_s 2.5)
  - yaml:11-12 det_score_threshold lowered 0.90→0.35 and min_face_area_ratio 0.02→0.001 — this maximizes recall but feeds the hallucinated-track problem that drove the 6/9 stranger_alert lockup (brain_node.py:362-364 comment)
  - README.md:113-115 (known issues: 無人幻覺 / 低光誤判 / 多人追蹤混亂)
- **建議**：Any retune (raise det_score_threshold / min_face_area_ratio, or add per-track min-age before events) requires a Jetson+D435 session with the 2026-06-04 baseline observer to confirm registered_recall stays 1.0. Do not retune blind before 6/18.

## SPEECH — Speech / ASR / LLM / TTS

### SPEECH-1 — No single owner of "what PawAI says" — reply text defined in 5+ places across 4 packages, RuleBrain templates triplicated

- **分級**：🔴 high · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — All 5 text sources verified: intent_tts_bridge_node.py:37-44 (set 1), llm_bridge_node.py:53-62 REPLY_TEMPLATES + ~74-99 SYSTEM_PROMPT + tools/llm_eval/persona.txt (set 2), rule_fallback.py:8-30 with docstring admitting 'copied verbatim from llm_bridge_node' (set 3), skill_contract.py canned SAY texts spanning ~173-653 (set 4), event_action_bridge.py POSE_TTS_MAP/GESTURE_TTS_MAP ~83-102 (set 5); speech README:287 carries the 架構碎片化警示. start_full_demo_tmux.sh pkills event_action_bridge/interaction_router and launches only interaction_executive, consistent with the single-/tts-writer invariant cited in the recommendation.
- **證據**：
  - speech_processor/speech_processor/intent_tts_bridge_node.py:37-44 (template set 1)
  - speech_processor/speech_processor/llm_bridge_node.py:53-69 (REPLY_TEMPLATES set 2) + :73-99 (inline SYSTEM_PROMPT) + tools/llm_eval/persona.txt
  - pawai_brain/pawai_brain/rule_fallback.py:8-30 (set 3, docstring admits 'copied verbatim from llm_bridge_node')
  - interaction_executive/interaction_executive/skill_contract.py:173-653 (canned SAY texts — actual demo content)
  - vision_perception/vision_perception/event_action_bridge.py:72-135 (set 5, demo bridge)
  - docs/pawai-brain/speech/README.md:287 (repo itself flags '架構碎片化警示')
- **建議**：Single utterance module: skill_contract as sole canned-text source + one shared RuleBrain template module imported by both llm_bridge and pawai_brain. Delete intent_tts_bridge templates after migrating run_speech_test.sh harness. Demo runtime already has single /tts writer (IE-node) — preserve that invariant.

### SPEECH-2 — Echo gate stuck-closed: tts_node robot-playback early-returns on WAV conversion failure without resetting /state/tts_playing → mic muted until next TTS

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: gate set True at tts_node.py:1219; _play_on_robot early returns at 1409-1410 and 1422-1423 lack reset (except handler 1427-1428 only covers raises; normal reset lives inside _play_on_robot_audio_track:1461 / _play_on_robot_datachannel:1525); stt_intent_node TRANSIENT_LOCAL sub at :398 latches gate and discards audio at 682-692/755-757; rules file explicitly requires 'early return 必須拉回 tts_playing=False'. Demo-safe claim also checks out: LOCAL_PLAYBACK defaults true in start_full_demo_tmux.sh and _play_locally has a correct finally at 1392-1393.
- **證據**：
  - speech_processor/speech_processor/tts_node.py:1219 (gate set True before synthesis)
  - speech_processor/speech_processor/tts_node.py:1407-1410 and 1419-1423 (early `return` inside _play_on_robot try-block, no _publish_tts_playing(False); exception handler at 1428 only covers raises)
  - speech_processor/speech_processor/stt_intent_node.py:682-692,755-757 (gate is latched TRANSIENT_LOCAL — audio discarded while True)
  - .claude/rules/speech-processor.md ('early return 必須拉回 tts_playing=False' — rule exists, code violates it)
- **建議**：Wrap _play_on_robot body in try/finally that resets tts_playing, or move reset to tts_callback finally. Demo unaffected today only because LOCAL_PLAYBACK=true (start_full_demo_tmux.sh:86) routes through _play_locally which has a correct finally (tts_node.py:1393). Fix after 6/18; do not flip to Megaphone before fixing.

### SPEECH-3 — LLM fallback chain implemented twice byte-for-byte; demo-primary chain has NO local-LLM tier despite docs claiming one

- **分級**：🔴 high · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: llm_client.py:1-9 docstring admits manual mirror of llm_bridge_node.py:542-701; grep for ollama/11434 in pawai_brain is empty while llm_bridge declares local_llm_endpoint :11434 (lines 215-220) and calls it at 479-482; CLAUDE.md and rules file both document a local-LLM tier that the langgraph demo default (start_full_demo_tmux.sh:63) does not have. Minor caveat: the temperature drift (0.8 vs 0.2) is in dataclass defaults only — conversation_graph_node overrides to 0.8 at construction, so runtime values currently match.
- **證據**：
  - pawai_brain/pawai_brain/llm_client.py:1-9 ('Mirrors llm_bridge_node._call_openrouter + _try_openrouter_chain ... :542-701 so behaviour is identical') — manual mirror, no shared module
  - speech_processor/speech_processor/llm_bridge_node.py:542-701 (original)
  - drift already present: llm_bridge temperature default 0.8 (llm_bridge_node.py:202) vs OpenRouterConfig 0.2 (llm_client.py:61)
  - grep ollama/11434 in pawai_brain → zero hits; only llm_bridge has Ollama tier (llm_bridge_node.py:215-220,479-482)
  - CLAUDE.md 'LLM fallback：雲端優先 → 本地 Qwen2.5-0.8B 備援' + .claude/rules/speech-processor.md 'Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain' describe legacy node, not the langgraph demo default (start_full_demo_tmux.sh:63)
- **建議**：Extract one OpenRouter chain client consumed by both nodes (llm_client.py is already ROS-free — make llm_bridge import it). Decide explicitly whether Brain v2 gets a local-LLM tier; until then fix docs: demo offline path = straight to RuleBrain canned, not 'local Qwen'.

### SPEECH-4 — ASR provider naming drift: docs say 'sensevoice_cloud', code provider is 'qwen_cloud'; unknown names silently dropped from provider_order

- **分級**：🟡 medium · `overclaim_risk` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: README.md:255-258 and CLAUDE.md say 'sensevoice_cloud' while code provider_name is 'qwen_cloud' (stt_intent_node.py:66); demo script points it at the SenseVoice server (port 8001, qwen_asr.model_name:=sensevoice at line 187) and uses 'qwen_cloud' in ASR_PROVIDER_ORDER (line 70); _build_provider_order (657-664) silently filters unknown names with fallback ['qwen_cloud','whisper_local'], so a docs-faithful order silently drops the cloud tier.
- **證據**：
  - docs/pawai-brain/speech/README.md:258 ('sensevoice_cloud (RTX 8000, FunASR) → sensevoice_local → whisper_local') and CLAUDE.md ASR 順序 use 'sensevoice_cloud'
  - speech_processor/speech_processor/stt_intent_node.py:66 (provider_name='qwen_cloud'), :618-624 (QwenASRProvider pointed at SenseVoice server, model_name='sensevoice')
  - speech_processor/speech_processor/stt_intent_node.py:657-664 (_build_provider_order silently filters unknown names; empty result falls back to ['qwen_cloud','whisper_local'] — a docs-faithful ASR_PROVIDER_ORDER=['sensevoice_cloud',...] yields an unintended chain with no error)
  - scripts/start_full_demo_tmux.sh:70 (real order uses 'qwen_cloud')
- **建議**：Doc-only fix now: state code name qwen_cloud(=SenseVoice cloud) in README/CLAUDE.md. Post-demo: rename provider to sensevoice_cloud with alias, and make _build_provider_order log+error on unknown names instead of silent filtering.

### SPEECH-5 — stt_intent_node (1209 LOC) has zero direct unit tests — ASR fallback iteration, echo gate, energy VAD, hallucination filter all CI-untested; ASR chain HITL evidence dated 3/29

- **分級**：🔴 high · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: speech_processor/test/ has no test importing stt_intent_node (test_pcm_trim/test_text_normalization cover separate modules; test_intent_classifier has exactly 15 tests); _transcribe_with_fallback (1051-1071), echo gate (666-692), and energy VAD (807-866) exist and are untested; README:255 heading dates ASR fallback validation to 2026-03-29; test_tts_audio_api_only.py contains 1 test. Providers are injectable via the self.providers dict as claimed.
- **證據**：
  - speech_processor/test/ — no test_stt_intent_node.py (15 test files; only pure intent_classifier covered, 15 tests)
  - speech_processor/speech_processor/stt_intent_node.py:1051-1071 (_transcribe_with_fallback — fallback + empty-transcript + degraded flag logic untested)
  - speech_processor/speech_processor/stt_intent_node.py:666-692,807-866 (echo gate + energy VAD untested)
  - docs/pawai-brain/speech/README.md:255 ('ASR 三級 Fallback（2026-03-29 驗證通過）' — predates SenseVoice-local addition / current tuning)
  - test_tts_audio_api_only.py: 1 test is the entire Megaphone-protocol safety net
- **建議**：Add ROS-free tests with fake ASRProvider objects for _transcribe_with_fallback (success/empty/exception/degraded) and a pure echo-gate state test — providers are already injectable via self.providers dict. Adding tests touches no runtime path. Re-HITL the cloud→local ASR transition post-demo.

### SPEECH-6 — tts_node is a 1611-line god-node that blocks its executor for the whole synth+playback duration

- **分級**：🟡 medium · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified: file is 1611 lines; tts_callback (1181-1364) does lane policy, cache, provider chain, and playback inline; time.sleep(duration+tail) at 1459 and 1512 and blocking aplay subprocess.run at 1378-1383 run inside the callback under single-threaded rclpy.spin (main 1590-1607); /tts subscription depth=10 (1163-1165); self_introduce in interaction_executive/skill_contract.py has 3 SAY steps; conflicting openrouter_gemini_timeout_s defaults 60.0 (line 153) vs 6.0 (987-990) confirmed.
- **證據**：
  - speech_processor/speech_processor/tts_node.py:1181-1364 (tts_callback does lane policy + cache + provider chain + playback inline in subscription callback)
  - speech_processor/speech_processor/tts_node.py:1459,1512 (time.sleep(duration+tail) inside callback), :1378-1383 (blocking aplay subprocess)
  - single-threaded spin (tts_node.py:1590-1596) → /tts depth-10 queue; burst SAY skills (skill_contract.py:227-231 self_intro = 3 SAY steps) serialize behind sleeps
  - openrouter_gemini_timeout_s dataclass default 60.0 (tts_node.py:153) vs declared param default 6.0 (tts_node.py:987-990) — two conflicting 'defaults' in one file
- **建議**：Freeze for 6/18 — demo pacing/echo-gate timing was HITL-tuned around this blocking behavior. Post-demo: split provider chain / lane policy / playback into modules (tts_provider.py Protocol is the started seam) and move playback to a worker thread with a serialized queue.

### SPEECH-7 — Dead/legacy provider and node residue: vad_node/asr_node/intent_node unreferenced, MeloTTS class survives its 3/26 deprecation, default provider 'elevenlabs' bricks a bare tts_node

- **分級**：🟡 medium · `dead_code` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: vad_node 353 / asr_node 204 / intent_node 211 LOC with zero references in scripts/tools/.github (speech_pipeline.launch.py itself unreferenced; asr_node/intent_node aren't even in it — case is stronger than stated); TTSProvider_MeloTTS at 292-351 + melo params 959-962 despite rules-file deprecation; provider default 'elevenlabs' (941) with no key → _create_tts_provider returns None → __init__ returns at 892-894 before _setup_communication (def :1161, call :926) so /tts is never subscribed. One inaccuracy: git shows these legacy nodes last touched by 23d1591 (2026-03-28 security fix), not c7179e9 — immaterial to the dead-code claim.
- **證據**：
  - speech_processor/speech_processor/vad_node.py (353 LOC) / asr_node.py (204) / intent_node.py (211) — no start script references them; only consumer is speech_pipeline.launch.py which itself is referenced nowhere (grep scripts/tools/.github = empty); last touched commit c7179e9 (2026-03-15 era)
  - speech_processor/speech_processor/tts_node.py:292-351 (TTSProvider_MeloTTS) + :959-962 (melo params) vs .claude/rules/speech-processor.md 'MeloTTS 已棄用（3/26 決議），不要加回來'
  - speech_processor/speech_processor/tts_node.py:941 (provider default 'elevenlabs') + :892-894 (no API key → __init__ returns before _setup_communication at :1161 — node runs but never subscribes /tts, silent brick)
  - ElevenLabs chain intentionally excluded from runtime chains (tts_node.py:1256 'no ElevenLabs until spike-real GO') — class kept per 5/9 quality-lane spike decision (.claude/rules/speech-processor.md)
- **建議**：Post-demo (any speech_processor edit forces Jetson rebuild of the frozen snapshot): delete vad/asr/intent nodes + speech_pipeline.launch.py + MeloTTS class/params, change provider default to edge_tts, and make missing-provider init fail-loud instead of silently not subscribing.

### SPEECH-8 — TTS cache warmup synthesizes 5 stale legacy phrases at every startup under a cache key that can never hit for the gemini lane

- **分級**：⚪ low · `demo_hack` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: all 5 _WARMUP_PHRASES (1540-1546) match intent_tts_bridge_node reply_templates verbatim; warmup keying (1552-1556: edge_tts_voice if EDGE_TTS else voice_name) mismatches runtime _cache_voice_for (1148-1159: openrouter_gemini → openrouter_gemini_voice), so gemini-lane warmup slots are unreachable; demo default edge_tts keeps keys consistent today. Minor overstatement: 'at every startup' only holds on first startup or cleared cache — warmup's own get/put keys are self-consistent so cached phrases are skipped on later boots.
- **證據**：
  - speech_processor/speech_processor/tts_node.py:1540-1546 (_WARMUP_PHRASES are intent_tts_bridge-era templates — '收到，正在拍照' etc.; current Brain says skill_contract/LLM text instead)
  - speech_processor/speech_processor/tts_node.py:1548-1566 (warmup cache_voice = voice_name unless EDGE_TTS) vs :1148-1159 (_cache_voice_for uses openrouter_gemini_voice at lookup) — provider=openrouter_gemini warms 5 cloud TTS calls into unreachable cache slots
  - demo default provider=edge_tts (start_full_demo_tmux.sh:82) keeps keys consistent today, so impact is latent
- **建議**：Route warmup through _cache_voice_for and source phrases from skill_contract canned texts (the lines actually spoken in demo), or delete warmup — cache makes it near-free only when keys actually match.

### SPEECH-9 — e2e_health_check.sh validates the wrong stack: expects llm_bridge_node + vLLM port-8000, but demo default runs conversation_graph_node + OpenRouter

- **分級**：🟡 medium · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: e2e_health_check.sh EXPECTED_NODES includes llm_bridge_node (line 49) and Layer 0 curls LLM_HEALTH_URL with a port-8000 vLLM tunnel hint (lines 35-44); start_full_demo_tmux.sh:63 defaults CONVERSATION_ENGINE=langgraph which starts conversation_graph_node instead of llm_bridge_node (lines 222-237) yet line ~315 tells the operator to run the stale health check; smoke_test_e2e.sh:26 hard-fails (exit 1) when llm_bridge_node is absent.
- **證據**：
  - scripts/e2e_health_check.sh:49 (EXPECTED_NODES includes llm_bridge_node) and :35-44 (Layer 0 fails when port-8000 vLLM tunnel absent)
  - scripts/start_full_demo_tmux.sh:63 (CONVERSATION_ENGINE default langgraph → conversation_graph_node, llm_bridge not started) and :314 ('Verify: bash scripts/e2e_health_check.sh' — instructs operator to run the stale check)
  - same stale pattern in scripts/smoke_test_e2e.sh:26
- **建議**：Update EXPECTED_NODES to branch on CONVERSATION_ENGINE (conversation_graph_node default) and make Layer 0 check OpenRouter reachability (or skip when OPENROUTER_KEY set). Pure ops-script fix, no runtime node touched — directly de-risks 6/18 preflight.

### SPEECH-10 — Megaphone path fragility is real and HITL-documented: mid-session tts_node restart silent-fails until Go2 driver/robot restart; driver-absent runs silent-fail too

- **分級**：🟡 medium · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified: thesis 5-1-5 documents mid-session tts_node restart → all uploads silent fail with recovery only via driver/Go2 restart; speech README documents driver-absent silent fail; troubleshooting table row exists; tts_node.py finally-block always sends EXIT(4002) + 0.5s cooldown and _send_audio_command publishes raw 4001/4003/4002 WebRtcReq; start_full_demo_tmux.sh:86 defaults LOCAL_PLAYBACK=true.
- **證據**：
  - docs/deliverables/thesis/5-系統限制與可行性分析.md:61 (mid-session restart → all uploads silent fail; only recovery = restart driver or Go2)
  - docs/archive/pawai-brain-legacy/architecture-0511/speech/speech-tts-lanes-megaphone.md:203 (troubleshooting table entry)
  - docs/pawai-brain/speech/README.md:70 (Megaphone silent fail when Go2 driver not running)
  - mitigations in code: EXIT always sent + 0.5s cooldown (speech_processor/speech_processor/tts_node.py:1513-1529); demo sidesteps entirely via LOCAL_PLAYBACK=true (start_full_demo_tmux.sh:86)
- **建議**：Keep LOCAL_PLAYBACK=true as the 6/18 invariant; never restart tts_node mid-session if Megaphone is ever used. Post-demo: move Megaphone protocol ownership into go2_robot_sdk driver (it owns the DataChannel/state machine) so tts_node restarts become safe — tts_node currently speaks raw 4001/4003/4002 via /webrtc_req (tts_node.py:1531-1538).

## VISION — Vision perception（pose + gesture）

### VISION-1 — Backend-dependent gesture vocabulary with no normalization; brain only understands recognizer names — backend swap silently severs palm→system_pause safety path

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: recognizer _GESTURE_MAP emits palm/fist/index/thumbs_up/peace; hands/rtmpose STATIC_GESTURES=(stop,point,fist); brain _GESTURE_DIRECT/_GESTURE_CONFIRM contain only wave/palm/fist/index/thumbs_up/peace (no stop/point anywhere in brain_node), so a hands-path swap emits 'stop' for open palm and the palm→system_pause mapping never fires; contract enum (wave/stop/point/ok/thumbs_up/thumbs_down/victory/i_love_you) matches neither producer; check_topic_contracts.py is report-only and checks topic names only.
- **證據**：
  - vision_perception/vision_perception/gesture_recognizer_backend.py:49-58 (_GESTURE_MAP → palm/fist/index/thumbs_up/peace)
  - vision_perception/vision_perception/gesture_classifier.py:14 (STATIC_GESTURES = stop/point/fist for hands/rtmpose path)
  - interaction_executive/interaction_executive/brain_node.py:818-824 (_GESTURE_DIRECT wave/palm/fist/index; _GESTURE_CONFIRM thumbs_up/peace — no stop/point entries)
  - docs/contracts/interaction_contract.md:487 (contract enum wave/stop/point/ok/thumbs_up/thumbs_down/victory/i_love_you matches NEITHER producer path)
  - scripts/ci/check_topic_contracts.py:1-50 (checker validates topic names only, report-only — enum drift invisible to tooling)
- **建議**：Create one gesture-enum module (single source) imported by both backends, brain, and mock publisher; rewrite contract §4.3 enum to the recognizer vocabulary; have hands-path emit the same names (stop→palm, point→index). Demo is pinned to recognizer so no pre-6/18 change.

### VISION-2 — Shipped defaults (inference_backend=mock + gesture/pose_backend=rtmpose) are a triple footgun: bare launch with use_camera:=true publishes MockInference synthetic pose events as real, and WaveDetector/OK/recognizer never run; entire demo behavior lives only in start_full_demo_tmux.sh overrides

- **分級**：🔴 high · `demo_hack` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified: yaml+launch default to inference_backend=mock + pose/gesture_backend=rtmpose with all 6/10 gates at no-op values (min_conf 0.0, min_votes 1, two_class false); backend==mock instantiates MockInference and _tick falls to result.body_kps when mp_pose is None, publishing synthetic pose; WaveDetector is fed only in the recognizer branch (the else branch never feeds it); demo gate values exist only as start_full_demo_tmux.sh:163-168 launch overrides (yaml comment confirms); demo launch leaves backend=mock so MockInference.infer() runs each tick with its result discarded.
- **證據**：
  - vision_perception/config/vision_perception.yaml:5-6,22-23,35-39 (mock + rtmpose defaults, all 6/10 gates at no-op values)
  - vision_perception/launch/vision_perception.launch.py:18-22 (same defaults)
  - vision_perception/vision_perception/vision_perception_node.py:176-177,293-296 (backend==mock → adapter=MockInference; pose source falls to result.body_kps when mp_pose is None → synthetic keypoints published as real events)
  - vision_perception/vision_perception/vision_perception_node.py:376-398 (WaveDetector fed only in recognizer branch; rtmpose/mediapipe-hands branches at 459-487 never feed it — confirms CLAUDE.md documented footgun)
  - scripts/start_full_demo_tmux.sh:163-168 (the only place demo values exist: pose_backend:=mediapipe gesture_backend:=recognizer pose_two_class:=true pose_min_avg_score:=0.15 sitting_trunk_max_deg:=45.0 gesture_recognizer_min_conf:=0.7 gesture_min_votes:=3)
  - Side-effect: demo launch leaves inference_backend=mock → MockInference instantiated and infer() executed every tick with results discarded (vision_perception_node.py:284-288)
- **建議**：Freeze start_full_demo_tmux.sh:163-168 verbatim until 6/18. Post-demo: flip yaml/launch defaults to the HITL-proven matrix (mediapipe/recognizer + demo gate values), make mock require explicit opt-in (refuse mock+use_camera combination), and skip MockInference when both pose and gesture backends bypass it.

### VISION-3 — interaction_router + event_action_bridge are superseded zombie code (~650 LOC + 380 test LOC) still shipped with entry points and launch files; bridge can publish Go2 motion and double-trigger against brain if accidentally started

- **分級**：🟡 medium · `dead_code` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: contract marks both nodes and all three /event/interaction/* topics deprecated; demo script pkills both and never launches them; brain tmux launches bridge with enable_event_action_bridge:=false and notes router 'intentionally not started'; git log matches (375d57a 2026-03-24, 320d4d0 2026-05-10); setup.py entry_points and both launch files still shipped; bridge publishes to /webrtc_req (GESTURE_ACTION_MAP api_id 1003/1020) and /tts (wave→'Hi！很高興看到你！'). LOC is 652+366 vs claimed ~650+380 — close enough.
- **證據**：
  - docs/contracts/interaction_contract.md:21,75,573 (/event/interaction/* deprecated — 'executive 內部處理')
  - scripts/start_full_demo_tmux.sh:99-100 (demo actively pkills both; never launches them)
  - scripts/start_pawai_brain_tmux.sh:52-53,72-73 (bridge launched with enable_event_action_bridge:=false; router 'intentionally not started')
  - git log: interaction_router.py last touched 2026-03-24 (375d57a); event_action_bridge.py 2026-05-10 (320d4d0)
  - vision_perception/setup.py entry_points still export both; launch/interaction_router.launch.py + launch/event_action_bridge.launch.py still installed
  - vision_perception/vision_perception/event_action_bridge.py:48-52 (GESTURE_ACTION_MAP → /webrtc_req api_id 1003/1020) + 99-101 (wave→TTS) would race brain_node _GESTURE_DIRECT/_GESTURE_CONFIRM if both run
- **建議**：Post-demo: delete both nodes + their launch files + entry points + test_interaction_rules/test_event_action_bridge; fold POSE_TTS_MAP wording into skill_contract if still wanted. Touching setup.py forces a Jetson colcon rebuild of the demo-critical package, so do not do this before 6/18.

### VISION-4 — Module 'rule source-of-truth' docs contradict code: rules forbid removing a fist→ok compat map that was emptied 2026-05-05 (and is now explicitly forbidden in code comments); fallen threshold and contract notes also stale

- **分級**：🟡 medium · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: gesture CLAUDE.md and .claude/rules/vision-perception.md both still say '不要移除 GESTURE_COMPAT_MAP（fist→ok）' while event_builder.py shows the map EMPTIED 2026-05-05 ('routing fist→ok silently corrupted the enum') and gesture_recognizer_backend.py explicitly forbids routing Closed_Fist→ok; contract §4.3 still claims ok comes from Closed_Fist→COMPAT_MAP and '下游收到的一律是 ok' while brain maps fist→enter_mute_mode; pose CLAUDE.md/README state fallen vertical_ratio < 0.4 vs code's N7 5/11 widening to 0.45.
- **證據**：
  - docs/pawai-brain/perception/gesture/CLAUDE.md:9 + .claude/rules/vision-perception.md:13 ('不要移除 GESTURE_COMPAT_MAP（fist→ok）')
  - vision_perception/vision_perception/event_builder.py:10-17 (map EMPTIED 2026-05-05; routing fist→ok 'silently corrupted the enum')
  - vision_perception/vision_perception/gesture_recognizer_backend.py:47-48 ('do NOT route Closed_Fist→ok')
  - docs/contracts/interaction_contract.md:498,506 (still claims ok comes from Closed_Fist→COMPAT_MAP and 'fist 映射為 ok，下游收到的一律是 ok' — false; brain maps fist→enter_mute_mode at brain_node.py:821)
  - docs/pawai-brain/perception/pose/CLAUDE.md:7 + docs/pawai-brain/perception/pose/README.md:73 (fallen vertical_ratio < 0.4) vs vision_perception/vision_perception/pose_classifier.py:157-161 (N7 5/11 widened to 0.45)
- **建議**：Docs-only fix, zero runtime risk: delete the fist→ok preservation rule from both rule files, correct contract §4.3 ok/fist rows, update fallen gate to 0.45 in pose CLAUDE.md/README. These files actively steer AI agents toward reintroducing a known enum-corruption bug.

### VISION-5 — 138 tests are all pure-logic level; the 608-line node pipeline (voting wiring, stable gate, wave bypass, two-class flow, backend matrix) and WaveDetector have zero tests, and 20 of 138 tests don't run in CI

- **分級**：🟡 medium · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: ran pytest myself — 138 passed; CI workflow lists only 7 of 9 vision test files (test_lidar_obstacle_detector + test_obstacle_detector absent = exactly 20 tests local-only, confirmed by running them: 20 passed); no test files exist for dynamic_gesture_detector/vision_perception_node/mock_event_publisher/rtmpose_inference; voting tests live in test_gesture_recognizer_backend.py (TestMajorityVoteMinVotes); node is exactly 608 lines; gesture README confirms wave 6/04 baseline fail (n=9, recall=0.0).
- **證據**：
  - vision_perception/test/: 138 pass (43 pose_classifier, 21 recognizer+voting, 17 event_action_bridge, 15 interaction_rules, 13 lidar_obstacle, 10 event_builder, 7 obstacle_detector, 6 gesture_classifier, 6 mediapipe_pose_mapping) — verified by pytest run
  - .github/workflows/ros_build.yaml:47-57 (CI lists only 7 of 9 files; test_lidar_obstacle_detector + test_obstacle_detector local-only)
  - no test file exists for dynamic_gesture_detector.py / vision_perception_node.py / mock_event_publisher.py / rtmpose_inference.py
  - voting.py tests live inside test_gesture_recognizer_backend.py:137-178 rather than a dedicated file
  - docs/pawai-brain/perception/gesture/README.md:19-20 (gesture.wave trusted baseline = fail, n=9 recall=0.0 — the only real-camera measurement of the temporal path)
- **建議**：Adding tests is runtime-safe now: dedicated WaveDetector unit tests (reversal/amplitude/window edge cases) and extracting _tick's vote→stable-gate→publish decision into a pure function with tests. Full node refactor (split 608-line class) is post-demo.

### VISION-6 — ~656 LOC disabled obstacle stack (D435 + LiDAR) lives inside the perception package and duplicates nav-domain reactive_stop_node

- **分級**：🟡 medium · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: the 5 files total exactly 656 LOC (97+142+112+133+172); contract §4.9 marks /event/obstacle_detected ⛔ disabled with the D435 camera-angle rationale; git log shows 22dde67 2026-04-03 '導航避障停用決策' as last functional change; go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py exists as the live safe-stop owner.
- **證據**：
  - vision_perception/vision_perception/{obstacle_detector.py(97),obstacle_avoidance_node.py(142),lidar_obstacle_detector.py(112),lidar_obstacle_node.py(133),obstacle_debug_overlay.py(172)} — wc -l verified
  - docs/contracts/interaction_contract.md:707-709 (/event/obstacle_detected ⛔ disabled, 'D435 鏡頭角度限制導致防撞不可靠，Demo 停用')
  - git log: obstacle_avoidance_node.py last functional change 2026-04-03 (22dde67 '導航避障停用決策')
  - go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py (the live safe-stop implementation that owns this responsibility)
- **建議**：Post-demo: delete the obstacle stack from vision_perception (or move lidar_obstacle_detector's tested zone logic into the nav package if reactive_stop wants it). Removing it also takes the local-only obstacle tests out of the 138-count honestly.

### VISION-7 — Wave bypass publishes confidence=1.0 and skips ALL 6/10 anti-false-positive gates (min_conf, min_votes, 0.5s stable gate); false-positive rate at demo range is unmeasured — containment relies entirely on brain-side gesture_enabled/demo_phase gates

- **分級**：🟡 medium · `missing_hitl` · **NEEDS_HITL**
- **查證**：✅ supported — Verified: wave bypass publishes build_gesture_event('wave', 1.0, hand) directly with only _wave_publish_cooldown_s=2.5 (code comments explicitly state wave does NOT enter the static buffer/0.5s stable gate, and the min_votes comment says 'wave bypass 不經 buffer，不受影響'); brain fires wave→wave_hello gated by gesture_enabled/demo_phase/conversation gates; gesture README's only HITL measurement is recall=0.0 (miss-rate), no FP measurement; demo snapshot lines 65-67 confirm the keep-gesture-toggle-off-outside-segment SOP.
- **證據**：
  - vision_perception/vision_perception/vision_perception_node.py:417-451 (wave bypass: direct publish, only 2.5s cooldown; comments confirm intentional buffer bypass)
  - vision_perception/vision_perception/vision_perception_node.py:494-499 (gesture_min_votes applies only to the static buffer; OK included, wave explicitly excluded)
  - interaction_executive/interaction_executive/brain_node.py:818-836 (wave→wave_hello direct skill; conversation gate + gesture_enabled are the only brakes)
  - docs/pawai-brain/perception/gesture/README.md:19-21 (6/04 trusted measurement is recall=0.0 at 1.5m — a miss-rate result; FP behavior under venue motion never measured)
- **建議**：Keep Studio gesture toggle OFF outside S4 (already demo SOP per docs/pawai-demo/2026-06-10-demo-snapshot.md:65-67). Post-demo HITL: measure wave FP rate with people walking through frame; if nonzero, route wave through min_votes-style gating or raise min_amplitude_px.

### VISION-8 — mock_event_publisher cycles legacy gesture names (stop/point/fist) that the production recognizer path never emits — Studio frontend dev tests against a vocabulary production doesn't speak

- **分級**：⚪ low · `fragile_runtime` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: _SEQUENCE cycles wave/stop/point/fist (mock_event_publisher.py:19-28), production recognizer emits palm/fist/index/thumbs_up/peace, and brain's gesture maps contain no stop/point. One correction: 'fist' IS emitted by production (Closed_Fist→fist, gesture_recognizer_backend.py) and brain maps fist→enter_mute_mode, so only stop/point are truly dead vocabulary — core finding and fix still hold.
- **證據**：
  - vision_perception/vision_perception/mock_event_publisher.py:19-28 (_SEQUENCE: wave/stop/point/fist)
  - vision_perception/vision_perception/gesture_recognizer_backend.py:49-58 (production emits palm/fist/index/thumbs_up/peace)
  - interaction_executive/brain_node.py:818-824 (brain ignores stop/point entirely)
- **建議**：One-line change: update _SEQUENCE to palm/index/thumbs_up/peace/ok/wave. No runtime path in the demo uses mock_event_publisher (Studio has its own mocks for 6/10 toggles), so safe now — but verify Studio panels don't snapshot-test against old names first.

### VISION-9 — pose_two_class demo mode drops fallen at the source (fallen→None, never enters vote buffer) — fall detection is structurally OFF during the entire demo profile; any 守護/fall narrative is a forbidden claim while this flag is set

- **分級**：⚪ low · `overclaim_risk` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — Verified end-to-end: COARSE_POSE_MAP omits fallen and to_two_class('fallen') returns None (test_fallen_dropped asserts it), vision_perception_node applies two_class before pose_buffer.append, start_full_demo_tmux.sh:167 sets pose_two_class:=true, and claim matrix + pose README mark pose.fall as future/DO_NOT_CLAIM with enable_fallen:=false. Recommendation is consistent with documented claim policy.
- **證據**：
  - vision_perception/vision_perception/pose_classifier.py:46-64 (COARSE_POSE_MAP omits fallen; to_two_class('fallen') → None, test-asserted at vision_perception/test/test_pose_classifier.py:574-575)
  - vision_perception/vision_perception/vision_perception_node.py:309-314 (two_class applied before buffer append)
  - scripts/start_full_demo_tmux.sh:167 (pose_two_class:=true in demo)
  - docs/mission/2026-06-18-capability-claim-matrix.md pose.fall = future / insufficient_data (cited via docs/pawai-brain/perception/pose/README.md:7,28)
- **建議**：Intentional and consistent with claim matrix (pose.fall = future). Keep as-is for 6/18; the synthesizer should note 'sitting' under two_class also means crouch/kneel/bend (broadened semantics), so demo narration must say 「我看到你了」-style wording, never 「偵測到跌倒/守護」.

### VISION-10 — Documented test invocation fails from repo root: outer package dir shadows inner module (ModuleNotFoundError: vision_perception.lidar_obstacle_detector); CI only passes via explicit PYTHONPATH

- **分級**：⚪ low · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Reproduced live: pytest from repo root fails collection with ModuleNotFoundError: No module named 'vision_perception.lidar_obstacle_detector'; the same suite passes 138 from vision_perception/. The rule file documents the root-relative command (at line ~15, not 9 — immaterial) and ros_build.yaml:47 confirms CI only passes via PYTHONPATH=speech_processor:vision_perception:benchmarks.
- **證據**：
  - Reproduced: `python3 -m pytest vision_perception/test/ -q` from /home/roy422/newLife/elder_and_dog fails collection; same command from vision_perception/ passes 138
  - .claude/rules/vision-perception.md:9 documents the failing root-relative invocation as the standard test command
  - .github/workflows/ros_build.yaml:47 (CI works only because PYTHONPATH=speech_processor:vision_perception:benchmarks)
- **建議**：Docs fix: change the rule file command to `cd vision_perception && python3 -m pytest test/` or add PYTHONPATH prefix. Root cause (pkg-dir == module-name namespace shadowing) resolves itself if a repo-root conftest.py or pytest.ini sets pythonpath.

## OBJECT — Object perception

### OBJECT-1 — Hardcoded 'Roy cup compound' demo path in brain _on_object（已修正：預設關閉，非 live）

- **分級**：🟡 medium（原判 high，查證後降級）· `demo_hack` · **POST_DEMO_ONLY**（原判 MUST_PRESERVE，查證後改判）
- **查證**：❌ REFUTED（部分駁回，本條已依查證結果改寫） — The hardcoded Roy/cup block exists with all cited literals, but the claim that it is 'live'/'still on' is contradicted by the repo: brain_node.py:376 declares demo_video_cup_compound default False, executive.yaml:22 sets false, and nothing in scripts/launch enables it (6/9 plan C-Step 4 + commit 932b74e deliberately turned it off). The recorded S3 cup segment used the separate weather-wording path (build_object_tts cup suffix), not this compound path.
- **修正後事實**：hardcoded「Roy 坐著拿杯子」複合句路徑**存在但預設關閉**（`demo_video_cup_compound=false`，brain_node.py:376 + executive.yaml:22，6/9 commit 932b74e 刻意關掉）。6/10 錄的 S3 杯子段走的是 `build_object_tts` 的 cup 天氣措辭路徑，不是這條。
- **證據**：
  - interaction_executive/interaction_executive/brain_node.py:1390-1420 (class_name=='cup' + cached_name=='Roy' literal + canned sentence 「我看到 Roy 坐著拿著杯子，是口渴了嗎？」 + inline magic numbers: identity fresh ≤30s, sitting ≤10s, compound dedup 60s)
  - brain_node.py:376 + interaction_executive/config/executive.yaml:22（demo_video_cup_compound 預設與 yaml 皆 false）
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:38（S3 已錄；錄製路徑為 build_object_tts cup 措辭，非 compound）
- **建議**：demo 後把這條已關閉的 demo hack 整段移除（人名/句子/魔術數字併入一般 object_remark 路徑或 demo config）。因為它是 dead-by-flag 的程式碼，不在 demo 凍結範圍，但動 brain_node.py 仍需 6/18 後（檔案級凍結）。

### OBJECT-2 — Brain consumes only objects[0]; no instance id, no depth — silent-miss by design

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: brain _on_object takes det = objects[0] and discards the rest; object_perception_node._publish_events batches every class passing the per-class 5s cooldown into one event in detection order; contract schema (interaction_contract.md §4.8) has no instance/track id or distance; README:20 shows distance=manual_declared; yaml:21 household-7 whitelist includes chair/laptop/cup so shadowing is plausible (synchronized cooldowns make persistent miss realistic).
- **證據**：
  - brain_node.py:1348-1356 (det = objects[0]; rest of array discarded)
  - object_perception_node.py:434-463 (event may batch multiple new classes per tick; objects ordered by raw YOLO row order)
  - docs/contracts/interaction_contract.md:659-686 (schema has no instance/track id, no distance)
  - docs/pawai-brain/perception/object/README.md:20 (6/4 baseline: distance=manual_declared — no depth in pipeline)
  - object_perception/config/object_perception.yaml:21 (household-7 whitelist: chair/laptop commonly co-visible with cup → cup can land at objects[1] and never be spoken)
- **建議**：Smallest fix: iterate objects[] in brain and pick first TTS-whitelisted class instead of [0]. Larger: add track/instance id + optional depth from D435 to the event (contract bump), and a continuous /state/perception/object topic like face's.

### OBJECT-3 — Speak-policy split across three layers (node 5s class cooldown / brain 60s dedup / SkillContract 5s)

- **分級**：🟡 medium · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified all three layers: node class_cooldown_sec=5.0 enforced in _publish_events, brain OBJECT_REMARK_DEDUP_S=60.0 with class-key dedup in _on_object, and skill_contract.py object_remark cooldown_s=5.0; README §5/7-night documents the layers were added because lower layers leaked. obj_matrix_cap.py:38 hardcodes OBJECT_EVENT_COOLDOWN_S=5.0 as a duplicate literal and validates window/gap against it as claimed.
- **證據**：
  - object_perception_node.py:163,184,441-452 (node-level per-class 5s event cooldown — perception decides eventness)
  - brain_node.py:69-73,1431-1435 (OBJECT_REMARK_DEDUP_S=60 class-key dedup)
  - interaction_executive/interaction_executive/skill_contract.py (object_remark cooldown_s) + docs/pawai-brain/perception/object/README.md:180-189 (5/7 night: layers added because each lower layer leaked)
  - scripts/obj_matrix_cap.py:37-56 (harness must hardcode OBJECT_EVENT_COOLDOWN_S=5.0 duplicate literal and validate window/gap against it — measurement constrained by perception-side policy)
- **建議**：Make node cooldown pure rate-limit (or publish continuous state + raw events) and own all 'when to speak' in brain. Export the node cooldown constant from one place so obj_matrix_cap stops duplicating the literal.

### OBJECT-4 — Hand-synced duplication: 3 zh dicts + double confidence_threshold default already caused a real demo bug

- **分級**：🟡 medium · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: coco_classes.py docstring says COCO_CLASSES_ZH is 'mirrored (NOT imported)' by object-config.ts and brain_node (brain_node.py:41-58 subset + COLOR_ZH, object-config.ts COCO_ZH_FALLBACK/COLOR_ZH all hand-synced). The 0.5-vs-0.35 launch-default-shadows-yaml bug is documented in both the launch file comment and object CLAUDE.md pitfall 9, fixed in real commit b1f5058 ('launch conf default 0.35'); confidence_threshold is confirmed non-runtime-settable.
- **證據**：
  - object_perception/object_perception/coco_classes.py:8-12 ('mirrored (NOT imported)' by studio object-config.ts and brain_node — keep 3 in sync by hand)
  - brain_node.py:41-58 (OBJECT_CLASS_ZH/OBJECT_COLOR_ZH subset copy)
  - pawai-studio/frontend/components/object/object-config.ts:158,204-205
  - object_perception/launch/object_perception.launch.py:35-39 (launch default ordered after config_file silently overrides yaml; the 0.5-vs-0.35 divergence dropped near-range cup events until commit b1f5058 — docs/pawai-brain/perception/object/CLAUDE.md pitfall 9)
  - object_perception/config/object_perception.yaml:11
- **建議**：Generate the three zh dicts from one source (JSON in docs/contracts + codegen or CI sync check). Remove the launch-arg duplicate default for confidence_threshold (pass through yaml only) and make it a runtime-settable param.

### OBJECT-5 — Model A/B switch chain unverified end-to-end (env→tmux→launch; fixed-shape ONNX hard-fails on size mismatch)

- **分級**：🟡 medium · `missing_hitl` · **NEEDS_HITL**
- **查證**：✅ supported — Verified: launch declares OBJECT_MODEL/OBJECT_INPUT_SIZE via EnvironmentVariable; start_full_demo_tmux.sh object window (~line 277-280) runs plain 'ros2 launch object_perception object_perception.launch.py' with no env interpolation, unlike speech vars ($TTS_PROVIDER/$PAWAI_LLM_MODEL) which are explicitly baked into window commands. CLAUDE.md pitfall 6 confirms fixed-shape ONNX hard-fails on size mismatch, the 6/10 research doc shows candidates exported/validated on WSL only, and demo snapshot item 4 confirms Jetson A/B remains an open measurement task.
- **證據**：
  - object_perception/launch/object_perception.launch.py:25-34 (OBJECT_MODEL/OBJECT_INPUT_SIZE env)
  - scripts/start_full_demo_tmux.sh:277-280 (object window does NOT forward OBJECT_MODEL/OBJECT_INPUT_SIZE explicitly, unlike speech vars; relies on tmux server env inheritance — known tmux env footgun per CLAUDE.md LD_LIBRARY_PATH rule)
  - docs/pawai-brain/perception/object/CLAUDE.md pitfall 6 (wrong input_size = inference fail + silent restart)
  - docs/archive/pawai-brain-legacy/research/2026-06-10-model-upgrade-decision-research.md:24-34 (candidates exported on WSL only; Jetson A/B not yet run)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:108 (YOLO26s A/B 'remains a measurement task')
- **建議**：Before any A/B session: scp candidates to /home/jetson/models/, run object_model_contract.py on-device, and verify env propagation by launching object_perception standalone (not via full-demo tmux) or add explicit OBJECT_MODEL forwarding into the tmux window command.

### OBJECT-6 — A/B export assets and export script live only in gitignored .tmp on the WSL box

- **分級**：🟡 medium · `fragile_runtime` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: .gitignore:31 ignores .tmp/ (git check-ignore matches), .tmp/yolo_export/ holds export_models.py + 3 .pt + 4 validated ONNX in out/ (sizes match), all untracked; research doc lines ~26-35 cites these paths as the prepared A/B candidates with WSL-only export and deployment pending. scripts/object_model_contract.py exists so the recommendation is viable.
- **證據**：
  - .gitignore:31 (.tmp/ ignored — confirmed via git check-ignore on .tmp/yolo_export/export_models.py)
  - .tmp/yolo_export/ (export_models.py, 4 validated ONNX: yolo26s_640 38.3MB / yolo26n_960 10.2MB / yolo26s_960 / yolo26n-pose_640, 3 .pt weights — none tracked, none on Jetson)
  - docs/archive/pawai-brain-legacy/research/2026-06-10-model-upgrade-decision-research.md:24-34 cites these paths as the prepared candidates
- **建議**：Commit export_models.py (e.g. scripts/ or benchmarks/), record sha256 of each ONNX via object_model_contract.py --json into docs/research or artifacts/, so A/B provenance survives a .tmp wipe. Zero demo impact.

### OBJECT-7 — Core inference path and HSV color have no tests; dedup tests re-implement logic instead of exercising it

- **分級**：🟡 medium · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: node comment (lines 80-83) claims test-importability but grep shows zero test imports of analyze_bbox_color; TestDedup (201-249) re-implements the cooldown expression inline with only the reset test using __new__; blob BGR2RGB at 364-372 and _publish_events at 434-463 have no test coverage (test line 329 only mirrors the gating logic); commit b1f5058 confirmed as the RGB-blob/threshold fix.
- **證據**：
  - object_perception_node.py:80-83 (comment claims module-level analyze_bbox_color exists 'so unit tests can import' — grep shows zero test imports it)
  - object_perception/test/test_object_perception.py:201-249 (TestDedup copies the cooldown expression inline; only test_reset_context_clears_class_cooldowns touches a real method via __new__)
  - no test covers _tick / letterbox→BGR2RGB blob (object_perception_node.py:364-372) — exactly the regression class fixed in commit b1f5058 (BGR blob depressed cup confidence)
  - _publish_events (object_perception_node.py:434-463) never called by tests
- **建議**：Add pure-numpy tests: analyze_bbox_color on synthetic solid/speckled crops (12 colors + Unknown gate), _publish_events via __new__-constructed node with stub publisher, and a blob-channel-order assertion. No runtime change needed.

### OBJECT-8 — Detections silently dropped at 5 brain gates with no operator-visible reason

- **分級**：🟡 medium · `observability` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: brain_node.py:1374-1388 has 5 sequential gates where 4 (ENGAGED, active skill, pending confirm, tts_playing) return with no log; only _phase_allows logs (306-316); studio_gateway.py:101 maps /event/object_detected to the UI while no drop-reason reaches Studio; snapshot line 105 documents the analogous silent-rejection UX item.
- **證據**：
  - brain_node.py:1374-1388 (phase gate, ENGAGED attention, active skill, pending confirm, tts_playing — four of five return with no log; only phase suppression logs at brain_node.py:306-313)
  - Studio shows the detection chip via gateway (studio_gateway.py:101) but nothing explains why no TTS followed — same UX class as snapshot Known Open Item 2 (docs/pawai-demo/2026-06-10-demo-snapshot.md:105, Studio silent goal rejection)
- **建議**：Emit a throttled debug log + a /brain/trace (or existing status topic) record with drop-reason enum for object events. Cheap, makes live debugging of 'cup seen but dog silent' a 10-second check instead of a HITL guessing game.

### OBJECT-9 — Dead code: unwired state_machine OBJECT_TTS_MAP path; coco_detector residue

- **分級**：⚪ low · `dead_code` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: _route_object + OBJECT_TTS_MAP exist in state_machine.py (~68, 283-295) with zero wiring in interaction_executive_node.py (grep empty), README documents it as 棄用路徑, and coco_detector/ was deleted in 955b00e (2026-03-25) with ignored __pycache__ residue still on the working copy. Minor wording nit: the residual __pycache__ dirs contain .pyc files rather than being empty — immaterial to the claim.
- **證據**：
  - interaction_executive/interaction_executive/state_machine.py:68,283-295 (_route_object + OBJECT_TTS_MAP; interaction_executive_node.py has no /event/object_detected subscription — grep empty)
  - docs/pawai-brain/perception/object/README.md:314-316 (officially documented as 棄用路徑, not wired)
  - coco_detector/ deleted from git in 955b00e (2026-03-25) but 3 untracked empty __pycache__ dirs remain on the WSL working copy (coco_detector/, coco_detector/coco_detector/, coco_detector/test/)
- **建議**：Delete the untracked coco_detector __pycache__ dirs anytime (zero risk). Remove _route_object/OBJECT_TTS_MAP + its tests after 6/18 since it edits a demo-runtime file and forces a Jetson rebuild.

### OBJECT-10 — Interface docs drifted from code (AGENT.md defaults, obj_matrix_cap help text)

- **分級**：⚪ low · `overclaim_risk` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: AGENT.md param table claims confidence_threshold 0.5 and class_whitelist [] all-80, while launch default is 0.35 (b1f5058), yaml is 0.35 with household-7 [39,41,45,56,63,67,73] at line 21, and node declared default is the [-1] INTEGER_ARRAY sentinel (node lines 168-175); obj_matrix_cap.py:108-109 still says 'node 預設已 0.5 過濾'; AGENT.md:3 frames itself as the read-this-first interface contract.
- **證據**：
  - docs/pawai-brain/perception/object/AGENT.md:48 (claims confidence_threshold default 0.5; actual launch+yaml are 0.35 since b1f5058) and AGENT.md:53 (claims class_whitelist default [] all-80; actual declared default is [-1] sentinel at object_perception_node.py:168-175 with yaml household-7 [39,41,45,56,63,67,73] at yaml:21)
  - scripts/obj_matrix_cap.py:108-109 (--conf-min help says 'node 預設已 0.5 過濾' — stale)
  - AGENT.md is explicitly the read-this-first interface contract for agents (AGENT.md:3)
- **建議**：One-pass doc sync: fix AGENT.md param table (0.35, [-1] sentinel, household-7 yaml default, runtime-settable=class_whitelist only) and the obj_matrix_cap help string. Docs-only, no demo impact.

## NAV — Navigation / 避障 stack

### NAV-1 — S1 blocker: AMCL yellow-gate (0.3<cov≤0.5 → only ≤0.5m goals) hardcoded in nav_action_server collides with Studio default goal 1.2m; cov flickers 0.41-0.47 around the 0.45 capability threshold

- **分級**：🔴 high · `fragile_runtime` · **NEEDS_HITL**
- **查證**：✅ supported — Verified: red >0.5 / yellow 0.3-0.5 cap-at-0.5m gates are hardcoded literals at nav_action_server_node.py:376-391 (node declares no threshold params) and duplicated at 558-571 for goto_named; NAV_DEFAULT_DISTANCE_M=1.2 at studio_gateway.py:119; references/project-status.md §5 (6/10 HITL) documents cov 0.41-0.47 flicker and 1.0/1.2m goal rejection blocking S1; snapshot lists the three candidate fixes.
- **證據**：
  - nav_capability/nav_capability/nav_action_server_node.py:376-391 (red >0.5 reject; yellow 0.3-0.5 caps distance at 0.5m; thresholds are literals, not ROS params)
  - nav_capability/nav_capability/nav_action_server_node.py:558-571 (same yellow gate duplicated for goto_named)
  - pawai-studio/gateway/studio_gateway.py:119 (NAV_DEFAULT_DISTANCE_M = 1.2)
  - references/project-status.md:35-37 (6/10 HITL: cov 0.41-0.47 抖, 1.0/1.2m goal 被拒, S1 沒錄成)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:99-104 (three candidate fixes)
- **建議**：For S1: fix (A) is one line — gateway NAV_DEFAULT_DISTANCE_M 1.2→0.5 or pass distance=0.5 in /api/nav/start (no nav-stack rebuild). Fix (B) widening the gate edits hardcoded literals at nav_action_server_node.py:376/384 + colcon rebuild + HITL (yellow-band 1.2m motion never proven). Post-demo: parameterize thresholds.

### NAV-2 — Goal-rejection reasons swallowed end-to-end: server collapses 3 distinct aborts into message='amcl_lost'; gateway discards result.message and broadcasts reason='failed'; Studio shows silence — the direct cause of Roy's '按開始狗不動'

- **分級**：🔴 high · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: three distinct abort branches (amcl-none line 374, cov-red 382, cov-yellow-distance 390) all return identical message='amcl_lost'; gateway _on_nav_result (652-676) never reads result.message and collapses failures to reason='failed'; nav-control.tsx renders reason only inside the isPausedConfirm block (line 201); snapshot:105 records the open item.
- **證據**：
  - nav_capability/nav_capability/nav_action_server_node.py:374,382,390 (amcl-none / cov-red / cov-yellow-too-far all return identical 'amcl_lost')
  - pawai-studio/gateway/studio_gateway.py:652-676 (_on_nav_result: success→'reached', anything else→'failed'; result.message never read)
  - pawai-studio/frontend/components/navigation/nav-control.tsx:201 (reason rendered only in paused view)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:105 (known open item: Studio should show rejection reasons)
- **建議**：Additive plumbing, no gate behavior change: distinct result.message per abort branch (cov_red / cov_yellow_distance / amcl_none), gateway passes result.message into nav_control broadcast, frontend renders it in idle state. Directly de-risks the S1 retake.

### NAV-3 — reactive_stop geometry params (front_arc_deg / danger_distance_m / slow_distance_m / front_offset_rad) are init-only; ros2 param set silently no-ops — mitigated only by REACTIVE_PROFILE env in one launch script

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: geometry params read once in __init__ (reactive_stop_node.py:108-118); _on_param_change (173-197) handles only enable_nav_pause/safety_only/mode and returns successful=True for everything else (a true silent no-op); REACTIVE_PROFILE open_space|indoor_tight workaround at start_nav_capability_demo_tmux.sh:29-49 with comments confirming the init-only limitation; HITL doc §4 confirms the ±30° false-danger root cause and the hardware-verified ±15°/±18° + low-speed fix.
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py:108-118 (read once in __init__), 173-197 (_on_param_change handles only enable_nav_pause/safety_only/mode)
  - scripts/start_nav_capability_demo_tmux.sh:29-49 (REACTIVE_PROFILE open_space|indoor_tight workaround, 6/9)
  - docs/archive/navigation-legacy/research/2026-06-08-trackB-hitl-results.md §4 (HITL: ±30° cone false-danger from side furniture; ±15-18° + low speed fix verified on hardware)
- **建議**：Post-demo: either accept geometry params in _on_param_change with a zone-reset, or reject the set with successful=False + loud warn so operators aren't silently fooled. Demo flow depends on the current restart-with-REACTIVE_PROFILE discipline — freeze until 6/18.

### NAV-4 — Nav motion safety rests on out-of-band discipline, not code: progressive mode is silent in slow/clear → mux 0.5s timeout hands /cmd_vel to any hot teleop publisher (100 > nav 10) — the documented 5/11 crash; only guards are launch flags and comments, plus test_mux_priority.py is a real-publisher footgun

- **分級**：🔴 high · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — All cited evidence verified: audit doc reconstructs teleop-100 takeover via mux 0.5s timeout as the corrected root cause; mux priorities 255/200/100/10 in twist_mux.yaml:18-41; demo script's only guards are teleop:=false flags + comments (lines 90-106); FakePublisher in test_mux_priority.py is a real 0.30 m/s publisher with the runaway documented in CLAUDE.md; reactive_stop_node.py:335-345 warns teleop may silently win on resume.
- **證據**：
  - docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §0-§1.2 (crash reconstruction; teleop 100 takeover as true root cause)
  - go2_robot_sdk/config/twist_mux.yaml:18-41 (emergency 255 / obstacle 200 / teleop 100 / nav2 10)
  - scripts/start_nav_capability_demo_tmux.sh:90-106 (teleop:=false joystick:=false + 'must kill teleop' comments are the only protection)
  - nav_capability/test/integration/test_mux_priority.py:21,64 (FakePublisher publishes real 0.30 m/s through mux — 4/26 22:30 runaway documented in CLAUDE.md)
  - reactive_stop_node.py:336-345 (code itself warns teleop may silently win on resume)
- **建議**：Freeze flags/discipline through 6/18. Post-demo: add a publisher-count watchdog on /cmd_vel_joy that refuses/pauses nav goals while a hot teleop publisher exists, and guard test_mux_priority.py behind an env check so it cannot run against a live stack.

### NAV-5 — Auto-resume lunge is HITL-banned but the code path remains live: nav_action_server re-sends the goal whenever /state/nav/paused flips false; Go2 MIN_X=0.5 m/s floor means resume starts at 0.5 m/s — measured stopping 0.21m from a wall; indoor_tight low speeds do NOT apply to the Nav2 path

- **分級**：🔴 high · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — HITL plan lines 53-59 document the resume lunge (stopped 0.21m from wall, MIN_X=0.5 floor root cause, 6/18 ban); nav_action_server_node.py:246-321 outer loop unconditionally re-sends the goal when /state/nav/paused flips false with no auto_resume switch (grep confirms); gateway 428-458/547-576 implements the operator-confirm workaround; indoor_tight low speed not applying to Nav2 path is explicitly stated in the HITL doc.
- **證據**：
  - docs/archive/superpowers-legacy/plans/2026-06-09-nav-vision-hitl-execution.md:53-59 (Task 1.6: resume lunge to front 0.21m, 6/18 ban, MIN_X floor root cause)
  - nav_capability/nav_action_server_node.py:246-321 (outer pause/resume loop auto re-sends on resume — no auto_resume switch)
  - go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py:41-79 (MIN_X deadband → StopMove routing)
  - pawai-studio/gateway/studio_gateway.py:428-458,547-576 (gateway works around it with cancel-on-danger + operator-confirm re-send)
- **建議**：S1 flow already routes around it via gateway danger-cancel → paused_confirm; do not touch before 6/18. Post-demo: add auto_resume param (default false) to nav_action_server's pause loop so route/CLI paths get the same operator-confirm semantics as Studio.

### NAV-6 — Three parallel pause/goal-supervision protocols: route_runner /nav/pause-resume services, nav_action_server's latched-topic cancel-and-resend loop, and the Studio gateway's own idle/running/paused_confirm/done state machine — duplicated policy with divergent resume semantics

- **分級**：🟡 medium · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Three distinct pause/supervision implementations confirmed in code: route_runner's /nav/pause//nav/resume services + latched /state/nav/paused, nav_action_server's auto-resend pause loop, and the gateway's idle/running/paused_confirm/done state machine with an explicit 'NO auto-resume' comment (lines 1134-1137); docs/navigation/CLAUDE.md records the BUG #2 history. Resume semantics demonstrably diverge (auto-resend vs operator-confirm).
- **證據**：
  - nav_capability/nav_capability/route_runner_node.py:5-13,106-110 (services + latched /state/nav/paused)
  - nav_capability/nav_capability/nav_action_server_node.py:89-99,231-321 (independent pause-aware loop)
  - pawai-studio/gateway/studio_gateway.py:431-458,524-603,1135-1137 (third state machine; deliberately bypasses auto-resume)
  - docs/navigation/CLAUDE.md ('/nav/pause 只有 route_runner_node 接、nav_action_server 沒接' history of BUG #2)
- **建議**：Post-demo Brain/CLI v2 work: a single nav-session supervisor owning pause/resume/cancel + reasons, consumed by Studio, IE, and CLI clients. The gateway operator-confirm semantics (HITL-blessed) should become the canonical default.

### NAV-7 — Covariance policy duplicated with three different numbers: capability_publisher param (lib default 0.20, demo launch 0.45) vs nav_action_server hardcoded 0.3/0.5 — /capability/nav_ready can be true while goto still rejects, and vice versa

- **分級**：🟡 medium · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Three different numbers verified: nav_ready_check.py:21 DEFAULT_COVARIANCE_THRESHOLD=0.20, launch/demo script 0.45 (with comment admitting it's an alignment hack to the node's YELLOW upper 0.50), nav_action_server hardcoded 0.5/0.3 at lines 376/384; project-status.md:35-37 records cov 0.41-0.47 oscillating at the 0.45 edge while 1.0/1.2m goto was rejected by the yellow gate.
- **證據**：
  - nav_capability/nav_capability/lib/nav_ready_check.py:21 (DEFAULT_COVARIANCE_THRESHOLD = 0.20)
  - scripts/start_nav_capability_demo_tmux.sh:119 (covariance_threshold:=0.45)
  - nav_capability/launch/nav_capability.launch.py:50-54 (0.45 default, comment admits alignment hack to YELLOW upper 0.50)
  - nav_capability/nav_capability/nav_action_server_node.py:376,384 (hardcoded 0.5/0.3)
  - references/project-status.md:35-37 (cov 0.41-0.47: nav_ready likely true at 0.45 threshold edge while 1m goto rejected)
- **建議**：Single source of truth: move green/yellow/red bands into one shared lib constant set (extend nav_ready_check.py), parameterize nav_action_server from it, and have capability_publisher publish the band (green/yellow/red) not just a Bool.

### NAV-8 — Node-level logic of the demo-critical path is untested: AMCL gate branches, pause-aware execute loop, goto_max_duration_s backstop, and _goto_active single-goal lock have zero unit tests — the yellow-gate branch that blocked S1 shipped untested

- **分級**：🟡 medium · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — nav_capability/test/ contains exactly 49 test functions across 8 pure-lib test files; none import nav_action_server_node (test_progress_check mentions it only in a docstring and imports lib.progress_check); test_nav_ready_check tests the 0.20 lib threshold, not the node's 0.3/0.5 gate. Driver/gateway coverage counts (27+23/11/10 and 52 gateway tests) also match.
- **證據**：
  - nav_capability/test/ (8 files, 49 test fns — all pure-lib helpers: route_fsm, route_validator, named_pose_store, nav_ready_check, progress_check, math helpers; none import nav_action_server_node)
  - nav_capability/test/test_nav_ready_check.py (tests 0.20 threshold lib, not the node's 0.3/0.5 gate)
  - go2_robot_sdk/test/ (reactive_stop 27+23 tests, robot_control_service 11, depth_geometry 10 — driver side is well covered)
  - pawai-studio/gateway/test_gateway.py:513-730 (~8 nav-control tests of 52 — gateway side covered)
- **建議**：Test-only addition is zero-risk now: extract the gate decision (cov, distance)→(accept, reason) into nav_capability/lib (pure function) post-demo; before that, add tests that import the existing node module and exercise _amcl_covariance_xy + gate constants via a stub to lock current behavior before any S1 gate change.

### NAV-9 — start_nav_capability_demo_tmux_detour.sh is a live footgun: safety_only:=true (auto-promotes to hold_brake → nav cannot move, contradicting detour purpose) + danger_distance_m:=0.40 (64% below the 1.1m audited floor), warned against only in docs, with a header that even shows the non-detour script's usage

- **分級**：🟡 medium · `demo_hack` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Detour script line 86 has safety_only:=true + danger_distance_m:=0.40, header lines 16-18 show copy-pasted non-detour usage text, and the script contains no warning/guard; reactive_stop_node.py:129-130 promotes safety_only=True to hold_brake (nav cannot move, contradicting detour purpose); docs/navigation/CLAUDE.md warns '不要直接用' citing the 5/12 subagent audit's 4 bugs including these two.
- **證據**：
  - scripts/start_nav_capability_demo_tmux_detour.sh:16-18 (header usage text copy-pasted from non-detour script), :86 (safety_only:=true -p danger_distance_m:=0.40)
  - docs/navigation/CLAUDE.md ('start_nav_capability_demo_tmux_detour.sh 不要直接用' — 4 bugs from 5/12 subagent audit)
  - go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py:129-130 (safety_only=True promotes to hold_brake)
- **建議**：Not in the 6/18 flow — add an immediate `echo WARNING + exit 1` guard (override env to run) or move to scripts/archive/. Five-person shared Jetson + tab-completion makes accidental launch plausible.

### NAV-10 — Capability-ladder honesty: only short goto (0.3-0.5m), frontal safe-stop, indoor-tight de-falsing, and log_pose are HARDWARE_PROVEN; run_route/patrol (K4) never passed HITL, goto_named never run on hardware, IE move_forward and 1m+ goto unproven — yet all are fully built code with advertised demo commands

- **分級**：🟡 medium · `overclaim_risk` · **NEEDS_HITL**
- **查證**：✅ supported — trackB results §1/§7 confirm only short goto + safe-stop proven and '不能講 route 巡場'; the 6/9 HITL plan line 13 states only 4 capabilities are HARDWARE_PROVEN with stop-resume demoted at lines 53-59; project-status lines 1885/2121/2122 show K4 run_route always blocked/deferred (no later pass found in any doc) and goto_named noted as ready-but-untested-on-hardware; the demo script still advertises run_route (:163) and 1.0m goto (:157); demo snapshot lines 88-97 list the matching forbidden claims.
- **證據**：
  - docs/archive/navigation-legacy/research/2026-06-08-trackB-hitl-results.md §1,§7 (goto 0.3m reached / safe-stop proven; 不能講 route 巡場)
  - docs/archive/superpowers-legacy/plans/2026-06-09-nav-vision-hitl-execution.md:13 (only 4 capabilities HARDWARE_PROVEN), :51-59 (safe-stop proven, stop-resume demoted)
  - references/project-status.md:1885,2122 (K4 run_route 全部阻塞/推遲 — no later pass recorded), :2121 (K10 log_pose 3/5 SUCCEEDED)
  - scripts/start_nav_capability_demo_tmux.sh:163 (advertises K4 run_route command), :157 (advertises 1.0m goto)
  - docs/pawai-demo/2026-06-10-demo-snapshot.md:88-97 (forbidden claims list incl. dynamic avoidance, D435 fusion, move_forward)
- **建議**：Ladder per feature: goto_relative≤0.5m=HARDWARE_PROVEN; safe-stop=HARDWARE_PROVEN; stop-resume=HARDWARE_PROVEN-but-banned; goto 1m+=WIRED_RUNTIME; goto_named/run_route=WIRED_RUNTIME; IE move_forward=EXISTING_CODE; patrol/approach-person=NOT_BUILT. Any report/demo claim above this needs a new Jetson+Go2 session.

## GO2RT — Go2 driver / robot runtime

### GO2RT-1 — Safety-critical driver tests (93 collected incl. 11 StopMove-routing tests) run in NO automated gate

- **分級**：🔴 high · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified by running pytest --collect-only: exactly 93 tests collected in go2_robot_sdk/test/ (collection succeeds without ROS runtime in 0.57s), including the 11 StopMove-routing/dedupe tests at test_robot_control_service.py:98-191; CI Fast Gate (ros_build.yaml:47-91) lists only speech/vision/benchmarks/pawai_brain tests, the colcon tier (143-150) excludes go2_robot_sdk marked TEMPORARY, and the pre-commit smart-scope (66-80) covers only speech/vision/face — so these safety tests run in no automated gate.
- **證據**：
  - .github/workflows/ros_build.yaml:47-91 (Fast Gate pytest list: speech/vision/benchmarks/pawai_brain only)
  - .github/workflows/ros_build.yaml:143-150 (colcon tier package-name excludes go2_robot_sdk, marked TEMPORARY)
  - scripts/hooks/git-pre-commit.sh:66-80 (smart-scope: speech/vision/face only)
  - go2_robot_sdk/test/test_robot_control_service.py:98-191 (the 5/11 B4/B5 regression suite)
- **建議**：Add go2_robot_sdk/test/ (minus test_import.py) to CI Fast Gate — files already bypass aioice via importlib stubs and pass in 0.65s locally. Zero runtime impact; protects the StopMove/dedupe safety fix from silent regression.

### GO2RT-2 — go2_robot_sdk/__init__.py calls exit(-1) at import time; 3 tests currently red on WSL

- **分級**：🟡 medium · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — exit(-1) confirmed at __init__.py:23; pytest run this session shows all 3 test_import.py tests FAILED with SystemExit: -1; all 4 other test files contain explicit bypass workarounds (importlib stub in test_robot_control_service.py, sys.path direct-file imports in depth/reactive tests with comments citing the aioice __init__ check).
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/__init__.py:21-23 (exit(-1) when aioice share files absent)
  - go2_robot_sdk/test/test_import.py (3 FAILED, SystemExit -1, verified via pytest this session)
  - go2_robot_sdk/test/test_robot_control_service.py:11-14,26-81 (every other test file does importlib stub gymnastics to dodge the import bomb)
- **建議**：Replace exit(-1) with raise ImportError so linters/pytest/tools are not process-killed; then delete the test stubs' workaround. Requires colcon rebuild on Jetson, so post-6/18 only.

### GO2RT-3 — Dead MCP-era services: move_service publishes /cmd_vel directly, bypassing twist_mux priorities

- **分級**：🟡 medium · `dead_code` · **POST_DEMO_ONLY**
- **查證**：✅ supported — move_service.py:49-53 publishes raw /cmd_vel, which is the twist_mux output topic (launch remaps /cmd_vel_out->/cmd_vel), so direct publish bypasses arbitration; entry points still in setup.py; no script/launch starts it; commit 955b00e removed ros-mcp-server; stale comment at robot_control_service.py:16 says MAX_LINEAR 0.3 but move_service.py:35 is 0.5.
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/move_service.py:49-53 (publishes '/cmd_vel' directly — no mux arbitration if ever revived)
  - go2_robot_sdk/setup.py:52-53 (entry points still registered); no launch script starts move_service (grep: only docs/navigation + AGENTS.md refs)
  - go2_robot_sdk/launch/robot.launch.py:122-124,425-432 (snapshot_service only via mcp_mode arg)
  - git commit 955b00e removed consumer ros-mcp-server
  - go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py:16 (stale comment claims move_service.MAX_LINEAR=0.3; actual is 0.5 at move_service.py:35)
- **建議**：Delete move_service.py, snapshot_service.py, mcp_mode launch plumbing, MoveForDuration.srv after 6/18. If any timed-move capability is still wanted, re-home it behind nav_capability publishing to a mux input topic, never raw /cmd_vel.

### GO2RT-4 — go2_omniverse/ and ros-mcp-server/ are orphan __pycache__ ghosts; foxglove/ layouts referenced only by archived docs

- **分級**：⚪ low · `dead_code` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Both dirs contain only .pyc files under __pycache__/, untracked (git ls-files empty), ignored via .gitignore __pycache__/ rule, and were removed in commit 955b00e. Minor inaccuracy: foxglove JSONs are also mentioned in references/project-status.md changelog (not only the two archived docs), but no runtime consumer exists, so the conclusion stands.
- **證據**：
  - go2_omniverse/ and ros-mcp-server/ contain only .pyc files under __pycache__/ (find verified; git ls-files empty; git check-ignore confirms ignored; removed in commit 955b00e)
  - foxglove/day3-verification.json + foxglove/go2-3d-dashboard.json referenced only from docs/archive/2026-05-docs-reorg/superpowers-legacy/{plans,specs}/2026-03-30-day3-verification*.md
- **建議**：rm -rf go2_omniverse ros-mcp-server on both WSL and Jetson working copies (untracked, zero runtime impact). Keep foxglove/*.json only if anyone still loads them manually into Foxglove; otherwise archive them next to the docs that reference them.

### GO2RT-5 — WebRTC stack survives on private-API monkeypatches + vendored aioice fork + aiortc==1.9.0 pin

- **分級**：🟡 medium · `fragile_runtime` · **NEEDS_RESEARCH**
- **查證**：✅ supported — All cited lines verified: aioice.ice.CONSENT_FAILURES=999 (go2_connection.py:21-22), forced _setReadyState('open') at ~178/192/510, aiortc==1.9.0 pin (setup.py:33), .gitmodules pins external_lib/aioice to legion1581 fork branch go2, and the addTransceiver-breaks-SCTP workaround comment at ~101-103; docs/pawai-demo/2026-06-10-demo-snapshot.md exists.
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py:21-22 (aioice.ice.CONSENT_FAILURES=999 — Go2 firmware ignores STUN consent probes)
  - go2_connection.py:178,192,510 (data_channel._setReadyState('open') forced via aiortc private API)
  - go2_robot_sdk/setup.py:33 (aiortc==1.9.0 pin); external_lib/aioice = submodule pinned to fork branch origin/go2
  - go2_connection.py:101-103 (addTransceiver sendrecv breaks SCTP handshake on aiortc — workaround comment)
- **建議**：Do not touch before 6/18 — this exact stack is the one HITL-proven (S2-S5 recorded, docs/pawai-demo/2026-06-10-demo-snapshot.md). Post-demo: research upstream go2_ros2_sdk/go2_webrtc_connect for cleaner consent/readyState handling before any aiortc upgrade; treat the pin as load-bearing until then.

### GO2RT-6 — Command sends are fire-and-forget and connection health API has zero consumers — dropped commands are invisible to Brain/Studio

- **分級**：🟡 medium · `observability` · **POST_DEMO_ONLY**
- **查證**：✅ supported — run_coroutine_threadsafe future discarded at webrtc_adapter.py:113-116; dc-not-open path is warn+return silent drop (~144-146); get_connection_health has zero callers repo-wide (only its definition at :265); ConnectionHealth dataclass built at go2_connection.py:35-48; demo snapshot Known Open Item #2 explicitly names silent goal rejection.
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py:113-116 (run_coroutine_threadsafe future discarded), 144-147 (dc not open → warn + silent drop)
  - webrtc_adapter.py:265-270 get_connection_health: grep shows no caller anywhere in repo — ConnectionHealth machinery (go2_connection.py:34-48 + lock updates) is built but never published to ROS
  - docs/pawai-demo/2026-06-10-demo-snapshot.md Known Open Items #2 (silent goal rejection is already a recognized class of problem)
- **建議**：Smallest fix: publish ConnectionHealth as a latched /state/go2_driver/health JSON topic at 1Hz and bump dropped-command log to a counter in it. Gives Studio/CLI a real driver liveness signal instead of inferring from tmux logs.

### GO2RT-7 — Every cmd_vel logged at INFO twice per message — 10Hz log flood drowns real warnings

- **分級**：⚪ low · `observability` · **POST_DEMO_ONLY**
- **查證**：✅ supported — Verified: INFO per callback at go2_driver_node.py:379-381 plus 'Received cmd_vel' INFO at robot_control_service.py:54-61 (third INFO at 93-100 for non-zero), so every cmd_vel logs at least twice at INFO; DC BUFFER warnings at webrtc_adapter.py:171-175 are at the same level; 10Hz rate from reactive_stop is documented in code comments (robot_control_service.py:21-25).
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py:380-382 (INFO per callback)
  - go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py:54-61,93-100 (second + third INFO per non-zero command)
  - webrtc_adapter.py:171-175 ([DC BUFFER] warnings are the signal being buried)
- **建議**：Demote per-message cmd_vel logs to DEBUG, keep zone/state transitions and DC BUFFER alerts at INFO/WARN. Requires rebuild — after 6/18.

### GO2RT-8 — reactive_stop safety thresholds are init-only params; runtime ros2 param set silently no-ops (HITL-documented footgun)

- **分級**：🟡 medium · `fragile_runtime` · **MUST_PRESERVE_FOR_DEMO**
- **查證**：✅ supported — danger/slow/speed/arc params read once in __init__ (reactive_stop_node.py:108-118) and _on_param_change (:173-197) only handles enable_nav_pause/safety_only/mode; start_nav_capability_demo_tmux.sh:30-46 implements REACTIVE_PROFILE with comments explicitly documenting the ros2-param-set-no-op footgun, cross-referenced to the 6/8 trackB HITL doc; 6/9 HITL execution doc confirms profile addition.
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py:108-118 (danger/slow/arc/speeds read once in __init__)
  - reactive_stop_node.py:173-197 (_on_param_change handles only enable_nav_pause/safety_only/mode)
  - docs/archive/superpowers-legacy/plans/2026-06-09-nav-vision-hitl-execution.md (6/9 HITL: must kill+restart with args; REACTIVE_PROFILE added)
  - scripts/start_nav_capability_demo_tmux.sh:33-46 (open_space|indoor_tight profile mitigation)
- **建議**：Freeze current behavior + REACTIVE_PROFILE for S1/6-18. Post-demo: extend _on_param_change to cover threshold/speed params (recompute _front_half_rad), or document init-only params in node docstring as a contract. Re-verify with a Jetson HITL before relying on runtime tuning.

### GO2RT-9 — CycloneDDS conn path is wired but stubbed; ~20 of 31 go2_interfaces msgs have zero consumers

- **分級**：⚪ low · `dead_code` · **POST_DEMO_ONLY**
- **查證**：✅ supported — CycloneDDS subscriptions wired at go2_driver_node.py:334-346 but all three callbacks are pass-stubs (:453-467); go2_interfaces/msg has 31 files and the 20 listed msgs have zero Python imports repo-wide (only WebRtcReq/VoxelMapCompressed/IMU/Go2State/LowState are consumed); LowState.msg confirmed to nest IMU/MotorState/BmsState.
- **證據**：
  - go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py:334-346 (cyclonedds subscriptions created) vs 453-467 (all three callbacks are pass)
  - grep over repo: AudioData/BmsCmd/Go2Cmd/Go2FrontVideoData/Go2Move/Go2RpyCmd/HeightMap/InterfaceConfig/LidarState/LowCmd/MotorCmd/PathPoint/Req/Res/SportModeCmd/TimeSpec/UwbState/UwbSwitch/VoxelHeightMapState/WirelessController = 0 Python imports (MotorState/BmsState/IMU kept as LowState.msg nested deps)
  - go2_interfaces/msg/LowState.msg (nested dep proof)
- **建議**：Either delete the cyclonedds branch + orphan msgs (faster interface builds, smaller contract surface) or mark them UPSTREAM-COMPAT in go2_interfaces/AGENTS.md. Interface changes force full downstream rebuild — strictly after 6/18.

### GO2RT-10 — robot.launch.py embeds a tts_node with deprecated ElevenLabs provider (dormant, enable_tts default false)

- **分級**：⚪ low · `dead_code` · **POST_DEMO_ONLY**
- **查證**：✅ supported — robot.launch.py:153 confirms enable_tts default false; lines 409-424 embed a speech_processor tts_node with provider:'elevenlabs', hardcoded voice id XrExE9yKIg1WjnnlVkGX and ELEVENLABS_API_KEY. CLAUDE.md states ElevenLabs deprecated (3/26 meeting) and both demo scripts pass enable_tts:=false at the cited lines, so the dormant dead-config claim holds.
- **證據**：
  - go2_robot_sdk/launch/robot.launch.py:153 (enable_tts default false), 409-424 (provider:'elevenlabs' + hardcoded voice id + ELEVENLABS_API_KEY)
  - CLAUDE.md: 'MeloTTS、ElevenLabs 已淘汰（3/26 會議確認）'; demo scripts always pass enable_tts:=false (scripts/start_full_demo_tmux.sh:136, scripts/start_nav_capability_demo_tmux.sh:90)
- **建議**：Delete the embedded tts_node block from robot.launch.py — speech stack ownership belongs to speech_processor launch/scripts. Anyone flipping enable_tts:=true today gets a dead provider.

## DEVOPS — Deploy / scripts / CI / test / HITL infra

### DEVOPS-1 — CI and pre-commit have zero test coverage of the demo-critical packages: interaction_executive, nav_capability, go2_robot_sdk, pawai_cli

- **分級**：🔴 high · `missing_tests` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Verified: ros_build.yaml pytest list covers only speech/vision/benchmarks/pawai_brain, Tier2 colcon scoped to 4 other packages, pre-commit smart-scope only speech/vision/face; I ran the claimed tests myself — nav_capability (31 pass), pawai_cli (16 pass), and 6 of 7 listed interaction_executive files (111 pass) run without ROS2. One caveat: test_safety_layer.py is NOT rclpy-free (safety_layer.py imports world_state.py which imports rclpy.node), so that one file in the evidence list is wrong, but the core zero-coverage claim is fully supported.
- **證據**：
  - .github/workflows/ros_build.yaml:44-91 (explicit pytest file list: speech/vision/benchmarks + pawai_brain only)
  - .github/workflows/ros_build.yaml:146-150 (Tier2 colcon scoped to go2_interfaces/speech_processor/face_perception/vision_perception)
  - scripts/hooks/git-pre-commit.sh:66-79 (smart-scope covers only speech/vision/face)
  - interaction_executive/test/ (13 test files; test_safety_layer.py, test_skill_contract.py, test_state_machine.py, test_pending_confirm.py, test_skill_queue.py, test_attention_machine.py, test_skill_contract_demo_fields.py are rclpy-free and CI-runnable today)
  - nav_capability/test/ (9 test files, rclpy-free: test_relative_goal_math.py, test_nav_ready_check.py, test_route_fsm.py, ...)
  - go2_robot_sdk/test/test_robot_control_service.py (authoritative StopMove/cmd_vel routing tests per CLAUDE.md 'Go2 sport mode cmd_vel = 0' section)
  - tools/pawai_cli/tests/ (6 files, ~2,150 LOC, incl. test_jetson_deploy_rsync_excludes_env_and_ssh)
  - references/project-status.md 6/10 §1 ('258 tests pass' for interaction_executive — local only)
- **建議**：Add a 3rd pytest invocation in ros_build.yaml fast gate for the rclpy-free interaction_executive + nav_capability + pawai_cli tests, and add these dirs to git-pre-commit.sh smart-scope. Pure CI/hook change, no runtime impact on 6/18 demo.

### DEVOPS-2 — Demo start false-success chain: full-mode start is backgrounded over SSH with output discarded, no post-start verification, CLI prints '✓ Demo running' regardless

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — start.sh:148-155 backgrounds start_full_demo_tmux.sh over SSH with '> /dev/null 2>&1 &' then blind 'sleep 30'; main.py:899-919 transitions lock to running and prints '✓ Demo running' based only on the wrapper rc; healthcheck.sh is merely suggested at start.sh:244-245. The documented 6/4 HITL false-success (CRLF abort, tmux never created, CLI still reported ✓) confirms this is a real, observed failure mode.
- **證據**：
  - .claude/skills/brain-studio-lane/scripts/start.sh:148-155 (`bash .../start_full_demo_tmux.sh > /dev/null 2>&1 &` then blind `sleep 30`)
  - tools/pawai_cli/pawai_cli/main.py:899-919 (rc only reflects start.sh wrapper; transitions lock to running and prints success)
  - .claude/skills/brain-studio-lane/scripts/start.sh:244-245 (healthcheck only suggested, never invoked)
  - CLAUDE.md 'Demo 啟動 / .env 環境陷阱（6/4 HITL 發現）' (documented real false-success: tmux never created, pawai demo start still reported ✓; operator SOP is manual tmux ls + ros2 node list)
- **建議**：After the 6/18 demo, make `pawai demo start` run a hard post-start gate: SSH `tmux has-session -t demo` + minimum `ros2 node list` count (reuse healthcheck.sh or jetson-verify demo profile) before transitioning lock to 'running'. Until then the manual tmux-ls SOP stays the defense.

### DEVOPS-3 — .env CRLF silent-abort and .env vs .env.local drift fixed only in the Python CLI layer; all demo shell scripts still raw-source .env under set -euo pipefail

- **分級**：🔴 high · `fragile_runtime` · **POST_DEMO_ONLY**
- **查證**：✅ supported — start_full_demo_tmux.sh has 'set -euo pipefail' (line 14) and raw-sources $WORKDIR/.env (lines 25-33) with no CRLF stripping; start.sh remote tmux windows raw-source .env at lines 135 and 167; main.py:24-50 contains the CRLF/BOM-normalizing loader with .env→.env.local override that exists only in the Python CLI. WSL repo root has only .env.local/.env.local.example (no .env), and CLAUDE.md 6/4 HITL explicitly notes the 5/14 CRLF defense never covered the .env source path.
- **證據**：
  - scripts/start_full_demo_tmux.sh:15,26-33 (set -euo pipefail + raw `source $WORKDIR/.env`)
  - .claude/skills/brain-studio-lane/scripts/start.sh:135,167 (remote tmux windows `set -a && source .env`)
  - tools/pawai_cli/pawai_cli/main.py:24-50 (_load_env_file CRLF/BOM normalization exists, .env then .env.local override — CLI only)
  - CLAUDE.md 6/4 HITL section ('5/14 已有 CRLF 防線但未覆蓋 .env source 路徑'; '.env vs .env.local 檔名漂移'; 'canonical 化是 roadmap follow-up')
  - WSL repo root has only .env.local + .env.local.example, no .env (ls .env*) while every start script expects .env
- **建議**：Canonicalize to one loader: a tiny scripts/lib/load_env.sh that strips CR before sourcing and falls back .env -> .env.local, sourced by all start_* scripts. Demo-critical scripts are frozen until 6/18; current mitigation stays `sed -i 's/\r$//' .env` + `cp .env.local .env` on Jetson.

### DEVOPS-4 — pawai jetson deploy prefers unaudited out-of-repo ~/sync over its own hardened rsync; the preferred path deleted Jetson .env (6/10 HITL) so the team bypasses the CLI entirely

- **分級**：🔴 high · `fragile_runtime` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — main.py:511-518 uses ~/sync unconditionally if executable with no exclude validation, while 520-544 fallback rsync excludes .git/.env/.env.*/.ssh/node_modules etc.; test_cli.py:785 tests only the fallback path (patches Path.home so ~/sync is absent); docs/pawai_cli/README.md documents the precedence. references/project-status.md 6/10 §4 (line 31) records the HITL outcome: team bypassed CLI deploy with safe manual rsync because ~/sync once deletes .env/node_modules.
- **證據**：
  - tools/pawai_cli/pawai_cli/main.py:511-518 (if ~/sync executable, use it unconditionally — no exclude validation)
  - tools/pawai_cli/pawai_cli/main.py:520-544 (fallback rsync correctly excludes .git/.env/.env.*/node_modules/build/install)
  - tools/pawai_cli/tests/test_cli.py:785-821 (excludes are unit-tested — but only for the fallback path)
  - references/project-status.md 2026-06-10 §4 ('deploy 走安全手動 rsync（CLI 的 ~/sync once 沒排除 .env/node_modules，會刪 → 繞過）')
  - docs/pawai_cli/README.md:256-257 (documents the ~/sync precedence)
- **建議**：Invert the priority (built-in rsync default, ~/sync only behind an explicit --use-sync flag) or grep ~/sync for the mandatory excludes before trusting it. The demo currently does not depend on CLI deploy (team uses manual rsync), so this is fixable now; carry into CLI v2 PRD.

### DEVOPS-5 — Four overlapping preflight/health systems; the demo-preflight skill is a broken runbook pointing at a script that does not exist

- **分級**：🟡 medium · `duplication` · **POST_DEMO_ONLY**
- **查證**：✅ supported — demo-preflight skill dir contains only SKILL.md whose lines 24-28 invoke .claude/skills/demo-preflight/scripts/preflight.py — find returns no such file anywhere in the repo, so the runbook is broken as claimed. The overlapping systems all verified: jetson-verify verify.py (277 LOC) + 3 profiles + 3 tests not in CI, lane preflight.sh (145/125 LOC) wired through CLI start paths (main.py _invoke_start_sh/_invoke_nav_start_sh), pawai doctor (main.py:171), and benchmarks/scripts/run_preflight.py (107 LOC).
- **證據**：
  - .claude/skills/demo-preflight/SKILL.md:24-29 (invokes .claude/skills/demo-preflight/scripts/preflight.py — `find . -name preflight.py` returns nothing; skill dir contains only SKILL.md)
  - .claude/skills/jetson-verify/scripts/verify.py (277 LOC declarative engine) + profiles/{smoke,demo,integration}.yaml + tests/jetson-verify/ (3 test files, not in CI)
  - .claude/skills/brain-studio-lane/scripts/preflight.sh (145 LOC) + nav-avoidance-lane/scripts/preflight.sh (125 LOC) — the only preflights actually wired into pawai CLI (main.py:640-649,725-729)
  - tools/pawai_cli/pawai_cli/main.py doctor command + benchmarks/scripts/run_preflight.py (fifth partial overlap)
- **建議**：CLI v2: one preflight engine (jetson-verify's YAML-profile shape is the right substrate) consumed by lane preflights and `pawai doctor`; delete or repoint demo-preflight SKILL.md now since it already cannot run as written.

### DEVOPS-6 — Dead scripts (~750 LOC) and a stale test-suite skill: pre-Megaphone audio experiments, archived nav launcher, CLI-rejected detour launcher

- **分級**：🟡 medium · `dead_code` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — All six scripts exist totaling 736 LOC (~750): start_nav2_demo_tmux.sh marked '不再啟用' at CLAUDE.md:556 and last touched 2026-05-01; the 3 audio scripts (404 LOC) were last touched 2026-03-17 and two were added in commit ed7495b which is literally 'switch to Megaphone DataChannel'; CLI rejects detour as 'intentionally unsupported; known unstable' (~main.py:755-758); audit_webrtc_publishers.py:30 references ab_test_audio.py. run_all_tests.py PACKAGES is frozen at 4 packages while pawai_brain/interaction_executive/nav_capability/object_perception/benchmarks all have test dirs, and grep shows no launcher/skill/CLI invoking the dead scripts (docs/plan references only).
- **證據**：
  - scripts/start_nav2_demo_tmux.sh (109 LOC; CLAUDE.md:556 'v3.6 cartographer pure-loc archive，不再啟用'; last touched 2026-05-01)
  - scripts/ab_test_audio.py, scripts/test_audio_track.py, scripts/test_mediaplayer_track.py (~404 LOC; superseded by Megaphone DataChannel, last touched 2026-03-17 in the very commit that switched to Megaphone)
  - scripts/start_nav_capability_demo_tmux_detour.sh (144 LOC; tools/pawai_cli/pawai_cli/main.py:760-762 rejects detour as 'intentionally unsupported; known unstable')
  - scripts/audit_webrtc_publishers.py (79 LOC one-off diagnostic referencing the dead ab_test_audio.py)
  - .claude/skills/ros2-test-suite/scripts/run_all_tests.py:16-33 (PACKAGES dict frozen at 4 packages; missing pawai_brain/interaction_executive/nav_capability/object_perception/benchmarks)
- **建議**：Move the 6 dead scripts to scripts/archive/ (none referenced by any launcher, skill, or CLI path) and extend ros2-test-suite PACKAGES to the current 9-package layout. Zero demo-flow contact.

### DEVOPS-7 — HITL evidence has no consistent format or landing zone; measured-result pipelines that should produce artifacts are broken or stranded on the Jetson

- **分級**：🟡 medium · `observability` · **POST_DEMO_ONLY**
- **查證**：✅ supported — All four HITL doc trees exist as prose with no shared format; test_results/ contains only .gitkeep (matching the CLAUDE.md 6/4 documented observer report-ack-timeout, with run_speech_test.sh:294-298 expecting summaries there); under_load_probe.sh:21 writes to $REPO/test_results/under_load/ on the Jetson side. benchmarks/results/raw and summary are empty while only results/archive/ has data, despite build_scoreboard.py and capture_baseline_round.py existing.
- **證據**：
  - docs/archive/navigation-legacy/research/2026-06-08-trackB-hitl-results.md, docs/archive/superpowers-legacy/plans/2026-06-09-nav-vision-hitl-execution.md, references/project-status.md dated sections, docs/archive/pawai-brain-legacy/research/2026-06-08-night-vision-brain-research.md (same class of HITL result in 4 different doc trees, prose-only)
  - test_results/ contains only .gitkeep (run_speech_test.sh observer report-ack-timeout → no CSV, documented in CLAUDE.md 6/4 section; scripts/run_speech_test.sh:294-298 expects summaries there)
  - scripts/under_load_probe.sh:14-22 (writes to Jetson-side test_results/under_load/, never synced to repo)
  - benchmarks/results/raw and benchmarks/results/summary are empty; only results/archive/ has data despite scoreboard tooling (benchmarks/core/build_scoreboard.py, capture_baseline_round.py)
- **建議**：Define one HITL evidence record (date, stack/profile, params, PASS/DEGRADED/FAIL, raw-log pointer) and one landing dir (benchmarks/results or docs/hitl/), then make under_load_probe / capture_baseline_round / nav HITL logs emit it. Pairs naturally with the scoreboard-first strategy already adopted.

### DEVOPS-8 — Claude PreToolUse guard blocks all .env access while .env state is the repo's #1 recurring failure mode, forcing every diagnosis to manual human steps

- **分級**：⚪ low · `observability` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — pre_tool_safety.sh:27 regex `\.(env|pem|key)(\s|"|$|/)` empirically blocks read-only probes (`[ -f .env ]`, `wc -l .env`, `test -f .env` all match) and is wired in .claude/settings.json for Bash; secret_guard blocks Edit/Write as described. Recurring .env incidents requiring manual SSH fixes are documented in CLAUDE.md 6/4 trap section and references/project-status.md 6/10 §4 (CLI sync deletes .env → manual rsync bypass).
- **證據**：
  - scripts/hooks/pre_tool_safety.sh (blocks any Bash command matching `\.(env|pem|key)` incl. read-only checks like `[ -f .env ]`)
  - scripts/hooks/pre_tool_secret_guard.sh (blocks Edit/Write of .env — appropriate)
  - CLAUDE.md 6/4 trap section + references/project-status.md 6/10 §4 (.env CRLF / deletion incidents requiring human SSH fixes)
- **建議**：Allow non-content .env probes (test -f, wc -l, file, `sed -n l` line-ending check via an allowlisted helper script) while keeping cat/edit blocked, so the agent can diagnose CRLF/missing-file without exposing secrets.

### DEVOPS-9 — Contract checker docstring claims report-only while it actually blocks on ghost topics; pre-commit discards its output entirely

- **分級**：⚪ low · `overclaim_risk` · **SAFE_TO_REFACTOR_NOW**
- **查證**：✅ supported — Docstring (lines 2-8) claims 'report-only... Exit code is always 0' while lines 257-274 sys.exit(1) on ghost topics; git-pre-commit.sh:53 discards all checker output via `> /dev/null 2>&1` leaving only a rerun hint. The WARN-never-block asymmetry for contract topics missing from code is confirmed at lines 250-251 and the exit-policy comments at 270-271.
- **證據**：
  - scripts/ci/check_topic_contracts.py:2-8 ('report-only, v1 ... Exit code is always 0') vs tail logic (ghost topics → sys.exit(1))
  - scripts/hooks/git-pre-commit.sh:53 (`check_topic_contracts.py > /dev/null 2>&1` — a blocked commit shows no failing topic, only a rerun hint)
  - asymmetry: contract topics missing from code are WARN-never-block, so contract removal regressions pass silently
- **建議**：Fix the stale docstring, let pre-commit show the checker's stderr on failure (drop 2>&1 redirect), and document the WARN-vs-FAIL asymmetry in docs/contracts/interaction_contract.md.

### DEVOPS-10 — Production lane lifecycle (start/cleanup/preflight/healthcheck) lives inside .claude/skills/ and the CLI hard-codes those paths — agent-skill folder layout is load-bearing ops infrastructure

- **分級**：🟡 medium · `ownership` · **POST_DEMO_ONLY**
- **查證**：✅ supported — CLI hard-codes .claude/skills lane-script paths at exactly the cited lines (main.py 642/700/713-715/727/734); LOC counts match (554/389) and the scripts encode lane mutual-exclusion, orphan-driver detection, and /dev/rplidar+map+runtime-dir gates, matching CLAUDE.md's documented `pawai demo start/stop` paths. Minor evidence inaccuracy: REACTIVE_PROFILE is not in the skill scripts (it lives in scripts/start_nav_capability_demo_tmux.sh, invoked without forwarding it), but this does not undermine the core ownership claim.
- **證據**：
  - tools/pawai_cli/pawai_cli/main.py:640-649,698-703,712-721,725-736 (subprocess paths into .claude/skills/brain-studio-lane/scripts/ and nav-avoidance-lane/scripts/)
  - .claude/skills/brain-studio-lane/scripts/{start,preflight,healthcheck,cleanup}.sh (~554 LOC) and nav-avoidance-lane equivalents (~389 LOC) encode HITL safety knowledge: lane mutual-exclusion checks, orphan-driver detection, REACTIVE_PROFILE, /dev/rplidar + map + runtime-dir gates
  - CLAUDE.md PawAI CLI section (these are the documented team-facing demo start/stop paths)
- **建議**：In CLI v2, promote lane scripts to scripts/lanes/ (or into the pawai package as data files) with the skills reduced to thin pointers; keep the encoded HITL knowledge (exclusivity checks, profiles) as the seed of the unified preflight system from DEVOPS-5. Frozen until after 6/18 since `pawai demo start` and the recording workflow depend on them.

