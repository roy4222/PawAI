# Spec 1 Writing Plan — LLM Naturalness / Self-Showcase A+

> **Status**: ready-to-execute
> **Date**: 2026-05-10
> **依據 spec**：[`2026-05-10-llm-naturalness-a-plus-design.md`](../specs/2026-05-10-llm-naturalness-a-plus-design.md)（14 點 review fix 後版本）
> **Demo 倒數**：5/16（剩 6 天）
> **總工時**：5.5 天（含 0.5d buffer）→ 5/15 完成
> **Branch**：`spec1/llm-naturalness-a-plus`（從 `fix/demo-motion-and-chat-polish` 開）
> **Owner**：Roy
> **Plan 用途**：把 spec 拆成可逐步 commit 的任務序列；每 phase 收尾有可執行驗證指令與 stop-the-line checkpoint。

---

## 0. 心法（執行時隨時對照）

1. **每 phase 完都跑驗證**，沒過不能進下一 phase。
2. **每個 sub-task 一個 commit**（commit message 帶 `[Spec1.Px.Ty]`），方便 rollback。
3. **不擴張 scope**：spec 沒寫的不要做。LangGraph 11 節點 / LLM JSON schema / 2-skill composition / 換模型 — 全部排除。
4. **Phase 5 結尾若 baseline diff 沒明顯改善 → 啟動 §11 Rollback 條件**，不要硬撐到 demo 當天。

---

## 1. 任務拆解一覽（給 TaskCreate / progress tracking）

| Phase | Sub-task | 工時 | 驗證 | 阻塞下一階段？ |
|---|---|:---:|---|:---:|
| P0 | branch + baseline 10-prompt | 0.5d | baseline md 落檔 | Y |
| P1.1 | 寫 MISSION.md | 0.3d | content review（無「老人/長者」字眼） | Y |
| P1.2 | 改 IDENTITY.md L24-27 | 0.1d | persona test pass | — |
| P1.3 | 改 EXAMPLES.md（5 改 + 5 新） | 0.3d | 行號比對 + manual review | — |
| P1.4 | 改 OUTPUT.md L21/L30/L35 | 0.1d | manual review | — |
| P1.5 | 改 CAPABILITIES.md | 0.1d | manual review | — |
| P1.6a | **新建** `pawai_brain/test/test_persona_load.py`（current repo 無此檔；可繼承 `test_conversation_graph_node.py` style） | 0.1d | 寫紅 → 紅 | Y |
| P1.6b | 改 `_load_persona` REQUIRED + BASE_ORDER + log | 0.2d | `test_persona_load.py` 紅 → 綠 | Y |
| P2.1 | `SkillPlan.source_llm_reply` field + `build_plan` 加參數 | 0.2d | `test_skill_plan_roundtrip.py` 紅 → 綠 | Y |
| P2.2 | `_plan_to_dict` / `_plan_from_dict` 加序列化 | 0.2d | round-trip test 綠 | Y |
| P2.3 | `_dispatch_step` call site 改造（`plan, step, step_idx`） | 0.3d | 既有 dispatch tests 綠 | Y |
| P2.4 | `_resolve_say_text` + `_first_say_idx` 三段邏輯 | 0.3d | `test_skill_contract_say_decoupling.py` | Y |
| P2.5 | `_on_chat_candidate` 三分支 (accepted/needs_confirm/rejected) | 0.5d | `test_chat_candidate_skill_gate.py` | Y |
| P3.1 | `SAY_TEXT_POOLS` + `_pick_from_pool` + history deque | 0.3d | `test_text_pool.py` | — |
| P3.2 | `GREET_KNOWN_PERSON_POOL` 10-15 條 / name | 0.2d | manual + smoke | — |
| P3.3 | `OBJECT_REMARK_POOL` 各 class 5-8 條 + 30min cooldown 沿用 | 0.3d | manual + smoke | — |
| P3.4 | 6 skill 第一個 SAY step `text=""` | 0.2d | smoke：rule 路徑走 pool | Y |
| P4.1 | `self_introduce` 重構（雙 SAY `text=""` + 4 motion） | 0.3d | Studio button smoke | — |
| P4.2 | 收尾 SAY 簡化分支判斷（雙 LLM call vs 單 LLM call） | 0.2d | Jetson smoke | — |
| P5.1 | wave_hello / sit_along / stand / wiggle / stretch / careful_remind 解綁 | 0.5d | unit tests | — |
| P5.2 | Jetson smoke：每 skill 各 3 trigger 看不重複 | 0.5d | tmux 跑全 stack | Y |
| P6.1 | A+ 10-prompt 跑（temperature 0.8 × 3） | 0.3d | `spec1_a_plus_2026-05-15.md` 落檔 | — |
| P6.2 | baseline diff + 質性 review + go/no-go | 0.2d | review 表 + 決定是否啟動模型 A/B | — |

