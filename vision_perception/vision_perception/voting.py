# vision_perception/vision_perception/voting.py
"""Temporal majority-vote helper.

Pure Python — no ROS2 — so the gesture/pose voting rule is unit-testable
(vision_perception_node.py imports rclpy and can't be imported in CI).
"""
from __future__ import annotations

from collections.abc import Iterable


def majority_vote(buffer: Iterable, min_votes: int = 1) -> str | None:
    """Return the most common non-None element, or None if empty.

    Args:
        buffer: iterable of labels (str or None). None entries are ignored.
        min_votes: 贏家票數下限（6/9 HITL，Roy 拍板）— 票數不足回 None，
            防單幀誤判直接奪冠（OK 手勢也誤觸的修正之一）。
            預設 1 = 現行行為（只要有一票就能當贏家）。

    Returns:
        Winning label, or None when buffer is empty / winner has fewer
        than min_votes votes.
    """
    items = [x for x in buffer if x is not None]
    if not items:
        return None
    winner = max(set(items), key=items.count)
    if items.count(winner) < max(1, int(min_votes)):
        return None
    return winner
