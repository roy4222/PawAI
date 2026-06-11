# Plan ISM: Interaction State Machine（PawAI Brain v2 互動流程）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development（建議）或 superpowers:executing-plans 逐 task 執行。步驟用 checkbox（`- [ ]`）追蹤。
> **本 plan 的特殊性**：這是「施工圖」。**Phase 0–1 是可立即執行的完整 TDD 任務**（純模組 + shadow 觀測）；**Phase 2–3 是設計鎖定的遷移序列**，每個 sub-phase 是一個獨立 flag-gated PR，但詳細 TDD 步驟刻意延後到 shadow 數據落地後再展開（master plan §7.8 + §7.7「狀態草案可被 trace 數據修正」）。不要在 Phase 0–1 完成前展開 Phase 2 的逐行實作。

**Goal:** 把 PawAI Brain 現在「5 個 callback 各自搶 TTS/plan、demo flag + cooldown + active_plan + pending_confirm 混在一起」的隱式狀態，重構成一個**顯式互動狀態機（ISM）**：感知事件只產生候選、由單一 policy 對照當前狀態裁決、優先序鐵律 `safety > explicit command > confirm > 自發社交`、每個 active interaction 有 watchdog、confirm 在飛時其他事件 queue-or-suppress-with-trace 不黑洞。

**Architecture:** 抽一個 **ROS-free 純模組** `interaction_state.py`（State enum + Candidate/Signal/Decision 型別 + 純函式 policy + `InteractionStateMachine` 類別），單測完整覆蓋。先 **shadow 模式**（`ism_shadow_enabled`，預設關）餵真實事件、發 STATE_TRANSITION trace 與 legacy 裁決並排比對、**不改行為**；再 **逐 gate family flag-gated 切換**（`ism_enabled`，預設關，v1 fallback）；最後翻 default + 刪 legacy。複用 Plan D Router（乾淨事件）+ Plan E Trace（裁決比對 + 回答「為什麼沒反應」）。

**Tech Stack:** Python dataclass + Enum（純模組，無 rclpy）、pytest、ROS String JSON `/brain/trace`（Plan E）、`pawai_contracts`（State/TraceKind 共用真相）。

---

## 0. 必讀：本 plan 受 master plan §7 凍結約束綁定

本 plan 的每條設計都必須對齊 [`post-demo-refactor-master-plan.md`](2026-06-10-post-demo-refactor-master-plan.md) §7 的 8 條 ISM 設計約束（D6 拍板）。逐條對應見 §3 設計，摘要：

1. **感知事件永不直接改狀態** → 只產生 candidate，policy 裁決（§3.3 source trust）。
2. **優先序鐵律** `safety > explicit command > confirm > 自發社交`（§3.4 arbitration）。
3. **每個 active interaction 有 watchdog**（吸收 6/9「stranger plan 卡死全系統」；複用 `SkillContract.timeout_s`，brain 側現未用）（§3.6）。
4. **pending confirm 不吃掉全部感知**——confirm 在飛時其他事件 queue 或 suppressed-with-trace，不黑洞（§3.5）。
5. **TTS ack（utterance_id + terminal event）最終取代 Bool 猜測**（§3.7，Phase 2d→2g）。
6. **demo_phase 未來是 operator scene mask**（latched topic、操作員工具發布、policy 表消費、每次變更是 trace 事件），不是硬編 flag（§3.8）。
7. **狀態草案（可被 trace 數據修正）**：IDLE / LISTENING / SPEAKING / CONFIRM_PENDING / EXECUTING / ALERT_ACTIVE / SAFETY_HOLD；轉移來源只有四種：skill_result 生命週期、confirm 結果、TTS ack、操作員指令（§3.1 / §3.2）。
8. **上線必須帶 `ism_enabled` flag + v1 fallback**；`test_brain_rules` 73 條 + 6/9 場景重演（ALERT 卡住 → cup/greet 被 queue/suppressed-with-trace 而非黑洞）是驗收網（§3.9 + Phase 3）。

> 使用者補充的 `RECOVERY` 狀態納入為 `ERROR_RECOVERY`（§3.1）——它正是 §7.3 watchdog 觸發後的歸宿，與 §7.7 的 7 狀態草案不衝突（草案明言「可被 trace 數據修正」）。

---

## 1. 為什麼要 ISM（問題陳述）

現行 Brain 是**隱式**事件機（見 §2 實證盤點）。症狀（使用者實際遇到）：

- 坐下沒講、拿杯子沒反應 → 候選被某個 gate 早退，但**沒有單一地方說明「為什麼此刻不該講」**（Plan E trace 已部分補上）。
- 手勢狂誤觸狂問 WeGo → gesture callback 直接驅動 confirm，無狀態約束。
- 人臉/物體/手勢互搶 TTS → **沒有單一 speaking chokepoint**，靠各 callback 各自查 `tts_playing` gate，race-prone。
- pending_confirm 一卡，其他功能變黑洞 → confirm 在飛時 object/greet/sit 被 `return` 掉、**無 trace、無 queue**（6/8 已部分加 trace，但仍是 drop）。
- stranger plan 卡死全系統（6/9 實機）→ **active_plan 無 watchdog**，skill 不回終態就永久占用。

根因不是單一 bug，是**沒有顯式狀態 + 沒有單一裁決點 + 沒有 watchdog**。ISM 解這三件事。

---

## 2. 現行隱式狀態機盤點（實證，遷移基準）

> 來源：`interaction_executive/interaction_executive/brain_node.py`（逐行查證）。這是遷移的 before-snapshot，Phase 1 shadow 比對的 legacy 基準。

