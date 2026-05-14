"""Route Runner FSM (pure logic, no ROS)。

State transitions:
    IDLE → PLANNING (start_route)
    PLANNING → MOVING (goal_accepted)
    MOVING → PLANNING (waypoint_reached normal, advance)
                | SUCCEEDED (last waypoint)
                | WAITING / TTS (waypoint_reached wait/tts)
    WAITING / TTS → PLANNING (task_complete, advance)
                | SUCCEEDED (last)
    {PLANNING, MOVING} → PAUSED (pause)
    PAUSED → PLANNING (resume; re-send current waypoint)
    {PLANNING, MOVING, PAUSED, WAITING, TTS} → FAILED (cancel)
"""
from enum import Enum, auto


class RouteState(Enum):
    IDLE = auto()
    PLANNING = auto()
    MOVING = auto()
    PAUSED = auto()
    WAITING = auto()
    TTS = auto()
    SUCCEEDED = auto()
    FAILED = auto()


ACTIVE_STATES = {
    RouteState.PLANNING,
    RouteState.MOVING,
    RouteState.PAUSED,
    RouteState.WAITING,
    RouteState.TTS,
}


class IllegalTransition(RuntimeError):
    pass


class RouteFSM:
    def __init__(self):
        self.state: RouteState = RouteState.IDLE
        self.current_waypoint_index: int = 0
        self._total: int = 0

    def start_route(self, total_waypoints: int) -> None:
        if self.state != RouteState.IDLE:
            raise IllegalTransition(f"cannot start_route from {self.state}")
        if total_waypoints <= 0:
            raise ValueError("total_waypoints must be > 0")
        self._total = total_waypoints
        self.current_waypoint_index = 0
        self.state = RouteState.PLANNING

    def goal_accepted(self) -> None:
        if self.state != RouteState.PLANNING:
            raise IllegalTransition(f"cannot goal_accepted from {self.state}")
        self.state = RouteState.MOVING

    def waypoint_reached(self, task: str) -> None:
        if self.state != RouteState.MOVING:
            raise IllegalTransition(f"cannot waypoint_reached from {self.state}")
        if task == "normal":
            self._advance_or_finish()
        elif task == "wait":
            self.state = RouteState.WAITING
        elif task == "tts":
            self.state = RouteState.TTS
        else:
            raise ValueError(f"unknown task: {task}")

    def task_complete(self) -> None:
        if self.state not in (RouteState.WAITING, RouteState.TTS):
            raise IllegalTransition(f"cannot task_complete from {self.state}")
        self._advance_or_finish()

    def pause(self) -> None:
        if self.state not in (RouteState.PLANNING, RouteState.MOVING):
            raise IllegalTransition(f"cannot pause from {self.state}")
        self.state = RouteState.PAUSED

    def resume(self) -> None:
        if self.state != RouteState.PAUSED:
            raise IllegalTransition(f"cannot resume from {self.state}")
        self.state = RouteState.PLANNING

    def cancel(self) -> None:
        if self.state not in ACTIVE_STATES:
            raise IllegalTransition(f"cannot cancel from {self.state}")
        self.state = RouteState.FAILED

    def _advance_or_finish(self) -> None:
        self.current_waypoint_index += 1
        if self.current_waypoint_index >= self._total:
            self.state = RouteState.SUCCEEDED
        else:
            self.state = RouteState.PLANNING
