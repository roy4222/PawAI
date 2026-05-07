# PawAI Demo Test Execution Plan (5/7 Night Fail-Map)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tonight (5/7-8) run the v1.1 spec end-to-end on Jetson, build a complete fail-map, then triage P0/P1 fixes before 5/13 LM 307 trip.

**Architecture:** Two phases — (1) checklist artifact prep + 3 small spec/checklist fixes; (2) operational fail-map run following spec §4 (Part A) + §5 (Part B), record per §3 / §12 format, triage per §6 / §13. Each test task = one operation with explicit command + expected result + record format.

**Tech Stack:** ROS2 Humble (zsh), `colcon build`, tmux, `ros2 topic echo`, Studio (Next.js + WS gateway), markdown checklist + Studio trace log + phone video (per spec §3 三層交付物).

**Success criteria:** Operational checklist saved + 3 small fixes applied + complete fail-map markdown produced + all P0 fails triaged + final §7 main-script regression PASS.

---

## File Structure

| Path | Purpose | Action |
|---|---|---|
| `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-checklist-v2.md` | Operational checklist (v2 from user, with 3 fixes applied) | Create |
| `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md` | Fail-map result log (per §3 L1 + §12 format) | Create |
| `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-plan.md` | Spec v1.1 (already committed `8b12cad`) | Possibly bump to v1.2 if §6.2 trace name issue surfaces |

**Decomposition principle**: spec stays as the design document; checklist is the operational sheet; fail-map is the result. Three files keep concerns separated and let spec evolve without disturbing today's record.

---

## Phase 1 — Artifact Prep (30 min)

### Task 1: Save operational checklist v2 with 3 fixes applied

**Files:**
- Create: `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-checklist-v2.md`

**3 fixes to apply** (from cross-check earlier in this conversation):
1. §6.2 trace stage names → use actual graph node names: `input / safety_gate / world_state / capability / memory / llm / validator / repair / skill_gate / output / trace` (not `llm_decision`/`json_validate`)
2. §3.1 `careful_remind` trigger → not "提醒我小心"; instead Roy does bending pose → PAI 主動觸發 (move into §5.3 pose section, or remove from LLM-active test)
3. §2.1 早晚問候 → mark `(OBS)` not P0 hard gate

- [ ] **Step 1: Create checklist file with v2 content + 3 fixes**

Use the v2 content Roy posted in conversation. Apply the 3 edits above before writing. Add header:
```md
# PawAI Demo Test Checklist v2.1

> Operational sheet for spec `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-plan.md`
> Use with fail-map `2026-05-07-pawai-demo-test-fail-map.md`
> Mark: `PASS` / `FAIL→A:BLOCKER` / `FAIL→B:OBS` / `SKIP→C`
```

- [ ] **Step 2: Verify the 3 fixes are applied**

Run:
```bash
grep -n "json_validate\|llm_decision" docs/pawai-brain/specs/2026-05-07-pawai-demo-test-checklist-v2.md
grep -n "提醒我小心" docs/pawai-brain/specs/2026-05-07-pawai-demo-test-checklist-v2.md
grep -n "早晚問候" docs/pawai-brain/specs/2026-05-07-pawai-demo-test-checklist-v2.md
```
Expected: first two return empty; third returns the line and it has `(OBS)` marker.

- [ ] **Step 3: Commit**
```bash
git add docs/pawai-brain/specs/2026-05-07-pawai-demo-test-checklist-v2.md
git commit -m "docs(test): add operational checklist v2.1 (Roy's v2 + 3 cross-check fixes)"
```

### Task 2: Create empty fail-map result file

**Files:**
- Create: `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md`

- [ ] **Step 1: Create skeleton with §12 format**

