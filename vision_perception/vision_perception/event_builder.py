"""Shared JSON event builders for gesture and pose events.

Used by both vision_perception_node and mock_event_publisher.
Output format aligns with interaction_contract.md v2.0 S4.3 / S4.4.
"""
from __future__ import annotations

import time

# GESTURE_COMPAT_MAP — historical compat layer, EMPTIED 2026-05-05 to align
# with MOC §3 9-gesture spec (Fist = Mute, OK = Confirm — two distinct
# semantics; routing fist→ok silently corrupted the enum).
#
# OK now comes ONLY from gesture_classifier.detect_ok_circle() geometric
# rule, never from MediaPipe Closed_Fist. Constant kept (empty) so callers
# importing this name don't break, but no actual rewriting happens.
GESTURE_COMPAT_MAP: dict[str, str] = {}


def build_gesture_event(gesture: str, confidence: float, hand: str) -> dict:
    """Build /event/gesture_detected JSON payload.

    stamp and event_type are auto-generated.
    GESTURE_COMPAT_MAP is empty (5/5 cleanup) — gestures pass through unchanged.

    Note: confidence is vote ratio (fraction of buffer frames matching the gesture),
    not raw classifier confidence. E.g. 0.67 = 2/3 frames voted for this gesture.
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

    Note: confidence is vote ratio (fraction of buffer frames matching the pose),
    not raw classifier confidence. E.g. 0.85 = 17/20 frames voted for this pose.
    """
    return {
        "stamp": time.time(),
        "event_type": "pose_detected",
        "pose": pose,
        "confidence": round(confidence, 4),
        "track_id": track_id,
    }
