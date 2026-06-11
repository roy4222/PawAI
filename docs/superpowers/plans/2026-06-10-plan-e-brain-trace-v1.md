# Plan E: Brain Trace v1（schema + 發射）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 回答「PawAI 為什麼沒反應」——每個 gate 早退都發 `suppressed` trace（含 gate 名 / reason / demo_phase / active_plan / pending_confirm / cooldown 剩餘 / 來源事件摘要），新 topic `/brain/trace` 用 `decision_id` 把 sensor event → 裁決 → plan → skill_result 串成一條因果鏈。

**Architecture:** Roy 拍板邊界（Master Plan D5）：**schema 屬 pawai_contracts、發射屬
Brain/IE、落盤與呈現屬 Studio（後續 plan）**。本 plan = schema + 發射 + gateway 的
一行 TOPIC_MAP 橋接（live 可見，**不落盤**——落盤/export/panel 是 Studio Evidence
Center plan 的事，不准在這裡寫第二套）。**Additive-only**：不改 gating、不改 plan
選擇、不改 TTS、不改 cooldown——只多發 trace；606 測試零修改全綠是驗收底線。

**Tech Stack:** dataclass schema（contracts）、ROS String JSON topic、pytest。

---

## Scope

- Create: `pawai_contracts/pawai_contracts/trace_schema.py` + `pawai_contracts/test/test_trace_schema.py`
- Modify: `interaction_executive/interaction_executive/brain_node.py`（TraceEmitter + 各 gate 插樁）
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py`（blocked_by_safety 鏡像 trace）
- Modify: `pawai-studio/gateway/studio_gateway.py`（TOPIC_MAP 一行）
- Modify: `docs/contracts/interaction_contract.md`（新 topic 條目——ghost-topic checker 會擋沒登記的新 topic，**必須同 PR**）
- Test: `interaction_executive/test/test_trace_emission.py`（rclpy 本機層）

## Forbidden scope（Roy 拍板原文 + 邊界）

- **不改 gating / plan 選擇 / TTS / cooldown——只多發 trace**
- 不做落盤、不做 export、不做 panel（Studio plan 的地盤；「不再發明第三套 trace」）
- 不動 tts_node（TTS ack 是 Brain v2 Phase 3，另案）
- `_trace()` 永不拋例外影響 callback（publish 包 try/except log）
- 不動既有 `/brain/conversation_trace`（LLM 對話 trace 照舊；新 topic 是決策鏈 trace，
  兩者用途不同，遷移整併屬 ISM 之後）

## 執行前提

Plan C merged（contracts 在）；Plan D merged 較佳（router 的 event_id 可直接當
decision_id 源頭）但**不阻塞**——D 未合時 decision_id 在 callback 入口生成即可。
單一 PR。

---

### Task E1: trace schema（pawai_contracts）

**Files:**
- Create: `pawai_contracts/pawai_contracts/trace_schema.py`
- Test: `pawai_contracts/test/test_trace_schema.py`

- [x] **Step 1: failing tests**

```python
# pawai_contracts/test/test_trace_schema.py
import json

from pawai_contracts.trace_schema import TraceEvent, TraceKind, Verdict, make_suppressed


def test_round_trip_json():
    ev = TraceEvent(decision_id="d1", node="brain_node", kind=TraceKind.POLICY_DECISION,
                    verdict=Verdict.SUPPRESSED, gate="demo_phase", reason="phase:s3_object")
    d = json.loads(ev.to_json())
    assert d["decision_id"] == "d1" and d["verdict"] == "suppressed" and d["ts"] > 0


def test_make_suppressed_carries_roy_required_fields():
    ev = make_suppressed(
        decision_id="d2", node="brain_node", gate="gesture_enabled",
        reason="gesture_enabled=false", demo_phase="all",
        active_plan="stranger_alert", pending_confirm="PENDING:wiggle",
        cooldown_remaining_s=12.5, source_summary="gesture=thumbs_up conf=0.95",
    )
    d = json.loads(ev.to_json())
    for key in ("gate", "reason", "demo_phase", "active_plan", "pending_confirm",
                "cooldown_remaining_s", "source_summary"):
        assert key in d["detail"], key


