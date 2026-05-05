"""Pure decision functions for interaction_router.

No ROS2 dependency — testable with pytest alone.
Only three rules: welcome, gesture_command, fall_alert.
"""
from __future__ import annotations

import time

# Only these gestures produce a gesture_command event.
# Everything else is ignored (node layer logs them as debug).
#
# 2026-05-05: raw MOC gestures are published on /event/gesture_detected for
# Studio/Brain. This legacy interaction_router path only forwards gestures
# that event_action_bridge can execute directly. Do not add palm/thumb/peace
# here unless GESTURE_ACTION_MAP grows matching actions; otherwise the router
# emits half-dead gesture_command events.
#
# Legacy aliases (stop/thumbs_up) kept temporarily so any old test
# fixtures still pass; production path emits new MOC names directly.
GESTURE_WHITELIST = {"stop", "thumbs_up", "ok"}


def should_welcome(
    face_event: dict,
    welcomed_tracks: set[int],
) -> dict | None:
    """Decide if a welcome event should be emitted.

    Triggers only on identity_stable for a known (non-unknown) person
    who hasn't been welcomed in this session yet.
    """
    if face_event.get("event_type") != "identity_stable":
        return None
    name = face_event.get("stable_name", "unknown")
    if name == "unknown":
        return None
    track_id = face_event.get("track_id")
    if track_id in welcomed_tracks:
        return None
    return {
        "stamp": time.time(),
        "event_type": "welcome",
        "track_id": track_id,
        "name": name,
        "sim": face_event.get("sim", 0.0),
        "distance_m": face_event.get("distance_m"),
    }


def should_gesture_command(
    gesture_event: dict,
    latest_face_state: dict | None,
) -> dict | None:
    """Enrich whitelisted gesture with face context.

    Non-whitelisted gestures return None (caller should log them).
    """
    gesture = gesture_event.get("gesture")
    if not gesture or gesture not in GESTURE_WHITELIST:
        return None

    who = None
    face_track_id = None
    if latest_face_state:
        for track in latest_face_state.get("tracks", []):
            if track.get("stable_name", "unknown") != "unknown":
                who = track["stable_name"]
                face_track_id = track.get("track_id")
                break  # take first known face

    return {
        "stamp": time.time(),
        "event_type": "gesture_command",
        "gesture": gesture,
        "confidence": gesture_event.get("confidence", 0.0),
        "hand": gesture_event.get("hand", "unknown"),
        "who": who,
        "face_track_id": face_track_id,
    }


def should_fall_alert(
    pose: str,
    fallen_first_ts: float,
    persist_threshold: float,
) -> bool:
    """Check if fallen pose has persisted long enough.

    Returns True if pose is 'fallen' and elapsed time >= threshold.
    Timer management and event assembly are done in the node layer.
    """
    if pose != "fallen":
        return False
    elapsed = time.time() - fallen_first_ts
    return elapsed >= persist_threshold
