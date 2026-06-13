"""Pure unit tests for structured goto rejection reasons."""
import asyncio
import sys
import types
from types import SimpleNamespace


def _install_go2_action_stubs_if_needed():
    try:
        import go2_interfaces.action  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    go2_interfaces = types.ModuleType("go2_interfaces")
    action = types.ModuleType("go2_interfaces.action")

    class GotoRelative:
        class Result:
            def __init__(self):
                self.success = False
                self.message = ""
                self.actual_distance = 0.0

    class GotoNamed:
        class Result:
            def __init__(self):
                self.success = False
                self.message = ""
                self.final_pose = SimpleNamespace(
                    position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                    orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
                )

    action.GotoRelative = GotoRelative
    action.GotoNamed = GotoNamed
    go2_interfaces.action = action
    sys.modules["go2_interfaces"] = go2_interfaces
    sys.modules["go2_interfaces.action"] = action


_install_go2_action_stubs_if_needed()

# CI fast-gate runs this dir on a runner WITHOUT rclpy. nav_action_server_node
# imports rclpy at module top, so guard collection to skip cleanly there.
import pytest  # noqa: E402

pytest.importorskip("rclpy")

from nav_capability.nav_action_server_node import (  # noqa: E402
    NavActionServerNode,
    build_goto_rejection_reason,
)


class FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warn(self, message):
        self.warnings.append(message)


class FakeGoalHandle:
    def __init__(self, request, goal_id="goal-1"):
        self.request = request
        self.goal_id = goal_id
        self.aborted = False
        self.canceled_called = False
        self.succeeded = False

    def abort(self):
        self.aborted = True

    def canceled(self):
        self.canceled_called = True

    def succeed(self):
        self.succeeded = True


class FakeClock:
    def now(self):
        return SimpleNamespace(nanoseconds=123456789)


class FakeNode:
    def __init__(self, covariance):
        self.logger = FakeLogger()
        self.covariance = covariance

    def get_logger(self):
        return self.logger

    def get_clock(self):
        return FakeClock()

    def _current_xy(self):
        return (0.0, 0.0)

    async def _wait_for_odom(self, timeout_s=3.0):
        return True

    def _amcl_covariance_xy(self):
        return self.covariance


def test_build_goto_rejection_reason_uses_structured_tokens():
    assert (
        build_goto_rejection_reason(covariance=0.45)
        == "nav_not_ready:covariance=0.45"
    )
    assert (
        build_goto_rejection_reason(active_goal_id="goal-abc")
        == "another_goto_active:goal-abc"
    )
    assert build_goto_rejection_reason(paused=True) == "paused"
    assert build_goto_rejection_reason(distance=1.0) == "yellow_band_limit:0.5m"


def test_accept_goal_logs_structured_reason_when_another_goto_is_active():
    fake = SimpleNamespace(
        _goto_active=True,
        _active_goto_goal_id="goal-abc",
        logger=FakeLogger(),
    )
    fake.get_logger = lambda: fake.logger

    response = NavActionServerNode._accept_goal(fake, object())

    assert str(response).endswith("REJECT")
    assert "another_goto_active:goal-abc" in fake.logger.warnings[-1]


def test_execute_relative_red_covariance_returns_structured_nav_not_ready_reason():
    fake = FakeNode(covariance=0.6)
    goal_handle = FakeGoalHandle(
        SimpleNamespace(distance=0.3, yaw_offset=0.0, max_speed=0.0)
    )

    result = asyncio.run(NavActionServerNode._execute_relative_inner(fake, goal_handle))

    assert goal_handle.aborted is True
    assert result.success is False
    assert "nav_not_ready:covariance=0.6" in result.message
    assert "nav_not_ready:covariance=0.6" in fake.logger.warnings[-1]


def test_execute_relative_yellow_band_returns_structured_limit_reason():
    fake = FakeNode(covariance=0.45)
    goal_handle = FakeGoalHandle(
        SimpleNamespace(distance=1.0, yaw_offset=0.0, max_speed=0.0)
    )

    result = asyncio.run(NavActionServerNode._execute_relative_inner(fake, goal_handle))

    assert goal_handle.aborted is True
    assert result.success is False
    assert "yellow_band_limit:0.5m" in result.message
    assert "yellow_band_limit:0.5m" in fake.logger.warnings[-1]