---

## 2. Phase 0 — 前置準備（5/10–11，0.5d）

### Tasks

```bash
# 1. 開 feature branch
git checkout -b spec1/llm-naturalness-a-plus

# 2. 確認 4fd148c 是 current main 的對應點（spec 引用的 baseline commit）
git log --oneline main | head -5

# 3. 跑 baseline 10-prompt（已有 tools/llm_eval/ 的話）
ls tools/llm_eval/ 2>/dev/null
# 若無：建立 tools/llm_eval/baseline_eval.py（template 用 spec §8.2 prompt 表）
# 跑 3 輪取代表性 reply，落 tools/llm_eval/baseline_2026-05-10.md
```

### 驗證
- [ ] feature branch 建立成功
- [ ] `tools/llm_eval/baseline_2026-05-10.md` 落檔（10 prompt × 3 reply 各一段）
- [ ] baseline 結果列出**現存 4 個無聊點**證據（self_introduce 死板、wave_hello hardcoded、greet 重複、object_remark 罐頭）

### Checkpoint（Stop-the-line）
若 baseline 結果其實**沒那麼死板**（例如 5/9 commits 已改善很多）→ 重新評估 Phase 1-5 範圍。可能不需要全做。

---

## 3. Phase 1 — Persona 6 檔（5/11，1d）

> **依賴**：P0 完成。
> **核心改動點**：spec §5 + §10 Phase 1。

### P1.1 新建 MISSION.md（0.3d）

- 路徑：`pawai_brain/personas/v1/MISSION.md`
- 內容：spec §5.1 整段（看懂 / 理解 / 決策 / 行動 四主軸）
- **禁字檢查**：
  ```bash
  grep -nE "老人|長者|長輩|陪伴" pawai_brain/personas/v1/MISSION.md
  # 應為 0 match
  ```

### P1.2 改 IDENTITY.md L24-27（0.1d）
- 砍能力清單句、改情境化敘述（spec §5.2）

### P1.3 改 EXAMPLES.md（0.3d）
- 5 個 identity few-shot：`self_introduce` → `chat_reply`（行號見 spec §5.3 表）
- 新增 5 條 self-showcase（spec §5.3 後段）

### P1.4 改 OUTPUT.md（0.1d）
- L21 / L30 / L35（spec §5.4 表）

### P1.5 改 CAPABILITIES.md（0.1d）
- 砍 L6-15 強制句、改自然語氣表（spec §5.5）

### P1.6a 新建 `test_persona_load.py`（0.1d）

> 5/10 確認：`pawai_brain/test/` 底下**沒有** `test_persona_load.py`，只有 `test_conversation_graph_node.py` 等 16 個檔案。本 plan 之前假設此檔存在 — 修正為先建檔。

選一條路：

**A（建議）**：新建獨立檔案 `pawai_brain/test/test_persona_load.py`
- 仿 `test_conversation_graph_node.py` 的 fixture / mock 結構
- 主要 assert：
  - 6 檔（含 MISSION.md）都能讀到
  - base prompt 含 IDENTITY + MISSION + STYLE + OUTPUT + EXAMPLES（5 檔）
  - CAPABILITIES.md 不在 base，是 lazy
  - 開機 log 出現 "6 files / base 5"
