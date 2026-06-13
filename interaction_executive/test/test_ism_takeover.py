"""ISM staged takeover flag skeleton tests.

rclpy local tier - NOT in the CI fast gate. This file instantiates BrainNode,
so environments without rclpy should skip at import time.
"""
import json
import time

import pytest

rclpy = pytest.importorskip("rclpy")
from rclpy.parameter import Parameter  # noqa: E402
from std_msgs.msg import Empty, String  # noqa: E402

from interaction_executive import brain_node as brain_node_module  # noqa: E402
from interaction_executive import interaction_state  # noqa: E402
from interaction_executive.attention_machine import AttentionState  # noqa: E402
from interaction_executive.brain_node import BrainNode  # noqa: E402
from interaction_executive.pending_confirm import ConfirmState  # noqa: E402


_ISM_TAKEOVER_FLAGS = (
    "ism_enabled",
    "ism_stage_2a_demo_phase",
    "ism_stage_2b_confirm",
    "ism_stage_2c_executing",
    "ism_stage_2d_speaking",
)

_ISM_STAGE_FLAGS = _ISM_TAKEOVER_FLAGS[1:]


@pytest.fixture(scope="module", autouse=True)
def rclpy_ctx():
    if not rclpy.ok():
        rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


def _make_node() -> BrainNode:
    n = BrainNode()
    n.proposals = []
    n._pub_proposal.publish = (  # type: ignore[method-assign]
        lambda m: n.proposals.append(json.loads(m.data))
    )
    n.traces = []
    n._pub_trace.publish = (  # type: ignore[method-assign]
        lambda m: n.traces.append(json.loads(m.data))
    )
    return n


@pytest.fixture
def node():
    n = _make_node()
    yield n
    n.destroy_node()


def _msg(payload: dict) -> String:
    m = String()
    m.data = json.dumps(payload, ensure_ascii=False)
    return m


def _normalize(proposals: list[dict]) -> list[dict]:
    """Strip volatile fields while keeping emitted proposal payload semantics."""
    return [
        {
            "selected_skill": p["selected_skill"],
            "steps": p["steps"],
            "reason": p["reason"],
            "source": p["source"],
            "priority_class": p["priority_class"],
        }
        for p in proposals
    ]


def _legacy_traces(n: BrainNode) -> list[tuple]:
    return [
        (t["kind"], t["gate"], t["reason"])
        for t in n.traces
        if not t.get("detail", {}).get("shadow")
    ]


def _shadow_traces(n: BrainNode) -> list[dict]:
    return [t for t in n.traces if t.get("detail", {}).get("shadow")]


_CUP = {"objects": [{"class_name": "cup", "confidence": 0.9, "color": "red"}]}
_PHASE_KINDS = ("greet", "object", "gesture")


def _phase_trace(n: BrainNode) -> list[tuple[str, str]]:
    return [
        (t["gate"], t["reason"])
        for t in n.traces
        if t["gate"] == "demo_phase"
    ]


def _enable_stage_2b(n: BrainNode) -> None:
    n.ism_enabled = True
    n.ism_stage_2b_confirm = True


def _enable_stage_2c(n: BrainNode) -> None:
    n.ism_shadow_enabled = True
    n.ism_enabled = True
    n.ism_stage_2c_executing = True


def _start_wiggle(n: BrainNode, plan_id: str = "p1") -> None:
    n._on_skill_result(_msg({
        "plan_id": plan_id,
        "status": "started",
        "selected_skill": "wiggle",
        "priority_class": 3,
    }))


def _watchdog_reset_traces(n: BrainNode) -> list[dict]:
    return [
        t for t in n.traces
        if t["reason"].startswith("watchdog_timeout:executing")
        and t.get("detail", {}).get("cleanup") == "active_plan_reset"
    ]


def _tick_after_deadline(monkeypatch, n: BrainNode) -> None:
    deadline = n._ism.deadline
    assert deadline is not None
    with monkeypatch.context() as m:
        m.setattr(brain_node_module.time, "time", lambda: deadline + 1.0)
        n._ism_shadow_tick()


def _enter_pending_confirm(n: BrainNode) -> None:
    n._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    assert n._pending_confirm.state == ConfirmState.PENDING
    n.proposals.clear()
    n.traces.clear()
    n._trace_throttle.clear()


def _fire_stable_fallen(n: BrainNode) -> None:
    n._on_pose(_msg({"pose": "fallen"}))
    n._state.fallen_first_seen = time.time() - n.fallen_accumulate_s - 0.1
    n._on_pose(_msg({"pose": "fallen"}))


