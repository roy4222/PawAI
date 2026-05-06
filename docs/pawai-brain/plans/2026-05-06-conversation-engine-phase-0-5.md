# Conversation Engine Phase 0.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Phase 0.5 of `docs/pawai-brain/specs/2026-05-06-conversation-engine-langgraph-design.md` — extend `/brain/chat_candidate` with optional skill proposal, gate it in `brain_node` with a 2-skill allowlist + execute/trace-only policy, light up Studio trace UI, and stand up a `pawai_brain` ROS2 shadow package running a minimal LangGraph that does not touch the production path.

**Architecture:** Three cuts, each independently demoable. Cut 1 = schema + brain allowlist + Studio trace + model default sync (the actual demo value). Cut 2 = `pawai_brain` ROS2 package with a 4-node LangGraph shadow that subscribes the same ASR input but only publishes `/brain/conversation_trace_shadow`. Cut 3 = slim `llm_bridge_node.py` by moving pure logic into `speech_processor/conversation/` (zero behavior change). All three cuts preserve the contract: legacy `llm_bridge_node` remains the sole `/brain/chat_candidate` publisher; `brain_node` remains the sole arbiter; `interaction_executive_node` remains the sole action sink.

**Tech Stack:** ROS2 Humble (rclpy), Python 3.10 (Jetson) / 3.11 (WSL Studio backend), pytest, colcon, LangGraph 0.2+ (`langgraph` + `langchain-core`), OpenRouter (Gemini 3 Flash + DeepSeek V4 Flash fallback), edge-tts / Piper TTS, FastAPI + websockets gateway, Next.js 14 + React 18 Studio frontend.

**Reference docs to keep open while executing:**
- Spec: `docs/pawai-brain/specs/2026-05-06-conversation-engine-langgraph-design.md`
- Overview: `docs/pawai-brain/architecture/overview.md` §3.5
- Contract: `docs/contracts/interaction_contract.md`
- llm_bridge entry: `speech_processor/speech_processor/llm_bridge_node.py:296` (parse) / `:1047` (publish)
- brain entry: `interaction_executive/interaction_executive/brain_node.py:296` (`_on_chat_candidate`)
- adapter: `speech_processor/speech_processor/llm_contract.py:101` (`adapt_eval_schema`)
- gateway: `pawai-studio/gateway/studio_gateway.py:67` (topic_map)
- Studio drawer: `pawai-studio/frontend/components/chat/brain/skill-trace-drawer.tsx`

---

## Cut 1 — Schema + Brain Gate + Studio Trace (MUST-DELIVER)

This cut alone is enough to record tonight's demo: viewers will see "LLM proposed → Brain accepted/blocked/rejected" trace bubbles. Cuts 2 & 3 add architectural value but do not unlock new demo behavior.

### Task 1: Add `extract_proposal()` to `llm_contract.py`

Persona JSON is `{reply, skill, args}`. Today `adapt_eval_schema()` drops `skill` unless it's one of the 4 P0 legacy commands. We need a separate helper that preserves the raw skill so `brain_node` can gate it.

**Files:**
- Modify: `speech_processor/speech_processor/llm_contract.py:101-149`
- Test: `speech_processor/test/test_llm_contract.py` (create or extend)

- [ ] **Step 1: Write the failing tests**

Append to `speech_processor/test/test_llm_contract.py` (create file if missing — copy module docstring + import block from existing tests folder pattern):

```python
"""Tests for llm_contract helpers."""
from speech_processor.llm_contract import adapt_eval_schema, extract_proposal


def test_extract_proposal_returns_skill_and_args_when_present():
    eval_obj = {
        "reply": "汪，我是 PawAI",
        "skill": "self_introduce",
        "args": {},
    }
    proposal = extract_proposal(eval_obj)
    assert proposal == {
        "proposed_skill": "self_introduce",
        "proposed_args": {},
        "proposal_reason": "openrouter:eval_schema",
    }


def test_extract_proposal_returns_none_skill_when_missing():
    proposal = extract_proposal({"reply": "你好"})
    assert proposal["proposed_skill"] is None
    assert proposal["proposed_args"] == {}


def test_extract_proposal_handles_non_dict_args():
    proposal = extract_proposal({"reply": "...", "skill": "show_status", "args": "ignore"})
    assert proposal["proposed_skill"] == "show_status"
    assert proposal["proposed_args"] == {}


def test_extract_proposal_preserves_skill_outside_legacy_p0():
    """The whole point: persona skill that adapt_eval_schema would drop must survive here."""
    proposal = extract_proposal({"reply": "...", "skill": "show_status", "args": {}})
    assert proposal["proposed_skill"] == "show_status"


def test_adapt_eval_schema_unchanged_for_legacy_skill():
    """Regression guard: adapt_eval_schema behavior must not change."""
    bridge = adapt_eval_schema({"reply": "stop", "skill": "stop_move", "args": {}})
    assert bridge["selected_skill"] == "stop_move"
    assert bridge["reply_text"] == "stop"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest speech_processor/test/test_llm_contract.py -v
```

Expected: tests for `extract_proposal` fail with `ImportError` or `AttributeError`. The `adapt_eval_schema` regression test should already pass.

- [ ] **Step 3: Implement `extract_proposal`**

Append after `adapt_eval_schema` at `speech_processor/speech_processor/llm_contract.py:149`:

```python
def extract_proposal(eval_obj: dict) -> dict:
    """Pull skill proposal fields from persona JSON, bypassing legacy filtering.

    Unlike adapt_eval_schema (which only keeps the 4 P0 legacy commands in
    selected_skill), this preserves any skill name. brain_node enforces its
    own allowlist downstream — this is just a faithful pass-through.

    Returns:
        dict with keys {proposed_skill, proposed_args, proposal_reason}.
        proposed_skill is None if persona did not include one.
    """
    if not isinstance(eval_obj, dict):
        eval_obj = {}

    raw_skill = eval_obj.get("skill")
    proposed_skill = raw_skill.strip() if isinstance(raw_skill, str) and raw_skill.strip() else None

    raw_args = eval_obj.get("args")
    proposed_args = raw_args if isinstance(raw_args, dict) else {}

    return {
        "proposed_skill": proposed_skill,
        "proposed_args": proposed_args,
        "proposal_reason": "openrouter:eval_schema",
    }
```

Add `extract_proposal` to the module's `__all__` if one exists; otherwise no extra change needed.

- [ ] **Step 4: Run tests to verify they pass**

```
pytest speech_processor/test/test_llm_contract.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```
git add speech_processor/speech_processor/llm_contract.py speech_processor/test/test_llm_contract.py
git commit -m "feat(speech_processor): add extract_proposal() bypassing legacy P0 filter"
```

---

### Task 2: Extend `chat_candidate` payload in `llm_bridge_node`

Wire `extract_proposal()` into the publish path so every chat_candidate carries the optional 4 fields plus `engine="legacy"`.

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:1047-1075` (`_emit_chat_candidate`)
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:920-1000` (call sites of `_emit_chat_candidate`)
- Test: `speech_processor/test/test_llm_bridge_node.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `speech_processor/test/test_llm_bridge_node.py` (find existing test that publishes a chat_candidate and copy its setup; append new assertions):

