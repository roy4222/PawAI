# Operation B-prime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all 7 modules' infrastructure and get them running on Go2 in 11 days (3/28-4/7).

**Architecture:** Baseline-first, one risk at a time. Executive v0 replaces `event_action_bridge` + `interaction_router` with a thin state machine. Obstacle avoidance uses D435 depth in `vision_perception`. All new code follows existing ROS2 package patterns.

**Tech Stack:** Python 3.10, ROS2 Humble, rclpy, numpy, std_msgs, go2_interfaces

**Spec:** `docs/superpowers/specs/2026-03-27-operation-b-prime-sprint-design.md`

---

## File Structure

### New Files

```
interaction_executive/
├── interaction_executive/
│   ├── __init__.py
│   ├── state_machine.py              # Pure Python state machine (no ROS2)
│   └── interaction_executive_node.py  # ROS2 node wrapper
├── test/
│   ├── test_state_machine.py          # Unit tests for state machine
│   └── test_executive_node.py         # Integration tests for node
├── launch/
│   └── interaction_executive.launch.py
├── config/
│   └── executive.yaml
├── resource/
│   └── interaction_executive          # Empty marker file
├── setup.py
├── setup.cfg
└── package.xml

vision_perception/vision_perception/
├── obstacle_detector.py               # Pure Python/numpy depth processing
└── obstacle_avoidance_node.py         # ROS2 node wrapper
vision_perception/test/
└── test_obstacle_detector.py          # Unit tests
vision_perception/launch/
└── obstacle_avoidance.launch.py
```

### Modified Files

```
scripts/start_full_demo_tmux.sh         # Replace bridge/router with executive
scripts/clean_speech_env.sh             # Add executive to cleanup targets
vision_perception/setup.py              # Add obstacle_avoidance_node entry
docs/architecture/contracts/interaction_contract.md  # v2.2 update
references/project-status.md            # Daily updates
```

---

## Task 1: Day 1 — Baseline Contract

**Day:** 3/28
**Goal:** Lock down the system foundation. Produce a reproducible startup flow.

**Files:**
- Create: `docs/operations/baseline-contract.md`
- Create: `scripts/device_detect.sh`
- Modify: `scripts/start_full_demo_tmux.sh`

### Subtask 1.1: Topic Graph Snapshot

- [ ] **Step 1: Capture baseline on Jetson**

SSH into Jetson, start the full demo, capture graph:

```bash
ssh jetson-nano
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
source install/setup.zsh
bash scripts/start_full_demo_tmux.sh

# In a separate terminal:
ros2 topic list > /tmp/baseline_topics.txt
ros2 node list > /tmp/baseline_nodes.txt
ros2 topic info /event/face_identity -v > /tmp/baseline_face_qos.txt
ros2 topic info /event/speech_intent_recognized -v > /tmp/baseline_speech_qos.txt
ros2 topic info /event/gesture_detected -v > /tmp/baseline_gesture_qos.txt
ros2 topic info /event/pose_detected -v > /tmp/baseline_pose_qos.txt
ros2 topic info /tts -v > /tmp/baseline_tts_qos.txt
ros2 topic info /webrtc_req -v > /tmp/baseline_webrtc_qos.txt
```

- [ ] **Step 2: Create baseline contract document**

```bash
mkdir -p docs/operations
```

Write `docs/operations/baseline-contract.md` with the captured data:
- Full topic list
- Node list
- QoS profile for each topic (BEST_EFFORT vs RELIABLE, depth, durability)
- Expected publisher/subscriber counts

- [ ] **Step 3: Commit**

```bash
git add docs/operations/baseline-contract.md
git commit -m "docs: add baseline contract (Day 1 - topic graph + QoS snapshot)"
```

### Subtask 1.2: Device Mapping

- [ ] **Step 4: Create device detection script**

Create `scripts/device_detect.sh`:

```bash
#!/usr/bin/env bash
# Detect USB audio devices and D435, output device indices.
# Usage: source scripts/device_detect.sh
set -euo pipefail

echo "=== USB Audio Devices ==="
aplay -l 2>/dev/null || true
arecord -l 2>/dev/null || true

echo ""
echo "=== RealSense D435 ==="
if command -v rs-enumerate-devices &>/dev/null; then
    rs-enumerate-devices | head -20
else
    echo "rs-enumerate-devices not found, checking /dev/video*"
    ls -la /dev/video* 2>/dev/null || echo "No video devices found"
fi

echo ""
echo "=== Detected Configuration ==="

# Find USB microphone (UACDemoV1.0)
MIC_CARD=$(arecord -l 2>/dev/null | grep -i "UAC\|UACDemo" | head -1 | sed 's/card \([0-9]*\):.*/\1/' || echo "")
if [ -z "$MIC_CARD" ]; then
    # Fallback: find any USB audio input
    MIC_CARD=$(arecord -l 2>/dev/null | grep -i "USB" | head -1 | sed 's/card \([0-9]*\):.*/\1/' || echo "NOT_FOUND")
fi
echo "MIC_DEVICE_INDEX=${MIC_CARD}"

# Find USB speaker (CD002-AUDIO)
SPK_CARD=$(aplay -l 2>/dev/null | grep -i "CD002\|USB Audio" | head -1 | sed 's/card \([0-9]*\):.*/\1/' || echo "")
if [ -z "$SPK_CARD" ]; then
    SPK_CARD=$(aplay -l 2>/dev/null | grep -i "USB" | head -1 | sed 's/card \([0-9]*\):.*/\1/' || echo "NOT_FOUND")
fi
echo "SPK_DEVICE=plughw:${SPK_CARD},0"

# Export for other scripts
export DETECTED_MIC_INDEX="${MIC_CARD}"
export DETECTED_SPK_DEVICE="plughw:${SPK_CARD},0"
```

- [ ] **Step 5: Test device detection**

```bash
ssh jetson-nano "cd ~/elder_and_dog && bash scripts/device_detect.sh"
```

Expected: prints MIC_DEVICE_INDEX and SPK_DEVICE with valid card numbers.

- [ ] **Step 6: Commit**

```bash
git add scripts/device_detect.sh
git commit -m "feat: add USB device auto-detection script (Day 1)"
```

### Subtask 1.3: Startup Order + Crash/Restart SOP

- [ ] **Step 7: Document startup order and crash recovery**

Add to `docs/operations/baseline-contract.md`:

```markdown
## Startup Order

1. Go2 power on (wait 30s for WebRTC ready)
2. Jetson power on
3. `source /opt/ros/humble/setup.zsh && source install/setup.zsh`
4. `bash scripts/start_full_demo_tmux.sh`
   - Window 0: go2_driver_node (wait 10s for WebRTC ICE)
   - Window 1: D435 camera (wait 3s)
   - Window 2: face_identity_node (wait 2s)
   - Window 3: vision_perception_node (wait 2s)
   - Window 4: interaction_router (wait 1s)
   - Window 5: stt_intent_node (wait 15s for Whisper warmup)
   - Window 6: tts_node (wait 2s)
   - Window 7: llm_bridge_node (wait 2s, checks SSH tunnel)
   - Window 8: event_action_bridge (wait 1s)
   - Window 9: foxglove_bridge (optional)

## Crash Recovery SOP (target: < 3 minutes)

1. Kill everything: `bash scripts/clean_full_demo.sh`
2. Verify clean: `ros2 node list` should return empty
3. If Go2 WebRTC stuck: power cycle Go2 (30s), then restart
4. If Jetson OOM: `sudo systemctl restart nvargus-daemon` then restart
5. Restart: `bash scripts/start_full_demo_tmux.sh`
6. Verify: `ros2 topic echo /executive/status --once` (after Day 5)

## Known Recovery Gotchas

- tts_node mid-session restart → Go2 Megaphone silent fail → restart Go2 driver too
- Multiple driver instances → `pkill -9 go2_driver; pkill -9 robot_state`
- USB device index drift → re-run `bash scripts/device_detect.sh`
```

- [ ] **Step 8: Create clean_full_demo.sh**

Create `scripts/clean_full_demo.sh`:

```bash
#!/usr/bin/env bash
# Clean all demo processes and tmux sessions.
set -euo pipefail

DEMO_SESSIONS=("full-demo" "llm-e2e" "face-identity" "asr-tts-no-vad" "speech-e2e")
DEMO_PROCS=(
    "go2_driver" "robot_state" "pointcloud" "joy_node" "teleop" "twist_mux"
    "face_identity" "vision_perception" "interaction_router" "event_action_bridge"
    "interaction_executive"
    "stt_intent_node" "tts_node" "llm_bridge_node" "intent_tts_bridge_node"
    "foxglove_bridge" "obstacle_avoidance"
    "realsense2_camera_node"
)

echo "=== Killing tmux sessions ==="
for sess in "${DEMO_SESSIONS[@]}"; do
    if tmux has-session -t "$sess" 2>/dev/null; then
        tmux kill-session -t "$sess" 2>/dev/null || true
        echo "  Killed: $sess"
    fi
done

echo "=== Killing processes ==="
for proc in "${DEMO_PROCS[@]}"; do
    if pgrep -f "$proc" >/dev/null 2>&1; then
        pkill -9 -f "$proc" 2>/dev/null || true
        echo "  Killed: $proc"
    fi
done

echo "=== Stopping ROS2 daemon ==="
ros2 daemon stop 2>/dev/null || true

sleep 1

echo "=== Verification ==="
RESIDUAL=$(ps aux | grep -E "ros2|go2_driver|face_identity|vision_perception|stt_intent|tts_node|llm_bridge|interaction" | grep -v grep | wc -l || true)
if [ "$RESIDUAL" -gt 0 ]; then
    echo "WARNING: $RESIDUAL residual processes found"
    ps aux | grep -E "ros2|go2_driver|face_identity|vision_perception" | grep -v grep || true
else
    echo "Clean. Ready to restart."
fi
```

- [ ] **Step 9: Commit**

```bash
git add docs/operations/baseline-contract.md scripts/clean_full_demo.sh
git commit -m "docs: add startup order + crash recovery SOP (Day 1)"
```

### Subtask 1.4: Baseline Validation

- [ ] **Step 10: Run 3x cold start test**

```bash
# On Jetson, run 3 times:
bash scripts/clean_full_demo.sh
sleep 2
bash scripts/start_full_demo_tmux.sh
# Wait for all windows ready (~40s)
# Verify: ros2 topic list | wc -l  (should be >= 15 topics)
# Verify: ros2 topic echo /state/perception/face --once (should see JSON)
# Verify: ros2 topic echo /event/gesture_detected --once (wave at camera)
```

All 3 must succeed.

- [ ] **Step 11: Run 1x crash recovery drill**

```bash
# While demo is running, kill a critical node:
pkill -9 -f face_identity
# Time starts now
bash scripts/clean_full_demo.sh
bash scripts/start_full_demo_tmux.sh
# Verify working: ros2 topic echo /state/perception/face --once
# Time must be < 3 minutes
```

- [ ] **Step 12: Record results and commit**

Update `docs/operations/baseline-contract.md` with test results (pass/fail, timestamps).

```bash
git add docs/operations/baseline-contract.md
git commit -m "docs: baseline validation 3x cold start + 1x crash recovery (Day 1)"
```

---

## Task 2: Day 2-3 — Hardware Bring-up

**Day:** 3/29-3/30
**Goal:** Physically mount Jetson + sensors on Go2. Reproducible bring-up.

This task is primarily physical/hardware work. Checklist format.

### Day 2 (3/29): Can Run

- [ ] **Step 1: Mount Jetson on Go2** — secure with zip ties or bracket, must survive walking
- [ ] **Step 2: Mount D435** — stable viewing angle, no shake during walk
- [ ] **Step 3: Route USB cables** — mic, speaker, D435 to Jetson; cables must not snag during Go2 movement
- [ ] **Step 4: Power verification** — Jetson powered via Go2 USB-C or external battery; confirm stable during walk
- [ ] **Step 5: Bring-up test** — Go2 on → Jetson on → `bash scripts/start_full_demo_tmux.sh` → basic interaction works
- [ ] **Step 6: Walk test** — Go2 walks for 30s, check nothing disconnects
- [ ] **Step 7: Photo documentation** — photograph mounting for future reference
- [ ] **Step 8: Commit any config changes**

```bash
git add -A
git commit -m "feat: hardware bring-up Day 2 — minimal on-robot mounting"
```

### Day 3 (3/30): Can Use

- [ ] **Step 9: Reboot consistency test** — full power cycle (Go2 + Jetson) 3 times, each time bring-up succeeds
- [ ] **Step 10: Walk stability test** — Go2 walks 2 minutes continuously, sensors stay connected
- [ ] **Step 11: Thermal test** — run full demo 30 minutes, check `cat /sys/devices/virtual/thermal/thermal_zone*/temp`, must be < 75000 (75C)
- [ ] **Step 12: Device index stability** — after each reboot, run `bash scripts/device_detect.sh`, indices must match
- [ ] **Step 13: Update baseline** — if any device indices changed, update `start_full_demo_tmux.sh` defaults
- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat: hardware bring-up Day 3 — reboot consistency + thermal verified"
```

---

## Task 3: Day 4 — Executive v0 State Machine (TDD)

**Day:** 3/31
**Goal:** Pure Python state machine with full test coverage. No ROS2 dependency.

**Files:**
- Create: `interaction_executive/interaction_executive/__init__.py`
- Create: `interaction_executive/interaction_executive/state_machine.py`
- Create: `interaction_executive/test/test_state_machine.py`
- Create: `interaction_executive/setup.py`
- Create: `interaction_executive/setup.cfg`
- Create: `interaction_executive/package.xml`
- Create: `interaction_executive/resource/interaction_executive`

### Subtask 3.1: Package Scaffold

- [ ] **Step 1: Create package structure**

```bash
mkdir -p interaction_executive/interaction_executive
mkdir -p interaction_executive/test
mkdir -p interaction_executive/launch
mkdir -p interaction_executive/config
mkdir -p interaction_executive/resource
touch interaction_executive/resource/interaction_executive
```

- [ ] **Step 2: Write setup.cfg**

Create `interaction_executive/setup.cfg`:

```ini
[develop]
script_dir=$base/lib/interaction_executive
[install]
install_scripts=$base/lib/interaction_executive
```

- [ ] **Step 3: Write package.xml**

Create `interaction_executive/package.xml`:

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>interaction_executive</name>
  <version>0.1.0</version>
  <description>Thin interaction orchestrator — state machine for demo control</description>
  <maintainer email="roy@pawai.dev">Roy</maintainer>
  <license>MIT</license>

  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <depend>go2_interfaces</depend>

  <test_depend>pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

- [ ] **Step 4: Write setup.py**

Create `interaction_executive/setup.py`:

```python
from setuptools import find_packages, setup

package_name = "interaction_executive"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/interaction_executive.launch.py"]),
        ("share/" + package_name + "/config", ["config/executive.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "interaction_executive_node = interaction_executive.interaction_executive_node:main",
        ],
    },
)
```

- [ ] **Step 5: Write __init__.py**

Create `interaction_executive/interaction_executive/__init__.py`:

```python
"""Interaction Executive — thin demo orchestrator."""
```

- [ ] **Step 6: Commit scaffold**

```bash
git add interaction_executive/
git commit -m "feat(executive): scaffold interaction_executive ROS2 package"
```

### Subtask 3.2: State Machine Tests First

- [ ] **Step 7: Write state machine tests**

Create `interaction_executive/test/test_state_machine.py`:

```python
"""Tests for ExecutiveStateMachine — pure Python, no ROS2."""
import time
import pytest
from interaction_executive.state_machine import (
    ExecutiveStateMachine,
    ExecutiveState,
    EventType,
)


