"""Shared JSON event builders for gesture and pose events.

Used by both vision_perception_node and mock_event_publisher.
Output format aligns with interaction_contract.md v2.0 S4.3 / S4.4.
"""
from __future__ import annotations

import time

# v2.0 contract uses "ok" but implementation uses "fist".
# Transition via compat map until 3/25 benchmark confirms switch.
GESTURE_COMPAT_MAP = {"fist": "ok"}


def build_gesture_event(gesture: str, confidence: float, hand: str) -> dict:
    """Build /event/gesture_detected JSON payload.

    stamp and event_type are auto-generated.
    Applies GESTURE_COMPAT_MAP (impl uses "fist", contract sends "ok").
    """
    return {
        "stamp": time.time(),
        "event_type": "gesture_detected",
        "gesture": GESTURE_COMPAT_MAP.get(gesture, gesture),
        "confidence": round(confidence, 4),
        "hand": hand,
    }


def build_pose_event(pose: str, confidence: float, track_id: int = 0) -> dict:
    """Build /event/pose_detected JSON payload.

    track_id: Phase 1 always 0 (no face association).
    Warning: track_id=0 is a Phase 1 internal convention, NOT a contract sentinel.
    Downstream must not use this value for face association logic.
    """
    return {
        "stamp": time.time(),
        "event_type": "pose_detected",
        "pose": pose,
        "confidence": round(confidence, 4),
        "track_id": track_id,
    }
