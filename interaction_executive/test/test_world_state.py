"""Tests for WorldState capability subscriptions (Phase A 5/2 P0).

Pure-Python: no rclpy.init(). We pass a tiny FakeNode that just records the
subscriptions it was asked to create, then drive callbacks directly.
"""
from std_msgs.msg import Bool

from interaction_executive.world_state import WorldState, WorldStateSnapshot


class _FakeSub:
    pass


class _FakeNode:
    """Stand-in for rclpy Node — captures subscription registrations only."""

    def __init__(self):
        self.subscriptions = {}  # topic -> callback

    def create_subscription(self, _msg_type, topic, callback, _qos):
        self.subscriptions[topic] = callback
        return _FakeSub()


def test_default_snapshot_is_fail_closed_for_capability_gates():
    node = _FakeNode()
    ws = WorldState(node)
    snap = ws.snapshot()
    # Phase A capability defaults: nav_ready / depth_clear MUST be fail-closed.
    assert snap.nav_ready is False, "nav_ready must default False (fail-closed)"
    assert snap.depth_clear is False, "depth_clear must default False (fail-closed)"
    # nav_paused defaults False (= not paused = motion allowed by this gate alone).
    # Reasoning lives in WorldStateSnapshot docstring.
    assert snap.nav_paused is False
    # Legacy fields untouched.
    assert snap.obstacle is False
    assert snap.emergency is False
    assert snap.nav_safe is True


def test_subscribes_three_capability_topics():
    node = _FakeNode()
    WorldState(node)
    assert "/capability/nav_ready" in node.subscriptions
    assert "/capability/depth_clear" in node.subscriptions
    assert "/state/nav/paused" in node.subscriptions


def test_capability_callbacks_flip_snapshot():
    node = _FakeNode()
    ws = WorldState(node)

    # Drive each callback to True
    node.subscriptions["/capability/nav_ready"](_bool(True))
    node.subscriptions["/capability/depth_clear"](_bool(True))
    node.subscriptions["/state/nav/paused"](_bool(True))

    snap = ws.snapshot()
    assert snap.nav_ready is True
    assert snap.depth_clear is True
    assert snap.nav_paused is True


def test_capability_callbacks_flip_back_to_false():
    node = _FakeNode()
    ws = WorldState(node)
    # Up
    for topic in ("/capability/nav_ready", "/capability/depth_clear", "/state/nav/paused"):
        node.subscriptions[topic](_bool(True))
    # Down
    for topic in ("/capability/nav_ready", "/capability/depth_clear", "/state/nav/paused"):
        node.subscriptions[topic](_bool(False))
    snap = ws.snapshot()
    assert snap.nav_ready is False
    assert snap.depth_clear is False
    assert snap.nav_paused is False


def test_capability_fields_are_independent():
    """Flipping one capability must not affect the other two."""
    node = _FakeNode()
    ws = WorldState(node)
    node.subscriptions["/capability/nav_ready"](_bool(True))
    snap = ws.snapshot()
    assert snap.nav_ready is True
    assert snap.depth_clear is False  # still default
    assert snap.nav_paused is False   # still default


def _bool(value: bool) -> Bool:
    msg = Bool()
    msg.data = value
    return msg
