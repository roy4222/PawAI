# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

"""Unit tests for RobotControlService.handle_cmd_vel routing.

Critical behavior: zero cmd_vel must route to StopMove (api_id=1003) — NOT
Move (1008) with x=0 — because Go2 sport mode silently ignores Move commands
with |x| < MIN_X (0.5 m/s), causing the robot to keep executing the last
non-zero Move until sport timeout. Found via on-Jetson B4 burndown 2026-05-11
(Go2 walked 2m past a stop command).

Test loads robot_control_service.py via importlib with a stubbed parent
package, bypassing go2_robot_sdk.__init__ which requires aioice submodule.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

import pytest


# --- Build stub package tree so robot_control_service relative imports resolve ---

_STUB_ROOT = "go2_rcs_test_stub"
_PKG_ROOT = os.path.join(os.path.dirname(__file__), "..", "go2_robot_sdk")


def _make_pkg(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__path__ = []
    sys.modules[name] = m
    return m


def _setup_stubs():
    if _STUB_ROOT in sys.modules:
        return  # already set up

    # Build skeleton:
    #   <stub>                        ← ...
    #   <stub>.domain                 ← ..
    #   <stub>.domain.interfaces      ← ...domain.interfaces (provides IRobotController)
    #   <stub>.domain.constants       ← ...domain.constants  (provides RTC_TOPIC)
    #   <stub>.application            ← ..
    #   <stub>.application.utils      ← ..utils              (provides command_generator submodule)
    #   <stub>.application.services   ← (target)
    _make_pkg(_STUB_ROOT)
    _make_pkg(f"{_STUB_ROOT}.domain")

    intf = _make_pkg(f"{_STUB_ROOT}.domain.interfaces")
    intf.IRobotController = object  # not actually used; service uses duck-typed controller

    const = _make_pkg(f"{_STUB_ROOT}.domain.constants")
    const.RTC_TOPIC = {}  # not used by handle_cmd_vel

    _make_pkg(f"{_STUB_ROOT}.application")
    utils = _make_pkg(f"{_STUB_ROOT}.application.utils")
    cg = _make_pkg(f"{_STUB_ROOT}.application.utils.command_generator")
    cg.gen_mov_command = lambda *a, **kw: ""  # service only uses return for log; safe stub
    utils.command_generator = cg

    _make_pkg(f"{_STUB_ROOT}.application.services")

    # Now load real robot_control_service.py into the stub namespace
    target = f"{_STUB_ROOT}.application.services.robot_control_service"
    spec = importlib.util.spec_from_file_location(
        target,
        os.path.join(_PKG_ROOT, "application", "services", "robot_control_service.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[target] = mod
    # Set __package__ so relative imports resolve via stub tree
    mod.__package__ = f"{_STUB_ROOT}.application.services"
    spec.loader.exec_module(mod)


_setup_stubs()
RCS = sys.modules[f"{_STUB_ROOT}.application.services.robot_control_service"]
RobotControlService = RCS.RobotControlService


# --- Tests ---

@pytest.fixture
def mock_controller():
    return MagicMock()


@pytest.fixture
def service(mock_controller):
    return RobotControlService(mock_controller)


def test_nonzero_forward_routes_to_move(service, mock_controller):
    service.handle_cmd_vel(0.5, 0.0, 0.0, "0")
    mock_controller.send_movement_command.assert_called_once()
    mock_controller.send_stop_move_command.assert_not_called()


def test_nonzero_angular_routes_to_move(service, mock_controller):
    service.handle_cmd_vel(0.0, 0.0, 0.3, "0")
    mock_controller.send_movement_command.assert_called_once()
    mock_controller.send_stop_move_command.assert_not_called()


def test_explicit_zero_routes_to_stop_move(service, mock_controller):
    """The safety-critical path that B4 burndown found broken."""
    service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
    mock_controller.send_stop_move_command.assert_called_once_with("0")
    mock_controller.send_movement_command.assert_not_called()


def test_subdeadband_routes_to_stop_move(service, mock_controller):
    """cmd_vel within deadband (|v| < 0.01) is zeroed → StopMove."""
    service.handle_cmd_vel(0.005, -0.005, 0.005, "0")
    mock_controller.send_stop_move_command.assert_called_once_with("0")
    mock_controller.send_movement_command.assert_not_called()


def test_negative_cmd_vel_routes_to_move(service, mock_controller):
    service.handle_cmd_vel(-0.3, 0.0, 0.0, "0")
    mock_controller.send_movement_command.assert_called_once()
    mock_controller.send_stop_move_command.assert_not_called()


def test_mixed_zero_and_nonzero_routes_to_move(service, mock_controller):
    service.handle_cmd_vel(0.0, 0.2, 0.0, "0")
    mock_controller.send_movement_command.assert_called_once()
    mock_controller.send_stop_move_command.assert_not_called()


def test_clamp_does_not_misroute_to_stop(service, mock_controller):
    """Over-limit cmd_vel clamps to MAX (0.5 m/s) — still Move."""
    service.handle_cmd_vel(5.0, 0.0, 0.0, "0")
    mock_controller.send_movement_command.assert_called_once()
    mock_controller.send_stop_move_command.assert_not_called()
    args, _ = mock_controller.send_movement_command.call_args
    assert args[1] == pytest.approx(0.5)


# --- StopMove dedupe (B5 burndown 2026-05-11: WebRTC DC backlog) ---

def test_first_stop_sends_immediately(service, mock_controller):
    """First stop after construction → send (no prior state to dedupe against)."""
    service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
    mock_controller.send_stop_move_command.assert_called_once_with("0")


def test_repeated_stop_within_window_is_deduped(service, mock_controller, monkeypatch):
    """10 consecutive 0 cmd_vel within 1s → only 1 StopMove sent."""
    fake_time = [0.0]
    monkeypatch.setattr(RCS, "time",
                        type("FakeTime", (), {"monotonic": lambda: fake_time[0]}))
    for _ in range(10):
        service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
        fake_time[0] += 0.1  # 10Hz spam
    # Only first call goes through; rest deduped
    assert mock_controller.send_stop_move_command.call_count == 1


def test_stop_refreshes_after_interval(service, mock_controller, monkeypatch):
    """After STOP_REFRESH_INTERVAL_S elapses, next stop fires (refresh)."""
    fake_time = [0.0]
    monkeypatch.setattr(RCS, "time",
                        type("FakeTime", (), {"monotonic": lambda: fake_time[0]}))
    service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
    assert mock_controller.send_stop_move_command.call_count == 1
    fake_time[0] += 1.5  # >1.0s elapsed
    service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
    assert mock_controller.send_stop_move_command.call_count == 2


def test_move_resets_stop_dedupe(service, mock_controller, monkeypatch):
    """After a Move, the next stop fires immediately (no dedupe penalty)."""
    fake_time = [0.0]
    monkeypatch.setattr(RCS, "time",
                        type("FakeTime", (), {"monotonic": lambda: fake_time[0]}))
    # First stop
    service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
    # Move resets tracker
    fake_time[0] += 0.05
    service.handle_cmd_vel(0.5, 0.0, 0.0, "0")
    # Stop again immediately — should fire (not deduped)
    fake_time[0] += 0.05
    service.handle_cmd_vel(0.0, 0.0, 0.0, "0")
    assert mock_controller.send_stop_move_command.call_count == 2
    assert mock_controller.send_movement_command.call_count == 1
