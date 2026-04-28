"""WorldState aggregates safety-relevant ROS2 state for Brain MVS."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field

from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Bool, String


_TRANSIENT_LOCAL = QoSProfile(
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    reliability=QoSReliabilityPolicy.RELIABLE,
)

_BEST_EFFORT = QoSProfile(
    depth=10,
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
)


@dataclass
class WorldStateSnapshot:
    obstacle: bool = False
    emergency: bool = False
    fallen: bool = False
    tts_playing: bool = False
    nav_safe: bool = True
    last_update: float = field(default_factory=time.time)


class WorldState:
    """Thread-safe state aggregator owned by a ROS2 node."""

    def __init__(self, node: Node) -> None:
        self._lock = threading.Lock()
        self._snap = WorldStateSnapshot()
        node.create_subscription(Bool, "/state/tts_playing", self._on_tts, _TRANSIENT_LOCAL)
        node.create_subscription(
            String, "/state/reactive_stop/status", self._on_reactive_stop, _BEST_EFFORT
        )
        node.create_subscription(String, "/state/nav/safety", self._on_nav_safety, _BEST_EFFORT)

    def snapshot(self) -> WorldStateSnapshot:
        with self._lock:
            return WorldStateSnapshot(
                obstacle=self._snap.obstacle,
                emergency=self._snap.emergency,
                fallen=self._snap.fallen,
                tts_playing=self._snap.tts_playing,
                nav_safe=self._snap.nav_safe,
                last_update=self._snap.last_update,
            )

    def set_fallen(self, value: bool) -> None:
        with self._lock:
            self._snap.fallen = value
            self._snap.last_update = time.time()

    def _on_tts(self, msg: Bool) -> None:
        with self._lock:
            self._snap.tts_playing = bool(msg.data)
            self._snap.last_update = time.time()

    def _on_reactive_stop(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return
        with self._lock:
            self._snap.obstacle = bool(data.get("obstacle_active", False))
            self._snap.emergency = bool(data.get("emergency", False))
            self._snap.last_update = time.time()

    def _on_nav_safety(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return
        with self._lock:
            self._snap.nav_safe = not bool(data.get("unsafe", False))
            self._snap.last_update = time.time()
