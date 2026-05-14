# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

"""5/11 B0 + 5/11 night Roy review fix — reactive_stop 4-mode state machine.

Critical behaviors under test:

1. **`hold_brake` mode**: ALWAYS return 0.0 in EVERY zone (permanent brake).
   Used for B5 safety verification + demo emergency hold. Holds mux priority
   200 forever — operator must switch mode to release.

2. **`progressive` mode**: danger → 0.0, slow/clear → None (silent).
   Used with nav stack — let nav (priority 10) control via mux timeout.
   ⚠️ Has known mux timeout vulnerability if teleop hot-publishes 0.5 m/s.
   Demo discipline: kill teleop before using progressive mode.

3. **`released` mode**: ALL zones → None (no publish), but caller's _on_scan
   still updates zone state. Operator-controlled hand-off to nav.

4. **`disabled` mode**: ALL zones → None.

5. **Standalone fallback (mode="")**: legacy zone-based velocity
   (0 / slow / normal). For demo backup when nav stack is down.

6. **Threshold defaults (B0.3)**: `danger_distance_m`=1.1, `slow_distance_m`=1.7
   in LiDAR frame (Go2 nose at base_link+~0.40m, LiDAR at +0.175m, so 1.1m
   LiDAR = 0.7m nose buffer for braking).

Direct file import bypassing package __init__ (which requires aioice).
"""
import os
import sys

import pytest

# Direct file import bypassing package __init__
_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "go2_robot_sdk")
sys.path.insert(0, _HELPERS_DIR)
from lidar_geometry import classify_zone, decide_velocity  # noqa: E402


SLOW_SPEED = 0.45
NORMAL_SPEED = 0.60


# --- Mode hold_brake: ALWAYS 0.0 (permanent brake) ---


class TestHoldBrakeAlwaysZero:
    """5/11 B0.1 fix → 5/11 night renamed: permanent brake, not auto-release."""

    @pytest.mark.parametrize("zone", ["danger", "slow", "clear", "emergency", "init"])
    def test_hold_brake_returns_zero_for_all_zones(self, zone):
        v = decide_velocity(zone, "hold_brake", SLOW_SPEED, NORMAL_SPEED)
        assert v == 0.0, f"hold_brake must publish 0 in zone {zone}, got {v}"

    def test_hold_brake_ignores_speed_params(self):
        v = decide_velocity("clear", "hold_brake", 10.0, 20.0)
        assert v == 0.0


# --- Mode progressive: danger=0, slow/clear silent ---


class TestProgressiveMode:
    """5/11 fix-前 behavior — danger publishes 0, slow/clear silent.

    Has known mux timeout vulnerability — only safe with teleop discipline.
    """

    def test_progressive_danger_returns_zero(self):
        v = decide_velocity("danger", "progressive", SLOW_SPEED, NORMAL_SPEED)
        assert v == 0.0

    def test_progressive_emergency_returns_zero(self):
        v = decide_velocity("emergency", "progressive", SLOW_SPEED, NORMAL_SPEED)
        assert v == 0.0

    def test_progressive_slow_returns_none(self):
        """Silent in slow — nav stack expected to manage speed."""
        v = decide_velocity("slow", "progressive", SLOW_SPEED, NORMAL_SPEED)
        assert v is None

    def test_progressive_clear_returns_none(self):
        v = decide_velocity("clear", "progressive", SLOW_SPEED, NORMAL_SPEED)
        assert v is None


# --- Mode released: silent in all zones ---


class TestReleasedMode:
    """Operator-controlled release — reactive_stop 不 publish 但 LiDAR 仍更新 zone state."""

    @pytest.mark.parametrize("zone", ["danger", "slow", "clear", "emergency", "init"])
    def test_released_returns_none_for_all_zones(self, zone):
        v = decide_velocity(zone, "released", SLOW_SPEED, NORMAL_SPEED)
        assert v is None, f"released must NOT publish in zone {zone}, got {v}"


# --- Mode disabled: silent in all zones ---


class TestDisabledMode:
    @pytest.mark.parametrize("zone", ["danger", "slow", "clear", "emergency", "init"])
    def test_disabled_returns_none_for_all_zones(self, zone):
        v = decide_velocity(zone, "disabled", SLOW_SPEED, NORMAL_SPEED)
        assert v is None


# --- Standalone fallback (mode="" or unset) — legacy 0/slow/normal ---


