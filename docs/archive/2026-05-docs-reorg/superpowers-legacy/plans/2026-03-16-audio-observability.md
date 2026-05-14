# Audio Pipeline Observability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Go2 audio playback observable — see Go2's responses, audiohub state, and detect playback failures instead of blindly trusting "send success".

**Architecture:** Add message classification + ConnectionHealth tracking in `go2_connection.py`, subscribe audiohub state in `webrtc_adapter.py`, publish health via `go2_driver_node`, and provide a layered diagnostic shell script.

**Tech Stack:** Python 3.10, ROS2 Humble, asyncio, WebRTC DataChannel, std_msgs/String JSON

**Spec:** `docs/superpowers/specs/2026-03-16-audio-observability-design.md` v1.2

---

## PR Structure

| PR | Scope | Files | Depends on |
|----|-------|-------|------------|
| PR-1 | B-lite core: message classification + audiohub subscribe + bufferedAmount | go2_connection.py, webrtc_adapter.py, constants/__init__.py | — |
| PR-2 | Diagnostics: layered audio diagnosis script | scripts/diagnose_audio.sh | — |
| PR-3 | B-full: /state/connection/go2 topic + playback confirmation | go2_driver_node.py, webrtc_adapter.py | PR-1 |

---

## Chunk 1: PR-1 — B-lite Core Observability

### Task 1: Export AUDIO_HUB_COMMANDS from constants

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/domain/constants/__init__.py:1-7`

- [ ] **Step 1: Add AUDIO_HUB_COMMANDS export**

```python
from .robot_commands import ROBOT_CMD
from .webrtc_topics import RTC_TOPIC, DATA_CHANNEL_TYPE, AUDIO_HUB_COMMANDS

__all__ = ['ROBOT_CMD', 'RTC_TOPIC', 'DATA_CHANNEL_TYPE', 'AUDIO_HUB_COMMANDS']
```

- [ ] **Step 2: Verify import works**

Run: `cd /home/jetson/elder_and_dog && python3 -c "from go2_robot_sdk.domain.constants import AUDIO_HUB_COMMANDS; print(AUDIO_HUB_COMMANDS)"`

Expected: `{'START_AUDIO': 4001, 'STOP_AUDIO': 4002, 'SEND_AUDIO_BLOCK': 4003, 'SET_VOLUME': 4004, 'GET_AUDIO_STATUS': 4005}`

- [ ] **Step 3: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/domain/constants/__init__.py
git commit -m "feat(go2): export AUDIO_HUB_COMMANDS from constants"
```

---

### Task 2: Add ConnectionHealth dataclass to go2_connection.py

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py:1-25` (imports)
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py` (add dataclass before Go2Connection class)

- [ ] **Step 1: Add imports and ConnectionHealth dataclass**

Add after existing imports (around line 25), before `class Go2Connection`:

```python
import threading
import time as _time
from dataclasses import dataclass, replace as _dc_replace

@dataclass
class ConnectionHealth:
    """Thread-safe health snapshot for Go2 WebRTC connection."""
    dc_state: str = "closed"
    connection_state: str = "new"
    validated: bool = False
    last_response_ts: float = 0.0
    last_heartbeat_ts: float = 0.0
    last_msg_type: str = ""
    last_audio_state: str = "unknown"
    last_audio_state_ts: float = 0.0
    error_count: int = 0
    last_error: str = ""
    connected_at: float = 0.0
```

- [ ] **Step 2: Initialize health and lock in Go2Connection.__init__**

Add in `__init__` (around line 50, after other instance vars):

```python
self._health = ConnectionHealth()
self._health_lock = threading.Lock()
```

- [ ] **Step 3: Add health property (returns thread-safe copy)**

Add as method on Go2Connection class:

```python
@property
def health(self) -> ConnectionHealth:
    with self._health_lock:
        return _dc_replace(self._health)
```

- [ ] **Step 4: Update health on connection state changes**

In `on_data_channel_open` (line 123), add:

```python
with self._health_lock:
    self._health.dc_state = "open"
    self._health.connected_at = _time.time()
```

In `on_data_channel_close` (line 115), add:

