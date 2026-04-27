# PawAI Brain Skill-First MVS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PawAI Brain Skill-first MVS — sport `/webrtc_req` 收成 Executive 單一出口、新增 brain_node 純規則仲裁、Studio Chat 升級為 Brain Skill Console，能 demo 7 場景（你好 / 停 / 介紹自己 / wave / 陌生人 3s / 熟人問候 / 跌倒）。

**Architecture:** 3 primitive executors（say/motion/nav）+ 9 semantic skills；brain_node 以純規則仲裁多源事件、發 `/brain/proposal` 給 executive；executive 是唯一 sport `/webrtc_req` publisher；Studio Chat 訂閱 `/state/pawai_brain` 與 `/brain/skill_result` 渲染 8 種 bubble + Skill Buttons + Trace Drawer。

**Tech Stack:** ROS2 Humble (rclpy / std_msgs / go2_interfaces.WebRtcReq) · Python 3.10 · pytest · FastAPI + Pydantic · Next.js 14 (TypeScript) · Zustand · WebSocket。

**Spec:** [`docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md`](../specs/2026-04-27-pawai-brain-skill-first-design.md)

---

## File Structure

### Phase 0（refactor）
- Modify: `speech_processor/speech_processor/llm_bridge_node.py` (+`output_mode` param + brain-mode branches)
- Create: `speech_processor/test/test_tts_audio_api_only.py` (源碼層 grep test)
- Modify: `vision_perception/launch/event_action_bridge.launch.py` (+`enable_event_action_bridge` arg)
- Create: `scripts/start_pawai_brain_tmux.sh`

### Phase 1（Brain MVS 後端）
- Create: `interaction_executive/interaction_executive/skill_contract.py`
- Create: `interaction_executive/interaction_executive/safety_layer.py`
- Create: `interaction_executive/interaction_executive/world_state.py`
- Create: `interaction_executive/interaction_executive/skill_queue.py`
- Create: `interaction_executive/interaction_executive/brain_node.py`
- Create: `interaction_executive/test/test_skill_contract.py`
- Create: `interaction_executive/test/test_safety_layer.py`
- Create: `interaction_executive/test/test_skill_queue.py`
- Create: `interaction_executive/test/test_brain_rules.py`
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py` (rewrite — subscribe `/brain/proposal`, dispatch say/motion/nav, publish `/brain/skill_result` and `/state/pawai_brain`)
- Modify: `interaction_executive/setup.py` (+brain_node entry_point)
- Modify: `interaction_executive/launch/interaction_executive.launch.py` (+brain_node)
- Modify: `interaction_executive/config/executive.yaml` (+brain params)
- Don't touch: `interaction_executive/interaction_executive/state_machine.py`

### Phase 2（Studio Brain Skill Console）
- Modify: `pawai-studio/backend/schemas.py` (+6 Pydantic models)
- Modify: `pawai-studio/gateway/studio_gateway.py` (+TOPIC_MAP entries, +2 publishers, +2 REST routes)
- Modify: `pawai-studio/backend/mock_server.py` (+/api/skill_request, +/api/text_input, +mock WS payloads)
- Modify: `pawai-studio/frontend/contracts/types.ts` (mirror schemas)
- Modify: `pawai-studio/frontend/stores/state-store.ts` (PawAIBrainState + 2 ring buffers)
- Modify: `pawai-studio/frontend/hooks/use-event-stream.ts` (3 new event dispatchers)
- Create: `pawai-studio/frontend/components/chat/brain-status-strip.tsx`
- Create: `pawai-studio/frontend/components/chat/skill-buttons.tsx`
- Create: `pawai-studio/frontend/components/chat/skill-trace-drawer.tsx`
- Create: `pawai-studio/frontend/components/chat/bubble-brain-plan.tsx`
- Create: `pawai-studio/frontend/components/chat/bubble-skill-step.tsx`
- Create: `pawai-studio/frontend/components/chat/bubble-safety.tsx`
- Create: `pawai-studio/frontend/components/chat/bubble-alert.tsx`
- Create: `pawai-studio/frontend/components/chat/bubble-skill-result.tsx`
- Modify: `pawai-studio/frontend/components/chat/chat-panel.tsx` (rewrite ChatMessage union + integrate)

---

## Phase 0 — Action Outlet Refactor

### Task 0.1: Add `output_mode` parameter to llm_bridge_node

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py` (param declaration + read; **actual method names**: `_declare_parameters` at line 160, `_read_parameters` at line 185 — NOT `_load_parameters`)

- [ ] **Step 1: Add param declaration**

In `_declare_parameters()` add line after `self.declare_parameter("subscribe_face", True)` (current last line at ~183):

```python
        self.declare_parameter("output_mode", "legacy")  # "legacy" | "brain"
        self.declare_parameter("chat_candidate_topic", "/brain/chat_candidate")
```

- [ ] **Step 2: Read param in `_read_parameters`**

After `self.subscribe_face = _bool("subscribe_face")` in `_read_parameters` (line 214) add:

```python
        self.output_mode = _str("output_mode").strip().lower()
        if self.output_mode not in ("legacy", "brain"):
            self.get_logger().warn(f"unknown output_mode={self.output_mode!r}, falling back to legacy")
            self.output_mode = "legacy"
        self.chat_candidate_topic = _str("chat_candidate_topic")
        self.get_logger().info(f"llm_bridge output_mode={self.output_mode}")
```

- [ ] **Step 3: Smoke build**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select speech_processor --symlink-install
source install/setup.zsh
# Sanity: node starts and reads param without error
ros2 run speech_processor llm_bridge_node --ros-args -p output_mode:=brain &
PID=$!
sleep 2
ros2 param get /llm_bridge_node output_mode
kill $PID
```

Expected: prints `String value is: brain`.

- [ ] **Step 4: Commit**

```bash
git add speech_processor/speech_processor/llm_bridge_node.py
git commit -m "feat(llm_bridge): add output_mode param (legacy|brain) for Brain MVS refactor"
```

---

### Task 0.2: Brain-mode output gate — publish ONLY `/brain/chat_candidate`

**Critical**: brain-mode must close BOTH decision sites:
- `_dispatch` (LLM success path)
- `_rule_fallback` (fast-path AND LLM-failure-fallback path)

If either path leaks `_send_tts()` or `_send_action()` in brain mode, the safety boundary breaks. We thread `session_id` + `confidence` through the call chain so both decision sites have what they need to emit chat_candidate.

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py` (publisher, signatures, decision-site gate, helper method)

- [ ] **Step 1: Add `chat_candidate` publisher in `__init__`**

After the existing publisher block (around line 112, immediately after the `if WebRtcReq is not None ... else: self.action_pub = None` clause), add:

```python
        # /brain/chat_candidate publisher (always created; only used when output_mode=="brain")
        self.chat_candidate_pub = self.create_publisher(
            String, self.chat_candidate_topic, 10
        )
```

- [ ] **Step 2: Plumb `session_id` through `_call_llm_and_act` signature**

Find the existing definition (around line 336):

```python
    def _call_llm_and_act(
        self,
        user_message: str,
        fallback_intent: str,
        source: str,
        face_name: str | None = None,
        confidence: float = 0.0,
    ) -> None:
```

Append `session_id`:

```python
    def _call_llm_and_act(
        self,
        user_message: str,
        fallback_intent: str,
        source: str,
        face_name: str | None = None,
        confidence: float = 0.0,
        session_id: str | None = None,
    ) -> None:
```

- [ ] **Step 3: Update `_call_llm_and_act` internal calls to pass session_id + confidence + intent**

Inside `_call_llm_and_act`, find the two `self._rule_fallback(...)` calls (fast-path around line 370, fallback around line 390) and the one `self._dispatch(result, source)` call (line 385). Update them:

```python
            # Fast path: high-confidence known intents skip LLM entirely
            if (
                not self.force_fallback
                and fallback_intent in self.FAST_PATH_INTENTS
                and confidence >= self.FAST_PATH_MIN_CONFIDENCE
                and source == "speech"
            ):
                self.get_logger().info(
                    f"Fast path: intent={fallback_intent} conf={confidence:.2f}, skipping LLM"
                )
                self._rule_fallback(fallback_intent, source, face_name,
                                    session_id=session_id, confidence=confidence)
                return
```

```python
            if result is not None:
                self._dispatch(result, source,
                               session_id=session_id, confidence=confidence,
                               fallback_intent=fallback_intent)
            elif self.enable_fallback:
                self.get_logger().info(
                    f"LLM failed, falling back to RuleBrain (intent={fallback_intent})"
                )
                self._rule_fallback(fallback_intent, source, face_name,
                                    session_id=session_id, confidence=confidence)
```

- [ ] **Step 4: Update `_on_speech_event` call site to pass session_id**

In `_on_speech_event` around line 253, change:

```python
        self._executor.submit(
            self._call_llm_and_act, user_message, intent, "speech", None, confidence
        )
```

to:

```python
        self._executor.submit(
            self._call_llm_and_act, user_message, intent, "speech", None, confidence, session_id
        )
```

(Face triggers don't need session_id — they don't emit chat_candidate.)

- [ ] **Step 5: Extend `_dispatch` signature**

Find `_dispatch` (line 472) and change signature:

```python
    def _dispatch(
        self,
        result: dict,
        source: str,
        session_id: str | None = None,
        confidence: float = 0.0,
        fallback_intent: str = "",
    ) -> None:
```

- [ ] **Step 6: Insert brain-mode gate at top of `_dispatch` (after safety filtering)**

Locate the line `self.last_error = ""` (around line 509, end of safety/skill filtering). Insert AFTER it (so banned_api / unknown skill gating still runs, then brain mode short-circuits):

```python
        self.last_trigger = source
        self.last_intent = intent
        self.last_reply = reply_text
        self.last_skill = selected_skill or ""
        self.last_error = ""

        self.get_logger().info(
            f"LLM decision: intent={intent} skill={selected_skill} "
            f"reply={reply_text!r} reason={reasoning}"
        )

        # ── Brain-mode output gate ───────────────────────────────────
        if self.output_mode == "brain":
            if source == "speech":
                self._emit_chat_candidate(
                    session_id=session_id or "",
                    reply_text=reply_text,
                    intent=intent,
                    selected_skill=selected_skill,
                    confidence=confidence,
                )
            # face/state-triggered LLM responses are silently dropped in brain mode;
            # Brain owns face → greet_known_person via its own face rule.
            return
        # ── legacy mode below (unchanged) ────────────────────────────
```

(Keep the existing `ACTION_ONLY_SKILLS` block + `_send_tts` + `_send_action` calls AFTER this gate; they only run in legacy mode now.)

- [ ] **Step 7: Extend `_rule_fallback` signature**

Find `_rule_fallback` (line 539) and change signature:

```python
    def _rule_fallback(
        self,
        intent: str,
        source: str,
        face_name: str | None = None,
        session_id: str | None = None,
        confidence: float = 0.0,
    ) -> None:
```

- [ ] **Step 8: Insert brain-mode gate in `_rule_fallback` (after computing reply + skill)**

Locate the line `self.last_error = "fallback"` (around line 552, end of state set). Insert AFTER it:

```python
        self.last_trigger = source
        self.last_intent = intent
        self.last_reply = reply
        self.last_skill = skill or ""
        self.last_error = "fallback"

        self.get_logger().info(
            f"RuleBrain fallback: intent={intent} skill={skill} reply={reply!r}"
        )

        # ── Brain-mode output gate ───────────────────────────────────
        if self.output_mode == "brain":
            if source == "speech":
                self._emit_chat_candidate(
                    session_id=session_id or "",
                    reply_text=reply,
                    intent=intent,
                    selected_skill=skill,
                    confidence=confidence,
                )
            return
        # ── legacy mode below (unchanged) ────────────────────────────
```

(Keep the existing `ACTION_ONLY_INTENTS` block + `_send_tts` + `_send_action` calls AFTER this gate.)

- [ ] **Step 9: Add `_emit_chat_candidate` helper**

Add new method (place near `_send_tts` / `_send_action`, around line 573):

```python
    # ── Brain mode output ────────────────────────────────────────────
    def _emit_chat_candidate(
        self,
        session_id: str,
        reply_text: str,
        intent: str,
        selected_skill: str | None,
        confidence: float,
    ) -> None:
        """Brain-mode output: publish reply for Brain to consume.

        selected_skill is diagnostic only — Brain MVS only uses reply_text.
        Empty reply_text is allowed; Brain will fall through to its
        chat_candidate timeout (say_canned).
        """
        payload = {
            "session_id": session_id,
            "reply_text": reply_text,
            "intent": intent,
            "selected_skill": selected_skill,
            "source": "llm_bridge",
            "confidence": float(confidence),
            "created_at": time.time(),
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.chat_candidate_pub.publish(msg)
        self.get_logger().info(
            f"Published /brain/chat_candidate: session={session_id} reply={reply_text!r}"
        )
```

- [ ] **Step 10: Update `_publish_state` for observability (optional but recommended)**

Find `_publish_state` and add `"output_mode": self.output_mode` to the published JSON.

- [ ] **Step 11: Build & syntax check**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select speech_processor --symlink-install
python3 -m py_compile speech_processor/speech_processor/llm_bridge_node.py
```

Expected: build success.

- [ ] **Step 12: Negative smoke — brain mode must NOT publish /tts or /webrtc_req**

```bash
source install/setup.zsh
ros2 run speech_processor llm_bridge_node --ros-args -p output_mode:=brain -p force_fallback:=true &
LLM_PID=$!
sleep 3

# Background-watch /tts and /webrtc_req for 5 seconds — both should stay silent
( timeout 5 ros2 topic echo /tts > /tmp/tts_brain.log 2>&1 ) &
( timeout 5 ros2 topic echo /webrtc_req > /tmp/webrtc_brain.log 2>&1 ) &

# Trigger fast-path (rule_fallback path)
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"greet\",\"text\":\"你好\",\"session_id\":\"neg1\",\"confidence\":0.95}"}'
sleep 1
# Trigger normal LLM path (force_fallback=true → also rule_fallback)
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"chat\",\"text\":\"今天天氣\",\"session_id\":\"neg2\",\"confidence\":0.5}"}'
sleep 1
# Trigger ACTION_ONLY (stop) — must also be gated
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"stop\",\"text\":\"停\",\"session_id\":\"neg3\",\"confidence\":0.95}"}'

wait
kill $LLM_PID 2>/dev/null

echo "=== /tts emissions (must be empty) ==="
wc -l /tmp/tts_brain.log
echo "=== /webrtc_req emissions (must be empty) ==="
wc -l /tmp/webrtc_brain.log
```

Expected: `/tmp/tts_brain.log` and `/tmp/webrtc_brain.log` both 0 bytes (or only contain the "WARNING: New publisher discovered" line ≤ 1 line, no actual data frames).

- [ ] **Step 13: Positive smoke — chat_candidate fired for all three paths**

```bash
ros2 run speech_processor llm_bridge_node --ros-args -p output_mode:=brain -p force_fallback:=true &
LLM_PID=$!
sleep 3
( timeout 8 ros2 topic echo /brain/chat_candidate > /tmp/cc.log 2>&1 ) &

ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"greet\",\"text\":\"你好\",\"session_id\":\"pos1\",\"confidence\":0.95}"}'
sleep 1
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"chat\",\"text\":\"今天天氣\",\"session_id\":\"pos2\",\"confidence\":0.5}"}'
sleep 1
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"stop\",\"text\":\"停\",\"session_id\":\"pos3\",\"confidence\":0.95}"}'
sleep 2
wait
kill $LLM_PID 2>/dev/null

