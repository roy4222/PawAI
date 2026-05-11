"""N3-C: response_repair verifier rule tests.

Rule-only verifier; never blocks output. Trace `stage='verifier', status='warn'`
fires when reply violates demo-host expectations.
"""
from __future__ import annotations

from pawai_brain.nodes.response_repair import response_repair


def _state(reply: str, mode: str = "chat", capabilities=None, demo_active=False,
           candidate_next=None) -> dict:
    return {
        "llm_json": {"reply": reply},
        "mode": mode,
        "capability_context": {
            "capabilities": capabilities or [],
            "demo_session": {
                "active": demo_active,
                "shown_skills": [],
                "candidate_next": candidate_next or [],
            },
        },
        "trace": [],
    }


def _verifier_trace(out: dict) -> dict | None:
    for t in reversed(out["trace"]):
        if t["stage"] == "verifier":
            return t
    return None


# ── Pre-existing pass-through behaviour (preserve) ────────────────────────


def test_pass_through_when_no_validation_error():
    out = response_repair(_state("這是一個夠長的回答耶你看"))
    assert out["repair_failed"] is False
    assert any(t["stage"] == "repair" and t["status"] == "ok" for t in out["trace"])


def test_validation_error_flips_repair_failed():
    state = _state("這是一個夠長的回答耶你看")
    state["validation_error"] = "bad json"
    out = response_repair(state)
    assert out["repair_failed"] is True


def test_validation_error_skips_verifier():
    """When repair fell back, no verifier warn should fire (avoid noise)."""
    state = _state("X")  # too short — but validation_error short-circuits
    state["validation_error"] = "bad json"
    out = response_repair(state)
    assert _verifier_trace(out) is None


# ── Rule 1: too_short ─────────────────────────────────────────────────────


def test_too_short_reply_warns():
    out = response_repair(_state("好"))
    trace = _verifier_trace(out)
    assert trace is not None
    assert trace["status"] == "warn"
    assert "too_short" in trace["detail"]


def test_long_reply_no_warn():
    out = response_repair(_state("這是一個夠長的回答耶你看看"))
    assert _verifier_trace(out) is None


def test_too_short_still_publishes_reply():
    """repair_failed MUST stay False — verifier only observes."""
    out = response_repair(_state("好"))
    assert out["repair_failed"] is False


# ── Rule 2: no_specific_skill (capability_question mode) ──────────────────


def test_capability_question_generic_reply_warns():
    capabilities = [
        {"name": "wiggle", "display_name": "搖擺"},
        {"name": "wave_hello", "display_name": "揮手打招呼"},
    ]
    out = response_repair(_state(
        "我會很多動作呢你想看哪一個嗎",
        mode="capability_question",
        capabilities=capabilities,
    ))
    trace = _verifier_trace(out)
    assert trace is not None
    assert "no_specific_skill" in trace["detail"]


def test_capability_question_with_skill_name_no_warn():
    capabilities = [{"name": "wiggle", "display_name": "搖擺"}]
    out = response_repair(_state(
        "我會搖擺給你看要不要試試呢",  # contains 搖擺 + followup marker
        mode="capability_question",
        capabilities=capabilities,
    ))
    assert _verifier_trace(out) is None


def test_capability_question_empty_caps_skips_rule():
    """No capabilities loaded → skip rule (avoid false positive)."""
    out = response_repair(_state(
        "我會很多很多動作哦哦哦",
        mode="capability_question",
        capabilities=[],
    ))
    trace = _verifier_trace(out)
    # Either no warn OR warn only contains other reasons (no no_specific_skill)
    if trace is not None:
        assert "no_specific_skill" not in trace["detail"]


def test_capability_question_uses_candidate_next_as_skill_source():
    """If demo_session.candidate_next has labels, those count as 'specific'."""
    out = response_repair(_state(
        "你可以試試 stretch 給你看",
        mode="capability_question",
        capabilities=[],  # empty
        demo_active=True,
        candidate_next=["stretch", "wave"],
    ))
    # capability_question + reply has 'stretch' → no_specific_skill should NOT fire.
    trace = _verifier_trace(out)
    if trace is not None:
        assert "no_specific_skill" not in trace["detail"]


# ── Rule 3: no_followup_invitation (demo active) ──────────────────────────


def test_demo_active_no_followup_marker_warns():
    out = response_repair(_state(
        "我剛剛搖了一下屁股很開心",  # ends with no ?/嗎/要不要
        demo_active=True,
    ))
    trace = _verifier_trace(out)
    assert trace is not None
    assert "no_followup_invitation" in trace["detail"]


def test_demo_active_with_question_mark_no_warn():
    out = response_repair(_state(
        "我搖了一下屁股，要不要再試試？",
        demo_active=True,
    ))
    trace = _verifier_trace(out)
    if trace is not None:
        assert "no_followup_invitation" not in trace["detail"]


def test_demo_inactive_no_followup_rule():
    """Outside demo, lone monolog is fine."""
    out = response_repair(_state(
        "天氣真好我覺得很舒服啊", demo_active=False,
    ))
    trace = _verifier_trace(out)
    if trace is not None:
        assert "no_followup_invitation" not in trace["detail"]


# ── Combined ──────────────────────────────────────────────────────────────


def test_multiple_rules_combined_into_one_detail():
    """Reply that violates 2 rules → both reasons in detail string."""
    out = response_repair(_state(
        "好",  # too short
        mode="capability_question",
        capabilities=[{"name": "wiggle", "display_name": "搖擺"}],
    ))
    trace = _verifier_trace(out)
    assert trace is not None
    # too_short fires; no_specific_skill fires too (no '搖擺' in "好")
    assert "too_short" in trace["detail"]
    assert "no_specific_skill" in trace["detail"]


def test_reply_from_reply_text_fallback():
    """When llm_json.reply absent, use state.reply_text."""
    state = {
        "mode": "chat",
        "reply_text": "好",
        "capability_context": {"capabilities": [], "demo_session": {"active": False}},
        "trace": [],
    }
    out = response_repair(state)
    trace = _verifier_trace(out)
    assert trace is not None
    assert "too_short" in trace["detail"]
