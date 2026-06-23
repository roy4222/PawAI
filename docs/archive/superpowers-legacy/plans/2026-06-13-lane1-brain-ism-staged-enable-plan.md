# Lane 1：Brain v2 / ISM Staged Enable（2a-2d 提前）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核
> **上游**：[aggressive master](2026-06-13-aggressive-pre618-master-plan.md)（策略授權 B-1）、[ISM plan](2026-06-11-plan-ism-interaction-state-machine.md)（§7 staged enable 設計鎖定，本 plan 把其 **2a/2b/2c/2d** 提前並展開、**2e/2f/2g 不動**）、[系統 Phase 2 plan](2026-06-11-phase2-core-brain-ops-refactor.md)（2A post-6/18 段）
> **Code 現實基準**：`brain_node.py`（2141 行，shadow 已接線）、`interaction_state.py`（272 行，ISM Phase 0 核心）、19 個 `_suppressed` 早退（行號見 §2）

---

## 1. Goal

讓 ISM 從 shadow 觀測逐步**接管**Brain 裁決，按 ISM plan 既定順序開前四個 gate family：

- **2a demo_phase**：scene mask 裁決收進 ISM policy（行為等價切換，建立 staged enable 骨架）。
- **2b CONFIRM_PENDING 非黑洞**：confirm 在飛時每個 candidate 有明確去向（suppress-with-trace / supersede / preempt），30s timeout 統一由 ISM watchdog 管。
- **2c EXECUTING watchdog**：`active_plan` 卡死自癒——skill 不回終態時依 `SkillContract.timeout_s` 逾時 → 清 plan → 回 IDLE（殺 6/9 stranger 卡死全系統）。
- **2d SPEAKING chokepoint**：「現在能不能說」由 ISM 單點裁決，取代各 callback 散落的 `tts_playing` 查表（殺搶話）。

解的問題對映：搶話=2d、pending_confirm 黑洞=2b、active_plan 卡死=2c、事件優先序混亂=2a-2d 的 `_PREEMPTIBLE_BY` 表逐步權威化（完整優先序接管=2e/2f，post-6/18）。

## 2. Current state（code 實證，2026-06-13）

**ISM shadow 已收的資料**（6 個接點，全部 never-raises）：

| 接點 | 位置 | shadow 呼叫 |
|---|---|---|
| ACCEPT 側 | `_emit()` → `_ism_shadow_on_emit()`（brain_node.py:673-683） | `propose()`（推進狀態機，由真實訊號校正） |
| SUPPRESS 側 | `_suppressed()` 漏斗 → `_ism_shadow_on_suppressed()`（:685-699） | 純 `evaluate()`（不推進，保 parity） |
| skill lifecycle | `_on_skill_result()` → `_ism_shadow_on_skill_result()`（:736-760） | `apply_signal(SKILL_RESULT)` |
| confirm | `_on_chat_candidate()` 的 confirm request（:701-717）+ `_tick_pending_confirm()` timeout（:719-734） | `apply_signal(CONFIRM_RESULT)` |
| TTS edge + watchdog | `_tick_attention()` 10Hz piggyback → `_ism_shadow_tick()`（:772-789） | `apply_signal(TTS_ACK)` + `tick()` |
| operator reset | `_on_reset_context()`（:2068） | `apply_signal(OPERATOR reset)` |

**6/12 真機 soak 已證明**：state_transition 軌跡與 demo 動線對得上（`idle→executing:candidate:chat`→`operator_reset`）；**已捕獲 legacy/ISM 分歧樣本**（object 事件：legacy `attention_engaged` 擋、ISM accept）→ 這是 2e/2f（社交 candidate 化）不能急的直接證據，也是本 plan 把它們留在 post-6/18 的依據。

**19 個 `_suppressed` 早退 → gate family 歸屬**（行號為 2026-06-13 main）：

| family | 早退點 |
|---|---|
| 2a demo_phase | `_phase_allows`（:338，gesture/greet/object 共用） |
| 2b confirm | gesture `pending_confirm`（:1234）、object `pending_confirm`（:1824）、greet gate 的 pending 條件（:1633 複合）、pose sitting/bending 的 skip |
| 2c executing | gesture `active_plan`（:1239）、object `active_plan`（:1819）、greet gate 的 active 條件 |
| 2d speaking | object `tts_playing`（:1828）、greet gate 的 tts 條件、gesture `conversation_gate` 的 tts 部分（:1270） |
| 不動（2e/2f/post） | dedup（:887）、llm_allowlist（:1071）、capability_health（:1084）、skill_cooldown（:1097/:1484）、gesture_enabled（:1215）、stranger_alert_enabled（:1592）、greet_sitting_window（:1645）、greet_cooldown（:1654）、attention_engaged（:1813）、object_remark_dedup（:1877） |