### 2.1 散落的狀態載體
- `_state: BrainInternalState`（`brain_node.py:124-149`）：`active_plan`/`active_step`（lifecycle `_on_skill_result:1707/1731`）、`unknown_face_first_seen`、`fallen_first_seen`、`sitting_first_seen`、`last_sitting_seen_ts`、`last_alert_ts`（per-key cooldown dict `_mark_cooldown:563`）、`dedup_cache`、`chat_buffer`、`current_gesture`+`current_gesture_ts`、idle clock。
- `_pending_confirm: PendingConfirm`（`:163`，`pending_confirm.py`）：`IDLE|PENDING`、`_skill`/`_args`/`_started_at`/`_ok_stable_since`/`_must_release_ok`，timeout 30s、stable 0.5s。
- `_attention: AttentionMachine`（`:177`）：IDLE/NOTICED/ENGAGED/INTERACTING。
- `_world: WorldState`（`:159`）：`tts_playing`/obstacle/emergency/nav readiness（讀 `/state/tts_playing` 等）。
- runtime flags：`demo_phase`（`_PHASE_ALLOWED_KINDS:301`）、`gesture_enabled`、`stranger_alert_enabled`、`perception_router_enabled`（Plan D）、一堆 `demo_video_*`。

### 2.2 隱式「狀態」其實是這些 flag 的組合
| 概念狀態 | 現行判定（散落） |
|---|---|
| IDLE | `active_plan is None` ∧ `_pending_confirm.state==IDLE` ∧ `¬tts_playing` ∧ attention∈{IDLE,NOTICED} |
| LISTENING | `chat_buffer` 非空（speech_intent 進來等 chat_candidate，`_on_speech_intent:719`） |
| SPEAKING | `_world.snapshot().tts_playing`（Bool 猜測） |
| CONFIRM_PENDING | `_pending_confirm.state==PENDING` |
| EXECUTING | `active_plan≠None` ∧ `priority∈{SKILL,SEQUENCE}`（`_has_active_skill_or_sequence:631`） |
| ALERT_ACTIVE | `active_plan.priority==ALERT`（stranger/fallen） |
| SAFETY_HOLD | 無顯式狀態；`SafetyLayer.hard_rule` 每次重判（`_on_speech_intent:673`） |
| ERROR_RECOVERY | **不存在** → 這就是黑洞與卡死的來源 |

### 2.3 仲裁＝「誰先 emit 誰贏」（無顯式 arbiter）
- 單執行緒 executor，5 callback 串行；brain **不排序**，靠每 callback emit 前的 gate 早退避免互搶。
- 19 個 `_suppressed(...)` 點（`brain_node.py` 實證行號）：`demo_phase:319`、`dedup:611`、`llm_allowlist:795`、`capability_health:809`、`skill_cooldown:821/1201`、`gesture_enabled:936`、`pending_confirm:955/1541`、`active_plan:960/1536`、`conversation_gate:991`、`stranger_alert_enabled:1309`、`greet_gate:1350`、`greet_sitting_window:1362`、`greet_cooldown:1371`、`attention_engaged:1530`、`tts_playing:1545`、`object_remark_dedup:1594`。
- **問題**：這 19 個點是「分散的 if」，沒有單一表能回答「狀態 X 下事件 Y 該怎樣」。ISM 把它們收斂成一張 policy 表。

### 2.4 已有可複用基礎
- **Plan D**：`perception_router` 把 5 callback 解析統一成乾淨 dataclass（`PerceptionEvent`）→ ISM 的 candidate 來源。
- **Plan E**：`_current_decision_id`（每事件一個 UUID，`speech-/gesture-/face-/pose-/object-/chat-/skill_request-`）+ `/brain/trace` + `_suppressed`/`_trace_skill_result` → ISM 直接複用做「狀態轉移 trace」與 shadow 比對。
- **單執行緒 + `self._lock`**：`_suppressed` 內部取鎖 → ISM 的 `propose()` 必須**在鎖外**呼叫 trace（沿用 Plan E 紀律）。

---

## 3. 目標設計（PawAI Brain v2 互動流程規則）

### 3.1 狀態定義（8 態，對齊 §7.7 + 使用者 RECOVERY）

```python
class InteractionState(str, Enum):
    IDLE            = "idle"             # 無互動；接受任何候選
    LISTENING       = "listening"        # 正在聽語音（chat_buffer 在飛）
    SPEAKING        = "speaking"         # 正在播 TTS（社交候選讓路）
    CONFIRM_PENDING = "confirm_pending"  # 等 OK 二確；只認 OK/cancel/timeout
    EXECUTING       = "executing"        # 正在執行 skill/sequence（感知只記錄）
    ALERT_ACTIVE    = "alert_active"     # 高優先警示播報中（stranger/fallen）
    SAFETY_HOLD     = "safety_hold"      # 硬安全停止保持（stop/emergency/obstacle）
    ERROR_RECOVERY  = "error_recovery"   # watchdog/STEP_FAILED 後恢復 → 回 IDLE
```

> `SAFETY_HOLD`（硬停、保持機器人不動）與 `ALERT_ACTIVE`（高優先**播報**，如陌生人/跌倒）刻意分離：前者是 motion 安全鎖、後者是社交/守護播報。§7.2 鐵律下 `SAFETY_HOLD` 優先級最高。

### 3.2 轉移驅動只有四種（§7.7）+ 安全 override

**正常轉移驅動（四種）**：
1. **skill_result lifecycle**：`STARTED` → `EXECUTING`（或 `ALERT_ACTIVE`，依 plan.priority_class）；terminal（COMPLETED/ABORTED/BLOCKED_BY_SAFETY/STEP_FAILED）→ 回 `IDLE`。
2. **confirm 結果**：`CONFIRMED` → `EXECUTING`；`CANCELLED`/`timeout` → `IDLE`。
3. **TTS ack**：speaking 開始 → `SPEAKING`；結束 → 回前狀態。Phase 2d 先用現行 Bool `tts_playing`；Phase 2g 換 `utterance_id + terminal`（§7.5）。
4. **operator 指令**：`demo_phase` scene mask 變更（§3.8）、`/brain/reset_context`。