```python
with self._health_lock:
    self._health.dc_state = "closed"
```

In existing `validate_robot_conn` success path, add:

```python
with self._health_lock:
    self._health.validated = True
```

- [ ] **Step 5: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py
git commit -m "feat(go2): add ConnectionHealth dataclass with thread-safe access"
```

---

### Task 3: Rewrite on_data_channel_message with full classification

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py:138-171`

- [ ] **Step 1: Rewrite on_data_channel_message**

Replace lines 138-171 with:

```python
def on_data_channel_message(self, message: Union[str, bytes]) -> None:
    """Receive and classify all Go2 DataChannel messages."""
    # Binary messages — existing logic unchanged
    if isinstance(message, bytes):
        logger.debug("Received binary message (%d bytes)", len(message))
        msgobj = legacy_deal_array_buffer(message, perform_decode=self.decode_lidar)
        if self.on_message:
            try:
                self.on_message(message, msgobj, self.robot_num)
            except Exception as e:
                logger.warning(f"[GO2 CALLBACK] on_message failed for binary: {e}")
        return

    # String messages — parse JSON with defense
    try:
        msgobj = json.loads(message)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"[GO2 PARSE] Bad JSON from Go2: {e}")
        return

    msg_type = msgobj.get("type", "unknown")
    topic = msgobj.get("topic", "")
    data = msgobj.get("data", {})

    # --- Classify and log by msg_type ---
    if msg_type == "validation":
        # Existing validation logic — don't touch
        self.validate_robot_conn(msgobj)
    elif msg_type == "response":
        header = data.get("header", {}) if isinstance(data, dict) else {}
        api_id = header.get("identity", {}).get("api_id", 0)
        # Try data.data.code first, fallback data.code
        inner = data.get("data", {}) if isinstance(data, dict) else {}
        code = inner.get("code") if isinstance(inner, dict) else None
        if code is None and isinstance(data, dict):
            code = data.get("code")
        logger.info(f"[GO2 RESPONSE] api_id={api_id} code={code} topic={topic}")
        with self._health_lock:
            self._health.last_response_ts = _time.time()
            self._health.last_msg_type = "response"
    elif msg_type == "heartbeat":
        logger.debug(f"[GO2 HEARTBEAT] topic={topic}")
        with self._health_lock:
            self._health.last_heartbeat_ts = _time.time()
            self._health.last_msg_type = "heartbeat"
    elif msg_type in ("errors", "err"):
        logger.warning(f"[GO2 ERROR] type={msg_type} data={data}")
        with self._health_lock:
            self._health.error_count += 1
            self._health.last_error = str(data)[:200]
            self._health.last_msg_type = msg_type
    else:
        logger.debug(f"[GO2 MSG] type={msg_type} topic={topic}")

    # --- Independent topic check (not elif — can overlap with msg_type) ---
    if topic == RTC_TOPIC.get("AUDIO_HUB_PLAY_STATE", ""):
        audio_data = data.get("data", data) if isinstance(data, dict) else data
        logger.info(f"[GO2 AUDIO STATE] {audio_data}")
        with self._health_lock:
            self._health.last_audio_state = str(audio_data)
            self._health.last_audio_state_ts = _time.time()

    # --- Forward to callback (protected) ---
    if self.on_message:
        try:
            self.on_message(message, msgobj, self.robot_num)
        except Exception as e:
            logger.warning(f"[GO2 CALLBACK] on_message failed: {e}")
```

Note: `legacy_deal_array_buffer` is a module-level function (not a method on self), and `validate_robot_conn` is the existing method on Go2Connection. Also preserve the existing `data_channel.readyState` check from the original code.

- [ ] **Step 2: Verify no syntax errors**

Run: `python3 -c "from go2_robot_sdk.infrastructure.webrtc.go2_connection import Go2Connection, ConnectionHealth; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py
git commit -m "feat(go2): classify all Go2 messages and update ConnectionHealth"
```

---