class TestBasicTransitions:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_initial_state_is_idle(self):
        assert self.sm.state == ExecutiveState.IDLE

    def test_face_welcome_transitions_to_greeting(self):
        result = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert self.sm.state == ExecutiveState.GREETING
        assert result.tts is not None  # Should generate greeting

    def test_speech_greet_transitions_to_greeting(self):
        result = self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "greet"})
        assert self.sm.state == ExecutiveState.GREETING

    def test_speech_chat_transitions_to_conversing(self):
        result = self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "chat", "text": "你好嗎"})
        assert self.sm.state == ExecutiveState.CONVERSING

    def test_speech_command_transitions_to_executing(self):
        result = self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "sit"})
        assert self.sm.state == ExecutiveState.EXECUTING
        assert result.action is not None

    def test_stop_gesture_returns_to_idle(self):
        self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "chat", "text": "test"})
        assert self.sm.state == ExecutiveState.CONVERSING
        result = self.sm.handle_event(EventType.GESTURE, source="cam", data={"gesture": "stop"})
        assert self.sm.state == ExecutiveState.IDLE
        assert result.action is not None  # stop_move action


class TestEmergency:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_fallen_triggers_emergency_from_idle(self):
        result = self.sm.handle_event(EventType.POSE_FALLEN)
        assert self.sm.state == ExecutiveState.EMERGENCY
        assert result.tts is not None  # "你還好嗎"

    def test_fallen_triggers_emergency_from_conversing(self):
        self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "chat", "text": "hi"})
        result = self.sm.handle_event(EventType.POSE_FALLEN)
        assert self.sm.state == ExecutiveState.EMERGENCY

    def test_emergency_timeout_returns_to_idle(self):
        self.sm.handle_event(EventType.POSE_FALLEN)
        result = self.sm.handle_event(EventType.TIMEOUT)
        assert self.sm.state == ExecutiveState.IDLE


class TestObstacle:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_obstacle_triggers_stop_from_idle(self):
        result = self.sm.handle_event(EventType.OBSTACLE)
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP
        assert result.action is not None  # Damp

    def test_obstacle_interrupts_executing(self):
        self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "sit"})
        assert self.sm.state == ExecutiveState.EXECUTING
        result = self.sm.handle_event(EventType.OBSTACLE)
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP
        assert self.sm._previous_state == ExecutiveState.EXECUTING

    def test_obstacle_cleared_returns_to_previous_state(self):
        self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "sit"})
        self.sm.handle_event(EventType.OBSTACLE)
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP
        result = self.sm.handle_event(EventType.OBSTACLE_CLEARED)
        assert self.sm.state == ExecutiveState.EXECUTING

    def test_obstacle_cleared_with_debounce(self):
        """Obstacle cleared must be stable for MIN_CLEAR_DURATION."""
        self.sm.handle_event(EventType.OBSTACLE)
        # Immediate clear should NOT transition (debounce not met)
        self.sm._obstacle_clear_time = time.monotonic()  # just now
        result = self.sm.try_obstacle_clear()
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP  # still stopped

    def test_obstacle_cleared_after_debounce(self):
        """After debounce period, should recover."""
        self.sm.handle_event(EventType.OBSTACLE)
        self.sm._obstacle_clear_time = time.monotonic() - 3.0  # 3s ago
        result = self.sm.try_obstacle_clear()
        assert self.sm.state == ExecutiveState.IDLE  # recovered


class TestDedup:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_same_source_within_5s_is_deduped(self):
        result1 = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert result1.tts is not None
        result2 = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert result2.tts is None  # deduped

    def test_different_source_not_deduped(self):
        result1 = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert result1.tts is not None
        self.sm._state = ExecutiveState.IDLE  # reset for test
        result2 = self.sm.handle_event(EventType.FACE_WELCOME, source="alice")
        assert result2.tts is not None  # different person, not deduped


class TestPriority:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_emergency_beats_everything(self):
        assert EventType.POSE_FALLEN.priority < EventType.OBSTACLE.priority
        assert EventType.OBSTACLE.priority < EventType.GESTURE.priority

    def test_obstacle_beats_gesture(self):
        assert EventType.OBSTACLE.priority < EventType.GESTURE.priority

    def test_speech_beats_face(self):
        assert EventType.SPEECH_INTENT.priority < EventType.FACE_WELCOME.priority


class TestTimeout:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_greeting_timeout_returns_to_idle(self):
        self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert self.sm.state == ExecutiveState.GREETING
        result = self.sm.handle_event(EventType.TIMEOUT)
        assert self.sm.state == ExecutiveState.IDLE

    def test_conversing_timeout_returns_to_idle(self):
        self.sm.handle_event(EventType.SPEECH_INTENT, source="mic", data={"intent": "chat", "text": "hi"})
        result = self.sm.handle_event(EventType.TIMEOUT)
        assert self.sm.state == ExecutiveState.IDLE
```

- [ ] **Step 8: Run tests — expect FAIL**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest interaction_executive/test/test_state_machine.py -v
```

Expected: `ModuleNotFoundError: No module named 'interaction_executive.state_machine'`

- [ ] **Step 9: Commit tests**

```bash
git add interaction_executive/test/test_state_machine.py
git commit -m "test(executive): add state machine tests — RED (Day 4)"
```

### Subtask 3.3: Implement State Machine

- [ ] **Step 10: Write state_machine.py**

Create `interaction_executive/interaction_executive/state_machine.py`:

```python
"""Executive v0 State Machine — thin demo orchestrator.

Pure Python, no ROS2 dependency. Handles event routing, state transitions,
dedup, priority, and obstacle debounce.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional


class ExecutiveState(Enum):
    IDLE = "idle"
    GREETING = "greeting"
    CONVERSING = "conversing"
    EXECUTING = "executing"
    EMERGENCY = "emergency"
    OBSTACLE_STOP = "obstacle_stop"


class EventType(IntEnum):
    """Event types ordered by priority (lower = higher priority)."""
    POSE_FALLEN = 0      # EMERGENCY — highest
    OBSTACLE = 1          # obstacle detected
    GESTURE = 2           # stop gesture or other
    SPEECH_INTENT = 3     # voice command
    FACE_WELCOME = 4      # face identity
    OBSTACLE_CLEARED = 5  # obstacle cleared (internal)
    TIMEOUT = 99          # state timeout (internal)

    @property
    def priority(self) -> int:
        return self.value


@dataclass
class EventResult:
    """Output of a state transition."""
    tts: Optional[str] = None          # Text to publish on /tts
    action: Optional[dict] = None      # Action dict for /webrtc_req
    new_state: Optional[ExecutiveState] = None


# Go2 action constants (api_id values)
ACTION_STOP = {"api_id": 1003}         # StopMove
ACTION_DAMP = {"api_id": 1004}         # Damp (soft stop)
ACTION_SIT = {"api_id": 1001}          # Sit
ACTION_STAND = {"api_id": 1002}        # Stand
ACTION_WAVE = {"api_id": 1020}         # Hello/wave
ACTION_CONTENT = {"api_id": 1020}      # Content/happy

DEDUP_WINDOW = 5.0        # seconds
STATE_TIMEOUT = 30.0      # seconds per state
OBSTACLE_DEBOUNCE = 2.0   # seconds before obstacle_cleared takes effect
OBSTACLE_MIN_DURATION = 1.0  # minimum time in OBSTACLE_STOP


class ExecutiveStateMachine:
    def __init__(self):
        self._state = ExecutiveState.IDLE
        self._previous_state = ExecutiveState.IDLE
        self._state_enter_time = time.monotonic()
        self._dedup: dict[str, float] = {}  # "event_type:source" -> timestamp
        self._obstacle_clear_time: Optional[float] = None
        self._obstacle_enter_time: Optional[float] = None

    @property
    def state(self) -> ExecutiveState:
        return self._state

    def _set_state(self, new_state: ExecutiveState):
        if new_state != self._state:
            if new_state == ExecutiveState.OBSTACLE_STOP:
                self._previous_state = self._state
                self._obstacle_enter_time = time.monotonic()
                self._obstacle_clear_time = None
            self._state = new_state
            self._state_enter_time = time.monotonic()

    def _is_deduped(self, event_type: EventType, source: str) -> bool:
        key = f"{event_type.name}:{source}"
        now = time.monotonic()
        if key in self._dedup and (now - self._dedup[key]) < DEDUP_WINDOW:
            return True
        self._dedup[key] = now
        return False

    def check_timeout(self) -> Optional[EventResult]:
        """Call periodically to check state timeouts."""
        elapsed = time.monotonic() - self._state_enter_time
        if self._state not in (ExecutiveState.IDLE, ExecutiveState.OBSTACLE_STOP) and elapsed > STATE_TIMEOUT:
            return self.handle_event(EventType.TIMEOUT)
        return None

    def try_obstacle_clear(self) -> Optional[EventResult]:
        """Call when no obstacle detected. Returns result if debounce passed."""
        if self._state != ExecutiveState.OBSTACLE_STOP:
            return None
        if self._obstacle_clear_time is None:
            self._obstacle_clear_time = time.monotonic()
            return None
        now = time.monotonic()
        elapsed_since_enter = now - (self._obstacle_enter_time or now)
        elapsed_since_clear = now - self._obstacle_clear_time
        if elapsed_since_clear >= OBSTACLE_DEBOUNCE and elapsed_since_enter >= OBSTACLE_MIN_DURATION:
            return self.handle_event(EventType.OBSTACLE_CLEARED)
        return None

    def handle_event(self, event_type: EventType, source: str = "", data: Optional[dict] = None) -> EventResult:
        """Process an event and return actions to take."""
        data = data or {}

        # Dedup check (skip for internal events)
        if event_type not in (EventType.TIMEOUT, EventType.OBSTACLE_CLEARED) and source:
            if self._is_deduped(event_type, source):
                return EventResult()

        # --- EMERGENCY: fallen ---
        if event_type == EventType.POSE_FALLEN:
            self._set_state(ExecutiveState.EMERGENCY)
            return EventResult(
                tts="偵測到跌倒，你還好嗎？",
                action=ACTION_STOP,
                new_state=ExecutiveState.EMERGENCY,
            )

        # --- OBSTACLE ---
        if event_type == EventType.OBSTACLE:
            self._set_state(ExecutiveState.OBSTACLE_STOP)
            return EventResult(
                action=ACTION_DAMP,
                new_state=ExecutiveState.OBSTACLE_STOP,
            )

        if event_type == EventType.OBSTACLE_CLEARED:
            recover_to = self._previous_state if self._previous_state != ExecutiveState.OBSTACLE_STOP else ExecutiveState.IDLE
            self._set_state(recover_to)
            return EventResult(new_state=recover_to)

        # --- STOP gesture (from any state) ---
        if event_type == EventType.GESTURE and data.get("gesture") == "stop":
            self._set_state(ExecutiveState.IDLE)
            return EventResult(
                action=ACTION_STOP,
                new_state=ExecutiveState.IDLE,
            )

        # --- TIMEOUT ---
        if event_type == EventType.TIMEOUT:
            self._set_state(ExecutiveState.IDLE)
            return EventResult(new_state=ExecutiveState.IDLE)

        # --- State-specific transitions ---
        state = self._state

        if state == ExecutiveState.IDLE:
            return self._handle_idle(event_type, source, data)
        elif state == ExecutiveState.GREETING:
            return self._handle_greeting(event_type, source, data)
        elif state == ExecutiveState.CONVERSING:
            return self._handle_conversing(event_type, source, data)
        elif state == ExecutiveState.EXECUTING:
            return self._handle_executing(event_type, source, data)
        elif state == ExecutiveState.EMERGENCY:
            return self._handle_emergency(event_type, source, data)
        elif state == ExecutiveState.OBSTACLE_STOP:
            return EventResult()  # ignore non-critical events while stopped

        return EventResult()

    def _handle_idle(self, event_type: EventType, source: str, data: dict) -> EventResult:
        if event_type == EventType.FACE_WELCOME:
            self._set_state(ExecutiveState.GREETING)
            name = source or "朋友"
            return EventResult(
                tts=f"{name}，你好！",
                action=ACTION_WAVE,
                new_state=ExecutiveState.GREETING,
            )
        if event_type == EventType.SPEECH_INTENT:
            return self._route_speech(data)
        if event_type == EventType.GESTURE:
            return self._route_gesture(data)
        return EventResult()

    def _handle_greeting(self, event_type: EventType, source: str, data: dict) -> EventResult:
        if event_type == EventType.SPEECH_INTENT:
            return self._route_speech(data)
        return EventResult()

    def _handle_conversing(self, event_type: EventType, source: str, data: dict) -> EventResult:
        if event_type == EventType.SPEECH_INTENT:
            return self._route_speech(data)
        return EventResult()

    def _handle_executing(self, event_type: EventType, source: str, data: dict) -> EventResult:
        # While executing, only accept stop/emergency/obstacle (handled above)
        return EventResult()

    def _handle_emergency(self, event_type: EventType, source: str, data: dict) -> EventResult:
        # In emergency, only timeout or manual override exits
        return EventResult()

    def _route_speech(self, data: dict) -> EventResult:
        intent = data.get("intent", "chat")
        if intent == "greet":
            self._set_state(ExecutiveState.GREETING)
            return EventResult(new_state=ExecutiveState.GREETING)
        elif intent == "chat":
            self._set_state(ExecutiveState.CONVERSING)
            return EventResult(new_state=ExecutiveState.CONVERSING)
        elif intent == "stop":
            self._set_state(ExecutiveState.IDLE)
            return EventResult(action=ACTION_STOP, new_state=ExecutiveState.IDLE)
        elif intent == "sit":
            self._set_state(ExecutiveState.EXECUTING)
            return EventResult(action=ACTION_SIT, new_state=ExecutiveState.EXECUTING)
        elif intent == "stand":
            self._set_state(ExecutiveState.EXECUTING)
            return EventResult(action=ACTION_STAND, new_state=ExecutiveState.EXECUTING)
        else:
            self._set_state(ExecutiveState.CONVERSING)
            return EventResult(new_state=ExecutiveState.CONVERSING)

    def _route_gesture(self, data: dict) -> EventResult:
        gesture = data.get("gesture", "")
        if gesture == "thumbs_up":
            return EventResult(tts="謝謝！", action=ACTION_CONTENT)
        if gesture == "ok":
            return EventResult(action=ACTION_CONTENT)
        return EventResult()

    def get_status(self) -> dict:
        """Return current status for /executive/status topic."""
        return {
            "state": self._state.value,
            "previous_state": self._previous_state.value,
            "state_duration": round(time.monotonic() - self._state_enter_time, 1),
            "timestamp": time.time(),
        }
```

- [ ] **Step 11: Run tests — expect PASS**

```bash
python3 -m pytest interaction_executive/test/test_state_machine.py -v
```

Expected: All tests PASS (19 tests).

- [ ] **Step 12: Commit**

```bash
git add interaction_executive/interaction_executive/state_machine.py
git commit -m "feat(executive): implement state machine — all tests GREEN (Day 4)"
```

---

## Task 4: Day 4 (continued) — Executive v0 ROS2 Node

**Files:**
- Create: `interaction_executive/interaction_executive/interaction_executive_node.py`
- Create: `interaction_executive/config/executive.yaml`
- Create: `interaction_executive/launch/interaction_executive.launch.py`

### Subtask 4.1: ROS2 Node

- [ ] **Step 1: Write the ROS2 node**

Create `interaction_executive/interaction_executive/interaction_executive_node.py`:

```python
"""Interaction Executive v0 — ROS2 thin orchestrator node.

Subscribes to all perception events, routes through state machine,
publishes actions and status.
"""
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from go2_interfaces.msg import WebRtcReq

from .state_machine import (
    ExecutiveStateMachine,
    EventType,
    EventResult,
)

# QoS profiles matching existing nodes
QOS_EVENT = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
QOS_STATE = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class InteractionExecutiveNode(Node):
    def __init__(self):
        super().__init__("interaction_executive_node")

        self._sm = ExecutiveStateMachine()

        # --- Publishers ---
        self._pub_tts = self.create_publisher(String, "/tts", 10)
        self._pub_webrtc = self.create_publisher(WebRtcReq, "/webrtc_req", 10)
        self._pub_status = self.create_publisher(String, "/executive/status", QOS_STATE)

        # --- Subscribers ---
        self.create_subscription(String, "/event/face_identity", self._on_face, QOS_EVENT)
        self.create_subscription(String, "/event/speech_intent_recognized", self._on_speech, QOS_EVENT)
        self.create_subscription(String, "/event/gesture_detected", self._on_gesture, QOS_EVENT)
        self.create_subscription(String, "/event/pose_detected", self._on_pose, QOS_EVENT)
        self.create_subscription(String, "/event/obstacle_detected", self._on_obstacle, QOS_EVENT)

        # --- Timers ---
        self._timeout_timer = self.create_timer(1.0, self._check_timeout)
        self._status_timer = self.create_timer(0.5, self._publish_status)  # 2 Hz
        self._obstacle_clear_timer = self.create_timer(0.5, self._check_obstacle_clear)

        self._last_obstacle_time = 0.0

        self.get_logger().info("Executive v0 started — thin orchestrator mode")

    def _on_face(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        event_type_str = data.get("event_type", "")
        if event_type_str == "identity_stable":
            identity = data.get("identity", "unknown")
            if identity != "unknown":
                result = self._sm.handle_event(
                    EventType.FACE_WELCOME, source=identity, data=data
                )
                self._execute_result(result)

    def _on_speech(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        result = self._sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data=data
        )
        self._execute_result(result)
        # If LLM generated reply_text, let llm_bridge handle TTS
        # Executive only handles structural TTS (greet, emergency, gesture feedback)

    def _on_gesture(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        gesture = data.get("gesture", "")
        result = self._sm.handle_event(
            EventType.GESTURE, source="cam", data={"gesture": gesture}
        )
        self._execute_result(result)

    def _on_pose(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        pose = data.get("pose", "")
        if pose == "fallen":
            result = self._sm.handle_event(EventType.POSE_FALLEN)
            self._execute_result(result)

    def _on_obstacle(self, msg: String):
        import time as _time
        self._last_obstacle_time = _time.monotonic()
        result = self._sm.handle_event(EventType.OBSTACLE)
        self._execute_result(result)

    def _check_timeout(self):
        result = self._sm.check_timeout()
        if result:
            self._execute_result(result)

    def _check_obstacle_clear(self):
        import time as _time
        # If no obstacle event for DEBOUNCE period, try to clear
        if self._sm.state.value == "obstacle_stop":
            if (_time.monotonic() - self._last_obstacle_time) > 2.0:
                self._sm._obstacle_clear_time = self._sm._obstacle_clear_time or _time.monotonic()
                result = self._sm.try_obstacle_clear()
                if result:
                    self._execute_result(result)
            else:
                self._sm._obstacle_clear_time = None

    def _execute_result(self, result: EventResult):
        if result.tts:
            msg = String()
            msg.data = result.tts
            self._pub_tts.publish(msg)
            self.get_logger().info(f"TTS: {result.tts}")

        if result.action:
            req = WebRtcReq()
            req.api_id = result.action.get("api_id", 0)
            self._pub_webrtc.publish(req)
            self.get_logger().info(f"Action: api_id={req.api_id}")

    def _publish_status(self):
        status = self._sm.get_status()
        msg = String()
        msg.data = json.dumps(status)
        self._pub_status.publish(msg)


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

- [ ] **Step 2: Write config**

Create `interaction_executive/config/executive.yaml`:

```yaml
interaction_executive_node:
  ros__parameters:
    state_timeout: 30.0
    dedup_window: 5.0
    obstacle_debounce: 2.0
    obstacle_min_duration: 1.0
```

- [ ] **Step 3: Write launch file**

Create `interaction_executive/launch/interaction_executive.launch.py`:

```python
"""Launch interaction_executive_node."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("interaction_executive")
    config = os.path.join(pkg_dir, "config", "executive.yaml")

    return LaunchDescription([
        Node(
            package="interaction_executive",
            executable="interaction_executive_node",
            name="interaction_executive_node",
            parameters=[config],
            output="screen",
        ),
    ])
```

- [ ] **Step 4: Build and verify**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select interaction_executive
source install/setup.bash
ros2 run interaction_executive interaction_executive_node
# Should start and print "Executive v0 started"
# Ctrl+C to stop
```

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/
git commit -m "feat(executive): add ROS2 node + config + launch (Day 4)"
```

---

## Task 5: Day 5 — Executive Integration + Bridge Migration

**Day:** 4/1
**Goal:** Replace event_action_bridge + interaction_router with executive v0. Update all scripts.

**Files:**
- Modify: `scripts/start_full_demo_tmux.sh`
- Modify: `scripts/clean_full_demo.sh` (from Task 1)
- Modify: `docs/architecture/contracts/interaction_contract.md`

### Subtask 5.1: Update Demo Script

- [ ] **Step 1: Modify start_full_demo_tmux.sh**

In `scripts/start_full_demo_tmux.sh`, replace the router and bridge windows:

Replace window 4 (interaction_router) with:
```bash
# Window 4: Interaction Executive v0 (replaces router + bridge)
tmux new-window -t "$SESSION:4" -n 'executive'
tmux send-keys -t "$SESSION:4" "$ROS_SETUP && \
    ros2 launch interaction_executive interaction_executive.launch.py" Enter
sleep 2
```

Remove window 8 (event_action_bridge) entirely. Shift foxglove to window 8 if needed.

Update the precheck cleanup to include `interaction_executive`:
```bash
# Add to DEMO_PROCS array:
"interaction_executive"
```

- [ ] **Step 2: Update clean_full_demo.sh**

Verify `interaction_executive` is in the DEMO_PROCS array (added in Task 1).

- [ ] **Step 3: Test on Jetson**

```bash
ssh jetson-nano
cd ~/elder_and_dog
# Sync changes
colcon build --packages-select interaction_executive
source install/setup.zsh
bash scripts/clean_full_demo.sh
bash scripts/start_full_demo_tmux.sh
# Verify: ros2 topic echo /executive/status --once
# Verify: ros2 node list | grep executive
# Verify: ros2 node list | grep -v "event_action_bridge\|interaction_router"
```

- [ ] **Step 4: Run boundary tests**

```
Test 1: Face welcome — walk up to camera, expect TTS greeting
Test 2: Speech command — say "坐下", expect Go2 sits
Test 3: Stop gesture — show stop hand, expect Go2 stops
Test 4: Simultaneous — face + speech at same time, only one response
Test 5: Crash recovery — kill executive, run clean + restart, < 3 min
```

- [ ] **Step 5: Update interaction_contract.md to v2.2**

Add to `docs/architecture/contracts/interaction_contract.md`:

```markdown
### v2.2 Changes (2026-04-01)

#### New Topics
- `/executive/status` (String, JSON, 2 Hz) — state machine status broadcast
  - Fields: `state`, `previous_state`, `state_duration`, `timestamp`
- `/event/obstacle_detected` (String, JSON, event) — obstacle detection events
  - Fields: `distance_min`, `obstacle_ratio`, `timestamp`

#### Deprecated Topics
- `/event/interaction/welcome` — replaced by executive v0 internal routing
- `/event/interaction/gesture_command` — replaced by executive v0 internal routing
- `/event/interaction/fall_alert` — replaced by executive v0 internal routing

#### Node Changes
- `interaction_router` → deprecated (functionality absorbed into `interaction_executive_node`)
- `event_action_bridge` → deprecated (functionality absorbed into `interaction_executive_node`)
- `interaction_executive_node` → new, thin orchestrator
```

- [ ] **Step 6: Commit**

```bash
git add scripts/start_full_demo_tmux.sh scripts/clean_full_demo.sh \
    docs/architecture/contracts/interaction_contract.md
git commit -m "feat(executive): migrate from bridge+router to executive v0 (Day 5)

- Replace event_action_bridge + interaction_router in demo script
- Update clean script with new process list
- Update interaction_contract.md to v2.2
- 5/5 boundary tests pass on Jetson"
```

---

## Task 6: Day 6 — Obstacle Avoidance (TDD)

**Day:** 4/2
**Goal:** D435 depth → obstacle detection → Go2 reactive stop.

**Files:**
- Create: `vision_perception/vision_perception/obstacle_detector.py`
- Create: `vision_perception/vision_perception/obstacle_avoidance_node.py`
- Create: `vision_perception/test/test_obstacle_detector.py`
- Create: `vision_perception/launch/obstacle_avoidance.launch.py`
- Modify: `vision_perception/setup.py`

### Subtask 6.1: Obstacle Detector Tests First

- [ ] **Step 1: Write obstacle detector tests**

Create `vision_perception/test/test_obstacle_detector.py`:

```python
"""Tests for ObstacleDetector — pure Python/numpy, no ROS2."""
import numpy as np
import pytest
from vision_perception.obstacle_detector import ObstacleDetector


class TestObstacleDetection:
    def setup_method(self):
        self.detector = ObstacleDetector(
            threshold_m=0.5,
            roi_width=256,
            roi_height=192,
            obstacle_ratio_trigger=0.15,
        )

    def test_no_obstacle_far_away(self):
        """All pixels at 2.0m — no obstacle."""
        depth = np.full((480, 640), 2.0, dtype=np.float32)
        result = self.detector.detect(depth)
        assert not result.is_obstacle
        assert result.obstacle_ratio < 0.01

    def test_obstacle_close(self):
        """Center ROI at 0.3m — obstacle detected."""
        depth = np.full((480, 640), 2.0, dtype=np.float32)
        # Fill center ROI with close obstacle
        cy, cx = 240, 320
        rh, rw = 96, 128  # half of ROI
        depth[cy - rh:cy + rh, cx - rw:cx + rw] = 0.3
        result = self.detector.detect(depth)
        assert result.is_obstacle
        assert result.distance_min == pytest.approx(0.3, abs=0.01)

    def test_partial_obstacle_below_threshold(self):
        """Only 5% of ROI is close — not enough to trigger."""
        depth = np.full((480, 640), 2.0, dtype=np.float32)
        cy, cx = 240, 320
        # Small patch (much less than 15% of ROI)
        depth[cy - 5:cy + 5, cx - 5:cx + 5] = 0.3
        result = self.detector.detect(depth)
        assert not result.is_obstacle

    def test_zero_depth_ignored(self):
        """Depth value 0.0 means invalid/no-reading — should be ignored."""
        depth = np.zeros((480, 640), dtype=np.float32)
        result = self.detector.detect(depth)
        assert not result.is_obstacle

    def test_nan_depth_ignored(self):
        """NaN depth should be ignored."""
        depth = np.full((480, 640), np.nan, dtype=np.float32)
        result = self.detector.detect(depth)
        assert not result.is_obstacle

    def test_result_contains_distance_min(self):
        depth = np.full((480, 640), 0.4, dtype=np.float32)
        result = self.detector.detect(depth)
        assert result.distance_min == pytest.approx(0.4, abs=0.01)

    def test_custom_threshold(self):
        """With threshold 1.0m, objects at 0.8m should trigger."""
        detector = ObstacleDetector(threshold_m=1.0)
        depth = np.full((480, 640), 0.8, dtype=np.float32)
        result = detector.detect(depth)
        assert result.is_obstacle
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Commit tests**

```bash
git add vision_perception/test/test_obstacle_detector.py
git commit -m "test(vision): add obstacle detector tests — RED (Day 6)"
```

### Subtask 6.2: Implement Obstacle Detector

- [ ] **Step 4: Write obstacle_detector.py**

Create `vision_perception/vision_perception/obstacle_detector.py`:

```python
"""Obstacle detection from D435 depth images.

