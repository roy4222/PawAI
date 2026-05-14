"""Integration test: twist_mux 4-layer priority routing.

Strategy: 啟動 twist_mux (用我們的 yaml) + 4 個 fake publishers，分別發到
emergency / obstacle / teleop / nav2，subscribe /cmd_vel mux output 確認
highest priority active source 勝出。

Pre-requisite (test runner):
  ros2 launch twist_mux twist_mux_launch.py \\
    config_topics:=$(pwd)/go2_robot_sdk/config/twist_mux.yaml \\
    config_locks:=$(pwd)/go2_robot_sdk/config/twist_mux.yaml \\
    cmd_vel_out:=/cmd_vel
"""
import time

import pytest
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class FakePublisher(Node):
    """Publishes fixed Twist at 10Hz to a target topic."""

    def __init__(self, name: str, topic: str, vx: float):
        super().__init__(name)
        self._pub = self.create_publisher(Twist, topic, 10)
        self._vx = vx
        self._timer = self.create_timer(0.1, self._tick)

    def _tick(self):
        msg = Twist()
        msg.linear.x = self._vx
        self._pub.publish(msg)


class CmdVelSink(Node):
    """Subscribe to /cmd_vel mux output, record latest linear.x."""

    def __init__(self):
        super().__init__("cmd_vel_sink")
        self.latest_vx = None
        self.create_subscription(Twist, "/cmd_vel", self._cb, 10)

    def _cb(self, msg: Twist):
        self.latest_vx = msg.linear.x


def _spin_briefly(nodes, secs: float = 1.5):
    end = time.time() + secs
    while time.time() < end:
        for n in nodes:
            rclpy.spin_once(n, timeout_sec=0.01)


@pytest.fixture(scope="module")
def ros_context():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_nav2_alone_passes_through(ros_context):
    """Only nav2 source active → mux output ≈ nav2 vx (0.30)."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    sink = CmdVelSink()
    _spin_briefly([nav, sink])
    assert sink.latest_vx is not None, "no /cmd_vel msg received — is twist_mux running?"
    assert abs(sink.latest_vx - 0.30) < 0.01, f"got {sink.latest_vx}"
    nav.destroy_node()
    sink.destroy_node()


def test_obstacle_overrides_nav2(ros_context):
    """obstacle (priority 200) > nav2 (priority 10) → mux output == obstacle vx (0.0)."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    obs = FakePublisher("fake_obs", "/cmd_vel_obstacle", 0.0)
    sink = CmdVelSink()
    _spin_briefly([nav, obs, sink])
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx) < 0.01, f"got {sink.latest_vx} (obstacle should win at 0.0)"
    nav.destroy_node()
    obs.destroy_node()
    sink.destroy_node()


def test_teleop_overrides_nav2_but_not_obstacle(ros_context):
    """teleop (100) > nav2 (10) but < obstacle (200)."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    teleop = FakePublisher("fake_teleop", "/cmd_vel_joy", 0.50)
    sink = CmdVelSink()
    _spin_briefly([nav, teleop, sink])
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx - 0.50) < 0.01, f"got {sink.latest_vx} (teleop 0.50 should win)"
    nav.destroy_node()
    teleop.destroy_node()
    sink.destroy_node()


def test_emergency_overrides_all(ros_context):
    """emergency (255) is highest, beats nav + teleop + obstacle."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    teleop = FakePublisher("fake_teleop", "/cmd_vel_joy", 0.50)
    obs = FakePublisher("fake_obs", "/cmd_vel_obstacle", 0.20)
    emer = FakePublisher("fake_emer", "/cmd_vel_emergency", 0.0)
    sink = CmdVelSink()
    _spin_briefly([nav, teleop, obs, emer, sink])
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx) < 0.01, f"got {sink.latest_vx} (emergency 0.0 should win)"
    for n in [nav, teleop, obs, emer, sink]:
        n.destroy_node()