```md
# PawAI Demo Fail-Map (5/7 Night)

> Records FAIL/OBS items only. PASS items just tick the checklist v2.1.
> Format per spec §12.

## Phase A — 7 Functions

(items appended as testing progresses)

## Phase B — Demo Main Flow

(items appended as testing progresses)

## Phase C — Triage Notes

(P0 fixes applied + verification results)
```

- [ ] **Step 2: Commit empty skeleton**
```bash
git add docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md
git commit -m "docs(test): seed fail-map result file"
```

---

## Phase 2 — Part A Run (4 hours)

**Strategy reminder (spec §4)**: fail-fast-to-record. Exception: if startup or safety risk, pause-and-fix immediately.

### Task 3: §1 Startup smoke (15m budget)

**Pre-flight commands:**
- [ ] **Step 1: Sync to Jetson**
```bash
~/sync once
```
Expected: rsync 完成、無錯誤。

- [ ] **Step 2: Build 5 packages on Jetson**
```bash
ssh jetson-nano "cd ~/elder_and_dog && colcon build --packages-select pawai_brain interaction_executive vision_perception speech_processor face_perception"
```
Expected: 5 packages built, no errors.

- [ ] **Step 3: Start full demo tmux**
```bash
ssh jetson-nano "cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh"
```
Expected: 10/10 windows up, no crash within 30s.

- [ ] **Step 4: Verify single chat publisher (spec v1.1 §1.2)**
```bash
ssh jetson-nano "ros2 node list | grep -E 'conversation_graph|llm_bridge'"
```
Expected: only `/conversation_graph_node` (langgraph default); NO `/llm_bridge_node`.

- [ ] **Step 5: Verify perception topics**
```bash
ssh jetson-nano "ros2 topic list | grep -E '/state/perception/face|/event/(gesture|pose|object)_detected|/brain/proposal'"
```
Expected: 5 topics all present.

- [ ] **Step 6: Record result in fail-map** (only if FAIL/OBS; else just tick checklist)

If PASS: tick all §1 boxes in checklist v2.1.
If FAIL: append to fail-map under "Phase A → §1" using spec §12 format. **STOP — startup is hard pause-and-fix exception**.

### Task 4: §2 Voice main chain (40m budget)

- [ ] **Step 1: 5-round dialogue baseline**

Speak into mic 5 prompts in sequence:
1. 「你好」
2. 「我是 Roy」
3. 「你記得我嗎」
4. 「現在幾點」
5. 「今天天氣如何」

Watch `/event/speech_intent_recognized` and `/tts` topics:
```bash
ros2 topic echo /event/speech_intent_recognized &
ros2 topic echo /tts &
```

Record per prompt: PASS / FAIL / OBS.

- [ ] **Step 2: Stop keyword test**

While TTS playing, say 「停」. Expected: TTS 立即靜音，下一輪 `stop_move` skill via safety_gate.

Repeat with: 「stop」, 「煞車」.

- [ ] **Step 3: Long sentence TTS**

Say: 「講一個短短的睡前故事」. Watch for:
- TTS 不漏整句、不卡死
- chunk 切割合理
- 後半段語氣（OBS）

- [ ] **Step 4: Network drop fallback**

Pull network for 10s during a query. Expected: Gemini timeout → DeepSeek (also fail) → RuleBrain rescue. System 不 crash。

- [ ] **Step 5: Record results in fail-map**

For each FAIL/OBS, append entry per §12. Move to §3 even if some fail (fail-fast-to-record).

### Task 5: §3 Brain × Skill chain (30m budget)

- [ ] **Step 1: 8 demo-safe skills via voice**

Voice triggers:
| 觸發句 | 預期 skill | 預期 trace |
|---|---|---|
| 「跟我打招呼」 | wave_hello | accepted |
| 「陪我坐一下」 | sit_along | accepted |
| 「你現在狀態如何」 | show_status | accepted |
| 「介紹一下你自己」 | self_introduce | accepted_trace_only（狗不動）|
| 「搖一下」 | wiggle | needs_confirm |
| 「伸個懶腰」 | stretch | needs_confirm |
| 「跳舞」 | dance | rejected_not_allowed |
| 「後空翻」 | (unknown) | rejected_or_blocked |

