"""ISM Phase 1 shadow parity + 6/9 blackhole replay tests (system Phase 2 T2A-2/T2A-3).

rclpy local tier — NOT in the CI fast gate (Invocation 3 is an explicit file
list; this file instantiates BrainNode → imports rclpy). Run locally:

    PYTHONPATH=pawai_contracts:$PYTHONPATH python3 -m pytest \
        interaction_executive/test/test_ism_shadow_parity.py -q

Contract under test (phase 2 plan, 2A):
  - ism_shadow_enabled declares False → emit byte-identical, zero shadow traces.
  - shadow on → emits unchanged, plus CANDIDATE/STATE_TRANSITION traces with
    detail.shadow=true.
  - shadow hooks never raise into a brain callback.
  - 6/9 replay: stuck EXECUTING/ALERT_ACTIVE/CONFIRM_PENDING → cup/greet get an
    explicit SUPPRESS-with-reason shadow verdict, never a silent drop; watchdog
    expiry walks ERROR_RECOVERY → IDLE.
"""
import json

import pytest

rclpy = pytest.importorskip("rclpy")
from std_msgs.msg import Empty, String  # noqa: E402

from interaction_executive.attention_machine import AttentionState  # noqa: E402
from interaction_executive.brain_node import BrainNode  # noqa: E402
from interaction_executive.interaction_state import (  # noqa: E402
    InteractionState as IsmState,
)
from interaction_executive.skill_contract import build_plan  # noqa: E402


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


def _shadow_traces(n: BrainNode) -> list[dict]:
    return [t for t in n.traces if t.get("detail", {}).get("shadow")]


def _legacy_traces(n: BrainNode) -> list[tuple]:
    return [
        (t["kind"], t["gate"], t["reason"])
        for t in n.traces
        if not t.get("detail", {}).get("shadow")
    ]


def _normalize(proposals: list[dict]) -> list[dict]:
    """Strip volatile fields (plan_id / created_at / session_id / decision_id).
    Parity = same skills in the same order with same steps/source/reason/priority."""
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


_CUP = {"objects": [{"class_name": "cup", "confidence": 0.9, "color": "red"}]}


def _run_scenario(n: BrainNode) -> None:
    """Deterministic sequence touching emit, suppress, lifecycle and reset paths."""
    # 1. safety stop via speech (SafetyLayer hard rule → immediate emit)
    n._on_speech_intent(_msg({"transcript": "停", "session_id": "s1"}))
    # 2. object remark while ENGAGED (emit), then repeat (60s remark dedup suppress)
    n._attention._state = AttentionState.ENGAGED
    n._on_object(_msg(_CUP))
    n._on_object(_msg(_CUP))
    # 3. full skill lifecycle for the first emitted plan (lowercase wire statuses)
    first = n.proposals[0]
    n._on_skill_result(_msg({
        "plan_id": first["plan_id"], "status": "started",
        "selected_skill": first["selected_skill"],
        "priority_class": first["priority_class"],
    }))
    n._on_skill_result(_msg({"plan_id": first["plan_id"], "status": "completed"}))
    # 4. gesture while disabled (suppressed-with-trace path)
    n.gesture_enabled = False
    n._on_gesture(_msg({"gesture": "wave", "confidence": 0.9}))
    n.gesture_enabled = True
    # 5. operator reset
    n._on_reset_context(Empty())


# ── T2A-2: parity ─────────────────────────────────────────────────────────────


def test_shadow_off_default_no_shadow_traces(node):
    assert node.ism_shadow_enabled is False
    _run_scenario(node)
    assert node.proposals, "scenario must emit plans"
    assert _shadow_traces(node) == []


def test_shadow_on_emits_unchanged_plus_shadow_traces():
    a, b = _make_node(), _make_node()
    try:
        b.ism_shadow_enabled = True
        _run_scenario(a)
        _run_scenario(b)
        assert _normalize(a.proposals) == _normalize(b.proposals)
        assert _legacy_traces(a) == _legacy_traces(b)
        kinds = {t["kind"] for t in _shadow_traces(b)}
        assert "candidate" in kinds
        assert "state_transition" in kinds
    finally:
        a.destroy_node()
        b.destroy_node()


def test_shadow_propose_exception_never_breaks_emit(node):
    node.ism_shadow_enabled = True
    node._ism.propose = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    node._on_speech_intent(_msg({"transcript": "停", "session_id": "s9"}))
    assert node.proposals, "emit must survive a shadow explosion"


def test_shadow_signal_exception_never_breaks_skill_result(node):
    node.ism_shadow_enabled = True
    node._ism.apply_signal = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    node._on_skill_result(_msg({"plan_id": "px", "status": "completed"}))


