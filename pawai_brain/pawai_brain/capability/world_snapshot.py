"""Process-local cache of /state/* topics used by capability_builder."""
from __future__ import annotations
import json
import threading

from .effective_status import WorldFlags


class WorldStateSnapshot:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tts_playing: bool = False
        self.obstacle: bool = False
        self.nav_safe: bool = True
        self.active_skill = None
        self.active_skill_step: int = 0

    # ── apply_*: called from ROS subscription callbacks ──

    def apply_tts_playing(self, value: bool) -> None:
        with self._lock:
            self.tts_playing = bool(value)

    def apply_reactive_stop_status_json(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self._lock:
            self.obstacle = bool(data.get("obstacle", False))

    def apply_nav_safety_json(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self._lock:
            self.nav_safe = bool(data.get("nav_safe", True))

    def apply_pawai_brain_state_json(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        plan = data.get("active_plan") or {}
        with self._lock:
            self.active_skill = plan.get("selected_skill") if isinstance(plan, dict) else None
            self.active_skill_step = int(plan.get("step_index", 0)) if isinstance(plan, dict) else 0

    # ── consumers ──

    def to_world_flags(self) -> WorldFlags:
        with self._lock:
            return WorldFlags(
                tts_playing=self.tts_playing,
                obstacle=self.obstacle,
                nav_safe=self.nav_safe,
            )

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "tts_playing": self.tts_playing,
                "obstacle": self.obstacle,
                "nav_safe": self.nav_safe,
                "active_skill": self.active_skill,
                "active_skill_step": self.active_skill_step,
            }
