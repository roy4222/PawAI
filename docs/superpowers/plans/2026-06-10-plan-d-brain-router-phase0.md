# Plan D: Brain Router Phase 0（PerceptionEvent 解析抽出）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `brain_node.py` 五個感知 callback（face/object/gesture/pose/speech）各自手刻的 JSON 解析抽成單一 `perception_router` 模組與標準化 `PerceptionEvent`，**輸出（/brain/proposal）逐 byte 不變**，golden fixture 測試為最終裁判。

**Architecture:** Phase 0 = **只抽解析、不動任何 gate/cooldown/dedup/文案**（Roy 拍板的窄版）。
`perception_router.py` 是純 Python（無 rclpy），住在 interaction_executive 套件內；
`PerceptionEvent` 暫不進 pawai_contracts（v1 contracts 範圍明文排除它；等第二個消費者
——Trace/ISM——出現再升格，YAGNI）。brain_node 以 `perception_router_enabled` 參數切換
新舊解析路徑，legacy 路徑保留一個 release 週期。

**Tech Stack:** dataclass、pytest（純解析測試進 CI；golden node 級測試屬本機 rclpy 層）。

---

## Scope

- Create: `interaction_executive/interaction_executive/perception_router.py`
- Create: `interaction_executive/test/test_perception_router.py`（純，CI-safe）
- Create: `interaction_executive/test/test_router_golden.py`（rclpy，本機層）
- Modify: `interaction_executive/interaction_executive/brain_node.py`（5 個 callback 的解析段 + `_declare_params`）
- Modify: `.github/workflows/ros_build.yaml` + `scripts/hooks/git-pre-commit.sh`（IE 清單補 `test_perception_router.py`）

## Forbidden scope（Roy 拍板原文）

- **不要在這一步改 gate、cooldown、TTS 文案**——dedup 窗口、accumulate timers、
  attention 邏輯、demo flags 全部原地不動（那是 ISM/Policy 的事）
- 不改 `/brain/proposal` wire format、不加新 topic、不動 `executive.yaml`
- 任何「順手修」（例如 object 雙格式統一、face or-chain 簡化）一律禁止——
  解析語意必須逐字搬移，golden test 不過就是搬錯
- PerceptionEvent 本 plan 不進 pawai_contracts

## 執行前提

Plan C merged（contracts 存在、606 測試綠為 baseline）。單一 PR。

---

### Task D1: PerceptionEvent + 五個 parser（純函數）

**Files:**
- Create: `interaction_executive/interaction_executive/perception_router.py`
- Test: `interaction_executive/test/test_perception_router.py`

- [ ] **Step 1: 寫 failing tests（每 kind 至少：正常 payload、缺欄位、legacy 替代格式）**

```python
# interaction_executive/test/test_perception_router.py
"""Pure parser tests — CI-safe (no rclpy). Payload shapes mirror the real wire
formats documented in docs/contracts/interaction_contract.md + the dual formats
brain_node historically accepts (face identity vs stable_name+event_type;
object objects[] vs flat)."""
from interaction_executive.perception_router import (
    PerceptionEvent, parse_face, parse_gesture, parse_object, parse_pose, parse_speech,
)


def test_parse_speech_or_chain_and_session_fallback():
    ev = parse_speech({"transcript": " 你好 ", "session_id": "s1"})
    assert (ev.kind, ev.transcript, ev.session_id) == ("speech", "你好", "s1")
    ev2 = parse_speech({"text": "hi", "request_id": "r9"})
    assert ev2.transcript == "hi" and ev2.session_id == "r9"
    ev3 = parse_speech({})
    assert ev3.transcript == "" and ev3.session_id.startswith("speech-")


def test_parse_face_both_wire_formats():
    new = parse_face({"stable_name": "Roy", "event_type": "identity_stable",
                      "distance_m": 1.2})
    assert (new.identity, new.stable) == ("Roy", True)
    old = parse_face({"identity": "alice", "identity_stable": True})
    assert (old.identity, old.stable) == ("alice", True)
    unk = parse_face({"event_type": "track_started"})
    assert unk.identity == "unknown" and unk.stable is False


def test_parse_object_array_and_flat_formats():
    arr = parse_object({"objects": [
        {"class_name": "cup", "confidence": 0.62, "color": "red"},
        {"class_name": "chair", "confidence": 0.9},
    ]})
    assert arr.class_name == "cup" and arr.color == "red" and len(arr.objects) == 2
    flat = parse_object({"class_name": "laptop", "confidence": 0.8})
    assert flat.class_name == "laptop" and flat.objects[0]["class_name"] == "laptop"
    empty = parse_object({"objects": []})
    assert empty.class_name is None


def test_parse_gesture_fields():
    ev = parse_gesture({"gesture": "thumbs_up", "confidence": 0.83, "hand": "right"})
    assert (ev.gesture, ev.confidence) == ("thumbs_up", 0.83)


def test_parse_pose_fields():
    ev = parse_pose({"pose": "sitting", "confidence": 0.7})
    assert ev.pose == "sitting"


def test_raw_payload_always_kept():
    payload = {"gesture": "wave", "extra": 1}
    assert parse_gesture(payload).raw is payload
```