echo "=== chat_candidate emissions (expect 3) ==="
grep -c '"session_id":' /tmp/cc.log
grep '"session_id":' /tmp/cc.log
```

Expected: 3 candidate emissions, with session_ids `pos1` / `pos2` / `pos3`.

- [ ] **Step 14: Verify legacy mode unchanged**

```bash
ros2 run speech_processor llm_bridge_node --ros-args -p force_fallback:=true &
LLM_PID=$!
sleep 3
( timeout 5 ros2 topic echo /tts > /tmp/tts_legacy.log 2>&1 ) &
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"greet\",\"text\":\"你好\",\"session_id\":\"leg1\",\"confidence\":0.95}"}'
wait
kill $LLM_PID 2>/dev/null
grep -c "data:" /tmp/tts_legacy.log
```

Expected: ≥ 1 emission on `/tts` (legacy preserved).

- [ ] **Step 15: Commit**

```bash
git add speech_processor/speech_processor/llm_bridge_node.py
git commit -m "feat(llm_bridge): brain mode emits chat_candidate at BOTH decision sites

- Plumb session_id + confidence through _call_llm_and_act → _dispatch / _rule_fallback
- Gate output at end of _dispatch (LLM success) and _rule_fallback (fast-path + LLM-fail)
- Both gates short-circuit BEFORE _send_tts / _send_action calls
- Face/state-triggered LLM is silently dropped in brain mode (Brain owns face rule)
- Empty reply_text is allowed; Brain falls through to say_canned timeout
- Legacy mode unchanged"
```

---

### Task 0.3: Add tts_node audio-api source guard test

**Files:**
- Create: `speech_processor/test/test_tts_audio_api_only.py`

- [ ] **Step 1: Write the test**

```python
"""Source-level guard: tts_node may only emit WebRtcReq with audio api_ids.

If tts_node ever publishes a sport api_id, this test catches it before runtime.
Allowed audio api_ids: Megaphone enter (4001), upload (4003), exit (4002), cleanup (4004).
"""
import re
from pathlib import Path

ALLOWED_AUDIO_API_IDS = {4001, 4002, 4003, 4004}
TTS_NODE = Path(__file__).resolve().parents[1] / "speech_processor" / "tts_node.py"


def test_tts_node_only_uses_audio_api_ids():
    assert TTS_NODE.exists(), f"tts_node.py not found at {TTS_NODE}"
    src = TTS_NODE.read_text(encoding="utf-8")

    # Match patterns like "api_id = 4001", "api_id=4001", "api_id: 4001", "WebRtcReq(api_id=4001"
    pattern = re.compile(r"api_id\s*[:=]\s*(\d+)")
    found = {int(m.group(1)) for m in pattern.finditer(src)}

    if not found:
        # No literal api_id assignments — fine, tts_node may use named constants
        return

    illegal = found - ALLOWED_AUDIO_API_IDS
    assert not illegal, (
        f"tts_node.py uses non-audio api_id(s) {sorted(illegal)}; "
        f"only audio Megaphone api_ids {sorted(ALLOWED_AUDIO_API_IDS)} are allowed. "
        "Sport actions must be dispatched by interaction_executive_node."
    )
```

- [ ] **Step 2: Run test**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest speech_processor/test/test_tts_audio_api_only.py -v
```

Expected: PASS（tts_node 目前只用 4001-4004）。

- [ ] **Step 3: Commit**

```bash
git add speech_processor/test/test_tts_audio_api_only.py
git commit -m "test(tts): guard tts_node uses only audio api_ids 4001-4004"
```

---

### Task 0.4: Add `enable_event_action_bridge` launch arg

**Files:**
- Modify: `vision_perception/launch/event_action_bridge.launch.py`

- [ ] **Step 1: Inspect current launch file**

```bash
cat /home/roy422/newLife/elder_and_dog/vision_perception/launch/event_action_bridge.launch.py
```

- [ ] **Step 2: Wrap node launch with condition**

Edit the launch file to gate the node behind a launch arg:

```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    enable_arg = DeclareLaunchArgument(
        "enable_event_action_bridge",
        default_value="true",
        description="Set false to disable in PawAI Brain MVS launches.",
    )
    bridge_node = Node(
        package="vision_perception",
        executable="event_action_bridge",
        name="event_action_bridge",
        output="screen",
        condition=IfCondition(LaunchConfiguration("enable_event_action_bridge")),
    )
    return LaunchDescription([enable_arg, bridge_node])
```

- [ ] **Step 3: Smoke test both modes**

```bash
colcon build --packages-select vision_perception --symlink-install
source install/setup.zsh
# Default — bridge starts
ros2 launch vision_perception event_action_bridge.launch.py &
sleep 2; ros2 node list | grep event_action_bridge && echo OK
killall -9 event_action_bridge 2>/dev/null
# Disabled — bridge does NOT start
ros2 launch vision_perception event_action_bridge.launch.py enable_event_action_bridge:=false &
sleep 2; ros2 node list | grep event_action_bridge && echo "FAIL: should not be running" || echo "OK: not running"
killall -9 event_action_bridge 2>/dev/null
```

- [ ] **Step 4: Commit**

```bash
git add vision_perception/launch/event_action_bridge.launch.py
git commit -m "feat(vision): add enable_event_action_bridge launch arg for Brain MVS"
```

---

### Task 0.5: Phase 0 milestone smoke + WebRtcReq publisher audit

- [ ] **Step 1: Drop the AST audit script (will also be used in Final Verification)**

Create `scripts/audit_webrtc_publishers.py` with the content given in **Final Verification → Option B** (see end of plan). At Phase 0 the whitelist is the same (interaction_executive_node will be rewritten in Phase 1 but already exists; tts_node is unchanged). Running it now catches any regression from Phase 0 changes:

```bash
cd /home/roy422/newLife/elder_and_dog
python3 scripts/audit_webrtc_publishers.py
```

Expected after Phase 0: `OK · only whitelisted files publish WebRtcReq` — confirms `llm_bridge_node.py` is no longer reachable as a sport publisher in brain mode (the publisher object still exists for legacy mode; this audit is **source-level structural** and at Phase 0 it will still flag llm_bridge as a violation because the `self.action_pub = self.create_publisher(WebRtcReq, ...)` line still exists).

**Phase 0 transitional behaviour**: in legacy mode `action_pub` is needed; in brain mode it's never used. To resolve the audit cleanly at Phase 0, **wrap the publisher creation behind an `output_mode == "legacy"` check**. Update `__init__` block in `llm_bridge_node.py` (around line 107) from:

```python
        if WebRtcReq is not None and self.enable_actions:
            self.action_pub = self.create_publisher(
                WebRtcReq, "/webrtc_req", 10
            )
        else:
            self.action_pub = None
```

to:

```python
        if WebRtcReq is not None and self.enable_actions and self.output_mode == "legacy":
            self.action_pub = self.create_publisher(
                WebRtcReq, "/webrtc_req", 10
            )
        else:
            self.action_pub = None
```

Now run audit again with both modes and confirm:

```bash
# Legacy mode boots → action_pub created → audit flags llm_bridge (expected, legacy)
# Brain mode boots → action_pub == None → no publisher → AST still sees the line!
```

Important caveat: AST audit is **static**, it sees the source line regardless of runtime branching. So Phase 0 audit will list `llm_bridge_node.py` as a "potential" publisher. Add `llm_bridge_node.py` to the whitelist with a comment `# legacy mode only; gated by output_mode=="legacy"`, then **remove from whitelist** at end of Phase 1 once Brain MVS is verified working and we flip the default to brain mode (or delete the legacy branch entirely).

Update `audit_webrtc_publishers.py` WHITELIST for Phase 0/1 transition:

```python
WHITELIST = {
    "interaction_executive/interaction_executive/interaction_executive_node.py",
    "speech_processor/speech_processor/tts_node.py",
    # Phase 0/1 transitional — remove when default flips to brain mode
    "speech_processor/speech_processor/llm_bridge_node.py",
}
```

- [ ] **Step 2: Run existing e2e (legacy mode default unchanged)**

```bash
cd /home/roy422/newLife/elder_and_dog
bash scripts/start_llm_e2e_tmux.sh
# Send a probe utterance; verify TTS plays. Kill afterwards.
```

Expected: 既有聊天 e2e 仍正常（legacy mode default 沒被破壞）。

- [ ] **Step 3: Commit audit script**

```bash
git add scripts/audit_webrtc_publishers.py
git commit -m "chore(audit): AST-based WebRtcReq publisher audit (Brain MVS gate)"
```

- [ ] **Step 4: Tag Phase 0 done**

```bash
git tag pawai-brain-phase0-done
```

---

## Phase 1 — Brain MVS Backend

### Task 1.1: Create skill_contract.py — types

**Files:**
- Create: `interaction_executive/interaction_executive/skill_contract.py`

- [ ] **Step 1: Write types + enums**

```python
"""Skill-first PawAI Brain core types.

Spec: docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md §3
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Literal


# ── Executor kinds ───────────────────────────────────────────
class ExecutorKind(str, Enum):
    SAY = "say"
    MOTION = "motion"
    NAV = "nav"


# ── Priority class ───────────────────────────────────────────
class PriorityClass(IntEnum):
    SAFETY = 0
    ALERT = 1
    SEQUENCE = 2
    SKILL = 3
    CHAT = 4


# ── SkillResult lifecycle ────────────────────────────────────
class SkillResultStatus(str, Enum):
    ACCEPTED = "accepted"
    STARTED = "started"
    STEP_STARTED = "step_started"
    STEP_SUCCESS = "step_success"
    STEP_FAILED = "step_failed"
    COMPLETED = "completed"
    ABORTED = "aborted"
    BLOCKED_BY_SAFETY = "blocked_by_safety"


# ── Step / contract / plan / result ──────────────────────────
@dataclass
class SkillStep:
    executor: ExecutorKind
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillContract:
    name: str
    steps: list[SkillStep]
    priority_class: PriorityClass
    safety_requirements: list[str] = field(default_factory=list)
    cooldown_s: float = 0.0
    timeout_s: float = 8.0
    fallback_skill: str | None = None
    description: str = ""
    enabled: bool = True
    args_schema: dict[str, Any] = field(default_factory=dict)
    ui_style: Literal["normal", "alert", "safety"] = "normal"


@dataclass
class SkillPlan:
    plan_id: str
    selected_skill: str
    steps: list[SkillStep]
    reason: str
    source: str
    priority_class: PriorityClass
    session_id: str | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class SkillResult:
    plan_id: str
    step_index: int | None
    status: SkillResultStatus
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


def new_plan_id(prefix: str = "p") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
```

- [ ] **Step 2: Add MOTION_NAME_MAP and BANNED_API_IDS**

Append to the same file:

```python
# ── Motion name → Go2 sport api_id (from go2_robot_sdk ROBOT_CMD) ─
MOTION_NAME_MAP: dict[str, int] = {
    "hello":         1016,
    "stop_move":     1003,
    "sit":           1009,
    "stand":         1004,
    "content":       1020,
    "balance_stand": 1002,
}

# Sport api_ids that must never be dispatched
BANNED_API_IDS: set[int] = {1030, 1031, 1301}  # FrontFlip / FrontJump / Handstand
```

- [ ] **Step 3: Add SKILL_REGISTRY**

Append:

```python
# ── SKILL_REGISTRY (MVS 9 條) ────────────────────────────────
SKILL_REGISTRY: dict[str, SkillContract] = {
    "chat_reply": SkillContract(
        name="chat_reply",
        steps=[SkillStep(ExecutorKind.SAY, {"text": ""})],  # text injected at plan-build
        priority_class=PriorityClass.CHAT,
        description="LLM-sourced free-form chat reply (alias of say).",
        args_schema={"text": "string"},
        ui_style="normal",
    ),
    "say_canned": SkillContract(
        name="say_canned",
        steps=[SkillStep(ExecutorKind.SAY, {"text": ""})],
        priority_class=PriorityClass.CHAT,
        description="Brain rule fallback canned line (alias of say).",
        args_schema={"text": "string"},
        ui_style="normal",
    ),
    "stop_move": SkillContract(
        name="stop_move",
        steps=[SkillStep(ExecutorKind.MOTION, {"name": "stop_move"})],
        priority_class=PriorityClass.SAFETY,
        description="Emergency stop. Hard-rule path; bypasses sequence preemption guard.",
        ui_style="safety",
    ),
    "acknowledge_gesture": SkillContract(
        name="acknowledge_gesture",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "content"}),
            SkillStep(ExecutorKind.SAY, {"text": "收到"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=3.0,
        description="Generic gesture acknowledgement (wave/ok/thumbs_up).",
        args_schema={"gesture": "string"},
    ),
    "greet_known_person": SkillContract(
        name="greet_known_person",
        steps=[
            SkillStep(ExecutorKind.SAY, {"text_template": "歡迎回來，{name}"}),
            SkillStep(ExecutorKind.MOTION, {"name": "hello"}),
        ],
        priority_class=PriorityClass.SKILL,
        cooldown_s=20.0,  # per-name cooldown computed by Brain
        description="Personalised greeting for a registered face.",
        args_schema={"name": "string"},
    ),
    "self_introduce": SkillContract(
        name="self_introduce",
        steps=[
            SkillStep(ExecutorKind.SAY,    {"text": "我是 PawAI，你的居家互動機器狗"}),
            SkillStep(ExecutorKind.MOTION, {"name": "hello"}),
            SkillStep(ExecutorKind.SAY,    {"text": "平常我會待在你身邊，等你叫我"}),
            SkillStep(ExecutorKind.MOTION, {"name": "sit"}),
            SkillStep(ExecutorKind.SAY,    {"text": "你可以用聲音、手勢，或直接跟我互動"}),
            SkillStep(ExecutorKind.MOTION, {"name": "content"}),
            SkillStep(ExecutorKind.SAY,    {"text": "我也會注意周圍發生的事情"}),
            SkillStep(ExecutorKind.MOTION, {"name": "stand"}),
            SkillStep(ExecutorKind.SAY,    {"text": "如果看到陌生人，我會提醒你提高注意"}),
            SkillStep(ExecutorKind.MOTION, {"name": "balance_stand"}),
        ],
        priority_class=PriorityClass.SEQUENCE,
        cooldown_s=60.0,
        timeout_s=60.0,
        description="6-segment self-introduction wow moment.",
    ),
    "stranger_alert": SkillContract(
        name="stranger_alert",
        steps=[SkillStep(ExecutorKind.SAY, {"text": "偵測到不認識的人，請注意"})],
        priority_class=PriorityClass.ALERT,
        cooldown_s=30.0,
        description="Unknown face stable for 3s. MVS: say only (no motion).",
        ui_style="alert",
    ),
    "fallen_alert": SkillContract(
        name="fallen_alert",
        steps=[
            SkillStep(ExecutorKind.MOTION, {"name": "stop_move"}),
            SkillStep(ExecutorKind.SAY,    {"text": "偵測到有人跌倒，請確認是否需要協助"}),
        ],
        priority_class=PriorityClass.ALERT,
        cooldown_s=15.0,
        description="Human fallen detected. stop_move stops the dog itself; no balance_stand.",
        ui_style="alert",
    ),
    "go_to_named_place": SkillContract(
        name="go_to_named_place",
        steps=[SkillStep(ExecutorKind.NAV, {"action": "goto_named", "args": {}})],
        priority_class=PriorityClass.SKILL,
        description="Navigate to a named pose. Disabled in MVS (nav KPI pending).",
        enabled=False,
        args_schema={"place_id": "string"},
    ),
}
```

