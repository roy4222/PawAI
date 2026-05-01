"""Pure-Python LiDAR scan geometry helpers (no ROS dependency, testable standalone)."""
import math


def compute_front_min_distance(ranges, angle_min, angle_increment,
                               front_half_rad, range_min, range_max,
                               front_offset_rad=0.0):
    """取「Go2 物理前方」±front_half_rad 扇形內最小有效距離。

    範圍以 atan2 normalize 到 -π..+π，與 sllidar angle_min 起始（0 或 -π）無關。
    無有效點回傳 inf。

    Args:
        ranges: 1D list/iterable of distances（meters）。inf/nan/0 = invalid。
        angle_min: 起始角度 (rad)。
        angle_increment: 每點角度步進 (rad)。
        front_half_rad: 前方扇形半角度 (rad)。例如 ±30° 傳 π/6。
        range_min: 最小有效距離（小於視為自身遮蔽）。
        range_max: 最大有效距離。
        front_offset_rad: laser frame 中「Go2 物理前方」的角度偏移 (rad)。
            v8 mount yaw=π → 設 math.pi（Go2 前方 = laser ±180°）。
            預設 0（laser 0° = Go2 前方，傳統 mount 假設）。
    """
    min_dist = float("inf")
    for i, r in enumerate(ranges):
        if not math.isfinite(r) or r < range_min or r > range_max:
            continue
        angle = angle_min + i * angle_increment
        # Subtract offset before normalize so |angle_rel| ≤ front_half_rad
        # means "this beam points at Go2 physical front".
        angle_rel = math.atan2(math.sin(angle - front_offset_rad),
                               math.cos(angle - front_offset_rad))
        if abs(angle_rel) > front_half_rad:
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
