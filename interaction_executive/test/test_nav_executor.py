"""NAV executor tests (issue #129) — fail-closed gates / clamp / async result / timeout.

不需 nav stack：GotoRelative 用 fake class monkeypatch、ActionClient 用 fake 注入
node._nav_client。對齊 test_mini_e2e 的 rclpy fixture 慣例。
"""
from __future__ import annotations

import pytest
import rclpy

from interaction_executive import interaction_executive_node as ien
from interaction_executive.interaction_executive_node import InteractionExecutiveNode
from interaction_executive.skill_contract import (
    SKILL_REGISTRY,
    ExecutorKind,
    SkillStep,
)
from interaction_executive.world_state import WorldStateSnapshot


@pytest.fixture(scope="module", autouse=True)
def rclpy_context():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


class FakeGoal:
    def __init__(self):
        self.distance = 0.0
        self.yaw_offset = 0.0
        self.max_speed = 0.0


class FakeGotoRelative:
    Goal = FakeGoal


class FakeFuture:
    def __init__(self):
        self._cb = None
        self._result = None
        self._exc = None

    def add_done_callback(self, cb):
        self._cb = cb

    def result(self):
        if self._exc is not None:
            raise self._exc
        return self._result

    def complete(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        if self._cb is not None:
            self._cb(self)


class FakeGoalHandle:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.cancel_called = False
        self.result_future = FakeFuture()

    def get_result_async(self):
        return self.result_future

    def cancel_goal_async(self):
        self.cancel_called = True
        return FakeFuture()


class FakeResultMsg:
    def __init__(self, success: bool, message: str = "", actual_distance: float = 0.0):
        class _R:
            pass

        self.result = _R()
        self.result.success = success
        self.result.message = message
        self.result.actual_distance = actual_distance


class FakeActionClient:
    def __init__(self, server_ready=True):
        self._ready = server_ready
        self.sent_goal = None
        self.send_future = FakeFuture()

    def server_is_ready(self):
        return self._ready

    def send_goal_async(self, goal):
        self.sent_goal = goal
        return self.send_future


def _snap(**kw) -> WorldStateSnapshot:
    base = dict(nav_ready=True, depth_clear=True, nav_paused=False, emergency=False)
    base.update(kw)
    return WorldStateSnapshot(**base)


@pytest.fixture
def node(monkeypatch):
    n = InteractionExecutiveNode()
    monkeypatch.setattr(ien, "GotoRelative", FakeGotoRelative)
    results = []

    def capture(msg):
        import json

        results.append(json.loads(msg.data))

    n._pub_skill_result.publish = capture
    n._captured_results = results
    try:
        yield n
    finally:
        n.destroy_node()


NAV_STEP = SkillStep(ExecutorKind.NAV, {"action": "goto_relative", "distance": 0.5})


def test_nav_disabled_by_default(node):
    """nav_executor_enabled 預設 False → fail-closed，保 Phase A 行為。"""
    assert node.nav_executor_enabled is False
    ok, detail = node._dispatch_step(NAV_STEP)
    assert ok is False
    assert detail == "nav_executor_disabled"


def test_nav_unsupported_action(node):
    node.nav_executor_enabled = True
    ok, detail = node._dispatch_step(SkillStep(ExecutorKind.NAV, {"action": "patrol"}))
    assert (ok, detail) == (False, "nav_action_unsupported:patrol")


@pytest.mark.parametrize(
    "snap_kw, reason",
    [
        ({"nav_ready": False}, "nav_gate:nav_ready"),
        ({"depth_clear": False}, "nav_gate:depth_clear"),
        ({"nav_paused": True}, "nav_gate:nav_paused"),
        ({"emergency": True}, "nav_gate:emergency"),
    ],
)
def test_nav_world_gates_fail_closed(node, monkeypatch, snap_kw, reason):
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap(**snap_kw))
    ok, detail = node._dispatch_step(NAV_STEP)
    assert (ok, detail) == (False, reason)


def test_nav_server_unavailable(node, monkeypatch):
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    node._nav_client = FakeActionClient(server_ready=False)
    ok, detail = node._dispatch_step(NAV_STEP)
    assert (ok, detail) == (False, "nav_server_unavailable")


def test_nav_distance_clamped(node, monkeypatch):
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client
    ok, detail = node._dispatch_step(
        SkillStep(ExecutorKind.NAV, {"action": "goto_relative", "distance": 5.0})
    )
    assert ok is True
    assert client.sent_goal.distance == pytest.approx(1.5)  # clamp 上限