- [ ] **Step 4: Add helper to build SkillPlan from registry**

Append:

```python
def build_plan(skill_name: str, args: dict[str, Any] | None = None,
               source: str = "rule", reason: str = "",
               session_id: str | None = None) -> SkillPlan:
    """Resolve template args and instantiate a SkillPlan from SKILL_REGISTRY."""
    args = args or {}
    contract = SKILL_REGISTRY[skill_name]
    if not contract.enabled:
        raise ValueError(f"Skill {skill_name!r} is disabled")
    resolved_steps: list[SkillStep] = []
    for step in contract.steps:
        new_args = dict(step.args)
        # template substitution
        for key in list(new_args.keys()):
            if key.endswith("_template") and isinstance(new_args[key], str):
                target_key = key[:-len("_template")]
                try:
                    new_args[target_key] = new_args.pop(key).format(**args)
                except KeyError:
                    new_args[target_key] = new_args.pop(key)
        # special-case: chat_reply / say_canned receive {text} via args
        if contract.name in ("chat_reply", "say_canned") and "text" in args:
            new_args["text"] = args["text"]
        resolved_steps.append(SkillStep(step.executor, new_args))
    return SkillPlan(
        plan_id=new_plan_id(),
        selected_skill=skill_name,
        steps=resolved_steps,
        reason=reason or f"build_plan:{skill_name}",
        source=source,
        priority_class=contract.priority_class,
        session_id=session_id,
    )
```

- [ ] **Step 5: Quick syntax check**

```bash
python3 -m py_compile interaction_executive/interaction_executive/skill_contract.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add interaction_executive/interaction_executive/skill_contract.py
git commit -m "feat(brain): add skill_contract.py with SKILL_REGISTRY, MOTION_NAME_MAP, build_plan"
```

---

### Task 1.2: Test skill_contract

**Files:**
- Create: `interaction_executive/test/test_skill_contract.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for skill_contract.py — registry shape, build_plan, template resolution."""
import pytest

from interaction_executive.skill_contract import (
    BANNED_API_IDS, MOTION_NAME_MAP, SKILL_REGISTRY,
    ExecutorKind, PriorityClass, SkillPlan, build_plan,
)


def test_registry_has_nine_entries():
    assert len(SKILL_REGISTRY) == 9


def test_required_skills_present():
    expected = {
        "chat_reply", "say_canned", "stop_move", "acknowledge_gesture",
        "greet_known_person", "self_introduce", "stranger_alert",
        "fallen_alert", "go_to_named_place",
    }
    assert set(SKILL_REGISTRY.keys()) == expected


def test_self_introduce_has_ten_steps():
    plan = build_plan("self_introduce")
    assert len(plan.steps) == 10
    assert plan.priority_class == PriorityClass.SEQUENCE


def test_greet_known_person_template_resolves():
    plan = build_plan("greet_known_person", args={"name": "alice"})
    assert plan.steps[0].executor == ExecutorKind.SAY
    assert plan.steps[0].args["text"] == "歡迎回來，alice"
    assert plan.steps[1].executor == ExecutorKind.MOTION
    assert plan.steps[1].args["name"] == "hello"


def test_chat_reply_text_injection():
    plan = build_plan("chat_reply", args={"text": "你好啊"}, source="llm_bridge")
    assert plan.steps[0].args["text"] == "你好啊"
    assert plan.priority_class == PriorityClass.CHAT


def test_say_canned_text_injection():
    plan = build_plan("say_canned", args={"text": "我聽不太懂"})
    assert plan.steps[0].args["text"] == "我聽不太懂"


def test_stranger_alert_no_motion():
    plan = build_plan("stranger_alert")
    assert all(s.executor == ExecutorKind.SAY for s in plan.steps)
    assert plan.priority_class == PriorityClass.ALERT


def test_fallen_alert_uses_stop_move_not_balance_stand():
    plan = build_plan("fallen_alert")
    motion_steps = [s for s in plan.steps if s.executor == ExecutorKind.MOTION]
    assert len(motion_steps) == 1
    assert motion_steps[0].args["name"] == "stop_move"
    # explicitly forbid balance_stand here
    for s in plan.steps:
        if s.executor == ExecutorKind.MOTION:
            assert s.args["name"] != "balance_stand"


def test_go_to_named_place_disabled():
    contract = SKILL_REGISTRY["go_to_named_place"]
    assert contract.enabled is False
    with pytest.raises(ValueError, match="disabled"):
        build_plan("go_to_named_place")


def test_motion_name_map_complete():
    # every motion referenced in registry must exist in MOTION_NAME_MAP
    referenced = set()
    for contract in SKILL_REGISTRY.values():
        for step in contract.steps:
            if step.executor == ExecutorKind.MOTION and "name" in step.args:
                referenced.add(step.args["name"])
    missing = referenced - set(MOTION_NAME_MAP.keys())
    assert not missing, f"missing motion names in MOTION_NAME_MAP: {missing}"


def test_no_banned_api_ids_referenced():
    for name in MOTION_NAME_MAP.values():
        assert name not in BANNED_API_IDS


def test_stop_move_priority_is_safety():
    plan = build_plan("stop_move")
    assert plan.priority_class == PriorityClass.SAFETY
```

- [ ] **Step 2: Run tests**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest interaction_executive/test/test_skill_contract.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/test/test_skill_contract.py
git commit -m "test(brain): cover SKILL_REGISTRY shape, build_plan, template resolution"
```

---

### Task 1.3: Create world_state.py

**Files:**
- Create: `interaction_executive/interaction_executive/world_state.py`

- [ ] **Step 1: Write the module**

```python
"""WorldState — aggregates safety-relevant state from ROS2 topics.

Subscribes to existing publishers (no new state sources):
- /state/tts_playing (Bool, TRANSIENT_LOCAL) — from tts_node
- /state/reactive_stop/status (String JSON, BEST_EFFORT) — from reactive_stop_node
- /state/nav/safety (String JSON, BEST_EFFORT) — from nav_capability state_broadcaster

Spec: docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md §3, §4.4
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field

from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Bool, String


_TRANSIENT_LOCAL = QoSProfile(
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    reliability=QoSReliabilityPolicy.RELIABLE,
)

_BEST_EFFORT = QoSProfile(
    depth=10,
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
)


@dataclass
class WorldStateSnapshot:
    obstacle: bool = False
    emergency: bool = False
    fallen: bool = False
    tts_playing: bool = False
    nav_safe: bool = True
    last_update: float = field(default_factory=time.time)


class WorldState:
    """Thread-safe world-state aggregator. Owned by a Node, but exposes pure snapshot."""

    def __init__(self, node: Node) -> None:
        self._node = node
        self._lock = threading.Lock()
        self._snap = WorldStateSnapshot()

        node.create_subscription(Bool, "/state/tts_playing", self._on_tts, _TRANSIENT_LOCAL)
        node.create_subscription(String, "/state/reactive_stop/status",
                                 self._on_reactive_stop, _BEST_EFFORT)
        node.create_subscription(String, "/state/nav/safety",
                                 self._on_nav_safety, _BEST_EFFORT)

    # ── snapshot ───────────────────────────────────────────
    def snapshot(self) -> WorldStateSnapshot:
        with self._lock:
            return WorldStateSnapshot(
                obstacle=self._snap.obstacle,
                emergency=self._snap.emergency,
                fallen=self._snap.fallen,
                tts_playing=self._snap.tts_playing,
                nav_safe=self._snap.nav_safe,
                last_update=self._snap.last_update,
            )

    def set_fallen(self, value: bool) -> None:
        # Fallen is event-driven (Brain timer sets it from /event/pose_detected)
        with self._lock:
            self._snap.fallen = value
            self._snap.last_update = time.time()

    # ── subscribers ────────────────────────────────────────
    def _on_tts(self, msg: Bool) -> None:
        with self._lock:
            self._snap.tts_playing = bool(msg.data)
            self._snap.last_update = time.time()

    def _on_reactive_stop(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        with self._lock:
            self._snap.obstacle = bool(data.get("obstacle_active", False))
            self._snap.emergency = bool(data.get("emergency", False))
            self._snap.last_update = time.time()

    def _on_nav_safety(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        with self._lock:
            # treat absence of explicit "unsafe" as safe
            self._snap.nav_safe = not bool(data.get("unsafe", False))
            self._snap.last_update = time.time()
```

- [ ] **Step 2: Syntax check**

```bash
python3 -m py_compile interaction_executive/interaction_executive/world_state.py
```

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/interaction_executive/world_state.py
git commit -m "feat(brain): add WorldState aggregator (tts_playing/reactive_stop/nav_safety)"
```

---

### Task 1.4: Create safety_layer.py

**Files:**
- Create: `interaction_executive/interaction_executive/safety_layer.py`

- [ ] **Step 1: Write the module**

```python
"""SafetyLayer — deterministic guards.

- hard_rule: keyword scan on speech transcript → emit stop_move plan immediately
- validate: pre-dispatch precondition check against WorldState
"""
from __future__ import annotations

from dataclasses import dataclass

from .skill_contract import (
    BANNED_API_IDS, MOTION_NAME_MAP, ExecutorKind, SkillPlan, build_plan,
)
from .world_state import WorldStateSnapshot


SAFETY_KEYWORDS_STOP = ("停", "stop", "煞車", "暫停", "緊急")


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


class SafetyLayer:
    """Pure-Python; no ROS2 dependency."""

    def hard_rule(self, transcript: str | None) -> SkillPlan | None:
        if not transcript:
            return None
        text = transcript.strip().lower()
        for kw in SAFETY_KEYWORDS_STOP:
            if kw in text:
                return build_plan(
                    "stop_move",
                    source="rule:safety_keyword",
                    reason=f"keyword:{kw}",
                )
        return None

    def validate(self, plan: SkillPlan, world: WorldStateSnapshot) -> ValidationResult:
        # SAFETY plans bypass requirements (they ARE the safety response)
        from .skill_contract import PriorityClass
        if plan.priority_class == PriorityClass.SAFETY:
            return ValidationResult(True)

        # banned api guard
        for step in plan.steps:
            if step.executor == ExecutorKind.MOTION:
                name = step.args.get("name")
                api_id = MOTION_NAME_MAP.get(name)
                if api_id is None:
                    return ValidationResult(False, f"unknown_motion:{name!r}")
                if api_id in BANNED_API_IDS:
                    return ValidationResult(False, f"banned_api:{api_id}")

        # world-state preconditions
        if world.emergency:
            return ValidationResult(False, "emergency_active")
        # ALERT plans bypass obstacle (they may need to react in obstacle context)
        if plan.priority_class != PriorityClass.ALERT:
            if world.obstacle and any(
                s.executor in (ExecutorKind.MOTION, ExecutorKind.NAV) for s in plan.steps
            ):
                return ValidationResult(False, "obstacle_active")

        return ValidationResult(True)
```

- [ ] **Step 2: Syntax check**

```bash
python3 -m py_compile interaction_executive/interaction_executive/safety_layer.py
```

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/interaction_executive/safety_layer.py
git commit -m "feat(brain): add SafetyLayer with hard_rule keyword scan and validate()"
```

---

### Task 1.5: Test safety_layer

**Files:**
- Create: `interaction_executive/test/test_safety_layer.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for safety_layer.py."""
import pytest

from interaction_executive.safety_layer import SAFETY_KEYWORDS_STOP, SafetyLayer
from interaction_executive.skill_contract import (
    PriorityClass, SkillPlan, build_plan,
)
from interaction_executive.world_state import WorldStateSnapshot


@pytest.fixture
def safety():
    return SafetyLayer()


@pytest.mark.parametrize("kw", list(SAFETY_KEYWORDS_STOP))
def test_hard_rule_hits_each_keyword(safety, kw):
    plan = safety.hard_rule(f"請{kw}一下")
    assert plan is not None
    assert plan.selected_skill == "stop_move"
    assert plan.priority_class == PriorityClass.SAFETY


def test_hard_rule_misses_normal_text(safety):
    assert safety.hard_rule("你好嗎") is None
    assert safety.hard_rule("") is None
    assert safety.hard_rule(None) is None


def test_validate_safety_bypasses_world(safety):
    plan = build_plan("stop_move")
    world = WorldStateSnapshot(obstacle=True, emergency=True)
    res = safety.validate(plan, world)
    assert res.ok


def test_validate_blocks_emergency(safety):
    plan = build_plan("self_introduce")
    world = WorldStateSnapshot(emergency=True)
    res = safety.validate(plan, world)
    assert not res.ok
    assert "emergency" in res.reason


def test_validate_blocks_obstacle_for_motion_skill(safety):
    plan = build_plan("greet_known_person", args={"name": "alice"})
    world = WorldStateSnapshot(obstacle=True)
    res = safety.validate(plan, world)
    assert not res.ok
    assert "obstacle" in res.reason


def test_validate_alert_bypasses_obstacle(safety):
    plan = build_plan("fallen_alert")
    world = WorldStateSnapshot(obstacle=True)
    res = safety.validate(plan, world)
    assert res.ok  # ALERT priority bypasses obstacle


def test_validate_blocks_banned_api(safety, monkeypatch):
    from interaction_executive import skill_contract as sc
    # inject a banned motion in MOTION_NAME_MAP for the duration of this test
    monkeypatch.setitem(sc.MOTION_NAME_MAP, "front_flip", 1030)
    plan = SkillPlan(
        plan_id="t-banned",
        selected_skill="custom",
        steps=[sc.SkillStep(sc.ExecutorKind.MOTION, {"name": "front_flip"})],
        reason="test",
        source="test",
        priority_class=PriorityClass.SKILL,
    )
    res = safety.validate(plan, WorldStateSnapshot())
    assert not res.ok
    assert "banned_api" in res.reason


def test_validate_pass_when_clean(safety):
    plan = build_plan("acknowledge_gesture", args={"gesture": "wave"})
    res = safety.validate(plan, WorldStateSnapshot())
    assert res.ok
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest interaction_executive/test/test_safety_layer.py -v
```

Expected: all PASS（5 keyword + 7 misc = 12 tests）。

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/test/test_safety_layer.py
git commit -m "test(brain): cover SafetyLayer hard_rule + validate (banned/world)"
```

---

### Task 1.6: Create skill_queue.py

**Files:**
- Create: `interaction_executive/interaction_executive/skill_queue.py`

- [ ] **Step 1: Write the module**

```python
"""SkillQueue — Executive's plan queue with preemption support."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from .skill_contract import SkillPlan


@dataclass
class PreemptedPlan:
    plan: SkillPlan
    reason: str


class SkillQueue:
    def __init__(self) -> None:
        self._dq: deque[SkillPlan] = deque()
        self._lock = threading.Lock()

    def push(self, plan: SkillPlan) -> None:
        with self._lock:
            self._dq.append(plan)

    def push_front(self, plan: SkillPlan) -> None:
        with self._lock:
            self._dq.appendleft(plan)

    def peek(self) -> SkillPlan | None:
        with self._lock:
            return self._dq[0] if self._dq else None

    def pop(self) -> SkillPlan | None:
        with self._lock:
            return self._dq.popleft() if self._dq else None

    def clear(self, reason: str = "preempted") -> list[PreemptedPlan]:
        with self._lock:
            preempted = [PreemptedPlan(p, reason) for p in self._dq]
            self._dq.clear()
            return preempted

    def __len__(self) -> int:
        with self._lock:
            return len(self._dq)
```