### Task 4: Subscribe AUDIO_HUB_PLAY_STATE + bufferedAmount monitoring

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py:13` (imports)
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py:211-224` (_on_validated subscription list)
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py:133-152` (_async_send_command)

- [ ] **Step 1: Update imports**

Change line 13 from:
```python
from ...domain.constants import ROBOT_CMD, RTC_TOPIC
```
to:
```python
from ...domain.constants import ROBOT_CMD, RTC_TOPIC, AUDIO_HUB_COMMANDS
```

- [ ] **Step 2: Add audiohub state to subscription list**

In `_on_validated` method (around line 211-224), find the `subscription_topics` list and append:

```python
subscription_topics.append(RTC_TOPIC["AUDIO_HUB_PLAY_STATE"])
```

- [ ] **Step 3: Replace AUDIO DEBUG code with bufferedAmount monitoring**

Replace the existing AUDIO DEBUG block (lines 139-148) in `_async_send_command` with:

```python
# Get DataChannel and send
dc = conn.data_channel
state = dc.readyState if dc else "no_dc"

if dc and state == "open":
    buffered_before = getattr(dc, 'bufferedAmount', None)
    dc.send(command)
    buffered_after = getattr(dc, 'bufferedAmount', None)

    # Parse api_id for audio command logging
    # Command structure: {"data": {"header": {"identity": {"api_id": ...}}}}
    try:
        _cmd = json.loads(command) if isinstance(command, str) else {}
        _api = _cmd.get("data", {}).get("header", {}).get("identity", {}).get("api_id", 0)
    except (json.JSONDecodeError, AttributeError):
        _api = 0

    # Detailed log for audio commands
    _audio_ids = set(AUDIO_HUB_COMMANDS.values())
    if _api in _audio_ids:
        _payload_len = len(command) if isinstance(command, (bytes, str)) else "?"
        logger.info(
            f"[AUDIO DEBUG] dc_state={state} api_id={_api} "
            f"payload_len={_payload_len} buffered={buffered_before}→{buffered_after}"
        )

    # Buffer backlog alerts
    if buffered_after is not None:
        if buffered_after > 512_000:
            logger.error(f"[DC BUFFER] bufferedAmount={buffered_after} — CRITICAL backlog")
        elif buffered_after > 64_000:
            logger.warning(f"[DC BUFFER] bufferedAmount={buffered_after} — backlogged")
else:
    logger.warning(f"[DC SEND] Cannot send: dc_state={state}")
```

**Important:** Preserve the existing logic that surrounds this block. The above replaces only the send + debug log portion inside `_async_send_command`. Keep any existing try/except and return logic.

- [ ] **Step 4: Build and verify**

```bash
cd /home/jetson/elder_and_dog
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
```

- [ ] **Step 5: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py
git commit -m "feat(go2): subscribe audiohub state + bufferedAmount monitoring"
```

---

### Task 5: Verify PR-1 end-to-end

- [ ] **Step 1: Restart driver and check logs**

```bash
# Kill existing session and restart
bash scripts/clean_speech_env.sh
# Start driver only
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

- [ ] **Step 2: Send a TTS test and check driver log for new messages**

```bash
# In another terminal
ros2 topic pub --once /tts std_msgs/msg/String '{data: "observability test"}'
```

Look for in driver log:
- `[GO2 RESPONSE]` — Go2's response to commands
- `[GO2 HEARTBEAT]` — Go2 heartbeat (debug level)
- `[GO2 AUDIO STATE]` — audiohub player state
- `[AUDIO DEBUG] ... buffered=` — bufferedAmount values
- `[GO2 ERROR]` — any errors from Go2

- [ ] **Step 3: Document what you see**

If `[GO2 AUDIO STATE]` shows data → we now know Go2's playback state.
If `[GO2 RESPONSE]` shows `code=0` for audio → Go2 received the commands.
If no `[GO2 AUDIO STATE]` at all → Go2 may not push state unless actively playing. Note this.

---

## Chunk 2: PR-2 — Diagnostic Script

### Task 6: Create diagnose_audio.sh

**Files:**
- Create: `scripts/diagnose_audio.sh`

- [ ] **Step 1: Write the diagnostic script**

```bash
#!/usr/bin/env bash
# PawAI Audio Diagnostics — layered troubleshooting
# Usage: bash scripts/diagnose_audio.sh [--include-l2]
set -euo pipefail

