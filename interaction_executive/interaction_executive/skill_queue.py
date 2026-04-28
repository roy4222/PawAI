"""SkillQueue with preemption support for interaction_executive_node."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from .skill_contract import SkillPlan


@dataclass
class PreemptedPlan:
    plan: SkillPlan
    reason: str


class SkillQueue:
    def __init__(self) -> None:
        self._dq: deque[SkillPlan] = deque()
        self._lock = threading.Lock()

    def push(self, plan: SkillPlan) -> None:
        with self._lock:
            self._dq.append(plan)

    def push_front(self, plan: SkillPlan) -> None:
        with self._lock:
            self._dq.appendleft(plan)

    def peek(self) -> SkillPlan | None:
        with self._lock:
            return self._dq[0] if self._dq else None

    def pop(self) -> SkillPlan | None:
        with self._lock:
            return self._dq.popleft() if self._dq else None

    def clear(self, reason: str = "preempted") -> list[PreemptedPlan]:
        with self._lock:
            preempted = [PreemptedPlan(plan, reason) for plan in self._dq]
            self._dq.clear()
            return preempted

    def __len__(self) -> int:
        with self._lock:
            return len(self._dq)
