# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

import json
import logging
import time


from ...domain.interfaces import IRobotController
from ..utils.command_generator import gen_mov_command
from ...domain.constants import RTC_TOPIC


logger = logging.getLogger(__name__)

MAX_LINEAR_X = 0.5  # C6: authoritative limit; move_service.MAX_LINEAR (0.3) is legacy
MAX_LINEAR_Y = 0.3
MAX_ANGULAR_Z = 0.5
DEADBAND = 0.01

# Refresh interval for repeated StopMove commands. reactive_stop_node publishes
# at 10 Hz; without dedupe, every 100ms a StopMove (1003) hits the WebRTC
# DataChannel → backlog grows ~138 bytes/msg unbounded (B5 burndown 2026-05-11
# saw bufferedAmount 115KB+ in 2 min). Once StopMove is acknowledged, Go2 stays
# stopped without refresh, so dedupe to 1 Hz refresh.
STOP_REFRESH_INTERVAL_S = 1.0


class RobotControlService:
    """Service for robot control"""

    def __init__(self, controller: IRobotController):
        self.controller = controller
        # Track last sent stop time for dedupe (None = no stop sent recently)
        self._last_stop_sent_at: float | None = None

    def handle_cmd_vel(self, x: float, y: float, z: float, robot_id: str, obstacle_avoidance: bool = False) -> None:
        """Process movement command.

        Routes to either Go2 sport Move (api_id=1008) for non-zero velocity, or
        Go2 sport StopMove (api_id=1003) for explicit stops (post-deadband zero).

        Why this branch matters: Go2 sport mode silently ignores Move commands
        with |x| < MIN_X (0.5 m/s), so plain Move {x:0} does NOT stop the robot —
        it keeps executing the last non-zero Move until sport timeout (~2-3s).
        Confirmed via on-Jetson B4 burndown 2026-05-11 (Go2 walked 2m after
        a stop command was sent).
        """
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

            # Explicit stop: all axes zero after deadband → use StopMove (1003)
            # instead of Move (1008) with x=0 (which Go2 sport mode ignores).
            is_stop = clamped_x == 0.0 and clamped_y == 0.0 and clamped_z == 0.0
            if is_stop:
                # Dedupe: only send first stop (or a 1Hz refresh) — once Go2
                # acknowledges StopMove it stays stopped without further commands.
                # Repeated 10Hz StopMove from reactive_stop_node would backlog
                # the WebRTC DataChannel.
                now = time.monotonic()
                if (self._last_stop_sent_at is not None
                        and (now - self._last_stop_sent_at) < STOP_REFRESH_INTERVAL_S):
                    return  # silent skip — already stopped recently
                logger.info(
                    "Sending StopMove (api_id=1003) to robot %s (post-deadband cmd_vel = 0)",
                    robot_id,
                )
                self.controller.send_stop_move_command(robot_id)
                self._last_stop_sent_at = now
                return

            # Non-zero motion: always send (sport mode needs frequent refresh
            # to maintain velocity). Reset stop tracker so the next stop fires
            # immediately without dedupe penalty.
            self._last_stop_sent_at = None
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
