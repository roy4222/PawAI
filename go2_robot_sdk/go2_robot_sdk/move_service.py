#!/usr/bin/env python3
# Copyright (c) 2025, Elder and Dog Project
# SPDX-License-Identifier: BSD-3-Clause
"""
Move Service for MCP Integration.

Provides /move_for_duration service to move the robot
for a specified duration with smooth velocity control.

Safety features:
- Uses ROS Clock consistently for all timing
- Checks rclpy.ok() for graceful shutdown
- Provides /stop_movement service for emergency stop
- Immediate stop on Ctrl+C
"""

import threading

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.callback_groups import ReentrantCallbackGroup
from geometry_msgs.msg import Twist
from std_srvs.srv import Trigger
from go2_interfaces.srv import MoveForDuration


class MoveService(Node):
    """ROS2 Node that provides timed movement control service."""

    def __init__(self):
        super().__init__('move_service')

        # Safety limits
        self.MAX_LINEAR = 0.5   # m/s  (C6: aligned with robot_control_service)
        self.MAX_ANGULAR = 0.5  # rad/s
        self.MAX_DURATION = 10.0  # seconds
        self.PUBLISH_RATE = 10  # Hz

        # Movement state
        self._is_moving = False
        self._stop_requested = False
        self._lock = threading.Lock()

        # Callback group for concurrent service handling
        self.callback_group = ReentrantCallbackGroup()

        # Publisher for cmd_vel
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )

        # Create ROS Rate (uses ROS Clock internally)
        self._rate = self.create_rate(self.PUBLISH_RATE)

        # Create move service
        self.create_service(
            MoveForDuration,
            '/move_for_duration',
            self.move_callback,
            callback_group=self.callback_group
        )

        # Create stop service (emergency stop)
        self.create_service(
            Trigger,
            '/stop_movement',
            self.stop_callback,
            callback_group=self.callback_group
        )

        self.get_logger().info('🚀 Move service ready: /move_for_duration')
        self.get_logger().info('🛑 Stop service ready: /stop_movement')
        self.get_logger().info(
            f'   Limits: linear={self.MAX_LINEAR}m/s, '
            f'angular={self.MAX_ANGULAR}rad/s, '
            f'max_duration={self.MAX_DURATION}s'
        )

    def clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value to specified range."""
        return max(min_val, min(max_val, value))

    def stop_callback(self, request, response):
        """Handle /stop_movement service call - emergency stop."""
        with self._lock:
            self._stop_requested = True

        # Immediately send stop command
        self.cmd_vel_pub.publish(Twist())

        response.success = True
        response.message = 'Stop requested'
        self.get_logger().warn('🛑 Emergency stop requested!')
        return response

    def move_callback(self, request, response):
        """Handle /move_for_duration service call."""
        # Check if already moving
        with self._lock:
            if self._is_moving:
                response.success = False
                response.message = 'Already moving. Call /stop_movement first.'
                response.actual_duration = 0.0
                return response
            self._is_moving = True
            self._stop_requested = False

        warnings = []

        # Validate and clamp inputs
        linear_x = self.clamp(request.linear_x, -self.MAX_LINEAR, self.MAX_LINEAR)
        angular_z = self.clamp(request.angular_z, -self.MAX_ANGULAR, self.MAX_ANGULAR)
        duration = self.clamp(request.duration, 0.0, self.MAX_DURATION)

        # Log and record clamp warnings
        if linear_x != request.linear_x:
            msg = f'linear_x clamped: {request.linear_x:.2f}→{linear_x:.2f}'
            warnings.append(msg)
            self.get_logger().warn(msg)
        if angular_z != request.angular_z:
            msg = f'angular_z clamped: {request.angular_z:.2f}→{angular_z:.2f}'
            warnings.append(msg)
            self.get_logger().warn(msg)
        if duration != request.duration:
            msg = f'duration clamped: {request.duration:.2f}→{duration:.2f}s (max={self.MAX_DURATION}s)'
            warnings.append(msg)
            self.get_logger().warn(msg)

        if duration <= 0:
            with self._lock:
                self._is_moving = False
            response.success = False
            response.message = 'Duration must be positive'
            response.actual_duration = 0.0
            return response

        self.get_logger().info(
            f'Moving: linear={linear_x:.2f}m/s, angular={angular_z:.2f}rad/s, '
            f'duration={duration:.2f}s'
        )

        # Create twist message
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z

        # Use ROS Clock for timing (consistent with Rate.sleep())
        start_time = self.get_clock().now()
        target_duration = Duration(seconds=duration)

        actual_duration = 0.0
        stopped_early = False

        try:
            while rclpy.ok():
                # Check for stop request
                with self._lock:
                    if self._stop_requested:
                        stopped_early = True
                        break

                # Check elapsed time using ROS Clock
                elapsed = self.get_clock().now() - start_time
                if elapsed >= target_duration:
                    break

                # Publish velocity command
                self.cmd_vel_pub.publish(twist)

                # Sleep using ROS Rate (uses ROS Clock internally)
                # This properly handles sim_time and clock synchronization
                self._rate.sleep()

            # Calculate actual duration using ROS Clock (consistent with Rate)
            actual_duration = (self.get_clock().now() - start_time).nanoseconds / 1e9

        except Exception as e:
            self.get_logger().error(f'Move failed: {e}')
            response.success = False
            response.message = f'Error: {str(e)}'
            response.actual_duration = (self.get_clock().now() - start_time).nanoseconds / 1e9
            # Ensure stop
            self.cmd_vel_pub.publish(Twist())
            with self._lock:
                self._is_moving = False
            return response
        finally:
            # ALWAYS stop the robot
            self.cmd_vel_pub.publish(Twist())
            with self._lock:
                self._is_moving = False

        # Build response message
        if stopped_early:
            response.success = True
            response.message = f'Stopped early after {actual_duration:.2f}s'
            self.get_logger().info(f'⚠️ Move stopped early: {actual_duration:.2f}s')
        else:
            warning_text = '; '.join(warnings) if warnings else ''
            response.success = True
            if warning_text:
                response.message = f'Moved for {actual_duration:.2f}s (warnings: {warning_text})'
            else:
                response.message = f'Moved for {actual_duration:.2f}s'
            self.get_logger().info(f'✅ Move complete: {actual_duration:.2f}s')

        response.actual_duration = actual_duration
        return response


def main(args=None):
    """Entry point."""
    rclpy.init(args=args)
    node = MoveService()

    # Use MultiThreadedExecutor for concurrent service handling
    from rclpy.executors import MultiThreadedExecutor
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down, sending stop command...')
        # Emergency stop on Ctrl+C
        node.cmd_vel_pub.publish(Twist())
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
