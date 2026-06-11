"""Perception Event Router — Phase 0 (Plan D, 2026-06-10).

Pure-Python extraction of the five JSON-parsing prologs that lived inline in
brain_node callbacks. SEMANTICS ARE LIFTED VERBATIM from the current
brain_node.py (post Plan C merge, 2026-06-11): speech :549-552,
gesture :802-805, face :1108-1129, pose :1217, object :1309-1321.
Behavior-frozen: the golden fixture suite (test_router_golden.py) asserts
identical /brain/proposal output with the router on vs off. No gating /
cooldown / dedup lives here — Phase 0 is parsing only; timers/dedup
relocation is a later ISM-phase decision.

Verbatim-fidelity notes (differences from the plan's draft, resolved in
favor of the live source per the plan's own extraction discipline):
- gesture: or-chain is gesture|type|label and the result is .strip().lower();
  empty string (not None) when absent — the callback's `if not gesture` guard
  relies on it.
- face: identity strips WITHOUT re-defaulting to "unknown" (a whitespace-only
  identity must stay "" so the callback's `if not identity` branch fires);
  stable checks identity_stable|stable|event_type=="identity_stable";
  distance reads distance_m|depth_m via or-chain and converts with
  try/except float() (numeric strings accepted — isinstance would reject).
- pose: or-chain pose|posture, .strip().lower().
- object: class_name fallbacks class_name|label|class on the first array
  element (or the flat payload), .strip(); color is str+strip with ""
  default. Empty/absent class_name stays "" (callback guard `if not
  class_name: return`).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerceptionEvent:
    kind: str                      # face | object | gesture | pose | speech
    source_topic: str
    ts: float
    raw: dict[str, Any]
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    # face
    identity: str | None = None
    stable: bool = False
    distance_m: float | None = None
    event_type: str | None = None
    # object — first detection's derived fields + the raw list
    class_name: str | None = None
    color: str | None = None
    objects: list[dict[str, Any]] = field(default_factory=list)
    # gesture
    gesture: str | None = None
    # pose
    pose: str | None = None
    # speech
    transcript: str | None = None
    session_id: str | None = None


def parse_speech(payload: dict[str, Any]) -> PerceptionEvent:
    # Verbatim from brain_node._on_speech_intent (:549-552).
    transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
    session_id = str(
        payload.get("session_id") or payload.get("request_id") or f"speech-{time.time_ns()}"
    )
    return PerceptionEvent(
        kind="speech", source_topic="/event/speech_intent_recognized",
        ts=time.time(), raw=payload, transcript=transcript, session_id=session_id,
    )


def parse_gesture(payload: dict[str, Any]) -> PerceptionEvent:
    # Verbatim from brain_node._on_gesture (:802-805).
    gesture = str(
        payload.get("gesture") or payload.get("type") or payload.get("label") or ""
    ).strip().lower()
    return PerceptionEvent(
        kind="gesture", source_topic="/event/gesture_detected",
        ts=time.time(), raw=payload, gesture=gesture,
    )


def parse_face(payload: dict[str, Any]) -> PerceptionEvent:
    # Verbatim from brain_node._on_face (:1108-1129). The or-chain accepts both
    # the real wire format {stable_name, event_type} and the doc-era
    # {identity, identity_stable}. Order and strip behavior must not change.
    identity = str(
        payload.get("identity")
        or payload.get("stable_name")
        or payload.get("name")
        or "unknown"
    ).strip()
    stable = bool(
        payload.get("identity_stable")
        or payload.get("stable")
        or payload.get("event_type") == "identity_stable"
    )
    distance_m: float | None = None
    raw_dist = payload.get("distance_m") or payload.get("depth_m")
    if raw_dist is not None:
        try:
            distance_m = float(raw_dist)
        except (TypeError, ValueError):
            distance_m = None
    event_type = str(payload.get("event_type") or "")
    return PerceptionEvent(
        kind="face", source_topic="/event/face_identity", ts=time.time(), raw=payload,
        identity=identity, stable=stable, distance_m=distance_m, event_type=event_type,
    )


def parse_pose(payload: dict[str, Any]) -> PerceptionEvent:
    # Verbatim from brain_node._on_pose (:1217).
    pose = str(payload.get("pose") or payload.get("posture") or "").strip().lower()
    return PerceptionEvent(
        kind="pose", source_topic="/event/pose_detected",
        ts=time.time(), raw=payload, pose=pose,
    )


def parse_object(payload: dict[str, Any]) -> PerceptionEvent:
    # Verbatim from brain_node._on_object (:1309-1321): production format takes
    # the first detection in the "objects" array; legacy/test format is the
    # payload itself as a flat single-object dict.
    objects = payload.get("objects")
    if isinstance(objects, list) and objects:
        det = objects[0]
        class_name = str(
            det.get("class_name") or det.get("label") or det.get("class") or ""
        ).strip()
        color = str(det.get("color") or "").strip()
        kept = objects
    else:
        class_name = str(
            payload.get("class_name") or payload.get("label") or payload.get("class") or ""
        ).strip()
        color = str(payload.get("color") or "").strip()
        kept = [payload] if class_name else []
    return PerceptionEvent(
        kind="object", source_topic="/event/object_detected", ts=time.time(), raw=payload,
        objects=kept, class_name=class_name, color=color,
    )