- [ ] **Step 2: Commit**

```bash
git add interaction_executive/interaction_executive/skill_queue.py
git commit -m "feat(brain): add SkillQueue with preemption support"
```

---

### Task 1.7: Test skill_queue

**Files:**
- Create: `interaction_executive/test/test_skill_queue.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for skill_queue.py."""
from interaction_executive.skill_contract import build_plan
from interaction_executive.skill_queue import SkillQueue


def _plan(name="hello"):
    # use a real registry skill; "stop_move" is fine
    return build_plan("stop_move")


def test_push_pop_fifo():
    q = SkillQueue()
    p1, p2 = _plan(), _plan()
    q.push(p1); q.push(p2)
    assert len(q) == 2
    assert q.pop() is p1
    assert q.pop() is p2
    assert q.pop() is None


def test_push_front_lifo_at_head():
    q = SkillQueue()
    p1, p2 = _plan(), _plan()
    q.push(p1)
    q.push_front(p2)
    assert q.peek() is p2


def test_clear_returns_preempted():
    q = SkillQueue()
    p1, p2 = _plan(), _plan()
    q.push(p1); q.push(p2)
    preempted = q.clear(reason="safety_preempt")
    assert len(preempted) == 2
    assert all(pp.reason == "safety_preempt" for pp in preempted)
    assert len(q) == 0


def test_clear_empty_returns_empty_list():
    q = SkillQueue()
    assert q.clear() == []
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest interaction_executive/test/test_skill_queue.py -v
```

Expected: 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/test/test_skill_queue.py
git commit -m "test(brain): cover SkillQueue push/pop/preempt"
```

---

### Task 1.8: Create brain_node.py — skeleton + subscriptions

**Files:**
- Create: `interaction_executive/interaction_executive/brain_node.py`

- [ ] **Step 1: Write skeleton with subscribers and publishers**

```python
"""brain_node — Skill-first PawAI Brain (pure-rules MVS).

Subscribes to perception events + Studio injection topics, applies rule table,
emits SkillPlan via /brain/proposal, publishes /state/pawai_brain at 2 Hz.

Spec: docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md §6
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String

from .safety_layer import SafetyLayer
from .skill_contract import (
    PriorityClass, SkillPlan, SkillResult, SkillResultStatus, build_plan,
    SKILL_REGISTRY,
)
from .world_state import WorldState


_RELIABLE_10 = QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE)
_TRANSIENT_LOCAL_1 = QoSProfile(
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    reliability=QoSReliabilityPolicy.RELIABLE,
)


@dataclass
class BufferedSpeech:
    session_id: str
    transcript: str
    enqueued_at: float


@dataclass
class BrainInternalState:
    unknown_face_first_seen: float | None = None
    fallen_first_seen: float | None = None
    last_alert_ts: dict[str, float] = field(default_factory=dict)
    last_known_face: dict[str, float] = field(default_factory=dict)  # name → ts
    chat_buffer: dict[str, BufferedSpeech] = field(default_factory=dict)
    dedup_cache: dict[tuple, float] = field(default_factory=dict)
    last_plans: deque = field(default_factory=lambda: deque(maxlen=5))
    active_plan: dict | None = None  # mirror of executive (best-effort)


class BrainNode(Node):

    def __init__(self) -> None:
        super().__init__("brain_node")
        self._declare_params()

        self._lock = threading.Lock()
        self._state = BrainInternalState()
        self._safety = SafetyLayer()
        self._world = WorldState(self)

        # publishers
        self._pub_proposal = self.create_publisher(String, "/brain/proposal", _RELIABLE_10)
        self._pub_brain_state = self.create_publisher(
            String, "/state/pawai_brain", _TRANSIENT_LOCAL_1
        )

        # subscribers — events
        self.create_subscription(String, "/event/speech_intent_recognized",
                                 self._on_speech_intent, _RELIABLE_10)
        self.create_subscription(String, "/event/gesture_detected",
                                 self._on_gesture, _RELIABLE_10)
        self.create_subscription(String, "/event/face_identity",
                                 self._on_face, _RELIABLE_10)
        self.create_subscription(String, "/event/pose_detected",
                                 self._on_pose, _RELIABLE_10)
        self.create_subscription(String, "/event/object_detected",
                                 self._on_object, _RELIABLE_10)

        # subscribers — Brain inputs
        self.create_subscription(String, "/brain/chat_candidate",
                                 self._on_chat_candidate, _RELIABLE_10)
        self.create_subscription(String, "/brain/text_input",
                                 self._on_text_input, _RELIABLE_10)
        self.create_subscription(String, "/brain/skill_request",
                                 self._on_skill_request, _RELIABLE_10)

        # subscribers — feedback from Executive
        self.create_subscription(String, "/brain/skill_result",
                                 self._on_skill_result, _RELIABLE_10)

        # timers
        self._chat_timeouts: dict[str, rclpy.timer.Timer] = {}
        self._brain_state_timer = self.create_timer(0.5, self._publish_brain_state)
        self._dedup_gc_timer = self.create_timer(2.0, self._gc_dedup)

        self.get_logger().info(
            f"brain_node ready · skills={len(SKILL_REGISTRY)} · "
            f"chat_wait={self.chat_wait_ms}ms · dedup={self.dedup_window_s}s"
        )

    # ── params ───────────────────────────────────────────
    def _declare_params(self) -> None:
        self.declare_parameter("chat_wait_ms", 1500)
        self.declare_parameter("dedup_window_s", 1.0)
        self.declare_parameter("unknown_face_accumulate_s", 3.0)
        self.declare_parameter("fallen_accumulate_s", 2.0)
        self.chat_wait_ms = int(self.get_parameter("chat_wait_ms").value)
        self.dedup_window_s = float(self.get_parameter("dedup_window_s").value)
        self.unknown_face_accumulate_s = float(self.get_parameter("unknown_face_accumulate_s").value)
        self.fallen_accumulate_s = float(self.get_parameter("fallen_accumulate_s").value)

    # ── stub callbacks (filled in Task 1.9) ──────────────
    def _on_speech_intent(self, msg: String) -> None: ...
    def _on_gesture(self, msg: String) -> None: ...
    def _on_face(self, msg: String) -> None: ...
    def _on_pose(self, msg: String) -> None: ...
    def _on_object(self, msg: String) -> None: ...
    def _on_chat_candidate(self, msg: String) -> None: ...
    def _on_text_input(self, msg: String) -> None: ...
    def _on_skill_request(self, msg: String) -> None: ...
    def _on_skill_result(self, msg: String) -> None: ...

    def _publish_brain_state(self) -> None: ...
    def _gc_dedup(self) -> None: ...


def main(args=None):
    rclpy.init(args=args)
    node = BrainNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax check**

```bash
python3 -m py_compile interaction_executive/interaction_executive/brain_node.py
```

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/interaction_executive/brain_node.py
git commit -m "feat(brain): brain_node skeleton — subs, pubs, params, internal state"
```

---

### Task 1.9: brain_node — implement rule table + arbitration

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py`

- [ ] **Step 1: Implement helper to emit plan**

Replace the stub block with:

```python
    # ── helpers ──────────────────────────────────────────
    def _emit(self, plan: SkillPlan) -> None:
        msg = String()
        msg.data = json.dumps(self._plan_to_dict(plan), ensure_ascii=False)
        self._pub_proposal.publish(msg)
        self._state.last_plans.appendleft({
            "plan_id": plan.plan_id,
            "selected_skill": plan.selected_skill,
            "source": plan.source,
            "priority": int(plan.priority_class),
            "accepted": True,  # optimistic; updated by skill_result feedback
            "reason": plan.reason,
            "created_at": plan.created_at,
        })
        self.get_logger().info(
            f"PROPOSAL · {plan.selected_skill} · src={plan.source} · "
            f"reason={plan.reason} · prio={plan.priority_class.name}"
        )

    def _plan_to_dict(self, plan: SkillPlan) -> dict:
        return {
            "plan_id": plan.plan_id,
            "selected_skill": plan.selected_skill,
            "steps": [{"executor": s.executor.value, "args": s.args} for s in plan.steps],
            "reason": plan.reason,
            "source": plan.source,
            "priority_class": int(plan.priority_class),
            "session_id": plan.session_id,
            "created_at": plan.created_at,
        }

    def _in_cooldown(self, key: str, cooldown_s: float) -> bool:
        last = self._state.last_alert_ts.get(key)
        if last is None:
            return False
        return (time.time() - last) < cooldown_s

    def _mark_cooldown(self, key: str) -> None:
        self._state.last_alert_ts[key] = time.time()

    def _check_dedup(self, source: str, key: str) -> bool:
        """Return True if within dedup window (caller should drop)."""
        now = time.time()
        bucket_key = (source, key, int(now / self.dedup_window_s))
        with self._lock:
            if bucket_key in self._state.dedup_cache:
                return True
            self._state.dedup_cache[bucket_key] = now
            return False

    def _gc_dedup(self) -> None:
        cutoff = time.time() - 5.0
        with self._lock:
            self._state.dedup_cache = {
                k: ts for k, ts in self._state.dedup_cache.items() if ts > cutoff
            }

    def _has_active_sequence(self) -> bool:
        ap = self._state.active_plan
        if ap is None:
            return False
        return ap.get("priority_class", 99) == int(PriorityClass.SEQUENCE)
```

- [ ] **Step 2: Implement speech intent handler**

Replace `_on_speech_intent` stub with:

```python
    def _on_speech_intent(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        transcript = (payload.get("transcript") or "").strip()
        session_id = str(payload.get("session_id") or "")

        # 1. Safety hard rule
        plan = self._safety.hard_rule(transcript)
        if plan:
            plan.session_id = session_id
            self._emit(plan); return

        # 2. self_introduce keyword
        for kw in ("介紹你自己", "自我介紹", "你是誰"):
            if kw in transcript:
                if not self._in_cooldown("self_introduce", 60.0):
                    p = build_plan("self_introduce",
                                   source="rule:self_introduce_keyword",
                                   reason=f"keyword:{kw}",
                                   session_id=session_id)
                    self._mark_cooldown("self_introduce")
                    self._emit(p)
                return

        # 3. dedup + active sequence guard
        if self._has_active_sequence():
            return  # only SAFETY/ALERT may interrupt; speech-CHAT cannot
        if self._check_dedup("speech", session_id):
            return

        # 4. unmatched → buffer for chat_candidate
        with self._lock:
            self._state.chat_buffer[session_id] = BufferedSpeech(
                session_id=session_id,
                transcript=transcript,
                enqueued_at=time.time(),
            )
        # schedule timeout
        timer = self.create_timer(self.chat_wait_ms / 1000.0,
                                  lambda sid=session_id: self._on_chat_timeout(sid))
        self._chat_timeouts[session_id] = timer

    def _on_chat_timeout(self, session_id: str) -> None:
        timer = self._chat_timeouts.pop(session_id, None)
        if timer is not None:
            self.destroy_timer(timer)
        with self._lock:
            buffered = self._state.chat_buffer.pop(session_id, None)
        if buffered is None:
            return  # already consumed by chat_candidate
        plan = build_plan("say_canned",
                          args={"text": "我聽不太懂"},
                          source="rule:chat_fallback",
                          reason="chat_candidate_timeout",
                          session_id=session_id)
        self._emit(plan)
```

- [ ] **Step 3: Implement chat_candidate handler**

Replace `_on_chat_candidate` stub:

```python
    def _on_chat_candidate(self, msg: String) -> None:
        try:
            cand = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        session_id = str(cand.get("session_id") or "")
        reply_text = (cand.get("reply_text") or "").strip()
        if not reply_text:
            return
        with self._lock:
            buffered = self._state.chat_buffer.pop(session_id, None)
        if buffered is None:
            return  # late arrival; already responded with say_canned
        # Cancel pending timeout
        timer = self._chat_timeouts.pop(session_id, None)
        if timer is not None:
            self.destroy_timer(timer)
        plan = build_plan("chat_reply",
                          args={"text": reply_text},
                          source="llm_bridge",
                          reason="chat_candidate_match",
                          session_id=session_id)
        self._emit(plan)
```

- [ ] **Step 4: Implement gesture handler**

```python
    def _on_gesture(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        gesture = (payload.get("gesture") or "").strip().lower()
        if gesture not in {"wave", "ok", "thumbs_up"}:
            return
        if self._has_active_sequence():
            return
        if self._check_dedup("gesture", gesture):
            return
        if self._in_cooldown("acknowledge_gesture", 3.0):
            return
        plan = build_plan("acknowledge_gesture",
                          args={"gesture": gesture},
                          source="rule:gesture_ack",
                          reason=f"gesture:{gesture}")
        self._mark_cooldown("acknowledge_gesture")
        self._emit(plan)
```

- [ ] **Step 5: Implement face handler (known + alert timer)**

```python
    def _on_face(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        identity = (payload.get("identity") or "").strip()
        stable = bool(payload.get("identity_stable", False))
        if not identity:
            self._state.unknown_face_first_seen = None
            return

        if identity == "unknown":
            now = time.time()
            if self._state.unknown_face_first_seen is None:
                self._state.unknown_face_first_seen = now
            elif (now - self._state.unknown_face_first_seen) >= self.unknown_face_accumulate_s:
                if not self._in_cooldown("stranger_alert", 30.0):
                    plan = build_plan("stranger_alert",
                                      source="rule:unknown_face_3s",
                                      reason="unknown_face_stable_3s")
                    self._mark_cooldown("stranger_alert")
                    self._emit(plan)
                    self._state.unknown_face_first_seen = None
            return

        # known identity → reset unknown timer
        self._state.unknown_face_first_seen = None
        if not stable:
            return
        cooldown_key = f"greet_known_person:{identity}"
        if self._in_cooldown(cooldown_key, 20.0):
            return
        if self._has_active_sequence():
            return
        plan = build_plan("greet_known_person",
                          args={"name": identity},
                          source="rule:known_face",
                          reason=f"identity:{identity}")
        self._mark_cooldown(cooldown_key)
        self._emit(plan)
```

- [ ] **Step 6: Implement pose handler (fallen timer)**

```python
    def _on_pose(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        pose = (payload.get("pose") or "").strip().lower()
        if pose != "fallen":
            self._state.fallen_first_seen = None
            self._world.set_fallen(False)
            return
        now = time.time()
        if self._state.fallen_first_seen is None:
            self._state.fallen_first_seen = now
        elif (now - self._state.fallen_first_seen) >= self.fallen_accumulate_s:
            if not self._in_cooldown("fallen_alert", 15.0):
                plan = build_plan("fallen_alert",
                                  source="rule:pose_fallen_2s",
                                  reason="pose_fallen_stable_2s")
                self._mark_cooldown("fallen_alert")
                self._world.set_fallen(True)
                self._emit(plan)
                self._state.fallen_first_seen = None
```

- [ ] **Step 7: Implement object stub (MVS no-op, structural only)**

```python
    def _on_object(self, msg: String) -> None:
        # MVS: no rule for object events. Reserved for Phase 3 PR integrations.
        pass
```

- [ ] **Step 8: Implement Studio injection handlers**

```python
    def _on_text_input(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        text = (payload.get("text") or "").strip()
        if not text:
            return
        # Repackage as synthetic speech intent and feed through main pipeline
        synthetic = json.dumps({
            "transcript": text,
            "session_id": payload.get("request_id") or f"studio-{int(time.time()*1000)}",
            "intent": "chat",
            "confidence": 1.0,
            "source": "studio_text",
        }, ensure_ascii=False)
        synth_msg = String(); synth_msg.data = synthetic
        self._on_speech_intent(synth_msg)

    def _on_skill_request(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        skill = (payload.get("skill") or "").strip()
        args = payload.get("args") or {}
        if skill not in SKILL_REGISTRY:
            self.get_logger().warn(f"skill_request: unknown skill {skill!r}")
            return
        contract = SKILL_REGISTRY[skill]
        if not contract.enabled:
            self.get_logger().warn(f"skill_request: disabled skill {skill!r}")
            return
        if contract.cooldown_s > 0 and self._in_cooldown(skill, contract.cooldown_s):
            self.get_logger().info(f"skill_request: {skill} in cooldown")
            return
        try:
            plan = build_plan(skill, args=args, source="studio_button",
                              reason=f"studio_request:{skill}")
        except (KeyError, ValueError) as exc:
            self.get_logger().warn(f"skill_request build_plan failed: {exc}")
            return
        if contract.cooldown_s > 0:
            self._mark_cooldown(skill)
        self._emit(plan)
```

- [ ] **Step 9: Implement skill_result feedback consumer + brain_state publisher**

```python
    def _on_skill_result(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        status = payload.get("status")
        plan_id = payload.get("plan_id")
        if status == SkillResultStatus.STARTED.value:
            self._state.active_plan = {
                "plan_id": plan_id,
                "selected_skill": payload.get("selected_skill"),
                "step_index": 0,
                "step_total": payload.get("step_total"),
                "started_at": payload.get("timestamp", time.time()),
                "priority_class": payload.get("priority_class", int(PriorityClass.SKILL)),
            }
        elif status in (SkillResultStatus.STEP_STARTED.value,
                        SkillResultStatus.STEP_SUCCESS.value):
            if self._state.active_plan and self._state.active_plan["plan_id"] == plan_id:
                if payload.get("step_index") is not None:
                    self._state.active_plan["step_index"] = int(payload["step_index"])
        elif status in (SkillResultStatus.COMPLETED.value,
                        SkillResultStatus.ABORTED.value,
                        SkillResultStatus.BLOCKED_BY_SAFETY.value):
            if self._state.active_plan and self._state.active_plan["plan_id"] == plan_id:
                self._state.active_plan = None
            if status == SkillResultStatus.BLOCKED_BY_SAFETY.value:
                # mark recent plan as not-accepted in last_plans
                for entry in self._state.last_plans:
                    if entry["plan_id"] == plan_id:
                        entry["accepted"] = False
                        entry["reason"] = f"{entry['reason']} | blocked:{payload.get('detail','')}"
                        break

    def _publish_brain_state(self) -> None:
        snap = self._world.snapshot()
        ap = self._state.active_plan
        mode = "idle"
        if ap:
            sk = ap.get("selected_skill")
            if sk == "stop_move":
                mode = "safety_stop"
            elif sk in ("stranger_alert", "fallen_alert"):
                mode = "alert"
            elif sk == "self_introduce":
                mode = "sequence"
            elif sk in ("chat_reply", "say_canned"):
                mode = "chat"
            else:
                mode = "skill"
        payload = {
            "timestamp": time.time(),
            "mode": mode,
            "active_plan": ap,
            "active_step": None,  # detailed step echo deferred to Studio bubble stream
            "fallback_active": False,
            "safety_flags": {
                "obstacle": snap.obstacle, "emergency": snap.emergency,
                "fallen": snap.fallen, "tts_playing": snap.tts_playing,
                "nav_safe": snap.nav_safe,
            },
            "cooldowns": dict(self._state.last_alert_ts),
            "last_plans": list(self._state.last_plans),
        }
        msg = String(); msg.data = json.dumps(payload, ensure_ascii=False)
        self._pub_brain_state.publish(msg)
```

- [ ] **Step 10: Build & run smoke**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select interaction_executive --symlink-install
source install/setup.zsh
ros2 run interaction_executive brain_node &
BPID=$!
sleep 2
ros2 topic echo /state/pawai_brain --once
# Send a "stop" intent and observe proposal
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"chat\",\"transcript\":\"停\",\"session_id\":\"smoke\"}"}'
ros2 topic echo /brain/proposal --once
kill $BPID
```

Expected: brain_state JSON appears, proposal shows `selected_skill: "stop_move"`.

- [ ] **Step 11: Commit**

```bash
git add interaction_executive/interaction_executive/brain_node.py
git commit -m "feat(brain): implement brain_node rules + arbitration

- 7 scenarios + chat_candidate buffer (1500ms) + 1s dedup
- studio text/skill_request handlers
- /state/pawai_brain publisher (2 Hz)"
```

---

### Task 1.10: Test brain rules (7 scenarios)

**Files:**
- Create: `interaction_executive/test/test_brain_rules.py`

- [ ] **Step 1: Write isolated rule-logic tests (no ROS2)**

Brain logic relies on rclpy timers; for fast unit testing we will exercise the underlying helpers and key callbacks via direct invocation with a mock node. Create a thin test that imports brain_node lazily.

```python
"""Brain rule logic — 7-scenario coverage. Uses rclpy minimal init.