def _legacy_suppressed_traces(n: BrainNode) -> list[dict]:
    return [
        t for t in n.traces
        if t["verdict"] == "suppressed" and not t.get("detail", {}).get("shadow")
    ]


def _stable_trace_payload(t: dict) -> dict:
    detail = t["detail"]
    return {
        "kind": t["kind"],
        "verdict": t["verdict"],
        "gate": t["gate"],
        "reason": t["reason"],
        "detail": {
            "gate": detail["gate"],
            "reason": detail["reason"],
            "active_plan": detail["active_plan"],
            "pending_confirm": detail["pending_confirm"],
            "cooldown_remaining_s": detail["cooldown_remaining_s"],
            "source_summary": detail["source_summary"],
        },
    }


def _run_social_during_confirm(*, kind: str, stage_2b_on: bool) -> dict:
    n = _make_node()
    try:
        if stage_2b_on:
            _enable_stage_2b(n)
        _enter_pending_confirm(n)
        if kind == "object":
            n._attention._state = AttentionState.ENGAGED
            n._on_object(_msg({"objects": [{"class_name": "cup", "confidence": 0.9}]}))
        elif kind == "gesture":
            n._on_gesture(_msg({"gesture": "wave", "confidence": 0.95}))
        else:
            raise AssertionError(f"unknown social kind {kind!r}")
        suppressed = [
            t for t in _legacy_suppressed_traces(n)
            if t["gate"] == "pending_confirm"
        ]
        assert len(suppressed) == 1
        return {
            "proposals": _normalize(n.proposals),
            "trace": _stable_trace_payload(suppressed[0]),
        }
    finally:
        n.destroy_node()


def _run_phase_gate(n: BrainNode, *, phase: str, kind: str,
                    stage_2a_on: bool) -> tuple[bool, list[tuple[str, str]]]:
    n.demo_phase = phase
    n.ism_enabled = stage_2a_on
    n.ism_stage_2a_demo_phase = stage_2a_on
    n.traces.clear()
    n._trace_throttle.clear()
    allowed = n._phase_allows(kind)
    return allowed, _phase_trace(n)


def _run_representative_sequence(n: BrainNode) -> dict:
    """Run a stable event sequence and return payload-level parity evidence."""
    n._on_speech_intent(_msg({"transcript": "停", "session_id": "s1"}))
    n._attention._state = AttentionState.ENGAGED
    n._on_object(_msg(_CUP))
    n._on_object(_msg(_CUP))
    first = n.proposals[0]
    n._on_skill_result(_msg({
        "plan_id": first["plan_id"],
        "status": "started",
        "selected_skill": first["selected_skill"],
        "priority_class": first["priority_class"],
    }))
    n._on_skill_result(_msg({"plan_id": first["plan_id"], "status": "completed"}))
    n.gesture_enabled = False
    n._on_gesture(_msg({"gesture": "wave", "confidence": 0.9}))
    n.gesture_enabled = True
    n._on_reset_context(Empty())
    return {
        "proposals": _normalize(n.proposals),
        "legacy_traces": _legacy_traces(n),
        "shadow_traces": _shadow_traces(n),
    }


def test_stage_flags_declared_default_false(node):
    for name in _ISM_TAKEOVER_FLAGS:
        assert node.get_parameter(name).value is False
        assert getattr(node, name) is False


def test_ism_stage_on_requires_master_and_stage(node):
    for stage in _ISM_STAGE_FLAGS:
        node.ism_enabled = False
        setattr(node, stage, True)
        assert node._ism_stage_on(stage) is False

        node.ism_enabled = True
        setattr(node, stage, False)
        assert node._ism_stage_on(stage) is False

        setattr(node, stage, True)
        assert node._ism_stage_on(stage) is True

        node.ism_enabled = False
        assert node._ism_stage_on(stage) is False


def test_on_set_params_runtime_toggle(node):
    for name in _ISM_TAKEOVER_FLAGS:
        assert getattr(node, name) is False
        result = node._on_set_params([Parameter(name, Parameter.Type.BOOL, True)])
        assert result.successful is True
        assert getattr(node, name) is True

        result = node._on_set_params([Parameter(name, Parameter.Type.BOOL, False)])
        assert result.successful is True
        assert getattr(node, name) is False


