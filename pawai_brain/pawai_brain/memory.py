"""ConversationMemory — process-local short-term history.

Behaviour mirrors llm_bridge_node._convo_history (deque maxlen=10 = 5 turns).
We expose the public surface needed by the graph nodes: add() and recent().
"""
from __future__ import annotations
import threading
from collections import deque


class ConversationMemory:
    def __init__(self, max_turns: int = 5) -> None:
        # 1 turn = 1 user msg + 1 assistant msg → maxlen = 2 * max_turns
        self._max_turns = max_turns
        self._history: deque = deque(maxlen=2 * max_turns)
        self._lock = threading.Lock()

    def add(self, user_text: str, assistant_reply: str) -> None:
        u = (user_text or "").strip()
        a = (assistant_reply or "").strip()
        if not u or not a:
            return
        with self._lock:
            self._history.append({"role": "user", "content": u})
            self._history.append({"role": "assistant", "content": a})

    def recent(self) -> list[dict]:
        """Return a snapshot copy of current history (oldest first)."""
        with self._lock:
            return list(self._history)

    def depth_turns(self) -> int:
        with self._lock:
            return len(self._history) // 2

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