Run isolated: each test starts/stops a brain_node instance.
"""
import json
import time

import pytest
import rclpy
from std_msgs.msg import String

from interaction_executive.brain_node import BrainNode


@pytest.fixture
def brain():
    rclpy.init()
    node = BrainNode()
    proposals: list[dict] = []
    sub = node.create_subscription(
        String, "/brain/proposal",
        lambda m: proposals.append(json.loads(m.data)),
        10,
    )
    node._captured_proposals = proposals
    yield node
    node.destroy_node()
    rclpy.shutdown()


def _spin(node, seconds: float = 0.3) -> None:
    end = time.time() + seconds
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.05)


def _send(node, topic_pub_helper, topic: str, payload: dict) -> None:
    msg = String(); msg.data = json.dumps(payload, ensure_ascii=False)
    pub = node.create_publisher(String, topic, 10)
    pub.publish(msg)
    _spin(node, 0.1)


def test_scenario_safety_stop(brain):
    _send(brain, None, "/event/speech_intent_recognized",
          {"transcript": "停！", "session_id": "s1", "intent": "chat"})
    _spin(brain, 0.2)
    assert any(p["selected_skill"] == "stop_move" for p in brain._captured_proposals)


def test_scenario_self_introduce(brain):
    _send(brain, None, "/event/speech_intent_recognized",
          {"transcript": "介紹你自己", "session_id": "s2", "intent": "chat"})
    _spin(brain, 0.2)
    assert any(p["selected_skill"] == "self_introduce" for p in brain._captured_proposals)


def test_scenario_chat_fallback_canned(brain):
    _send(brain, None, "/event/speech_intent_recognized",
          {"transcript": "今天的天氣", "session_id": "s3", "intent": "chat"})
    # wait for chat_wait_ms (1500ms) + buffer
    _spin(brain, 1.8)
    canned = [p for p in brain._captured_proposals if p["selected_skill"] == "say_canned"]
    assert canned, "expected say_canned fallback"
    assert canned[-1]["steps"][0]["args"]["text"] == "我聽不太懂"


def test_scenario_chat_candidate_consumed(brain):
    sid = "s4"
    _send(brain, None, "/event/speech_intent_recognized",
          {"transcript": "今天天氣", "session_id": sid, "intent": "chat"})
    _spin(brain, 0.1)
    _send(brain, None, "/brain/chat_candidate",
          {"session_id": sid, "reply_text": "今天很適合散步", "intent": "chat",
           "selected_skill": None, "source": "llm_bridge", "confidence": 0.8})
    _spin(brain, 0.3)
    chat = [p for p in brain._captured_proposals if p["selected_skill"] == "chat_reply"]
    assert chat
    assert chat[-1]["steps"][0]["args"]["text"] == "今天很適合散步"


def test_scenario_gesture_wave(brain):
    _send(brain, None, "/event/gesture_detected",
          {"gesture": "wave", "confidence": 0.9})
    _spin(brain, 0.2)
    assert any(p["selected_skill"] == "acknowledge_gesture"
               for p in brain._captured_proposals)


def test_scenario_known_face(brain):
    _send(brain, None, "/event/face_identity",
          {"identity": "alice", "identity_stable": True})
    _spin(brain, 0.2)
    plans = [p for p in brain._captured_proposals
             if p["selected_skill"] == "greet_known_person"]
    assert plans
    assert "alice" in plans[-1]["steps"][0]["args"]["text"]


def test_scenario_unknown_face_3s_timer(brain):
    # send unknown face every 0.5s for 3.5s
    pub = brain.create_publisher(String, "/event/face_identity", 10)
    end = time.time() + 3.5
    while time.time() < end:
        msg = String(); msg.data = json.dumps({"identity": "unknown"})
        pub.publish(msg); _spin(brain, 0.4)
    plans = [p for p in brain._captured_proposals
             if p["selected_skill"] == "stranger_alert"]
    assert plans, "stranger_alert should fire after >=3s"


def test_scenario_pose_fallen_2s_timer(brain):
    pub = brain.create_publisher(String, "/event/pose_detected", 10)
    end = time.time() + 2.5
    while time.time() < end:
        msg = String(); msg.data = json.dumps({"pose": "fallen"})
        pub.publish(msg); _spin(brain, 0.3)
    plans = [p for p in brain._captured_proposals
             if p["selected_skill"] == "fallen_alert"]
    assert plans
    # fallen plan must use stop_move not balance_stand
    motions = [s for s in plans[-1]["steps"] if s["executor"] == "motion"]
    assert motions[0]["args"]["name"] == "stop_move"


def test_skill_request_button(brain):
    _send(brain, None, "/brain/skill_request",
          {"skill": "self_introduce", "args": {}, "request_id": "btn-1"})
    _spin(brain, 0.2)
    assert any(p["source"] == "studio_button" and p["selected_skill"] == "self_introduce"
               for p in brain._captured_proposals)


def test_skill_request_disabled_blocked(brain):
    _send(brain, None, "/brain/skill_request",
          {"skill": "go_to_named_place", "args": {}, "request_id": "btn-2"})
    _spin(brain, 0.2)
    assert not any(p["selected_skill"] == "go_to_named_place"
                   for p in brain._captured_proposals)


def test_text_input_through_pipeline(brain):
    _send(brain, None, "/brain/text_input",
          {"text": "停", "request_id": "txt-1"})
    _spin(brain, 0.3)
    assert any(p["selected_skill"] == "stop_move"
               for p in brain._captured_proposals)
```

- [ ] **Step 2: Run tests**

```bash
cd /home/roy422/newLife/elder_and_dog
source install/setup.zsh
python3 -m pytest interaction_executive/test/test_brain_rules.py -v
```

Expected: all tests PASS（some may take ~3s for timer scenarios; 11 tests total）。

- [ ] **Step 3: Commit**

```bash
git add interaction_executive/test/test_brain_rules.py
git commit -m "test(brain): cover 7 MVS scenarios + studio button + text input"
```

---

### Task 1.11: Rewrite interaction_executive_node — subscribe /brain/proposal

**Files:**
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py` (full rewrite)

- [ ] **Step 1: Back up current file**

```bash
cp interaction_executive/interaction_executive/interaction_executive_node.py \
   interaction_executive/interaction_executive/interaction_executive_node.py.bak
```

(File `.bak` will be deleted at end of task; kept temporarily to compare during integration smoke.)

- [ ] **Step 2: Write the new node**

Replace entire content of `interaction_executive_node.py`:

```python
"""interaction_executive_node — single sport /webrtc_req publisher.

Subscribes /brain/proposal (SkillPlan), validates via SafetyLayer, dispatches
say/motion/nav steps, publishes /brain/skill_result for every plan/step event.

Spec: docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md §7
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String

try:
    from go2_interfaces.msg import WebRtcReq
except ImportError:
    WebRtcReq = None  # tests / dev environments without go2_interfaces

from .safety_layer import SafetyLayer
from .skill_contract import (
    BANNED_API_IDS, MOTION_NAME_MAP, ExecutorKind, PriorityClass,
    SkillPlan, SkillResult, SkillResultStatus, SkillStep,
)
from .skill_queue import SkillQueue
from .world_state import WorldState


_RELIABLE_10 = QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE)
_RELIABLE_20 = QoSProfile(depth=20, reliability=QoSReliabilityPolicy.RELIABLE)


@dataclass
class _ActiveStep:
    """Hold a reference to the active plan (not just plan_id) so that when
    SAFETY/ALERT preempts mid-step, the ABORTED SkillResult carries the OLD
    plan's selected_skill / priority_class / step_total — not the new plan's.
    """
    plan: SkillPlan
    step_index: int
    started_at: float