```python
def test_chat_candidate_includes_proposal_fields_when_persona_returns_skill(monkeypatch, tmp_path):
    """Persona returns {reply, skill: 'show_status', args: {}} →
    chat_candidate should carry proposed_skill='show_status'."""
    captured = {}

    def fake_publish(msg):
        captured["payload"] = json.loads(msg.data)

    node = _make_node_for_test(monkeypatch, tmp_path)
    node.chat_candidate_pub.publish = fake_publish
    node.output_mode = "brain"

    node._emit_chat_candidate(
        session_id="test-1",
        reply_text="目前一切正常",
        intent="status",
        selected_skill=None,
        confidence=0.85,
        proposed_skill="show_status",
        proposed_args={},
        proposal_reason="openrouter:eval_schema",
    )

    p = captured["payload"]
    assert p["reply_text"] == "目前一切正常"
    assert p["selected_skill"] is None
    assert p["proposed_skill"] == "show_status"
    assert p["proposed_args"] == {}
    assert p["proposal_reason"] == "openrouter:eval_schema"
    assert p["engine"] == "legacy"


def test_chat_candidate_proposal_fields_default_to_none_when_omitted():
    captured = {}
    # ... same setup ...
    node._emit_chat_candidate(
        session_id="test-2",
        reply_text="你好",
        intent="chat",
        selected_skill=None,
        confidence=0.8,
    )
    p = captured["payload"]
    assert p["proposed_skill"] is None
    assert p["proposed_args"] == {}
    assert p["engine"] == "legacy"
```

If `_make_node_for_test` doesn't exist, write a minimal one using existing pattern (look for how other tests in the file instantiate `LlmBridgeNode`). If existing tests use `rclpy.init()` / `node = LlmBridgeNode()`, copy that.

- [ ] **Step 2: Run test to verify it fails**

```
pytest speech_processor/test/test_llm_bridge_node.py::test_chat_candidate_includes_proposal_fields_when_persona_returns_skill -v
```

Expected: TypeError (unexpected keyword argument `proposed_skill`) or KeyError (`engine`).

- [ ] **Step 3: Update `_emit_chat_candidate` signature and payload**

Replace `speech_processor/speech_processor/llm_bridge_node.py:1047-1075` with:

```python
    def _emit_chat_candidate(
        self,
        session_id: str,
        reply_text: str,
        intent: str,
        selected_skill: str | None,
        confidence: float,
        proposed_skill: str | None = None,
        proposed_args: dict | None = None,
        proposal_reason: str = "",
    ) -> None:
        """Brain-mode output: publish reply for Brain to consume.

        selected_skill is legacy diagnostic (4 P0 commands only).
        proposed_skill / proposed_args are the new Phase 0.5 contract;
        brain_node enforces an allowlist downstream.
        """
        payload = {
            "session_id": session_id,
            "reply_text": reply_text,
            "intent": intent,
            "selected_skill": selected_skill,
            "source": "llm_bridge",
            "confidence": float(confidence),
            "created_at": time.time(),
            # Phase 0.5 additions
            "proposed_skill": proposed_skill,
            "proposed_args": proposed_args if isinstance(proposed_args, dict) else {},
            "proposal_reason": proposal_reason,
            "engine": "legacy",
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.chat_candidate_pub.publish(msg)
        self.get_logger().info(
            f"Published /brain/chat_candidate: session={session_id} "
            f"reply={reply_text!r} proposed={proposed_skill}"
        )
```

- [ ] **Step 4: Wire the call sites**

Find both `self._emit_chat_candidate(` calls (around lines 920-1000) — they currently pass 5 positional args. After parsing `bridge_dict = adapt_eval_schema(parsed)` (`llm_bridge_node.py:648`), also call `extract_proposal(parsed)` and pass through. Concretely, in the function that owns the line at `:648`:

```python
from .llm_contract import adapt_eval_schema, extract_proposal  # update existing import on line 44

# ... after bridge_dict = adapt_eval_schema(parsed) ...
proposal = extract_proposal(parsed)
```

Then at every `self._emit_chat_candidate(...)` call, add the three new kwargs:

```python
self._emit_chat_candidate(
    session_id=session_id,
    reply_text=reply,
    intent=intent,
    selected_skill=selected_skill,
    confidence=confidence,
    proposed_skill=proposal["proposed_skill"],
    proposed_args=proposal["proposed_args"],
    proposal_reason=proposal["proposal_reason"],
)
```

For the RuleBrain fallback call site (no `parsed`), pass `proposed_skill=None`, `proposed_args={}`, `proposal_reason=""`.

- [ ] **Step 5: Run tests to verify they pass**

```
pytest speech_processor/test/test_llm_bridge_node.py -v
```

Expected: all tests pass, including the new two.

- [ ] **Step 6: Commit**

```
git add speech_processor/speech_processor/llm_bridge_node.py speech_processor/test/test_llm_bridge_node.py
git commit -m "feat(llm_bridge): emit proposed_skill/proposed_args/engine in chat_candidate"
```

---

### Task 3: Sync OpenRouter model defaults to Gemini 3 Flash

Spec §3 requires `google/gemini-3-flash-preview` as primary. Current default is 2.5-flash; tmux script overrides primary slot to deepseek-v4-flash (so both slots are deepseek today).

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:232`
- Modify: `scripts/start_full_demo_tmux.sh:192`
- Modify: `scripts/start_llm_e2e_tmux.sh` (search for `openrouter_gemini_model`; if absent, no-op)

- [ ] **Step 1: Update llm_bridge default**

Change `speech_processor/speech_processor/llm_bridge_node.py:232` from:

```python
            "openrouter_gemini_model", "google/gemini-2.5-flash"
```

to:

```python
            "openrouter_gemini_model", "google/gemini-3-flash-preview"
```

- [ ] **Step 2: Update tmux launch override**

`scripts/start_full_demo_tmux.sh:192` currently:

```
    -p openrouter_gemini_model:=deepseek/deepseek-v4-flash \
```

Change to:

```
    -p openrouter_gemini_model:=google/gemini-3-flash-preview \
```

- [ ] **Step 3: Check the other launch script**

```
grep -n openrouter_gemini_model scripts/start_llm_e2e_tmux.sh
```

If it sets a value, update it the same way. If not, skip.

- [ ] **Step 4: Smoke (optional, only if you can hit the cloud right now)**

```
ros2 run speech_processor llm_bridge_node --ros-args -p enable_openrouter:=true \
  -p openrouter_gemini_model:=google/gemini-3-flash-preview