Watch `/brain/proposal` and `/brain/conversation_trace` for each.

- [ ] **Step 2: PendingConfirm flow**

After 「搖一下」 → needs_confirm → 比 OK gesture (0.5s 穩定) → wiggle execute.

Then test cancel: say 「搖一下」 → 不比 OK → 5s 後超時、不執行。

- [ ] **Step 3: Studio button: 完整自我介紹**

In Studio UI, click「完整自我介紹」button. Expected: 6-step sequence (say + motion × 3) 跑完。

- [ ] **Step 4: Trace coverage in DevPanel (?dev=1)**

Visually confirm in Studio DevPanel that 4 trace types appeared at least once: `accepted` / `needs_confirm` / `rejected_or_blocked` / `accepted_trace_only`.

- [ ] **Step 5: Record results**

Tick PASS in checklist; append FAILs to fail-map.

### Task 6: §4 Misfire suppression (25m budget)

- [ ] **Step 1: Stranger 5s accumulation**

Have a non-Roy face enter and stay 6s. Watch:
- `/state/perception/face` chip 顯示 unknown
- 4s 內 NO TTS
- 5s+ 觸發 stranger_alert（OR Studio-only chip if explain_only）

- [ ] **Step 2: Hand / reflection / glass**

Wave hand close to camera, glass reflection, etc. for 3 minutes. Expected: 0 TTS 打斷.

- [ ] **Step 3: Roy repeat greeting cooldown**

Roy walks in/out 3 times within 60s. Expected: only 1st triggers greet; 2nd-3rd silent (cooldown).

- [ ] **Step 4: Fall while talking**

Start a dialogue. Mid-reply, Roy 側躺. Expected:
- Studio 紅 fall chip 出現
- TTS 不被打斷
- `/event/interaction/fall_alert` 觸發但 `/tts` 沒新內容

- [ ] **Step 5: Cart / chair fallen check**

Place a cart in frame for 10s. Expected: 0 出聲打斷 (ankle-on-floor gate works).

- [ ] **Step 6: Record results**

This section is HEAVY in spec — any FAIL→A:BLOCKER here is P0 (出聲打斷 = demo-killer).

### Task 7: §5 Perception 4 sub-tests (90m total budget — split below)

Run sequentially, record success rate (B 類觀察).

- [ ] **Step 1: §5.1 Face — 25m**

Roy at 1.5m × 5 attempts → record `x/5`. 
Multi-person, side face, low light → OBS only.
Stranger misfire count per 5min → OBS.

- [ ] **Step 2: §5.2 Gesture — 20m**

OK / Thumbs / Palm / Peace each × 5 → record `x/5`.
Wave (side 45°) × 5 → OBS rate.
Wave (front), 轉圈 → mark SKIP→C.
Verify OK 0.5s stable check works.

- [ ] **Step 3: §5.3 Pose — 25m**

Standing × 5, sitting × 5 → record.
Side-lying / lying flat — verify Studio chip + 0 TTS.
Cart/chair static 10s — verify 0 false fall alert.
Squat → OBS.
Bending / akimbo / knee_kneel → SKIP→C or OBS.

- [ ] **Step 4: §5.4 Object — 20m**

Chair < 1.5m × 5, cup × 5 (red, blue, green pure colors), human × 3 → record success.
Color label in TTS template correct? PASS/FAIL.
White cup, mixed background → OBS.
Small object > 2m → SKIP→C.

- [ ] **Step 5: Record per spec §12 format**

For EACH sub-test, append 1 fail-map entry summarizing success rate even if technically PASS — gives Roy data for B 類 observation column.

### Task 8: §6 Studio (covered partly in Task 5; 10m residual)

- [ ] **Step 1: Verify already-tested elements**

