"""Tests for route_validator (schema_version=1)."""
import pytest

from nav_capability.lib.route_validator import (
    RouteValidationError,
    validate_route,
)


VALID = {
    "schema_version": 1,
    "route_id": "test1",
    "frame_id": "map",
    "map_id": "m1",
    "created_at": "2026-04-26T00:00:00+08:00",
    "initial_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
    "waypoints": [
        {
            "id": "wp1",
            "task": "normal",
            "pose": {"x": 1.0, "y": 0.0, "yaw": 0.0},
            "tolerance": 0.3,
            "timeout_sec": 30,
        },
    ],
}


def test_valid_passes():
    validate_route(VALID)


def test_missing_schema_version_fails():
    bad = {k: v for k, v in VALID.items() if k != "schema_version"}
    with pytest.raises(RouteValidationError, match="schema_version"):
        validate_route(bad)


def test_unknown_schema_version_fails():
    bad = {**VALID, "schema_version": 99}
    with pytest.raises(RouteValidationError, match="schema_version"):
        validate_route(bad)


def test_missing_frame_id_fails():
    bad = {k: v for k, v in VALID.items() if k != "frame_id"}
    with pytest.raises(RouteValidationError, match="missing required keys"):
        validate_route(bad)


def test_frame_id_must_be_map():
    bad = {**VALID, "frame_id": "odom"}
    with pytest.raises(RouteValidationError, match="frame_id"):
        validate_route(bad)


def test_waypoints_empty_fails():
    bad = {**VALID, "waypoints": []}
    with pytest.raises(RouteValidationError, match="waypoints"):
        validate_route(bad)


def test_waypoint_unknown_task_fails():
    bad = {
        **VALID,
        "waypoints": [
            {
                "id": "x",
                "task": "object_scan",
                "pose": {"x": 0, "y": 0, "yaw": 0},
                "tolerance": 0.3,
                "timeout_sec": 30,
            },
        ],
    }
    with pytest.raises(RouteValidationError, match="task"):
        validate_route(bad)


def test_waypoint_wait_requires_wait_sec():
    bad = {
        **VALID,
        "waypoints": [
            {
                "id": "x",
                "task": "wait",
                "pose": {"x": 0, "y": 0, "yaw": 0},
                "tolerance": 0.3,
                "timeout_sec": 30,
            },
        ],
    }
    with pytest.raises(RouteValidationError, match="wait_sec"):
        validate_route(bad)


def test_waypoint_tts_requires_tts_text():
    bad = {
        **VALID,
        "waypoints": [
            {
                "id": "x",
                "task": "tts",
                "pose": {"x": 0, "y": 0, "yaw": 0},
                "tolerance": 0.3,
                "timeout_sec": 30,
            },
        ],
    }
    with pytest.raises(RouteValidationError, match="tts_text"):
        validate_route(bad)