```

Watch logs for first request; expect a successful response or an explicit OpenRouter "model not found" — which would mean the model id is wrong and we need the real one before demo.

- [ ] **Step 5: Commit**

```
git add speech_processor/speech_processor/llm_bridge_node.py scripts/start_full_demo_tmux.sh scripts/start_llm_e2e_tmux.sh
git commit -m "config(llm_bridge): switch primary OpenRouter model to gemini-3-flash-preview"
```

---

### Task 4: Add LLM proposal allowlist + trace publisher to `brain_node`

Spec §6 — `_on_chat_candidate` keeps emitting `chat_reply` always; on top of that, gate `proposed_skill` through `LLM_PROPOSABLE_SKILLS`, run safety/cooldown, and emit `/brain/conversation_trace`.

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py` (around `:296` and class top for constants)
- Test: `interaction_executive/test/test_brain_rules.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `interaction_executive/test/test_brain_rules.py`:

```python
def test_chat_candidate_with_show_status_proposal_emits_chat_reply_then_show_status(brain):
    """show_status is in EXECUTE allowlist → both chat_reply and show_status enqueued."""
    brain.feed_speech("你還好嗎", session_id="s1")
    brain.feed_chat_candidate({
        "session_id": "s1",
        "reply_text": "我很好",
        "proposed_skill": "show_status",
        "proposed_args": {},
        "proposal_reason": "openrouter:eval_schema",
        "engine": "legacy",
    })
    plans = brain.drain_proposals()
    skills = [p["skill"] for p in plans]
    assert skills == ["chat_reply", "show_status"]
    traces = brain.drain_traces()
    assert any(t["stage"] == "skill_gate" and t["status"] == "accepted" for t in traces)


def test_chat_candidate_with_self_introduce_proposal_emits_chat_reply_only_trace_only(brain):
    """self_introduce is TRACE_ONLY → only chat_reply enqueued; trace records accepted_trace_only."""
    brain.feed_speech("你是誰", session_id="s2")
    brain.feed_chat_candidate({
        "session_id": "s2",
        "reply_text": "汪，我是 PawAI",
        "proposed_skill": "self_introduce",
        "proposed_args": {},
        "engine": "legacy",
    })
    plans = brain.drain_proposals()
    assert [p["skill"] for p in plans] == ["chat_reply"]
    traces = brain.drain_traces()
    assert any(
        t["stage"] == "skill_gate" and t["status"] == "accepted_trace_only" and t["detail"] == "self_introduce"
        for t in traces
    )


def test_chat_candidate_with_disallowed_proposal_rejected(brain):
    brain.feed_speech("跳舞", session_id="s3")
    brain.feed_chat_candidate({
        "session_id": "s3",
        "reply_text": "好啊",
        "proposed_skill": "dance",
        "proposed_args": {},
        "engine": "legacy",
    })
    plans = brain.drain_proposals()
    assert [p["skill"] for p in plans] == ["chat_reply"]
    traces = brain.drain_traces()
    assert any(
        t["stage"] == "skill_gate" and t["status"] == "rejected_not_allowed"
        for t in traces
    )


def test_chat_candidate_with_no_proposal_only_chat_reply(brain):
    brain.feed_speech("天氣如何", session_id="s4")
    brain.feed_chat_candidate({
        "session_id": "s4",
        "reply_text": "今天很適合散步",
        "proposed_skill": None,
        "engine": "legacy",
    })
    plans = brain.drain_proposals()
    assert [p["skill"] for p in plans] == ["chat_reply"]
    traces = brain.drain_traces()
    assert not any(t["stage"] == "skill_gate" for t in traces)
```

The `brain` fixture and `feed_*` / `drain_*` helpers may not exist exactly as written — adapt to whatever the existing test file uses (likely `_make_brain()` or fixture in `conftest.py`). Look at existing tests in the file for the pattern; mirror it. If you need to add `drain_traces()`, expose it from the test helper by capturing the `conversation_trace_pub.publish` call (same as proposal capture).

- [ ] **Step 2: Run tests to verify they fail**

```
pytest interaction_executive/test/test_brain_rules.py -k "proposal or trace_only or disallowed" -v
```

Expected: tests fail because `LLM_PROPOSABLE_SKILLS` is undefined and `drain_traces` returns nothing.

- [ ] **Step 3: Add allowlist constants**

Insert near the top of `BrainNode` class in `interaction_executive/interaction_executive/brain_node.py` (next to `_GESTURE_DIRECT` at `:328`):

```python
    # Phase 0.5 LLM proposal gate (spec 2026-05-06 §6)
    LLM_PROPOSABLE_SKILLS = frozenset({"show_status", "self_introduce"})
    LLM_PROPOSAL_EXECUTE = {
        "show_status": "execute",
        "self_introduce": "trace_only",
    }
```

- [ ] **Step 4: Add the trace publisher**

Find the section that creates publishers (search for `create_publisher`; near the proposal publisher). Add:

```python
        self.conversation_trace_pub = self.create_publisher(
            String, "/brain/conversation_trace", _RELIABLE_10
        )
```

Then add a helper method (place near `_emit`):

```python
    def _emit_trace(
        self,
        *,
        session_id: str,
        engine: str,
        stage: str,
        status: str,
        detail: str = "",
    ) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "session_id": session_id,
                "engine": engine,
                "stage": stage,
                "status": status,
                "detail": detail,
                "ts": time.time(),
            },
            ensure_ascii=False,
        )
        self.conversation_trace_pub.publish(msg)
```

If `json` / `time` are not yet imported, add the imports.

- [ ] **Step 5: Update `_on_chat_candidate`**

Replace `interaction_executive/interaction_executive/brain_node.py:296-320` with:

```python
    def _on_chat_candidate(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        session_id = str(payload.get("session_id") or "")
        reply_text = str(payload.get("reply_text") or "").strip()
        engine = str(payload.get("engine") or "legacy")
        if not session_id:
            return

        with self._lock:
            buffered = self._state.chat_buffer.pop(session_id, None)
            self._state.fallback_active = False

        # 1. Always speak the reply (if non-empty and we were waiting on this session).
        if reply_text and buffered is not None:
            timer = self._chat_timeouts.pop(session_id, None)
            if timer is not None:
                self.destroy_timer(timer)
            self._emit(
                build_plan(
                    "chat_reply",
                    args={"text": reply_text},
                    source="llm_bridge",
                    reason="chat_candidate_match",
                    session_id=session_id,
                )
            )

        # 2. Optional skill proposal — independent side effect.
        proposed_skill = payload.get("proposed_skill")
        if not isinstance(proposed_skill, str) or not proposed_skill:
            return
        proposed_args = payload.get("proposed_args") or {}
        if not isinstance(proposed_args, dict):
            proposed_args = {}

        if proposed_skill not in self.LLM_PROPOSABLE_SKILLS:
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="rejected_not_allowed",
                detail=proposed_skill,
            )
            return

        cd = SKILL_REGISTRY[proposed_skill].cooldown_s
        if self._in_cooldown(proposed_skill, cd):
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="blocked",
                detail=f"{proposed_skill}:cooldown",
            )
            return

        mode = self.LLM_PROPOSAL_EXECUTE.get(proposed_skill, "trace_only")
        if mode == "execute":
            self._emit_with_cooldown(
                proposed_skill,
                args=proposed_args,
                source="llm_proposal",
                reason=f"llm_proposal:{proposed_skill}",
            )
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="accepted",
                detail=proposed_skill,
            )
        else:
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="accepted_trace_only",
                detail=proposed_skill,
            )