class InteractionExecutiveNode(Node):

    def __init__(self) -> None:
        super().__init__("interaction_executive_node")
        self.declare_parameter("step_settle_s", 0.4)
        self.declare_parameter("tts_idle_timeout_s", 6.0)
        self.step_settle_s = float(self.get_parameter("step_settle_s").value)
        self.tts_idle_timeout_s = float(self.get_parameter("tts_idle_timeout_s").value)

        self._safety = SafetyLayer()
        self._world = WorldState(self)
        self._queue = SkillQueue()
        self._active: _ActiveStep | None = None
        self._lock = threading.Lock()

        # publishers
        self._pub_tts = self.create_publisher(String, "/tts", 10)
        if WebRtcReq is not None:
            self._pub_webrtc = self.create_publisher(WebRtcReq, "/webrtc_req", 10)
        else:
            self._pub_webrtc = None
        self._pub_skill_result = self.create_publisher(String, "/brain/skill_result", _RELIABLE_20)

        # subscribers
        self.create_subscription(String, "/brain/proposal", self._on_proposal, _RELIABLE_10)

        # worker tick
        self._tick = self.create_timer(0.1, self._worker_tick)

        self.get_logger().info("interaction_executive_node ready (Brain MVS)")

    # ── proposal entrypoint ──────────────────────────────
    def _on_proposal(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except (ValueError, json.JSONDecodeError):
            return
        plan = SkillPlan(
            plan_id=data["plan_id"],
            selected_skill=data["selected_skill"],
            steps=[SkillStep(ExecutorKind(s["executor"]), s["args"]) for s in data["steps"]],
            reason=data.get("reason", ""),
            source=data.get("source", ""),
            priority_class=PriorityClass(int(data["priority_class"])),
            session_id=data.get("session_id"),
            created_at=float(data.get("created_at", time.time())),
        )

        # validate
        snap = self._world.snapshot()
        result = self._safety.validate(plan, snap)
        if not result.ok:
            self._emit_result(plan.plan_id, None, SkillResultStatus.BLOCKED_BY_SAFETY,
                              detail=result.reason, selected_skill=plan.selected_skill,
                              priority_class=plan.priority_class, step_total=len(plan.steps))
            return

        self._emit_result(plan.plan_id, None, SkillResultStatus.ACCEPTED,
                          detail=plan.selected_skill, selected_skill=plan.selected_skill,
                          priority_class=plan.priority_class, step_total=len(plan.steps))

        # preemption
        if plan.priority_class in (PriorityClass.SAFETY, PriorityClass.ALERT):
            preempted = self._queue.clear(reason="preempted")
            for pp in preempted:
                self._emit_result(pp.plan.plan_id, None, SkillResultStatus.ABORTED,
                                  detail=pp.reason, selected_skill=pp.plan.selected_skill,
                                  priority_class=pp.plan.priority_class,
                                  step_total=len(pp.plan.steps))
            with self._lock:
                if self._active is not None:
                    # IMPORTANT: emit ABORTED for the ACTIVE plan (old), not the new preempting plan
                    active_plan = self._active.plan
                    self._emit_result(active_plan.plan_id, self._active.step_index,
                                      SkillResultStatus.ABORTED, detail="preempted_by_higher_priority",
                                      selected_skill=active_plan.selected_skill,
                                      priority_class=active_plan.priority_class,
                                      step_total=len(active_plan.steps))
                    self._active = None
            self._queue.push_front(plan)
        else:
            self._queue.push(plan)

    # ── worker ───────────────────────────────────────────
    def _worker_tick(self) -> None:
        with self._lock:
            if self._active is not None:
                # currently dispatching a step; wait for settle / TTS idle
                age = time.time() - self._active.started_at
                if age < self.step_settle_s:
                    return
                # TTS-bound steps: wait until tts_playing flips false
                snap = self._world.snapshot()
                if snap.tts_playing and age < self.tts_idle_timeout_s:
                    return
                # Step done — emit success using ACTIVE plan reference (not queue.peek())
                active_plan = self._active.plan
                self._emit_result(active_plan.plan_id, self._active.step_index,
                                  SkillResultStatus.STEP_SUCCESS,
                                  selected_skill=active_plan.selected_skill,
                                  priority_class=active_plan.priority_class,
                                  step_total=len(active_plan.steps))
                self._active = None

            plan = self._queue.peek()
            if plan is None:
                return
            # determine next step
            if not getattr(plan, "_started", False):
                self._emit_result(plan.plan_id, None, SkillResultStatus.STARTED,
                                  selected_skill=plan.selected_skill,
                                  priority_class=plan.priority_class,
                                  step_total=len(plan.steps))
                plan._started = True
                plan._next_index = 0

            if plan._next_index >= len(plan.steps):
                self._emit_result(plan.plan_id, None, SkillResultStatus.COMPLETED,
                                  selected_skill=plan.selected_skill,
                                  priority_class=plan.priority_class,
                                  step_total=len(plan.steps))
                self._queue.pop()
                return

            step = plan.steps[plan._next_index]
            self._emit_result(plan.plan_id, plan._next_index, SkillResultStatus.STEP_STARTED,
                              detail=step.executor.value,
                              selected_skill=plan.selected_skill,
                              priority_class=plan.priority_class,
                              step_total=len(plan.steps))
            ok = self._dispatch_step(step)
            if not ok:
                self._emit_result(plan.plan_id, plan._next_index, SkillResultStatus.STEP_FAILED,
                                  detail="dispatch_error",
                                  selected_skill=plan.selected_skill,
                                  priority_class=plan.priority_class,
                                  step_total=len(plan.steps))
                self._queue.pop()
                return
            # Store full plan reference so preemption can correctly attribute ABORTED
            self._active = _ActiveStep(plan=plan, step_index=plan._next_index,
                                      started_at=time.time())
            plan._next_index += 1

    # ── dispatch ─────────────────────────────────────────
    def _dispatch_step(self, step: SkillStep) -> bool:
        try:
            if step.executor == ExecutorKind.SAY:
                text = str(step.args.get("text", ""))
                if not text:
                    return False
                msg = String(); msg.data = text
                self._pub_tts.publish(msg)
                return True
            if step.executor == ExecutorKind.MOTION:
                name = step.args.get("name")
                api_id = MOTION_NAME_MAP.get(name)
                if api_id is None or api_id in BANNED_API_IDS:
                    self.get_logger().error(f"refuse motion: name={name!r}")
                    return False
                if self._pub_webrtc is None or WebRtcReq is None:
                    self.get_logger().warn(f"WebRtcReq unavailable; skipping motion {name}")
                    return True  # treat as ok in dev env
                req = WebRtcReq()
                req.api_id = int(api_id)
                req.parameter = str(api_id)
                req.priority = 0
                req.topic = "rt/api/sport/request"
                self._pub_webrtc.publish(req)
                return True
            if step.executor == ExecutorKind.NAV:
                # MVS nav skill is disabled (go_to_named_place enabled=false). Stub.
                self.get_logger().info(f"NAV step (stub): {step.args}")
                return True
        except Exception as exc:
            self.get_logger().error(f"dispatch failed: {exc}")
            return False
        return False

    # ── result emit ─────────────────────────────────────
    def _emit_result(self, plan_id: str, step_index: int | None,
                     status: SkillResultStatus, *, detail: str = "",
                     selected_skill: str = "", priority_class: PriorityClass | int = 3,
                     step_total: int = 0) -> None:
        payload = {
            "plan_id": plan_id,
            "step_index": step_index,
            "status": status.value,
            "detail": detail,
            "selected_skill": selected_skill,
            "priority_class": int(priority_class),
            "step_total": step_total,
            "timestamp": time.time(),
        }
        msg = String(); msg.data = json.dumps(payload, ensure_ascii=False)
        self._pub_skill_result.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = InteractionExecutiveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Build & syntax check**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m py_compile interaction_executive/interaction_executive/interaction_executive_node.py
colcon build --packages-select interaction_executive --symlink-install
```

- [ ] **Step 4: Remove backup**

```bash
rm interaction_executive/interaction_executive/interaction_executive_node.py.bak
```

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_executive_node.py
git commit -m "refactor(executive): rewrite as Brain-driven step dispatcher

- Subscribes /brain/proposal; no longer subscribes to raw event topics
- Single sport /webrtc_req publisher (with banned_api guard)
- Emits /brain/skill_result for every plan/step lifecycle event
- Does NOT subscribe to its own /brain/skill_result"
```

---

### Task 1.12: Wire setup.py + launch + config

**Files:**
- Modify: `interaction_executive/setup.py`
- Modify: `interaction_executive/launch/interaction_executive.launch.py`
- Modify: `interaction_executive/config/executive.yaml`

- [ ] **Step 1: Add brain_node entry_point**

Open `interaction_executive/setup.py`, find `entry_points` block. It looks like:

```python
entry_points={
    "console_scripts": [
        "interaction_executive_node = interaction_executive.interaction_executive_node:main",
    ],
},
```

Update to:

```python
entry_points={
    "console_scripts": [
        "interaction_executive_node = interaction_executive.interaction_executive_node:main",
        "brain_node = interaction_executive.brain_node:main",
    ],
},
```

- [ ] **Step 2: Update launch file**

Replace `interaction_executive/launch/interaction_executive.launch.py` content:

```python
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    cfg = PathJoinSubstitution([
        FindPackageShare("interaction_executive"), "config", "executive.yaml"
    ])
    return LaunchDescription([
        Node(
            package="interaction_executive",
            executable="brain_node",
            name="brain_node",
            parameters=[cfg],
            output="screen",
        ),
        Node(
            package="interaction_executive",
            executable="interaction_executive_node",
            name="interaction_executive_node",
            parameters=[cfg],
            output="screen",
        ),
    ])
```

- [ ] **Step 3: Extend config**

Open `interaction_executive/config/executive.yaml`. Replace whole file:

```yaml
brain_node:
  ros__parameters:
    chat_wait_ms: 1500
    dedup_window_s: 1.0
    unknown_face_accumulate_s: 3.0
    fallen_accumulate_s: 2.0

interaction_executive_node:
  ros__parameters:
    step_settle_s: 0.4
    tts_idle_timeout_s: 6.0
```

- [ ] **Step 4: Build**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select interaction_executive --symlink-install
source install/setup.zsh
```

- [ ] **Step 5: Launch smoke**

```bash
ros2 launch interaction_executive interaction_executive.launch.py &
LPID=$!
sleep 3
ros2 node list | grep -E "brain_node|interaction_executive_node"
kill $LPID
```

Expected: both nodes listed.

- [ ] **Step 6: Commit**

```bash
git add interaction_executive/setup.py \
        interaction_executive/launch/interaction_executive.launch.py \
        interaction_executive/config/executive.yaml
git commit -m "build(brain): wire brain_node entry_point + launch + config"
```

---

### Task 1.13: Phase 1 integration smoke (real ROS2 dry-run)

**Files:**
- Create: `scripts/start_pawai_brain_tmux.sh`

- [ ] **Step 1: Write tmux launch script**

```bash
#!/usr/bin/env bash
# Brain MVS dry-run tmux: brain_node + interaction_executive_node + llm_bridge in brain mode.
# Does NOT start go2_driver (use a separate session for hardware).

set -euo pipefail
SESSION="pawai_brain"
WORKSPACE="${WORKSPACE:-$HOME/newLife/elder_and_dog}"
SOURCE_CMD="source /opt/ros/humble/setup.zsh && cd $WORKSPACE && source install/setup.zsh"

tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -n brain "$SOURCE_CMD; \
  ros2 launch interaction_executive interaction_executive.launch.py; bash"
tmux new-window -t "$SESSION" -n llm_bridge "$SOURCE_CMD; \
  ros2 run speech_processor llm_bridge_node --ros-args -p output_mode:=brain; bash"
tmux new-window -t "$SESSION" -n monitor "$SOURCE_CMD; \
  echo '--- /state/pawai_brain ---'; ros2 topic echo /state/pawai_brain"
tmux new-window -t "$SESSION" -n results "$SOURCE_CMD; \
  ros2 topic echo /brain/skill_result"
echo "tmux session '$SESSION' started. Attach: tmux attach -t $SESSION"
```

```bash
chmod +x /home/roy422/newLife/elder_and_dog/scripts/start_pawai_brain_tmux.sh
```

- [ ] **Step 2: Run dry-run**

```bash
bash /home/roy422/newLife/elder_and_dog/scripts/start_pawai_brain_tmux.sh
sleep 5
# In another shell:
source install/setup.zsh
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"chat\",\"transcript\":\"介紹你自己\",\"session_id\":\"smoke-1\"}"}'
sleep 2
# Switch to "results" tmux window — should see ACCEPTED → STARTED → STEP_STARTED(0,1,...,9) → STEP_SUCCESS → COMPLETED
tmux attach -t pawai_brain
```

Expected: 10 STEP_STARTED + STEP_SUCCESS pairs + COMPLETED for self_introduce.

- [ ] **Step 3: Test safety preemption**

```bash
# While self_introduce is running:
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"chat\",\"transcript\":\"停\",\"session_id\":\"smoke-2\"}"}'
```

Expected: ABORTED for self_introduce, then ACCEPTED → COMPLETED for stop_move.

- [ ] **Step 4: Tear down**

```bash
tmux kill-session -t pawai_brain
```

- [ ] **Step 5: Commit + tag**

```bash
git add scripts/start_pawai_brain_tmux.sh
git commit -m "chore(brain): tmux launcher for Brain MVS dry-run"
git tag pawai-brain-phase1-done
```

---

## Phase 2 — Studio Brain Skill Console

### Task 2.1: Extend backend/schemas.py

**Files:**
- Modify: `pawai-studio/backend/schemas.py`

- [ ] **Step 1: Inspect current file**

```bash
head -80 /home/roy422/newLife/elder_and_dog/pawai-studio/backend/schemas.py
```

- [ ] **Step 2: Append new models**

Append to the file:

```python
# ── Brain MVS models ─────────────────────────────────────
from typing import Literal as _Literal

ExecutorKindLit = _Literal["say", "motion", "nav"]
PriorityClassLit = _Literal[0, 1, 2, 3, 4]
SkillResultStatusLit = _Literal[
    "accepted", "started", "step_started", "step_success", "step_failed",
    "completed", "aborted", "blocked_by_safety",
]
BrainModeLit = _Literal["idle", "chat", "skill", "sequence", "alert", "safety_stop"]


class SkillStepModel(BaseModel):
    executor: ExecutorKindLit
    args: dict


class SkillPlanModel(BaseModel):
    plan_id: str
    selected_skill: str
    steps: list[SkillStepModel]
    reason: str
    source: str
    priority_class: PriorityClassLit
    session_id: str | None = None
    created_at: float


class SkillResultModel(BaseModel):
    plan_id: str
    step_index: int | None = None
    status: SkillResultStatusLit
    detail: str = ""
    selected_skill: str = ""
    priority_class: PriorityClassLit = 3
    step_total: int = 0
    timestamp: float


class BrainActivePlan(BaseModel):
    plan_id: str
    selected_skill: str
    step_index: int
    step_total: int | None = None
    started_at: float
    priority_class: PriorityClassLit = 3


class BrainSafetyFlags(BaseModel):
    obstacle: bool = False
    emergency: bool = False
    fallen: bool = False
    tts_playing: bool = False
    nav_safe: bool = True


class BrainPlanRecord(BaseModel):
    plan_id: str
    selected_skill: str
    source: str
    priority: int
    accepted: bool
    reason: str
    created_at: float


class PawAIBrainState(BaseModel):
    timestamp: float
    mode: BrainModeLit
    active_plan: BrainActivePlan | None = None
    active_step: SkillStepModel | None = None
    fallback_active: bool = False
    safety_flags: BrainSafetyFlags
    cooldowns: dict[str, float] = {}
    last_plans: list[BrainPlanRecord] = []


class SkillRequestPayload(BaseModel):
    skill: str
    args: dict = {}
    request_id: str | None = None


class TextInputPayload(BaseModel):
    text: str
    request_id: str | None = None
```

- [ ] **Step 3: Lint**

```bash
python3 -c "from pawai_studio.backend import schemas; print('ok')" 2>/dev/null || \
python3 -m py_compile pawai-studio/backend/schemas.py
```

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/backend/schemas.py
git commit -m "feat(studio): add Brain MVS Pydantic schemas"
```

---

### Task 2.2: Extend studio_gateway.py

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py`

- [ ] **Step 1: Add to TOPIC_MAP**

Locate the `TOPIC_MAP` dict (around line 59) and extend:

```python
TOPIC_MAP: dict[str, str] = {
    "/state/perception/face":          "face",
    "/event/gesture_detected":         "gesture",
    "/event/pose_detected":            "pose",
    "/event/speech_intent_recognized": "speech",
    "/event/object_detected":          "object",
    # Brain MVS additions
    "/state/pawai_brain":              "brain_state",
    "/brain/proposal":                 "brain_proposal",
    "/brain/skill_result":             "brain_skill_result",
}
```

- [ ] **Step 2: Add publishers**

In the `GatewayNode.__init__` (after existing publishers), add:

```python
        from std_msgs.msg import String as _String
        self._pub_skill_request = self.create_publisher(_String, "/brain/skill_request", 10)
        self._pub_text_input    = self.create_publisher(_String, "/brain/text_input", 10)
```

- [ ] **Step 3: Add REST endpoints**

Locate the FastAPI app definition. Add:

```python
import json as _json
from pawai_studio.backend.schemas import SkillRequestPayload, TextInputPayload


@app.post("/api/skill_request")
async def post_skill_request(payload: SkillRequestPayload):
    msg = _String()
    msg.data = _json.dumps({
        "skill": payload.skill,
        "args": payload.args or {},
        "request_id": payload.request_id or f"req-{int(time.time()*1000)}",
        "source": "studio_button",
        "created_at": time.time(),
    }, ensure_ascii=False)
    gateway_node._pub_skill_request.publish(msg)
    return {"ok": True, "request_id": payload.request_id}


