# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

from abc import ABC, abstractmethod
from typing import Any


class IRobotController(ABC):
    """Interface for robot control operations"""

    @abstractmethod
    def send_movement_command(self, robot_id: str, x: float, y: float, z: float) -> None:
        """Send movement command to robot (Go2 sport Move, api_id=1008)"""
        pass

    @abstractmethod
    def send_stop_move_command(self, robot_id: str) -> None:
        """Send hard-stop command (Go2 sport StopMove, api_id=1003).

        Required because Go2 sport mode silently ignores Move (1008) commands with
        |x| < MIN_X (0.5 m/s) — a plain `Move {x:0, y:0, z:0}` does NOT actually
        stop the robot; it keeps executing the last non-zero Move until sport
        timeout (~2-3s). Always use this for explicit stops (cmd_vel = 0,
        nav goal reached, reactive_stop triggered, /stop_movement service).
        """
        pass

    @abstractmethod
    def send_stand_up_command(self, robot_id: str) -> None:
        """Send stand up command"""
        pass

    @abstractmethod
    def send_stand_down_command(self, robot_id: str) -> None:
        """Send stand down command"""
        pass

    @abstractmethod
    def send_webrtc_request(self, robot_id: str, api_id: int, parameter: Any, topic: str) -> None:
        """Send WebRTC request"""
        pass 