```

Verify `_emit_with_cooldown` signature matches; if it doesn't accept `args`, fall back to:

```python
            self._emit(
                build_plan(
                    proposed_skill,
                    args=proposed_args,
                    source="llm_proposal",
                    reason=f"llm_proposal:{proposed_skill}",
                    session_id=session_id,
                )
            )
            self._record_cooldown(proposed_skill)  # or whatever the existing method is
```

Use existing `_emit_with_cooldown` if it can take args; otherwise the `_emit` + cooldown form is fine.

- [ ] **Step 6: Run tests to verify they pass**

```
pytest interaction_executive/test/test_brain_rules.py -v
```

Expected: all tests pass, including the 4 new ones.

- [ ] **Step 7: Commit**

```
git add interaction_executive/interaction_executive/brain_node.py interaction_executive/test/test_brain_rules.py
git commit -m "feat(brain_node): LLM proposal allowlist + conversation_trace publisher"
```

---

### Task 5: Wire `/brain/conversation_trace` through Studio gateway

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py:67` (topic_map)

- [ ] **Step 1: Add the topic to the gateway map**

Edit `pawai-studio/gateway/studio_gateway.py:67`. Add a line:

```python
    "/brain/conversation_trace":       "brain:conversation_trace",
    "/brain/conversation_trace_shadow":"brain:conversation_trace_shadow",
```

These join the existing `/brain/proposal` and `/brain/skill_result` entries. Existing subscription/broadcast plumbing should pick them up automatically — verify by reading the loop that iterates topic_map (search for `topic_map` references in the file). If iteration uses `String` as message type, no further change needed.

- [ ] **Step 2: Smoke-test with ros2 topic pub**

```
ros2 topic pub --once /brain/conversation_trace std_msgs/String '{data: "{\"session_id\":\"x\",\"stage\":\"skill_gate\",\"status\":\"accepted\",\"detail\":\"show_status\",\"engine\":\"legacy\",\"ts\":0}"}'
```

Then check the Studio WS stream (open browser devtools network → WS, or `wscat`) for a frame with type `brain:conversation_trace`. If present, gateway is wired.

- [ ] **Step 3: Commit**

```
git add pawai-studio/gateway/studio_gateway.py
git commit -m "feat(studio_gateway): broadcast /brain/conversation_trace[_shadow]"
```

---

### Task 6: Render proposal trace in Studio Skill Trace Drawer

**Files:**
- Modify: `pawai-studio/frontend/components/chat/brain/skill-trace-drawer.tsx`
- Possibly modify: `pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx`
- Possibly modify: `pawai-studio/frontend/lib/events.ts` (or wherever WS event types live — search for `brain:proposal`)

- [ ] **Step 1: Add the new event type**

Search `pawai-studio/frontend/` for `brain:proposal`:

```
grep -rn "brain:proposal" pawai-studio/frontend
```

Wherever the union type lives (likely a discriminated union with `type: "brain:proposal" | "brain:skill_result" | ...`), add `"brain:conversation_trace"` and `"brain:conversation_trace_shadow"`. Add a TS interface for the trace payload:

```typescript
export interface ConversationTracePayload {
  session_id: string;
  engine: "legacy" | "langgraph";
  stage: "input" | "safety_gate" | "context" | "memory" | "llm_decision"
       | "json_validate" | "repair" | "skill_gate" | "output";
  status: "ok" | "retry" | "fallback" | "error"
        | "proposed" | "accepted" | "accepted_trace_only" | "blocked" | "rejected_not_allowed";
  detail: string;
  ts: number;
}
```

- [ ] **Step 2: Render trace chips in the drawer**

Open `skill-trace-drawer.tsx`. Add a state slot for traces (mirror the existing proposals slot — a ring buffer of last ~20). On `brain:conversation_trace` event, push to the buffer. Render:

```tsx
function statusToColor(status: string): string {
  switch (status) {
    case "accepted":
    case "ok":
      return "bg-emerald-100 text-emerald-700 border-emerald-300";
    case "accepted_trace_only":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "proposed":
      return "bg-slate-100 text-slate-700 border-slate-300";
    case "blocked":
    case "fallback":
    case "retry":
      return "bg-amber-100 text-amber-800 border-amber-300";
    case "rejected_not_allowed":
    case "error":
      return "bg-rose-100 text-rose-700 border-rose-300";
    default:
      return "bg-slate-100 text-slate-700 border-slate-300";
  }
}

// inside the drawer body, alongside existing proposal list:
<section className="space-y-1">
  <h3 className="text-xs font-semibold text-slate-500">Conversation Trace</h3>
  {traces.length === 0 ? (
    <p className="text-xs text-slate-400">尚無 trace</p>
  ) : (
    <ul className="space-y-1">
      {traces.map((t, i) => (
        <li
          key={`${t.session_id}-${t.ts}-${i}`}
          className={`text-xs border rounded px-2 py-1 ${statusToColor(t.status)}`}
        >
          <span className="font-mono">{t.stage}</span>
          {" · "}
          <span className="font-semibold">{t.status}</span>
          {t.detail ? (
            <>
              {" · "}
              <span>{t.detail}</span>
            </>
          ) : null}
          <span className="ml-2 text-[10px] opacity-60">
            {t.engine}
          </span>
        </li>
      ))}
    </ul>
  )}
</section>
```

If traces are aggregated in `skill-trace-content.tsx` instead, place this section there.

- [ ] **Step 3: Run frontend dev server and eyeball**

```
cd pawai-studio
bash start.sh   # or npm --prefix frontend run dev
```

Open http://localhost:3000/studio, open the Skill Trace Drawer. Trigger a fake trace via Task 5 step 2's `ros2 topic pub` (or the mock_server `/mock/scenario/...` if it has one). Confirm chip appears with the right colour.

- [ ] **Step 4: Commit**

```
git add pawai-studio/frontend
git commit -m "feat(studio): render /brain/conversation_trace chips in trace drawer"
```

---

### Task 7: Update topic contract doc

**Files:**
- Modify: `docs/contracts/interaction_contract.md`

- [ ] **Step 1: Edit the contract**

Add to the `/brain/chat_candidate` section a new "Phase 0.5 fields" block listing `proposed_skill`, `proposed_args`, `proposal_reason`, `engine`, with the same descriptions as spec §4.1.

Add new top-level entries for `/brain/conversation_trace` and `/brain/conversation_trace_shadow` with schema (mirror spec §4.2).

- [ ] **Step 2: Run the contract check (pre-commit hook covers this on commit)**

```
bash scripts/check_topic_contract.sh   # if it exists; otherwise pre-commit will run it
```

- [ ] **Step 3: Commit**

```
git add docs/contracts/interaction_contract.md
git commit -m "docs(contract): add chat_candidate proposal fields + conversation_trace topics"
```

---

### Task 8: End-to-end smoke for Cut 1

- [ ] **Step 1: Build affected packages**

```
colcon build --packages-select speech_processor interaction_executive
source install/setup.zsh
```

- [ ] **Step 2: Run unit suites**

```
pytest speech_processor/test interaction_executive/test -v
```

Expected: all green.

- [ ] **Step 3: Live smoke (Jetson, full demo tmux)**

```
bash scripts/start_full_demo_tmux.sh
```