- [ ] **Step 2: 跑確認 fail**

```bash
PYTHONPATH=interaction_executive python3 -m pytest \
  interaction_executive/test/test_perception_router.py -q
```
Expected: FAIL（ModuleNotFoundError: perception_router）。

- [ ] **Step 3: 實作 `perception_router.py`**

```python
"""Perception Event Router — Phase 0 (Plan D, 2026-06-10).

Pure-Python extraction of the five JSON-parsing prologs that lived inline in
brain_node callbacks. SEMANTICS ARE LIFTED VERBATIM from brain_node.py at tag
post-demo-refactor-baseline-2026-06-10 (face :1145-1175, object :1333-1364,
gesture :841-, pose :1254-, speech :565-575). Behavior-frozen: the golden
fixture suite (test_router_golden.py) asserts byte-identical /brain/proposal
output with the router on vs off. No gating/cooldown/dedup lives here — Phase 0
is parsing only; timers/dedup relocation is a later ISM-phase decision.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerceptionEvent:
    kind: str                      # face | object | gesture | pose | speech
    source_topic: str
    ts: float
    raw: dict[str, Any]
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    confidence: float | None = None
    # face
    identity: str | None = None
    stable: bool = False
    distance_m: float | None = None
    # object — first object's fields + full list
    class_name: str | None = None
    color: str | None = None
    objects: list[dict[str, Any]] = field(default_factory=list)
    # gesture
    gesture: str | None = None
    hand: str | None = None
    # pose
    pose: str | None = None
    # speech
    transcript: str | None = None
    session_id: str | None = None


def parse_speech(payload: dict[str, Any]) -> PerceptionEvent:
    # Lifted verbatim from brain_node._on_speech_intent (baseline :567-573)
    transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
    session_id = str(
        payload.get("session_id") or payload.get("request_id") or f"speech-{time.time_ns()}"
    )
    return PerceptionEvent(
        kind="speech", source_topic="/event/speech_intent_recognized",
        ts=time.time(), raw=payload, transcript=transcript, session_id=session_id,
    )


def parse_face(payload: dict[str, Any]) -> PerceptionEvent:
    # Lifted from brain_node._on_face (baseline :1145-1175): or-chain accepts both
    # the real wire format {stable_name, event_type} and the doc-era {identity,
    # identity_stable}. KEEP the or-chain order identical to the source.
    identity = str(
        payload.get("identity")
        or payload.get("stable_name")
        or payload.get("name")
        or "unknown"
    ).strip() or "unknown"
    stable = bool(payload.get("identity_stable")) or (
        str(payload.get("event_type") or "") == "identity_stable"
    )
    distance = payload.get("distance_m", payload.get("distance"))
    return PerceptionEvent(
        kind="face", source_topic="/event/face_identity", ts=time.time(), raw=payload,
        identity=identity, stable=stable,
        distance_m=float(distance) if isinstance(distance, (int, float)) else None,
    )


def parse_object(payload: dict[str, Any]) -> PerceptionEvent:
    # Lifted from brain_node._on_object (baseline :1333-1364): dual format —
    # {"objects": [...]} (current wire) vs flat single-object dict (legacy).
    objects = payload.get("objects")
    if not isinstance(objects, list):
        objects = [payload] if payload.get("class_name") else []
    first = objects[0] if objects else {}
    conf = first.get("confidence")
    return PerceptionEvent(
        kind="object", source_topic="/event/object_detected", ts=time.time(), raw=payload,
        objects=objects,
        class_name=first.get("class_name"),
        color=first.get("color"),
        confidence=float(conf) if isinstance(conf, (int, float)) else None,
    )


def parse_gesture(payload: dict[str, Any]) -> PerceptionEvent:
    conf = payload.get("confidence")
    return PerceptionEvent(
        kind="gesture", source_topic="/event/gesture_detected", ts=time.time(), raw=payload,
        gesture=str(payload.get("gesture") or "") or None,
        hand=payload.get("hand"),
        confidence=float(conf) if isinstance(conf, (int, float)) else None,
    )


def parse_pose(payload: dict[str, Any]) -> PerceptionEvent:
    conf = payload.get("confidence")
    return PerceptionEvent(
        kind="pose", source_topic="/event/pose_detected", ts=time.time(), raw=payload,
        pose=str(payload.get("pose") or "") or None,
        confidence=float(conf) if isinstance(conf, (int, float)) else None,
    )
```