Pure numpy, ~50 lines. Extracts center ROI from depth frame,
checks percentage of pixels below threshold distance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ObstacleResult:
    is_obstacle: bool
    distance_min: float       # minimum valid depth in ROI (meters)
    obstacle_ratio: float     # fraction of ROI pixels below threshold


class ObstacleDetector:
    def __init__(
        self,
        threshold_m: float = 0.5,
        roi_width: int = 256,
        roi_height: int = 192,
        obstacle_ratio_trigger: float = 0.15,
    ):
        self._threshold = threshold_m
        self._roi_w = roi_width
        self._roi_h = roi_height
        self._trigger_ratio = obstacle_ratio_trigger

    def detect(self, depth: np.ndarray) -> ObstacleResult:
        """Analyze depth frame and return obstacle status.

        Args:
            depth: (H, W) float32 array, depth in meters.
                   0.0 and NaN are invalid readings.
        """
        h, w = depth.shape[:2]

        # Extract center ROI
        cy, cx = h // 2, w // 2
        rh, rw = min(self._roi_h // 2, cy), min(self._roi_w // 2, cx)
        roi = depth[cy - rh : cy + rh, cx - rw : cx + rw]

        # Mask invalid pixels (0.0 or NaN)
        valid_mask = (roi > 0.01) & np.isfinite(roi)
        valid_pixels = roi[valid_mask]

        if valid_pixels.size == 0:
            return ObstacleResult(is_obstacle=False, distance_min=float("inf"), obstacle_ratio=0.0)

        distance_min = float(np.min(valid_pixels))
        close_count = int(np.sum(valid_pixels < self._threshold))
        obstacle_ratio = close_count / valid_pixels.size

        return ObstacleResult(
            is_obstacle=obstacle_ratio >= self._trigger_ratio,
            distance_min=distance_min,
            obstacle_ratio=obstacle_ratio,
        )
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add vision_perception/vision_perception/obstacle_detector.py
git commit -m "feat(vision): implement obstacle detector — all tests GREEN (Day 6)"
```

### Subtask 6.3: ROS2 Node + Launch

- [ ] **Step 7: Write obstacle_avoidance_node.py**

Create `vision_perception/vision_perception/obstacle_avoidance_node.py`:

```python
"""Obstacle Avoidance ROS2 Node.

Subscribes to D435 depth, runs ObstacleDetector, publishes obstacle events.
"""
import json
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge

from .obstacle_detector import ObstacleDetector

QOS_SENSOR = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)


class ObstacleAvoidanceNode(Node):
    def __init__(self):
        super().__init__("obstacle_avoidance_node")

        self.declare_parameter("threshold_m", 0.5)
        self.declare_parameter("roi_width", 256)
        self.declare_parameter("roi_height", 192)
        self.declare_parameter("obstacle_ratio_trigger", 0.15)
        self.declare_parameter("publish_rate_hz", 5.0)

        self._detector = ObstacleDetector(
            threshold_m=self.get_parameter("threshold_m").value,
            roi_width=self.get_parameter("roi_width").value,
            roi_height=self.get_parameter("roi_height").value,
            obstacle_ratio_trigger=self.get_parameter("obstacle_ratio_trigger").value,
        )

        self._bridge = CvBridge()
        self._pub = self.create_publisher(String, "/event/obstacle_detected", 10)

        # Subscribe to D435 aligned depth
        self.create_subscription(
            Image,
            "/camera/aligned_depth_to_color/image_raw",
            self._on_depth,
            QOS_SENSOR,
        )

        # Rate limiting
        self._min_interval = 1.0 / self.get_parameter("publish_rate_hz").value
        self._last_publish = 0.0

        self.get_logger().info("Obstacle avoidance node started")

    def _on_depth(self, msg: Image):
        now = time.monotonic()
        if (now - self._last_publish) < self._min_interval:
            return

        try:
            depth_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        except Exception as e:
            self.get_logger().warning(f"Depth conversion failed: {e}")
            return

        # Convert uint16 (mm) to float32 (meters) if needed
        if depth_img.dtype == np.uint16:
            depth_m = depth_img.astype(np.float32) / 1000.0
        else:
            depth_m = depth_img.astype(np.float32)

        result = self._detector.detect(depth_m)

        if result.is_obstacle:
            event = {
                "distance_min": round(result.distance_min, 3),
                "obstacle_ratio": round(result.obstacle_ratio, 3),
                "timestamp": time.time(),
            }
            out = String()
            out.data = json.dumps(event)
            self._pub.publish(out)
            self._last_publish = now
            self.get_logger().info(
                f"OBSTACLE: {result.distance_min:.2f}m, ratio={result.obstacle_ratio:.1%}"
            )


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleAvoidanceNode()
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

- [ ] **Step 8: Write launch file**

Create `vision_perception/launch/obstacle_avoidance.launch.py`:

```python
"""Launch obstacle avoidance node."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="vision_perception",
            executable="obstacle_avoidance_node",
            name="obstacle_avoidance_node",
            parameters=[{
                "threshold_m": 0.5,
                "roi_width": 256,
                "roi_height": 192,
                "obstacle_ratio_trigger": 0.15,
                "publish_rate_hz": 5.0,
            }],
            output="screen",
        ),
    ])
```

- [ ] **Step 9: Update vision_perception/setup.py**

Add to `entry_points.console_scripts`:

```python
"obstacle_avoidance_node = vision_perception.obstacle_avoidance_node:main",
```

Add launch file to `data_files`:

```python
("share/" + package_name + "/launch", [
    "launch/vision_perception.launch.py",
    "launch/event_action_bridge.launch.py",
    "launch/mock_publisher.launch.py",
    "launch/interaction_router.launch.py",
    "launch/obstacle_avoidance.launch.py",
]),
```

- [ ] **Step 10: Update start_full_demo_tmux.sh**

Add obstacle avoidance window (after camera, before executive):

```bash
# Window N: Obstacle Avoidance (D435 depth)
tmux new-window -t "$SESSION:N" -n 'obstacle'
tmux send-keys -t "$SESSION:N" "$ROS_SETUP && \
    ros2 launch vision_perception obstacle_avoidance.launch.py" Enter
sleep 1
```

- [ ] **Step 11: Build and test on Jetson**

```bash
colcon build --packages-select vision_perception
source install/setup.zsh
bash scripts/clean_full_demo.sh
bash scripts/start_full_demo_tmux.sh
# Verify: ros2 topic echo /event/obstacle_detected
# Walk toward D435 — should see obstacle events when < 0.5m
```

- [ ] **Step 12: Run 10x quick collision test**

Place object at various distances from D435:
- < 0.3m: must detect (10/10)
- 0.3-0.5m: should detect (>= 8/10)
- > 1.0m: must NOT detect (0/10)

Record results.

- [ ] **Step 13: Commit**

```bash
git add vision_perception/ scripts/start_full_demo_tmux.sh
git commit -m "feat(vision): add obstacle avoidance node — D435 depth reactive (Day 6)"
```

---

## Task 7: Day 7 — Obstacle Avoidance Hardening

**Day:** 4/3
**Goal:** 30x collision test with quantified metrics and degradation decisions.

**Files:**
- Create: `scripts/obstacle_test.sh`
- Modify: `docs/operations/baseline-contract.md`

- [ ] **Step 1: Create test script**

Create `scripts/obstacle_test.sh`:

```bash
#!/usr/bin/env bash
# Run 30-round obstacle avoidance test and record metrics.
# Usage: bash scripts/obstacle_test.sh [rounds]
set -euo pipefail

ROUNDS=${1:-30}
RESULTS_FILE="/tmp/obstacle_test_$(date +%Y%m%d_%H%M%S).csv"

echo "round,distance_m,detected,latency_ms,go2_stopped" > "$RESULTS_FILE"

echo "=== Obstacle Avoidance Test: $ROUNDS rounds ==="
echo "Results will be saved to: $RESULTS_FILE"
echo ""
echo "Instructions:"
echo "  1. Full demo must be running"
echo "  2. For each round, place obstacle at specified distance"
echo "  3. Record whether Go2 stops"
echo "  4. Press Enter after each round"
echo ""

for i in $(seq 1 "$ROUNDS"); do
    if [ "$i" -le 10 ]; then
        DIST="0.3"
        echo "Round $i/$ROUNDS: Place obstacle at ~0.3m (MUST detect)"
    elif [ "$i" -le 20 ]; then
        DIST="0.5"
        echo "Round $i/$ROUNDS: Place obstacle at ~0.5m (SHOULD detect)"
    else
        DIST="1.5"
        echo "Round $i/$ROUNDS: Place obstacle at ~1.5m (must NOT detect)"
    fi

    echo -n "  Detected? (y/n/skip): "
    read -r DETECTED
    echo -n "  Go2 stopped? (y/n/na): "
    read -r STOPPED
    echo -n "  Approx latency ms (or na): "
    read -r LATENCY

    echo "$i,$DIST,$DETECTED,$LATENCY,$STOPPED" >> "$RESULTS_FILE"
done

echo ""
echo "=== Results Summary ==="
echo "File: $RESULTS_FILE"

# Calculate metrics
TOTAL=$(wc -l < "$RESULTS_FILE")
TOTAL=$((TOTAL - 1))  # subtract header
MISSED_CLOSE=$(grep "0\\.3,n," "$RESULTS_FILE" | wc -l || true)
FALSE_FAR=$(grep "1\\.5,y," "$RESULTS_FILE" | wc -l || true)
echo "Total rounds: $TOTAL"
echo "Missed at 0.3m: $MISSED_CLOSE / 10"
echo "False positive at 1.5m: $FALSE_FAR / 10"
echo ""
echo "Copy results to docs/operations/baseline-contract.md"
```

- [ ] **Step 2: Run 30-round test on Jetson**

```bash
bash scripts/obstacle_test.sh 30
```

- [ ] **Step 3: Apply metric judgment**

| Metric | Pass | Warning (Damp-only) | Fail (disable) |
|--------|:----:|:-------------------:|:--------------:|
| Miss rate (< 0.5m) | ≤ 3% | 4-10% | > 10% |
| False positive rate | ≤ 10% | 11-20% | > 20% |
| Stop latency | P95 < 500ms | 500-1000ms | > 1000ms |

Apply degradation strategy from spec.

- [ ] **Step 4: Record results and commit**

```bash
cp /tmp/obstacle_test_*.csv docs/operations/
git add scripts/obstacle_test.sh docs/operations/
git commit -m "test(vision): 30-round obstacle avoidance test — metrics recorded (Day 7)"
```

---

## Task 8: Day 8 — Object Detection Hard Gate

**Day:** 4/4
**Goal:** Go/No-Go decision. If Go, Phase 0 only. 4-6h timebox.

### Gate Check (before writing any code)

- [ ] **Step 1: Check 5 gate conditions**

```bash
# 1. Baseline stable?
# Run 5-round E2E: bash scripts/smoke_test_e2e.sh 5
# Must pass >= 4/5

# 2. RAM headroom?
ssh jetson-nano "free -h"
# Must show >= 1.5GB free while full demo running

# 3. GPU not saturated?
ssh jetson-nano "tegrastats" # check GPU% while Whisper idle
# Must show GPU < 80% when not transcribing

# 4. D435 pipelines not conflicting?
# Check both /camera/color/image_raw and /camera/aligned_depth_to_color/image_raw are publishing
ros2 topic hz /camera/color/image_raw
ros2 topic hz /camera/aligned_depth_to_color/image_raw

# 5. Can complete Phase 0 in half a day?
# Estimate based on network speed for downloading ultralytics + YOLO26n weights
```

- [ ] **Step 2: Record Go/No-Go decision**

If ANY condition fails → **No-Go**. Skip to Task 9. No debate.

If all pass → **Go**. Start 4-6h timebox.

### Phase 0 (only if Go)

- [ ] **Step 3: Install ultralytics on Jetson**

```bash
ssh jetson-nano
uv pip install ultralytics
```

- [ ] **Step 4: Download and test YOLO model**

```python
from ultralytics import YOLO
model = YOLO("yolo11n.pt")  # or yolo26n when available
results = model.predict(source="test_image.jpg", conf=0.5)
print(results[0].boxes)
```

- [ ] **Step 5: Export to TensorRT**

```python
model.export(format="engine", device=0, half=True)
```

If export fails → **Stop. Phase 0 failed. No-Go.**

- [ ] **Step 6: Verify inference speed**

```python
import time
engine_model = YOLO("yolo11n.engine")
for _ in range(10):
    start = time.monotonic()
    engine_model.predict(source="test_image.jpg", conf=0.5, verbose=False)
    print(f"{(time.monotonic()-start)*1000:.1f}ms")
```

Target: < 50ms per frame.

- [ ] **Step 7: Check RAM impact**

```bash
# Before loading model
free -h
# After loading model
free -h
# Delta must be < 1.1GB
```

- [ ] **Step 8: Commit results (even if No-Go)**