**`ism_enabled` 不存在**；`interaction_state.py` 已有 8 態 / 優先序 P0-P4 / `_PREEMPTIBLE_BY` 表 / `evaluate()`（純）vs `propose()`（推進）/ watchdog（CONFIRM 30s + EXECUTING timeout_s）/ ERROR_RECOVERY 兩步回 IDLE。**測試基數**：IE 320（含 11 條 shadow parity）+ `test_brain_rules` 73 條 + ISM 純測 33 條。

## 3. Problems / gaps

1. **黑洞**：confirm 在飛時 object/greet/pose 雖有 trace（Plan E），但去向規則散在各 callback，無單一表保證「每個 candidate 有去向」；P0/P1（safety/alert）能否 preempt confirm **未驗證**（pose fallen 路徑與 pending_confirm 的交互要先寫 parity test 確認 legacy 行為）。
2. **卡死**：`active_plan` 無 timeout——skill 不回終態即永久占用（6/9 stranger 實證）；`SkillContract.timeout_s` 存在但 brain 從未消費；30 個 skill 的 timeout_s 值合理性從未審視。
3. **搶話**：`tts_playing` Bool 在 ≥5 處被各自查，race-prone；無單一 speaking 裁決點。
4. **scene mask**：`demo_phase` 是 hardcoded 表 `_PHASE_ALLOWED_KINDS`（:301），不在 ISM policy 內。
5. **比對與退路**：尚無「takeover 後 ISM 裁決 vs 原 legacy 預期」的持續比對手段；無 master kill flag。
6. **soak 盲點**：demo 重啟後 `ism_shadow_enabled` 歸 False（param 不持久），soak 數據會斷流。

## 4. Scope

- `interaction_executive/interaction_executive/brain_node.py`：staged enable 接線（4 個 stage、flag-gated）。
- `interaction_executive/interaction_executive/interaction_state.py`：僅在 parity 需要時做**等價性修正**（如 demo_phase 表搬入 policy）；不改 8 態與優先序設計。
- `interaction_executive/test/`：每 stage 一個測試檔或併入 `test_ism_takeover.py`（新）；既有 320 + 73 條零修改。
- soak 分歧分析：消費 Lane 2 T2-5 的 report endpoint（本 lane 只寫分析結論文件）。

## 5. Forbidden scope

1. **2e（ALERT/SAFETY 全表）、2f（自發社交 candidate 化）、2g（TTS utterance_id）不做**——6/12 分歧樣本（attention_engaged）證明社交路徑 ISM 與 legacy 有真實分歧，需 soak 數據收斂後 post-6/18 再動。
2. **source trust enforcement 不做**（B-2 建議 post-6/18）：`_STUDIO_BUTTON_BYPASS_CONFIRM`（:1437-1487 一帶）原樣保留——enforce 會讓 Studio nav 按鈕多一步 confirm，動發表日操作流程；正解是配 gateway 簽章（Lane 5 post-6/18）。本 lane 只在 trace 加 `source_trusted=false` 標記（觀測）。
3. **19 個早退死碼一行不刪**（刪碼=系統 Phase 5 T5B-3，硬依賴 G7）；takeover 後 legacy gate 變成 flag-off fallback 路徑，保留。
4. 不碰 `executive.yaml` / `start_full_demo_tmux.sh` / `.claude/skills/`——所有開關走 runtime `ros2 param set`；shadow 自動重開屬 Lane 3 B-7。
5. 不改 `PendingConfirm`、`SafetyLayer`、`AttentionMachine`、IE executor 本體；2b 是「裁決點收斂」不是重寫 confirm 機。
6. QUEUE verdict 第一版**不實作佇列重放**（QUEUE 一律降為 SUPPRESS-with-trace，reason 帶 `queue_v2_pending` 標記）——佇列重放是新行為爆炸面，post-6/18。

## 6. Proposed tasks

**Flag 架構（T1-0，全 stage 前置）**：

- `ism_enabled`（bool，declare 預設 **False**）= master 開關；False 時 4 個 stage 全失效 → 一鍵退 legacy。
- `ism_stage_2a_demo_phase` / `ism_stage_2b_confirm` / `ism_stage_2c_executing` / `ism_stage_2d_speaking`（bool，預設 **False**）。
- 生效 = `ism_enabled AND ism_stage_2x`；全部每次使用時讀（不在 `__init__` 快取——6/8 reactive_stop param 教訓）、`_on_set_params` 支援 runtime 切換。
- takeover 開啟的 family：shadow trace 照發並標 `authoritative=true`；**legacy gate 程式碼不刪**，由 flag 短路。

