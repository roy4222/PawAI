"""env_builder — time always; weather best-effort.

Time mapping mirrors llm_bridge_node._time_of_day_zh (5/4 spec).
Weather lookup is intentionally optional and fast — wttr.in best-effort
with 2 s timeout; failures yield empty string and never raise.
"""
from __future__ import annotations
import time
from datetime import datetime

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..state import ConversationState


# Process-local weather cache (10 min TTL).
_WEATHER_CACHE: dict = {"text": "", "ts": 0.0}
_WEATHER_TTL_S = 600.0


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
    if (
        _WEATHER_CACHE["text"]
        and now - _WEATHER_CACHE["ts"] < _WEATHER_TTL_S
    ):
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


def env_builder(state: ConversationState) -> ConversationState:
    now_dt = datetime.now()
    period = _time_of_day_zh(now_dt.hour)
    weather = _get_weather()
    state["env_context"] = {
        "period": period,
        "time": now_dt.strftime("%H:%M"),
        "weather": weather,
    }
    state.setdefault("trace", []).append(
        {
            "stage": "env",
            "status": "ok" if weather else "fallback",
            "detail": f"{period} {now_dt.strftime('%H:%M')}{' ' + weather if weather else ''}",
        }
    )
    return state