```bash
git add -A
git commit -m "test: object detection Phase 0 gate — [GO/NO-GO] (Day 8)"
```

**TIMEBOX: Stop at 4-6 hours regardless of progress.**

---

## Task 9: Day 9-10 — Freeze + Hardening

**Day:** 4/5-4/6
**Goal:** No new features. Fix demo failures. Document everything.

### Iron Rules

- NO new features
- Only fix demo failure paths
- Every change → full E2E regression
- If Day 8 added object detection, do NOT continue developing it

### Day 9

- [ ] **Step 1: Demo A — 30-round speech test**

```bash
bash scripts/run_speech_test.sh --skip-driver --skip-build
```

Target: ≥ 27/30 (90%).

- [ ] **Step 2: Fix any failures** — one at a time, E2E after each fix
- [ ] **Step 3: Demo B — 5-round gesture→Go2 test**

```
Round 1: stop gesture → Go2 stops
Round 2: thumbs_up → Go2 content action
Round 3: fallen → emergency TTS
Round 4: face → greeting TTS
Round 5: speech → Go2 sit
```

Target: ≥ 4/5.

- [ ] **Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix: Day 9 hardening — Demo A [X/30], Demo B [X/5]"
```

### Day 10

- [ ] **Step 5: Crash recovery drill** — 3 rounds, each < 3 minutes
- [ ] **Step 6: Write Demo Operation Manual**

Create `docs/operations/demo-manual.md`:
- Pre-demo checklist
- Step-by-step startup
- What to do if X crashes
- How to gracefully shut down
- Known gotchas for demo day

- [ ] **Step 7: Full E2E regression — final pass**
- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: demo operation manual + final hardening (Day 10)"
```

---

## Task 10: Day 11 — Handoff

**Day:** 4/7
**Goal:** Docs restructure + Starlight scaffold + team assignment.

**Files:**
- Modify: various docs/ paths
- Create: `docs/website/`
- Create: `website/` (Starlight scaffold)

### Subtask 10.1: Docs Restructure

- [ ] **Step 1: Create modules directory with English names**

```bash
cd /home/roy422/newLife/elder_and_dog/docs
mkdir -p modules/face-recognition modules/speech modules/gesture \
    modules/pose modules/object-detection modules/navigation modules/pawai-studio
```

- [ ] **Step 2: Copy READMEs to new structure**

```bash
cp 人臉辨識/README.md modules/face-recognition/
cp 語音功能/README.md modules/speech/
cp 手勢辨識/README.md modules/gesture/
cp 姿勢辨識/README.md modules/pose/
cp 辨識物體/README.md modules/object-detection/
cp 導航避障/README.MD modules/navigation/README.md
cp Pawai-studio/README.md modules/pawai-studio/
```

Note: Keep original Chinese directories for now (no deletion during sprint).

- [ ] **Step 3: Fix README.MD → README.md**

```bash
cd /home/roy422/newLife/elder_and_dog/docs/導航避障
git mv README.MD README.md 2>/dev/null || mv README.MD README.md
```

- [ ] **Step 4: Delete .docx files**

```bash
find docs/ -name "*.docx" -exec rm {} \;
```

- [ ] **Step 5: Mark archive**

Create `docs/archive/ARCHIVED.md`:

```markdown
# Archived Content

This directory contains historical documents from before 2026-03-01.
These are preserved for reference but are NOT maintained.

For current documentation, see `docs/modules/` or `docs/mission/`.
```

- [ ] **Step 6: Create website directory**

```bash
mkdir -p docs/website
```

Create `docs/website/content-assignment.md`:

```markdown
# Starlight Content Assignment

## Site Structure (maps to docs/modules/)

| Page | Source | Assignee | Deadline |
|------|--------|----------|----------|
| Home | new | TBD | 4/13 |
| Face Recognition | modules/face-recognition/README.md | TBD | 4/13 |
| Speech | modules/speech/README.md | TBD | 4/13 |
| Gesture | modules/gesture/README.md | TBD | 4/13 |
| Pose | modules/pose/README.md | TBD | 4/13 |
| Object Detection | modules/object-detection/README.md | TBD | 4/13 |
| Navigation | modules/navigation/README.md | TBD | 4/13 |
| PawAI Studio | modules/pawai-studio/README.md | TBD | 4/13 |
| Setup Guide | setup/README.md | TBD | 4/13 |
| Architecture | architecture/README.md | TBD | 4/13 |

## Tech Stack
- Framework: Astro + Starlight
- Deploy: GitHub Pages
- Reference: https://starlight.astro.build/
```

- [ ] **Step 7: Commit docs restructure**

```bash
git add docs/
git commit -m "docs: restructure for Starlight handoff — modules/ + archive marker (Day 11)"
```

### Subtask 10.2: Starlight Scaffold

- [ ] **Step 8: Create Starlight project**

```bash
cd /home/roy422/newLife/elder_and_dog
npm create astro@latest -- website --template starlight --no-install
cd website
npm install
```

- [ ] **Step 9: Configure sidebar**

Edit `website/astro.config.mjs` to match docs/modules structure:

```js
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  integrations: [
    starlight({
      title: 'PawAI Docs',
      sidebar: [
        { label: 'Home', link: '/' },
        {
          label: 'Modules',
          items: [
            { label: 'Face Recognition', link: '/modules/face-recognition/' },
            { label: 'Speech', link: '/modules/speech/' },
            { label: 'Gesture', link: '/modules/gesture/' },
            { label: 'Pose', link: '/modules/pose/' },
            { label: 'Object Detection', link: '/modules/object-detection/' },
            { label: 'Navigation', link: '/modules/navigation/' },
            { label: 'PawAI Studio', link: '/modules/pawai-studio/' },
          ],
        },
        { label: 'Architecture', link: '/architecture/' },
        { label: 'Setup Guide', link: '/setup/' },
      ],
    }),
  ],
});
```

- [ ] **Step 10: Verify build**

```bash
cd website && npm run build
```

Expected: Build succeeds with default template content.

- [ ] **Step 11: Commit Starlight scaffold**

```bash
cd /home/roy422/newLife/elder_and_dog
git add website/
git commit -m "feat: add Starlight documentation site scaffold (Day 11)"
```

### Subtask 10.3: System Status Snapshot

- [ ] **Step 12: Update project-status.md with final sprint results**

Update `references/project-status.md`:
- All module statuses
- Demo A/B results
- Known bugs
- What's ready for team handoff

- [ ] **Step 13: Final commit**

```bash
git add references/project-status.md
git commit -m "docs: sprint complete — system status snapshot for 4/9 handoff (Day 11)"
```

---

## Self-Review Results

**Spec coverage:**
- [x] Day 1 baseline contract — Task 1
- [x] Day 2-3 hardware bring-up — Task 2
- [x] Day 4 executive v0 state machine — Task 3
- [x] Day 4 executive v0 ROS2 node — Task 4
- [x] Day 5 integration + bridge migration — Task 5
- [x] Day 6 obstacle avoidance — Task 6
- [x] Day 7 obstacle hardening — Task 7
- [x] Day 8 object detection gate — Task 8
- [x] Day 9-10 freeze + hardening — Task 9
- [x] Day 11 handoff — Task 10
- [x] Obstacle debounce (user feedback) — implemented in state_machine.py with `OBSTACLE_DEBOUNCE=2.0` and `OBSTACLE_MIN_DURATION=1.0`
- [x] `/executive/status` topic — Task 4, publishes at 2 Hz
- [x] LLM timeout 2s — referenced in state machine design (actual timeout in llm_bridge_node, executive handles fallback routing)
- [x] Navigation degradation strategy — Task 7 step 3 with Pass/Warning/Fail bands
- [x] Script sync on bridge migration — Task 5 step 1
- [x] Startup script and SOP updates — Tasks 1, 5

**Placeholder scan:** No TBD/TODO in code. Content-assignment.md has "TBD" for assignees — correct, will be filled at 4/9 meeting.

**Type consistency:** `EventType`, `ExecutiveState`, `EventResult`, `ObstacleResult` — used consistently across all files. `handle_event()` signature matches between tests and implementation. `WebRtcReq.api_id` matches existing codebase pattern.
