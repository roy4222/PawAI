#!/usr/bin/env python3
"""Emergency stop CLI helper.

Publishes:
  /cmd_vel_emergency: geometry_msgs/Twist (zero velocity, mux priority 255)
  /lock/emergency: std_msgs/Bool (true engages mux lock; false releases)

Usage:
  python3 emergency_stop.py engage    # lock 鎖死所有 cmd_vel
  python3 emergency_stop.py release   # 解鎖

Phase 1.4 — full emergency trigger source (joy button / safety relay) listed
in spec §14 T2.
"""
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool


class EmergencyStopCLI(Node):
    def __init__(self, engage: bool):
        super().__init__("emergency_stop_cli")
        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel_emergency", 10)
        self._lock_pub = self.create_publisher(Bool, "/lock/emergency", 10)
        # Latch by publishing for 2s
        end = time.time() + 2.0
        while time.time() < end and rclpy.ok():
            self._cmd_pub.publish(Twist())  # zero velocity
            self._lock_pub.publish(Bool(data=engage))
            rclpy.spin_once(self, timeout_sec=0.05)
            time.sleep(0.1)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("engage", "release"):
        print(__doc__)
        sys.exit(1)
    rclpy.init()
    EmergencyStopCLI(engage=(sys.argv[1] == "engage"))
    rclpy.shutdown()


if __name__ == "__main__":
    main()