**安全 override（最高優先，可從任何狀態搶入）**：`SafetyLayer.hard_rule`（STOP 關鍵字）/ emergency / obstacle → `SAFETY_HOLD`；alert 候選被接受 → `ALERT_ACTIVE`（仍走 skill_result lifecycle 回歸）。

> **鐵律**：感知事件（face/object/gesture/pose）**不在這四種驅動內**——它們只產生 candidate（§3.3）。狀態只由「動作生命週期 / 確認 / 說話 / 操作員 / 安全」推動。

### 3.3 Source trust boundary（§7.1 + 安全 finding P2-1）

- 所有**感知事件 → `Candidate`**（候選 intent），永不直接進 `EXECUTING`。`Candidate.source` 是**諮詢性 metadata，不是授權**。
- 進入 `EXECUTING` 只有兩條合法路徑：① **explicit command**（受信任通道：語音 intent / studio 已認證按鈕 / 操作員）② **已解析的 CONFIRM_PENDING OK**。
- **移除 `_STUDIO_BUTTON_BYPASS_CONFIRM` 對 `source` 自稱的信任**（安全 ledger P2-1 / GAP1-01）：`requires_confirmation=True` 的 skill 一律走 `CONFIRM_PENDING`，不能靠 wire 欄位 `source==studio_button` 繞過。（gateway 端認證後簽章是 S0 post-freeze 的事，ISM 這層只負責「不信任自稱 source」。）

### 3.4 仲裁優先序（§7.2 鐵律）

```
P0 SAFETY_HOLD     （stop / emergency / obstacle）
P1 ALERT_ACTIVE    （stranger_alert / fallen_alert）
P2 explicit command（speech intent / gesture 直接指令 / studio 按鈕 / 操作員）
P3 confirm flow    （CONFIRM_PENDING 的 OK/cancel）
P4 自發社交 proposal（greet / object_remark / sit_along / careful_remind / idle）
```

**裁決規則**：candidate 帶 priority；只有當 `candidate.priority` 足以 pre-empt 當前 state 時才被接受，否則 `SUPPRESS`（帶 trace）或 `QUEUE`（短暫保留）。例：
- `EXECUTING` 中：只有 P0/P1/P2-stop 能 pre-empt；P4 社交一律 `SUPPRESS`（**發 trace 說明**，非黑洞）。
- `CONFIRM_PENDING` 中（§3.5）：P0/P1 pre-empt（取消 confirm + trace）；P2 explicit 取消 confirm 並處理；P3 OK→`EXECUTING`；P4 社交 `SUPPRESS-with-trace`。
- `SPEAKING` 中：P4 社交 `QUEUE`（短）或 `SUPPRESS`；P0/P1/P2 pre-empt。

### 3.5 CONFIRM_PENDING 非黑洞規則（§7.4）

confirm 在飛時，**每個進來的 candidate 都要有明確去向**（這是 6/8「pending 卡住其他全黑」的修正）：

| candidate 類 | CONFIRM_PENDING 下處置 |
|---|---|
| P0 safety | pre-empt：取消 confirm（trace `confirm_cancelled:safety`）→ `SAFETY_HOLD` |
| P1 alert | pre-empt：取消 confirm → `ALERT_ACTIVE` |
| P2 explicit（新語音/手勢指令）| 取消 confirm（trace `confirm_cancelled:superseded`）→ 處理新指令 |
| P3 OK gesture | `CONFIRMED` → `EXECUTING` |
| P3 cancel / timeout(30s) | → `IDLE`（trace `confirm_timeout`/`confirm_cancelled`） |
| P4 社交（greet/object/sit）| `SUPPRESS-with-trace`（reason `gate:confirm_pending`）——**永遠發 trace，永不靜默 drop** |

### 3.6 Watchdog（§7.3，殺 6/9 卡死）

- 每個 `EXECUTING`/`ALERT_ACTIVE`/`CONFIRM_PENDING` 進入時記 `deadline = now + timeout`。
- timeout 來源：`EXECUTING`/`ALERT_ACTIVE` 用該 plan 的 `SkillContract.timeout_s`（已存在於 contract，brain 側現未消費）；`CONFIRM_PENDING` 用既有 30s。
- 10Hz tick 檢查 deadline；逾時 → `ERROR_RECOVERY`（發 trace `watchdog_timeout:{state}:{plan_id}`）→ 清 active_plan/confirm → 回 `IDLE`。
- 額外 backstop：對齊 IE 的 `nav_step_timeout` 模式 + Plan B-E HITL 的 `goto_max_duration_s=120`。

### 3.7 SPEAKING / TTS 仲裁（§7.5）

- **單一 speaking chokepoint**：ISM 是唯一決定「現在能不能說」的地方；callback 不再各自查 `tts_playing`。
- Phase 2d：先用現行 `/state/tts_playing` Bool 當 SPEAKING enter/exit 訊號（行為等價現況）。
- Phase 2g（§7.5）：TTS service 發 `utterance_id` + terminal event（取代 Bool 猜測），ISM 用 ack 精準切 SPEAKING→prior，解決「Bool race 導致社交插嘴」。

### 3.8 demo_phase → operator scene mask（§7.6）

- 現行 `demo_phase` 是 hardcoded param + `_PHASE_ALLOWED_KINDS` 表（`brain_node.py:301`）。
- ISM 目標：`demo_phase` 是**操作員 scene mask**——latched topic（操作員工具發布）、ISM policy 表消費、**每次變更本身是一個 trace 事件**（operator command 驅動，§3.2.4）。
- 遷移：Phase 2a 先讓 ISM policy 消費現有 param（行為等價）；latched-topic 化是 Studio/operator-tool 的後續（不在本 plan 強制）。

