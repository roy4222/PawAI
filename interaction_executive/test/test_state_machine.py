"""Tests for ExecutiveStateMachine — pure Python, no ROS2.

api_id 權威來源：go2_robot_sdk/domain/constants/robot_commands.py (ROBOT_CMD)
"""
import time
import pytest
from interaction_executive.state_machine import (
    ExecutiveStateMachine,
    ExecutiveState,
    EventType,
    ACTION_DAMP,
    ACTION_STOP,
    ACTION_SIT,
    ACTION_STAND,
    ACTION_HELLO,
    ACTION_CONTENT,
)


class TestApiIdAlignment:
    """Verify api_ids match go2_robot_sdk ROBOT_CMD authority.

    If robot_commands.py changes, this test catches the drift.
    Authority: go2_robot_sdk/domain/constants/robot_commands.py
    """

    # Snapshot of ROBOT_CMD values — update here if robot_commands.py changes
    ROBOT_CMD = {
        "Damp": 1001,
        "StopMove": 1003,
        "StandUp": 1004,
        "Sit": 1009,
        "Hello": 1016,
        "Content": 1020,
    }

    def test_damp_matches(self):
        assert ACTION_DAMP["api_id"] == self.ROBOT_CMD["Damp"]

    def test_stop_matches(self):
        assert ACTION_STOP["api_id"] == self.ROBOT_CMD["StopMove"]

    def test_stand_matches(self):
        assert ACTION_STAND["api_id"] == self.ROBOT_CMD["StandUp"]

    def test_sit_matches(self):
        assert ACTION_SIT["api_id"] == self.ROBOT_CMD["Sit"]

    def test_hello_matches(self):
        assert ACTION_HELLO["api_id"] == self.ROBOT_CMD["Hello"]

    def test_content_matches(self):
        assert ACTION_CONTENT["api_id"] == self.ROBOT_CMD["Content"]

    def test_all_actions_have_required_fields(self):
        """Every action must have topic, parameter, priority for WebRtcReq."""
        for name, action in [
            ("DAMP", ACTION_DAMP), ("STOP", ACTION_STOP),
            ("STAND", ACTION_STAND), ("SIT", ACTION_SIT),
            ("HELLO", ACTION_HELLO), ("CONTENT", ACTION_CONTENT),
        ]:
            assert "topic" in action, f"{name} missing topic"
            assert "parameter" in action, f"{name} missing parameter"
            assert "priority" in action, f"{name} missing priority"
            assert action["topic"] == "rt/api/sport/request", f"{name} wrong topic"
            assert action["parameter"] == str(action["api_id"]), f"{name} parameter != api_id"

    def test_stop_has_priority_1(self):
        assert ACTION_STOP["priority"] == 1


class TestBasicTransitions:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_initial_state_is_idle(self):
        assert self.sm.state == ExecutiveState.IDLE

    def test_face_welcome_transitions_to_greeting(self):
        result = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert self.sm.state == ExecutiveState.GREETING
        assert result.tts is not None

    def test_speech_greet_transitions_to_greeting(self):
        result = self.sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data={"intent": "greet"}
        )
        assert self.sm.state == ExecutiveState.GREETING

    def test_speech_chat_transitions_to_conversing(self):
        result = self.sm.handle_event(
            EventType.SPEECH_INTENT,
            source="mic",
            data={"intent": "chat", "text": "你好嗎"},
        )
        assert self.sm.state == ExecutiveState.CONVERSING

    def test_speech_command_transitions_to_executing(self):
        result = self.sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data={"intent": "sit"}
        )
        assert self.sm.state == ExecutiveState.EXECUTING
        assert result.action is not None

    def test_come_here_starts_forward(self):
        result = self.sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data={"intent": "come_here"}
        )
        assert self.sm.state == ExecutiveState.EXECUTING
        assert result.action is not None
        assert result.action.get("cmd_vel") is True
        assert result.action["x"] == 0.3
        assert result.tts is not None

    def test_come_here_interrupted_by_obstacle(self):
        self.sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data={"intent": "come_here"}
        )
        assert self.sm.state == ExecutiveState.EXECUTING
        result = self.sm.handle_event(EventType.OBSTACLE)
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP
        assert result.action is not None

    def test_stop_gesture_returns_to_idle(self):
        self.sm.handle_event(
            EventType.SPEECH_INTENT,
            source="mic",
            data={"intent": "chat", "text": "test"},
        )
        assert self.sm.state == ExecutiveState.CONVERSING
        result = self.sm.handle_event(
            EventType.GESTURE, source="cam", data={"gesture": "stop"}
        )
        assert self.sm.state == ExecutiveState.IDLE
        assert result.action is not None


class TestEmergency:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_fallen_triggers_emergency_from_idle(self):
        result = self.sm.handle_event(EventType.POSE_FALLEN)
        assert self.sm.state == ExecutiveState.EMERGENCY
        assert result.tts is not None

    def test_fallen_triggers_emergency_from_conversing(self):
        self.sm.handle_event(
            EventType.SPEECH_INTENT,
            source="mic",
            data={"intent": "chat", "text": "hi"},
        )
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
        assert result.action is not None

    def test_obstacle_interrupts_executing(self):
        self.sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data={"intent": "sit"}
        )
        assert self.sm.state == ExecutiveState.EXECUTING
        result = self.sm.handle_event(EventType.OBSTACLE)
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP
        assert self.sm._previous_state == ExecutiveState.EXECUTING

    def test_obstacle_cleared_returns_to_previous_state(self):
        self.sm.handle_event(
            EventType.SPEECH_INTENT, source="mic", data={"intent": "sit"}
        )
        self.sm.handle_event(EventType.OBSTACLE)
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP
        result = self.sm.handle_event(EventType.OBSTACLE_CLEARED)
        assert self.sm.state == ExecutiveState.EXECUTING

    def test_obstacle_cleared_with_debounce(self):
        """Obstacle cleared must be stable for MIN_CLEAR_DURATION."""
        self.sm.handle_event(EventType.OBSTACLE)
        self.sm._obstacle_clear_time = time.monotonic()
        result = self.sm.try_obstacle_clear()
        assert self.sm.state == ExecutiveState.OBSTACLE_STOP

    def test_obstacle_cleared_after_debounce(self):
        """After debounce period + min duration, should recover."""
        self.sm.handle_event(EventType.OBSTACLE)
        self.sm._obstacle_enter_time = time.monotonic() - 3.0
        self.sm._obstacle_clear_time = time.monotonic() - 3.0
        result = self.sm.try_obstacle_clear()
        assert self.sm.state == ExecutiveState.IDLE


class TestDedup:
    def setup_method(self):
        self.sm = ExecutiveStateMachine()

    def test_same_source_within_5s_is_deduped(self):
        result1 = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert result1.tts is not None
        result2 = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert result2.tts is None

    def test_different_source_not_deduped(self):
        result1 = self.sm.handle_event(EventType.FACE_WELCOME, source="roy")
        assert result1.tts is not None
        self.sm._state = ExecutiveState.IDLE
        result2 = self.sm.handle_event(EventType.FACE_WELCOME, source="alice")
        assert result2.tts is not None


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
        self.sm.handle_event(
            EventType.SPEECH_INTENT,
            source="mic",
            data={"intent": "chat", "text": "hi"},
        )
        result = self.sm.handle_event(EventType.TIMEOUT)
        assert self.sm.state == ExecutiveState.IDLE
