"""LiDAR 360-degree obstacle detector — pure Python, no ROS2 dependency.

Analyzes LaserScan ranges array to detect obstacles in any direction.
"""
import math
from dataclasses import dataclass
from typing import List


@dataclass
class LidarObstacleResult:
    """Result of a single LiDAR scan analysis."""

    is_obstacle: bool
    distance_min: float       # meters (inf if no valid ranges)
    obstacle_ratio: float     # 0.0~1.0
    zone: str                 # "clear" / "warning" / "danger"
    direction_deg: float      # angle of closest obstacle (0=front, -180..+180)
    obstacle_count: int       # number of ranges below safety_distance


class LidarObstacleDetector:
    """Stateless 360-degree LiDAR obstacle detector.

    Parameters are constructor args so the class stays pure and testable.
    """

    def __init__(
        self,
        safety_distance_m: float = 0.5,
        warning_distance_m: float = 0.8,
        min_obstacle_points: int = 2,
        ignore_behind: bool = False,
    ):
        self.safety_distance_m = safety_distance_m
        self.warning_distance_m = warning_distance_m
        self.min_obstacle_points = min_obstacle_points
        self.ignore_behind = ignore_behind

    def detect(
        self,
        ranges: List[float],
        angle_min: float,
        angle_increment: float,
        range_min: float = 0.25,
        range_max: float = 8.0,
    ) -> LidarObstacleResult:
        """Analyze a LaserScan ranges array and return obstacle status.

        Args:
            ranges: 1D list of distances (meters). inf/nan/0 = invalid.
            angle_min: Start angle in radians.
            angle_increment: Angular step in radians.
            range_min: Minimum valid range (below = invalid).
            range_max: Maximum valid range (above = invalid).
        """
        min_dist = float("inf")
        min_angle = 0.0
        obstacle_count = 0
        valid_count = 0

        for i, r in enumerate(ranges):
            # Skip invalid readings
            if not math.isfinite(r) or r < range_min or r > range_max:
                continue

            angle_rad = angle_min + i * angle_increment
            # Normalize to -pi..+pi
            angle_norm = math.atan2(math.sin(angle_rad), math.cos(angle_rad))

            # Optional: skip rear arc (135..225 deg = roughly -pi*3/4..-pi*3/4)
            if self.ignore_behind:
                angle_deg = math.degrees(angle_norm)
                if abs(angle_deg) > 135.0:
                    continue

            valid_count += 1

            if r < min_dist:
                min_dist = r
                min_angle = angle_norm

            if r < self.safety_distance_m:
                obstacle_count += 1

        # No valid readings
        if valid_count == 0:
            return LidarObstacleResult(
                is_obstacle=False, distance_min=float("inf"),
                obstacle_ratio=0.0, zone="clear",
                direction_deg=0.0, obstacle_count=0,
            )

        obstacle_ratio = obstacle_count / valid_count
        direction_deg = math.degrees(min_angle)

        # Zone classification
        if obstacle_count >= self.min_obstacle_points and min_dist < self.safety_distance_m:
            zone = "danger"
        elif min_dist < self.warning_distance_m:
            zone = "warning"
        else:
            zone = "clear"

        return LidarObstacleResult(
            is_obstacle=zone == "danger",
            distance_min=min_dist,
            obstacle_ratio=obstacle_ratio,
            zone=zone,
            direction_deg=direction_deg,
            obstacle_count=obstacle_count,
        )