### 3.9 Trace 整合（複用 Plan E）

- 新 `TraceKind.STATE_TRANSITION`（contracts，additive）：記 `from_state`/`to_state`/`trigger`/`decision_id`。
- 新 `TraceKind.CANDIDATE`（Plan E 已預留 enum 值 `candidate`）：記每個 candidate 的 `ACCEPT/SUPPRESS/QUEUE/PREEMPT` verdict + reason + 當前 state。
- 沿用 `_current_decision_id`：candidate→裁決→轉移→plan→skill_result 串同一條因果鏈。
- **shadow 模式**（Phase 1）：ISM 發 `verdict` 屬性標 `shadow=true`，與 legacy 並排，不影響行為。

### 3.10 demo 範例對映（使用者要的流程）

| 步驟 | 事件 | 當前 state | candidate | 裁決 | 轉移 |
|---|---|---|---|---|---|
| Roy 出現 | face known stable | IDLE | greet(P4) | ACCEPT | →SPEAKING→IDLE |
| Roy 坐下 | pose sitting | IDLE | sit_along(P4) | ACCEPT | →SPEAKING→IDLE |
| Roy 拿杯子 | object cup | IDLE | object_remark(P4) | ACCEPT | →SPEAKING→IDLE |
| 杯子又被偵測 | object cup | SPEAKING | object_remark(P4) | SUPPRESS(trace `gate:speaking`) | — |
| Roy 比讚 | gesture thumbs_up | IDLE | confirm_wiggle(P3 req) | ACCEPT | →CONFIRM_PENDING |
| confirm 在飛時拿杯子 | object cup | CONFIRM_PENDING | object_remark(P4) | SUPPRESS(trace `gate:confirm_pending`) | — |
| Roy 比 OK | gesture ok | CONFIRM_PENDING | confirm_ok(P3) | CONFIRMED | →EXECUTING |
| 執行中拿杯子 | object cup | EXECUTING | object_remark(P4) | SUPPRESS(trace `gate:executing`) | — |
| 跌倒 | pose fallen | EXECUTING | fallen_alert(P1) | PREEMPT | →ALERT_ACTIVE |

---

## 4. 檔案結構（遷移單元邊界）

| 檔案 | 角色 | 動作 |
|---|---|---|
| `interaction_executive/interaction_executive/interaction_state.py` | **新**。ROS-free 純核心：State/Priority/Verdict enum、`Candidate`/`TransitionSignal`/`Decision` dataclass、`InteractionPolicy`（純函式裁決 + 轉移）、`InteractionStateMachine`（持當前 state + deadline + history，`propose(candidate)→Decision`、`apply_signal(signal)`、`tick(now)→Decision\|None`） | Phase 0 Create |
| `interaction_executive/test/test_interaction_state.py` | **新**。純機器單測（狀態轉移、優先序、confirm 非黑洞、watchdog、source trust） | Phase 0 Create |
| `pawai_contracts/pawai_contracts/trace_schema.py` | 加 `TraceKind.STATE_TRANSITION`（additive，不改現有值） | Phase 1 Modify |
| `pawai_contracts/test/test_trace_schema.py` | 加 STATE_TRANSITION 測試 | Phase 1 Modify |
| `interaction_executive/interaction_executive/brain_node.py` | 接 ISM：Phase 1 shadow（觀測+trace，不改行為）；Phase 2 逐 family 切換（flag `ism_enabled`）；Phase 3 刪 legacy | Phase 1–3 Modify |
| `interaction_executive/test/test_ism_shadow_parity.py` | **新**。shadow 比對 + 6/9 場景重演（ALERT 卡住→cup/greet queued/suppressed-with-trace 非黑洞） | Phase 1 Create |
| `.github/workflows/ros_build.yaml` | fast-gate 加 ISM 純測 invocation（`PYTHONPATH=pawai_contracts:interaction_executive`） | Phase 0 Modify |

---

## 5. Phase 0：純 ISM 核心（無接線、零行為變更）— 可立即執行

> 紀律同 Plan C/D 抽取：純模組、逐字對照現行語義、完整單測、**brain_node 尚未 import**。

### Task 0.1：State / Priority / Verdict / 型別

**Files:** Create `interaction_executive/interaction_executive/interaction_state.py`

- [ ] **Step 1: 寫核心 enum 與 dataclass（先寫測試見 Task 0.2，這裡先放型別骨架）**

```python
"""Interaction State Machine — ROS-free core (Plan ISM, master plan §7).

感知事件只產生 Candidate，policy 對照當前 state 裁決；轉移只由四種驅動 +
safety override 推動（§3.2）。本模組無 rclpy / 無 I/O，可單測、可被 Studio 共用。"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class InteractionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"
    CONFIRM_PENDING = "confirm_pending"
    EXECUTING = "executing"
    ALERT_ACTIVE = "alert_active"
    SAFETY_HOLD = "safety_hold"
    ERROR_RECOVERY = "error_recovery"


class Priority(IntEnum):                 # 數字小 = 優先（§3.4）
    SAFETY = 0
    ALERT = 1
    EXPLICIT = 2
    CONFIRM = 3
    SOCIAL = 4


class Verdict(str, Enum):
    ACCEPT = "accept"        # 進狀態 / emit
    SUPPRESS = "suppress"    # 不做，發 trace 說明（非黑洞）
    QUEUE = "queue"          # 短暫保留（SPEAKING 中的社交）
    PREEMPT = "preempt"      # 搶占當前 active interaction


class TriggerKind(str, Enum):            # §3.2 四種驅動 + safety
    SKILL_RESULT = "skill_result"
    CONFIRM_RESULT = "confirm_result"
    TTS_ACK = "tts_ack"
    OPERATOR = "operator"
    SAFETY = "safety"


@dataclass(frozen=True)
class Candidate:
    """感知/語音/手勢產生的候選 intent。source 是諮詢性 metadata，非授權（§3.3）。"""
    kind: str                  # greet | object_remark | sit_along | gesture_cmd | chat | alert | stop ...
    priority: Priority
    source: str                # face | object | gesture | pose | speech | studio | operator
    skill: str = ""            # 要 emit 的 skill（若被 ACCEPT）
    args: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    decision_id: str = ""
    explicit: bool = False     # True = 受信任 explicit command（§3.3）


@dataclass(frozen=True)
class TransitionSignal:
    """非候選的狀態驅動（§3.2）：skill lifecycle / confirm 結果 / TTS ack / operator。"""
    trigger: TriggerKind
    detail: dict[str, Any] = field(default_factory=dict)
    decision_id: str = ""


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str                       # gate:executing / preempt:safety / accept ...
    next_state: InteractionState | None = None   # None = 不轉移
    emit_skill: str = ""
    emit_args: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_state.py
git commit -m "feat(ism): ROS-free core types — State/Priority/Verdict/Candidate/Signal/Decision (Plan ISM Phase 0)"
```