INCLUDE_L2=false
for arg in "$@"; do
  case "$arg" in
    --include-l2) INCLUDE_L2=true ;;
  esac
done

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass()    { echo -e "[${1}] ${2} .......... ${GREEN}PASS${NC}"; }
fail()    { echo -e "[${1}] ${2} .......... ${RED}FAIL${NC}"; }
skip()    { echo -e "[${1}] ${2} .......... ${YELLOW}SKIP${NC}"; }
manual()  { echo -e "[${1}] ${2} .......... ${CYAN}MANUAL${NC}"; }
hint()    { echo -e "     → ${1}"; }

echo "=== PawAI Audio Diagnostics ==="
echo ""

# ────────────────────────────────────────────
# L1: Go2 Speaker Hardware
# ────────────────────────────────────────────
manual "L1" "Go2 Speaker Hardware"
hint "Open Go2 App → Settings → Voice → test any sound"
hint "If Go2 App plays sound: speaker is OK, proceed to L2/L3"
hint "If Go2 App is silent: hardware/firmware issue, not our code"

# Optional SSH check
if command -v ssh &>/dev/null; then
  GO2_IP="${GO2_IP:-192.168.123.161}"
  hint "(Optional) SSH test: ssh unitree@${GO2_IP} 'aplay -l'"
fi
echo ""

# ────────────────────────────────────────────
# L2: WebRTC Direct (bypasses ROS2)
# ────────────────────────────────────────────
if [ "$INCLUDE_L2" = true ]; then
  echo -e "${YELLOW}⚠ L2 will kill go2_driver_node to get exclusive WebRTC access${NC}"
  echo -n "Continue? [y/N] "
  read -r confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    skip "L2" "WebRTC Direct"
    hint "Skipped by user"
  else
    # Kill driver
    pkill -f go2_driver_node || true
    sleep 2

    # Run direct beep test
    echo "Sending 440Hz beep via direct WebRTC..."
    # TODO: implement scripts/test_direct_beep.py
    # python3 scripts/test_direct_beep.py
    skip "L2" "WebRTC Direct"
    hint "Direct beep script not yet implemented"
    hint "Restart driver after L2: ros2 launch go2_robot_sdk robot.launch.py ..."
  fi
else
  skip "L2" "WebRTC Direct"
  hint "Use --include-l2 to enable (will kill driver)"
fi
echo ""

# ────────────────────────────────────────────
# L3: ROS2 Pipeline
# ────────────────────────────────────────────
echo "Testing ROS2 pipeline..."

# Check nodes exist
DRIVER_OK=false
TTS_OK=false

if ros2 node list 2>/dev/null | grep -q "go2_driver_node"; then
  DRIVER_OK=true
fi
if ros2 node list 2>/dev/null | grep -q "tts_node"; then
  TTS_OK=true
fi

if [ "$DRIVER_OK" = false ]; then
  fail "L3" "ROS2 Pipeline"
  hint "go2_driver_node not running"
  hint "Start: ros2 launch go2_robot_sdk robot.launch.py"
  echo ""
elif [ "$TTS_OK" = false ]; then
  fail "L3" "ROS2 Pipeline"
  hint "tts_node not running"
  hint "Start: ros2 run speech_processor tts_node"
  echo ""
else
  # Send test TTS and monitor /webrtc_req for 5 seconds
  WEBRTC_LOG=$(mktemp)
  timeout 5 ros2 topic echo /webrtc_req --no-arr --once > "$WEBRTC_LOG" 2>/dev/null &
  ECHO_PID=$!
  sleep 0.5

  ros2 topic pub --once /tts std_msgs/msg/String "{data: 'diagnostics probe'}" > /dev/null 2>&1

  # Wait for echo to capture
  wait $ECHO_PID 2>/dev/null || true

  if [ -s "$WEBRTC_LOG" ]; then
    pass "L3" "ROS2 Pipeline"
    hint "TTS → /webrtc_req confirmed"
    hint "Check driver log for [AUDIO DEBUG] and [GO2 RESPONSE]"
  else
    fail "L3" "ROS2 Pipeline"
    hint "No /webrtc_req message within 5 seconds"
    hint "Check: ros2 topic info /webrtc_req -v"
  fi
  rm -f "$WEBRTC_LOG"