In a separate window:

```
ros2 topic echo /brain/chat_candidate
ros2 topic echo /brain/conversation_trace
ros2 topic echo /brain/proposal
```

Drive a voice prompt: "你是誰" → expect `/brain/chat_candidate` with `proposed_skill="self_introduce"`, `/brain/conversation_trace` with `status=accepted_trace_only`, `/brain/proposal` containing only `chat_reply`.

Drive: "你還好嗎" → expect `proposed_skill="show_status"`, trace `accepted`, `/brain/proposal` containing `chat_reply` then `show_status`.

Drive: "跳舞" → expect proposal rejected (trace `rejected_not_allowed`), only `chat_reply` enqueued.

- [ ] **Step 4: Cut 1 done — record demo footage now if you want to lock value**

Before moving to Cut 2, capture the screen recording. Cut 2 runs as a separate process and won't perturb Cut 1's behavior, but keeping a known-good recording is cheap insurance.

---

## Cut 2 — `pawai_brain` ROS2 Package: LangGraph Shadow

This cut creates the new ROS2 package and runs a 4-node LangGraph in shadow mode. It only publishes `/brain/conversation_trace_shadow`. **It must not publish `/brain/chat_candidate`.**

### Task 9: Install LangGraph dependencies

**Files:** none (env work)

- [ ] **Step 1: Install on the development machine**

```
uv pip install langgraph langchain-core
```

- [ ] **Step 2: Install on the Jetson**

```
ssh jetson-nano "uv pip install --user langgraph langchain-core" \
  || ssh jetson-nano "pip install --user langgraph langchain-core"
```

Verify:

```
ssh jetson-nano "python3 -c 'import langgraph, langchain_core; print(langgraph.__version__)'"
```

If install fails (Jetson Python wheel issue), abort Cut 2 and proceed to Cut 3 — Cut 1 already delivers demo value. Document the failure in `docs/pawai-brain/specs/2026-05-06-conversation-engine-langgraph-design.md` §10 risk row.

- [ ] **Step 3: Note the version**

Record installed versions in the package's `setup.py` install_requires (Task 10 will reference these).

---

### Task 10: Scaffold `pawai_brain` ROS2 package skeleton

**Files (new):**
- `pawai_brain/package.xml`
- `pawai_brain/setup.py`
- `pawai_brain/setup.cfg`
- `pawai_brain/resource/pawai_brain` (empty marker file)
- `pawai_brain/pawai_brain/__init__.py` (empty)

- [ ] **Step 1: Create the directory tree**

```
mkdir -p pawai_brain/pawai_brain/nodes
mkdir -p pawai_brain/launch
mkdir -p pawai_brain/resource
mkdir -p pawai_brain/test
touch pawai_brain/resource/pawai_brain
touch pawai_brain/pawai_brain/__init__.py
touch pawai_brain/pawai_brain/nodes/__init__.py
```

- [ ] **Step 2: Write `package.xml`**

```xml
<?xml version="1.0"?>
<package format="3">
  <name>pawai_brain</name>
  <version>0.1.0</version>
  <description>PawAI Conversation Engine — LangGraph-based stateful conversation graph (shadow + future primary).</description>
  <maintainer email="roy422roy@gmail.com">roy</maintainer>
  <license>MIT</license>

  <exec_depend>rclpy</exec_depend>
  <exec_depend>std_msgs</exec_depend>

  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_pep257</test_depend>
  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

- [ ] **Step 3: Write `setup.py`**

```python
from setuptools import setup
from glob import glob

package_name = "pawai_brain"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name, f"{package_name}.nodes"],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=[
        "setuptools",
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
    ],
    zip_safe=True,
    maintainer="roy",
    maintainer_email="roy422roy@gmail.com",
    description="PawAI Conversation Engine — LangGraph shadow runtime.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "conversation_graph_node = pawai_brain.conversation_graph_node:main",
        ],
    },
)
```

- [ ] **Step 4: Write `setup.cfg`**

```
[develop]
script_dir=$base/lib/pawai_brain
[install]
install_scripts=$base/lib/pawai_brain
```

- [ ] **Step 5: colcon build sanity check**

```
colcon build --packages-select pawai_brain
```

Expected: builds clean with no source files yet (just metadata).

- [ ] **Step 6: Commit**

```
git add pawai_brain
git commit -m "feat(pawai_brain): scaffold empty ROS2 package"
```

---

### Task 11: ConversationState + 4 graph nodes

**Files (new):**
- `pawai_brain/pawai_brain/state.py`
- `pawai_brain/pawai_brain/nodes/input_normalizer.py`
- `pawai_brain/pawai_brain/nodes/llm_decision.py`
- `pawai_brain/pawai_brain/nodes/output_builder.py`
- `pawai_brain/pawai_brain/nodes/trace_emitter.py`
- `pawai_brain/pawai_brain/graph.py`
- `pawai_brain/test/test_graph_smoke.py`

- [ ] **Step 1: `state.py`**

```python
"""Phase 0.5 ConversationState — minimal fields for the shadow graph.

Phase 1 will expand this with safety_level, perception_context, validation_errors,
retry_count, etc. Today we only need enough to emit a trace and a candidate
response that mirrors what legacy llm_bridge produces.
"""
from __future__ import annotations
from typing import TypedDict, Literal


class ConversationState(TypedDict, total=False):
    session_id: str
    source: Literal["speech", "studio_text"]
    user_text: str

    llm_raw: str | None
    llm_json: dict | None

    reply_text: str
    proposed_skill: str | None
    proposed_args: dict
    proposal_reason: str

    trace: list[dict]
```

- [ ] **Step 2: `nodes/input_normalizer.py`**

```python
"""Normalise incoming ASR / Studio text events into ConversationState."""
from ..state import ConversationState


def input_normalizer(state: ConversationState) -> ConversationState:
    user_text = (state.get("user_text") or "").strip()
    state["user_text"] = user_text
    state.setdefault("trace", []).append(
        {"stage": "input", "status": "ok", "detail": user_text[:40]}
    )
    return state
```

- [ ] **Step 3: `nodes/llm_decision.py`**

For the shadow, we don't need to actually hit OpenRouter — we can stub a deterministic response so the graph runs without network. (The real LLM call lives in legacy `llm_bridge_node` for now; Phase 1 will swap shadow over.)

```python
"""LLM decision node.

Phase 0.5 (shadow): deterministic stub so the graph runs without network.
We just produce a reply mirroring the user_text and emit a fake trace.
Phase 1 swaps this for an OpenRouter call.
"""
from ..state import ConversationState


def llm_decision(state: ConversationState) -> ConversationState:
    user_text = state.get("user_text", "")
    reply = f"(shadow) 你說：{user_text}"
    state["reply_text"] = reply
    state["llm_json"] = {"reply": reply, "skill": None, "args": {}}
    state["proposed_skill"] = None
    state["proposed_args"] = {}
    state["proposal_reason"] = "shadow:stub"
    state.setdefault("trace", []).append(
        {"stage": "llm_decision", "status": "ok", "detail": "shadow_stub"}
    )
    return state