- 先寫紅（assert 6 但目前載 5），P1.6b 改 code 後綠

**B（替代）**：在現有 `test_conversation_graph_node.py` 補 persona load case
- 適合 fixture 已寫好的場合
- 但若該檔 mock 範圍跟 `_load_persona` 解耦不完全 → 走 A

### P1.6b 改 `_load_persona`（0.2d）

實際行號：`pawai_brain/pawai_brain/conversation_graph_node.py:349-393`（已確認 5/10）

```python
# L383
REQUIRED = ["IDENTITY.md", "MISSION.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md", "CAPABILITIES.md"]
# L384
BASE_ORDER = ["IDENTITY.md", "MISSION.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md"]
```
log 訊息「5 files / base 4」改「6 files / base 5」。

### 驗證

```bash
colcon build --packages-select pawai_brain
source install/setup.zsh
pytest pawai_brain/test/test_persona_load.py -v
# 預期 assert：MISSION.md 在 base prompt、CAPABILITIES.md 在 lazy
```

### Checkpoint
- [ ] 6 檔都載入、log 顯示「6 files / base 5」
- [ ] base prompt token 預算未爆（manual：dump system_prompt 到 stdout，目視 < 4k tokens）

---

## 4. Phase 2 — SAY 解綁機制（5/12, 1.5d）

> **依賴**：P1.6 通過。
> **核心改動點**：spec §6.2。
> **這是整個 Spec 1 最高風險的 phase**：動到 brain ↔ executive contract，要嚴格做 round-trip test。

### P2.1 SkillPlan + build_plan（0.2d）

- 檔案：`interaction_executive/interaction_executive/skill_contract.py:86`（class SkillPlan）+ `:641`（build_plan）
- 改動：spec §6.2.1 + §6.2.4b
- **先寫測試紅 → 改 code 綠**（TDD）：
  ```python
  # interaction_executive/test/test_skill_plan_roundtrip.py
  def test_source_llm_reply_roundtrip():
      plan = build_plan("wave_hello", {}, source_llm_reply="[playful] 嘿 Roy！")
      d = brain_node._plan_to_dict(plan)  # P2.2 完成才綠
      restored = exec_node._plan_from_dict(d)
      assert restored.source_llm_reply == "[playful] 嘿 Roy！"
  ```

### P2.2 序列化（0.2d）

- `brain_node.py:270` `_plan_to_dict` 加 `"source_llm_reply": plan.source_llm_reply`
- `interaction_executive_node.py:250` `_plan_from_dict` 加 `source_llm_reply=payload.get("source_llm_reply")`（用 `.get` 確保向後相容）

### P2.3 `_dispatch_step` call site 改造（0.3d）

實際行號：`interaction_executive_node.py:149`（call site）+ `:177`（定義）

- 簽名：`_dispatch_step(self, plan, step, step_idx)`
- queue worker 也要對應改（搜 `_dispatch_step` 全 call site，確認都帶 plan/step_idx）

### P2.4 `_resolve_say_text` + `_first_say_idx`（0.3d）

- 實作 spec §6.3 三段邏輯
- 寫測試 `test_skill_contract_say_decoupling.py`：
  - case A: `source_llm_reply` 非空 → 用之
  - case B: `step.args["text"]` 非空 → 用之
  - case C: 兩者皆空 → 走 `SAY_TEXT_POOLS`（P3.1 寫好後才綠）

### P2.5 `_on_chat_candidate` 三分支（0.5d）

- 檔案：`brain_node.py:396`
- 實作 spec §6.2.5 三分支：accepted / needs_confirm / rejected-cooldown-blocked
- **review 1 + 3 fix 重點**：`needs_confirm` 不 emit motion plan、用 module-level `build_plan`
- 寫 `test_chat_candidate_skill_gate.py`：
  - rejected → emit chat_reply（不靜音）
  - cooldown → emit chat_reply
  - needs_confirm → emit chat_reply + register PendingConfirm，**沒** motion plan
  - accepted → emit skill plan（含 source_llm_reply），**沒** 額外 chat_reply