fi

# ────────────────────────────────────────────
# L4: End-to-End (manual)
# ────────────────────────────────────────────
# Check if ASR node is running
ASR_OK=false
if ros2 node list 2>/dev/null | grep -q "stt_intent_node"; then
  ASR_OK=true
fi

if [ "$ASR_OK" = true ]; then
  manual "L4" "End-to-End"
  hint "Say something to the microphone and listen for Go2 response"
  hint "Monitor: ros2 topic echo /asr_result"
  hint "Monitor: ros2 topic echo /event/speech_intent_recognized"
else
  skip "L4" "End-to-End"
  hint "stt_intent_node not running — start full speech session first"
fi

echo ""
echo "=== Diagnostics Complete ==="
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/diagnose_audio.sh
```

- [ ] **Step 3: Test locally (without Go2)**

```bash
bash scripts/diagnose_audio.sh
```

Expected: L1=MANUAL, L2=SKIP, L3=FAIL (no nodes), L4=SKIP

- [ ] **Step 4: Commit**

```bash
git add scripts/diagnose_audio.sh
git commit -m "feat(scripts): add layered audio diagnostics (L1-L4)"
```

---

## Chunk 3: PR-3 — B-full Observability

### Task 7: Add /state/connection/go2 publisher to go2_driver_node

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py:1-44` (imports)
- Modify: `go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py:51-91` (__init__)

- [ ] **Step 1: Add imports**

Add to imports (around line 5-10):

```python
import time as _time
from std_msgs.msg import String
```

Also ensure `json` is imported (should already be).

- [ ] **Step 2: Add publisher and timer in __init__**

Add after existing publisher setup (around line 60-70, after `_setup_publishers` call):

```python
# Connection health publisher (always active, publishes default state before validation)
self._health_pub = self.create_publisher(String, '/state/connection/go2', 10)
self._health_timer = self.create_timer(2.0, self._publish_connection_health)
self._health_seq = 0
```

- [ ] **Step 3: Add _publish_connection_health method**

Add as a new method on the class:

```python
def _publish_connection_health(self) -> None:
    """Publish Go2 connection health every 2 seconds."""
    health = None
    if hasattr(self, 'adapter') and self.webrtc_adapter:
        health = self.webrtc_adapter.get_connection_health("0")

    if health is None:
        # Pre-validation or adapter not ready
        payload = {
            "stamp": _time.time(),
            "seq": self._health_seq,
            "dc_state": "unknown",
            "connection_state": "unknown",
            "validated": False,
            "last_response_ts": 0.0,
            "last_heartbeat_ts": 0.0,
            "last_msg_type": "",
            "last_audio_state": "unknown",
            "last_audio_state_ts": 0.0,
            "error_count": 0,
            "last_error": "",
            "uptime_s": 0.0,
        }
    else:
        now = _time.time()
        payload = {
            "stamp": now,
            "seq": self._health_seq,
            "dc_state": health.dc_state,
            "connection_state": health.connection_state,
            "validated": health.validated,
            "last_response_ts": health.last_response_ts,
            "last_heartbeat_ts": health.last_heartbeat_ts,
            "last_msg_type": health.last_msg_type,
            "last_audio_state": health.last_audio_state,
            "last_audio_state_ts": health.last_audio_state_ts,
            "error_count": health.error_count,
            "last_error": health.last_error,
            "uptime_s": now - health.connected_at if health.connected_at > 0 else 0.0,
        }

    msg = String()
    msg.data = json.dumps(payload)
    self._health_pub.publish(msg)
    self._health_seq += 1
```

- [ ] **Step 4: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py
git commit -m "feat(go2): publish /state/connection/go2 health topic"
```

---

### Task 8: Add get_connection_health accessor to webrtc_adapter

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py`

- [ ] **Step 1: Add import for ConnectionHealth**

Add to imports:

```python
from .go2_connection import Go2Connection, ConnectionHealth
```

(If `Go2Connection` is already imported, just add `ConnectionHealth`)

- [ ] **Step 2: Add get_connection_health method**

Add as public method on WebRTCAdapter class:

```python
def get_connection_health(self, robot_id: str = "0"):
    """Get thread-safe health snapshot for a robot connection."""
    conn = self.connections.get(robot_id)
    if conn is None:
        return None
    return conn.health  # Returns a copy via @property
```

- [ ] **Step 3: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py
git commit -m "feat(go2): add get_connection_health accessor"
```

---

### Task 9: Add driver-side playback confirmation

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py`

- [ ] **Step 1: Add playback tracking state**

Add instance variables in `__init__`:

```python
self._last_audio_send_ts: float = 0.0
self._audio_playback_confirmed: bool = False
```

- [ ] **Step 2: Record audio send timestamp**

In `_async_send_command`, after the `dc.send(command)` call, when `_api == AUDIO_HUB_COMMANDS["START_AUDIO"]` (4001):

```python
if _api == AUDIO_HUB_COMMANDS.get("START_AUDIO", 4001):
    self._last_audio_send_ts = _time.time()
    self._audio_playback_confirmed = False
```

Add `import time as _time` to imports if not already present.

- [ ] **Step 3: Detect playback confirmation in _on_data_channel_message**

In the adapter's `_on_data_channel_message` callback (which receives parsed Go2 messages), add a check:

```python
# Check for audiohub playback confirmation
topic = msg.get("topic", "") if isinstance(msg, dict) else ""
if topic == RTC_TOPIC.get("AUDIO_HUB_PLAY_STATE", ""):
    if self._last_audio_send_ts > 0 and not self._audio_playback_confirmed:
        self._audio_playback_confirmed = True
        latency = _time.time() - self._last_audio_send_ts
        logger.info(f"[AUDIO CONFIRM] Go2 playback confirmed, latency={latency:.2f}s")
```

- [ ] **Step 4: Add playback timeout check in go2_driver_node's health timer**

In `go2_driver_node.py`, add timeout check inside `_publish_connection_health` (the 2-second timer callback). This keeps `get_connection_health` side-effect-free.

Add to `_publish_connection_health`, before the publish call:

```python
# Check for unconfirmed audio playback timeout
if hasattr(self, 'webrtc_adapter') and self.webrtc_adapter:
    audio_ts = self.webrtc_adapter._last_audio_send_ts
    confirmed = self.webrtc_adapter._audio_playback_confirmed
    if audio_ts > 0 and not confirmed and _time.time() - audio_ts > 3.0:
        self.get_logger().warning(
            "[AUDIO TIMEOUT] Audio sent %.1fs ago but Go2 did not report playback",
            _time.time() - audio_ts,
        )
        self.webrtc_adapter._last_audio_send_ts = 0.0  # Reset
```

- [ ] **Step 5: Build and verify**

```bash
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
```

- [ ] **Step 6: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py
git commit -m "feat(go2): add driver-side playback confirmation with timeout warning"
```

---

### Task 10: Verify PR-3 end-to-end

- [ ] **Step 1: Restart and verify /state/connection/go2**

```bash
# After colcon build + source
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

```bash
# In another terminal — should see JSON every 2 seconds
ros2 topic echo /state/connection/go2
```

Expected: JSON with `dc_state`, `validated`, `last_audio_state`, etc.

- [ ] **Step 2: Send TTS and verify playback confirmation or timeout**

```bash
ros2 run speech_processor tts_node --ros-args -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx
```

```bash
ros2 topic pub --once /tts std_msgs/msg/String '{data: "playback confirmation test"}'
```

Look for in driver log:
- `[AUDIO CONFIRM] Go2 playback confirmed` → success
- `[AUDIO TIMEOUT] Audio sent but Go2 did not report playback` → Go2 didn't play

- [ ] **Step 3: Verify /state/connection/go2 updates after audio**

```bash
ros2 topic echo /state/connection/go2 --once
```

Check that `last_audio_state` and `last_audio_state_ts` have updated values.
