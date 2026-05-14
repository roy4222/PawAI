"""Route JSON schema validator (schema_version=1)."""
from typing import Any, Dict

SUPPORTED_SCHEMA_VERSIONS = {1}
ALLOWED_TASKS = {"normal", "wait", "tts"}
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