### 驗證

```bash
colcon build --packages-select interaction_executive
source install/setup.zsh
pytest interaction_executive/test/ -v -k "skill_plan_roundtrip or say_decoupling or chat_candidate_skill_gate"
```

### Checkpoint（Stop-the-line）
- [ ] round-trip JSON 序列化向後相容（舊 plan 沒 `source_llm_reply` 欄位 → 還原成 None，不 crash）
- [ ] 既有 dispatch tests 全綠（沒打破現有功能）
- [ ] `_on_chat_candidate` 三分支單測全綠

---

## 5. Phase 3 — text_pool 變體池（5/13 早, 1d）

> **依賴**：P2 全綠。

### P3.1 SAY_TEXT_POOLS 主架（0.3d）
- spec §6.3 整段 module dict
- `_pick_from_pool(skill, plan)` + `self._text_pool_history: dict[str, deque(maxlen=3)]`
- test：連 6 次 wave_hello pick，前 3 次絕不重複；7 次後可能回收

### P3.2 GREET_KNOWN_PERSON_POOL（0.2d）
- spec §6.2 範例：roy / grama / _default
- name 透過 `plan.args["name"]` 帶入 `_default` template

### P3.3 OBJECT_REMARK_POOL（0.3d）
- 各 object class 5-8 條（cup / bottle / book / chair / _default）
- 30min cooldown：沿用 brain_node 端現有 dedup（不在 pool 內處理）

### P3.4 6 skill 第一個 SAY step text=""（0.2d）
- skill_contract.py：`wave_hello` / `sit_along` / `stand` / `wiggle` / `stretch` / `careful_remind`
- self_introduce 留 P4 處理

### 驗證
```bash
pytest interaction_executive/test/test_text_pool.py -v
# tmux smoke: 連續觸發 wave_hello 3 次，看 reply 都不同
```

### Checkpoint
- [ ] 任一 skill rule 路徑（無 LLM reply）走得到 text_pool
- [ ] history deque 每個 skill 獨立、跨 skill 不互相干擾

---

## 6. Phase 4 — self_introduce 重構（5/13 晚, 0.5d）

> **依賴**：P3 完成。

### P4.1 skill_contract 重構（0.3d）
- spec §7.2：雙 SAY `text=""` + 4 motion (hello / sit / stand_down / balance_stand)
- 確認 Studio button 仍能觸發（路徑：button → brain emit plan，無 LLM reply → 第一個 SAY 走 pool）

### P4.2 收尾 SAY 簡化分支（0.2d）
- 預設 demo 用**簡化版**：砍尾 SAY，保留 1 個 LLM 開場 + 4 motion
- 雙 LLM call 版本標記為 future work（節省複雜度，避免 demo 風險）

### 驗證
- [ ] Studio button 觸發 self_introduce → 開場 SAY 從 6 條變體中挑一條
- [ ] 連觸 3 次 → 3 條不同變體
- [ ] 4 motion 順序執行成功（Jetson 實機）

---

## 7. Phase 5 — 6 skill SAY 解綁全收（5/14, 1d）

> **依賴**：P4 完成。

### P5.1 6 skill 各 5 條 fallback 變體（0.5d）
- `wave_hello` / `sit_along` / `stand` / `wiggle` / `stretch` / `careful_remind`
- 用 §6.3 已寫好的 `SAY_TEXT_POOLS` 條目（P3.1 已建）→ 這裡只是補完內容、寫 test

### P5.2 Jetson 全鏈路 smoke（0.5d）
```bash
# Jetson 上
bash scripts/start_full_demo_tmux.sh
# 各 skill 觸發 3 次（語音 + Studio button）
# 觀察：
#   - LLM 路徑：reply 與 SAY 一致（不重複播）
#   - Rule 路徑：text_pool 取 3 條不同
```