def test_all_off_parity_matches_shadow_off_behavior():
    baseline, all_off = _make_node(), _make_node()
    try:
        all_off._on_set_params([
            Parameter(name, Parameter.Type.BOOL, False)
            for name in _ISM_TAKEOVER_FLAGS
        ])

        baseline_evidence = _run_representative_sequence(baseline)
        all_off_evidence = _run_representative_sequence(all_off)

        assert all_off_evidence["proposals"] == baseline_evidence["proposals"]
        assert all_off_evidence["legacy_traces"] == baseline_evidence["legacy_traces"]
        assert all_off_evidence["shadow_traces"] == []
    finally:
        baseline.destroy_node()
        all_off.destroy_node()


def test_demo_phase_stage_2a_takeover_matches_legacy_phase_kind_matrix():
    legacy, takeover = _make_node(), _make_node()
    try:
        for phase in interaction_state.PHASE_ALLOWED_KINDS:
            for kind in _PHASE_KINDS:
                legacy_result = _run_phase_gate(
                    legacy, phase=phase, kind=kind, stage_2a_on=False
                )
                takeover_result = _run_phase_gate(
                    takeover, phase=phase, kind=kind, stage_2a_on=True
                )
                assert takeover_result == legacy_result
    finally:
        legacy.destroy_node()
        takeover.destroy_node()


def test_demo_phase_stage_2a_takeover_fallback_never_raises(monkeypatch):
    legacy, takeover = _make_node(), _make_node()
    try:
        phase = "s3_object"
        kind = "gesture"
        legacy_result = _run_phase_gate(
            legacy, phase=phase, kind=kind, stage_2a_on=False
        )

        def _boom(_demo_phase: str, _kind: str) -> bool:
            raise RuntimeError("boom")

        monkeypatch.setattr(interaction_state, "phase_allows", _boom)
        takeover_result = _run_phase_gate(
            takeover, phase=phase, kind=kind, stage_2a_on=True
        )
        assert takeover_result == legacy_result
    finally:
        legacy.destroy_node()
        takeover.destroy_node()


def test_legacy_fallen_fires_during_pending_confirm(node):
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    assert node._pending_confirm.state == ConfirmState.PENDING
    node.proposals.clear()

    node._on_pose(_msg({"pose": "fallen"}))
    node._state.fallen_first_seen = time.time() - node.fallen_accumulate_s - 0.1
    node._on_pose(_msg({"pose": "fallen"}))

    assert any(p["selected_skill"] == "fallen_alert" for p in node.proposals)
    assert node._pending_confirm.state == ConfirmState.PENDING


def test_2b_fallen_preempts_pending_confirm_flag_on(node):
    _enable_stage_2b(node)
    _enter_pending_confirm(node)

    _fire_stable_fallen(node)

    assert any(p["selected_skill"] == "fallen_alert" for p in node.proposals)
    assert node._pending_confirm.state == ConfirmState.IDLE


def test_2b_fallen_orphans_confirm_flag_off(node):
    _enter_pending_confirm(node)

    _fire_stable_fallen(node)

    assert any(p["selected_skill"] == "fallen_alert" for p in node.proposals)
    assert node._pending_confirm.state == ConfirmState.PENDING


def test_2b_social_suppress_byte_identical_flag_on_vs_off():
    for kind in ("object", "gesture"):
        legacy = _run_social_during_confirm(kind=kind, stage_2b_on=False)
        takeover = _run_social_during_confirm(kind=kind, stage_2b_on=True)

        assert takeover == legacy
        assert takeover["proposals"] == []
        assert takeover["trace"]["gate"] == "pending_confirm"
        assert takeover["trace"]["reason"] == "confirm_in_flight"
        assert takeover["trace"]["detail"]["gate"] == "pending_confirm"
        assert takeover["trace"]["detail"]["reason"] == "confirm_in_flight"


def test_2b_confirm_preempt_never_raises(monkeypatch, node):
    _enable_stage_2b(node)
    _enter_pending_confirm(node)

    def _boom(_state, _candidate):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        interaction_state.InteractionPolicy,
        "evaluate",
        staticmethod(_boom),
    )
    _fire_stable_fallen(node)

    assert any(p["selected_skill"] == "fallen_alert" for p in node.proposals)
    assert node._pending_confirm.state == ConfirmState.PENDING


def test_2b_explicit_speech_still_cancels_confirm():
    results = []
    for stage_2b_on in (False, True):
        n = _make_node()
        try:
            if stage_2b_on:
                _enable_stage_2b(n)
            _enter_pending_confirm(n)
            n._on_speech_intent(_msg({"transcript": "你好", "session_id": "s1"}))
            results.append(n._pending_confirm.state)
        finally:
            n.destroy_node()

    assert results == [ConfirmState.IDLE, ConfirmState.IDLE]


