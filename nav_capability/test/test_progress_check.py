"""Pure-function tests for nav_action_server progress-timeout helper (BUG #2 / A2).

Real pause/cancel/re-send flow is validated on Jetson with K-pause; here we only
guard the math + None handling so the timeout decision is well-defined.
"""
import pytest

from nav_capability.lib.progress_check import (
    PROGRESS_THRESHOLD_M,
    has_progress,
)


@pytest.mark.parametrize(
    "prev,curr,threshold,expected",
    [
        # 有進度 (above threshold)
        ((0.0, 0.0), (0.06, 0.0), 0.05, True),
        ((1.0, 1.0), (1.04, 1.04), 0.05, True),  # diagonal hypot ≈ 0.0566
        # 無進度 (below threshold)
        ((0.0, 0.0), (0.03, 0.0), 0.05, False),
        ((0.0, 0.0), (0.0, 0.0), 0.05, False),
        # threshold 邊界 (>= 視為有進度)
        ((0.0, 0.0), (0.05, 0.0), 0.05, True),
        ((0.0, 0.0), (0.04999, 0.0), 0.05, False),
        # None 視為無進度
        (None, (1.0, 1.0), 0.05, False),
        ((1.0, 1.0), None, 0.05, False),
        (None, None, 0.05, False),
    ],
)
def test_has_progress(prev, curr, threshold, expected):
    assert has_progress(prev, curr, threshold) is expected


def test_default_threshold_constant():
    """Make sure default threshold matches what the node uses; if someone bumps the
    default they should bump it on purpose, not silently drift the test."""
    assert PROGRESS_THRESHOLD_M == 0.05


def test_default_threshold_when_omitted():
    """Calling has_progress without explicit threshold uses PROGRESS_THRESHOLD_M."""
    # 0.06m > 0.05m default → True
    assert has_progress((0.0, 0.0), (0.06, 0.0)) is True
    # 0.04m < 0.05m default → False
    assert has_progress((0.0, 0.0), (0.04, 0.0)) is False
