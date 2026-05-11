"""Process-local cache of /state/* topics used by capability_builder."""
from __future__ import annotations
import json
import threading
import time
from collections import deque

from .effective_status import WorldFlags


_OBJECT_RECENT_MAXLEN = 8
_OBJECT_WINDOW_S = 30.0


class WorldStateSnapshot:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tts_playing: bool = False
        self.obstacle: bool = False
        self.nav_safe: bool = True
        self.active_skill = None
        self.active_skill_step: int = 0
        # N3-A: object cache for JIT prompt inject.
        # Stores {"class": str, "color": str|None, "ts": float} — recent first.
        self._recent_objects: deque = deque(maxlen=_OBJECT_RECENT_MAXLEN)

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

    def apply_object_detected_json(self, raw: str) -> None:
        """N3-A: ingest /event/object_detected payload into recent_objects cache.

        Schema (from object_perception_node):
          {"stamp": float, "event_type": "object_detected",
           "objects": [{"class_name": str, "confidence": float,
                        "bbox": [...], "color"?: str, "color_confidence"?: float}, ...]}

        We store one entry per class_name (latest wins) so the prompt doesn't
        get spammed by 5 sequential "chair" detections within cooldown window.
        """
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        objects = data.get("objects") or []
        if not isinstance(objects, list):
            return
        now = time.time()
        with self._lock:
            existing = {entry["class"]: entry for entry in self._recent_objects}
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                cls = str(obj.get("class_name") or "").strip()
                if not cls:
                    continue
                color = obj.get("color")
                color = str(color).strip() if color and color != "Unknown" else None
                existing[cls] = {"class": cls, "color": color, "ts": now}
            # Order: latest ts first.
            sorted_entries = sorted(existing.values(), key=lambda e: e["ts"], reverse=True)
            self._recent_objects = deque(
                sorted_entries[:_OBJECT_RECENT_MAXLEN], maxlen=_OBJECT_RECENT_MAXLEN
            )

    def get_recent_objects(self, window_s: float = _OBJECT_WINDOW_S) -> list[dict]:
        """Return recent objects within window_s; each entry has age_s computed."""
        now = time.time()
        with self._lock:
            out = []
            for entry in self._recent_objects:
                age = now - float(entry.get("ts", 0.0))
                if age <= window_s:
                    out.append({
                        "class": entry["class"],
                        "color": entry.get("color"),
                        "age_s": round(age, 1),
                    })
            return out

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
            base = {
                "tts_playing": self.tts_playing,
                "obstacle": self.obstacle,
                "nav_safe": self.nav_safe,
                "active_skill": self.active_skill,
                "active_skill_step": self.active_skill_step,
            }
        # N3-A: recent_objects with computed age (own lock inside get_*).
        base["recent_objects"] = self.get_recent_objects()
        return base