def test_2c_watchdog_clears_stuck_active_plan_flag_on(monkeypatch, node):
    _enable_stage_2c(node)

    _start_wiggle(node, plan_id="p1")
    with node._lock:
        node._state.active_step = {"executor": "mock"}

    assert node._state.active_plan is not None
    assert node._ism.state is interaction_state.InteractionState.EXECUTING
    assert node._ism.deadline is not None

    _tick_after_deadline(monkeypatch, node)

    assert node._state.active_plan is None
    assert node._state.active_step is None
    assert any(
        "watchdog_timeout:executing" in t["reason"]
        and t["detail"].get("watchdog") is True
        for t in _watchdog_reset_traces(node)
    )


def test_2c_watchdog_no_clear_flag_off(monkeypatch, node):
    node.ism_shadow_enabled = True

    _start_wiggle(node, plan_id="p1")
    assert node._state.active_plan is not None
    assert node._ism.state is interaction_state.InteractionState.EXECUTING
    assert node._ism.deadline is not None

    _tick_after_deadline(monkeypatch, node)

    assert node._state.active_plan is not None
    assert _watchdog_reset_traces(node) == []


def test_2c_healthy_skill_not_killed(monkeypatch, node):
    _enable_stage_2c(node)

    _start_wiggle(node, plan_id="p1")
    deadline = node._ism.deadline
    assert deadline is not None
    node._on_skill_result(_msg({"plan_id": "p1", "status": "completed"}))

    assert node._state.active_plan is None
    assert node._ism.state is interaction_state.InteractionState.IDLE

    with monkeypatch.context() as m:
        m.setattr(brain_node_module.time, "time", lambda: deadline + 1.0)
        node._ism_shadow_tick()

    assert _watchdog_reset_traces(node) == []


def test_2c_zero_timeout_not_armed():
    machine = interaction_state.InteractionStateMachine(now=5.0)
    machine.apply_signal(
        interaction_state.TransitionSignal(
            interaction_state.TriggerKind.SKILL_RESULT,
            {"status": "STARTED", "plan_id": "p1", "timeout_s": 0},
        ),
        now=5.0,
    )

    assert machine.state is interaction_state.InteractionState.EXECUTING
    assert machine.deadline is None
    assert machine.tick(now=999999.0) is None
    assert machine.state is interaction_state.InteractionState.EXECUTING


def test_2c_watchdog_cleanup_never_raises(monkeypatch, node):
    _enable_stage_2c(node)
    _start_wiggle(node, plan_id="p1")
    monkeypatch.setattr(
        node._ism,
        "tick",
        lambda _now: (_ for _ in ()).throw(RuntimeError("tick boom")),
    )

    node._ism_shadow_tick()

    trace_node = _make_node()
    try:
        _enable_stage_2c(trace_node)
        _start_wiggle(trace_node, plan_id="p2")
        monkeypatch.setattr(
            trace_node,
            "_trace",
            lambda _event: (_ for _ in ()).throw(RuntimeError("trace boom")),
        )

        _tick_after_deadline(monkeypatch, trace_node)
    finally:
        trace_node.destroy_node()


def test_legacy_sitting_skipped_during_pending_confirm(node):
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    assert node._pending_confirm.state == ConfirmState.PENDING
    node.proposals.clear()

    node._on_pose(_msg({"pose": "sitting"}))
    node._state.sitting_first_seen = time.time() - 1.1
    node._on_pose(_msg({"pose": "sitting"}))

    assert not any(p["selected_skill"] == "sit_along" for p in node.proposals)


def test_legacy_object_suppressed_during_pending_confirm(node):
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    assert node._pending_confirm.state == ConfirmState.PENDING
    node.traces.clear()
    node._attention._state = AttentionState.ENGAGED

    node._on_object(_msg({"objects": [{"class_name": "cup", "confidence": 0.9}]}))

    assert any(
        t["verdict"] == "suppressed"
        and t["gate"] == "pending_confirm"
        and t["reason"] == "confirm_in_flight"
        and not t.get("detail", {}).get("shadow")
        for t in node.traces
    )


def test_legacy_gesture_suppressed_during_pending_confirm(node):
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    assert node._pending_confirm.state == ConfirmState.PENDING
    node.traces.clear()

    node._on_gesture(_msg({"gesture": "wave", "confidence": 0.95}))

    assert any(
        t["verdict"] == "suppressed"
        and t["gate"] == "pending_confirm"
        and t["reason"] == "confirm_in_flight"
        and not t.get("detail", {}).get("shadow")
        for t in node.traces
    )
