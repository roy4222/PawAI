import json

from pawai_contracts.trace_schema import TraceEvent, TraceKind, Verdict, make_suppressed


def test_round_trip_json():
    ev = TraceEvent(decision_id="d1", node="brain_node", kind=TraceKind.POLICY_DECISION,
                    verdict=Verdict.SUPPRESSED, gate="demo_phase", reason="phase:s3_object")
    d = json.loads(ev.to_json())
    assert d["decision_id"] == "d1" and d["verdict"] == "suppressed" and d["ts"] > 0


def test_make_suppressed_carries_roy_required_fields():
    ev = make_suppressed(
        decision_id="d2", node="brain_node", gate="gesture_enabled",
        reason="gesture_enabled=false", demo_phase="all",
        active_plan="stranger_alert", pending_confirm="PENDING:wiggle",
        cooldown_remaining_s=12.5, source_summary="gesture=thumbs_up conf=0.95",
    )
    d = json.loads(ev.to_json())
    for key in ("gate", "reason", "demo_phase", "active_plan", "pending_confirm",
                "cooldown_remaining_s", "source_summary"):
        assert key in d["detail"], key


def test_verdict_and_kind_enums_frozen():
    assert {v.value for v in Verdict} == {"accepted", "suppressed", "blocked"}
    assert {k.value for k in TraceKind} == {
        "perception_event", "candidate", "policy_decision",
        "plan_emitted", "skill_result", "tts_state",
    }


def test_plan_id_only_when_set():
    base = TraceEvent(decision_id="d3", node="brain_node",
                      kind=TraceKind.PLAN_EMITTED, verdict=Verdict.ACCEPTED)
    assert "plan_id" not in json.loads(base.to_json())
    withid = TraceEvent(decision_id="d3", node="brain_node",
                        kind=TraceKind.PLAN_EMITTED, verdict=Verdict.ACCEPTED,
                        plan_id="p-1")
    assert json.loads(withid.to_json())["plan_id"] == "p-1"