def test_nav_success_path(node, monkeypatch):
    """dispatch → goal accepted → result success → _nav_step_done True 且 ok。"""
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client

    ok, detail = node._dispatch_step(NAV_STEP)
    assert ok is True and detail.startswith("nav_goal_sent")
    assert node._nav_state["phase"] == "sending"

    handle = FakeGoalHandle(accepted=True)
    client.send_future.complete(result=handle)
    assert node._nav_state["phase"] == "active"

    handle.result_future.complete(result=FakeResultMsg(True, "reached", 0.48))
    assert node._nav_state["phase"] == "done"
    assert node._nav_state["ok"] is True
    assert node._nav_state["detail"].startswith("nav_reached")
    assert node._nav_step_done(age=1.0) is True


def test_nav_stale_callback_does_not_corrupt_next_goal(node, monkeypatch):
    """舊 goal 的遲到 result 不得寫進下一個 NAV step 的 state（review #3）。"""
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client

    # 第一個 goal：goal accepted，result 還沒回
    node._dispatch_step(NAV_STEP)
    handle_a = FakeGoalHandle(accepted=True)
    client.send_future.complete(result=handle_a)
    state_a = node._nav_state

    # 模擬 worker 收掉（timeout / preempt）→ _nav_state 換新
    node._nav_state = None
    node._dispatch_step(NAV_STEP)  # 第二個 goal，新 dict
    state_b = node._nav_state
    assert state_b is not state_a

    # 舊 goal 的遲到 result 進來 → 必須 no-op，不污染 state_b
    handle_a.result_future.complete(result=FakeResultMsg(True, "reached", 0.48))
    assert state_b["phase"] == "sending"  # 未被舊 goal 改成 done


def test_nav_preempt_cancels_inflight_goal(node, monkeypatch):
    """_cancel_active_nav_goal 取消在飛 goal 並棄置 state（review #2 搶佔路徑）。"""
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client
    node._dispatch_step(NAV_STEP)
    handle = FakeGoalHandle(accepted=True)
    client.send_future.complete(result=handle)

    node._cancel_active_nav_goal()
    assert handle.cancel_called is True
    assert node._nav_state is None


def test_nav_goal_rejected(node, monkeypatch):
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client
    node._dispatch_step(NAV_STEP)
    client.send_future.complete(result=FakeGoalHandle(accepted=False))
    assert node._nav_state["phase"] == "done"
    assert node._nav_state["ok"] is False
    assert node._nav_state["detail"] == "nav_goal_rejected"


def test_nav_result_failure(node, monkeypatch):
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client
    node._dispatch_step(NAV_STEP)
    handle = FakeGoalHandle(accepted=True)
    client.send_future.complete(result=handle)
    handle.result_future.complete(result=FakeResultMsg(False, "no_progress_timeout"))
    assert node._nav_state["ok"] is False
    assert node._nav_state["detail"] == "nav_failed:no_progress_timeout"


def test_nav_timeout_cancels_goal(node, monkeypatch):
    node.nav_executor_enabled = True
    monkeypatch.setattr(node._world, "snapshot", lambda: _snap())
    client = FakeActionClient()
    node._nav_client = client
    node._dispatch_step(NAV_STEP)
    handle = FakeGoalHandle(accepted=True)
    client.send_future.complete(result=handle)
    # result 未回，age 超過 nav_step_timeout_s
    done = node._nav_step_done(age=node.nav_step_timeout_s + 1.0)
    assert done is True
    assert handle.cancel_called is True
    assert node._nav_state["detail"] == "nav_timeout"
    assert node._nav_state["ok"] is False


def test_nav_runtime_param_toggle(node):
    """ros2 param set nav_executor_enabled true 即時生效（demo 現場免重啟）。"""
    from rclpy.parameter import Parameter

    results = node.set_parameters(
        [Parameter("nav_executor_enabled", Parameter.Type.BOOL, True)]
    )
    assert all(r.successful for r in results)
    assert node.nav_executor_enabled is True


def test_move_forward_registry_shape():
    skill = SKILL_REGISTRY["move_forward"]
    assert skill.steps[0].executor == ExecutorKind.NAV
    assert skill.steps[0].args["action"] == "goto_relative"
    assert skill.steps[0].args["distance"] == pytest.approx(0.5)
    assert skill.requires_confirmation is True
    assert set(skill.safety_requirements) == {"nav_ready", "depth_clear"}
    assert skill.risk_level == "high"