### Task 0.2：`InteractionPolicy` 純函式裁決（先測後寫）

**Files:** Modify `interaction_state.py`；Test `interaction_executive/test/test_interaction_state.py`

- [ ] **Step 1: 寫失敗測試（優先序鐵律 + 非黑洞）**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "interaction_executive"))
from interaction_state import (  # noqa: E402
    InteractionState as S, Priority as P, Verdict as V, Candidate, InteractionPolicy,
)

def _cand(kind, prio, **kw):
    return Candidate(kind=kind, priority=prio, source=kw.pop("source", "test"), **kw)

def test_social_suppressed_while_executing():
    d = InteractionPolicy.evaluate(S.EXECUTING, _cand("object_remark", P.SOCIAL))
    assert d.verdict == V.SUPPRESS and d.reason == "gate:executing"

def test_safety_preempts_executing():
    d = InteractionPolicy.evaluate(S.EXECUTING, _cand("stop", P.SAFETY))
    assert d.verdict == V.PREEMPT and d.next_state == S.SAFETY_HOLD

def test_confirm_pending_social_suppressed_not_blackhole():
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("greet", P.SOCIAL))
    assert d.verdict == V.SUPPRESS and d.reason == "gate:confirm_pending"

def test_confirm_pending_ok_confirms():
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("confirm_ok", P.CONFIRM))
    assert d.verdict == V.ACCEPT and d.next_state == S.EXECUTING

def test_explicit_command_supersedes_confirm():
    d = InteractionPolicy.evaluate(S.CONFIRM_PENDING, _cand("chat", P.EXPLICIT, explicit=True))
    assert d.verdict == V.PREEMPT  # 取消 confirm 處理新指令

def test_idle_accepts_social():
    d = InteractionPolicy.evaluate(S.IDLE, _cand("greet", P.SOCIAL, skill="greet_known_person"))
    assert d.verdict == V.ACCEPT and d.next_state == S.SPEAKING

def test_speaking_queues_social():
    d = InteractionPolicy.evaluate(S.SPEAKING, _cand("object_remark", P.SOCIAL))
    assert d.verdict in (V.QUEUE, V.SUPPRESS) and "speaking" in d.reason

def test_perception_never_enters_executing_directly():
    # 感知社交候選不得直接進 EXECUTING（§3.3 source trust）
    d = InteractionPolicy.evaluate(S.IDLE, _cand("object_remark", P.SOCIAL))
    assert d.next_state != S.EXECUTING
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONPATH=pawai_contracts:interaction_executive python3 -m pytest interaction_executive/test/test_interaction_state.py -v`
Expected: FAIL（`InteractionPolicy` 未定義）

- [ ] **Step 3: 寫 `InteractionPolicy.evaluate`（最小實作）**

```python
# interaction_state.py 末端新增
# 每個 state 允許「被誰 pre-empt / 接受誰」的表（§3.4）。
_PREEMPTIBLE_BY = {
    S.IDLE:            {P.SAFETY, P.ALERT, P.EXPLICIT, P.CONFIRM, P.SOCIAL},
    S.LISTENING:       {P.SAFETY, P.ALERT, P.EXPLICIT},
    S.SPEAKING:        {P.SAFETY, P.ALERT, P.EXPLICIT},
    S.CONFIRM_PENDING: {P.SAFETY, P.ALERT, P.EXPLICIT, P.CONFIRM},
    S.EXECUTING:       {P.SAFETY, P.ALERT},   # + explicit-stop 特例見下
    S.ALERT_ACTIVE:    {P.SAFETY},
    S.SAFETY_HOLD:     {P.SAFETY},            # 只有 safety-clear/operator 能離開
    S.ERROR_RECOVERY:  {P.SAFETY},
}
_PRIORITY_TARGET = {                         # 被接受時的目標狀態
    P.SAFETY: S.SAFETY_HOLD, P.ALERT: S.ALERT_ACTIVE,
}

