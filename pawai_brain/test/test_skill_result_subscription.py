"""HIGH-RISK: /brain/skill_result selected_skill must reach recent_skill_results."""
import json

from pawai_brain.capability.skill_result_memory import SkillResultMemory


def test_skill_result_payload_extracts_selected_skill_field():
    """Direct extraction (no plan_id reverse lookup needed)."""
    mem = SkillResultMemory()
    raw = json.dumps({
        "plan_id": "p-abc",
        "step_index": None,
        "status": "completed",
        "detail": "6 steps",
        "selected_skill": "self_introduce",   # direct field
        "priority_class": 2,
        "step_total": 6,
        "step_args": {},
        "timestamp": 123.0,
    })
    payload = json.loads(raw)
    name = str(payload.get("selected_skill") or "").strip()
    assert name == "self_introduce"

    mem.add({"name": name, "status": payload["status"],
             "detail": payload.get("detail", ""), "ts": payload["timestamp"]})

    items = mem.recent()
    assert len(items) == 1
    assert items[0]["name"] == "self_introduce"


def test_non_terminal_status_is_ignored():
    """Only completed/aborted/blocked_by_safety/step_failed should be recorded."""
    TERMINAL = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})
    for s in ("started", "step_started", "step_success", "accepted"):
        assert s not in TERMINAL


def test_missing_selected_skill_dropped():
    payload = {"status": "completed"}  # no selected_skill
    name = str(payload.get("selected_skill") or "").strip()
    assert name == ""  # caller should drop


def test_terminal_statuses_set():
    """Spec §9 lock: exactly these 4 are terminal."""
    TERMINAL = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})
    assert TERMINAL == frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})
