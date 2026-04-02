"""Executive v0 State Machine — thin demo orchestrator.

Pure Python, no ROS2 dependency. Handles event routing, state transitions,
dedup, priority, and obstacle debounce.

api_id 權威來源：go2_robot_sdk/domain/constants/robot_commands.py (ROBOT_CMD)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
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
    POSE_FALLEN = 0       # EMERGENCY — highest
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
    tts: Optional[str] = None
    action: Optional[dict] = None
    new_state: Optional[ExecutiveState] = None


# Go2 action constants — values from ROBOT_CMD + WebRtcReq fields
_SPORT = "rt/api/sport/request"

ACTION_DAMP    = {"api_id": 1001, "topic": _SPORT, "parameter": "1001", "priority": 0}
ACTION_STOP    = {"api_id": 1003, "topic": _SPORT, "parameter": "1003", "priority": 1}
ACTION_STAND   = {"api_id": 1004, "topic": _SPORT, "parameter": "1004", "priority": 0}
ACTION_SIT     = {"api_id": 1009, "topic": _SPORT, "parameter": "1009", "priority": 0}
ACTION_HELLO   = {"api_id": 1016, "topic": _SPORT, "parameter": "1016", "priority": 0}
ACTION_CONTENT = {"api_id": 1020, "topic": _SPORT, "parameter": "1020", "priority": 0}
ACTION_FORWARD = {"cmd_vel": True, "x": 0.3, "y": 0.0, "z": 0.0}  # continuous forward

DEDUP_WINDOW = 5.0          # seconds
STATE_TIMEOUT = 30.0        # seconds per state
OBSTACLE_DEBOUNCE = 2.0     # seconds before obstacle_cleared takes effect
OBSTACLE_MIN_DURATION = 1.0  # minimum time in OBSTACLE_STOP


class ExecutiveStateMachine:
    def __init__(self):
        self._state = ExecutiveState.IDLE
        self._previous_state = ExecutiveState.IDLE
        self._state_enter_time = time.monotonic()
        self._dedup: dict[str, float] = {}
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
        # C2 fix: purge expired entries to prevent unbounded growth
        expired = [k for k, t in self._dedup.items() if (now - t) > DEDUP_WINDOW * 2]
        for k in expired:
            del self._dedup[k]
        return False

    def check_timeout(self) -> Optional[EventResult]:
        """Call periodically to check state timeouts."""
        elapsed = time.monotonic() - self._state_enter_time
        if self._state not in (ExecutiveState.IDLE, ExecutiveState.OBSTACLE_STOP) and elapsed > STATE_TIMEOUT:
            return self.handle_event(EventType.TIMEOUT)
        return None

    def reset_obstacle_clear(self):
        """Call when a new obstacle is detected to reset the clear timer."""
        self._obstacle_clear_time = None

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

    def handle_event(self, event_type: EventType, source: str = "",
                     data: Optional[dict] = None) -> EventResult:
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
                action=ACTION_STOP,
                new_state=ExecutiveState.OBSTACLE_STOP,
            )

        if event_type == EventType.OBSTACLE_CLEARED:
            recover_to = (
                self._previous_state
                if self._previous_state != ExecutiveState.OBSTACLE_STOP
                else ExecutiveState.IDLE
            )
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
            return EventResult()

        return EventResult()

    def _handle_idle(self, event_type: EventType, source: str,
                     data: dict) -> EventResult:
        if event_type == EventType.FACE_WELCOME:
            self._set_state(ExecutiveState.GREETING)
            name = source or "朋友"
            return EventResult(
                tts=f"{name}，你好！",
                action=ACTION_HELLO,
                new_state=ExecutiveState.GREETING,
            )
        if event_type == EventType.SPEECH_INTENT:
            return self._route_speech(data)
        if event_type == EventType.GESTURE:
            return self._route_gesture(data)
        return EventResult()

    def _handle_greeting(self, event_type: EventType, source: str,
                         data: dict) -> EventResult:
        if event_type == EventType.SPEECH_INTENT:
            return self._route_speech(data)
        return EventResult()

    def _handle_conversing(self, event_type: EventType, source: str,
                           data: dict) -> EventResult:
        if event_type == EventType.SPEECH_INTENT:
            return self._route_speech(data)
        return EventResult()

    def _handle_executing(self, event_type: EventType, source: str,
                          data: dict) -> EventResult:
        return EventResult()

    def _handle_emergency(self, event_type: EventType, source: str,
                          data: dict) -> EventResult:
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
        elif intent == "come_here":
            self._set_state(ExecutiveState.EXECUTING)
            return EventResult(
                tts="好的，我過來了",
                action=ACTION_FORWARD,
                new_state=ExecutiveState.EXECUTING,
            )
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