If Task 5 step 4 confirmed 4 trace types + 11-stage trace + DevPanel works → tick §6.2 boxes.

- [ ] **Step 2: 5-function panel cycling**

Switch between gesture / pose / face / object panels in Studio while dialogue runs. Expected: 對話不中斷，panel 各自 live。

- [ ] **Step 3: Record OBS for big-screen clarity**

Subjective observation only — leave note in fail-map Phase C「Studio 觀眾視角」 box.

### Task 9: §7 Navigation (30m budget; reduce to 15m if env not ready)

- [ ] **Step 1: Determine env mode**

Is there ≥ 1.5m straight-line space at testing location? If NO → skip to Step 4 (degraded).

- [ ] **Step 2: Full goto_relative test (env ready)**

```bash
bash scripts/start_nav_capability_demo_tmux.sh
# wait ~50s for AMCL warmup + nav_ready=true
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 1.0}"
```
Mid-run, place box at 0.6m. Expected: reactive_stop triggers, `/state/nav/paused=true`.

- [ ] **Step 3: Resume**

Remove box. Expected: auto-resume, finish goal.

- [ ] **Step 4: Degraded mode (env not ready)**

Don't issue goto. Just verify:
```bash
ros2 topic echo /capability/nav_ready --once
ros2 topic echo /capability/depth_clear --once
```
Then wave hand 0.5m in front of D435 → `/capability/depth_clear` flips to false.

- [ ] **Step 5: Record results**

Detour / dynamic avoidance → SKIP→C unconditionally.

### Task 10: §A.9 Re-run BLOCKERS (30m budget)

- [ ] **Step 1: List all FAIL→A:BLOCKER from fail-map**

```bash
grep -E "FAIL→A:BLOCKER" docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md
```

- [ ] **Step 2: Reproduce each once**

For each blocker, repeat the trigger and record:
- Repro? YES / NO / INTERMITTENT
- Same trace path?

- [ ] **Step 3: Commit fail-map snapshot before triage**

```bash
git add docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md
git commit -m "docs(test): part A fail-map snapshot before triage"
```

---

## Phase 3 — Part B Demo Main Flow (90m budget)

### Task 11: §5 Spec — 3 rounds main script

- [ ] **Step 1: Round 1**

Run S0-S10 sequentially per spec §5 main script (10 steps). Record any FAIL.

S0  Roy 入鏡 → greet
S1  「你可以做什麼」→ 列六大功能
S2  「介紹一下你自己」→ trace_only
S3  Studio button → sequence
S4  「跟我打招呼」→ wave_hello
S5  Roy 拿紅杯 < 1.5m → object_remark
S6  「搖一下」→ confirm → OK → wiggle
S7  「陪我坐一下」→ sit_along
S8  Roy 側躺 → fall chip silent
S9  「跳舞」→ blocked
S10 「停」→ instant stop

- [ ] **Step 2: Round 2**

Repeat. Record.

- [ ] **Step 3: Round 3**

Repeat. Record.

- [ ] **Step 4: Verify hard gate (3 rounds 0 tolerance)**

Check: 誤觸 TTS 打斷 = 0? invalid skill 真動 = 0? stop 失效 = 0? 系統需重啟 = 0?

If any of the 4 hard gates fail any round → mark as A:BLOCKER P0.

- [ ] **Step 5: Verify trace coverage**

Did all 4 trace types (`accepted` / `needs_confirm` / `rejected_or_blocked` / `accepted_trace_only`) appear ≥ 1 time across 3 rounds? If NO → flag in fail-map.

### Task 12: Free interaction — 30m, OBS only

- [ ] **Step 1: Roy free interaction 15m**

No script. Just talk to PAI naturally. Note any awkwardness, 誤觸, freezes.

- [ ] **Step 2: Second person (if available) free interaction 15m**

Family member / 老師 if reachable. Same observation.

