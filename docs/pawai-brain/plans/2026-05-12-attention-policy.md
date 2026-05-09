# Branch D — Attention Policy Skeleton Plan

> **Skeleton plan** — task list 列改哪檔做什麼，不寫 TDD step 細節。實際開工前 expand。

**Goal:** 解 issue 4（路過/同物體重複觸發干擾）。4 狀態 attention machine + emit gate + dedup key 改 class_name + `_has_active_skill_or_sequence` 修 SKILL 不擋 SKILL。

**Spec 來源:** `docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md` P2-1 Attention Policy。

**前置依賴**: Branch B merged（B 改 brain_node.py:447-456 LLM_PROPOSAL_EXECUTE，避免衝突）。

**工時**: ~1 天

---

## File Structure

```
interaction_executive/interaction_executive/attention_machine.py   # NEW — 4 state machine module
interaction_executive/interaction_executive/world_state.py         # MODIFY — 加 attention field
interaction_executive/interaction_executive/brain_node.py          # MODIFY — gate logic + dedup + helper rename
interaction_executive/test/test_attention_machine.py               # NEW — 8 unit tests
```

**brain_node.py 改動點**（spec L702-803）：
- L67 `OBJECT_REMARK_DEDUP_S = 60.0` 保留
- L256-259 `_has_active_sequence` → `_has_active_skill_or_sequence`（修 SKILL 不擋 SKILL bug）
- L637-640 `greet_known_person` per-identity 20s cooldown 保留 + 加 attention gate（僅 ENGAGED）
- L715 `_on_object`：spec 明確不讀 distance_m（payload 無此欄位）；改加 attention + active_plan + pending + tts not 條件
- L760-764 dedup key 從 `(class_name, color)` 改 `class_name only`

---

## Task D-1: AttentionMachine 純 Python state machine

- [ ] 建 `attention_machine.py` 4 狀態：
  - `IDLE`: 無 face ≥ 0.5s
  - `NOTICED`: face stable
  - `ENGAGED`: distance ≤ 1.6m AND dwell ≥ 1.5s
  - `INTERACTING`: 任意 skill active
- [ ] threshold 定義：dwell 1.5s / face_lost 3s / quiet 8s / engaged_distance 1.6m
- [ ] state transitions：
  - IDLE → NOTICED: face appear
  - NOTICED → ENGAGED: distance ≤ 1.6m AND dwell ≥ 1.5s
  - NOTICED → IDLE: face lost ≥ 3s
  - ENGAGED → INTERACTING: plan emit / speech intent
  - INTERACTING → ENGAGED: active_plan done + 8s 安靜
  - INTERACTING → IDLE: face lost ≥ 3s
- [ ] tick(now, face_msg, plan_active) → return current state + transitions list
- [ ] 8 unit tests 涵蓋每個 transition + threshold edge cases
- [ ] commit

## Task D-2: Wire AttentionMachine into brain_node

- [ ] brain_node `__init__` 建 `self._attention = AttentionMachine(...)`
- [ ] `_on_face_state` callback 推 face msg 給 attention
- [ ] 10Hz tick timer 跑 attention.tick()
- [ ] state.attention field 加進 `/state/pawai_brain` JSON broadcast（讓 Studio Trace Drawer 顯示）
- [ ] commit

## Task D-3: Emit gate per skill

- [ ] `greet_known_person`：emit 條件加 `attention.state == ENGAGED`（per-identity 20s cooldown 保留）
- [ ] `object_remark`：emit 條件加 `attention.state == ENGAGED AND not active_plan AND not pending_confirm AND not tts_playing`
- [ ] `gesture confirm (thumbs_up/OK→wiggle)`：在 `NOTICED+` 允許（不擋走過去比 OK）
- [ ] `speech intent`：任何狀態允許（語音是明確互動邀請）
- [ ] `stranger_alert`：`NOTICED+` + 已有 3s 累積（不變）
- [ ] `fallen_alert`：任何狀態（safety override）
- [ ] commit

## Task D-4: dedup key 改 class_name + active skill guard 修

- [ ] `brain_node.py:760-764` dedup_cache key 從 `(class_name, color)` 改 `class_name only`
- [ ] `_has_active_sequence` rename → `_has_active_skill_or_sequence`：擋 SEQUENCE + SKILL（修 SKILL 不擋 SKILL bug）
- [ ] 既有 callsite 全更新到新名字
- [ ] commit

## Task D-5: integration tests

- [ ] 模擬「Roy 路過比 OK」場景時序：
  - t=0 face stable → NOTICED（不發 greet）
  - t=0.5 thumbs_up → PendingConfirm（NOTICED 允許 gesture）
  - t=1.0 OK → wiggle → INTERACTING
  - t=1.5 椅子 → state ≠ ENGAGED → 靜音
- [ ] 模擬「Roy 停下來互動」：
  - dwell ≥ 1.5s + dist ≤ 1.6m → ENGAGED → greet 才發
- [ ] 模擬「同椅子顏色抖動」：dedup key class_name → 60s 內不繞過
- [ ] 模擬「active wave_hello 中椅子入鏡」：object_remark not emit（active_plan guard）
- [ ] commit

## Task D-6: Jetson smoke

- [ ] 5 場景驗：
  1. 路過比 OK 5 次：face greet 出現 ≤ 2 次
  2. 停下來互動：dwell ≥ 1.5s + dist ≤ 1.6m → greet 發
  3. 同咖啡色椅子 60s 內 5 次入鏡 → object_remark 1 次
  4. wiggle skill 中入鏡椅子 → 不打斷
  5. fallen 偵測：任何 attention 狀態都觸發 alert
- [ ] dev-log 結果

---

## Verification

- [ ] `python3 -m pytest interaction_executive/test/test_attention_machine.py -v`：8 tests PASS
- [ ] `python3 -m pytest interaction_executive/test/ -v`：0 regression
- [ ] Jetson smoke 5 場景全 PASS

---

## Out of Scope

- Gaze detection（D435 視角不穩，5/13 demo 來不及）
- Exponential backoff cooldown
- DISENGAGING 5 狀態
- object_remark distance gate（payload 無 distance_m，demo 後再做）
- RL/HMM
