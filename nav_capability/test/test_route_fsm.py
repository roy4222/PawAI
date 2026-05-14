"""Pure-logic FSM tests."""
import pytest

from nav_capability.lib.route_fsm import RouteFSM, RouteState, IllegalTransition


def test_initial_state_is_idle():
    assert RouteFSM().state == RouteState.IDLE


def test_start_to_planning():
    fsm = RouteFSM()
    fsm.start_route(total_waypoints=3)
    assert fsm.state == RouteState.PLANNING
    assert fsm.current_waypoint_index == 0


def test_planning_to_moving():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    assert fsm.state == RouteState.MOVING


def test_normal_advances():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    assert fsm.state == RouteState.PLANNING
    assert fsm.current_waypoint_index == 1


def test_wait_enters_waiting():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="wait")
    assert fsm.state == RouteState.WAITING


def test_tts_enters_tts():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="tts")
    assert fsm.state == RouteState.TTS


def test_waiting_complete_advances():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="wait")
    fsm.task_complete()
    assert fsm.state == RouteState.PLANNING
    assert fsm.current_waypoint_index == 1


def test_last_normal_succeeds():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    assert fsm.state == RouteState.SUCCEEDED


def test_pause_from_moving():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.pause()
    assert fsm.state == RouteState.PAUSED


def test_resume_re_enters_planning():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.pause()
    fsm.resume()
    assert fsm.state == RouteState.PLANNING


def test_cancel_to_failed():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.cancel()
    assert fsm.state == RouteState.FAILED


def test_pause_from_idle_raises():
    fsm = RouteFSM()
    with pytest.raises(IllegalTransition):
        fsm.pause()


def test_pause_resume_preserves_index():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    fsm.goal_accepted()
    fsm.pause()
    fsm.resume()
    assert fsm.current_waypoint_index == 1