```

- [ ] **Step 4: `nodes/output_builder.py`**

```python
"""Build the chat_candidate-equivalent dict (NOT published in shadow)."""
from ..state import ConversationState


def output_builder(state: ConversationState) -> ConversationState:
    state.setdefault("trace", []).append(
        {
            "stage": "output",
            "status": "ok",
            "detail": (state.get("reply_text") or "")[:40],
        }
    )
    return state
```

- [ ] **Step 5: `nodes/trace_emitter.py`**

This one is a marker — actual ROS publish happens in the node wrapper that wraps the graph. Trace emitter just consolidates trace.

```python
"""Trace emitter — final node; ROS publish happens in the wrapper."""
from ..state import ConversationState


def trace_emitter(state: ConversationState) -> ConversationState:
    # No-op transformation; the wrapper reads state['trace'] and publishes.
    return state
```

- [ ] **Step 6: `graph.py`**

```python
"""Phase 0.5 LangGraph — minimal 4-node linear graph.

Phase 1 expands to 9-10 nodes with conditional edges (safety branches,
repair retries). For now: input → llm → output → trace.
"""
from langgraph.graph import StateGraph, END

from .state import ConversationState
from .nodes.input_normalizer import input_normalizer
from .nodes.llm_decision import llm_decision
from .nodes.output_builder import output_builder
from .nodes.trace_emitter import trace_emitter


def build_graph():
    g = StateGraph(ConversationState)
    g.add_node("input", input_normalizer)
    g.add_node("llm", llm_decision)
    g.add_node("output", output_builder)
    g.add_node("trace", trace_emitter)
    g.set_entry_point("input")
    g.add_edge("input", "llm")
    g.add_edge("llm", "output")
    g.add_edge("output", "trace")
    g.add_edge("trace", END)
    return g.compile()
```

- [ ] **Step 7: Smoke test**

`pawai_brain/test/test_graph_smoke.py`:

```python
"""Phase 0.5 graph happy-path smoke test."""
from pawai_brain.graph import build_graph


def test_graph_runs_end_to_end_and_collects_trace():
    graph = build_graph()
    final = graph.invoke({"session_id": "s1", "user_text": "你好", "source": "speech"})
    assert "reply_text" in final
    assert final["reply_text"].startswith("(shadow)")
    stages = [t["stage"] for t in final["trace"]]
    assert stages == ["input", "llm_decision", "output"]
```

Run:

```
pytest pawai_brain/test/test_graph_smoke.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```
git add pawai_brain
git commit -m "feat(pawai_brain): minimal LangGraph shadow with 4 stub nodes"
```

---

### Task 12: ROS2 wrapper node + launch file

**Files (new):**
- `pawai_brain/pawai_brain/conversation_graph_node.py`
- `pawai_brain/launch/pawai_conversation_graph.launch.py`

- [ ] **Step 1: Wrapper node**

```python
"""ROS2 wrapper around the LangGraph shadow runtime.

Subscribes /event/speech_intent_recognized.
Runs the graph (no network call in Phase 0.5).
Publishes /brain/conversation_trace_shadow per stage.
NEVER publishes /brain/chat_candidate in shadow mode.
"""
from __future__ import annotations
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .graph import build_graph


class ConversationGraphNode(Node):
    def __init__(self):
        super().__init__("conversation_graph_node")

        self.declare_parameter("conversation_engine", "shadow")  # shadow | langgraph
        engine_role = self.get_parameter("conversation_engine").get_parameter_value().string_value
        self._role = engine_role  # "shadow" today; "langgraph" reserved for Phase 1
        self._engine_label = "langgraph"

        self._graph = build_graph()

        self.create_subscription(
            String, "/event/speech_intent_recognized", self._on_speech, 10
        )

        trace_topic = (
            "/brain/conversation_trace_shadow"
            if self._role == "shadow"
            else "/brain/conversation_trace"
        )
        self._trace_pub = self.create_publisher(String, trace_topic, 10)

        self.get_logger().info(
            f"ConversationGraphNode online (role={self._role}, trace_topic={trace_topic})"
        )

    def _on_speech(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        user_text = str(payload.get("transcript") or payload.get("text") or "").strip()
        session_id = str(payload.get("session_id") or f"shadow-{time.time()}")
        if not user_text:
            return

        try:
            final = self._graph.invoke(
                {"session_id": session_id, "user_text": user_text, "source": "speech"}
            )
        except Exception as exc:  # noqa: BLE001 — shadow must never crash main flow
            self.get_logger().warning(f"graph invoke failed: {exc}")
            self._publish_trace(session_id, "output", "error", str(exc)[:80])
            return

        for entry in final.get("trace", []):
            self._publish_trace(
                session_id,
                entry.get("stage", ""),
                entry.get("status", "ok"),
                entry.get("detail", ""),
            )

    def _publish_trace(self, session_id: str, stage: str, status: str, detail: str) -> None:
        out = String()
        out.data = json.dumps(
            {
                "session_id": session_id,
                "engine": self._engine_label,
                "stage": stage,
                "status": status,
                "detail": detail,
                "ts": time.time(),
            },
            ensure_ascii=False,
        )
        self._trace_pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = ConversationGraphNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Launch file**

`pawai_brain/launch/pawai_conversation_graph.launch.py`:

```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    role = LaunchConfiguration("conversation_engine")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "conversation_engine",
                default_value="shadow",
                description="shadow | langgraph (Phase 1: primary cutover)",
            ),
            Node(
                package="pawai_brain",
                executable="conversation_graph_node",
                name="conversation_graph_node",
                output="screen",
                parameters=[{"conversation_engine": role}],
            ),
        ]
    )
