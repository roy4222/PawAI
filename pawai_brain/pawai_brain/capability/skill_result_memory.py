"""Process-local FIFO of recent terminal skill_result events."""
from __future__ import annotations
import threading
from collections import deque


class SkillResultMemory:
    def __init__(self, maxlen: int = 5) -> None:
        self._dq: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, entry: dict) -> None:
        with self._lock:
            self._dq.append(dict(entry))

    def recent(self) -> list:
        with self._lock:
            return [dict(e) for e in self._dq]

    def clear(self) -> None:
        with self._lock:
            self._dq.clear()
