"""Unit tests for capability_publisher_node nav_ready decision (Phase A Step 3)."""
import pytest

from nav_capability.lib.nav_ready_check import (
    DEFAULT_COVARIANCE_THRESHOLD,
    DEFAULT_MAX_POSE_AGE_S,
    compute_nav_ready,
)


@pytest.mark.parametrize(
    "pose_age_s,cov,expected",
    [
        # Never received → false
        (None, None, False),
        (None, 0.10, False),
        # AMCL truly dead (>300s) → false
        (400.0, 0.10, False),
        (300.01, 0.10, False),
        # Covariance unknown → false
        (0.5, None, False),
        # Covariance too high (red zone) → false
        (0.5, 0.50, False),
        (0.5, 0.20, False),  # exactly threshold (>= → fail)
        # Healthy (within age window + green) → true
        (0.5, 0.10, True),
        (60.0, 0.19, True),  # stationary robot, AMCL silent — still ready
        (299.99, 0.19, True),
        (0.0, 0.0, True),  # ideal
    ],
)
def test_compute_nav_ready(pose_age_s, cov, expected):
    assert compute_nav_ready(pose_age_s, cov) is expected


def test_default_threshold_constant():
    assert DEFAULT_COVARIANCE_THRESHOLD == 0.20
    assert DEFAULT_MAX_POSE_AGE_S == 300.0


def test_threshold_override():
    """Caller can override threshold for tighter/looser gating."""
    # 0.15 is OK with default 0.20 threshold
    assert compute_nav_ready(0.5, 0.15) is True
    # but fails with stricter 0.10 threshold
    assert compute_nav_ready(0.5, 0.15, covariance_threshold=0.10) is False
