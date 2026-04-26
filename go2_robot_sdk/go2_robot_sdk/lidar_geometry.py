"""Pure-Python LiDAR scan geometry helpers (no ROS dependency, testable standalone)."""
import math


def compute_front_min_distance(ranges, angle_min, angle_increment,
                               front_half_rad, range_min, range_max):
    """取前方 ±front_half_rad 扇形內最小有效距離。

    範圍以 atan2 normalize 到 -π..+π，與 sllidar angle_min 起始（0 或 -π）無關。
    無有效點回傳 inf。

    Args:
        ranges: 1D list/iterable of distances（meters）。inf/nan/0 = invalid。
        angle_min: 起始角度 (rad)。
        angle_increment: 每點角度步進 (rad)。
        front_half_rad: 前方扇形半角度 (rad)。例如 ±30° 傳 π/6。
        range_min: 最小有效距離（小於視為自身遮蔽）。
        range_max: 最大有效距離。
    """
    min_dist = float("inf")
    for i, r in enumerate(ranges):
        if not math.isfinite(r) or r < range_min or r > range_max:
            continue
        angle = angle_min + i * angle_increment
        angle_norm = math.atan2(math.sin(angle), math.cos(angle))
        if abs(angle_norm) > front_half_rad:
            continue
        if r < min_dist:
            min_dist = r
    return min_dist


def classify_zone(distance_m, danger_m, slow_m):
    """距離 → zone 名稱（嚴格小於閾值）。

    Returns: "danger" | "slow" | "clear"
    """
    if distance_m < danger_m:
        return "danger"
    if distance_m < slow_m:
        return "slow"
    return "clear"