```

- [ ] **Step 3: Build and run**

```
colcon build --packages-select pawai_brain
source install/setup.zsh
ros2 launch pawai_brain pawai_conversation_graph.launch.py
```

In another shell:

```
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"transcript\":\"你好\",\"session_id\":\"shadow-test-1\"}"}'
ros2 topic echo /brain/conversation_trace_shadow
```

Expected: 3 trace messages (input, llm_decision, output) with `engine: "langgraph"` and `session_id: "shadow-test-1"`.

- [ ] **Step 4: Confirm shadow does NOT touch primary topic**

```
ros2 topic echo /brain/chat_candidate &
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"transcript\":\"shadow-only-test\",\"session_id\":\"x\"}"}'
```

Expected: nothing on `/brain/chat_candidate` — only `_shadow` got the message. Kill the `echo` after 5 seconds.

- [ ] **Step 5: Commit**

```
git add pawai_brain
git commit -m "feat(pawai_brain): ROS2 wrapper + launch for shadow conversation graph"
```

---

### Task 13: Wire shadow trace into Studio gateway broadcast

Already done in Cut 1 Task 5 (we added both `_shadow` and primary trace topics to the gateway map). Verify by running shadow + Studio together.

- [ ] **Step 1: Live verify**

Start full demo + shadow:

```
bash scripts/start_full_demo_tmux.sh
ros2 launch pawai_brain pawai_conversation_graph.launch.py &
```

Open Studio, fire a voice utterance, confirm:
- Skill Trace Drawer shows legacy traces (engine=`legacy`)
- Skill Trace Drawer shows shadow traces (engine=`langgraph`)
- ChatPanel main flow unchanged
- Demo recording works

- [ ] **Step 2: If Studio drawer doesn't visibly distinguish engines, add a tiny filter toggle**

In `skill-trace-drawer.tsx` add a 2-button toggle: `legacy | langgraph | both`. State default `both`. Filter the `traces` array on render.

- [ ] **Step 3: Commit any frontend tweaks**

```
git add pawai-studio/frontend
git commit -m "feat(studio): engine filter on conversation trace drawer"
```

---

## Cut 3 — Slim `llm_bridge_node.py` (post-demo, optional)

Pure-module extraction. Behavior must remain identical; existing `pytest speech_processor/test/test_llm_bridge_node.py` is the regression net. Do this only if Cut 1 + Cut 2 demo recording is in the bag.

### Task 14: Create `speech_processor/conversation/` package

**Files (new):**
- `speech_processor/speech_processor/conversation/__init__.py`
- `speech_processor/speech_processor/conversation/memory.py`
- `speech_processor/speech_processor/conversation/validator.py`
- `speech_processor/speech_processor/conversation/repair.py`
- `speech_processor/speech_processor/conversation/llm_client.py`
- `speech_processor/speech_processor/conversation/prompt_builder.py`

- [ ] **Step 1: Create empty package**

```
mkdir -p speech_processor/speech_processor/conversation
touch speech_processor/speech_processor/conversation/__init__.py
```

Verify it gets discovered by `find_packages` in `setup.py`. If `setup.py` lists packages explicitly, append `"speech_processor.conversation"`.

- [ ] **Step 2: colcon sanity build**

```
colcon build --packages-select speech_processor
```

- [ ] **Step 3: Commit**

```
git add speech_processor
git commit -m "feat(speech_processor): scaffold conversation/ subpackage"
```

---

### Task 15: Extract `memory.py` (history merge)

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py` (search for `_remember_turn` and `history`)
- Create: `speech_processor/speech_processor/conversation/memory.py`
- Test: `speech_processor/test/test_conversation_memory.py`

- [ ] **Step 1: Identify the surface**

```
grep -n "_remember_turn\|self\.history\|conversation_history" speech_processor/speech_processor/llm_bridge_node.py
```

Note the lines.

- [ ] **Step 2: Move to module**

Cut `_remember_turn` body and `history` data structure into `conversation/memory.py` as a `ConversationMemory` class with methods `record_turn(user, assistant)` and `recent_messages(n) -> list[dict]`. Pure Python, no rclpy.

- [ ] **Step 3: Replace in node**

In `LlmBridgeNode.__init__`, instantiate `self._memory = ConversationMemory(max_turns=self.history_max_turns)`. Replace direct list access with `self._memory.record_turn(...)` and `self._memory.recent_messages(self.history_max_turns)`.

- [ ] **Step 4: Add unit test for `ConversationMemory`**

```python
from speech_processor.conversation.memory import ConversationMemory


def test_memory_keeps_last_n_turns():
    m = ConversationMemory(max_turns=2)
    m.record_turn("u1", "a1")
    m.record_turn("u2", "a2")
    m.record_turn("u3", "a3")
    msgs = m.recent_messages(10)
    assert len(msgs) == 4  # 2 turns × (user + assistant)
    assert msgs[0]["content"] == "u2"
```

- [ ] **Step 5: Run full speech_processor test suite**

```
pytest speech_processor/test -v
```

Expected: all green (existing chat_candidate tests should be unaffected).

- [ ] **Step 6: Commit**

```
git add speech_processor
git commit -m "refactor(llm_bridge): extract ConversationMemory module"
```

---

### Task 16: Extract `validator.py` (JSON parse + schema check + emoji strip)

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py` (`_post_process_reply` and the JSON parse path around `:648`)
- Create: `speech_processor/speech_processor/conversation/validator.py`
- Test: `speech_processor/test/test_conversation_validator.py`

- [ ] **Step 1: Identify the surface**

```
grep -n "_post_process_reply\|EMOJI\|truncat\|parse_llm_response" speech_processor/speech_processor/llm_bridge_node.py
```

- [ ] **Step 2: Move pure functions**

Extract `_post_process_reply`, emoji-strip regex, and any reply truncation guard into `validator.py` as standalone functions:

```python
# conversation/validator.py
import re

_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U0001F600-\U0001F6FF]")


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def is_truncated_at_clause(text: str) -> bool:
    """Heuristic from llm_bridge: reply ending mid-clause is suspect."""
    if not text:
        return False
    return text.rstrip().endswith(("，", ","))