| Task | 內容 | 風險 | 驗證 |
|---|---|---|---|
| **T1-0** | flag 架構 + `test_ism_takeover.py` 骨架：all-off = 320+73 測試零變動全綠（byte-identical 斷言沿用 shadow parity 模式） | 低 | all-off parity 紅綠 |
| **T1-1（2a）** | demo_phase 接管：`_phase_allows()` 在 flag-on 時改由 ISM policy 判定（`_PHASE_ALLOWED_KINDS` 表搬入/對映 `interaction_state` 的 policy 入口，單源）；suppress 走既有 `_suppressed` 漏斗、reason 格式不變 | 低（表等價） | 全 phase×kind 矩陣 parity test：flag on/off 裁決逐格相同；73 brain_rules 綠 |
| **T1-2（2b）** | confirm 接管：flag-on 時 gesture/object/greet/pose 的 pending_confirm 早退改為「組 `Candidate` → `propose()` → 依 Decision 行動」，§3.5 表為準（P4 suppress-with-trace、P2 supersede 取消 confirm、P0/P1 preempt）；confirm 30s timeout 由 ISM watchdog 驅動（與既有 PendingConfirm 30s 對齊，**PendingConfirm 機制保留**、ISM 只當裁決源）。**前置子 task T1-2pre**：寫 legacy 行為快照測試（pose fallen × pending_confirm 的現行為），分歧處以 legacy 為準先行等價、preempt 增強標 flag 內新行為並單測 | 中 | 6/9 重演：confirm 卡住時 cup/greet 有去向（trace 斷言）；timeout 30s 回 IDLE；explicit speech 取消 confirm（與 legacy `:985-987` 等價）；fallen preempt 新行為單測 |
| **T1-3（2c）** | executing watchdog 接管：flag-on 時 `STARTED` 餵 ISM 帶 `timeout_s`（從 `SKILL_REGISTRY` 重查，不信 wire）；watchdog 逾時 → trace `watchdog_timeout:executing:{plan_id}` → 走 `_on_reset_context` 同等清理（清 active_plan/active_step）→ IDLE。**前置子 task T1-3pre（純審視）**：列 30 個 skill 的 timeout_s 值表，標不合理值（如 0/缺省）→ Roy 過目；timeout_s ≤0 的 skill watchdog 不武裝（保守） | 中（真實新行為） | 單測：mock skill 不回終態 → timeout 後 active_plan 清空 + trace；正常 skill 不被誤殺（timeout 前回終態）；6/9 stranger 場景重演自癒 |
| **T1-4（2d）** | speaking 接管：flag-on 時 object/greet/gesture 的 `tts_playing` gate 改由 ISM SPEAKING 狀態裁決（TTS edge 已在 shadow 接好）；QUEUE 降 SUPPRESS-with-trace（見 Forbidden 6） | 中（Bool race 時序） | parity：tts_playing=true 期間社交候選全 suppress 且 reason=`gate:speaking`；TTS 結束後放行；race 單測（edge 與 candidate 同 tick） |
| **T1-5** | soak 分歧分析報告：用 `pawai evidence pull` + Lane 2 T2-5 report，產出「legacy vs ISM 裁決分歧統計」文件（按 gate 分組、各附樣本 decision_id）→ 作為 2e/2f post-6/18 展開的數據基礎 | 零（純分析） | 文件落 `docs/pawai-brain/research/`，引用真實 JSONL |

## 7. Pure software tasks（WSL，可 AFK）

T1-0 / T1-1 / T1-2pre / T1-2 / T1-3pre / T1-3 / T1-4 的全部 TDD 實作與單測；T1-5 的統計腳本。全程 mock 事件序列，不需硬體。

## 8. Jetson / Go2 HITL tasks（Roy 在場）

每 stage 一個最小 smoke（全走 runtime param，先 `ism_enabled=true` 再開該 stage）：

| Stage | 最小 HITL smoke（各 ~10 min） | 需 Go2 |
|---|---|---|
| 2a | `demo_phase` 切 `s3_object` → 比手勢 → trace `phase:s3_object:gesture` suppress；切回 `all` 放行 | 否（感知流即可） |
| 2b | thumbs_up → confirm 在飛 → 拿杯子 → cup suppress-with-trace 非黑洞 → 比 OK → wiggle 執行；第二輪不比 OK → 30s timeout 回 IDLE | **是**（wiggle 動作） |
| 2c | 短暫開 `stranger_alert_enabled` 重演 6/9 卡死（或發不回終態的 mock skill_request）→ timeout_s 後 trace `watchdog_timeout` + cup/greet 恢復回應 | 建議是 |
| 2d | 觸發長 TTS（chat 長句）→ TTS 中拿杯子 → suppress `gate:speaking`；講完再拿 → 放行 | 否 |
| 收尾 | 每 stage 驗完保持該 flag on 繼續跑 10 min demo 動線，觀察無 callback 例外 / 無延遲回退，才算過 | — |

