"""Route JSON schema validator (schema_version=1)."""
import os
import re
from typing import Any, Dict

SUPPORTED_SCHEMA_VERSIONS = {1}
ALLOWED_TASKS = {"normal", "wait", "tts"}
ROUTE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
REQUIRED_TOP_KEYS = {
    "schema_version",
    "route_id",
    "frame_id",
    "map_id",
    "initial_pose",
    "waypoints",
}
REQUIRED_WAYPOINT_KEYS = {"id", "task", "pose", "tolerance", "timeout_sec"}


class RouteValidationError(ValueError):
    """Raised when route JSON fails schema validation."""


def sanitize_route_name(name: str) -> str:
    """Return a filesystem-safe route_id / route name, or raise RouteValidationError.

    T5S-2 source of truth: Lane 5 security hardening plan requires
    os.path.basename plus whitelist [A-Za-z0-9_-] for nav route_id/name values.
    Percent-encoded path separators are rejected by disallowing percent-encoding.
    """
    if not isinstance(name, str):
        raise RouteValidationError("route name must be a string")

    if not name or not name.strip():
        raise RouteValidationError("route name must not be empty")

    if "%" in name:
        raise RouteValidationError("route name must not contain percent-encoding")

    if name in {".", ".."}:
        raise RouteValidationError("route name must not be '.' or '..'")

    if "/" in name or "\\" in name:
        raise RouteValidationError("route name must not contain path separators")

    basename = os.path.basename(name)
    if not basename or basename in {".", ".."}:
        raise RouteValidationError("route name must not collapse to empty or traversal")

    if not ROUTE_NAME_PATTERN.fullmatch(basename):
        raise RouteValidationError(
            "route name must contain only [A-Za-z0-9_-] characters"
        )

    return basename


def validate_route(route: Dict[str, Any]) -> None:
    """Raise RouteValidationError if route is not v1-compliant."""
    if not isinstance(route, dict):
        raise RouteValidationError("route must be a dict")

    missing = REQUIRED_TOP_KEYS - set(route.keys())
    if missing:
        raise RouteValidationError(f"missing required keys: {missing}")

    sv = route["schema_version"]
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        raise RouteValidationError(
            f"schema_version {sv} not supported (require {SUPPORTED_SCHEMA_VERSIONS})"
        )

    if route["frame_id"] != "map":
        raise RouteValidationError(
            f"frame_id must be 'map', got '{route['frame_id']}'"
        )

    waypoints = route["waypoints"]
    if not isinstance(waypoints, list) or len(waypoints) == 0:
        raise RouteValidationError("waypoints must be a non-empty list")

    for i, wp in enumerate(waypoints):
        prefix = f"waypoints[{i}]"
        if not isinstance(wp, dict):
            raise RouteValidationError(f"{prefix}: must be a dict")
        missing_wp = REQUIRED_WAYPOINT_KEYS - set(wp.keys())
        if missing_wp:
            raise RouteValidationError(f"{prefix}: missing keys {missing_wp}")
        task = wp["task"]
        if task not in ALLOWED_TASKS:
            raise RouteValidationError(
                f"{prefix}: task '{task}' not in {ALLOWED_TASKS}"
            )
        if task == "wait" and "wait_sec" not in wp:
            raise RouteValidationError(f"{prefix}: task=wait requires wait_sec")
        if task == "tts" and "tts_text" not in wp:
            raise RouteValidationError(f"{prefix}: task=tts requires tts_text")
        for k in ("x", "y", "yaw"):
            if k not in wp["pose"]:
                raise RouteValidationError(f"{prefix}.pose missing '{k}'")