def post_process_reply(text: str, max_chars: int = 80) -> str:
    text = strip_emoji(text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text
```

(Verify against the actual `_post_process_reply` body — copy whatever rules are there. Do not invent new rules.)

- [ ] **Step 3: Replace in node**

```python
from .conversation.validator import post_process_reply, is_truncated_at_clause
```

Replace inline calls.

- [ ] **Step 4: Test**

```python
from speech_processor.conversation.validator import strip_emoji, is_truncated_at_clause, post_process_reply

def test_strip_emoji_removes_smileys():
    assert strip_emoji("你好😀") == "你好"

def test_is_truncated_at_clause_detects_chinese_comma():
    assert is_truncated_at_clause("這是一個很長的回答，")
    assert not is_truncated_at_clause("這是完整的回答。")

def test_post_process_truncates_to_max_chars():
    assert len(post_process_reply("a" * 200, max_chars=20)) == 20
```

- [ ] **Step 5: Run suite + commit**

```
pytest speech_processor/test -v
git add speech_processor
git commit -m "refactor(llm_bridge): extract reply validator module"
```

---

### Task 17: Extract `repair.py` (truncation retry prompt)

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py` (search for retry-on-truncation logic)
- Create: `speech_processor/speech_processor/conversation/repair.py`
- Test: `speech_processor/test/test_conversation_repair.py`

- [ ] **Step 1: Identify**

```
grep -n "retry\|repair\|truncat" speech_processor/speech_processor/llm_bridge_node.py
```

- [ ] **Step 2: Move repair prompt builder**

```python
# conversation/repair.py

REPAIR_INSTRUCTION = (
    "上一輪回覆被截斷了。請重新給一個完整的中文回覆，"
    "結尾必須是句號或問號。維持 PawAI persona 的 JSON 格式。"
)


def build_repair_messages(original_user: str, broken_reply: str) -> list[dict]:
    return [
        {"role": "user", "content": original_user},
        {"role": "assistant", "content": broken_reply},
        {"role": "user", "content": REPAIR_INSTRUCTION},
    ]
```

- [ ] **Step 3: Replace in node and add test**

```python
from speech_processor.conversation.repair import build_repair_messages, REPAIR_INSTRUCTION


def test_repair_messages_includes_instruction_and_history():
    msgs = build_repair_messages("你好", "嗨，")
    assert len(msgs) == 3
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["content"] == "嗨，"
    assert REPAIR_INSTRUCTION in msgs[2]["content"]
```

- [ ] **Step 4: Run + commit**

```
pytest speech_processor/test -v
git add speech_processor
git commit -m "refactor(llm_bridge): extract repair prompt module"
```

---

### Task 18: Extract `llm_client.py` (OpenRouter call + fallback chain)

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:541-690` (`_call_openrouter` and `_try_openrouter_chain`)
- Create: `speech_processor/speech_processor/conversation/llm_client.py`
- Test: `speech_processor/test/test_conversation_llm_client.py`

- [ ] **Step 1: Move both methods**

Lift `_call_openrouter(model, user_message, timeout)` and `_try_openrouter_chain(user_message, total_timeout)` into a stateless `OpenRouterClient` class in `llm_client.py`. Constructor takes `(api_key, primary_model, fallback_model, timeout_s)`. Methods: `call(model, user_message, timeout)` and `call_chain(user_message, total_timeout)`. No rclpy. Use the `requests` import that already exists.

- [ ] **Step 2: Replace in node**

```python
self._llm_client = OpenRouterClient(
    api_key=self._openrouter_key,
    primary_model=self.openrouter_gemini_model,
    fallback_model=self.openrouter_deepseek_model,
    timeout_s=self.openrouter_request_timeout_s,
)
```

Replace `self._call_openrouter(...)` with `self._llm_client.call(...)` etc.

- [ ] **Step 3: Test (mock requests)**

```python
from unittest.mock import patch, Mock
from speech_processor.conversation.llm_client import OpenRouterClient


def test_call_chain_uses_primary_then_fallback_on_first_failure():
    client = OpenRouterClient("k", "primary", "fallback", timeout_s=5.0)
    with patch("speech_processor.conversation.llm_client.requests.post") as post:
        post.side_effect = [
            Mock(status_code=500, text="boom"),  # primary fails
            Mock(status_code=200, json=lambda: {"choices": [{"message": {"content": "{}"}}]}),  # fallback ok
        ]
        result = client.call_chain("hi", total_timeout=10.0)
        assert result is not None
        assert post.call_count == 2
```

- [ ] **Step 4: Run + commit**

```
pytest speech_processor/test -v
git add speech_processor
git commit -m "refactor(llm_bridge): extract OpenRouterClient"
```

---

### Task 19: Extract `prompt_builder.py` (persona load + system prompt)

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:499-525` (persona load) + system prompt assembly site
- Create: `speech_processor/speech_processor/conversation/prompt_builder.py`
- Test: `speech_processor/test/test_conversation_prompt_builder.py`

- [ ] **Step 1: Move**

Extract:
- Persona file load (with fallback to inline `SYSTEM_PROMPT`)
- Function that, given persona + history + current user_text + optional env context, returns the full `messages` list for OpenRouter.

```python
# conversation/prompt_builder.py
from pathlib import Path


def load_persona(path: str | Path | None, inline_fallback: str) -> str:
    if not path:
        return inline_fallback
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8").strip()
    except OSError:
        return inline_fallback
    return text or inline_fallback


def build_messages(persona: str, history: list[dict], user_text: str) -> list[dict]:
    msgs = [{"role": "system", "content": persona}]
    msgs.extend(history)
    msgs.append({"role": "user", "content": user_text})
    return msgs
```

- [ ] **Step 2: Replace in node**

In `__init__`:

```python
from .conversation.prompt_builder import load_persona, build_messages
self._persona = load_persona(self.llm_persona_file, SYSTEM_PROMPT)
```

In the call site:

```python
messages = build_messages(self._persona, self._memory.recent_messages(self.history_max_turns), user_text)
```

- [ ] **Step 3: Test**

```python
from speech_processor.conversation.prompt_builder import load_persona, build_messages

def test_load_persona_falls_back_when_path_missing():
    assert load_persona("/nonexistent/file", "INLINE") == "INLINE"

def test_build_messages_orders_system_history_user(tmp_path):
    msgs = build_messages("PERSONA", [{"role": "user", "content": "x"}], "現在問題")
    assert [m["role"] for m in msgs] == ["system", "user", "user"]
    assert msgs[0]["content"] == "PERSONA"
    assert msgs[-1]["content"] == "現在問題"
```

- [ ] **Step 4: Run + commit**

```
pytest speech_processor/test -v
git add speech_processor
git commit -m "refactor(llm_bridge): extract persona/prompt builder"
```

---

### Task 20: Cut 3 regression check + final commit

- [ ] **Step 1: Full speech_processor + interaction_executive suites**

```
pytest speech_processor/test interaction_executive/test pawai_brain/test -v
```

Expected: every test green, including the original `test_llm_bridge_node.py` (proves zero behavior change).

- [ ] **Step 2: colcon clean build**

```
rm -rf build install log
colcon build
source install/setup.zsh
```

Expected: clean build of every package.

- [ ] **Step 3: Live E2E smoke (Jetson)**

```
bash scripts/start_full_demo_tmux.sh
```

Repeat the Cut 1 Step 3 prompts ("你是誰" / "你還好嗎" / "跳舞"). Behavior must be identical to Cut 1 — same chat_candidate fields, same proposals, same traces.

- [ ] **Step 4: Update memory + status**

Append to `references/project-status.md` a short note: "Phase 0.5 Conversation Engine landed: chat_candidate proposal contract + brain allowlist gate + pawai_brain shadow + llm_bridge slimmed."

```
git add references/project-status.md
git commit -m "docs(status): Phase 0.5 Conversation Engine complete"
```

---

## Self-Review Checklist (run before handing off to executor)

- [ ] Spec §3 model stack → Task 3 syncs both default & tmux override.
- [ ] Spec §4.1 chat_candidate schema → Task 2 emits all four new fields + engine.
- [ ] Spec §4.2 trace topic + status enum → Task 4 emits with correct enum values; Task 7 documents.
- [ ] Spec §6 brain behavior (always reply + allowlist + execute/trace_only) → Task 4 tests cover all four branches (show_status execute, self_introduce trace_only, disallowed rejected, no proposal).
- [ ] Spec §7 pawai_brain shadow with 4 nodes → Tasks 10-12 build it; Task 12 verifies it doesn't publish chat_candidate.
- [ ] Spec §8 llm_bridge slim into 5 modules → Tasks 14-19 (memory/validator/repair/llm_client/prompt_builder).
- [ ] Spec §9 Studio drawer 4 chip states → Task 6 maps statuses to colours.
- [ ] Spec §10 fallbacks → Task 9 documents Jetson dep failure path; Task 12 step 4 confirms shadow isolation; Task 20 confirms zero regression after Cut 3.
- [ ] Spec §13.1 cut order (gate first, shadow second, slim last) → plan ordering matches.
- [ ] No "TBD" / "implement later" / "similar to Task N" patterns.
- [ ] Method names referenced consistently: `_emit_trace`, `_emit_with_cooldown`, `extract_proposal`, `LLM_PROPOSABLE_SKILLS`, `LLM_PROPOSAL_EXECUTE`, `ConversationMemory`, `OpenRouterClient`.
- [ ] Topic names referenced consistently: `/brain/conversation_trace`, `/brain/conversation_trace_shadow`, `/brain/chat_candidate`, `/brain/proposal`.
