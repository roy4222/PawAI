"""AttentionMachine — 4-state pure Python attention state machine.

States
------
IDLE        No face visible, or face visible < 0.5 s (brief flicker)
NOTICED     Face stable, but person hasn't approached yet
ENGAGED     Face stable + distance ≤ 1.6 m + dwell ≥ 1.5 s
INTERACTING Active plan / speech intent in flight

Design notes
------------
- Pure Python, zero ROS2 dependency — 100% testable with fake clock.
- Caller injects `now: float` (monotonic seconds) so tests can control time
  without sleep.
- No side-effects: transitions only change internal state.

Spec reference: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P2-1
Plan reference: docs/pawai-brain/plans/2026-05-12-attention-policy.md
"""
from __future__ import annotations

from enum import Enum


class AttentionState(str, Enum):
    IDLE = "IDLE"
    NOTICED = "NOTICED"
    ENGAGED = "ENGAGED"
    INTERACTING = "INTERACTING"


# Default thresholds (all in seconds / metres)
_DEFAULT_DWELL_S = 1.5         # seconds near-distance before ENGAGED
_DEFAULT_FACE_LOST_S = 3.0     # seconds without face before dropping state
_DEFAULT_QUIET_S = 8.0         # seconds quiet after plan done before back to ENGAGED
_DEFAULT_ENGAGED_DIST_M = 1.6  # max distance for ENGAGED
_DEFAULT_FACE_STABLE_S = 0.5   # face must be visible this long to leave IDLE