class InteractionPolicy:
    @staticmethod
    def evaluate(state: "InteractionState", c: "Candidate") -> "Decision":
        allowed = _PREEMPTIBLE_BY[state]
        # P3 confirm：CONFIRM_PENDING 下 OK → EXECUTING
        if state is S.CONFIRM_PENDING and c.priority is P.CONFIRM:
            if c.kind == "confirm_ok":
                return Decision(V.ACCEPT, "confirm_ok", S.EXECUTING, c.skill, c.args)
            return Decision(V.ACCEPT, "confirm_cancel", S.IDLE)
        if c.priority not in allowed:
            verb = V.QUEUE if (state is S.SPEAKING and c.priority is P.SOCIAL) else V.SUPPRESS
            return Decision(verb, f"gate:{state.value}")
        # 被接受：safety/alert → 專屬狀態；explicit/social → 看是否需 confirm
        if c.priority in _PRIORITY_TARGET:
            return Decision(V.PREEMPT, f"preempt:{c.priority.name.lower()}",
                            _PRIORITY_TARGET[c.priority], c.skill, c.args)
        if c.requires_confirmation:
            return Decision(V.ACCEPT, "confirm_request", S.CONFIRM_PENDING, c.skill, c.args)
        # explicit command 取消 confirm（§3.5）
        if state is S.CONFIRM_PENDING and c.explicit:
            return Decision(V.PREEMPT, "confirm_superseded", S.EXECUTING if c.skill else S.LISTENING,
                            c.skill, c.args)
        target = S.EXECUTING if (c.explicit and c.skill) else S.SPEAKING
        return Decision(V.ACCEPT, "accept", target, c.skill, c.args)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `PYTHONPATH=pawai_contracts:interaction_executive python3 -m pytest interaction_executive/test/test_interaction_state.py -v`
Expected: PASS（8/8）

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_state.py interaction_executive/test/test_interaction_state.py
git commit -m "feat(ism): InteractionPolicy.evaluate — 優先序鐵律 + 非黑洞裁決 (Plan ISM Phase 0)"
```

### Task 0.3：`InteractionStateMachine` 類別 + watchdog tick（先測後寫）

**Files:** Modify `interaction_state.py` + `test_interaction_state.py`

- [ ] **Step 1: 寫失敗測試（轉移、watchdog、confirm timeout）**

```python
from interaction_state import InteractionStateMachine, TransitionSignal, TriggerKind as T

def test_skill_started_enters_executing():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "priority_class": 4,
                                                     "plan_id": "p1", "timeout_s": 10.0}))
    assert m.state == InteractionState.EXECUTING

def test_skill_terminal_returns_idle():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1", "timeout_s": 10.0}))
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "COMPLETED", "plan_id": "p1"}))
    assert m.state == InteractionState.IDLE

def test_watchdog_timeout_to_recovery():
    m = InteractionStateMachine(now=0.0)
    m.apply_signal(TransitionSignal(T.SKILL_RESULT, {"status": "STARTED", "plan_id": "p1", "timeout_s": 5.0}))
    d = m.tick(now=6.0)            # 逾時
    assert m.state == InteractionState.IDLE  # ERROR_RECOVERY → IDLE
    assert d is not None and "watchdog_timeout" in d.reason

def test_confirm_timeout_30s():
    m = InteractionStateMachine(now=0.0, state=InteractionState.CONFIRM_PENDING, deadline=30.0)
    m.tick(now=31.0)
    assert m.state == InteractionState.IDLE
```

- [ ] **Step 2: 跑測試確認失敗** — Run 同上；Expected: FAIL

- [ ] **Step 3: 寫 `InteractionStateMachine`（最小實作）**

```python
_TERMINAL = {"COMPLETED", "ABORTED", "BLOCKED_BY_SAFETY", "STEP_FAILED"}

class InteractionStateMachine:
    def __init__(self, now: float, state: "InteractionState" = InteractionState.IDLE,
                 deadline: float | None = None):
        self.state = state
        self._deadline = deadline
        self._active_plan_id = ""
        self.history: list[tuple[float, str, str, str]] = []  # (ts, from, to, trigger)

    def propose(self, c: "Candidate", now: float) -> "Decision":
        d = InteractionPolicy.evaluate(self.state, c)
        if d.next_state and d.verdict in (Verdict.ACCEPT, Verdict.PREEMPT):
            self._transition(self.state, d.next_state, f"candidate:{c.kind}", now,
                             deadline=now + 30.0 if d.next_state is InteractionState.CONFIRM_PENDING else None)
        return d

    def apply_signal(self, sig: "TransitionSignal", now: float = 0.0) -> None:
        if sig.trigger is TriggerKind.SKILL_RESULT:
            status = sig.detail.get("status", "")
            if status == "STARTED":
                prio = int(sig.detail.get("priority_class", int(Priority.SOCIAL)))
                nxt = InteractionState.ALERT_ACTIVE if prio == int(Priority.ALERT) else InteractionState.EXECUTING
                self._active_plan_id = sig.detail.get("plan_id", "")
                t = float(sig.detail.get("timeout_s", 0) or 0)
                self._transition(self.state, nxt, "skill_started", now,
                                 deadline=(now + t) if t > 0 else None)
            elif status in _TERMINAL and sig.detail.get("plan_id", "") == self._active_plan_id:
                self._active_plan_id = ""
                self._transition(self.state, InteractionState.IDLE, f"skill_{status.lower()}", now)
        elif sig.trigger is TriggerKind.TTS_ACK:
            if sig.detail.get("event") == "start":
                self._transition(self.state, InteractionState.SPEAKING, "tts_start", now)
            elif self.state is InteractionState.SPEAKING:
                self._transition(self.state, InteractionState.IDLE, "tts_end", now)
        elif sig.trigger is TriggerKind.OPERATOR and sig.detail.get("op") == "reset":
            self._active_plan_id = ""
            self._transition(self.state, InteractionState.IDLE, "operator_reset", now)

    def tick(self, now: float) -> "Decision | None":
        if self._deadline is not None and now >= self._deadline:
            stuck = self.state
            self._active_plan_id = ""
            self._transition(stuck, InteractionState.IDLE, "watchdog", now)
            return Decision(Verdict.PREEMPT, f"watchdog_timeout:{stuck.value}",
                            InteractionState.IDLE)
        return None

    def _transition(self, frm, to, trigger, now, deadline=None):
        self.state = to
        self._deadline = deadline
        self.history.append((now, frm.value, to.value, trigger))
        if len(self.history) > 64:
            self.history = self.history[-64:]
