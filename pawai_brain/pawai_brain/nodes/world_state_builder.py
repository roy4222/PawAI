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
_WEATHER_CACHE = {"text": "", "ts": 0.0}
_WEATHER_TTL_S = 600.0


def set_world_provider(fn: Callable[[], WorldStateSnapshot]) -> None:
    global _world_provider
    _world_provider = fn


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

    snap_dict = snap.to_dict()
    state["world_state"] = {
        "period": period,
        "time": time_str,
        "weather": weather,
        "source": state.get("source", "speech"),
        "timestamp": time.time(),
        **snap_dict,
    }
    state.setdefault("trace", []).append(
        {
            "stage": "world_state",
            "status": "ok",
            "detail": f"{period} {time_str}",
        }
    )
    return state
