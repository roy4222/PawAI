"""Face baseline observer pure logic for /state/perception/face streams.

The face benchmark is intentionally split from the gesture/object event observer.
Face identity events only emit stable transitions, so this module evaluates the
continuous face state stream where each snapshot contains all current tracks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_IDLE_LABELS = {"unknown", "none", "idle", ""}


@dataclass
class FaceStateSnapshot:
    ts: float
    tracks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FaceRoundMeta:
    capability_id: str
    scenario_id: str
    expected_label: str
    distance_m: float | None = None
    distance_source: str = "manual_declared"
    window_start_ts: float = 0.0


def _known_tracks(snap: FaceStateSnapshot) -> list[dict[str, Any]]:
    return [track for track in snap.tracks if track.get("stable_name", "unknown") != "unknown"]


def evaluate_face_round(meta: FaceRoundMeta, snapshots: list[FaceStateSnapshot]) -> dict[str, Any]:
    is_idle = meta.expected_label in _IDLE_LABELS

    if is_idle:
        for snap in snapshots:
            known = _known_tracks(snap)
            if known:
                track = known[0]
                return _face_record(
                    meta,
                    predicted_label=track["stable_name"],
                    pass_fail="fail",
                    false_trigger=True,
                    confidence=track.get("sim"),
                    distance_m=track.get("distance_m"),
                )

        return _face_record(
            meta,
            predicted_label="unknown",
            pass_fail="pass",
            false_trigger=False,
            confidence=None,
            distance_m=None,
        )

    for snap in snapshots:
        for track in snap.tracks:
            if track.get("stable_name") == meta.expected_label:
                return _face_record(
                    meta,
                    predicted_label=meta.expected_label,
                    pass_fail="pass",
                    false_trigger=False,
                    confidence=track.get("sim"),
                    distance_m=track.get("distance_m"),
                    latency_ms=(snap.ts - meta.window_start_ts) * 1000.0,
                )

    for snap in snapshots:
        known = _known_tracks(snap)
        if known:
            track = known[0]
            return _face_record(
                meta,
                predicted_label=track["stable_name"],
                pass_fail="fail",
                false_trigger=True,
                confidence=track.get("sim"),
                distance_m=track.get("distance_m"),
            )

    return _face_record(
        meta,
        predicted_label="unknown",
        pass_fail="fail",
        false_trigger=False,
        confidence=None,
        distance_m=None,
    )


def _face_record(
    meta: FaceRoundMeta,
    *,
    predicted_label: str,
    pass_fail: str,
    false_trigger: bool,
    confidence: float | None,
    distance_m: float | None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "capability_id": meta.capability_id,
        "scenario_id": meta.scenario_id,
        "scenario_kind": "idle" if meta.expected_label in _IDLE_LABELS else "positive",
        "expected_label": meta.expected_label,
        "predicted_label": predicted_label,
        "pass_fail": pass_fail,
        "false_trigger": false_trigger,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "latency_ms": latency_ms,
        "distance_m": distance_m if distance_m is not None else meta.distance_m,
        "distance_source": "d435_depth" if distance_m is not None else meta.distance_source,
    }


# --- ROS node wrapper sketch (Jetson runtime; not implemented in CI) ---
# class FaceBaselineObserver(Node):
#   - subscribe to /state/perception/face and parse each tick into FaceStateSnapshot
#   - collect snapshots inside the operator-declared round window
#   - call evaluate_face_round(meta, snapshots) when the round ends
#   - enrich the record with run_id/timestamp/git_commit before appending JSONL output
#   * Keep this wrapper thin; do not change face_identity_node and do not connect Brain here.