- [ ] **Step 3: Append OBS notes to fail-map Phase B**

Subjective only; no PASS/FAIL.

- [ ] **Step 4: Commit fail-map with full Part B**

```bash
git add docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md
git commit -m "docs(test): part B fail-map (3 rounds + free interaction)"
```

---

## Phase 4 — Triage (open-ended; 2-3h estimate)

### Task 13: Triage P0 BLOCKERs

Per spec §6 SOP.

- [ ] **Step 1: List P0 blockers**

```bash
grep -B1 -A8 "FAIL→A:BLOCKER" docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md
```

Classify per spec §13:
- P0 = main-chain break / stop / crash / 撞 / 摔 / queue
- P1 = single demo path break
- P2 = quality / numbers

- [ ] **Step 2: Sort fix order**

Write order to fail-map "Phase C — Triage Notes" section. P0 first, then P1.

- [ ] **Step 3: Fix top P0 — one at a time**

Per spec §6 修法守則:
- 改參數優先於改邏輯（YAML threshold > Python rule > 架構動）
- 改完跑該項驗證
- 改完跑一輪 §5 主腳本

For each fix:
1. Identify root cause from Studio trace log + repo grep
2. Apply minimal change
3. Rebuild affected package: `colcon build --packages-select <pkg>`
4. Sync to Jetson, restart relevant node
5. Re-run the failing test
6. Record fix in fail-map Phase C: file:line, change summary, verify result
7. Commit

```bash
git add <changed files>
git commit -m "fix(<area>): <issue> — verified by re-running §X test"
```

- [ ] **Step 4: Repeat for each P0**

Don't move to P1 until ALL P0 are resolved or explicitly accepted as "demo-time workaround" (e.g., 用話術繞過).

### Task 14: Triage P1 (if time permits)

Same process as Task 13 but for P1 entries. Stop when:
- 23:00 hard cutoff (sleep before 5/8 work)
- OR all P1 cleared

### Task 15: Final regression — re-run §5 main script once

- [ ] **Step 1: One full round of S0-S10**

Verify no regression introduced by triage fixes.

- [ ] **Step 2: Append final-round result to fail-map**

If still BLOCKERs remain → list as "carry-over to 5/13".

- [ ] **Step 3: Final commit**

```bash
git add docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md
git commit -m "docs(test): final regression after triage — N P0 fixed, M carry-over to 5/13"
```

---

## Phase 5 — Spec Sync (10m)

### Task 16: Update spec Changelog if anything material learned

- [ ] **Step 1: Decide if spec needs v1.2**

If fail-map revealed spec inaccuracy (e.g., trace stage names mismatch found in real run) → bump.
If only operational findings (e.g., wave_hello cooldown actually 60s not 30s) → just record in fail-map Phase C, don't touch spec.

- [ ] **Step 2: If bump, edit Changelog**

Append to `docs/pawai-brain/specs/2026-05-07-pawai-demo-test-plan.md`:
```md
| v1.2 | 2026-05-07 | Post-fail-map: <list material updates> |
```

- [ ] **Step 3: Commit**

```bash
git add docs/pawai-brain/specs/2026-05-07-pawai-demo-test-plan.md
git commit -m "docs(test): bump spec v1.2 with post-fail-map findings"
```

---

## Stop Conditions

- **Hard pause**: build / startup / safety risk → fix immediately, don't continue testing
- **Hard cutoff**: 23:00 — stop and sleep regardless of progress
- **Carry-over rule**: any unresolved P0 → write to "carry-over to 5/13" in fail-map Phase C and on 5/12 LM 307 night re-test before scoping the morning of 5/13

---

## Checklist Reminders (spec §6 修法守則 reprint)

- fail-map 收完才動手（exception: startup / safety hard-pause）
- 修一條測一條，不堆積
- 改參數優先於改邏輯
- 改完跑一輪 §5 主腳本