def test_verdict_and_kind_enums_frozen():
    assert {v.value for v in Verdict} == {"accepted", "suppressed", "blocked"}
    assert {k.value for k in TraceKind} == {
        "perception_event", "candidate", "policy_decision",
        "plan_emitted", "skill_result", "tts_state",
    }
```

- [x] **Step 2: 實作 `trace_schema.py`**

```python
"""/brain/trace event schema — single source (Plan E, Roy ruling 2026-06-10 D5):
'Trace 的單一真相是 pawai_contracts schema + gateway JSONL。Brain 只負責說明自己
為什麼做/不做；Studio 只負責記錄與呈現；CLI 只負責讀取與匯出。'

decision_id chains one causal line: perception event → gate verdicts → plan →
skill_result. Emission: brain_node / interaction_executive (this plan);
conversation_graph joins later. Persistence: Studio gateway (separate plan).
ADDITIVE-ONLY: schema changes must stay backward-compatible (add fields, never
rename/remove)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TraceKind(str, Enum):
    PERCEPTION_EVENT = "perception_event"
    CANDIDATE = "candidate"
    POLICY_DECISION = "policy_decision"
    PLAN_EMITTED = "plan_emitted"
    SKILL_RESULT = "skill_result"
    TTS_STATE = "tts_state"


class Verdict(str, Enum):
    ACCEPTED = "accepted"
    SUPPRESSED = "suppressed"
    BLOCKED = "blocked"


@dataclass
class TraceEvent:
    decision_id: str
    node: str                      # brain_node | interaction_executive | conversation_graph
    kind: TraceKind
    verdict: Verdict
    gate: str = ""                 # e.g. demo_phase / gesture_enabled / active_plan / tts_playing
    reason: str = ""               # e.g. phase:s3_object / cooldown:greet:Roy / banned_api:1301
    detail: dict[str, Any] = field(default_factory=dict)
    plan_id: str = ""
    ts: float = field(default_factory=time.time)
    v: int = 1

    def to_json(self) -> str:
        d = {
            "v": self.v, "ts": self.ts, "decision_id": self.decision_id,
            "node": self.node, "kind": self.kind.value, "verdict": self.verdict.value,
            "gate": self.gate, "reason": self.reason, "detail": self.detail,
        }
        if self.plan_id:
            d["plan_id"] = self.plan_id
        return json.dumps(d, ensure_ascii=False)


def make_suppressed(*, decision_id: str, node: str, gate: str, reason: str,
                    demo_phase: str = "", active_plan: str = "",
                    pending_confirm: str = "", cooldown_remaining_s: float | None = None,
                    source_summary: str = "") -> TraceEvent:
    """Roy-required suppressed payload: 被哪個 gate 擋 / 當時 demo_phase /
    active_plan 是誰 / pending_confirm 是誰 / cooldown 還剩多久 / 來源摘要."""
    return TraceEvent(
        decision_id=decision_id, node=node, kind=TraceKind.POLICY_DECISION,
        verdict=Verdict.SUPPRESSED, gate=gate, reason=reason,
        detail={
            "gate": gate, "reason": reason, "demo_phase": demo_phase,
            "active_plan": active_plan, "pending_confirm": pending_confirm,
            "cooldown_remaining_s": cooldown_remaining_s,
            "source_summary": source_summary,
        },
    )
```

- [x] **Step 3: 跑綠 + commit**

```bash
PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q
git add pawai_contracts/ && git commit -m "feat(contracts): /brain/trace schema v1 — decision_id chain + suppressed payload (Plan E1)"
```

---

### Task E2: brain_node TraceEmitter + decision_id 流

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py`

- [x] **Step 1: publisher + helper（`__init__` publisher 區 + `_emit_trace` 旁）**

```python
        # Plan E (2026-06-10): decision-chain trace. Distinct from
        # /brain/conversation_trace (LLM dialogue stages) — this one answers
        # 「為什麼沒反應」. Persistence belongs to the Studio gateway, NOT here.
        self._pub_trace = self.create_publisher(String, "/brain/trace", _RELIABLE_10)
        self._plan_decision: dict[str, str] = {}   # plan_id → decision_id (GC'd in _gc_dedup)
```

```python
    def _trace(self, ev) -> None:
        """Publish a TraceEvent. NEVER raises — tracing must not break callbacks."""
        try:
            msg = String()
            msg.data = ev.to_json()
            self._pub_trace.publish(msg)
        except Exception as exc:  # noqa: BLE001 — additive instrumentation only
            self.get_logger().debug(f"trace publish failed: {exc}")

    def _suppressed(self, *, decision_id: str, gate: str, reason: str,
                    source_summary: str = "", cooldown_remaining_s: float | None = None) -> None:
        from pawai_contracts.trace_schema import make_suppressed
        with self._lock:
            active = self._state.active_plan or {}
        self._trace(make_suppressed(
            decision_id=decision_id, node="brain_node", gate=gate, reason=reason,
            demo_phase=self.demo_phase,
            active_plan=str(active.get("selected_skill") or ""),
            pending_confirm=f"{self._pending_confirm.state.name}:"
                            f"{getattr(self._pending_confirm, 'skill', '') or ''}",
            cooldown_remaining_s=cooldown_remaining_s,
            source_summary=source_summary,
        ))

    def _cooldown_remaining(self, key: str, cooldown_s: float) -> float:
        last = self._state.last_alert_ts.get(key)
        if last is None:
            return 0.0
        return max(0.0, cooldown_s - (time.time() - last))
```

- [x] **Step 2: decision_id 源頭**——五個 callback 入口（D 已合：`ev.event_id`；
D 未合：`decision_id = f"{kind}-{uuid.uuid4().hex[:12]}"`）。`_emit` 簽名不改，
但 `_plan_to_dict` **additive** 加欄位（IE `_on_proposal` 容忍未知欄位）：

```python
            "decision_id": getattr(plan, "decision_id", "") or
                           self._current_decision_id,   # set at callback entry
```
實作上最小侵入：callback 入口 `self._current_decision_id = decision_id`（單執行緒
executor，callback 內串行安全）；`_emit` 裡記 `self._plan_decision[plan.plan_id] =
self._current_decision_id` 並發 `plan_emitted` trace：

```python
        from pawai_contracts.trace_schema import TraceEvent, TraceKind, Verdict
        self._trace(TraceEvent(
            decision_id=self._current_decision_id, node="brain_node",
            kind=TraceKind.PLAN_EMITTED, verdict=Verdict.ACCEPTED,
            gate="", reason=plan.reason, plan_id=plan.plan_id,
            detail={"skill": plan.selected_skill, "source": plan.source,
                    "priority": int(plan.priority_class)},
        ))
```
`_on_skill_result` 加（terminal 與 blocked 路徑）：

```python
        decision_id = self._plan_decision.get(plan_id, "")
        self._trace(TraceEvent(
            decision_id=decision_id, node="brain_node", kind=TraceKind.SKILL_RESULT,
            verdict=Verdict.BLOCKED if status == "blocked_by_safety" else Verdict.ACCEPTED,
            gate="safety" if status == "blocked_by_safety" else "",
            reason=str(payload.get("reason") or status), plan_id=plan_id,
            detail={"status": status},
        ))
```
`_gc_dedup` 順手修剪 `self._plan_decision`（len > 200 時清最舊——dict 按插入序）。

- [x] **Step 3: commit**：`feat(brain): /brain/trace emitter + decision_id chain (Plan E2)`

---

### Task E3: 插樁——每個 suppression 點發 trace

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py`（下表每一點）
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py`（safety 鏡像）

插樁對照表（gate 名固定字串 = Studio 之後的 filter 鍵；行號為 baseline 參考）：

| 位置（baseline 行號） | gate | reason 格式 |
|---|---|---|
| `_phase_allows` return False（:306-316，改為帶 decision_id 的呼叫點插樁） | `demo_phase` | `phase:{self.demo_phase}:{kind}` |
| `_on_gesture` gesture_enabled early-return | `gesture_enabled` | `gesture_enabled=false` |
| `_on_gesture` confirm-in-flight / active-skill / 1s dedup / 30s conversation gate / tts_playing 各 return | `pending_confirm` / `active_plan` / `dedup` / `conversation_gate` / `tts_playing` | 各自常數字串 + 數值（dedup 帶 window、conversation gate 帶剩餘秒） |
| `_on_face` greet 路徑各 early-return（:1225-1252：not stable / sitting window 未滿 / greet cooldown） | `face_stable` / `greet_sitting_window` / `greet_cooldown` | cooldown 用 `self._cooldown_remaining(f"greet:{identity}", self.greet_cooldown_s)` |
| `_on_face` stranger 分支 stranger_alert_enabled=false 跳過 | `stranger_alert_enabled` | `stranger_alert_enabled=false` |
| `_on_object` 五 gate（:1374-1388：phase / ENGAGED / active-skill / pending-confirm / tts_playing）+ 60s dedup（:1431-1435） | `demo_phase` / `attention_engaged` / `active_plan` / `pending_confirm` / `tts_playing` / `object_remark_dedup` | dedup 帶剩餘秒（`OBJECT_REMARK_DEDUP_S - (now - seen_ts)`） |
| `_on_chat_candidate` re-gate（allowlist / capability health / cooldown，:703-779） | `llm_allowlist` / `capability_health` / `skill_cooldown` | `skill:{name}` + health block 字串 |
| `emit_with_cooldown` blocked（:1110-1115） | `skill_cooldown` | `cooldown:{skill}:{remaining:.1f}s` |
| `_check_dedup` 命中的呼叫點（speech/gesture/face/pose/object 各處） | `dedup` | `dedup:{source}:{key}` |
| IE `interaction_executive_node` SafetyLayer block（發 blocked_by_safety 處） | `safety` | 沿用既有 reason（如 `banned_api:1301`），verdict=BLOCKED，node="interaction_executive" |

- [x] **Step 1: 按表逐點插入 `self._suppressed(...)`**——每點一行呼叫，**不改動
return 行為本身**；`source_summary` 用該 callback 的關鍵欄位
（如 `f"gesture={gesture} conf={conf}"`、`f"class={class_name}"`、`f"identity={identity}"`）。

- [x] **Step 2: IE 鏡像**——IE node 加同款 `_pub_trace` publisher + 在 blocked_by_safety
publish 處同步發 TraceEvent（decision_id 從 proposal payload 的 `decision_id` 欄位讀，
缺省空字串——Plan E2 已 additive 加入）。

- [x] **Step 3: 行為不變驗證**

```bash
python3 -m pytest interaction_executive/test/ -q   # 258 passed — 零修改
```

- [x] **Step 4: commit**：`feat(brain): suppressed-trace instrumentation at every gate early-return (Plan E3)`

---

### Task E4: 新 trace 測試（本機 rclpy 層）

**Files:**
- Create: `interaction_executive/test/test_trace_emission.py`

- [x] **Step 1: 三條代表性斷言（capture `_pub_trace.publish`）**

```python
"""Trace emission tests (Plan E4) — rclpy local tier.
Pattern: capture /brain/trace publishes, fire one suppression scenario, assert
gate/reason/decision-chain fields. Behavior itself is asserted unchanged by the
untouched 258-test suite."""
import json

import pytest
import rclpy
from std_msgs.msg import String

from interaction_executive.brain_node import BrainNode


@pytest.fixture(scope="module", autouse=True)
def rclpy_ctx():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


@pytest.fixture
def node():
    n = BrainNode()
    n.traces = []
    n._pub_trace.publish = lambda m: n.traces.append(json.loads(m.data))  # type: ignore
    yield n
    n.destroy_node()


def _msg(payload: dict) -> String:
    m = String(); m.data = json.dumps(payload, ensure_ascii=False); return m


def test_gesture_disabled_emits_suppressed(node):
    node.gesture_enabled = False
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    hits = [t for t in node.traces if t["gate"] == "gesture_enabled"]
    assert hits and hits[0]["verdict"] == "suppressed"
    assert hits[0]["detail"]["demo_phase"] == node.demo_phase


def test_phase_gate_emits_suppressed_with_phase(node):
    node.demo_phase = "s3_object"
    node.gesture_enabled = True
    node._on_gesture(_msg({"gesture": "wave", "confidence": 0.9}))
    hits = [t for t in node.traces if t["gate"] == "demo_phase"]
    assert hits and "s3_object" in hits[0]["reason"]


def test_plan_emitted_and_skill_result_share_decision_id(node):
    node._on_speech_intent(_msg({"transcript": "停", "session_id": "t1"}))
    emitted = [t for t in node.traces if t["kind"] == "plan_emitted"]
    assert emitted, "stop keyword should emit a plan"
    plan_id, decision_id = emitted[0]["plan_id"], emitted[0]["decision_id"]
    node._on_skill_result(_msg({"plan_id": plan_id, "status": "completed"}))
    results = [t for t in node.traces if t["kind"] == "skill_result"]
    assert results and results[0]["decision_id"] == decision_id
```
（若「停」走 SafetyLayer 直發路徑的 plan reason 與假設不符，依實際行為調整觸發
fixture——用任何必發 plan 的輸入即可，斷言重點是 decision_id 串鏈。）

- [x] **Step 2: 跑綠 + commit**：`test(brain): trace emission + decision-chain assertions (Plan E4)`

---

### Task E5: gateway 橋接 + contract 登記 + PR

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py` TOPIC_MAP（:96-107）
- Modify: `docs/contracts/interaction_contract.md`

- [x] **Step 1: TOPIC_MAP 加一行（橋接 only，不落盤——邊界紀律）**

```python
    "/brain/trace":                     "brain:trace",
```

- [x] **Step 2: contract 登記（additive，v2.12）**——`interaction_contract.md` 的
brain topic 段新增 `/brain/trace`（發布者 brain_node + interaction_executive_node、
String JSON、schema 指向 `pawai_contracts/trace_schema.py`、用途「決策鏈 trace，
回答為什麼做/不做」、QoS RELIABLE depth 10）。跑：

```bash
python3 scripts/ci/check_topic_contracts.py
```
Expected: PASS（沒登記會被 ghost-topic 擋下——這就是同 PR 的原因）。

- [x] **Step 3: gateway 測試確認不破**

```bash
cd pawai-studio/gateway && python3 -m pytest -q   # 64 passed, 1 skipped
```

- [x] **Step 4: 全量 + PR**

```bash
python3 -m pytest interaction_executive/test/ -q && \
PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q
gh pr create --title "Brain Trace v1 — decision-chain /brain/trace, additive-only (Plan E)" --fill
```

---

## Tests / 驗收

- 既有 258 IE + 348 brain + 64 gateway **零修改全綠**（additive 鐵證）。
- 新增：contracts trace schema 測試（CI）+ trace emission 測試（本機）。
- **Jetson smoke**（merge 後）：brain lane 起、`ros2 topic echo /brain/trace` 同時
  做一次「gesture off 時比手勢」+「s3_object phase 時比手勢」→ 兩條 suppressed
  trace 即時可見；Studio event drawer 出現 `brain:trace` 事件。
- 驗收金句：之後任何「為什麼沒講/沒動」的問題，第一步永遠是看 `/brain/trace`，
  不再用猜的。

## Rollback

Revert PR 即可（additive topic，無消費者依賴）。gateway 那行先 revert 也不影響
brain 端發射。

## 交棒（明確不在本 plan）

Studio Evidence Center plan 接手：gateway JSONL 落盤 `runtime/traces/{session_id}.jsonl`
（retention ~20MB × 20 sessions）、`GET /api/trace/*` + export、decision trace panel、
perception confidence panels。CLI 只讀同一份 JSONL。

---

## 執行結果（2026-06-11）

**PR #154 merged**（6 commits E1-E5 + review）。IE **276**（+6 emission 測試）/ brain 348 / contracts 10 / gateway 64 全綠零修改；golden referee 不受擾動；flake8 持平。
插樁 = plan 表 100%（15 點 + IE safety 鏡像）；熱路徑限流走獨立 `_trace_throttle`（不汙染 /brain/state）；contract v2.12 與 E2 同 commit（ghost-topic gate 攔截後前移）。
表外 gap（v2 候選）：gesture confirm cooldown / stranger 內部 5 條件 / pose 路徑 / object whitelist / skill_request cooldown / chat stale drop。Timer 驅動 emission 的 decision_id 歸屬留 ISM。
**Jetson smoke 未做**（需 Roy）：`ros2 topic echo /brain/trace` + gesture off / s3_object phase 兩情境驗 suppressed 即時可見。