**⚠ 抽取紀律**：上面 face/object 的表達式是按 baseline 原始碼起草的——實作時必須
開著 `brain_node.py` 對應行**逐字核對**（or-chain 順序、strip 行為、預設值、
isinstance 防衛），有任何出入以原始碼為準改 parser，**不准反過來改語意**。
golden suite（Task D3）是最終裁判。

- [ ] **Step 4: 跑綠 + commit**

```bash
PYTHONPATH=interaction_executive python3 -m pytest \
  interaction_executive/test/test_perception_router.py -q   # all pass
git add interaction_executive/ && \
git commit -m "feat(brain): perception_router Phase 0 — PerceptionEvent + 5 pure parsers, verbatim semantics (Plan D1)"
```

---

### Task D2: brain_node 接線（flag 雙路徑）

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py`

- [ ] **Step 1: `_declare_params` 加 flag（預設 True；golden 證明等價後才合理）**

```python
        # Plan D Phase 0 (2026-06-10): perception parsing extracted to
        # perception_router. False = legacy inline parsing (kept one release
        # as instant fallback). Flip via executive.yaml or ros2 param set.
        self.declare_parameter("perception_router_enabled", True)
```
與讀值行：

```python
        self.perception_router_enabled = bool(
            self.get_parameter("perception_router_enabled").value
        )