排程：2a/2b → HITL #1（6/14 晚）；2c/2d → HITL #2（6/15 晚）。任一 stage 失敗 → flag-off，修復後下個 HITL 再驗，**不擋其他 stage 之前的成果**。

## 9. Tests

- all-off byte-identical：320+73 既有測試零修改全綠（每 stage PR 必跑）。
- 每 stage parity / 行為測試（§6 表）；6/9 黑洞重演測試擴充為 takeover 版（shadow 版保留）。
- never-raises 紀律延續：takeover 路徑的 ISM 呼叫例外 → fallback legacy 行為 + error log（不是 drop 事件）——專屬單測：mock `propose()` 拋例外時行為 = flag-off。
- CI：純 ROS-free 斷言抽入 fast-gate Invocation 3 逐檔清單；rclpy 依賴測試走本機 tier（既有慣例）。

## 10. Rollback strategy

- **一鍵退**：`ros2 param set /brain_node ism_enabled false`（秒級、不重啟、全 stage 同退）。單 stage 退：對應 `ism_stage_2x false`。
- 每 stage 獨立 PR，可單刀 revert；legacy gate 碼全保留 = flag-off 即原行為。
- 發表日預設：6/17 回穩日只保留**已過 HITL 的 stage** 為 on；有疑慮一律 off（shadow 照常收數據，不影響發表）。
- 異常訊號（觸發即退）：brain callback 例外、事件→TTS 延遲明顯回退、HITL 中任何「該回應沒回應」且 trace 無法解釋。

## 11. Done criteria

1. T1-0~T1-4 merged，all-off 全綠；2a/2b HITL 過（最低標），2c/2d HITL 過（達標）。
2. 6/9 兩大黑洞場景在 takeover 模式下有 trace 證據的自癒/非黑洞行為。
3. T1-5 分歧報告落檔，2e/2f 的 post-6/18 展開條件成文。
4. 6/17 回穩日：發表日 flag 組合寫入 checklist 並彩排驗證。

## 12. Execution order

T1-0 → T1-1（2a）→ HITL → T1-2pre → T1-2（2b）→ HITL → T1-3pre → T1-3（2c）→ T1-4（2d）→ HITL → T1-5。嚴格串行開 stage（前一 stage HITL 未過不開下一個的 flag，但**實作可先行**）。

## 13. 6/18 presentation impact

- 正面：可講「Brain 互動狀態機已部分上線——confirm 不黑洞、卡死有 watchdog、說話有單一裁決點」，每句有 trace/HITL 證據；shadow soak 全程開著收 2e/2f 數據。
- 風險控制：發表日 flag 組合 = 6/17 驗過的子集；任何 stage 可秒退；最壞全退 legacy = 6/12 驗收過的行為。
- 不可講：「狀態機全面接管」「事件優先序已完全重構」（2e/2f 未做）。

## 14. Fable review checklist

- [ ] all-off parity 是每個 PR 的第一個測試且確實 byte-identical（斷言到 emit payload 級）
- [ ] flag 讀取無 `__init__` 快取；`_on_set_params` 覆蓋全部新 param
- [ ] takeover 路徑 never-raises：例外 fallback legacy（有單測）
- [ ] 2b 未動 PendingConfirm 機制本體；2c 清理走 reset 同等路徑（無半清狀態）
- [ ] timeout_s 從 SKILL_REGISTRY 重查（不信 wire payload）
- [ ] 19 早退零刪除；2e/2f/2g/source-trust 無夾帶
- [ ] reason 字串格式與 Plan E 既有格式一致（Lane 2 zh 表能對上）
- [ ] 每 PR 附「HITL 驗證項」清單供 Roy 照做

## 15. Codex implementation prompt template

```
你在 /home/roy422/newLife/elder_and_dog（branch: 新開 feature branch）。
任務：執行 Lane 1 Task <T1-x>（見 docs/superpowers/plans/2026-06-13-lane1-brain-ism-staged-enable-plan.md §6）。
紀律：
- TDD：先寫紅測試（含 all-off byte-identical parity），再實作到綠。
- 只動 §4 Scope 列的檔案；§5 Forbidden scope 一條不碰（特別：不刪 19 個 _suppressed 早退、
  不碰 executive.yaml / start_full_demo_tmux.sh、不動 2e/2f/2g）。
- flag 預設 False；每次使用時讀 param；_on_set_params 支援 runtime 切換。
- takeover 呼叫包 try/except，例外 fallback legacy 行為（加單測）。
驗證命令：
  python3 -m pytest interaction_executive/test/ -q          # 320+ 全綠零修改
  PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q
完成後：單 commit、PR 描述附 紅綠證據 + HITL 驗證項清單。不得 merge，等 Fable review。
```
