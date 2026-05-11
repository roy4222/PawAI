"""world_state_builder — fold time + perception flags into state.world_state."""
from __future__ import annotations
import time
from datetime import datetime
from typing import Callable

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..capability.world_snapshot import WorldStateSnapshot
from ..state import ConversationState


_world_provider: Callable[[], WorldStateSnapshot] = lambda: WorldStateSnapshot()
_speaker_provider: Callable[[], tuple[str, float]] = lambda: ("unknown", 0.0)
# N5-B: pose / gesture latest-one providers, mirror speaker pattern.
_pose_provider: Callable[[], tuple[str, float]] = lambda: ("none", 0.0)
_gesture_provider: Callable[[], tuple[str, float]] = lambda: ("none", 0.0)
_SPEAKER_STALE_S = 3.0  # identity older than 3s → treat as unknown
_POSE_STALE_S = 10.0    # N5-B: pose changes infrequently — wider window
_GESTURE_STALE_S = 5.0  # N5-B: gesture is transient — tighter window
_WEATHER_CACHE = {"text": "", "ts": 0.0}
_WEATHER_TTL_S = 600.0


def set_world_provider(fn: Callable[[], WorldStateSnapshot]) -> None:
    global _world_provider
    _world_provider = fn


def set_speaker_provider(fn: Callable[[], tuple[str, float]]) -> None:
    """1H: register a provider for current_speaker (name, timestamp).

    fn() returns (identity: str, last_seen_ts: float).
    If identity == 'unknown' or age > _SPEAKER_STALE_S, world_state injects 'unknown'.
    """
    global _speaker_provider
    _speaker_provider = fn


def set_pose_provider(fn: Callable[[], tuple[str, float]]) -> None:
    """N5-B: register a provider for latest pose (name, timestamp)."""
    global _pose_provider
    _pose_provider = fn


def set_gesture_provider(fn: Callable[[], tuple[str, float]]) -> None:
    """N5-B: register a provider for latest gesture (name, timestamp)."""
    global _gesture_provider
    _gesture_provider = fn


def _time_of_day_zh(hour: int) -> str:
    if 5 <= hour < 11:
        return "早上"
    if 11 <= hour < 13:
        return "中午"
    if 13 <= hour < 17:
        return "下午"
    if 17 <= hour < 19:
        return "傍晚"
    if 19 <= hour < 23:
        return "晚上"
    return "深夜"


def _get_weather() -> str:
    now = time.time()
    if _WEATHER_CACHE["text"] and now - _WEATHER_CACHE["ts"] < _WEATHER_TTL_S:
        return _WEATHER_CACHE["text"]
    if requests is None:
        return ""
    try:
        resp = requests.get(
            "https://wttr.in/Taipei?format=%C+%t+濕度%h&lang=zh-tw",
            timeout=2.0,
        )
        if resp.status_code != 200:
            return ""
        text = resp.text.strip()
        if not text or len(text) > 80 or text.startswith("<"):
            return ""
    except Exception:
        return ""
    _WEATHER_CACHE["text"] = text
    _WEATHER_CACHE["ts"] = now
    return text


def world_state_builder(state: ConversationState) -> ConversationState:
    snap = _world_provider()
    now_dt = datetime.now()
    period = _time_of_day_zh(now_dt.hour)
    time_str = now_dt.strftime("%H:%M")
    weather = _get_weather()

    # 1H: current_speaker from face state subscription
    identity, ts = _speaker_provider()
    if identity and identity != "unknown" and (time.time() - ts) < _SPEAKER_STALE_S:
        current_speaker = identity
    else:
        current_speaker = "unknown"

    # N5-B: pose / gesture providers — same age-filter pattern as speaker.
    now = time.time()
    pose_name, pose_ts = _pose_provider()
    if pose_name and pose_name != "none" and (now - pose_ts) < _POSE_STALE_S:
        current_pose = {"name": pose_name, "age_s": round(now - pose_ts, 1)}
    else:
        current_pose = None
    gesture_name, gesture_ts = _gesture_provider()
    if gesture_name and gesture_name != "none" and (now - gesture_ts) < _GESTURE_STALE_S:
        current_gesture = {"name": gesture_name, "age_s": round(now - gesture_ts, 1)}
    else:
        current_gesture = None

    snap_dict = snap.to_dict()
    state["world_state"] = {
        "period": period,
        "time": time_str,
        "weather": weather,
        "source": state.get("source", "speech"),
        "timestamp": time.time(),
        "current_speaker": current_speaker,
        "current_pose": current_pose,
        "current_gesture": current_gesture,
        **snap_dict,
    }
    # N3-A / N5-B: trace detail extension — smoke can verify
    # objs/spk/pose/gst arrived without echoing full prompt.
    n_objs = len(snap_dict.get("recent_objects") or [])
    pose_tag = (current_pose or {}).get("name") or "none"
    gst_tag = (current_gesture or {}).get("name") or "none"
    state.setdefault("trace", []).append(
        {
            "stage": "world_state",
            "status": "ok",
            "detail": f"{period} {time_str} objs={n_objs} spk={current_speaker} pose={pose_tag} gst={gst_tag}",
        }
    )
    return state
