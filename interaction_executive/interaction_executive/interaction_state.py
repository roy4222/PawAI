"""Interaction State Machine — ROS-free core (Plan ISM Phase 0, master plan §7).

The PawAI Brain today is an *implicit* state machine: five perception callbacks
each race for the TTS/plan channel, gated by a scatter of demo flags + cooldowns
+ active_plan + pending_confirm checks (19 separate `_suppressed` early-returns in
brain_node.py). This module is the *explicit* replacement core.

Phase 0 scope (this file): pure types + policy + machine ONLY. It is NOT imported
by brain_node yet — no runtime wiring, no behaviour change. Later phases run it in
shadow mode, then cut brain_node's gates over to it one family at a time behind an
`ism_enabled` flag. See docs/superpowers/plans/2026-06-11-plan-ism-interaction-state-machine.md.

Design rules honoured here (master plan §7):
- §7.1 perception events only ever produce a `Candidate`; they never drive a
  transition directly (the four transition drivers are skill_result lifecycle,
  confirm result, TTS ack, operator command — plus a safety override).
- §7.2 priority iron law: safety > explicit command > confirm > spontaneous social.
- §7.3 every active interaction carries a watchdog deadline → ERROR_RECOVERY on
  expiry (kills the 6/9 "stranger plan deadlocks everything" failure).
- §7.4 pending-confirm is not a black hole: every candidate gets an explicit
  verdict (ACCEPT / PREEMPT / QUEUE / SUPPRESS-with-reason), never a silent drop.

No rclpy, no I/O, no time.time() — `now` is always injected so the machine is
deterministic and unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class InteractionState(str, Enum):
    IDLE = "idle"                        # 無互動；接受任何候選
    LISTENING = "listening"              # 正在聽語音（chat_buffer 在飛）
    SPEAKING = "speaking"                # 正在播 TTS（社交候選讓路）
    CONFIRM_PENDING = "confirm_pending"  # 等 OK 二確；只認 OK/cancel/timeout
    EXECUTING = "executing"              # 正在執行 skill/sequence（感知只記錄）
    ALERT_ACTIVE = "alert_active"        # 高優先警示播報中（stranger/fallen）
    SAFETY_HOLD = "safety_hold"          # 硬安全停止保持（stop/emergency/obstacle）
    ERROR_RECOVERY = "error_recovery"    # watchdog/STEP_FAILED 後恢復 → 回 IDLE


class Priority(IntEnum):
    """Smaller = higher priority (§3.4 iron law)."""
    SAFETY = 0
    ALERT = 1
    EXPLICIT = 2
    CONFIRM = 3
    SOCIAL = 4


class Verdict(str, Enum):
    ACCEPT = "accept"        # 進狀態 / emit
    SUPPRESS = "suppress"    # 不做，附 reason trace（非黑洞）
    QUEUE = "queue"          # 短暫保留（SPEAKING 中的社交）
    PREEMPT = "preempt"      # 搶占當前 active interaction


class TriggerKind(str, Enum):
    """The four legitimate transition drivers (§3.2) plus the safety override."""
    SKILL_RESULT = "skill_result"
    CONFIRM_RESULT = "confirm_result"
    TTS_ACK = "tts_ack"
    OPERATOR = "operator"
    SAFETY = "safety"


@dataclass(frozen=True)
class Candidate:
    """A candidate intent produced by perception/speech/gesture.

    `source` is advisory metadata, NOT an authorization (§3.3 source-trust): a
    perception event cannot self-assert `source=studio_button` to bypass a
    confirmation. Only the policy, against the current state, decides.
    """
    kind: str                  # greet | object_remark | sit_along | gesture_cmd | chat | alert | stop ...
    priority: Priority
    source: str                # face | object | gesture | pose | speech | studio | operator
    skill: str = ""            # skill to emit if ACCEPTed
    args: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    decision_id: str = ""
    explicit: bool = False     # True = trusted explicit command (§3.3)


@dataclass(frozen=True)
class TransitionSignal:
    """A non-candidate state driver (§3.2): skill lifecycle / confirm result /
    TTS ack / operator command."""
    trigger: TriggerKind
    detail: dict[str, Any] = field(default_factory=dict)
    decision_id: str = ""


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str                                  # gate:executing / preempt:safety / accept ...
    next_state: InteractionState | None = None   # None = no transition
    emit_skill: str = ""
    emit_args: dict[str, Any] = field(default_factory=dict)


# Per-state allow-set: which candidate priorities may be admitted / pre-empt the
# current state (§3.4). A priority NOT in the set is suppressed-with-reason (or
# queued, for social-during-speaking). This single table replaces the 19 scattered
# `_suppressed` early-returns in brain_node.py.
_S = InteractionState
_P = Priority
_PREEMPTIBLE_BY: dict[InteractionState, set[Priority]] = {
    _S.IDLE:            {_P.SAFETY, _P.ALERT, _P.EXPLICIT, _P.CONFIRM, _P.SOCIAL},
    _S.LISTENING:       {_P.SAFETY, _P.ALERT, _P.EXPLICIT},
    _S.SPEAKING:        {_P.SAFETY, _P.ALERT, _P.EXPLICIT},
    _S.CONFIRM_PENDING: {_P.SAFETY, _P.ALERT, _P.EXPLICIT, _P.CONFIRM},
    _S.EXECUTING:       {_P.SAFETY, _P.ALERT},   # explicit-stop handled as SAFETY candidate
    _S.ALERT_ACTIVE:    {_P.SAFETY},
    _S.SAFETY_HOLD:     {_P.SAFETY},             # only safety-clear / operator leaves
    _S.ERROR_RECOVERY:  {_P.SAFETY},
}
# Safety/alert candidates route to their dedicated states when admitted.
_PRIORITY_TARGET: dict[Priority, InteractionState] = {
    _P.SAFETY: _S.SAFETY_HOLD,
    _P.ALERT: _S.ALERT_ACTIVE,
}

# skill_result terminal statuses that clear EXECUTING/ALERT_ACTIVE (mirrors
# brain_node._TERMINAL_RESULT_STATUSES).
_TERMINAL = frozenset({"COMPLETED", "ABORTED", "BLOCKED_BY_SAFETY", "STEP_FAILED"})

# How long a CONFIRM_PENDING waits for OK before the watchdog gives up (§3.6;
# mirrors pending_confirm.py's existing 30s).
CONFIRM_TIMEOUT_S = 30.0


class InteractionPolicy:
    """Pure, stateless arbitration: given the current state and a candidate,
    return a Decision. No side effects — the machine applies it."""

    @staticmethod
    def evaluate(state: InteractionState, c: Candidate) -> Decision:
        allowed = _PREEMPTIBLE_BY[state]

        # CONFIRM_PENDING only resolves via a CONFIRM-priority candidate (§3.5).
        if state is _S.CONFIRM_PENDING and c.priority is _P.CONFIRM:
            if c.kind == "confirm_ok":
                return Decision(Verdict.ACCEPT, "confirm_ok", _S.EXECUTING, c.skill, c.args)
            return Decision(Verdict.ACCEPT, "confirm_cancel", _S.IDLE)

        # Not admitted by this state → suppress (or queue social during speaking).
        if c.priority not in allowed:
            verb = Verdict.QUEUE if (state is _S.SPEAKING and c.priority is _P.SOCIAL) else Verdict.SUPPRESS
            return Decision(verb, f"gate:{state.value}")

        # Safety / alert → dedicated pre-empt target.
        if c.priority in _PRIORITY_TARGET:
            return Decision(Verdict.PREEMPT, f"preempt:{c.priority.name.lower()}",
                            _PRIORITY_TARGET[c.priority], c.skill, c.args)

        # A skill needing confirmation always routes through CONFIRM_PENDING —
        # never bypassed by a self-asserted source (§3.3 / security P2-1).
        if c.requires_confirmation:
            return Decision(Verdict.ACCEPT, "confirm_request", _S.CONFIRM_PENDING, c.skill, c.args)

        # An explicit command supersedes an in-flight confirm (§3.5).
        if state is _S.CONFIRM_PENDING and c.explicit:
            return Decision(Verdict.PREEMPT, "confirm_superseded",
                            _S.EXECUTING if c.skill else _S.LISTENING, c.skill, c.args)

        # Plain accept: explicit-with-skill executes; everything else speaks.
        target = _S.EXECUTING if (c.explicit and c.skill) else _S.SPEAKING
        return Decision(Verdict.ACCEPT, "accept", target, c.skill, c.args)


class InteractionStateMachine:
    """Holds the current interaction state + watchdog deadline + a short history.

    Two entry points mirror the design: `propose(candidate)` for perception/intent
    candidates (arbitrated by InteractionPolicy), and `apply_signal(signal)` for the
    four transition drivers. `tick(now)` enforces the watchdog. All `now` values are
    injected — the machine never reads the clock itself.
    """

    def __init__(self, now: float = 0.0, state: InteractionState = InteractionState.IDLE,
                 deadline: float | None = None) -> None:
        self.state = state
        self._deadline = deadline
        self._active_plan_id = ""
        # (ts, from_state, to_state, trigger) — bounded ring for trace/diagnostics.
        self.history: list[tuple[float, str, str, str]] = []

    @property
    def deadline(self) -> float | None:
        return self._deadline

    def propose(self, c: Candidate, now: float) -> Decision:
        """Arbitrate a candidate against the current state; apply any transition."""
        d = InteractionPolicy.evaluate(self.state, c)
        if d.next_state is not None and d.verdict in (Verdict.ACCEPT, Verdict.PREEMPT):
            deadline = now + CONFIRM_TIMEOUT_S if d.next_state is _S.CONFIRM_PENDING else None
            self._transition(self.state, d.next_state, f"candidate:{c.kind}", now, deadline=deadline)
        return d

    def apply_signal(self, sig: TransitionSignal, now: float = 0.0) -> None:
        """Apply a non-candidate transition driver (§3.2)."""
        if sig.trigger is TriggerKind.SKILL_RESULT:
            status = sig.detail.get("status", "")
            if status == "STARTED":
                prio = int(sig.detail.get("priority_class", int(Priority.SOCIAL)))
                nxt = _S.ALERT_ACTIVE if prio == int(Priority.ALERT) else _S.EXECUTING
                self._active_plan_id = sig.detail.get("plan_id", "")
                t = float(sig.detail.get("timeout_s", 0) or 0)
                self._transition(self.state, nxt, "skill_started", now,
                                 deadline=(now + t) if t > 0 else None)
            elif status in _TERMINAL and sig.detail.get("plan_id", "") == self._active_plan_id:
                self._active_plan_id = ""
                self._transition(self.state, _S.IDLE, f"skill_{status.lower()}", now)
        elif sig.trigger is TriggerKind.TTS_ACK:
            if sig.detail.get("event") == "start":
                self._transition(self.state, _S.SPEAKING, "tts_start", now)
            elif self.state is _S.SPEAKING:
                self._transition(self.state, _S.IDLE, "tts_end", now)
        elif sig.trigger is TriggerKind.OPERATOR and sig.detail.get("op") == "reset":
            self._active_plan_id = ""
            self._transition(self.state, _S.IDLE, "operator_reset", now)

    def tick(self, now: float) -> Decision | None:
        """Watchdog (§3.6): if the current interaction's deadline has passed, drop
        to ERROR_RECOVERY → IDLE and return a watchdog Decision for tracing."""
        if self._deadline is not None and now >= self._deadline:
            stuck = self.state
            self._active_plan_id = ""
            self._transition(stuck, _S.IDLE, "watchdog", now)
            return Decision(Verdict.PREEMPT, f"watchdog_timeout:{stuck.value}", _S.IDLE)
        return None

    def _transition(self, frm: InteractionState, to: InteractionState, trigger: str,
                    now: float, deadline: float | None = None) -> None:
        self.state = to
        self._deadline = deadline
        self.history.append((now, frm.value, to.value, trigger))
        if len(self.history) > 64:
            self.history = self.history[-64:]
