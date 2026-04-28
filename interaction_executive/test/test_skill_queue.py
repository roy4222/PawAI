"""Tests for skill_queue.py."""
from interaction_executive.skill_contract import build_plan
from interaction_executive.skill_queue import SkillQueue


def _plan():
    return build_plan("stop_move")


def test_push_pop_fifo():
    queue = SkillQueue()
    p1, p2 = _plan(), _plan()
    queue.push(p1)
    queue.push(p2)
    assert len(queue) == 2
    assert queue.pop() is p1
    assert queue.pop() is p2
    assert queue.pop() is None


def test_push_front_puts_plan_at_head():
    queue = SkillQueue()
    p1, p2 = _plan(), _plan()
    queue.push(p1)
    queue.push_front(p2)
    assert queue.peek() is p2


def test_clear_returns_preempted_plans():
    queue = SkillQueue()
    p1, p2 = _plan(), _plan()
    queue.push(p1)
    queue.push(p2)
    preempted = queue.clear(reason="safety_preempt")
    assert [item.plan for item in preempted] == [p1, p2]
    assert all(item.reason == "safety_preempt" for item in preempted)
    assert len(queue) == 0


def test_clear_empty_returns_empty_list():
    assert SkillQueue().clear() == []
