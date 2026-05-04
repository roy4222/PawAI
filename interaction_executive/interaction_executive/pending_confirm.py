"""PendingConfirm state machine — OK 二次確認共用邏輯.

Spec:
  - docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md §4.2
  - docs/pawai-brain/specs/2026-05-04-phase-b-implementation-notes.md §2

Active Confirm Set (4): wiggle / stretch / approach_person /
                       nav_demo_point (非 Studio button trigger)

Behaviour:
  - request_confirm(skill, args, now) → 進 Pending
  - tick(now, current_gesture):
      - now - started_at > timeout_s          → CANCELLED("timeout")
      - current_gesture == "ok":
          - 累積 ok_stable_since
          - now - ok_stable_since >= stable_s → CONFIRMED(skill, args)
      - current_gesture in {"", None}:        → 維持 Pending，但 ok_stable_since 重置
      - other gesture:                        → CANCELLED("different_gesture")

Pure Python. Zero ROS2 dependency. 100% pytest-able.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfirmState(str, Enum):
    IDLE = "idle"
    PENDING = "pending"


class ConfirmOutcomeKind(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class ConfirmOutcome:
    kind: ConfirmOutcomeKind
    skill: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    @classmethod
    def pending(cls) -> "ConfirmOutcome":
        return cls(ConfirmOutcomeKind.PENDING)

    @classmethod
    def confirmed(cls, skill: str, args: dict[str, Any]) -> "ConfirmOutcome":
        return cls(ConfirmOutcomeKind.CONFIRMED, skill=skill, args=dict(args))

    @classmethod
    def cancelled(cls, reason: str) -> "ConfirmOutcome":
        return cls(ConfirmOutcomeKind.CANCELLED, reason=reason)


_NEUTRAL_GESTURES = frozenset({"", None})


def _normalize_gesture(g: str | None) -> str | None:
    if g is None:
        return None
    g = g.strip().lower()
    return g or None


class PendingConfirm:
    """5-second OK confirmation gate shared by high-risk skills."""

    def __init__(
        self,
        timeout_s: float = 5.0,
        stable_s: float = 0.5,
        ok_gesture: str = "ok",
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if stable_s < 0:
            raise ValueError("stable_s must be non-negative")
        self.timeout_s = float(timeout_s)
        self.stable_s = float(stable_s)
        self.ok_gesture = ok_gesture.strip().lower()
        self._reset()

    # ---- public state inspection -----------------------------------------

    @property
    def state(self) -> ConfirmState:
        return self._state

    @property
    def pending_skill(self) -> str | None:
        return self._skill

    @property
    def pending_args(self) -> dict[str, Any]:
        return dict(self._args)

    # ---- transitions ------------------------------------------------------

    def request_confirm(
        self,
        skill: str,
        args: dict[str, Any] | None,
        now: float,
    ) -> ConfirmOutcome:
        """Enter Pending state. Replaces any prior pending request.

        Returns ConfirmOutcome.pending().
        """
        self._state = ConfirmState.PENDING
        self._skill = skill
        self._args = dict(args or {})
        self._started_at = float(now)
        self._ok_stable_since = None
        return ConfirmOutcome.pending()

    def cancel(self, reason: str = "manual") -> ConfirmOutcome:
        """Force-cancel any pending request."""
        if self._state == ConfirmState.IDLE:
            return ConfirmOutcome.cancelled("not_pending")
        self._reset()
        return ConfirmOutcome.cancelled(reason)

    def tick(self, now: float, current_gesture: str | None) -> ConfirmOutcome:
        """Advance the state machine one tick.

        - If Idle: returns PENDING (no-op outcome). Caller should treat as
          "nothing to do".
        - If Pending: evaluate timeout / OK stability / wrong-gesture.
        """
        if self._state == ConfirmState.IDLE:
            return ConfirmOutcome.pending()

        # Pending branch.
        if now - self._started_at > self.timeout_s:
            self._reset()
            return ConfirmOutcome.cancelled("timeout")

        gesture = _normalize_gesture(current_gesture)

        if gesture == self.ok_gesture:
            if self._ok_stable_since is None:
                self._ok_stable_since = float(now)
            if now - self._ok_stable_since >= self.stable_s:
                skill = self._skill
                args = dict(self._args)
                self._reset()
                assert skill is not None  # invariant: pending always has a skill
                return ConfirmOutcome.confirmed(skill, args)
            return ConfirmOutcome.pending()

        if gesture in _NEUTRAL_GESTURES:
            # No gesture this tick — break stability streak but stay pending.
            self._ok_stable_since = None
            return ConfirmOutcome.pending()

        # Any other concrete gesture cancels the pending request.
        self._reset()
        return ConfirmOutcome.cancelled("different_gesture")

    # ---- internal --------------------------------------------------------

    def _reset(self) -> None:
        self._state = ConfirmState.IDLE
        self._skill: str | None = None
        self._args: dict[str, Any] = {}
        self._started_at = 0.0
        self._ok_stable_since: float | None = None