@app.post("/api/text_input")
async def post_text_input(payload: TextInputPayload):
    msg = _String()
    msg.data = _json.dumps({
        "text": payload.text,
        "request_id": payload.request_id or f"txt-{int(time.time()*1000)}",
        "source": "studio_text",
        "created_at": time.time(),
    }, ensure_ascii=False)
    gateway_node._pub_text_input.publish(msg)
    return {"ok": True, "request_id": payload.request_id}
```

(Adjust import paths to whatever `gateway_node` reference exists in this file; pattern-match the existing endpoints.)

- [ ] **Step 4: Smoke test**

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio
python3 gateway/studio_gateway.py &
GW=$!
sleep 2
curl -s -X POST http://localhost:8080/api/skill_request \
  -H 'Content-Type: application/json' \
  -d '{"skill":"self_introduce","args":{}}' | python3 -m json.tool
kill $GW
```

Expected: `{"ok": true, ...}`.

- [ ] **Step 5: Commit**

```bash
git add pawai-studio/gateway/studio_gateway.py
git commit -m "feat(studio-gateway): bridge /state/pawai_brain + skill_request/text_input REST"
```

---

### Task 2.3: Extend mock_server.py

**Files:**
- Modify: `pawai-studio/backend/mock_server.py`

- [ ] **Step 1: Add mock endpoints + WS payloads**

Add to mock_server.py (after existing routes):

```python
from .schemas import SkillRequestPayload, TextInputPayload, PawAIBrainState

# In-memory mock state
_mock_brain_state = {
    "timestamp": 0.0,
    "mode": "idle",
    "active_plan": None,
    "active_step": None,
    "fallback_active": False,
    "safety_flags": {"obstacle": False, "emergency": False,
                     "fallen": False, "tts_playing": False, "nav_safe": True},
    "cooldowns": {},
    "last_plans": [],
}


@app.post("/api/skill_request")
async def mock_skill_request(payload: SkillRequestPayload):
    return {"ok": True, "mock": True, "request_id": payload.request_id}


@app.post("/api/text_input")
async def mock_text_input(payload: TextInputPayload):
    return {"ok": True, "mock": True, "request_id": payload.request_id}


@app.post("/mock/scenario/self_introduce")
async def mock_scenario_self_introduce():
    """Push 10 step events through /ws/events to simulate self_introduce."""
    import time
    plan_id = f"p-mock-{int(time.time()*1000)}"
    steps = [
        ("say", {"text": "我是 PawAI，你的居家互動機器狗"}),
        ("motion", {"name": "hello"}),
        ("say", {"text": "平常我會待在你身邊，等你叫我"}),
        ("motion", {"name": "sit"}),
        ("say", {"text": "你可以用聲音、手勢，或直接跟我互動"}),
        ("motion", {"name": "content"}),
        ("say", {"text": "我也會注意周圍發生的事情"}),
        ("motion", {"name": "stand"}),
        ("say", {"text": "如果看到陌生人，我會提醒你提高注意"}),
        ("motion", {"name": "balance_stand"}),
    ]
    await broadcast_event("brain_proposal", {
        "plan_id": plan_id, "selected_skill": "self_introduce",
        "steps": [{"executor": e, "args": a} for e, a in steps],
        "reason": "mock_scenario", "source": "mock", "priority_class": 2,
        "session_id": None, "created_at": time.time(),
    })
    await broadcast_event("brain_skill_result", {
        "plan_id": plan_id, "step_index": None, "status": "accepted",
        "detail": "self_introduce", "selected_skill": "self_introduce",
        "priority_class": 2, "step_total": 10, "timestamp": time.time(),
    })
    await broadcast_event("brain_skill_result", {
        "plan_id": plan_id, "step_index": None, "status": "started",
        "detail": "", "selected_skill": "self_introduce",
        "priority_class": 2, "step_total": 10, "timestamp": time.time(),
    })
    for idx, (executor, args) in enumerate(steps):
        await asyncio.sleep(0.5)
        await broadcast_event("brain_skill_result", {
            "plan_id": plan_id, "step_index": idx, "status": "step_started",
            "detail": executor, "selected_skill": "self_introduce",
            "priority_class": 2, "step_total": 10, "timestamp": time.time(),
        })
        await asyncio.sleep(0.3)
        await broadcast_event("brain_skill_result", {
            "plan_id": plan_id, "step_index": idx, "status": "step_success",
            "detail": "", "selected_skill": "self_introduce",
            "priority_class": 2, "step_total": 10, "timestamp": time.time(),
        })
    await broadcast_event("brain_skill_result", {
        "plan_id": plan_id, "step_index": None, "status": "completed",
        "detail": "", "selected_skill": "self_introduce",
        "priority_class": 2, "step_total": 10, "timestamp": time.time(),
    })
    return {"ok": True, "plan_id": plan_id}
```

(Use `broadcast_event` helper function name that matches existing mock_server pattern; if the helper is named differently, adapt.)

- [ ] **Step 2: Smoke**

```bash
bash pawai-studio/start.sh &
sleep 5
curl -s -X POST http://localhost:8001/mock/scenario/self_introduce
```

Expected: response `{"ok": true, ...}`. Open browser → check that ws/events streams 10 step events.

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/backend/mock_server.py
git commit -m "feat(studio-mock): add Brain endpoints + self_introduce scenario"
```

---

### Task 2.4: Mirror schemas in frontend types.ts

**Files:**
- Modify: `pawai-studio/frontend/contracts/types.ts`

- [ ] **Step 1: Append type mirrors**

```ts
// ── Brain MVS types ─────────────────────────────────────
export type ExecutorKind = "say" | "motion" | "nav";
export type PriorityClass = 0 | 1 | 2 | 3 | 4;
export type SkillResultStatus =
  | "accepted" | "started" | "step_started" | "step_success" | "step_failed"
  | "completed" | "aborted" | "blocked_by_safety";
export type BrainMode = "idle" | "chat" | "skill" | "sequence" | "alert" | "safety_stop";

export interface SkillStep { executor: ExecutorKind; args: Record<string, unknown>; }

export interface SkillPlan {
  plan_id: string;
  selected_skill: string;
  steps: SkillStep[];
  reason: string;
  source: string;
  priority_class: PriorityClass;
  session_id?: string | null;
  created_at: number;
}

export interface SkillResult {
  plan_id: string;
  step_index: number | null;
  status: SkillResultStatus;
  detail: string;
  selected_skill: string;
  priority_class: PriorityClass;
  step_total: number;
  timestamp: number;
}

export interface BrainActivePlan {
  plan_id: string;
  selected_skill: string;
  step_index: number;
  step_total: number | null;
  started_at: number;
  priority_class: PriorityClass;
}

export interface BrainSafetyFlags {
  obstacle: boolean; emergency: boolean; fallen: boolean;
  tts_playing: boolean; nav_safe: boolean;
}

export interface BrainPlanRecord {
  plan_id: string;
  selected_skill: string;
  source: string;
  priority: number;
  accepted: boolean;
  reason: string;
  created_at: number;
}

export interface PawAIBrainState {
  timestamp: number;
  mode: BrainMode;
  active_plan: BrainActivePlan | null;
  active_step: SkillStep | null;
  fallback_active: boolean;
  safety_flags: BrainSafetyFlags;
  cooldowns: Record<string, number>;
  last_plans: BrainPlanRecord[];
}

export interface SkillRequestBody { skill: string; args?: Record<string, unknown>; request_id?: string; }
export interface TextInputBody { text: string; request_id?: string; }
```

- [ ] **Step 2: TypeScript build check**

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend
npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/contracts/types.ts
git commit -m "types(studio-frontend): mirror Brain MVS schemas"
```

---

### Task 2.5: Extend Zustand store

**Files:**
- Modify: `pawai-studio/frontend/stores/state-store.ts`

- [ ] **Step 1: Inspect current store shape**

```bash
grep -n "brainState\|interface .*State\|create<" /home/roy422/newLife/elder_and_dog/pawai-studio/frontend/stores/state-store.ts | head -30
```

- [ ] **Step 2: Add Brain slice**

Replace the existing `brainState` slot definition with:

```ts
import type { PawAIBrainState, SkillResult, SkillPlan } from "@/contracts/types";

// Inside StoreState interface
brainState: PawAIBrainState | null;
brainProposals: SkillPlan[];        // ring buffer (last N)
brainResults: SkillResult[];        // ring buffer (last N)

updateBrainState: (s: PawAIBrainState) => void;
appendBrainProposal: (p: SkillPlan) => void;
appendBrainResult: (r: SkillResult) => void;
```

In the `create<...>(set => ({...}))` body:

```ts
brainState: null,
brainProposals: [],
brainResults: [],

updateBrainState: (s) => set({ brainState: s }),

appendBrainProposal: (p) =>
  set((state) => ({
    brainProposals: [p, ...state.brainProposals].slice(0, 50),
  })),

appendBrainResult: (r) =>
  set((state) => ({
    brainResults: [r, ...state.brainResults].slice(0, 200),
  })),
```

- [ ] **Step 3: TS check**

```bash
cd pawai-studio/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/frontend/stores/state-store.ts
git commit -m "feat(studio-store): brainState slice + proposal/result ring buffers"
```

---

### Task 2.6: Extend use-event-stream hook

**Files:**
- Modify: `pawai-studio/frontend/hooks/use-event-stream.ts`

- [ ] **Step 1: Add new event handlers**

Locate the WebSocket message dispatcher (e.g. `switch(event.type)` or similar). Add cases:

```ts
case "brain_state":
  store.updateBrainState(event.payload as PawAIBrainState);
  break;
case "brain_proposal":
  store.appendBrainProposal(event.payload as SkillPlan);
  break;
case "brain_skill_result":
  store.appendBrainResult(event.payload as SkillResult);
  break;
```

Add type imports at top:

```ts
import type { PawAIBrainState, SkillPlan, SkillResult } from "@/contracts/types";
```

- [ ] **Step 2: TS check**

```bash
cd pawai-studio/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/hooks/use-event-stream.ts
git commit -m "feat(studio-frontend): dispatch brain_state/proposal/skill_result events"
```

---

### Task 2.7: Create brain-status-strip.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/brain-status-strip.tsx`

- [ ] **Step 1: Write component**

```tsx
"use client";

import { useStateStore } from "@/stores/state-store";
import { Brain } from "lucide-react";

const MODE_LABEL: Record<string, string> = {
  idle: "待命", chat: "聊天中", skill: "執行技能",
  sequence: "序列中", alert: "警示", safety_stop: "安全停止",
};

export function BrainStatusStrip() {
  const brain = useStateStore((s) => s.brainState);
  const mode = brain?.mode ?? "idle";
  const ap = brain?.active_plan;
  const sf = brain?.safety_flags;

  return (
    <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-3 py-2 text-xs">
      <div className="flex items-center gap-1 font-medium">
        <Brain size={14} className="text-purple-500" />
        Brain · {MODE_LABEL[mode] ?? mode}
      </div>
      {ap && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <span>· {ap.selected_skill}</span>
          {ap.step_total ? (
            <span>· step {ap.step_index + 1}/{ap.step_total}</span>
          ) : null}
        </div>
      )}
      <div className="ml-auto flex items-center gap-2 text-muted-foreground">
        <span className={sf?.obstacle ? "text-red-500" : ""}>obs {sf?.obstacle ? "✗" : "✓"}</span>
        <span className={sf?.emergency ? "text-red-500" : ""}>emrg {sf?.emergency ? "✗" : "✓"}</span>
        <span className={sf?.fallen ? "text-red-500" : ""}>fall {sf?.fallen ? "✗" : "✓"}</span>
        <span>tts {sf?.tts_playing ? "▶" : "·"}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/brain-status-strip.tsx
git commit -m "feat(studio-frontend): brain-status-strip showing mode/skill/step/safety"
```

---

### Task 2.8: Create skill-buttons.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/skill-buttons.tsx`

- [ ] **Step 1: Write component**

```tsx
"use client";

import { Button } from "@/components/ui/button";

const BUTTONS: { skill: string; label: string; disabled?: boolean; tip?: string }[] = [
  { skill: "self_introduce", label: "自我介紹" },
  { skill: "stop_move",      label: "停" },
  { skill: "acknowledge_gesture", label: "OK 手勢" }, // requires args.gesture
  { skill: "greet_known_person",  label: "打招呼" }, // requires args.name
  { skill: "go_to_named_place",   label: "去地點", disabled: true,
    tip: "Disabled: nav KPI pending" },
];

async function postSkill(skill: string, args: Record<string, unknown> = {}) {
  await fetch("/api/skill_request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skill, args, request_id: `btn-${Date.now()}` }),
  });
}

export function SkillButtons() {
  return (
    <div className="flex flex-wrap gap-2 border-t border-border bg-muted/20 px-3 py-2">
      {BUTTONS.map((b) => (
        <Button
          key={b.skill}
          variant={b.skill === "stop_move" ? "destructive" : "secondary"}
          size="sm"
          disabled={b.disabled}
          title={b.tip}
          onClick={() => {
            const args: Record<string, unknown> = {};
            if (b.skill === "acknowledge_gesture") args.gesture = "ok";
            if (b.skill === "greet_known_person") args.name = "Studio";
            postSkill(b.skill, args);
          }}
        >
          {b.label}
        </Button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/skill-buttons.tsx
git commit -m "feat(studio-frontend): skill-buttons → POST /api/skill_request"
```

---

### Task 2.9: Create bubble-brain-plan.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/bubble-brain-plan.tsx`

- [ ] **Step 1: Write component**

```tsx
import { Brain } from "lucide-react";
import type { SkillPlan } from "@/contracts/types";

export function BubbleBrainPlan({ plan }: { plan: SkillPlan }) {
  return (
    <div className="flex gap-2 px-3 py-1.5 text-xs text-muted-foreground">
      <Brain size={14} className="mt-0.5 shrink-0 text-purple-500" />
      <div>
        <span className="font-mono text-purple-600">brain</span>
        <span> · selected </span>
        <span className="font-medium text-foreground">{plan.selected_skill}</span>
        <span> · {plan.reason}</span>
        <span className="ml-1 text-muted-foreground/70">[{plan.source}]</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/bubble-brain-plan.tsx
git commit -m "feat(studio-frontend): bubble-brain-plan"
```

---

### Task 2.10: Create bubble-skill-step.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/bubble-skill-step.tsx`

- [ ] **Step 1: Write component**

```tsx
import { ChevronRight } from "lucide-react";
import type { SkillResult } from "@/contracts/types";

export function BubbleSkillStep({ result }: { result: SkillResult }) {
  return (
    <div className="flex gap-2 px-3 py-1 text-xs text-muted-foreground">
      <ChevronRight size={14} className="mt-0.5 shrink-0 text-blue-400" />
      <div>
        <span className="font-mono text-blue-500">skill_step</span>
        {result.step_index !== null && (
          <span> · {result.step_index + 1}/{result.step_total}</span>
        )}
        <span> · {result.detail}</span>
        {result.status === "step_failed" && (
          <span className="ml-1 text-red-500">FAILED</span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/bubble-skill-step.tsx
git commit -m "feat(studio-frontend): bubble-skill-step"
```

---

### Task 2.11: Create bubble-safety.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/bubble-safety.tsx`

- [ ] **Step 1: Write component**

