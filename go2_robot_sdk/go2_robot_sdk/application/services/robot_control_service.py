# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

import json
import logging


from ...domain.interfaces import IRobotController
from ..utils.command_generator import gen_mov_command
from ...domain.constants import RTC_TOPIC


logger = logging.getLogger(__name__)

MAX_LINEAR_X = 0.5
MAX_LINEAR_Y = 0.3
MAX_ANGULAR_Z = 0.5
DEADBAND = 0.01


class RobotControlService:
    """Service for robot control"""

    def __init__(self, controller: IRobotController):
        self.controller = controller

    def handle_cmd_vel(self, x: float, y: float, z: float, robot_id: str, obstacle_avoidance: bool = False) -> None:
        """Process movement command"""
        try:
            clamped_x = self._apply_deadband(self._clamp(x, -MAX_LINEAR_X, MAX_LINEAR_X))
            clamped_y = self._apply_deadband(self._clamp(y, -MAX_LINEAR_Y, MAX_LINEAR_Y))
            clamped_z = self._apply_deadband(self._clamp(z, -MAX_ANGULAR_Z, MAX_ANGULAR_Z))

            logger.info(
                "Received cmd_vel: x=%.3f, y=%.3f, z=%.3f, robot_id=%s, obstacle_avoidance=%s",
                x,
                y,
                z,
                robot_id,
                obstacle_avoidance,
            )
            cmd = gen_mov_command(
                round(clamped_x, 2),
                round(clamped_y, 2),
                round(clamped_z, 2),
                obstacle_avoidance,
            )
            logger.info(
                "Sending movement command to robot %s: %s (clamped x=%.3f y=%.3f z=%.3f)",
                robot_id,
                cmd,
                clamped_x,
                clamped_y,
                clamped_z,
            )
            self.controller.send_movement_command(robot_id, clamped_x, clamped_y, clamped_z)
        except Exception as e:
            logger.error(f"Error handling cmd_vel: {e}")

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    @staticmethod
    def _apply_deadband(value: float) -> float:
        return 0.0 if abs(value) < DEADBAND else value

    def handle_webrtc_request(self, api_id: int, parameter_str: str, topic: str, msg_id: str, robot_id: str) -> None:
        """Process WebRTC request"""
        try:
            parameter = "" if parameter_str == "" else json.loads(parameter_str)
            self.controller.send_webrtc_request(robot_id, api_id, parameter, topic)
            logger.info(f"WebRTC request sent to robot {robot_id}")
        except ValueError as e:
            logger.error(f"Invalid JSON in WebRTC request: {e}")
        except Exception as e:
            logger.error(f"Error handling WebRTC request: {e}")

    def handle_joy_command(self, joy_buttons: list, robot_id: str) -> None:
        """Process joystick commands"""
        try:
            if joy_buttons and len(joy_buttons) > 1:
                if joy_buttons[1]:  # Stand down
                    self.controller.send_stand_down_command(robot_id)
                    logger.info(f"Stand down command sent to robot {robot_id}")
                
                elif joy_buttons[0]:  # Stand up
                    self.controller.send_stand_up_command(robot_id)
                    logger.info(f"Stand up command sent to robot {robot_id}")

        except Exception as e:
            logger.error(f"Error handling joy command: {e}")

    def set_obstacle_avoidance(self, enabled: bool, robot_id: str) -> None:
        """Set obstacle avoidance mode"""
        try:
            self.controller.send_webrtc_request(
                robot_id, 
                1004, 
                {"is_remote_commands_from_api": enabled},
                RTC_TOPIC['OBSTACLES_AVOID']
            )
            logger.info(f"Obstacle avoidance set to {enabled} for robot {robot_id}")
        except Exception as e:
            logger.error(f"Error setting obstacle avoidance: {e}") 