### 驗證 / Checkpoint
- [ ] LLM 提案 wave_hello → SAY 用 LLM reply、不雙播
- [ ] Studio button wave_hello → SAY 走 pool、5 次內最多重複 1 次
- [ ] Roy 入鏡 greet_known_person → 連 3 次都不同句
- [ ] safety skill 全部不變（stop_move / stranger_alert / fallen_alert hardcoded 仍生效）

---

## 8. Phase 6 — 驗收 + benchmark（5/15, 0.5d）

### P6.1 跑 A+ 10-prompt（0.3d）
```bash
python tools/llm_eval/spec1_a_plus_eval.py > tools/llm_eval/spec1_a_plus_2026-05-15.md
# spec §8.2 表 × 3 輪
```

### P6.2 baseline diff + 質性 + go/no-go（0.2d）
- 比 `baseline_2026-05-10.md` vs `spec1_a_plus_2026-05-15.md`
- 對照 spec §8.2 pass criteria：≥ 8/10 pass → A+ 鎖、不啟動模型 A/B
- 5/10 ≤ pass ≤ 7：跑模型 A/B（spec §9）
- < 5：rollback（§11）

### Checkpoint（Demo Go/No-Go）
- [ ] 10/10 或 ≥8/10 → 鎖 v1.1-A+，準備 5/16 demo
- [ ] 5-7/10 → 啟動 §9 模型 A/B，但要在 5/15 結束前決定（不要拖到 demo 當天）
- [ ] < 5/10 → §11 rollback，切回 v1.0 跑 demo

---

## 9. 不在這份 plan 的事（嚴格排除）

照 spec §4 排除清單：

❌ LLM JSON schema 改動
❌ `output.skills: list` / 2-skill composition
❌ ReAct loop / 完整 OpenClaw 9 層
❌ LangGraph 11 節點任何一個
❌ nav_capability 整合 / follow mode
❌ 手勢 9 種 enum 擴充（→ Spec 2）
❌ 姿勢 7 種綁定（→ Spec 3）
❌ 換更聰明的模型（A+ 後再決定）

如果執行中發現「順便改一下會更好」 → **不要**，記到 `docs/pawai-brain/dev-logs/` 留待 demo 後。

---

## 10. Rollback 機制

### Feature flag

新增 persona version param：
```yaml
# pawai_brain config
persona_version: v1.1-A+   # 新版（spec 1 後）
# persona_version: v1.0    # 舊版 fallback
```
`_load_persona` 看 flag 決定載哪份 persona 目錄（`personas/v1/` vs `personas/v1.0-archive/`）。

P1 開頭先 archive 一份 v1.0 → `personas/v1.0-archive/`。

### Rollback 條件

| 觸發 | 動作 |
|---|---|
| P2 round-trip test 連 3 次無法綠 | 退回 P1，把 §6.2 改動全部 revert，spec 1 改用 §11 簡化版（只改 persona、不解綁 SAY） |
| P5.2 Jetson smoke regression | revert P3-P5 commits，保留 P1 persona 改動 |
| P6 ≤5/10 pass | 切 `persona_version=v1.0` demo，spec 1 延後 |

### 簡化版（emergency fallback）
若 P2 SAY 解綁實作風險過高 → spec 1 簡化為「只改 persona 6 檔（P0+P1）」，SAY hardcoded 不動。
雖然犧牲多變體 / LLM reply 灌入，但持身體驗仍可改善（MISSION.md + 自我展示 few-shot 即足以解決「不知道自己是誰」）。

---

## 11. 進度回報節奏

每 phase 結束時更新：
- `references/project-status.md`（spec 1 進度欄）
- 本 plan 的「驗證 [ ]」勾選

每日收工跑 `update-docs` skill 同步。

---

## 12. 給後續 Spec 2 的指針

A+ 完成後：
- Spec 2 lightweight plan：基於本 plan 範本、但 phase 數 ≤ 3
- 共用本 plan 的 `text_pool` 機制（gesture command 觸發的 SAY 也走 pool）
- 共用 feature flag 機制（gesture mapping 也走 v1.0 / v1.1 切換）

---

**End of Spec 1 Plan**