class TestStandaloneFallback:
    """Legacy behavior — reactive_stop 直接驅動 Go2 (nav stack 不在時 demo 備援)."""

    def test_standalone_danger_returns_zero(self):
        v = decide_velocity("danger", "", SLOW_SPEED, NORMAL_SPEED)
        assert v == 0.0

    def test_standalone_emergency_returns_zero(self):
        v = decide_velocity("emergency", "", SLOW_SPEED, NORMAL_SPEED)
        assert v == 0.0

    def test_standalone_slow_returns_slow_speed(self):
        v = decide_velocity("slow", "", SLOW_SPEED, NORMAL_SPEED)
        assert v == pytest.approx(SLOW_SPEED)

    def test_standalone_clear_returns_normal_speed(self):
        v = decide_velocity("clear", "", SLOW_SPEED, NORMAL_SPEED)
        assert v == pytest.approx(NORMAL_SPEED)

    def test_standalone_init_returns_normal(self):
        """init transient → normal (rare, only at boot before first scan)."""
        v = decide_velocity("init", "", SLOW_SPEED, NORMAL_SPEED)
        assert v == pytest.approx(NORMAL_SPEED)


# --- B0.3 threshold zoning consistency at new defaults 1.1 / 1.7 ---


class TestEnlargedThresholdsClassifyZone:
    """5/11 B0.3 — danger 0.6→1.1m, slow 1.0→1.7m."""

    DANGER_NEW = 1.1
    SLOW_NEW = 1.7

    def test_below_new_danger_threshold(self):
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

    def test_old_safe_distance_now_slow(self):
        """The 1.5m obstacle that crashed Go2 on 5/11 — under new thresholds
        it's classified `slow` (1.1 ≤ 1.5 < 1.7), giving reactive_stop +
        nav buffer. Combined with hold_brake mode (always-0), Go2 stays put
        when teleop is hot-publishing 0.5."""
        assert classify_zone(1.5, self.DANGER_NEW, self.SLOW_NEW) == "slow"


# --- Cross-validation: zone × mode matrix ---


class TestZoneModeMatrix:
    """Compact matrix coverage of decide_velocity × classify_zone integration."""

    @pytest.mark.parametrize("dist,expected_zone", [
        (0.5, "danger"),
        (1.0, "danger"),
        (1.5, "slow"),
        (2.0, "clear"),
    ])
    def test_distance_to_zone_to_velocity_hold_brake(self, dist, expected_zone):
        zone = classify_zone(dist, 1.1, 1.7)
        assert zone == expected_zone
        v = decide_velocity(zone, "hold_brake", SLOW_SPEED, NORMAL_SPEED)
        assert v == 0.0  # hold_brake always 0

    @pytest.mark.parametrize("dist,expected_zone,expected_v", [
        (0.5, "danger", 0.0),    # progressive blocks danger
        (1.5, "slow", None),     # progressive silent in slow
        (2.0, "clear", None),    # progressive silent in clear
    ])
    def test_distance_to_zone_to_velocity_progressive(self, dist, expected_zone, expected_v):
        zone = classify_zone(dist, 1.1, 1.7)
        assert zone == expected_zone
        v = decide_velocity(zone, "progressive", SLOW_SPEED, NORMAL_SPEED)
        assert v == expected_v  # None or 0.0

    @pytest.mark.parametrize("dist,expected_zone,expected_v", [
        (0.5, "danger", 0.0),
        (1.5, "slow", SLOW_SPEED),
        (2.0, "clear", NORMAL_SPEED),
    ])
    def test_distance_to_zone_to_velocity_standalone(self, dist, expected_zone, expected_v):
        zone = classify_zone(dist, 1.1, 1.7)
        assert zone == expected_zone
        v = decide_velocity(zone, "", SLOW_SPEED, NORMAL_SPEED)
        assert v == pytest.approx(expected_v)


# --- Defensive: unrecognized mode falls back to standalone ---


class TestUnrecognizedModeFallback:
    """Defensive: unknown mode strings fall back to standalone (legacy
    behavior). Node init also logs a warning + promotes to hold_brake at
    the node level — this lower-level helper is more permissive."""

    def test_unknown_mode_uses_standalone_velocities(self):
        v = decide_velocity("clear", "nonsense_mode", SLOW_SPEED, NORMAL_SPEED)
        assert v == pytest.approx(NORMAL_SPEED)
        v2 = decide_velocity("danger", "nonsense_mode", SLOW_SPEED, NORMAL_SPEED)
        assert v2 == 0.0