class AttentionMachine:
    """4-state attention machine driven by periodic tick() calls.

    Parameters
    ----------
    dwell_s : float
        How long person must be within engaged_distance_m before ENGAGED.
    face_lost_s : float
        How long face must be absent to fall back to IDLE.
    quiet_s : float
        How long after active_plan=False before transitioning INTERACTING→ENGAGED.
    engaged_distance_m : float
        Maximum distance considered "close enough" for ENGAGED.
    face_stable_s : float
        Minimum face-visible duration to leave IDLE (prevents flicker).
    """

    def __init__(
        self,
        dwell_s: float = _DEFAULT_DWELL_S,
        face_lost_s: float = _DEFAULT_FACE_LOST_S,
        quiet_s: float = _DEFAULT_QUIET_S,
        engaged_distance_m: float = _DEFAULT_ENGAGED_DIST_M,
        face_stable_s: float = _DEFAULT_FACE_STABLE_S,
    ) -> None:
        self.dwell_s = dwell_s
        self.face_lost_s = face_lost_s
        self.quiet_s = quiet_s
        self.engaged_distance_m = engaged_distance_m
        self.face_stable_s = face_stable_s

        self._state: AttentionState = AttentionState.IDLE
        self._state_since: float = 0.0  # monotonic ts when current state was entered

        # Timestamps for dwell / face-lost tracking
        self._face_first_seen_ts: float | None = None   # monotonic ts face appeared
        self._face_last_seen_ts: float | None = None    # monotonic ts of last face tick
        self._dwell_start_ts: float | None = None       # monotonic ts distance entered threshold
        self._plan_done_ts: float | None = None         # monotonic ts plan last went inactive

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> AttentionState:
        return self._state

    @property
    def state_since(self) -> float:
        return self._state_since

    def tick(
        self,
        now: float,
        face_visible: bool,
        distance_m: float | None,
        active_plan: bool,
        speech_intent: bool = False,
    ) -> AttentionState:
        """Advance the state machine by one tick.

        Parameters
        ----------
        now : float
            Current monotonic time (seconds).  Injected for testability.
        face_visible : bool
            True if at least one known or unknown face is detected this tick.
        distance_m : float | None
            Estimated distance to the nearest person (metres).  None if unknown.
        active_plan : bool
            True if brain_node has an active skill/sequence plan running.
        speech_intent : bool
            True if a speech-intent event arrived this tick.

        Returns
        -------
        AttentionState
            Current state after processing this tick.
        """
        self._update_face_timestamps(now, face_visible)
        self._update_dwell(now, distance_m, face_visible)
        self._update_plan_done(now, active_plan)

        if self._state == AttentionState.IDLE:
            self._tick_idle(now, face_visible, active_plan, speech_intent)
        elif self._state == AttentionState.NOTICED:
            self._tick_noticed(now, distance_m, face_visible, active_plan, speech_intent)
        elif self._state == AttentionState.ENGAGED:
            self._tick_engaged(now, face_visible, active_plan, speech_intent)
        elif self._state == AttentionState.INTERACTING:
            self._tick_interacting(now, face_visible, active_plan)

        return self._state

    def reset(self, now: float = 0.0) -> None:
        """Hard reset to IDLE (e.g. on page reset)."""
        self._transition(AttentionState.IDLE, now)
        self._face_first_seen_ts = None
        self._face_last_seen_ts = None
        self._dwell_start_ts = None
        self._plan_done_ts = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, new_state: AttentionState, now: float) -> None:
        if self._state != new_state:
            self._state = new_state
            self._state_since = now

    def _update_face_timestamps(self, now: float, face_visible: bool) -> None:
        if face_visible:
            if self._face_first_seen_ts is None:
                self._face_first_seen_ts = now
            self._face_last_seen_ts = now
        else:
            # Face gone — don't clear face_first_seen yet; let state logic handle it
            pass

    def _face_stable_duration(self, now: float) -> float:
        """Seconds face has been continuously visible."""
        if self._face_first_seen_ts is None or self._face_last_seen_ts is None:
            return 0.0
        # If face not visible this tick, it was visible up to _face_last_seen_ts
        return self._face_last_seen_ts - self._face_first_seen_ts

    def _face_lost_duration(self, now: float, face_visible: bool) -> float:
        """Seconds since face was last seen (0 if currently visible)."""
        if face_visible:
            return 0.0
        if self._face_last_seen_ts is None:
            # Never seen — treat as always lost
            return now
        return now - self._face_last_seen_ts

    def _update_dwell(self, now: float, distance_m: float | None, face_visible: bool) -> None:
        """Track how long person has been within engaged_distance_m."""
        within = (
            face_visible
            and distance_m is not None
            and distance_m <= self.engaged_distance_m
        )
        if within:
            if self._dwell_start_ts is None:
                self._dwell_start_ts = now
        else:
            self._dwell_start_ts = None

    def _dwell_duration(self, now: float) -> float:
        if self._dwell_start_ts is None:
            return 0.0
        return now - self._dwell_start_ts

    def _update_plan_done(self, now: float, active_plan: bool) -> None:
        """Record when plan last became inactive."""
        if not active_plan:
            if self._plan_done_ts is None:
                self._plan_done_ts = now
        else:
            self._plan_done_ts = None  # plan active again, reset quiet timer

    def _quiet_duration(self, now: float) -> float:
        """Seconds since plan became inactive (0 if plan still active)."""
        if self._plan_done_ts is None:
            return 0.0
        return now - self._plan_done_ts

    # ------------------------------------------------------------------
    # Per-state tick methods
    # ------------------------------------------------------------------

    def _tick_idle(
        self,
        now: float,
        face_visible: bool,
        active_plan: bool,
        speech_intent: bool,
    ) -> None:
        if not face_visible:
            # Clear face tracking when in IDLE with no face
            self._face_first_seen_ts = None
            self._face_last_seen_ts = None
            return

        # Face appeared — wait for face_stable_s before NOTICED
        stable_dur = self._face_stable_duration(now)
        if stable_dur >= self.face_stable_s:
            # If already interacting (plan active or speech), jump to INTERACTING
            if active_plan or speech_intent:
                self._transition(AttentionState.INTERACTING, now)
            else:
                self._transition(AttentionState.NOTICED, now)

    def _tick_noticed(
        self,
        now: float,
        distance_m: float | None,
        face_visible: bool,
        active_plan: bool,
        speech_intent: bool,
    ) -> None:
        # Face lost → back to IDLE
        lost = self._face_lost_duration(now, face_visible)
        if lost >= self.face_lost_s:
            self._transition(AttentionState.IDLE, now)
            self._face_first_seen_ts = None
            self._face_last_seen_ts = None
            return

        # Speech intent or plan → INTERACTING (user is actively engaging)
        if active_plan or speech_intent:
            self._transition(AttentionState.INTERACTING, now)
            return

        # Close enough + long enough → ENGAGED
        dwell = self._dwell_duration(now)
        if dwell >= self.dwell_s:
            self._transition(AttentionState.ENGAGED, now)

    def _tick_engaged(
        self,
        now: float,
        face_visible: bool,
        active_plan: bool,
        speech_intent: bool,
    ) -> None:
        # Face lost → back to IDLE (no grace period needed; they left)
        lost = self._face_lost_duration(now, face_visible)
        if lost >= self.face_lost_s:
            self._transition(AttentionState.IDLE, now)
            self._face_first_seen_ts = None
            self._face_last_seen_ts = None
            return

        # Active plan or speech → INTERACTING
        if active_plan or speech_intent:
            self._transition(AttentionState.INTERACTING, now)

    def _tick_interacting(
        self,
        now: float,
        face_visible: bool,
        active_plan: bool,
    ) -> None:
        # Face lost → IDLE (regardless of plan)
        lost = self._face_lost_duration(now, face_visible)
        if lost >= self.face_lost_s:
            self._transition(AttentionState.IDLE, now)
            self._face_first_seen_ts = None
            self._face_last_seen_ts = None
            return

        # Plan done + quiet for quiet_s → ENGAGED
        quiet = self._quiet_duration(now)
        if not active_plan and quiet >= self.quiet_s:
            self._transition(AttentionState.ENGAGED, now)