def test_runtime_param_switch_via_callback(node):
    from types import SimpleNamespace

    assert node.ism_shadow_enabled is False
    node._on_set_params([SimpleNamespace(name="ism_shadow_enabled", value=True)])
    assert node.ism_shadow_enabled is True
    node._on_set_params([SimpleNamespace(name="ism_shadow_enabled", value=False)])
    assert node.ism_shadow_enabled is False


def test_shadow_state_tracks_skill_lifecycle(node):
    node.ism_shadow_enabled = True
    node._on_skill_result(_msg({"plan_id": "p1", "status": "started",
                                "selected_skill": "wiggle", "priority_class": 3}))
    assert node._ism.state is IsmState.EXECUTING
    node._on_skill_result(_msg({"plan_id": "p1", "status": "completed"}))
    assert node._ism.state is IsmState.IDLE


def test_tts_bool_edge_drives_speaking(node):
    node.ism_shadow_enabled = True
    assert node._ism.state is IsmState.IDLE
    node._world._snap.tts_playing = True
    node._ism_shadow_tick()
    assert node._ism.state is IsmState.SPEAKING
    node._world._snap.tts_playing = False
    node._ism_shadow_tick()
    assert node._ism.state is IsmState.IDLE
    starts = [t for t in _shadow_traces(node)
              if t["kind"] == "state_transition" and "tts_start" in t["reason"]]
    assert starts


# ── T2A-3: 6/9 blackhole replay ──────────────────────────────────────────────


def test_executing_stuck_cup_greet_suppressed_with_trace(node):
    """6/9 replay: plan never reaches terminal → cup/greet must get an explicit
    SUPPRESS verdict with reason gate:executing, not a silent drop."""
    node.ism_shadow_enabled = True
    node._attention._state = AttentionState.ENGAGED
    node._on_skill_result(_msg({"plan_id": "p-stuck", "status": "started",
                                "selected_skill": "wiggle", "priority_class": 3}))
    assert node._ism.state is IsmState.EXECUTING
    node._on_object(_msg(_CUP))
    node._on_face(_msg({"identity": "roy", "identity_stable": True}))
    sups = [t for t in _shadow_traces(node)
            if t["detail"].get("ism_reason") == "gate:executing"]
    assert len(sups) >= 2, [t.get("detail") for t in _shadow_traces(node)]
    assert all(t["detail"]["ism_verdict"] == "suppress" for t in sups)


def test_alert_stuck_social_suppressed_with_alert_reason(node):
    node.ism_shadow_enabled = True
    node._attention._state = AttentionState.ENGAGED
    node._on_skill_result(_msg({"plan_id": "p-alert", "status": "started",
                                "selected_skill": "stranger_alert",
                                "priority_class": 1}))
    assert node._ism.state is IsmState.ALERT_ACTIVE
    node._on_object(_msg(_CUP))
    sups = [t for t in _shadow_traces(node)
            if t["detail"].get("ism_reason") == "gate:alert_active"]
    assert sups


def test_confirm_pending_social_suppressed_and_ok_executes(node):
    node.ism_shadow_enabled = True
    node._on_gesture(_msg({"gesture": "thumbs_up", "confidence": 0.95}))
    assert node._ism.state is IsmState.CONFIRM_PENDING
    node._attention._state = AttentionState.ENGAGED
    node._on_object(_msg(_CUP))
    sups = [t for t in _shadow_traces(node)
            if t["detail"].get("ism_reason") == "gate:confirm_pending"]
    assert sups, "social during confirm must be suppressed-with-trace, not dropped"
    # OK confirm resolves through the rule:confirmed emit → EXECUTING
    node._emit(build_plan("wiggle", args={}, source="rule:confirmed",
                          reason="confirmed_via_ok:wiggle"))
    assert node._ism.state is IsmState.EXECUTING


def test_watchdog_timeout_recovers_to_idle_with_trace(node):
    node.ism_shadow_enabled = True
    node._on_skill_result(_msg({"plan_id": "p-w", "status": "started",
                                "selected_skill": "wiggle", "priority_class": 3}))
    deadline = node._ism.deadline
    assert deadline is not None, "STARTED must arm the SkillContract.timeout_s watchdog"
    node._ism.tick(deadline + 1.0)
    assert node._ism.state is IsmState.ERROR_RECOVERY
    node._ism.tick(deadline + 2.0)
    assert node._ism.state is IsmState.IDLE
    node._ism_shadow_drain_transitions("")
    watchdogs = [t for t in _shadow_traces(node)
                 if t["kind"] == "state_transition" and "watchdog" in t["reason"]]
    assert watchdogs