```tsx
import { ShieldAlert } from "lucide-react";
import type { SkillResult } from "@/contracts/types";

export function BubbleSafety({ result }: { result: SkillResult }) {
  const blocked = result.status === "blocked_by_safety";
  return (
    <div className="mx-3 my-1 flex items-start gap-2 rounded border border-amber-400/40 bg-amber-50 px-3 py-2 text-xs dark:bg-amber-900/20">
      <ShieldAlert size={14} className="mt-0.5 shrink-0 text-amber-600" />
      <div>
        <span className="font-mono font-medium text-amber-700">safety</span>
        <span> · </span>
        <span>{blocked ? "blocked_by_safety" : "safety_stop"}</span>
        {result.detail && <span className="ml-1 text-muted-foreground">· {result.detail}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/bubble-safety.tsx
git commit -m "feat(studio-frontend): bubble-safety"
```

---

### Task 2.12: Create bubble-alert.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/bubble-alert.tsx`

- [ ] **Step 1: Write component**

```tsx
import { AlertTriangle } from "lucide-react";
import type { SkillPlan } from "@/contracts/types";

export function BubbleAlert({ plan }: { plan: SkillPlan }) {
  return (
    <div className="mx-3 my-1 flex items-start gap-2 rounded border border-red-400/50 bg-red-50 px-3 py-2 text-xs dark:bg-red-950/30">
      <AlertTriangle size={14} className="mt-0.5 shrink-0 text-red-600" />
      <div>
        <span className="font-mono font-medium text-red-700">alert</span>
        <span> · </span>
        <span className="font-medium text-foreground">{plan.selected_skill}</span>
        <span className="ml-1 text-muted-foreground">· {plan.reason}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/bubble-alert.tsx
git commit -m "feat(studio-frontend): bubble-alert"
```

---

### Task 2.13: Create bubble-skill-result.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/bubble-skill-result.tsx`

- [ ] **Step 1: Write component**

```tsx
import { CheckCircle2, XCircle } from "lucide-react";
import type { SkillResult } from "@/contracts/types";

export function BubbleSkillResult({ result }: { result: SkillResult }) {
  const ok = result.status === "completed";
  const Icon = ok ? CheckCircle2 : XCircle;
  const colour = ok ? "text-green-600" : "text-amber-600";
  return (
    <div className="flex gap-2 px-3 py-1 text-xs text-muted-foreground">
      <Icon size={14} className={`mt-0.5 shrink-0 ${colour}`} />
      <div>
        <span className="font-mono">{result.status}</span>
        <span className="ml-1">· {result.selected_skill}</span>
        {result.detail && <span className="ml-1">· {result.detail}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/bubble-skill-result.tsx
git commit -m "feat(studio-frontend): bubble-skill-result"
```

---

### Task 2.14: Create skill-trace-drawer.tsx

**Files:**
- Create: `pawai-studio/frontend/components/chat/skill-trace-drawer.tsx`

- [ ] **Step 1: Write component**

```tsx
"use client";

import { useState } from "react";
import { useStateStore } from "@/stores/state-store";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight } from "lucide-react";

export function SkillTraceDrawer() {
  const [open, setOpen] = useState(false);
  const proposals = useStateStore((s) => s.brainProposals);
  const brain = useStateStore((s) => s.brainState);

  return (
    <div className="border-t border-border bg-muted/10">
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-full justify-start gap-1 rounded-none px-3 text-xs"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Skill Trace · {proposals.length} proposals
      </Button>
      {open && (
        <div className="max-h-48 overflow-y-auto px-3 pb-2">
          {brain && (
            <div className="mb-2 text-xs text-muted-foreground">
              World: obs={String(brain.safety_flags.obstacle)} ·
              emerg={String(brain.safety_flags.emergency)} ·
              fall={String(brain.safety_flags.fallen)} ·
              tts={String(brain.safety_flags.tts_playing)}
            </div>
          )}
          <ul className="space-y-1 text-xs">
            {proposals.slice(0, 10).map((p) => (
              <li key={p.plan_id} className="font-mono text-muted-foreground">
                <span className="text-foreground">{p.selected_skill}</span>
                <span> · src={p.source}</span>
                <span> · prio={p.priority_class}</span>
                <span> · {p.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/skill-trace-drawer.tsx
git commit -m "feat(studio-frontend): skill-trace-drawer (collapsible)"
```

---

### Task 2.15: Rewrite chat-panel.tsx — integrate Brain Skill Console

**Files:**
- Modify: `pawai-studio/frontend/components/chat/chat-panel.tsx`

- [ ] **Step 1: Add new ChatMessage union variants**

Locate the existing ChatMessage type definitions (around line 14-37) and replace:

```ts
interface UserMessage {
  id: string;
  type: "user";
  text: string;
  timestamp: number;
}

interface SayMessage {           // replaces old AIMessage
  id: string;
  type: "say";
  text: string;
  timestamp: number;
  variant?: "chat_reply" | "say_canned";
}

interface VoiceMessage {
  id: string;
  type: "voice";
  text: string;
  timestamp: number;
}

interface BrainPlanMessage {
  id: string; type: "brain_plan"; plan: SkillPlan; timestamp: number;
}
interface SkillStepMessage {
  id: string; type: "skill_step"; result: SkillResult; timestamp: number;
}
interface SafetyMessage {
  id: string; type: "safety"; result: SkillResult; timestamp: number;
}
interface AlertMessage {
  id: string; type: "alert"; plan: SkillPlan; timestamp: number;
}
interface SkillResultMessage {
  id: string; type: "skill_result"; result: SkillResult; timestamp: number;
}

type ChatMessage =
  | UserMessage | VoiceMessage | SayMessage
  | BrainPlanMessage | SkillStepMessage | SafetyMessage
  | AlertMessage | SkillResultMessage;
```

Add imports at top:

```ts
import type { SkillPlan, SkillResult, PriorityClass } from "@/contracts/types";
import { BubbleBrainPlan } from "./bubble-brain-plan";
import { BubbleSkillStep } from "./bubble-skill-step";
import { BubbleSafety } from "./bubble-safety";
import { BubbleAlert } from "./bubble-alert";
import { BubbleSkillResult } from "./bubble-skill-result";
import { BrainStatusStrip } from "./brain-status-strip";
import { SkillButtons } from "./skill-buttons";
import { SkillTraceDrawer } from "./skill-trace-drawer";
```

- [ ] **Step 2: Subscribe to Brain stores → push messages**

In the component body, add effect to convert proposals/results into ChatMessages:

```tsx
const brainProposals = useStateStore((s) => s.brainProposals);
const brainResults = useStateStore((s) => s.brainResults);
const seenProposalIds = useRef<Set<string>>(new Set());
const seenResultKeys = useRef<Set<string>>(new Set());

useEffect(() => {
  for (const p of brainProposals) {
    if (seenProposalIds.current.has(p.plan_id)) continue;
    seenProposalIds.current.add(p.plan_id);
    const isAlert = p.priority_class === 1;
    setMessages((prev) => [
      ...prev,
      isAlert
        ? { id: `bp-${p.plan_id}`, type: "alert", plan: p, timestamp: Date.now() }
        : { id: `bp-${p.plan_id}`, type: "brain_plan", plan: p, timestamp: Date.now() },
    ]);
  }
}, [brainProposals]);

useEffect(() => {
  for (const r of brainResults) {
    const key = `${r.plan_id}-${r.step_index ?? "-"}-${r.status}`;
    if (seenResultKeys.current.has(key)) continue;
    seenResultKeys.current.add(key);
    if (r.status === "blocked_by_safety" || r.selected_skill === "stop_move") {
      setMessages((prev) => [
        ...prev,
        { id: `sr-${key}`, type: "safety", result: r, timestamp: Date.now() },
      ]);
    } else if (r.status === "step_started" || r.status === "step_success" ||
               r.status === "step_failed") {
      setMessages((prev) => [
        ...prev,
        { id: `sr-${key}`, type: "skill_step", result: r, timestamp: Date.now() },
      ]);
    } else if (r.status === "completed" || r.status === "aborted") {
      setMessages((prev) => [
        ...prev,
        { id: `sr-${key}`, type: "skill_result", result: r, timestamp: Date.now() },
      ]);
    }
  }
}, [brainResults]);
```

- [ ] **Step 3: Render new bubble types in the message map**

Locate the existing `messages.map((msg) => { ... })` block. Add cases:

```tsx
{messages.map((msg) => {
  if (msg.type === "user") return /* existing */;
  if (msg.type === "voice") return /* existing */;
  if (msg.type === "say") return /* render like old AIMessage */;
  if (msg.type === "brain_plan") return <BubbleBrainPlan key={msg.id} plan={msg.plan} />;
  if (msg.type === "skill_step") return <BubbleSkillStep key={msg.id} result={msg.result} />;
  if (msg.type === "safety") return <BubbleSafety key={msg.id} result={msg.result} />;
  if (msg.type === "alert") return <BubbleAlert key={msg.id} plan={msg.plan} />;
  if (msg.type === "skill_result") return <BubbleSkillResult key={msg.id} result={msg.result} />;
  return null;
})}
```

- [ ] **Step 4: Wire BrainStatusStrip + SkillButtons + SkillTraceDrawer**

In the panel layout JSX, restructure root return:

```tsx
return (
  <div className="flex h-full flex-col">
    <BrainStatusStrip />
    <div className="flex-1 overflow-y-auto">
      {/* existing message stream */}
    </div>
    <SkillTraceDrawer />
    <SkillButtons />
    {/* existing input bar */}
  </div>
);
```

- [ ] **Step 5: Switch chat input POST target to /api/text_input**

Locate the existing input submit handler. Change the POST URL from `/api/chat` (or whatever) to:

```ts
await fetch("/api/text_input", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: input, request_id: `txt-${Date.now()}` }),
});
```

- [ ] **Step 6: TS + lint**

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend
npx tsc --noEmit
npx next lint --file components/chat/chat-panel.tsx 2>&1 | head -30
```

- [ ] **Step 7: Commit**

```bash
git add pawai-studio/frontend/components/chat/chat-panel.tsx
git commit -m "feat(studio-frontend): chat-panel becomes Brain Skill Console

- 8-variant ChatMessage union (user/voice/say + brain_plan/skill_step/safety/alert/skill_result)
- BrainStatusStrip on top, SkillButtons + SkillTraceDrawer at bottom
- Input posts to /api/text_input (not synthetic speech intent)"
```

---

### Task 2.16: Phase 2 E2E mock smoke

- [ ] **Step 1: Start mock + frontend**

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio
bash start.sh &
sleep 8
```

- [ ] **Step 2: Trigger self_introduce scenario**

```bash
curl -s -X POST http://localhost:8001/mock/scenario/self_introduce
```

Open browser to `http://localhost:3000/studio` and verify:
- BrainStatusStrip mode flashes through `idle → sequence`
- Chat stream shows: brain_plan(self_introduce) → 10 × (skill_step + step_success) → completed
- SkillTraceDrawer (toggle open) lists the proposal

- [ ] **Step 3: Click [stop] Skill Button**

Verify a safety bubble appears.

- [ ] **Step 4: Type "今天天氣"**

Wait 1.5s, expect a `say` bubble with "我聽不太懂" (canned fallback in mock_server should respond).

- [ ] **Step 5: Tag**

```bash
git tag pawai-brain-phase2-done
```

---

## Final Verification

- [ ] **All unit tests pass**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest interaction_executive/test/ speech_processor/test/test_tts_audio_api_only.py -v
```

Expected: ~30 tests, 100% PASS.

- [ ] **No new sport /webrtc_req publishers (multiline-aware audit)**

The existing publisher in `llm_bridge_node.py` is split across two lines:

```python
self.action_pub = self.create_publisher(
    WebRtcReq, "/webrtc_req", 10
)
```

A single-line `grep` would miss it and false-pass. Use one of:

**Option A — ripgrep multiline mode** (preferred):

```bash
cd /home/roy422/newLife/elder_and_dog
rg -nU --multiline --type py 'create_publisher\([^)]*WebRtcReq' \
  --glob '!build/**' --glob '!install/**' --glob '!log/**'
```

Expected files (whitelist): `interaction_executive/.../interaction_executive_node.py` only.
**Forbidden** to appear: `llm_bridge_node.py`, `event_action_bridge.py`, anything except `tts_node.py` (which uses literal int api_ids 4001-4004 and is covered by `test_tts_audio_api_only.py`).

**Option B — Python AST audit script** (run in CI):

Create `scripts/audit_webrtc_publishers.py`:

```python
"""Audit script: find every WebRtcReq publisher in the workspace.

Whitelist:
- interaction_executive/interaction_executive/interaction_executive_node.py
  (sole sport /webrtc_req publisher)
- speech_processor/speech_processor/tts_node.py
  (Megaphone audio publisher; api_ids 4001-4004 enforced by separate test)

Any other file publishing WebRtcReq is a violation of the Brain MVS
single-outlet contract.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

WHITELIST = {
    "interaction_executive/interaction_executive/interaction_executive_node.py",
    "speech_processor/speech_processor/tts_node.py",
    # Phase 0/1 transitional: llm_bridge keeps a publisher object for legacy mode
    # but it's gated by `output_mode == "legacy"` in __init__. Remove this entry
    # when the legacy code path is finally deleted (post-MVS).
    "speech_processor/speech_processor/llm_bridge_node.py",
}
ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {"build", "install", "log", ".git", "node_modules"}


def find_violations(root: Path) -> list[tuple[Path, int]]:
    violations: list[tuple[Path, int]] = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if any(part in EXCLUDED_DIRS for part in py.parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # match `self.create_publisher(...)` or `node.create_publisher(...)`
            if not (isinstance(func, ast.Attribute) and func.attr == "create_publisher"):
                continue
            # first positional arg should be the message type
            if not node.args:
                continue
            first = node.args[0]
            type_name = first.id if isinstance(first, ast.Name) else None
            if type_name == "WebRtcReq":
                if rel not in WHITELIST:
                    violations.append((py, node.lineno))
    return violations


def main() -> int:
    violations = find_violations(ROOT)
    if not violations:
        print("OK · only whitelisted files publish WebRtcReq")
        return 0
    print("VIOLATIONS · WebRtcReq publishers outside whitelist:")
    for path, line in violations:
        print(f"  {path.relative_to(ROOT)}:{line}")
    print("\nWhitelist:")
    for w in sorted(WHITELIST):
        print(f"  {w}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

Run:

```bash
python3 scripts/audit_webrtc_publishers.py
```

Expected: `OK · only whitelisted files publish WebRtcReq`, exit 0.

(Optional: wire this into `scripts/hooks/git-pre-commit.sh` so it runs on every commit.)

- [ ] **Brain Skill Console end-to-end (real Jetson run)**

```bash
bash scripts/start_pawai_brain_tmux.sh
bash pawai-studio/start.sh
# In browser: /studio · click [self_introduce] · verify 10-step trace
```

- [ ] **Tag final**

```bash
git tag pawai-brain-mvs-complete
```

---

## Out-of-scope reminders

Phase 3 (after MVS stabilises) — explicitly NOT in this plan:
- Copying PR #38 wave dynamic gesture algorithm
- Copying PR #41 fallen geometric rules
- Copying PR #42 prompt + Plan B 台詞
- PR #40 not adopted (TensorRT YOLO already superior)
- PawAI Memory (person_profiles / session_context)
- LLM function calling integration with SKILL_REGISTRY
- nav_capability `go_to_named_place` enable