```

- [ ] **Step 2: 五個 callback 改造（模式一致；以 speech 為例）**

```python
    def _on_speech_intent(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        if self.perception_router_enabled:
            ev = parse_speech(payload)
            transcript, session_id = ev.transcript, ev.session_id
        else:  # legacy parse — Phase 0 fallback, byte-identical semantics
            transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
            session_id = str(
                payload.get("session_id") or payload.get("request_id") or f"speech-{time.time_ns()}"
            )
        # ……以下原邏輯一行不動，繼續用 transcript / session_id ……
```
face/object/gesture/pose 同款：**只把「派生變數的計算」換成 router 取值**，
callback 內所有 gate/timer/dedup/emit 邏輯原封不動。檔頭加
`from .perception_router import parse_face, parse_gesture, parse_object, parse_pose, parse_speech`。

- [ ] **Step 3: 既有測試全綠（第一道等價證據）**

```bash
python3 -m pytest interaction_executive/test/ -q
```
Expected: 258 passed（test_brain_rules 73 條 gate 測試會穿過新路徑——它們綠 =
解析語意沒變的強訊號）。

- [ ] **Step 4: commit**：`feat(brain): wire perception_router into 5 callbacks behind perception_router_enabled (Plan D2)`

---

### Task D3: Golden fixture suite（雙路徑逐 byte 比對）

**Files:**
- Create: `interaction_executive/test/test_router_golden.py`（rclpy — 本機 L1 層，**不進 CI 清單**）

- [ ] **Step 1: 寫 golden 測試**

```python
"""Golden fixtures (Plan D3): same payload through router-ON vs router-OFF
must produce IDENTICAL /brain/proposal sequences (normalized on plan_id /
created_at / session_id uuids). This suite is the Phase 0 behavior-frozen
authority. rclpy required → local tier, run before every Plan-D-touching PR."""
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


FIXTURES: list[tuple[str, dict]] = [
    # (callback_name, payload) — cover both wire formats + demo-relevant shapes
    ("_on_speech_intent", {"transcript": "你好", "session_id": "g1"}),
    ("_on_speech_intent", {"text": "停", "request_id": "g2"}),
    ("_on_gesture", {"gesture": "palm", "confidence": 0.9, "hand": "right"}),
    ("_on_gesture", {"gesture": "thumbs_up", "confidence": 0.95}),
    ("_on_face", {"stable_name": "Roy", "event_type": "identity_stable"}),
    ("_on_face", {"identity": "alice", "identity_stable": True}),
    ("_on_face", {"event_type": "track_lost"}),
    ("_on_pose", {"pose": "sitting", "confidence": 0.8}),
    ("_on_pose", {"pose": "fallen", "confidence": 0.9}),
    ("_on_object", {"objects": [{"class_name": "cup", "confidence": 0.6, "color": "red"}]}),
    ("_on_object", {"objects": [{"class_name": "chair", "confidence": 0.9},
                                 {"class_name": "cup", "confidence": 0.5}]}),
    ("_on_object", {"class_name": "laptop", "confidence": 0.7}),   # flat legacy
    ("_on_object", {"objects": []}),
]


def _normalize(published: list[str]) -> list[dict]:
    out = []
    for raw in published:
        d = json.loads(raw)
        for vol in ("plan_id", "created_at", "session_id"):
            d.pop(vol, None)
        for step in d.get("steps", []):
            step.pop("step_id", None)
        out.append(d)
    return out


def _run_path(router_on: bool) -> list[dict]:
    node = BrainNode()
    try:
        node.perception_router_enabled = router_on
        # 凍結時間敏感 gate 的影響：把 cooldown/dedup 的狀態保持初始即可——
        # 兩條路徑用同一個全新 node，差異只可能來自解析。
        published: list[str] = []
        node._pub_proposal.publish = lambda m: published.append(m.data)  # type: ignore
        for cb_name, payload in FIXTURES:
            msg = String(); msg.data = json.dumps(payload, ensure_ascii=False)
            getattr(node, cb_name)(msg)
        return _normalize(published)
    finally:
        node.destroy_node()


def test_router_on_off_identical_proposals():
    assert _run_path(True) == _run_path(False)
```

- [ ] **Step 2: 跑（本機）**

```bash
python3 -m pytest interaction_executive/test/test_router_golden.py -q
```
Expected: PASS。若 fail → diff 兩邊 normalized JSON，**修 parser 對齊 legacy**，
不准動 legacy。

- [ ] **Step 3: commit**：`test(brain): golden fixtures — router on/off byte-identical proposals (Plan D3)`

---

### Task D4: CI / pre-commit 清單補檔 + PR

- [ ] **Step 1**: `.github/workflows/ros_build.yaml` invocation 3 檔案清單 +
`scripts/hooks/git-pre-commit.sh` IE 檔案清單各加
`interaction_executive/test/test_perception_router.py`（golden 檔**不加**——rclpy）。

- [ ] **Step 2: 全量驗證 + PR**

```bash
python3 -m pytest interaction_executive/test/ -q && \
PYTHONPATH=pawai_brain python3 -m pytest pawai_brain/test/ -q
gh pr create --title "Brain Router Phase 0 — parsing extraction, behavior-frozen (Plan D)" --fill
```
PR description 必含：golden suite 輸出截圖/log + 「258+348 零修改全綠」。

---

## Tests / 驗收

- 純 parser 測試（CI）+ golden 雙路徑等價（本機）+ 既有 606 全綠零修改。
- Jetson smoke（merge 後首次部署）：brain lane 起來後對著真感知各觸發一輪
  （說話/比手勢/露臉/放杯子），`pawai logs brain` 確認 PROPOSAL 行為與部署前一致
  ——**不需 Go2 motion**。

## Rollback

`ros2 param set /brain_node perception_router_enabled false`（runtime 即回 legacy 路徑，
不用重佈）；或 revert PR。legacy 解析碼保留至 ISM Phase 1 落地後才刪（另開 PR）。