```

- [ ] **Step 4: 跑測試確認通過** — Expected: PASS（12/12 累計）

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_state.py interaction_executive/test/test_interaction_state.py
git commit -m "feat(ism): InteractionStateMachine + watchdog tick (Plan ISM Phase 0)"
```

### Task 0.4：fast-gate 接 ISM 純測

**Files:** Modify `.github/workflows/ros_build.yaml`

- [ ] **Step 1: 加 Invocation 9（ISM 純測）**

於 fast-gate「Pure Python unit tests」step 末端、`pawai-studio/gateway` invocation 後加：

```yaml
          # Invocation 9 (Plan ISM Phase 0): interaction_state pure machine.
          PYTHONPATH=pawai_contracts:interaction_executive pytest \
            interaction_executive/test/test_interaction_state.py -v --tb=short
```

- [ ] **Step 2: 本機驗證等價指令通過** — Run 同 Task 0.2 Step 4；Expected: PASS

- [ ] **Step 3: Commit + 推 PR（Phase 0 = 一個 PR）**

```bash
git add .github/workflows/ros_build.yaml
git commit -m "ci(ism): fast-gate runs interaction_state pure tests (Plan ISM Phase 0)"
```

> **Phase 0 PR 驗收**：純模組 + 完整單測綠、`brain_node` 零改動、現有 73 條 `test_brain_rules` + 612 測試零影響。

---

## 6. Phase 1：Shadow 模式（觀測 + 比對 trace，零行為變更）— 可立即執行

> 目標：brain_node **實例化 ISM、餵真實事件、發 STATE_TRANSITION/CANDIDATE shadow trace**，但**不依其裁決行動**。收集真實節奏數據驗證 ISM 與 legacy 一致/更好（§7.7「狀態草案可被 trace 數據修正」）。

### Task 1.1：contracts 加 `TraceKind.STATE_TRANSITION`（additive）

**Files:** Modify `pawai_contracts/pawai_contracts/trace_schema.py` + test

- [ ] **Step 1: 寫測試**：`TraceKind.STATE_TRANSITION.value == "state_transition"`；確認既有值不變（CANDIDATE 已存在）。
- [ ] **Step 2: 加 enum 值**（不改現有）：`STATE_TRANSITION = "state_transition"`。
- [ ] **Step 3: 測試通過 + commit**。

### Task 1.2：brain_node shadow 接線（flag `ism_shadow_enabled`，預設 False）

**Files:** Modify `brain_node.py`；Test `interaction_executive/test/test_ism_shadow_parity.py`

- [ ] **Step 1: 寫 shadow 比對測試**（用合成事件序列，斷言 shadow 開啟時：① 不改 emit 行為 ② 每事件發一條 shadow trace ③ ISM 裁決與 legacy 早退理由可對映）。
- [ ] **Step 2: 接線**：`__init__` 建 `self._ism = InteractionStateMachine(now)`；param `ism_shadow_enabled`（declare 預設 False）；在 5 callback 入口（已有 `_current_decision_id`）把事件轉成 `Candidate`、呼叫 `self._ism.propose(cand, now)`（在 `self._lock` 外）、發 `STATE_TRANSITION`/`CANDIDATE` trace（標 `shadow=true`）；**ISM 的 Decision 不影響任何 emit/return**。skill_result/tts/reset 也餵 `apply_signal`。
- [ ] **Step 3: 測試通過**（shadow on/off 下 legacy emit byte-identical）。
- [ ] **Step 4: Commit。**

### Task 1.3：6/9 場景重演測試（黑洞回歸網，§7.8）

**Files:** `test_ism_shadow_parity.py`

- [ ] **Step 1: 寫場景**：模擬「ALERT/EXECUTING 卡住時，cup/greet 進來」→ 斷言 **ISM 裁決為 `SUPPRESS-with-trace`（reason `gate:executing`/`gate:alert_active`），非靜默 drop**；watchdog 逾時 → `ERROR_RECOVERY`→IDLE。
- [ ] **Step 2: 跑通 + commit。**

> **Phase 1 PR 驗收**：`ism_shadow_enabled=False`（預設）時 612+73 測試零變動全綠；`=True` 時多發 shadow trace、emit 行為不變；真機 Jetson 開 shadow 跑一輪 demo，`ros2 topic echo /brain/trace | grep state_transition` 看 ISM 跟著真實事件走的狀態軌跡（這就是「被 trace 數據修正設計」的數據源）。

---

## 7. Phase 2：逐 gate family flag-gated 切換（`ism_enabled`，預設 False）— 設計鎖定，shadow 數據後展開

> **不要在 Phase 1 shadow 數據落地前展開以下逐行 TDD。** 每個 sub-phase = 一個獨立 PR，帶 `ism_enabled` 子開關、legacy fallback、red-green、真機驗證。順序由「風險低→高」排，每步都可單獨 rollback。

| Sub-phase | 切換的 family | 取代的 legacy | 新行為（ISM 權威） | 驗收 |
|---|---|---|---|---|
| **2a** | demo_phase scene mask | `_PHASE_ALLOWED_KINDS`/`_phase_allows` | ISM policy 消費 demo_phase（先 param，行為等價） | 73 條 brain_rules 綠 + demo_phase 切換 trace |
| **2b** | CONFIRM_PENDING + 非黑洞 + watchdog | `_pending_confirm` + 各 callback 的 `pending_confirm` 早退 | confirm 在飛時 candidate 全走 §3.5 表（queue/suppress-with-trace），30s watchdog | 6/9 重演：confirm 卡住 cup/greet 有 trace 非黑洞 |
| **2c** | EXECUTING + watchdog | `active_plan`/`_has_active_skill_or_sequence` | skill_result lifecycle 驅動 EXECUTING；`SkillContract.timeout_s` watchdog | 6/9 重演：stranger plan 不回終態 → watchdog→IDLE 不卡死 |
| **2d** | SPEAKING（Bool tts） | 各 callback 散落的 `tts_playing` gate | 單一 chokepoint：ISM 是唯一「能不能說」裁決點 | 社交不在 SPEAKING 插嘴；trace 證明 |
| **2e** | ALERT_ACTIVE / SAFETY_HOLD 優先序 | stranger/fallen 各自 gate + SafetyLayer 重判 | §3.4 鐵律 arbiter：safety/alert pre-empt | fallen 在 EXECUTING 中能 pre-empt；stop 最高 |
| **2f** | 自發社交 candidate 化 | greet/object/sit/careful/idle 各自 emit | 全變 P4 candidate 經 ISM 裁決 | greet/object/sit 時序正確（§3.10 表） |
| **2g** | TTS ack（utterance_id） | Bool `tts_playing` 猜測 | TTS service 發 utterance_id+terminal，ISM 精準切 SPEAKING（§7.5） | 需 speech 模組配合（跨模組，最後做） |

