# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

"""B0.6 unit tests — release gate + threshold defaults + classify_zone consistency.

Critical behavior under test (5/11 B5 burndown fix):

1. **Release gate (B0.1)**: `decide_velocity(safety_only=True, ...)` MUST return
   0.0 in EVERY zone (danger/slow/clear/emergency). Otherwise mux 0.5s timeout
   hands /cmd_vel back to stale teleop /cmd_vel_joy=0.5 and Go2 walks into
   obstacles. Reproduced 5/11 — Go2 hit a 1.5m obstacle.

2. **Threshold defaults (B0.3)**: `danger_distance_m` default raised from 0.6
   to 1.1 m, `slow_distance_m` from 1.0 to 1.7 m. LiDAR mounted base_link+0.175m,
   Go2 nose at base_link+~0.40m, so previous 0.6m LiDAR-frame distance =
   0.2m at the nose → guaranteed crash.

3. **Standalone mode unchanged**: when safety_only=False, behavior preserves
   the legacy zone-based velocity (0 / slow / normal). This is the demo
   fallback when nav stack is down.

Direct file import bypassing package __init__ (which requires aioice).
Pattern follows test_reactive_stop_node.py.
"""
import math
import os
import sys

import pytest

# Direct file import bypassing package __init__
_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "go2_robot_sdk")
sys.path.insert(0, _HELPERS_DIR)
from lidar_geometry import classify_zone, decide_velocity  # noqa: E402


SLOW_SPEED = 0.45
NORMAL_SPEED = 0.60


# --- B0.1 release gate: safety_only=True ALWAYS returns 0 ---


class TestSafetyOnlyAlwaysZero:
    """5/11 B5 撞牆 fix — safety_only mode never relinquishes mux priority 200."""

    @pytest.mark.parametrize("zone", ["danger", "slow", "clear", "emergency", "init"])
    def test_safety_only_returns_zero_for_all_zones(self, zone):
        v = decide_velocity(zone, safety_only=True,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == 0.0, f"safety_only must publish 0 in zone {zone}, got {v}"

    def test_safety_only_ignores_speed_params(self):
        """Even if slow_speed/normal_speed are non-zero, safety_only forces 0."""
        v = decide_velocity("clear", safety_only=True,
                            slow_speed=10.0, normal_speed=20.0)
        assert v == 0.0

    def test_safety_only_unknown_zone_still_zero(self):
        """Defensive: unrecognized zone string still returns 0 in safety mode."""
        v = decide_velocity("nonsense_zone", safety_only=True,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == 0.0


# --- Standalone mode (safety_only=False) — legacy behavior preserved ---


class TestStandaloneModeVelocityByZone:
    """Demo fallback when nav stack is down — reactive_stop drives Go2 directly."""

    def test_standalone_danger_returns_zero(self):
        v = decide_velocity("danger", safety_only=False,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == 0.0

    def test_standalone_emergency_returns_zero(self):
        """LiDAR timeout — same as danger."""
        v = decide_velocity("emergency", safety_only=False,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == 0.0

    def test_standalone_slow_returns_slow_speed(self):
        v = decide_velocity("slow", safety_only=False,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == pytest.approx(SLOW_SPEED)

    def test_standalone_clear_returns_normal_speed(self):
        v = decide_velocity("clear", safety_only=False,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == pytest.approx(NORMAL_SPEED)

    def test_standalone_init_returns_normal(self):
        """init transient → normal (rare, only at boot before first scan)."""
        v = decide_velocity("init", safety_only=False,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == pytest.approx(NORMAL_SPEED)


# --- B0.3 threshold zoning consistency at new defaults 1.1 / 1.7 ---


class TestEnlargedThresholdsClassifyZone:
    """5/11 B0.3 — danger 0.6→1.1m, slow 1.0→1.7m. Verify classify_zone behaves
    correctly at boundaries that matter for Go2 mechanical geometry."""

    DANGER_NEW = 1.1  # was 0.6
    SLOW_NEW = 1.7    # was 1.0

    def test_below_new_danger_threshold(self):
        # 5/11 incident range: object at LiDAR 0.57m → was already in danger,
        # but at 1.0m (still danger under new threshold, was clear under old).
        assert classify_zone(1.0, self.DANGER_NEW, self.SLOW_NEW) == "danger"

    def test_at_new_danger_boundary(self):
        # Strict-less-than → 1.1 is NOT danger
        assert classify_zone(1.1, self.DANGER_NEW, self.SLOW_NEW) == "slow"

    def test_between_new_danger_and_slow(self):
        assert classify_zone(1.4, self.DANGER_NEW, self.SLOW_NEW) == "slow"

    def test_at_new_slow_boundary(self):
        assert classify_zone(1.7, self.DANGER_NEW, self.SLOW_NEW) == "clear"

    def test_above_new_slow_threshold(self):
        assert classify_zone(2.5, self.DANGER_NEW, self.SLOW_NEW) == "clear"

    def test_old_safe_distance_now_danger(self):
        """The 1.5m obstacle that crashed Go2 on 5/11 — under new thresholds
        it would be classified `slow` (1.1 ≤ 1.5 < 1.7), giving reactive_stop
        and Nav2 buffer to react. Combined with always-publish-0 in
        safety_only mode, Go2 stays put when teleop is hot-publishing 0.5."""
        assert classify_zone(1.5, self.DANGER_NEW, self.SLOW_NEW) == "slow"


# --- Cross-validation: zone × safety_only matrix ---


class TestZoneSafetyMatrix:
    """Compact matrix coverage of decide_velocity × classify_zone integration."""

    @pytest.mark.parametrize("dist,expected_zone", [
        (0.5, "danger"),   # very close — emergency in old config too
        (1.0, "danger"),   # was "clear" under old 0.6/1.0; NOW "danger"
        (1.5, "slow"),     # 5/11 撞牆對象，新閾值下 slow zone
        (2.0, "clear"),
    ])
    def test_distance_to_zone_to_velocity_safety_mode(self, dist, expected_zone):
        zone = classify_zone(dist, 1.1, 1.7)
        assert zone == expected_zone
        # In safety mode the answer is always 0 regardless
        v = decide_velocity(zone, safety_only=True,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == 0.0

    @pytest.mark.parametrize("dist,expected_zone,expected_v", [
        (0.5, "danger", 0.0),
        (1.5, "slow", SLOW_SPEED),
        (2.0, "clear", NORMAL_SPEED),
    ])
    def test_distance_to_zone_to_velocity_standalone_mode(self, dist, expected_zone, expected_v):
        zone = classify_zone(dist, 1.1, 1.7)
        assert zone == expected_zone
        v = decide_velocity(zone, safety_only=False,
                            slow_speed=SLOW_SPEED, normal_speed=NORMAL_SPEED)
        assert v == pytest.approx(expected_v)
