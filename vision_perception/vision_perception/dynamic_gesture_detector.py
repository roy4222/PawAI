"""Dynamic (temporal) gesture detectors.

Pure Python — no ROS2, no GPU. Each detector keeps a small rolling buffer
of wrist KP samples and emits a True/False decision on every tick.

Currently implements:
  • WaveDetector — left↔right hand sweep (MOC §3 group 3 "Wave / Greeting")

ComeHere / Circle (also MOC group 3) would live here when their detectors
land, but are deferred to post-demo per `~/.claude/plans/speech-bright-rivest.md`
Phase 2 Out-of-Scope.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class _Sample:
    ts: float
    x: float
    y: float


class WaveDetector:
    """Detect a hand wave by counting X-direction velocity reversals.

    Definition (MOC §3 dynamic gesture):
      • the hand sweeps left↔right (wrist X coord oscillates)
      • amplitude (max-min X within window) is wide enough that we don't
        confuse it with idle hand jitter
      • at least N velocity-sign reversals within the window

    All thresholds are pixel-space; tuned for ~640×480 D435 frames at
    ~15 Hz publishing. Increase `min_amplitude_px` if false positives appear
    (e.g. when the user just holds a still hand).
    """

    def __init__(
        self,
        window_s: float = 1.5,
        min_reversals: int = 2,
        min_amplitude_px: float = 50.0,
        min_samples: int = 6,
    ) -> None:
        self.window_s = window_s
        self.min_reversals = min_reversals
        self.min_amplitude_px = min_amplitude_px
        self.min_samples = min_samples
        self._samples: deque[_Sample] = deque()

    def reset(self) -> None:
        self._samples.clear()

    def feed(self, ts: float, x: float, y: float) -> None:
        """Append a wrist KP sample (in pixel coords)."""
        self._samples.append(_Sample(ts=ts, x=float(x), y=float(y)))
        cutoff = ts - self.window_s
        while self._samples and self._samples[0].ts < cutoff:
            self._samples.popleft()

    def detect(self) -> bool:
        """Return True iff the buffered samples look like a wave."""
        if len(self._samples) < self.min_samples:
            return False

        xs = [s.x for s in self._samples]
        amplitude = max(xs) - min(xs)
        if amplitude < self.min_amplitude_px:
            return False

        reversals = 0
        last_sign = 0  # 0 = unknown, +1 = moving right, -1 = moving left
        for prev, cur in zip(self._samples, list(self._samples)[1:]):
            dx = cur.x - prev.x
            if abs(dx) < 1.0:  # ignore noise frames
                continue
            sign = 1 if dx > 0 else -1
            if last_sign != 0 and sign != last_sign:
                reversals += 1
            last_sign = sign
        return reversals >= self.min_reversals