每 sub-phase 的 TDD 任務在該 PR 動工時依 Phase 0 的型別 + Phase 1 的 shadow 數據展開（屆時把 legacy 早退逐一替換成「呼叫 `self._ism.propose()` 並依 Decision 行動」，舊 gate 行為由 ISM policy 表保證等價，差異由 shadow trace 事先抓出）。

---

## 8. Phase 3：ISM 權威化 + 刪 legacy

- [ ] **3.1** 全 sub-phase 綠後，`ism_enabled` 預設翻 True；保留 env/param 可一鍵 fallback v1。
- [ ] **3.2** 跑完整驗收網：`test_brain_rules` 73 條 + Phase 1/2 全測 + 6/9 場景重演 + 真機 Jetson demo 一輪（§7.8）。
- [ ] **3.3** 刪 legacy gate 死碼（19 個分散 `_suppressed` 早退收斂進 ISM policy 後，移除重複判斷），`refactor-cleaner` 掃 dead code。
- [ ] **3.4** 更新 `docs/contracts/interaction_contract.md`（STATE_TRANSITION trace）+ `docs/pawai-brain/architecture/0511/brain/brain.md`（ISM 取代隱式機）。

---

## 9. 風險與 rollback

- **每階段 flag-gated**：`ism_shadow_enabled`（Phase 1）/`ism_enabled`（Phase 2-3）預設關，v1 永遠是 fallback（§7.8）。
- **shadow 先行**：Phase 1 不改行為，純收數據；任何「ISM 與 legacy 不一致」在 shadow trace 先暴露，才進 Phase 2。
- **逐 family 切換**：Phase 2 一次只動一個 gate family，單獨 PR + rollback；不一次炸 Brain。
- **驗收網**：73 條 brain_rules + 6/9 黑洞重演 + 真機，每 PR 都跑。
- **跨模組依賴**：2g（TTS ack）需 speech 模組配合，排最後、可獨立延後。
- **demo 凍結**：本 plan 全程 `ism_enabled` 預設關 → 對 6/18 demo 零影響；Phase 2/3 翻 default 在 demo 凍結解除後。

---

## 10. Self-Review（對照使用者 11 問 + master plan §7）

| 使用者要回答的 | 本 plan 位置 |
|---|---|
| 有哪些狀態？ | §3.1（8 態） |
| 每個狀態允許哪些事件？ | §3.4 `_PREEMPTIBLE_BY` 表 + §5 Task 0.2 |
| 哪些事件被 suppressed？ | §3.4 / §3.5（confirm 非黑洞表） |
| 誰可以打斷誰？ | §3.4 優先序鐵律 P0-P4 |
| TTS 正在講話時怎麼辦？ | §3.7（SPEAKING chokepoint + queue/suppress） |
| 手勢確認流程怎麼走？ | §3.5（CONFIRM_PENDING 表）+ Task 0.3 |
| 物體提醒什麼時候能講？ | §3.10 demo 表（IDLE accept / 其他 suppress-with-trace） |
| 人臉問候什麼時候能講？ | §3.10 + §2.2 greet gate 對映 |
| timeout / cooldown 怎麼算？ | §3.6 watchdog（plan.timeout_s / confirm 30s）+ cooldown 留在 candidate 產生端 |
| trace 要怎麼記？ | §3.9（STATE_TRANSITION/CANDIDATE，複用 decision_id） |
| 怎麼一步步改不炸？ | §5-§8（Phase 0 純模組→1 shadow→2 逐 family→3 權威化），全程 flag + fallback |

§7 八條約束逐條對映見 §0。**Placeholder 掃描**：Phase 0-1 為完整 TDD 含真實 code；Phase 2-3 為**刻意延後的設計鎖定遷移序列**（§7.8 + §7.7「待 shadow 數據修正」），非懶散佔位——每 sub-phase 有明確 family/取代對象/驗收。**型別一致性**：`Candidate`/`Decision`/`InteractionState`/`Priority`/`Verdict` 跨 §3/§5 命名一致。

---

## Execution Handoff

Plan 已存到 `docs/superpowers/plans/2026-06-11-plan-ism-interaction-state-machine.md`。

**這份是「施工圖」**：Phase 0–1（純模組 + shadow）是可立即逐 task 執行的完整 TDD；Phase 2–3 是設計鎖定的遷移序列，待 Phase 1 shadow 數據落地後再展開逐行任務（master plan §7.8）。

兩種執行方式（Phase 0-1）：
1. **Subagent-Driven（建議）** — 每 task 一個 fresh subagent，spec + 品質兩段 review。
2. **Inline** — 本 session 用 executing-plans 批次執行。

**等 Roy 指示再動工。** 本 plan 現在只是設計交付，未開始實作（§8 master plan「Brain ISM 詳細實作等 D+E」已滿足，現在 D+E 已 merge）。
